"""Link products to TikTok accounts.

There is no shared key between products.csv (`store_name`) and accounts.csv
(`handle`), so the link is an explicit, reviewable table:

1. "store"  - the product is sold by the brand's own store (exact store_name).
2. "title"  - a reseller lists the brand's product; the brand name is in the
              title (e.g. Unineed US selling COSRX). Lower confidence: the
              brand's videos may still drive demand for that listing.
3. "none"   - no TikTok account in the dataset (hair, fashion, Laka, ...).

The 3 creators are not linked to any product: no product mentions them.
"""
from __future__ import annotations

import re

import pandas as pd

# handle -> brand info. `stores` must match products.store_name exactly.
BRAND_ACCOUNTS: dict[str, dict] = {
    "bubble":            {"brand": "Bubble Skincare", "stores": ["Bubble Skincare"], "pattern": r"\bbubble\b"},
    "cerave":            {"brand": "CeraVe", "stores": ["CeraVe"], "pattern": r"\bcerave\b"},
    "cosrx_official":    {"brand": "COSRX", "stores": ["COSRX US"], "pattern": r"\bcosrx\b"},
    "elfyeah":           {"brand": "e.l.f. Cosmetics", "stores": ["e.l.f. Cosmetics"], "pattern": r"\be\.l\.f\."},
    "golinutrition":     {"brand": "Goli Nutrition", "stores": ["Goli Nutrition"], "pattern": r"\bgoli\b"},
    "medicube_official": {"brand": "medicube", "stores": ["medicube US Store"], "pattern": r"\bmedicube\b"},
    "nyxcosmetics":      {"brand": "NYX Professional Makeup", "stores": ["NYX Professional Makeup"], "pattern": r"\bnyx\b"},
    "soldejaneiro":      {"brand": "Sol de Janeiro", "stores": ["Sol de Janeiro"], "pattern": r"\bsol de janeiro\b"},
    "starface":          {"brand": "Starface", "stores": ["Starface World"], "pattern": r"\bstarface\b"},
    "theordinary":       {"brand": "The Ordinary", "stores": ["The Ordinary Store"], "pattern": r"\bthe ordinary\b|\bdeciem\b"},
}
CREATORS = ["hyram", "mikaylanogueira", "rocio.roses"]
KNOWN_HANDLES = set(BRAND_ACCOUNTS) | set(CREATORS)

STORE_TO_HANDLE = {store: handle for handle, info in BRAND_ACCOUNTS.items() for store in info["stores"]}


def link_product(title: str, store_name: str) -> tuple[str | None, str]:
    """Return (handle, match_type) for one product."""
    if store_name in STORE_TO_HANDLE:
        return STORE_TO_HANDLE[store_name], "store"
    lowered = title.lower()
    hits = [h for h, info in BRAND_ACCOUNTS.items() if re.search(info["pattern"], lowered)]
    if len(hits) == 1:
        return hits[0], "title"
    return None, "none"


def build_mapping(products: pd.DataFrame) -> list[dict]:
    """One dict per product: title, store_name, handle (or None), match_type, brand."""
    firsts = products.groupby("title", sort=True)["store_name"].first()
    rows = []
    for title, store in firsts.items():
        handle, match = link_product(str(title), str(store))
        rows.append({
            "title": str(title),
            "store_name": str(store),
            "handle": handle,
            "match_type": match,
            "brand": BRAND_ACCOUNTS[handle]["brand"] if handle else None,
        })
    return rows


def mapping_summary(mapping: list[dict]) -> list[dict]:
    """Store-level view of the mapping (shown in the README and the UI)."""
    order = {"store": 0, "title": 1, "none": 2}
    counts: dict[tuple, int] = {}
    for row in mapping:
        key = (row["match_type"], row["store_name"], row["handle"])
        counts[key] = counts.get(key, 0) + 1
    out = [
        {"store_name": store, "handle": handle, "match_type": match, "products": n}
        for (match, store, handle), n in counts.items()
    ]
    return sorted(out, key=lambda r: (order[r["match_type"]], r["store_name"].lower(), r["handle"] or ""))
