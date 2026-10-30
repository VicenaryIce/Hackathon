"""Hype score (0-100), phase and prediction per product per day.

The detector walks through each product day by day and keeps a small state
(its sales history, whether it is bursting, its peak). Because it never
looks ahead, running it on data up to day N gives exactly the same answer
for day N as running it on all 19 days. backtest.py checks this.

Phases (Dutch labels in the UI):
  geen_data  "Geen data"  sales numbers not trustworthy yet (truncated source)
  opwarmen   "Opwarmen"   only one measurement, no trend yet
  stabiel    "Stabiel"    flat daily sales
  opbouw     "Opbouw"     build-up: sales rising + another signal
  burst      "Burst"      daily sales >= 2x the product's own baseline
  afkoeling  "Afkoeling"  after a burst, sales fell to <= 60% of the peak
"""
from __future__ import annotations

import math
from collections import deque
from dataclasses import dataclass, field
from statistics import median

import numpy as np
import pandas as pd

from . import config, nl
from .mapping import BRAND_ACCOUNTS

PHASE_LABELS = {
    "geen_data": "Geen data",
    "opwarmen": "Opwarmen",
    "stabiel": "Stabiel",
    "opbouw": "Opbouw",
    "burst": "Burst",
    "afkoeling": "Afkoeling",
}


def _isnan(x) -> bool:
    return x is None or (isinstance(x, float) and math.isnan(x))


@dataclass
class ProductState:
    history: list[float] = field(default_factory=list)   # valid sales/day measurements
    phase: str = "geen_data"
    pre_burst_baseline: float = float("nan")
    peak: float = float("nan")
    peak_date: pd.Timestamp | None = None
    burst_start: pd.Timestamp | None = None
    last_burst_day: pd.Timestamp | None = None
    decay_start: pd.Timestamp | None = None
    opbouw_recent: deque = field(default_factory=lambda: deque(maxlen=config.ALERT_LOOKBACK_OBS))
    last: dict | None = None


def noise_floor(res: float, baseline: float, mult: float, min_units: float) -> float:
    """Minimum excess (units/day) that is clearly above the counter's noise.
    Rounded counters: `mult` rounding steps. Exact counters: `mult` x sqrt(baseline)
    (Poisson noise of small counts), but at least `min_units`."""
    if res > 1:
        return mult * res
    return max(float(min_units), mult * math.sqrt(max(baseline, 1.0)))


def impact(level: float) -> float:
    """0.4 for tiny sellers up to 1.0 at 1,000+ per day (log scale)."""
    vol = math.log10(1 + max(level, 0.0)) / math.log10(1 + config.IMPACT_FULL_AT)
    return config.IMPACT_FLOOR + (1 - config.IMPACT_FLOOR) * min(1.0, vol)


def _rising_streak(values: list[float], res: float) -> int:
    streak = 0
    for i in range(len(values) - 1, 0, -1):
        if values[i] > values[i - 1] + res / 2:
            streak += 1
        else:
            break
    return streak


def _brand(handle) -> str | None:
    return BRAND_ACCOUNTS[handle]["brand"] if isinstance(handle, str) and handle in BRAND_ACCOUNTS else None


def _confidence_pct(n_signals: int, persistence: int) -> int:
    """A-priori confidence of an alert: more independent signals = more confident.
    The backtest (backtest.json) reports how often alerts actually came true."""
    pct = 35 + 15 * max(0, n_signals - 2) + (10 if persistence >= config.ALERT_LOOKBACK_OBS else 0)
    return int(min(85, pct))


