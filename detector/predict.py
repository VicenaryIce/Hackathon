"""Parcel forecast and return-risk heuristic, built on the radar's state.

ASSUMPTIONS (also shown in the UI and README):
- 1 order = 1 parcel.
- This is US TikTok Shop data, so the numbers illustrate the method; they
  are not Dutch volumes.
- Return risk is a heuristic: the data has no returns column.
"""
from __future__ import annotations

import math

from . import config
from .score import noise_floor


def _num(x) -> float:
    return 0.0 if x is None or (isinstance(x, float) and math.isnan(x)) else float(x)


def forecast(rec: dict) -> dict:
    """Expected parcels per day for the next FORECAST_DAYS days, from day N's state."""
    phase = rec["phase"]
    level = _num(rec.get("level"))
    base = rec.get("baseline")
    pre = rec.get("pre_burst_baseline")
    days = config.FORECAST_DAYS
    hl = config.DECAY_HALF_LIFE_DAYS

    if phase == "burst":
        normal = _num(pre)
        excess = max(0.0, level - normal)
        remain = rec.get("expected_days") or 1
        extra = [excess if k <= remain else excess * 0.5 ** ((k - remain) / hl) for k in range(1, days + 1)]
    elif phase == "afkoeling":
        normal = min(level, _num(pre)) if pre is not None else level
        excess = max(0.0, level - normal)
        extra = [excess * 0.5 ** (k / hl) for k in range(1, days + 1)]
    elif rec.get("alert"):
        normal = _num(base) if base is not None else level
        p = (rec.get("confidence") or 0) / 100
        res = rec.get("resolution") or 1.0
        burst_extra = max((config.BURST_RATIO - 1) * normal,
                          noise_floor(res, normal, config.BURST_NOISE_MULT, config.BURST_MIN_EXCESS_UNITS))
        dur = config.BIG_PEAK_DAYS if normal >= config.BIG_PRODUCT_MIN_PER_DAY else config.MICRO_PULSE_DAYS
        extra = []
        for k in range(1, days + 1):
            # burst starts on day 1, 2 or 3 (equally likely) and lasts `dur` days
            active = sum(1 for s in (1, 2, 3) if s <= k < s + dur) / 3
            extra.append(p * burst_extra * active)
    else:
        normal = _num(base) if base is not None and phase in ("stabiel", "opbouw") else level
        extra = [0.0] * days

    per_parcel = config.PARCELS_PER_ORDER
    return {
        "normal": round(normal * per_parcel, 1),
        "extra": [round(e * per_parcel, 1) for e in extra],
        "expected": [round((normal + e) * per_parcel, 1) for e in extra],
    }


# --------------------------------------------------------------------------
# Return risk (HEURISTIC, not measured)
# --------------------------------------------------------------------------
_TYPE_RISK = {
    "fashion": (25, "pasvorm valt vaak anders uit"),
    "lip": (20, "kleur/tint valt vaak anders uit"),
    "makeup": (20, "kleur/tint valt vaak anders uit"),
    "fragrance": (20, "geur valt vaak tegen"),
    "hair": (15, "kleur/lengte valt vaak anders uit"),
    "skincare": (10, "werkt niet voor elk huidtype"),
    "body": (10, "geur/textuur valt soms tegen"),
    "other": (10, ""),
    "gummies": (5, "goedkoop verbruiksproduct"),
    "patch": (5, "goedkoop verbruiksproduct"),
}
_PHASE_RISK = {
    "afkoeling": (35, "hype voorbij: spijtaankopen komen terug"),
    "burst": (20, "hype-kopers kopen impulsief"),
    "opbouw": (10, "vroege hype-kopers"),
}


def return_risk(rec: dict, info: dict) -> dict:
    pts, reasons = 0, []
    p = _PHASE_RISK.get(rec["phase"])
    if p:
        pts += p[0]
        reasons.append(p[1])
    t_pts, t_reason = _TYPE_RISK.get(info["type"], (10, ""))
    pts += t_pts
    if t_reason:
        reasons.append(t_reason)
    price = info.get("price")
    if price is not None and price >= 50:
        pts += 15
        reasons.append("duurder product (vanaf $50)")
    elif price is not None and price >= 20:
        pts += 8
    if info.get("n_colors", 0) >= 3:
        pts += 10
        reasons.append(f"{info['n_colors']} tinten/kleuren om uit te kiezen")
    pts = min(100, pts)
    label = "hoog" if pts >= 60 else "middel" if pts >= 35 else "laag"
    return {"score": pts, "label": label, "reasons": reasons}
