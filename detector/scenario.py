"""Hype scenario per product: "what if it goes viral, and how likely is that?"

The Voorspelling tab answers three questions per product, looking forward:

1. NU         normal orders per day next week (momentum model, momentum.py)
2. ALS VIRAAL how many parcels if it goes viral: peak per day and extra in total.
              Learned from the real hypes in the data: during a burst, orders
              jumped to `peak_mult` x the normal level for `days` days.
              Only bursts on products that already sold >= BIG_BASE per day are
              used for the multipliers: on tiny products (0-3 per day) a ratio
              like "16x" is noise.
3. WANNEER    a date cannot be predicted (in the backtest no signal showed up
              before a burst). We give:
              - the live status from the radar (burst now / build-up / nothing),
              - the chance of a hype in the next 7 days, from how often this
                product type, and this product itself, went viral in the clean
                days (smoothed towards the overall rate, so 0 bursts != 0%).
              Once the radar sees a burst, the parcels arrive 1-3 days later.

Everything is a first estimate from 7 hypes in 12 clean days.
"""
from __future__ import annotations

import math
import statistics as st

from . import config

BIG_BASE = 50            # orders/day before the burst for it to count in the multipliers
TYPE_PRIOR_DAYS = 100    # smoothing of the per-type rate towards the overall rate (in product-days)
PRODUCT_PRIOR_DAYS = 30  # smoothing of the per-product rate towards its type rate
MAX_WAVE_DAYS = 7
LIVE_PHASES = ("stabiel", "opbouw", "burst", "afkoeling")


def _waves(info: dict, events: list, dates: list) -> list[dict]:
    """Measure every burst: peak multiple, days elevated, extra orders, day-by-day shape."""
    waves = []
    for e in events:
        p = info[e["id"]]
        t = p["timeline"]
        i = dates.index(e["date"])
        pre = t["pre_burst_baseline"][i] or t["baseline"][i] or 0
        sales = t["sales_filled"]
        shape, extra, days = [], 0.0, 0
        for k in range(MAX_WAVE_DAYS):
            j = i + k
            if j >= len(dates) or sales[j] is None:
                break
            shape.append(sales[j] / pre if pre else None)
            if sales[j] > pre:
                extra += sales[j] - pre
                days += 1
            elif k > 0:
                break
        peak = max((s for s in sales[i:i + days] if s is not None), default=None)
        waves.append({"id": e["id"], "date": e["date"], "product": p["short"], "base": pre, "peak": peak,
                      "peak_mult": (peak / pre) if pre and peak else None,
                      "extra": extra, "extra_days_of_base": (extra / pre) if pre else None,
                      "days": days, "shape": shape, "big": pre >= BIG_BASE})
    return waves


def _range(vals):
    vals = [v for v in vals if v is not None]
    return {"low": min(vals), "mid": st.median(vals), "high": max(vals)} if vals else None


def _shape(big: list[dict]) -> list[float]:
    """Median multiple of normal on day 0, 1, 2 ... after a hype starts."""
    out = []
    for k in range(MAX_WAVE_DAYS):
        vals = [w["shape"][k] for w in big if k < len(w["shape"]) and w["shape"][k] is not None]
        if len(vals) < 2:
            break
        out.append(st.median(vals))
    return out


def build_scenarios(info: dict, backtest: dict, momentum: dict, dates: list) -> dict:
    first_live = backtest.get("first_live_day") or dates[0]
    i0 = dates.index(first_live) if first_live in dates else 0
    waves = _waves(info, backtest["events"], dates)
    big = [w for w in waves if w["big"]]
    mult = _range([w["peak_mult"] for w in big])
    extra = _range([w["extra_days_of_base"] for w in big])
    dur = _range([w["days"] for w in big])
    shape = _shape(big)

    # how often did each product / type go viral in the clean days?
    live_days, bursts_by_id = {}, {}
    for pid, p in info.items():
        t = p["timeline"]
        live_days[pid] = sum(1 for i in range(i0, len(dates)) if t["phase"][i] in LIVE_PHASES and t["measured"][i])
    for e in backtest["events"]:
        bursts_by_id[e["id"]] = bursts_by_id.get(e["id"], 0) + 1
    total_days = sum(live_days.values()) or 1
    overall = len(backtest["events"]) / total_days
    by_type = {}
    for pid, p in info.items():
        d = by_type.setdefault(p["type"], {"label": p["type_label"], "days": 0, "bursts": 0})
        d["days"] += live_days[pid]
        d["bursts"] += bursts_by_id.get(pid, 0)
    for d in by_type.values():
        d["rate"] = (d["bursts"] + TYPE_PRIOR_DAYS * overall) / (d["days"] + TYPE_PRIOR_DAYS)
        d["week_pct"] = 100 * (1 - (1 - d["rate"]) ** 7)

    last = momentum["days"][-1]
    now = {p["id"]: p for p in last["products"]}
    lo, hi = config.ORDER_TO_DOOR_DAYS
    rows = []
    for pid, p in info.items():
        m = now.get(pid)
        if not m or m["phase"] == "te_weinig" or m["mid"] < 1:
            continue
        normal = m["mid"]
        tr = by_type[p["type"]]["rate"]
        rate = (bursts_by_id.get(pid, 0) + PRODUCT_PRIOR_DAYS * tr) / (live_days[pid] + PRODUCT_PRIOR_DAYS)
        chance = 1 - (1 - rate) ** 7
        status = p["timeline"]["phase"][-1]
        viral = {"peak_low": normal * mult["low"], "peak": normal * mult["mid"], "peak_high": normal * mult["high"],
                 "extra_low": normal * extra["low"], "extra": normal * extra["mid"], "extra_high": normal * extra["high"],
                 "days_low": dur["low"], "days": dur["mid"], "days_high": dur["high"]}
        rows.append({
            "id": pid, "normal": normal, "normal_low": m["low"], "normal_high": m["high"], "trend": m["phase"],
            "parcel_size": m["parcel_size"], "viral": viral,
            "chance_week_pct": 100 * chance, "type_chance_week_pct": by_type[p["type"]]["week_pct"],
            "went_viral_before": bursts_by_id.get(pid, 0),
            "status": status if status in ("burst", "opbouw", "afkoeling") else "rustig",
            "expected_extra": chance * viral["extra"],
        })
    rows.sort(key=lambda r: -r["expected_extra"])
    return {
        "as_of": last["date"],
        "delivery_days": [lo, hi],
        "parcels_per_driver": config.PARCELS_PER_DRIVER,
        "model": {"peak_mult": mult, "extra_days_of_base": extra, "days": dur, "shape": shape,
                  "n_big": len(big), "n_all": len(waves), "big_base": BIG_BASE,
                  "overall_week_pct": 100 * (1 - (1 - overall) ** 7), "clean_from": first_live},
        "types": sorted(({"type": k, **v} for k, v in by_type.items()), key=lambda d: -d["week_pct"]),
        "waves": waves,
        "totals": {"normal": sum(r["normal"] for r in rows), "expected_extra_week": sum(r["expected_extra"] for r in rows)},
        "products": rows,
    }
