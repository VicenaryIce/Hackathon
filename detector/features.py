"""Per product, per day: the raw signals the hype score is built from.

Every value at day D only uses snapshots from day D and earlier.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import config


def _asof(dates: list[pd.Timestamp], values: list[float], when: pd.Timestamp) -> tuple[pd.Timestamp | None, float]:
    """Last (date, value) with date <= when, or (None, nan)."""
    best_d, best_v = None, np.nan
    for d, v in zip(dates, values):
        if d > when:
            break
        best_d, best_v = d, v
    return best_d, best_v


def _window_change(dates, values, when, days) -> tuple[float, float]:
    """(change, days_between) between the last value <= when and the last value <= when-days."""
    d_now, v_now = _asof(dates, values, when)
    d_then, v_then = _asof(dates, values, when - pd.Timedelta(days=days))
    if d_now is None or d_then is None or d_now == d_then or pd.isna(v_now) or pd.isna(v_then):
        return np.nan, np.nan
    return float(v_now - v_then), float((d_now - d_then).days)


def account_signals(accounts: pd.DataFrame, calendar: list[pd.Timestamp]) -> pd.DataFrame:
    """Brand-level signals per handle per calendar day."""
    rows = []
    for handle, grp in accounts.groupby("handle", sort=True):
        grp = grp.sort_values("date")
        dts = list(grp["date"])
        vids, likes, foll = list(grp["videos_count_clean"]), list(grp["likes_clean"]), list(grp["followers"])
        for day in calendar:
            d_now, v_now = _asof(dts, vids, day)
            dv, gap = _window_change(dts, vids, day, config.VIDEO_WINDOW_DAYS)
            dv_prev, gap_prev = _window_change(dts, vids, day - pd.Timedelta(days=config.VIDEO_WINDOW_DAYS),
                                               config.VIDEO_WINDOW_DAYS)
            dl, _ = _window_change(dts, likes, day, config.VIDEO_WINDOW_DAYS)
            # followers can legitimately go down; use the last non-missing value
            f_dts = [d for d, f in zip(dts, foll) if not pd.isna(f)]
            f_vals = [f for f in foll if not pd.isna(f)]
            df_, _ = _window_change(f_dts, f_vals, day, config.VIDEO_WINDOW_DAYS)
            _, f_now = _asof(f_dts, f_vals, day)
            _, l_now = _asof(dts, likes, day)
            rows.append({
                "handle": handle,
                "date": day,
                "account_stale_days": np.nan if d_now is None else float((day - d_now).days),
                "videos_total": v_now,
                "video_cadence": dv / gap if gap and not pd.isna(gap) else np.nan,
                "video_cadence_prev": dv_prev / gap_prev if gap_prev and not pd.isna(gap_prev) else np.nan,
                "likes_total": l_now,
                "likes_change_3d": dl,
                "followers": f_now,
                "followers_change_3d": df_,
                "followers_res": np.nan if pd.isna(f_now) else (100_000.0 if f_now >= 1_000_000 else 100.0),
            })
    return pd.DataFrame(rows)


def product_signals(products: pd.DataFrame) -> pd.DataFrame:
    """Signals at each product snapshot (row-level)."""
    out = []
    for title, grp in products.groupby("title", sort=True):
        grp = grp.sort_values("date")

        # --- sales per day (valid rows only, same segment, normalised by gap) ---
        prev_date, prev_sold, prev_seg = None, np.nan, None
        # --- corrected cumulative review count (wrap-aware deltas from clean.py) ---
        rc_dates, rc_vals, running = [], [], np.nan
        for _, row in grp.iterrows():
            if not pd.isna(row["reviews_count"]):
                if pd.isna(running):
                    running = float(row["reviews_count"])
                elif not pd.isna(row["review_delta"]):
                    running += float(row["review_delta"])
                rc_dates.append(row["date"])
                rc_vals.append(running)

        prev_price_ok_disc = np.nan
        for _, row in grp.iterrows():
            rec = {
                "title": title,
                "date": row["date"],
                "has_row": True,
                "sold_raw": row["sold"],
                "sold_clean": row["sold_clean"],
                "sold_valid": bool(row["sold_valid"]),
                "seg": int(row["seg"]),
                "resolution": row["resolution"],
                "final_price": row["final_price"],
                "discount": row["discount"],
                "reviews_raw": row["reviews_count"],
                "review_delta": row["review_delta"],
                "sales_per_day": np.nan,
                "sales_gap": np.nan,
            }
            if row["sold_valid"]:
                if prev_date is not None and prev_seg == row["seg"]:
                    gap = (row["date"] - prev_date).days
                    rec["sales_per_day"] = (row["sold_clean"] - prev_sold) / gap
                    rec["sales_gap"] = float(gap)
                prev_date, prev_sold, prev_seg = row["date"], row["sold_clean"], row["seg"]

            # reviews in the last 2 days, and the rate in the 5 days before that
            rd, _ = _window_change(rc_dates, rc_vals, row["date"], config.REVIEW_JUMP_WINDOW_DAYS)
            before_end = row["date"] - pd.Timedelta(days=config.REVIEW_JUMP_WINDOW_DAYS)
            rb, rb_gap = _window_change(rc_dates, rc_vals, before_end, 5)
            rec["reviews_2d"] = rd
            rec["review_rate_before"] = rb / rb_gap if rb_gap and not pd.isna(rb_gap) else np.nan
            _, rec["reviews_corrected"] = _asof(rc_dates, rc_vals, row["date"])

            # discount change vs the previous trusted price row
            disc = row["discount"]
            rec["discount_change"] = (disc - prev_price_ok_disc
                                      if not pd.isna(disc) and not pd.isna(prev_price_ok_disc) else np.nan)
            if not pd.isna(disc):
                prev_price_ok_disc = disc
            out.append(rec)
    return pd.DataFrame(out)


def build_panel(products: pd.DataFrame, accounts: pd.DataFrame, mapping: list[dict],
                calendar: list[pd.Timestamp]) -> pd.DataFrame:
    """Full product x calendar-day grid (days without a snapshot have has_row=False)."""
    snap = product_signals(products)
    grid = pd.MultiIndex.from_product([sorted(snap["title"].unique()), calendar], names=["title", "date"])
    panel = snap.set_index(["title", "date"]).reindex(grid).reset_index()
    panel["has_row"] = panel["has_row"].eq(True)
    panel["sold_valid"] = panel["sold_valid"].eq(True)

    handles = {m["title"]: m["handle"] for m in mapping}
    panel["handle"] = panel["title"].map(handles)
    acc = account_signals(accounts, calendar)
    panel = panel.merge(acc, on=["handle", "date"], how="left")
    return panel.sort_values(["title", "date"]).reset_index(drop=True)
