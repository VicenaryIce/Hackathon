"""Honest backtest: replay the radar day by day using only data up to that day.

1. Walk-forward: for every day N, run the full pipeline on data <= N and keep
   the radar's output for day N.
2. Leakage check: that output must be identical to the full run's output for
   day N. If anything peeked into the future, this check fails.
3. Score the alerts against what really happened: did a burst follow within
   1-3 days? How many bursts were seen coming, and how early?
4. Compare with one-signal rules ("only followers", "only videos", ...).
"""
from __future__ import annotations

import math

import pandas as pd

from . import config
from .pipeline import burst_onsets, run_pipeline

CHECK_COLUMNS = ["phase", "score", "alert", "confidence", "level", "baseline"]


def walk_forward(raw_products: pd.DataFrame, raw_accounts: pd.DataFrame) -> pd.DataFrame:
    days = sorted(raw_products["date"].unique())
    rows = []
    for day in days:
        run = run_pipeline(raw_products[raw_products["date"] <= day],
                           raw_accounts[raw_accounts["date"] <= day])
        rows.append(run.scored[run.scored["date"] == day])
    return pd.concat(rows, ignore_index=True)


def _same(a, b) -> bool:
    if isinstance(a, float) and isinstance(b, float) and math.isnan(a) and math.isnan(b):
        return True
    if a is None and b is None:
        return True
    if isinstance(a, float) and isinstance(b, float):
        return abs(a - b) < 1e-9
    try:
        if pd.isna(a) and pd.isna(b):
            return True
    except (TypeError, ValueError):
        pass
    return a == b


def leakage_check(full: pd.DataFrame, walk: pd.DataFrame) -> dict:
    """Day-N output of the walk-forward run must equal the full run's day-N output.

    Rows only in the full run are fine if the product simply did not exist yet
    on that day (it first appears in a later snapshot)."""
    merged = full.merge(walk, on=["title", "date"], suffixes=("_full", "_walk"), how="outer", indicator=True)
    only_walk = int((merged["_merge"] == "right_only").sum())
    only_full = merged[merged["_merge"] == "left_only"]
    unexpected_full = int((only_full["phase_full"] != "geen_data").sum())
    both = merged[merged["_merge"] == "both"]
    mismatches = []
    for col in CHECK_COLUMNS:
        for _, r in both.iterrows():
            if not _same(r[f"{col}_full"], r[f"{col}_walk"]):
                mismatches.append({"title": r["title"], "date": r["date"].strftime("%Y-%m-%d"), "column": col,
                                   "full": str(r[f"{col}_full"]), "walk": str(r[f"{col}_walk"])})
    return {
        "passed": only_walk == 0 and unexpected_full == 0 and not mismatches,
        "rows_compared": int(len(both)),
        "columns_compared": CHECK_COLUMNS,
        "rows_not_yet_in_data": int(len(only_full)),
        "n_mismatches": len(mismatches),
        "mismatches": mismatches[:20],
    }


def _evaluate(alert_rows: pd.DataFrame, onsets: pd.DataFrame, last_day: pd.Timestamp) -> dict:
    """Alerts (title, date) vs burst onsets."""
    horizon = pd.Timedelta(days=config.PREDICTION_HORIZON_DAYS)
    onset_days = {t: sorted(g["date"]) for t, g in onsets.groupby("title")}
    hits, false_alarms, open_alerts = [], [], []
    for _, a in alert_rows.iterrows():
        hit = [d for d in onset_days.get(a["title"], []) if a["date"] < d <= a["date"] + horizon]
        if hit:
            hits.append({"title": a["title"], "date": a["date"], "burst": hit[0]})
        elif a["date"] + horizon > last_day:
            open_alerts.append({"title": a["title"], "date": a["date"]})
        else:
            false_alarms.append({"title": a["title"], "date": a["date"]})
    events = []
    for _, e in onsets.iterrows():
        before = alert_rows[(alert_rows["title"] == e["title"]) & (alert_rows["date"] < e["date"])
                            & (alert_rows["date"] >= e["date"] - horizon)]
        lead = int((e["date"] - before["date"].min()).days) if len(before) else None
        events.append({"title": e["title"], "date": e["date"], "predicted": lead is not None, "lead_days": lead})
    resolved = len(hits) + len(false_alarms)
    predicted = [ev for ev in events if ev["predicted"]]
    return {
        "alerts": int(len(alert_rows)),
        "hits": len(hits),
        "false_alarms": len(false_alarms),
        "open": len(open_alerts),
        "precision": (len(hits) / resolved) if resolved else None,
        "events": len(events),
        "events_predicted": len(predicted),
        "recall": (len(predicted) / len(events)) if events else None,
        "avg_lead_days": (sum(ev["lead_days"] for ev in predicted) / len(predicted)) if predicted else None,
        "_hits": hits, "_false": false_alarms, "_open": open_alerts, "_events": events,
    }