def evaluate_product(rows: pd.DataFrame) -> list[dict]:
    """rows: one product's panel rows sorted by date (one per calendar day)."""
    st = ProductState()
    seg = None
    out: list[dict] = []
    for _, r in rows.iterrows():
        day = r["date"]
        # After a data-source change the old numbers are on another scale: start over.
        if r["has_row"] and r["sold_valid"]:
            if seg is not None and int(r["seg"]) != seg:
                st = ProductState()
            seg = int(r["seg"])
        brand = _brand(r["handle"])
        level = r["sales_per_day"]
        res = r["resolution"] if not _isnan(r["resolution"]) else 1.0

        # ---------------- no usable sales measurement today ----------------
        if not r["has_row"] or _isnan(level):
            if st.last is not None and st.history:
                carried = dict(st.last)
                carried["date"] = day
                carried["stale_days"] = int((day - st.last["measured_on"]).days)
                carried["alert"] = False
                carried["is_measurement"] = False
                out.append(carried)
                continue
            gated = bool(r["has_row"]) and not bool(r["sold_valid"]) and not _isnan(r["sold_raw"])
            first = bool(r["sold_valid"])
            if first:
                why = (f"Eerste betrouwbare meting ({nl.num(r['sold_clean'])} stuks verkocht in totaal). "
                       "Vanaf de volgende meting ziet de radar het verloop.")
                phase = "opwarmen"
            elif gated:
                why = "Verkoopcijfers van deze dag zijn afgekapt tot 1 cijfer: de radar wacht op betrouwbare data."
                phase = "geen_data"
            else:
                why = "Nog geen betrouwbare verkoopmeting."
                phase = "geen_data"
            out.append(_blank(day, phase, why))
            continue

        # ---------------- signals ----------------
        hist = st.history[-config.BASELINE_WINDOW:]
        n_hist = len(st.history)
        baseline = float(median(hist)) if len(hist) >= 1 else float("nan")
        has_base = not _isnan(baseline)
        excess = level - baseline if has_base else float("nan")
        if has_base:
            ratio = level / baseline if baseline > 0 else (float("inf") if level > 0 else 1.0)
        else:
            ratio = float("nan")
        noise_base = baseline if has_base else level
        burst_floor = noise_floor(res, noise_base, config.BURST_NOISE_MULT, config.BURST_MIN_EXCESS_UNITS)
        mom_floor = noise_floor(res, noise_base, config.MOMENTUM_NOISE_MULT, config.MOMENTUM_MIN_EXCESS_UNITS)
        burst_cond = has_base and ratio >= config.BURST_RATIO and excess >= burst_floor
        momentum = has_base and ratio >= config.MOMENTUM_RATIO and excess >= mom_floor
        seq = st.history + [level]
        streak = _rising_streak(seq, res)
        streak_rise = level - seq[-1 - streak] if streak > 0 else 0.0
        steady_rise = streak >= config.RISING_STREAK_MIN and streak_rise >= mom_floor
        sales_up = momentum or steady_rise

        rev2 = r["reviews_2d"]
        rate_before = r["review_rate_before"]
        quiet = _isnan(rate_before) or rate_before <= config.REVIEW_QUIET_MAX_PER_DAY
        review_jump = (not _isnan(rev2)) and rev2 >= config.REVIEW_JUMP_MIN and quiet

        cadence = r["video_cadence"]
        video_on = (not _isnan(cadence)) and cadence >= config.VIDEO_CADENCE_MIN
        likes_on = (not _isnan(r["likes_change_3d"])) and r["likes_change_3d"] > 0
        other_signal = review_jump or video_on or likes_on
        n_signals = int(sales_up) + int(review_jump) + int(video_on) + int(likes_on)

        # ---------------- phase (state machine) ----------------
        prev_phase = st.phase
        new_wave = False
        if prev_phase == "burst":
            if level > st.peak:
                st.peak, st.peak_date = level, day
            pre_floor = noise_floor(res, st.pre_burst_baseline, config.BURST_NOISE_MULT,
                                    config.BURST_MIN_EXCESS_UNITS)
            still = (level > config.DECAY_MAX_SHARE_OF_PEAK * st.peak
                     and level - st.pre_burst_baseline >= pre_floor)
            if still:
                phase = "burst"
                st.last_burst_day = day
            else:
                phase = "afkoeling"
                st.decay_start = day
        elif prev_phase == "afkoeling":
            last_level = st.history[-1] if st.history else float("nan")
            days_since_burst = (day - st.last_burst_day).days if st.last_burst_day is not None else 99
            if burst_cond and level > last_level:
                phase, new_wave = "burst", True
            elif days_since_burst > config.DECAY_LOOKBACK_DAYS:
                phase = "opbouw" if (sales_up and other_signal) else "stabiel"
            else:
                phase = "afkoeling"   # falling after a burst is never new hype
        else:
            if burst_cond:
                phase = "burst"
            elif (sales_up and other_signal) or (steady_rise and streak >= 3):
                # Build-up needs the product's OWN sales to rise. Reviews and brand
                # videos only confirm (in this data reviews lag sales, see insights).
                phase = "opbouw"
            elif has_base:
                phase = "stabiel"
            else:
                phase = "opwarmen"

        if phase == "burst" and prev_phase != "burst":
            st.pre_burst_baseline = baseline
            st.peak, st.peak_date = level, day
            st.burst_start = day
            st.last_burst_day = day

        # ---------------- alert / prediction ----------------
        st.opbouw_recent.append(phase == "opbouw")
        persistence = sum(st.opbouw_recent)
        alert = phase == "opbouw" and (persistence >= config.ALERT_PERSISTENCE or n_signals >= 3)
        confidence = _confidence_pct(n_signals, persistence) if alert else None

        # ---------------- score = 100 x signal strength x impact ----------------
        if phase == "burst":
            s_sales = 1.0
        elif phase == "afkoeling":
            s_sales = 0.5 * min(1.0, level / st.peak) if st.peak and st.peak > 0 else 0.0
        elif momentum:
            s_sales = 0.5 + 0.5 * min(1.0, max(0.0, (ratio - config.MOMENTUM_RATIO)
                                                 / (config.BURST_RATIO - config.MOMENTUM_RATIO)))
        elif steady_rise:
            s_sales = 0.5
        else:
            s_sales = 0.0
        if steady_rise and streak >= 3:
            s_sales = min(1.0, s_sales + 0.15)
        moves = sales_up or phase == "burst"          # brand buzz only counts if the product moves
        s_rev = (1.0 if rev2 >= 3 else 0.7) if review_jump else 0.0
        s_vid = min(1.0, max(0.0, cadence / config.VIDEO_CADENCE_MIN)) if (moves and not _isnan(cadence)) else 0.0
        s_likes = 1.0 if (likes_on and moves) else 0.0
        w = config.WEIGHTS
        strength = w["sales"] * s_sales + w["reviews"] * s_rev + w["video"] * s_vid + w["likes"] * s_likes
        # fewer previous measurements = less certain baseline
        history_mult = 0.8 if n_hist <= 1 else 0.9 if n_hist == 2 else 1.0
        score = int(round(100 * strength * impact(level) * history_mult))
        if phase == "afkoeling":
            score = min(score, config.DECAY_SCORE_CAP)

        days_in_burst = (day - st.burst_start).days if (phase == "burst" and st.burst_start is not None) else None
        big = (not _isnan(st.pre_burst_baseline)) and st.pre_burst_baseline >= config.BIG_PRODUCT_MIN_PER_DAY
        expected_days = None
        if phase == "burst":
            total = config.BIG_PEAK_DAYS if big else config.MICRO_PULSE_DAYS
            expected_days = max(1, total - (days_in_burst or 0))

        rec = {
            "date": day,
            "measured_on": day,
            "is_measurement": True,
            "stale_days": 0,
            "phase": phase,
            "score": score,
            "alert": bool(alert),
            "confidence": confidence,
            "level": float(level),
            "baseline": baseline,
            "ratio": ratio if has_base else None,
            "excess": excess,
            "resolution": res,
            "n_history": n_hist,
            "streak": streak,
            "momentum": bool(momentum),
            "steady_rise": bool(steady_rise),
            "sales_up": bool(sales_up),
            "burst_cond": bool(burst_cond),
            "impact": round(impact(level), 3),
            "reviews_2d": rev2,
            "review_jump": bool(review_jump),
            "video_cadence": cadence,
            "video_on": bool(video_on),
            "likes_on": bool(likes_on),
            "n_signals": n_signals,
            "peak": st.peak if phase in ("burst", "afkoeling") else None,
            "peak_date": st.peak_date if phase in ("burst", "afkoeling") else None,
            "pre_burst_baseline": st.pre_burst_baseline if phase in ("burst", "afkoeling") else None,
            "days_in_burst": days_in_burst,
            "expected_days": expected_days,
            "big_product": bool(big),
            "new_wave": new_wave,
        }
        rec["why"] = explain(rec, brand, r)
        rec["prediction"] = predict_text(rec, brand)

        st.phase = phase
        st.history.append(float(level))
        st.last = rec
        out.append(rec)
    return out


