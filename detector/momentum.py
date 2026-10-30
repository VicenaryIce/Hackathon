"""Momentum model: how many orders will a product get next week?

From the findings report (section 4): social signals (followers, likes, brand
videos, discounts, reviews) did not predict orders in this data. A product's
own recent sales did:

    log(1 + orders_next_week) = a x log(1 + orders_this_week) + b

(orders = average orders per day over a 7-day window). The coefficients are
fitted on the data, never hardcoded. The report found a ~ 0.78, b ~ 0.22.

Two versions:
- `full_fit`: the one complete week pair in the clean data (14->20 vs 20->27).
  Used for the Inzichten page, the validation numbers, and the live forecast
  made on 27 Oct.
- `rolling`: for every day D from 21 Oct, a forecast made with ONLY data up to
  D. Before 28 Oct there is no complete earlier week pair, so the rolling fit
  uses two equal half-windows inside the data up to D (e.g. on 21 Oct:
  15->18 vs 18->21). This keeps the time slider honest (no look-ahead).
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd

from . import catalog

GROWING, COOLING = 1.2, 0.8          # week-over-week ratio thresholds (report 4.4)
MIN_RATE_FOR_PHASE = 1.0             # below 1 order/day the ratio is mostly noise
ROLLING_FROM = pd.Timestamp("2026-10-21")
HYPE_BOOST_DEFAULT = 0.0             # slot for future creator-video data (report 4.5)


def phase_of(r: float | None, rate: float) -> str:
    if rate < MIN_RATE_FOR_PHASE or r is None or (isinstance(r, float) and math.isnan(r)):
        return "te_weinig"
    if r > GROWING:
        return "groeiend"
    if r < COOLING:
        return "afkoelend"
    return "stabiel"


class SoldIndex:
    """Fast 'cumulative sold as of day X' lookups on the clean sales series."""

    def __init__(self, products: pd.DataFrame):
        valid = products[products["sold_valid"]]
        seg = valid["seg"].max()                       # trustworthy series (from 14 Oct)
        v = valid[valid["seg"] == seg].sort_values("date")
        self.series = {t: (list(g["date"]), list(g["sold_clean"])) for t, g in v.groupby("title")}
        self.first_day = v["date"].min()

    def asof(self, title: str, day: pd.Timestamp):
        dates, vals = self.series.get(title, ([], []))
        best = (None, np.nan)
        for d, s in zip(dates, vals):
            if d > day:
                break
            best = (d, s)
        return best

    def rate(self, title: str, start: pd.Timestamp, end: pd.Timestamp) -> float:
        """Average orders/day between the last snapshots on or before start and end."""
        d0, s0 = self.asof(title, start)
        d1, s1 = self.asof(title, end)
        if d0 is None or d1 is None or d1 <= d0:
            return np.nan
        r = (s1 - s0) / (d1 - d0).days
        return r if r >= 0 else np.nan              # negative deltas are never real

    def titles(self):
        return sorted(self.series)


def fit(x: np.ndarray, y: np.ndarray) -> dict:
    """Least squares on log1p, plus residual quartiles for the low/high range."""
    lx, ly = np.log1p(x), np.log1p(y)
    a, b = np.polyfit(lx, ly, 1)
    resid = ly - (a * lx + b)
    ss_res = float((resid ** 2).sum())
    ss_tot = float(((ly - ly.mean()) ** 2).sum())
    se_a = math.sqrt(ss_res / (len(x) - 2) / ((lx - lx.mean()) ** 2).sum())
    return {"a": float(a), "b": float(b), "se_a": se_a, "n": int(len(x)),
            "r2": 1 - ss_res / ss_tot, "corr": float(np.corrcoef(lx, ly)[0, 1]),
            "q_low": float(np.quantile(resid, 0.25)), "q_high": float(np.quantile(resid, 0.75))}


def fit_ratio(x: np.ndarray, y: np.ndarray) -> dict:
    """The report's simple version: next week = median ratio x this week, range = quartiles.
    Only products selling >= 1/day, because ratios of tiny numbers are noise."""
    m = x >= MIN_RATE_FOR_PHASE
    r = y[m] / x[m]
    return {"mid": float(np.median(r)), "low": float(np.quantile(r, 0.25)), "high": float(np.quantile(r, 0.75)),
            "n": int(m.sum())}


def predict_ratio(rm: dict, this_week: float, hype_boost: float = HYPE_BOOST_DEFAULT) -> dict:
    """Used for parcels and the UI. `hype_boost` (multiplier on the log scale, default 0)
    is the slot for future creator-video data; we have no data to estimate it."""
    f = math.exp(hype_boost)
    return {k: this_week * rm[k] * f for k in ("low", "mid", "high")}


def predict(model: dict, this_week: float, hype_boost: float = HYPE_BOOST_DEFAULT) -> dict:
    """Predicted orders/day next week (low/mid/high). `hype_boost` is added on the
    log scale and defaults to 0: we have no data to estimate it yet."""
    z = model["a"] * math.log1p(this_week) + model["b"] + hype_boost
    return {"low": max(0.0, math.expm1(z + model["q_low"])), "mid": max(0.0, math.expm1(z)),
            "high": max(0.0, math.expm1(z + model["q_high"]))}


def _pairs(idx: SoldIndex, a0, a1, b1):
    rows = []
    for t in idx.titles():
        x, y = idx.rate(t, a0, a1), idx.rate(t, a1, b1)
        if not (math.isnan(x) or math.isnan(y)):
            rows.append((t, x, y))
    return rows


def validation(model: dict, rows: list, ratio_model: dict | None = None) -> dict:
    t = [r[0] for r in rows]
    x = np.array([r[1] for r in rows])
    y = np.array([r[2] for r in rows])
    if ratio_model is not None:
        pred = np.array([predict_ratio(ratio_model, v)["mid"] for v in x])
        lp, ly = np.log1p(pred), np.log1p(y)
        r2 = 1 - ((ly - lp) ** 2).sum() / ((ly - ly.mean()) ** 2).sum()
    else:
        pred = np.array([predict(model, v)["mid"] for v in x])
        r2 = model["r2"]
    active = y >= 1
    within = (pred[active] / y[active] >= 0.5) & (pred[active] / y[active] <= 2)
    top_pred = set(np.array(t)[np.argsort(-pred)[:10]])
    top_act = set(np.array(t)[np.argsort(-y)[:10]])
    ratios = y[(x >= 1)] / x[(x >= 1)]
    return {
        "r2": float(r2), "corr": model["corr"],
        "within_2x": float(within.mean()), "n_active": int(active.sum()),
        "top10_overlap": len(top_pred & top_act),
        "total_predicted": float(pred.sum()), "total_actual": float(y.sum()),
        "total_ratio": float(y.sum() / x.sum()),
        "median_ratio": float(np.median(ratios)),
        "ratio_q25": float(np.quantile(ratios, 0.25)), "ratio_q75": float(np.quantile(ratios, 0.75)),
    }


def run_momentum(run, ids: dict) -> dict:
    idx = SoldIndex(run.products)
    start = idx.first_day                                   # 14 Oct
    mid_day, last = start + pd.Timedelta(days=6), run.products["date"].max()   # 20 Oct, 27 Oct

    rows = _pairs(idx, start, mid_day, last)
    xs, ys = np.array([r[1] for r in rows]), np.array([r[2] for r in rows])
    model = fit(xs, ys)
    ratio_model = fit_ratio(xs, ys)
    val = validation(model, rows)
    val_ratio = validation(model, rows, ratio_model)

    titles = idx.titles()
    info = {t: {"type": catalog.product_type(t, str(run.products.loc[run.products["title"] == t, "category"].iloc[0]))}
            for t in titles}
    size = {t: catalog.parcel_size(t, info[t]["type"], catalog.item_count(t)) for t in titles}

    days, causal_errors = [], []
    calendar = sorted(run.products["date"].unique())
    for D in [pd.Timestamp(d) for d in calendar if pd.Timestamp(d) >= ROLLING_FROM]:
        k = min(7, (D - start).days // 2)
        h0, h1 = D - pd.Timedelta(days=2 * k), D - pd.Timedelta(days=k)
        if D == last:
            m, rm = model, ratio_model                        # the full week pair is known on 27 Oct
            fit_note = f"volle weken 14-20 okt → 20-27 okt"
        else:
            hp = _pairs(idx, h0, h1, D)
            hx, hy = np.array([r[1] for r in hp]), np.array([r[2] for r in hp])
            m, rm = fit(hx, hy), fit_ratio(hx, hy)
            fit_note = f"halve vensters van {k} dagen ({h0:%d}-{h1:%d} → {h1:%d}-{D:%d} okt)"
        wk_start = max(start, D - pd.Timedelta(days=7))
        prods, tot = [], {"low": 0.0, "mid": 0.0, "high": 0.0}
        by_size = {"brievenbus": 0.0, "pakket": 0.0, "groot pakket": 0.0}
        actual_total, actual_known = 0.0, False
        for t in titles:
            this_week = idx.rate(t, wk_start, D)
            if math.isnan(this_week):
                continue
            recent, earlier = idx.rate(t, h1, D), idx.rate(t, h0, h1)
            r = (recent / earlier) if earlier and earlier > 0 else (float("inf") if recent and recent > 0 else None)
            pr = predict_ratio(rm, this_week)
            for key in tot:
                tot[key] += pr[key]
            by_size[size[t]] += pr["mid"]
            actual = idx.rate(t, D, min(last, D + pd.Timedelta(days=7))) if D < last else np.nan
            if not math.isnan(actual):
                actual_total += actual
                actual_known = True
                if D == ROLLING_FROM and this_week >= 1 and actual >= 1:
                    causal_errors.append(pr["mid"] / actual)
            prods.append({"id": ids[t], "this_week": this_week, "ratio": None if r is None or math.isinf(r) else r,
                          "phase": phase_of(r if r is not None else None, this_week),
                          "low": pr["low"], "mid": pr["mid"], "high": pr["high"],
                          "parcel_size": size[t], "actual_next": None if math.isnan(actual) else actual})
        prods.sort(key=lambda p: -p["mid"])
        days.append({"date": D.strftime("%Y-%m-%d"), "fit": {"a": m["a"], "b": m["b"], "n": m["n"], "r2": m["r2"],
                                                              "ratio": rm["mid"], "ratio_low": rm["low"], "ratio_high": rm["high"]},
                     "fit_note": fit_note, "totals": tot, "by_size": by_size,
                     "actual_total": actual_total if actual_known else None,
                     "actual_window_days": int((min(last, D + pd.Timedelta(days=7)) - D).days),
                     "products": prods})

    ce = np.array(causal_errors)
    causal = {"date": ROLLING_FROM.strftime("%Y-%m-%d"), "n": int(len(ce)),
              "within_2x": float(((ce >= 0.5) & (ce <= 2)).mean()) if len(ce) else None,
              "median_pred_over_actual": float(np.median(ce)) if len(ce) else None}
    scatter = [{"id": ids[t], "x": x, "y": y} for t, x, y in rows]
    return {"model": model, "ratio_model": ratio_model, "validation_log": val, "validation": val_ratio,
            "causal_check": causal, "scatter": scatter,
            "thresholds": {"growing": GROWING, "cooling": COOLING, "min_rate": MIN_RATE_FOR_PHASE},
            "days": days}
