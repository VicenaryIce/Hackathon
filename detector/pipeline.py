"""One function that runs the whole detector on (a slice of) the raw data.

The backtest calls this once per day with only the data up to that day.
"""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from . import clean, config, features, mapping, score


@dataclass
class RadarRun:
    quality: pd.DataFrame
    products: pd.DataFrame
    accounts: pd.DataFrame
    mapping: list[dict]
    panel: pd.DataFrame
    scored: pd.DataFrame
    log: clean.ExclusionLog


def run_pipeline(raw_products: pd.DataFrame, raw_accounts: pd.DataFrame) -> RadarRun:
    log = clean.ExclusionLog()
    quality = clean.day_quality(raw_products, log)
    products = clean.clean_products(raw_products, quality, log)
    accounts = clean.clean_accounts(raw_accounts, log)
    links = mapping.build_mapping(raw_products)
    calendar = list(quality["date"])
    panel = features.build_panel(products, accounts, links, calendar)
    scored = score.score_panel(panel)
    scored = calibrate(scored)
    return RadarRun(quality, products, accounts, links, panel, scored, log)


# --------------------------------------------------------------------------
# Burst onsets and self-calibrating confidence
# --------------------------------------------------------------------------
def burst_onsets(scored: pd.DataFrame) -> pd.DataFrame:
    """Days on which a product enters the Burst phase (incl. second waves)."""
    m = scored[scored["is_measurement"]].sort_values(["title", "date"])
    prev = m.groupby("title")["phase"].shift()
    onsets = m[(m["phase"] == "burst") & (prev != "burst")]
    return onsets[["title", "date", "level", "baseline"]].reset_index(drop=True)


def calibrate(scored: pd.DataFrame) -> pd.DataFrame:
    """Replace each alert's a-priori confidence by a calibrated one.

    confidence(day N) = (prior x w + hits) / (w + resolved)
    where `resolved` are earlier alerts whose 1-3 day window is over (or that
    already came true) by day N, and `hits` those that came true. This only
    uses information available on day N.
    """
    scored = scored.copy()
    for col in ["confidence_prior", "calibration_hits", "calibration_resolved"]:
        scored[col] = float("nan")
    scored["confidence"] = scored["confidence"].astype(float)
    scored["prediction"] = scored["prediction"].astype(object)
    onsets = burst_onsets(scored)
    onset_days = {t: sorted(g["date"]) for t, g in onsets.groupby("title")}
    horizon = pd.Timedelta(days=config.PREDICTION_HORIZON_DAYS)
    alerts = scored[scored["alert"]].sort_values("date")
    w = config.CONFIDENCE_PRIOR_WEIGHT

    def outcome(title, made_on, as_of):
        """'hit', 'miss' or None (still open) for an alert, judged on day `as_of`."""
        for d in onset_days.get(title, []):
            if made_on < d <= min(made_on + horizon, as_of):
                return "hit"
        return "miss" if as_of >= made_on + horizon else None

    for idx, row in alerts.iterrows():
        earlier = alerts[alerts["date"] < row["date"]]
        results = [outcome(t, d, row["date"]) for t, d in zip(earlier["title"], earlier["date"])]
        hits = sum(r == "hit" for r in results)
        resolved = sum(r is not None for r in results)
        prior = row["confidence"] / 100
        cal = (prior * w + hits) / (w + resolved)
        scored.at[idx, "confidence_prior"] = row["confidence"]
        scored.at[idx, "confidence"] = int(round(100 * cal))
        scored.at[idx, "calibration_hits"] = hits
        scored.at[idx, "calibration_resolved"] = resolved
        scored.at[idx, "prediction"] = (f"Explosie verwacht binnen 1 tot 3 dagen "
                                        f"(betrouwbaarheid {int(round(100 * cal))}%)")
    return scored
