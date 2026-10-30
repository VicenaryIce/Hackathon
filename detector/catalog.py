"""Simple, keyword-based product facts used by the UI and the insights:
product type, number of items in a listing, and a rough PostNL parcel size.
Categories come in English, Spanish and Chinese, so we match keywords on
both the title and the category."""
from __future__ import annotations

import re

TYPE_LABELS = {
    "patch": "Puistjespleisters",
    "lip": "Lipproducten",
    "gummies": "Vitamine-gummies",
    "skincare": "Huidverzorging",
    "makeup": "Make-up",
    "fragrance": "Geuren",
    "body": "Bodycare",
    "hair": "Haar",
    "fashion": "Mode & accessoires",
    "other": "Overig",
}

# 1) Strong title keywords win.
_TITLE_FIRST = [
    ("patch", r"patch|star strips"),
    ("lip", r"\blip\b|lip balm|lipstick|lip gloss|lip oil|\bgloss\b|star balm"),
    ("gummies", r"gumm"),
]
# 2) Then the (multilingual) category.
_CATEGORY_RULES = [
    ("gummies", r"vitamin|supplement|suplemento|保健"),
    ("fragrance", r"fragrance|perfume|香水"),
    ("body", r"body|bath|baño|卫浴|身体|cremas y lociones"),
    ("hair", r"shampoo|champú|洗发|hair|pelo|wig|extension|extensiones|接发"),
    ("makeup", r"makeup|maquillaje|concealer|corrector|bronzer|highlighter|高光|blush|colorete|eyeliner|brow|cejas|brush|brocha|primer|bases de maquillaje"),
    ("fashion", r"jacket|dress|socks|pants|pantalones|ring"),
    ("skincare", r"serum|sérum|moistur|hidratantes|toner|tónico|cleanser|limpiador|mask|mascarilla|eye treatment|ojos|sunscreen|protección solar|skin care|cuidado de la piel|acne|acné|面部|保湿|面膜|痘痘"),
]
# 3) Title fallback for anything left.
_TITLE_FALLBACK = [
    ("skincare", r"serum|moistur|cream|cleanser|toner|mask|sunscreen|spf|lotion|skincare|skin care"),
    ("fashion", r"jacket|dress|socks|pants|\bring\b"),
]

_SET_WORDS = r"\b(set|duo|trio|kit|bundle|routine|collection|combo)\b"
_COUNT_PATTERN = r"(\d+)\s*[-‑ ]?\s*(piece|pieces|pc|pcs|step|steps|pack|bottle|bottles)\b|\b(\d+)x\b"
_MAX_SET_ITEMS = 12   # "144pcs" toothbrush heads is one product, not a 144-item set
_KBEAUTY = r"medicube|cosrx|laka|k-beauty|korean"


def product_type(title: str, category: str) -> str:
    t, c = title.lower(), category.lower()
    for key, pattern in _TITLE_FIRST:
        if re.search(pattern, t):
            return key
    for key, pattern in _CATEGORY_RULES:
        if re.search(pattern, c):
            return key
    for key, pattern in _TITLE_FALLBACK:
        if re.search(pattern, t):
            return key
    return "other"


def item_count(title: str) -> int:
    """Number of items in the listing (1 = single product, 2 = set of unknown size)."""
    text = title.lower()
    m = re.search(_COUNT_PATTERN, text)
    if m:
        n = int(m.group(1) or m.group(3))
        return n if 1 <= n <= _MAX_SET_ITEMS else 1
    if re.search(r"\btrio\b", text):
        return 3
    if re.search(r"\bduo\b|\b2x\b", text):
        return 2
    if re.search(_SET_WORDS, text):
        return 2
    return 1


def is_kbeauty_set(title: str) -> bool:
    return bool(re.search(_KBEAUTY, title.lower())) and item_count(title) >= 2


def parcel_size(title: str, ptype: str, items: int) -> str:
    """Rough PostNL size class: 'brievenbus' (letterbox), 'pakket' or 'groot pakket'."""
    text = title.lower()
    if ptype in ("patch", "lip") and items <= 5:
        return "brievenbus"
    if re.search(r"socks|\bring\b|screen protector|brush", text):
        return "brievenbus"
    if items >= 4 or re.search(r"wig|jacket|trash bag|dress|pants|sweater", text):
        return "groot pakket"
    return "pakket"
