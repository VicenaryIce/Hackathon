"""Dutch number/date formatting for the plain-language WHY sentences."""
from __future__ import annotations

import math

import pandas as pd

MONTHS = ["jan", "feb", "mrt", "apr", "mei", "jun", "jul", "aug", "sep", "okt", "nov", "dec"]


def num(x: float, decimals: int = 0) -> str:
    """1234.5 -> '1.234,5' (Dutch separators)."""
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return "?"
    s = f"{x:,.{decimals}f}"
    return s.replace(",", "_").replace(".", ",").replace("_", ".")


def smart(x: float) -> str:
    """Whole numbers for big values, one decimal for small ones (e.g. 2,5)."""
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return "?"
    if abs(x) >= 10 or float(x).is_integer():
        return num(round(x))
    return num(x, 1)


def date(d) -> str:
    d = pd.Timestamp(d)
    return f"{d.day} {MONTHS[d.month - 1]}"


def times(x: float) -> str:
    """2.17 -> '2,2×'"""
    return f"{num(x, 1)}×"


def usd(x: float) -> str:
    """19.99 -> '$19,99'"""
    return "$" + num(x, 2)


def plural(n: float, one: str, many: str) -> str:
    return one if round(n) == 1 else many
