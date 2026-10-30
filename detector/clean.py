"""Data-quality rules. Nothing is silently dropped: every excluded or
corrected value is written to the exclusion log with a reason.

All rules are *causal*: whether a value on day D is trusted only depends on
data from day D and earlier, so the backtest can replay them day by day.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from . import config
from .mapping import KNOWN_HANDLES


# --------------------------------------------------------------------------
# Exclusion log
# --------------------------------------------------------------------------
@dataclass
class ExclusionLog:
    rows: list[dict] = field(default_factory=list)

    def add(self, table: str, rule: str, action: str, reason: str, *,
            date=None, entity: str | None = None, column: str | None = None,
            value=None, prev=None, n_rows: int = 1) -> None:
        self.rows.append({
            "table": table,
            "rule": rule,
            "action": action,
            "date": None if date is None else pd.Timestamp(date).strftime("%Y-%m-%d"),
            "entity": entity,
            "column": column,
            "value": None if value is None or (isinstance(value, float) and np.isnan(value)) else value,
            "prev": None if prev is None or (isinstance(prev, float) and np.isnan(prev)) else prev,
            "n_rows": int(n_rows),
            "reason": reason,
        })

    def frame(self) -> pd.DataFrame:
        cols = ["table", "rule", "action", "date", "entity", "column", "value", "prev", "n_rows", "reason"]
        return pd.DataFrame(self.rows, columns=cols)

    def summary(self) -> list[dict]:
        df = self.frame()
        if df.empty:
            return []
        out = (df.groupby(["table", "rule", "action"], sort=False)
                 .agg(entries=("reason", "size"), rows=("n_rows", "sum"))
                 .reset_index())
        return [{k: (int(v) if isinstance(v, (np.integer,)) else v) for k, v in r.items()}
                for r in out.to_dict("records")]


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------
def significant_digits(x: float) -> float:
    """7000 -> 1, 3 -> 1, 207100 -> 4. NaN stays NaN."""
    if pd.isna(x):
        return np.nan
    n = int(round(abs(x)))
    if n == 0:
        return 1
    return len(str(n).rstrip("0"))


def resolution_of(sold: float) -> float:
    """How precisely TikTok shows `sold` at this size (verified in the data):
    exact below 1,000; rounded to 100 up to 1M; rounded to 100k above."""
    if pd.isna(sold):
        return np.nan
    if sold < 1_000:
        return 1.0
    if sold < 1_000_000:
        return 100.0
    return 100_000.0


def count_resolution(value: float) -> float:
    """Followers/likes are shown as e.g. 4.1M (100k steps) or 851.9K (100 steps)."""
    if pd.isna(value):
        return np.nan
    return 100_000.0 if value >= 1_000_000 else 100.0


def _fmt_share(x: float) -> str:
    return f"{100 * x:.0f}%"


# --------------------------------------------------------------------------
# Day-level quality (precision gate + mass-jump / source change)
# --------------------------------------------------------------------------
def day_quality(products: pd.DataFrame, log: ExclusionLog) -> pd.DataFrame:
    """One row per calendar date with the day-level quality verdicts."""
    dates = sorted(products["date"].unique())
    counts = products.groupby("date")["title"].size()
    median_count = float(counts.median())

    rows = []
    prev = None
    for d in dates:
        day = products[products["date"] == d].set_index("title")
        sold = day["sold"].dropna()
        one_digit_share = float((sold.map(significant_digits) == 1).mean()) if len(sold) else np.nan
        gated = bool(len(sold) and one_digit_share > config.PRECISION_GATE_MAX_ONE_DIGIT_SHARE)

        changed_share, n_comparable, uniform_ratio, uniform_count = np.nan, 0, None, 0
        if prev is not None:
            both = day.join(prev, how="inner", rsuffix="_prev")
            pair = both[["sold", "sold_prev"]].dropna()
            n_comparable = int(len(pair))
            if n_comparable:
                changed_share = float((pair["sold"] != pair["sold_prev"]).mean())
            ratio = (both["final_price"] / both["final_price_prev"]).round(2)
            ratio = ratio[(ratio > 0) & (ratio != 1.0)]
            if len(ratio):
                vc = ratio.value_counts()
                uniform_ratio, uniform_count = float(vc.index[0]), int(vc.iloc[0])

        mass_jump = bool(n_comparable >= config.MASS_JUMP_MIN_COMPARABLE
                         and changed_share >= config.MASS_JUMP_CHANGED_SHARE)
        uniform_price = bool(uniform_count >= config.UNIFORM_PRICE_MIN_PRODUCTS)
        source_change = mass_jump or uniform_price
        partial = bool(counts.get(d, 0) < 0.5 * median_count)

        rows.append({
            "date": pd.Timestamp(d),
            "n_products": int(counts.get(d, 0)),
            "n_sold": int(len(sold)),
            "one_digit_share": one_digit_share,
            "sales_gated": gated,
            "n_comparable": n_comparable,
            "changed_share": changed_share,
            "uniform_price_ratio": uniform_ratio,
            "uniform_price_count": uniform_count,
            "mass_jump": mass_jump,
            "uniform_price": uniform_price,
            "source_change": source_change,
            "partial_day": partial,
        })

        if gated:
            log.add("products", "precision_gate", "sold ignored for this day",
                    f"{_fmt_share(one_digit_share)} of sold values have a single significant digit "
                    f"(e.g. 7000 or 3; normally ~5%): the source truncated the numbers",
                    date=d, column="sold", n_rows=len(sold))
        if source_change:
            parts = []
            if mass_jump:
                parts.append(f"{_fmt_share(changed_share)} of {n_comparable} comparable products changed "
                             f"`sold` on the same day (normally 30-40%)")
            if uniform_price:
                parts.append(f"{uniform_count} products got the same price multiplier x{uniform_ratio:.2f}")
            log.add("products", "source_change", "deltas into this day ignored; new series starts",
                    "; ".join(parts) + " -> data-source change, not hype", date=d, column="sold",
                    n_rows=n_comparable)
        if partial:
            log.add("products", "partial_day", "kept (gaps are normalised per day)",
                    f"only {int(counts.get(d, 0))} products scraped (median {median_count:.0f})",
                    date=d, n_rows=int(counts.get(d, 0)))
        prev = day
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------
# Products
# --------------------------------------------------------------------------
def clean_products(raw: pd.DataFrame, quality: pd.DataFrame, log: ExclusionLog) -> pd.DataFrame:
    df = raw.copy()

    # Segments: a gated day or a source-change day breaks the sales series.
    # seg(d) = number of break days up to and including d (global calendar).
    q = quality.set_index("date")
    is_break = (q["sales_gated"] | q["source_change"]).astype(int)
    seg_of_date = is_break.cumsum()
    df["seg"] = df["date"].map(seg_of_date).astype(int)
    df["sales_gated"] = df["date"].map(q["sales_gated"]).astype(bool)
    df["sold_valid"] = df["sold"].notna() & ~df["sales_gated"]

    # Running maximum within a segment: `sold` is cumulative and may never drop.
    df["sold_clean"] = np.nan
    for (title, seg), grp in df[df["sold_valid"]].groupby(["title", "seg"], sort=False):
        running = grp["sold"].cummax()
        df.loc[grp.index, "sold_clean"] = running
        dropped = grp[grp["sold"] < running]
        for idx, row in dropped.iterrows():
            log.add("products", "sold_decrease", "kept running maximum",
                    f"sold went down to {row['sold']:,.0f} (max so far {running[idx]:,.0f}); "
                    "a cumulative counter cannot drop -> scraping artifact",
                    date=row["date"], entity=title, column="sold", value=float(row["sold"]))
    df["resolution"] = df["sold_clean"].map(resolution_of)

    # Currency: the dataset should be USD only.
    non_usd = df["currency"] != "USD"
    for idx, row in df[non_usd].iterrows():
        log.add("products", "currency", "price ignored",
                f"price listed in {row['currency']} instead of USD",
                date=row["date"], entity=row["title"], column="final_price", value=float(row["final_price"]))
    df["price_ok"] = ~non_usd

    # Price glitches (causal: compare with the previous trusted price).
    df["prev_price"] = np.nan
    for title, grp in df.groupby("title", sort=False):
        last_ok = np.nan
        for idx, row in grp.iterrows():
            price = row["final_price"]
            if not row["price_ok"] or pd.isna(price):
                continue
            if not pd.isna(last_ok) and price < config.PRICE_GLITCH_MAX_RATIO * last_ok:
                df.at[idx, "price_ok"] = False
                log.add("products", "price_glitch", "price ignored",
                        f"price ${price:.2f} is below 30% of the previous price ${last_ok:.2f}",
                        date=row["date"], entity=title, column="final_price", value=float(price),
                        prev=float(last_ok))
                continue
            df.at[idx, "prev_price"] = last_ok
            last_ok = price
    df.loc[~df["price_ok"], ["final_price", "initial_price", "discount_percent"]] = np.nan
    df["discount"] = np.where(df["price_ok"], df["discount_percent"].fillna(0.0), np.nan)

    # Ratings outside 0-5 are impossible.
    bad_rating = df["prodct_rating"] > 5
    if bad_rating.any():
        log.add("products", "rating_out_of_range", "rating ignored (not used as a signal)",
                f"{int(bad_rating.sum())} rows have prodct_rating 6-9 on a 0-5 scale",
                column="prodct_rating", n_rows=int(bad_rating.sum()))
    df.loc[bad_rating, "prodct_rating"] = np.nan

    # Reviews: many listings only show the LAST DIGIT of the review count,
    # so 9 -> 0 means +1 review, not -9.
    df["review_delta"] = np.nan
    df["review_gap"] = np.nan
    for title, grp in df.groupby("title", sort=False):
        prev_val, prev_date = np.nan, None
        for idx, row in grp.iterrows():
            cur = row["reviews_count"]
            if pd.isna(cur):
                continue
            if prev_date is not None:
                delta = cur - prev_val
                if delta < 0:
                    if prev_val <= 9 and cur <= 9:
                        delta = cur + 10 - prev_val
                        log.add("products", "review_wrap", "corrected (+10)",
                                f"reviews {prev_val:.0f} -> {cur:.0f}: counter keeps only the last digit, "
                                f"so this is +{delta:.0f}",
                                date=row["date"], entity=title, column="reviews_count", value=float(cur),
                                prev=float(prev_val))
                    else:
                        log.add("products", "review_decrease", "delta ignored",
                                f"reviews dropped {prev_val:.0f} -> {cur:.0f}",
                                date=row["date"], entity=title, column="reviews_count", value=float(cur))
                        delta = np.nan
                df.at[idx, "review_delta"] = delta
                df.at[idx, "review_gap"] = (row["date"] - prev_date).days
            prev_val, prev_date = cur, row["date"]
    return df


# --------------------------------------------------------------------------
# Accounts
# --------------------------------------------------------------------------
def clean_accounts(raw: pd.DataFrame, log: ExclusionLog) -> pd.DataFrame:
    df = raw.copy()

    unknown = ~df["handle"].isin(KNOWN_HANDLES)
    for handle, grp in df[unknown].groupby("handle"):
        first = grp.iloc[0]
        log.add("accounts", "wrong_account", "dropped",
                f"'{handle}' is '{first['nickname']}' ({'verified' if first['is_verified'] else 'not verified'}, "
                f"{first['followers']:,.0f} followers): the scraper returned a different account",
                date=first["date"], entity=handle, n_rows=len(grp))
    df = df[~unknown].copy()

    zero = df["followers"] <= 0
    for idx, row in df[zero].iterrows():
        log.add("accounts", "zero_followers", "followers ignored",
                f"followers = {row['followers']:.0f} for an account with millions of followers",
                date=row["date"], entity=row["handle"], column="followers", value=float(row["followers"]))
    df.loc[zero, ["followers", "following"]] = np.nan

    # Likes and video counts are cumulative: any dip is a scraping artifact.
    for col in ["likes", "videos_count"]:
        clean_col = f"{col}_clean"
        df[clean_col] = np.nan
        for handle, grp in df.groupby("handle", sort=False):
            running = grp[col].cummax()
            df.loc[grp.index, clean_col] = running
            for idx in grp.index[grp[col] < running]:
                drop = 1 - grp.at[idx, col] / running[idx]
                hard = drop > config.ACCOUNT_HARD_DROP_SHARE
                log.add("accounts", f"{col}_dip", "kept running maximum",
                        f"{col} dipped {running[idx]:,.0f} -> {grp.at[idx, col]:,.0f} ({100 * drop:.1f}%)"
                        + ("; >10% drop = hard scraping error" if hard else "; recovers -> scraping artifact"),
                        date=grp.at[idx, "date"], entity=handle, column=col, value=float(grp.at[idx, col]),
                        prev=float(running[idx]))
    df["followers_res"] = df["followers"].map(count_resolution)
    df["likes_res"] = df["likes_clean"].map(count_resolution)
    return df.reset_index(drop=True)