def _blank(day, phase: str, why: str) -> dict:
    return {
        "date": day, "measured_on": day, "is_measurement": False, "stale_days": 0,
        "phase": phase, "score": 0, "alert": False, "confidence": None,
        "level": None, "baseline": None, "ratio": None, "excess": None, "resolution": None,
        "n_history": 0, "streak": 0, "momentum": False, "steady_rise": False, "sales_up": False,
        "burst_cond": False, "impact": None,
        "reviews_2d": None, "review_jump": False, "video_cadence": None, "video_on": False,
        "likes_on": False, "n_signals": 0, "peak": None, "peak_date": None,
        "pre_burst_baseline": None, "days_in_burst": None, "expected_days": None,
        "big_product": False, "new_wave": False, "why": why, "prediction": None,
    }


# --------------------------------------------------------------------------
# Plain-language explanations (Dutch, shown in the UI)
# --------------------------------------------------------------------------
def videos_per_day(c: float) -> str:
    """1.0 -> '1 video per dag', 1.33 -> '1,3 video's per dag'"""
    txt = nl.smart(round(c, 1))
    return f"{txt} {'video' if txt == '1' else 'video’s'} per dag"


def _signal_bits(rec: dict, brand: str | None) -> list[str]:
    bits = []
    if rec["review_jump"]:
        bits.append(f"reviews +{nl.smart(rec['reviews_2d'])} in 2 dagen (normaal hooguit 1 per dag)")
    if rec["video_on"] and brand:
        bits.append(f"{brand} post {videos_per_day(rec['video_cadence'])}")
    if rec["likes_on"] and brand:
        bits.append(f"de likes van {brand} stijgen")
    return bits


