"""Valse alarmen: spikes that a naive system would call hype, and why they are not.

Each alarm has the date it became visible, what a naive reading would
conclude, and what is really going on. All checks only use data up to
that date.
"""
from __future__ import annotations

import math

import pandas as pd

from . import nl
from .mapping import BRAND_ACCOUNTS


def _brand_sales(scored: pd.DataFrame, panel: pd.DataFrame, handle: str, start, end) -> dict:
    """Sales/day and whether any product of the brand moved between start and end (inclusive)."""
    titles = panel.loc[panel["handle"] == handle, "title"].unique()
    win = scored[(scored["title"].isin(titles)) & (scored["date"] >= start) & (scored["date"] <= end)
                 & (scored["is_measurement"])]
    moved = bool((win["sales_up"] | win["phase"].isin(["burst"])).any())
    per_day = win.groupby("date")["level"].sum()
    return {"n_products": int(len(titles)), "moved": moved,
            "sales_per_day": float(per_day.mean()) if len(per_day) else float("nan")}


def build_alarms(quality: pd.DataFrame, log_df: pd.DataFrame, panel: pd.DataFrame,
                 scored: pd.DataFrame, accounts: pd.DataFrame, raw_accounts: pd.DataFrame) -> list[dict]:
    alarms: list[dict] = []
    accounts_raw_first = {h: g.sort_values("date").iloc[0].to_dict() for h, g in raw_accounts.groupby("handle")}

    def add(date, kind, severity, entity, title, naive, real, entity_type="dag"):
        alarms.append({
            "date": pd.Timestamp(date).strftime("%Y-%m-%d"),
            "type": kind, "severity": severity, "entity": entity, "entity_type": entity_type,
            "title": title, "naive": naive, "real": real,
        })

    # 1) Truncated sales numbers (precision gate)
    gated = quality[quality["sales_gated"]]
    for _, q in gated.iterrows():
        add(q["date"], "afgekapte_cijfers", "hoog", "alle producten",
            "Verkoopcijfers afgekapt tot 1 cijfer",
            f"{q['n_sold']} producten hebben een verkoopcijfer als 7000 of 3; sommige 'stijgen' 1000 per dag.",
            f"{nl.num(100 * q['one_digit_share'])}% van de waarden heeft maar 1 significant cijfer "
            "(normaal ~5%). De bron gaf afgekapte getallen door: deze dag telt niet mee.")

    # 2) Data-source change (mass jump + uniform price multiplier)
    for _, q in quality[quality["source_change"]].iterrows():
        bits = []
        if q["mass_jump"]:
            bits.append(f"{nl.num(100 * q['changed_share'])}% van {q['n_comparable']} vergelijkbare producten "
                        "veranderde tegelijk van verkoopcijfer (normaal 30-40%)")
        if q["uniform_price"]:
            bits.append(f"{q['uniform_price_count']} prijzen gingen precies ×{nl.num(q['uniform_price_ratio'], 2)}")
        add(q["date"], "bronwissel", "hoog", "alle producten",
            "Massale sprong: wissel van databron",
            "Bijna alle producten 'exploderen' op dezelfde dag: mega-hype!",
            "; ".join(bits).capitalize() + ". Dat is een andere databron, geen hype. "
            "De radar start hier een nieuwe meetreeks.")

    # 3) Follower jumps that are rounding flips, and whether sales moved
    for handle, grp in accounts.groupby("handle"):
        if handle not in BRAND_ACCOUNTS:
            continue
        grp = grp.sort_values("date")
        prev = None
        for _, row in grp.iterrows():
            if prev is not None and not math.isnan(row["followers"]) and not math.isnan(prev["followers"]):
                jump = row["followers"] - prev["followers"]
                if prev["followers"] >= 1_000_000 and jump >= 100_000:
                    start = row["date"] - pd.Timedelta(days=3)
                    s = _brand_sales(scored, panel, handle, start, row["date"])
                    brand = BRAND_ACCOUNTS[handle]["brand"]
                    sales_txt = (f"verkochten de {s['n_products']} producten van {brand} samen ~"
                                 f"{nl.smart(s['sales_per_day'])} per dag"
                                 + (" en steeg geen enkel product" if not s["moved"] else ""))
                    add(row["date"], "volgers_zonder_verkoop", "middel", f"@{handle}",
                        f"{brand}: +{nl.num(jump)} volgers in één dag",
                        f"Volgers {nl.num(prev['followers'] / 1e6, 1)}M → {nl.num(row['followers'] / 1e6, 1)}M: "
                        "het merk gaat viraal!",
                        f"TikTok toont volgers per 100.000: dit is de afronding die omklapt (echte groei "
                        f"kan 1 volger zijn). Ondertussen {sales_txt}.", entity_type="account")
            prev = row

    # 4) Scraping errors in accounts (dips, zero followers, wrong account)
    acc_log = log_df[log_df["table"] == "accounts"]
    for _, e in acc_log.iterrows():
        if e["rule"] == "wrong_account":
            first = accounts_raw_first.get(e["entity"], {})
            add(e["date"], "verkeerd_account", "middel", f"@{e['entity']}",
                "Verkeerd account gescrapet",
                f"Een creator-account met maar {nl.num(first.get('followers', float('nan')))} volgers en "
                f"{nl.num(first.get('likes', float('nan')))} likes duikt op.",
                f"'@{e['entity']}' is '{first.get('nickname', '?')}' "
                f"({'geverifieerd' if first.get('is_verified') else 'niet geverifieerd'}): de scraper haalde een "
                "ander account op. Rij verwijderd.",
                entity_type="account")
        elif e["rule"] == "zero_followers":
            add(e["date"], "scrapefout", "middel", f"@{e['entity']}",
                "Volgers vallen naar 0",
                "Het account verliest in één dag al zijn volgers.",
                "Een account met 2 miljoen volgers heeft niet ineens 0 volgers: scrapefout, waarde genegeerd.",
                entity_type="account")
        elif e["rule"] in ("videos_count_dip", "likes_dip"):
            is_vid = e["rule"] == "videos_count_dip"
            prev, val = float(e["prev"]), float(e["value"])
            n = prev - val
            what = nl.plural(n, "video", "video's") if is_vid else "likes"
            drop = 1 - val / prev if prev else 0.0
            add(e["date"], "scrapefout", "laag", f"@{e['entity']}",
                f"{'Video-teller' if is_vid else 'Likes-teller'} daalt",
                f"{nl.num(n)} {what} minder, en zodra het getal terugkomt lijkt dat een plotselinge post-golf.",
                f"Van {nl.num(prev)} naar {nl.num(val)} (−{nl.num(100 * drop, 2 if 100 * drop < 0.1 else 1)}%). "
                "Een totaalteller hoort niet te dalen: dit is een scrapefout"
                f"{' of afrondingsruis' if not is_vid else ' of een verwijderde video'}. "
                "De radar rekent met het hoogste getal tot dan toe, zodat het herstel niet als hype telt.",
                entity_type="account")

    # 5) Review counters that keep only the last digit
    for _, e in log_df[log_df["rule"] == "review_wrap"].iterrows():
        add(e["date"], "teller_overloop", "laag", e["entity"],
            "Reviews '9 → 0'",
            "Reviews dalen met 9: slecht teken (of een reset).",
            "Deze teller toont alleen het laatste cijfer: 9 → 0 betekent +1 review.",
            entity_type="product")

    # 6) Price glitches
    for _, e in log_df[log_df["rule"].isin(["price_glitch", "currency"])].iterrows():
        if e["rule"] == "price_glitch":
            add(e["date"], "prijsfout", "laag", e["entity"],
                f"Prijs ineens {nl.usd(float(e['value']))}",
                "Megakorting: dit wordt een verkoophit!",
                f"Van {nl.usd(float(e['prev']))} naar {nl.usd(float(e['value']))}: minder dan 30% van de vorige "
                "prijs, dus een prijsfout (genegeerd).", entity_type="product")
        else:
            add(e["date"], "prijsfout", "laag", e["entity"],
                "Prijs in Singaporese dollar",
                "Prijsdaling van tientallen procenten.",
                "Deze rij staat in SGD in plaats van USD: prijs genegeerd.", entity_type="product")

    alarms = _merge_repeats(alarms)
    order = {"hoog": 0, "middel": 1, "laag": 2}
    alarms.sort(key=lambda a: (a["date"], order[a["severity"]]))
    for i, a in enumerate(alarms):
        a["id"] = f"a{i + 1}"
    return alarms


def _merge_repeats(alarms: list[dict]) -> list[dict]:
    """The same counter dip on consecutive days is one alarm, not two."""
    out: list[dict] = []
    last_by_key: dict[tuple, dict] = {}
    for a in sorted(alarms, key=lambda x: x["date"]):
        key = (a["type"], a["entity"], a["title"])
        prev = last_by_key.get(key)
        if a["type"] == "scrapefout" and prev is not None and \
                (pd.Timestamp(a["date"]) - pd.Timestamp(prev["last_date"])).days == 1:
            prev["last_date"] = a["date"]
            prev["days"] = prev.get("days", 1) + 1
            continue
        a = dict(a, last_date=a["date"], days=1)
        last_by_key[key] = a
        out.append(a)
    for a in out:
        if a["days"] > 1:
            a["title"] += f" ({a['days']} dagen)"
    return out
