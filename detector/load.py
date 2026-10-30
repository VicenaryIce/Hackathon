"""Read the two CSVs exactly as delivered (they start with a UTF-8 BOM)."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from . import config


def find_csv(name: str) -> Path:
    for folder in config.DATA_DIR_CANDIDATES:
        path = folder / name
        if path.exists():
            return path
    searched = ", ".join(str(f) for f in config.DATA_DIR_CANDIDATES)
    raise FileNotFoundError(f"{name} not found (looked in: {searched})")


def load_products() -> pd.DataFrame:
    df = pd.read_csv(find_csv("products.csv"), encoding="utf-8-sig")
    df["date"] = pd.to_datetime(df["date"])
    for col in ["initial_price", "final_price", "discount_percent", "sold",
                "reviews_count", "prodct_rating", "shipping_fee"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    # `sold` contains float noise like 32200.000000000004 -> whole units.
    df["sold"] = df["sold"].round()
    df["reviews_count"] = df["reviews_count"].round()
    df["title"] = df["title"].astype(str)
    df["store_name"] = df["store_name"].astype(str)
    return df.sort_values(["title", "date"]).reset_index(drop=True)


def load_accounts() -> pd.DataFrame:
    df = pd.read_csv(find_csv("accounts.csv"), encoding="utf-8-sig")
    df["date"] = pd.to_datetime(df["date"])
    for col in ["followers", "following", "likes", "videos_count"]:
        df[col] = pd.to_numeric(df[col], errors="coerce").astype(float)
    df["handle"] = df["handle"].astype(str)
    return df.sort_values(["handle", "date"]).reset_index(drop=True)