def explain(rec: dict, brand: str | None, r) -> str:
    level, base = rec["level"], rec["baseline"]
    phase = rec["phase"]
    if phase == "burst":
        pre = rec["pre_burst_baseline"]
        mult = level / pre if pre and pre > 0 else None
        head = (f"Verkoopt nu {nl.smart(level)} per dag"
                + (f": {nl.times(mult)} het eigen normale niveau ({nl.smart(pre)} per dag)." if mult else
                   f", tegen normaal {nl.smart(pre)} per dag."))
        if rec["new_wave"]:
            head = "Tweede golf! " + head
        bits = _signal_bits(rec, brand)
        if rec["peak"] and rec["peak"] > level:
            bits.append(f"piek tot nu {nl.smart(rec['peak'])} per dag op {nl.date(rec['peak_date'])}")
        return head + (" " + _sentence(bits) if bits else "")
    if phase == "afkoeling":
        peak = rec["peak"]
        drop = 1 - level / peak if peak else 0
        txt = (f"Verkoop zakt naar {nl.smart(level)} per dag ({nl.num(100 * drop)}% onder de piek van "
               f"{nl.smart(peak)} op {nl.date(rec['peak_date'])}). Dit is afkoeling, geen nieuwe hype.")
        if brand and not _isnan(rec["video_cadence"]):
            if rec["video_cadence"] >= 0.5:
                txt += f" {brand} post nog {videos_per_day(rec['video_cadence'])}, maar de vraag zakt toch."
            else:
                txt += f" {brand} post (bijna) niet meer."
        return txt
    if phase == "opbouw":
        bits = []
        if rec["momentum"]:
            bits.append(f"verkoop stijgt van {nl.smart(base)} naar {nl.smart(level)} per dag")
        elif rec["steady_rise"]:
            bits.append(f"verkoop stijgt {rec['streak']} metingen op rij (nu {nl.smart(level)} per dag)")
        bits += _signal_bits(rec, brand)
        txt = "Opbouw: " + _sentence(bits, capital=False)
        if rec["alert"]:
            txt += " Verwacht: explosie binnen 1 tot 3 dagen."
        return txt
    if phase == "opwarmen":
        return f"Eerste verkoopmeting: {nl.smart(level)} per dag. Vanaf de volgende meting ziet de radar het verloop."
    # stabiel
    txt = f"Stabiel rond {nl.smart(base)} per dag; geen opbouwsignalen."
    if rec["video_on"] and brand:
        txt = (f"Stabiel rond {nl.smart(base)} per dag. {brand} post {videos_per_day(rec['video_cadence'])}, "
               "maar dit product beweegt niet mee.")
    elif rec["review_jump"]:
        txt = f"Stabiel rond {nl.smart(base)} per dag. Reviews lopen op, verkoop (nog) niet."
    if rec["resolution"] and rec["resolution"] > 1 and level is not None and level <= rec["resolution"] * 2:
        txt += f" (TikTok toont dit getal per {nl.num(rec['resolution'])}, kleine schommelingen zijn ruis.)"
    return txt


def _sentence(bits: list[str], capital: bool = True) -> str:
    if not bits:
        return ""
    if len(bits) == 1:
        s = bits[0]
    else:
        s = ", ".join(bits[:-1]) + " en " + bits[-1]
    if capital and not s.startswith("e.l.f."):   # brand names keep their own spelling
        s = s[0].upper() + s[1:]
    return s + "."


def predict_text(rec: dict, brand: str | None) -> str | None:
    if rec["alert"]:
        return f"Explosie verwacht binnen 1 tot 3 dagen (betrouwbaarheid {rec['confidence']}%)"
    if rec["phase"] == "burst":
        who = brand or "de verkoper"
        return (f"Nog ongeveer {rec['expected_days']} dag{'en' if rec['expected_days'] != 1 else ''} verhoogd, "
                f"daarna afkoeling, tenzij {who} blijft posten")
    if rec["phase"] == "afkoeling":
        return "Afkoeling: retourgolf verwacht, stuur tips om het product goed te gebruiken"
    return None


def score_panel(panel: pd.DataFrame) -> pd.DataFrame:
    """Run the detector for every product over the whole panel."""
    results = []
    for title, rows in panel.groupby("title", sort=True):
        for rec in evaluate_product(rows.sort_values("date")):
            rec["title"] = title
            results.append(rec)
    return pd.DataFrame(results)