def _persistent(flags: pd.Series, need: int, window: int) -> pd.Series:
    return flags.astype(int).rolling(window, min_periods=1).sum() >= need


def single_signal_rules(scored: pd.DataFrame, panel: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """Alert rows for simple one-signal rules, evaluated on measurement days."""
    m = scored[scored["is_measurement"]].merge(
        panel[["title", "date", "followers_change_3d", "followers_res"]], on=["title", "date"], how="left")
    m = m.sort_values(["title", "date"])
    rules = {}
    sales = m.groupby("title")["sales_up"].transform(
        lambda s: _persistent(s, config.ALERT_PERSISTENCE, config.ALERT_LOOKBACK_OBS))
    # Only judge rules where the radar is "live" (a baseline exists), like the real alerts.
    live = m["phase"].isin(["stabiel", "opbouw"])
    rules["Alleen verkoopstijging"] = m[live & sales.astype(bool)]
    rules["Alleen volgersgroei"] = m[live & (m["followers_change_3d"].fillna(0) > 0)]
    rules["Alleen video's (>= 1 per dag)"] = m[live & m["video_on"]]
    rules["Alleen reviewsprong"] = m[live & m["review_jump"]]
    return rules


def run_backtest(raw_products: pd.DataFrame, raw_accounts: pd.DataFrame, full) -> dict:
    walk = walk_forward(raw_products, raw_accounts)
    check = leakage_check(full.scored, walk)
    onsets = burst_onsets(full.scored)
    last_day = full.scored["date"].max()
    radar = _evaluate(full.scored[full.scored["alert"]], onsets, last_day)

    comparisons = []
    for name, rows in single_signal_rules(full.scored, full.panel).items():
        res = _evaluate(rows, onsets, last_day)
        comparisons.append({k: v for k, v in res.items() if not k.startswith("_")} | {"rule": name})

    lo, hi = config.ORDER_TO_DOOR_DAYS
    first_live = full.scored.loc[full.scored["phase"].isin(["stabiel", "opbouw", "burst", "afkoeling"]), "date"].min()

    def fmt(rows, keys):
        return [{k: (v.strftime("%Y-%m-%d") if isinstance(v, pd.Timestamp) else v) for k, v in r.items() if k in keys}
                for r in rows]

    return {
        "leakage_check": check,
        "first_live_day": first_live.strftime("%Y-%m-%d"),
        "horizon_days": config.PREDICTION_HORIZON_DAYS,
        "radar": {k: v for k, v in radar.items() if not k.startswith("_")},
        "events": fmt(radar["_events"], {"title", "date", "predicted", "lead_days"}),
        "hits": fmt(radar["_hits"], {"title", "date", "burst"}),
        "false_alarms": fmt(radar["_false"], {"title", "date"}),
        "open_alerts": fmt(radar["_open"], {"title", "date"}),
        "detection": {
            "events_detected_on_first_day": len(radar["_events"]),
            "parcel_warning_days": [lo, hi],
            "note": (f"Elke burst staat op de eerste dag van de piek op de radar. Bestellingen van die dag "
                     f"worden {lo}-{hi} dagen later bezorgd, dus PostNL heeft {lo}-{hi} dagen voorsprong "
                     "op de extra pakketten (aanname)."),
        },
        "comparisons": comparisons,
        "model": ("Geen extra model toegevoegd: met zo weinig bursts (en geen enkel signaal dat er in deze "
                  "data vooraf consequent aan voorafging) zou een getraind model alleen ruis leren."),
    }
