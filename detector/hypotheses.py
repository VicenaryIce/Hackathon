"""Test the team's early hypotheses against the cleaned data.

Each test returns a card for the "Inzichten" page: hypothesis, verdict,
a short explanation with numbers, and a small dataset for a chart.
Sales numbers only come from the trustworthy window (from 14 Oct).
"""
from __future__ import annotations

import math
from statistics import median

import numpy as np
import pandas as pd

from . import catalog, config, nl
from .mapping import BRAND_ACCOUNTS
from .pipeline import burst_onsets


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------
def spearman(x: list[float], y: list[float]) -> float:
    """Rank correlation without scipy (average ranks for ties)."""
    a = pd.Series(x).rank().to_numpy(dtype=float)
    b = pd.Series(y).rank().to_numpy(dtype=float)
    if a.std() == 0 or b.std() == 0:
        return float("nan")
    return float(np.corrcoef(a, b)[0, 1])


def _r(x, d=2):
    return None if x is None or (isinstance(x, float) and math.isnan(x)) else round(float(x), d)


def product_window(products: pd.DataFrame) -> pd.DataFrame:
    """Units/day per product in the trustworthy sales window (latest series)."""
    valid = products[products["sold_valid"]]
    seg = valid["seg"].max()
    v = valid[valid["seg"] == seg].sort_values("date")
    rows = []
    for title, g in v.groupby("title"):
        if len(g) < 2:
            continue
        days = (g["date"].iloc[-1] - g["date"].iloc[0]).days
        start, end = float(g["sold_clean"].iloc[0]), float(g["sold_clean"].iloc[-1])
        per_day = (end - start) / days if days else 0.0
        rows.append({
            "title": title,
            "store_name": g["store_name"].iloc[0],
            "category": g["category"].iloc[0],
            "price": float(g["final_price"].median()) if g["final_price"].notna().any() else float("nan"),
            "start": start, "end": end, "days": days,
            "units_per_day": per_day,
            "growth_pct_per_day": 100 * per_day / start if start > 0 else float("nan"),
        })
    out = pd.DataFrame(rows)
    out["type"] = [catalog.product_type(t, c) for t, c in zip(out["title"], out["category"])]
    out["items"] = out["title"].map(catalog.item_count)
    out["kbeauty_set"] = out["title"].map(catalog.is_kbeauty_set)
    return out


# --------------------------------------------------------------------------
# H1 video cadence vs followers
# --------------------------------------------------------------------------
def h1_video_vs_followers(run, pw: pd.DataFrame, bt: dict) -> dict:
    acc = run.accounts
    brand_rows = []
    for handle, info in BRAND_ACCOUNTS.items():
        g = acc[acc["handle"] == handle].sort_values("date")
        days = (g["date"].iloc[-1] - g["date"].iloc[0]).days
        vids = (g["videos_count_clean"].iloc[-1] - g["videos_count_clean"].iloc[0]) / days
        f = g["followers"].dropna()
        prods = pw[pw["store_name"].isin(info["stores"])]
        start_total = prods["start"].sum()
        brand_rows.append({
            "brand": info["brand"],
            "handle": handle,
            "videos_per_day": round(float(vids), 2),
            "followers_start": float(f.iloc[0]), "followers_end": float(f.iloc[-1]),
            "followers_rounded_to": 100_000 if f.iloc[0] >= 1_000_000 else 100,
            "sales_per_day": round(float(prods["units_per_day"].sum()), 1),
            "growth_pct_per_day": round(100 * float(prods["units_per_day"].sum()) / start_total, 3) if start_total else None,
            "products": int(len(prods)),
        })
    brand_rows.sort(key=lambda r: -r["videos_per_day"])
    rho_sales = spearman([r["videos_per_day"] for r in brand_rows], [r["sales_per_day"] for r in brand_rows])
    rho_growth = spearman([r["videos_per_day"] for r in brand_rows], [r["growth_pct_per_day"] or 0 for r in brand_rows])
    daily = [r for r in brand_rows if r["videos_per_day"] >= 0.9]
    other = [r for r in brand_rows if r["videos_per_day"] < 0.9]
    g_daily = median([r["growth_pct_per_day"] or 0 for r in daily]) if daily else float("nan")
    g_other = median([r["growth_pct_per_day"] or 0 for r in other]) if other else float("nan")
    nyx = next(r for r in brand_rows if r["handle"] == "nyxcosmetics")
    comp = {c["rule"]: c for c in bt["comparisons"]}
    fol = comp.get("Alleen volgersgroei", {})
    vid = comp.get("Alleen video's (>= 1 per dag)", {})
    measurable = [r for r in brand_rows if r["followers_rounded_to"] == 100]
    summary = (
        f"Volgers zeggen inderdaad weinig: bij {10 - len(measurable)} van de 10 merken toont TikTok volgers per 100.000, "
        f"dus groei is onzichtbaar, en de regel 'volgers stijgen' voorspelde {fol.get('events_predicted', 0)} van de "
        f"{fol.get('events', 0)} bursts. Maar video's alleen ook niet: NYX post het meest "
        f"({nl.num(nyx['videos_per_day'], 1)} per dag) en verkoopt bijna niets ({nl.smart(nyx['sales_per_day'])} per dag "
        f"voor {nyx['products']} producten). Over de 10 merken is de samenhang tussen video's per dag en verkoop "
        f"{'zelfs negatief' if rho_sales < -0.3 else 'zwak'} (Spearman ρ = {nl.num(rho_sales, 2)}): wie het meest post, "
        "verkoopt niet het meest. Merken die dagelijks posten groeiden mediaan "
        f"{nl.num(g_daily, 2)}% per dag tegen {nl.num(g_other, 2)}% voor de rest, niet 5 tot 10 keer zo snel. "
        f"De regel 'merk post ≥1 video per dag' gaf bij {vid.get('events_predicted', 0)} van de "
        f"{vid.get('events', 0)} bursts vooraf een seintje, maar sloeg {vid.get('alerts', 0)} keer aan "
        f"(trefkans {nl.num(100 * (vid.get('precision') or 0), 1)}%). Eén geval past wél: e.l.f. postte van 10 tot en met "
        "13 okt niets, begon op 14 okt weer elke dag te posten en 2 dagen later explodeerde de Glow Reviver-lijn."
    )
    return {
        "id": "h1",
        "title": "Video-ritme verslaat volgers",
        "hypothesis": "Merken die dagelijks video's posten groeien 5-10× sneller; volgers alleen voorspellen weinig.",
        "verdict": "deels",
        "summary": summary,
        "numbers": [
            {"label": "Bursts voorspeld door volgersgroei", "value": f"{fol.get('events_predicted', 0)} van {fol.get('events', 0)}"},
            {"label": "Spearman ρ video's/dag ↔ verkoop/dag (10 merken)", "value": nl.num(rho_sales, 2)},
            {"label": "Groei dagelijks posten vs rest", "value": f"{nl.num(g_daily, 2)}% vs {nl.num(g_other, 2)}% per dag"},
            {"label": "NYX: video's per dag / verkoop per dag", "value": f"{nl.num(nyx['videos_per_day'], 1)} / {nl.smart(nyx['sales_per_day'])}"},
        ],
        "chart": {"type": "brands", "rows": brand_rows},
        "stats": {"rho_sales": _r(rho_sales), "rho_growth": _r(rho_growth), "growth_daily": _r(g_daily, 3),
                  "growth_other": _r(g_other, 3)},
    }


# --------------------------------------------------------------------------
# H2 reviews as earliest signal
# --------------------------------------------------------------------------
def h2_reviews(run, bt: dict) -> dict:
    sc = run.scored
    panel = run.panel
    p = panel[["title", "date", "review_delta"]].merge(
        sc[["title", "date", "level", "is_measurement"]], on=["title", "date"], how="left")
    # reviews per day at each snapshot (gap-normalised)
    prod = run.products[["title", "date", "review_gap"]]
    p = p.merge(prod, on=["title", "date"], how="left")
    p["rev_per_day"] = p["review_delta"] / p["review_gap"]
    p.loc[~p["is_measurement"].eq(True), "level"] = np.nan
    live_from = pd.Timestamp(bt["first_live_day"]) - pd.Timedelta(days=1)
    p = p[p["date"] >= live_from]

    lag_rows = []
    for k in range(-3, 4):
        xs, ys = [], []
        for _, g in p.groupby("title"):
            g = g.set_index("date").sort_index()
            rev = g["rev_per_day"]
            sales = g["level"].shift(-k, freq="D").reindex(g.index) if k else g["level"]
            pair = pd.DataFrame({"r": rev, "s": sales}).dropna()
            if len(pair) < 4 or pair["r"].std() == 0 or pair["s"].std() == 0:
                continue
            xs += list(pair["r"] - pair["r"].mean())
            ys += list(pair["s"] - pair["s"].mean())
        corr = float(np.corrcoef(xs, ys)[0, 1]) if len(xs) > 5 else float("nan")
        lag_rows.append({"lag": k, "corr": _r(corr, 3), "pairs": len(xs)})
    best = max((r for r in lag_rows if r["corr"] is not None), key=lambda r: r["corr"])

    # event study around burst onsets
    onsets = burst_onsets(sc)
    ev_rows = []
    for k in range(-3, 4):
        vals = []
        for _, e in onsets.iterrows():
            day = e["date"] + pd.Timedelta(days=k)
            v = p[(p["title"] == e["title"]) & (p["date"] == day)]["rev_per_day"].dropna()
            vals += list(v)
        ev_rows.append({"day": k, "reviews_per_day": _r(np.mean(vals), 2) if vals else None, "n": len(vals)})
    comp = {c["rule"]: c for c in bt["comparisons"]}
    rv = comp.get("Alleen reviewsprong", {})
    before = [r["reviews_per_day"] for r in ev_rows if r["day"] < 0 and r["reviews_per_day"] is not None]
    after = [r["reviews_per_day"] for r in ev_rows if r["day"] >= 0 and r["reviews_per_day"] is not None]
    summary = (
        f"Niet in deze data. Rond de {len(onsets)} bursts lagen reviews vooraf op gemiddeld "
        f"{nl.num(np.mean(before), 1)} per dag en vanaf de burstdag op {nl.num(np.mean(after), 1)} per dag: "
        f"reviews lopen mee of achter, logisch want je reviewt pas na ontvangst. De sterkste samenhang tussen "
        f"reviews en verkoop zit bij een verschuiving van {best['lag']:+d} dag(en) (r = {nl.num(best['corr'], 2)}). "
        f"De regel 'reviewsprong ≥2 in 2 dagen' sloeg {rv.get('alerts', 0)} keer aan en ging "
        f"{rv.get('hits', 0)} keer vooraf aan een burst. Let op: bij 116 van de 134 producten met reviews toont de "
        "dataset alleen het laatste cijfer (9 → 0), dat corrigeren we eerst. Reviews gebruiken we dus als "
        "bevestiging (echte kopers, geen nep-hype), niet als vroeg signaal."
    )
    return {
        "id": "h2",
        "title": "Reviews als vroegste signaal",
        "hypothesis": "Een sprong van +2/+3 reviews in 1-2 dagen bij een stil product komt 1-3 dagen vóór een verkoopburst.",
        "verdict": "niet bevestigd",
        "summary": summary,
        "numbers": [
            {"label": "Reviews per dag vóór burst", "value": nl.num(np.mean(before), 1)},
            {"label": "Reviews per dag vanaf burstdag", "value": nl.num(np.mean(after), 1)},
            {"label": "Reviewsprong vooraf aan burst", "value": f"{rv.get('hits', 0)} van {rv.get('alerts', 0)} keer"},
        ],
        "chart": {"type": "event_study", "rows": ev_rows, "lags": lag_rows},
    }


# --------------------------------------------------------------------------
# H3 discounts
# --------------------------------------------------------------------------
def h3_discounts(run) -> dict:
    prod = run.products.sort_values(["title", "date"])
    sc = run.scored[run.scored["is_measurement"]][["title", "date", "level", "resolution"]]
    m = prod[["title", "date", "final_price", "prev_price", "discount", "price_ok"]].merge(sc, on=["title", "date"])
    m = m.sort_values(["title", "date"])
    events, others = [], []
    for title, g in m.groupby("title"):
        g = g.reset_index(drop=True)
        prev_disc = np.nan
        for i in range(len(g)):
            row = g.loc[i]
            disc_up = (not pd.isna(row["discount"]) and not pd.isna(prev_disc)
                       and row["discount"] - prev_disc >= 5)
            price_drop = (row["price_ok"] and not pd.isna(row["prev_price"]) and row["prev_price"] > 0
                          and row["final_price"] <= 0.95 * row["prev_price"])
            if not pd.isna(row["discount"]):
                prev_disc = row["discount"]
            before = g.loc[max(0, i - 3):i - 1, "level"].dropna()
            after = g.loc[i:i + 1, "level"].dropna()
            if len(before) < 1 or len(after) < 1:
                continue
            base = float(before.median())
            lift = float(after.mean())
            res = row["resolution"] if not pd.isna(row["resolution"]) else 1.0
            floor = 2 * res if res > 1 else 3.0
            up = lift >= config.MOMENTUM_RATIO * base and lift - base >= floor
            rec = {"title": title, "date": row["date"], "base": base, "after": lift, "up": up}
            (events if (disc_up or price_drop) else others).append(rec)
    share_ev = np.mean([e["up"] for e in events]) if events else float("nan")
    share_ot = np.mean([e["up"] for e in others]) if others else float("nan")
    ups = [e for e in events if e["up"]]
    ex = ", ".join(sorted({e["title"][:40] for e in ups}))
    summary = (
        f"Bevestigd. Bij {len(events)} keer korting of een prijsdaling van ≥5% steeg de verkoop daarna "
        f"{len(ups)} keer duidelijk ({nl.num(100 * share_ev)}%), tegen {nl.num(100 * share_ot)}% op gewone dagen"
        + (f" (wel bij: {ex})" if ex else "") + ". "
        "Het enige geval dat erop lijkt: de e.l.f. Melting Lip Balm ging op 15 okt van $35,10 naar $20 en "
        "explodeerde 2 dagen later. Maar de Lip Oil Stick uit dezelfde lijn explodeerde tegelijk zónder korting: "
        "de hype zat in de productlijn, niet in de prijs. (Die korting telt hierboven niet mee, want van vóór "
        "15 okt is er geen betrouwbare verkoop om mee te vergelijken.)"
    )
    return {
        "id": "h3",
        "title": "Korting zorgt niet direct voor meer verkoop",
        "hypothesis": "Kortingen en prijsdalingen leiden niet betrouwbaar tot een directe verkoopstijging.",
        "verdict": "bevestigd",
        "summary": summary,
        "numbers": [
            {"label": "Kortings-/prijsdalingsmomenten", "value": str(len(events))},
            {"label": "Daarna duidelijke stijging", "value": f"{len(ups)} ({nl.num(100 * share_ev)}%)"},
            {"label": "Stijging op gewone dagen", "value": f"{nl.num(100 * share_ot)}%"},
        ],
        "chart": {"type": "bars", "rows": [
            {"label": "Na korting/prijsdaling", "value": _r(100 * share_ev, 1)},
            {"label": "Gewone dagen", "value": _r(100 * share_ot, 1)},
        ], "unit": "% met verkoopstijging"},
    }


# --------------------------------------------------------------------------
# H4 decay
# --------------------------------------------------------------------------
def h4_decay(run) -> dict:
    """How fast do bursts fade, and did posting stop first?"""
    sc = run.scored[run.scored["is_measurement"]].sort_values(["title", "date"])
    episodes = []
    for title, g in sc.groupby("title"):
        g = g.reset_index(drop=True)
        in_burst = list(g["phase"] == "burst")
        i = 0
        while i < len(g):
            if not in_burst[i]:
                i += 1
                continue
            j = i
            while j + 1 < len(g) and in_burst[j + 1]:
                j += 1
            ep = g.loc[i:j]
            peak_i = int(ep["level"].idxmax())
            peak = float(g.loc[peak_i, "level"])
            peak_day = g.loc[peak_i, "date"]
            points, half_days = [], None
            for k in range(peak_i, len(g)):
                t = int((g.loc[k, "date"] - peak_day).days)
                if t > 4:
                    break
                pct = 100 * float(g.loc[k, "level"]) / peak
                points.append({"t": t, "pct": round(pct, 1)})
                if half_days is None and t > 0 and pct <= 50:
                    half_days = t
            last_seen = int((g["date"].iloc[-1] - peak_day).days)
            episodes.append({"title": title, "peak_date": peak_day.strftime("%Y-%m-%d"), "peak": peak,
                             "burst_measurements": int(j - i + 1), "days_to_half": half_days,
                             "days_observed_after_peak": last_seen, "points": points})
            i = j + 1
    halved = [e for e in episodes if e["days_to_half"] is not None]
    within2 = [e for e in halved if e["days_to_half"] <= 2]
    med_half = median([e["days_to_half"] for e in halved]) if halved else float("nan")

    acc = run.panel[run.panel["handle"] == "elfyeah"].drop_duplicates("date").set_index("date")
    elf_decay = acc.loc["2026-10-20":"2026-10-24", "video_cadence"].dropna()
    elf_cad = float(elf_decay.mean()) if len(elf_decay) else float("nan")
    oil = next((e for e in episodes if e["title"] == "e.l.f. Glow Reviver Lip Oil Stick"), None)
    oil_txt = ""
    if oil:
        after = [p for p in oil["points"] if p["t"] > 0]
        path = " → ".join(f"{nl.num(p['pct'])}%" for p in after[:2])
        oil_txt = (f" De e.l.f. Lip Oil Stick piekte {oil['burst_measurements']} metingen lang tot "
                   f"{nl.smart(oil['peak'])} per dag ({nl.date(oil['peak_date'])}) en zakte daarna naar {path} van die piek.")
    summary = (
        f"Deels. Bursts doven veel sneller dan 'halveren in 5-7 dagen': bij {len(within2)} van de {len(episodes)} bursts "
        f"zat de verkoop binnen 2 dagen na de piek al onder de helft (mediaan {nl.smart(med_half)} "
        f"{nl.plural(med_half, 'dag', 'dagen')})." + oil_txt +
        f" En e.l.f. postte tijdens die afkoeling gewoon door ({nl.num(elf_cad, 1)} video's per dag): stoppen met posten "
        "is dus geen voorwaarde voor afkoeling. Voor PostNL betekent dit: na een piek snel afschalen en meteen inzetten "
        "op retourpreventie. De radar rekent daarom na een piek met een halvering van de extra vraag per dag."
    )
    return {
        "id": "h4",
        "title": "Hype dooft als posten stopt",
        "hypothesis": "Dagelijkse verkoop halveert binnen ~5-7 dagen nadat de videostroom opdroogt.",
        "verdict": "deels",
        "summary": summary,
        "numbers": [
            {"label": "Bursts onder de helft binnen 2 dagen", "value": f"{len(within2)} van {len(episodes)}"},
            {"label": "Mediaan dagen tot halvering", "value": nl.smart(med_half)},
            {"label": "e.l.f. video's per dag tijdens afkoeling", "value": nl.num(elf_cad, 1)},
        ],
        "chart": {"type": "decay", "curves": [{"title": e["title"], "peak_date": e["peak_date"], "points": e["points"]}
                                              for e in episodes]},
        "stats": {"episodes": [{k: v for k, v in e.items() if k != "points"} for e in episodes],
                  "median_days_to_half": _r(med_half, 1)},
    }


# --------------------------------------------------------------------------
# H5 categories and sets
# --------------------------------------------------------------------------
def h5_categories(pw: pd.DataFrame) -> dict:
    rows = []
    for t, g in pw.groupby("type"):
        rows.append({"type": t, "label": catalog.TYPE_LABELS.get(t, t), "products": int(len(g)),
                     "units_per_day": round(float(g["units_per_day"].sum()), 1),
                     "median_growth": _r(float(g["growth_pct_per_day"].median()), 3)})
    kb = pw[pw["kbeauty_set"]]
    rows.append({"type": "kbeauty_set", "label": "K-beauty sets (deel van huidverzorging)", "products": int(len(kb)),
                 "units_per_day": round(float(kb["units_per_day"].sum()), 1),
                 "median_growth": _r(float(kb["growth_pct_per_day"].median()), 3)})
    rows.sort(key=lambda r: -r["units_per_day"])
    big_sets = pw[pw["items"] >= 4]
    small = pw[pw["items"] < 4]
    cheap_single = pw[(pw["items"] == 1) & (pw["price"] < 20)]
    rest = pw[~((pw["items"] == 1) & (pw["price"] < 20))]
    by_type = {r["type"]: r for r in rows}
    lip, kset = by_type.get("lip", {}), by_type.get("kbeauty_set", {})
    gum, patch = by_type.get("gummies", {}), by_type.get("patch", {})
    total = float(pw["units_per_day"].sum())
    top = pw.sort_values("units_per_day", ascending=False).head(3)
    summary = (
        f"Deels. Lipproducten ({nl.smart(lip.get('units_per_day', 0))} per dag, vooral de e.l.f. Glow Reviver-lijn) "
        f"en K-beauty sets ({nl.smart(kset.get('units_per_day', 0))} per dag) zijn de grootste verkopers: samen "
        f"{nl.num(100 * (lip.get('units_per_day', 0) + kset.get('units_per_day', 0)) / total)}% van alle verkoop. "
        f"Maar vitamine-gummies ({nl.smart(gum.get('units_per_day', 0))} per dag voor {gum.get('products', 0)} producten) "
        f"en puistjespleisters ({nl.smart(patch.get('units_per_day', 0))} per dag) waren in deze 2 weken níet viraal. "
        f"Sets met 4+ items verkopen per listing gemiddeld {nl.smart(big_sets['units_per_day'].mean())} per dag "
        f"tegen {nl.smart(small['units_per_day'].mean())} voor kleinere listings ({len(big_sets)} sets): klopt. "
        f"Maar goedkope losse producten (<$20) groeiden níet relatief het snelst: mediaan "
        f"{nl.num(cheap_single['growth_pct_per_day'].median(), 2)}% per dag tegen "
        f"{nl.num(rest['growth_pct_per_day'].median(), 2)}% voor de rest."
    )
    return {
        "id": "h5",
        "title": "Virale categorieën en sets",
        "hypothesis": "Lip, K-beauty sets, vitamine-gummies en puistjespleisters gaan viraal; sets (4+) maken de grootste "
                      "totalen, goedkope losse producten groeien relatief het snelst.",
        "verdict": "deels",
        "summary": summary,
        "numbers": [
            {"label": "Lip + K-beauty sets", "value": f"{nl.num(100 * (lip.get('units_per_day', 0) + kset.get('units_per_day', 0)) / total)}% van de verkoop"},
            {"label": "Vitamine-gummies per dag", "value": nl.smart(gum.get("units_per_day", 0))},
            {"label": "Per listing: sets 4+ vs rest", "value": f"{nl.smart(big_sets['units_per_day'].mean())} vs {nl.smart(small['units_per_day'].mean())} per dag"},
            {"label": "Top-verkoper", "value": f"{top.iloc[0]['title'][:38]} ({nl.smart(top.iloc[0]['units_per_day'])} per dag)"},
        ],
        "chart": {"type": "categories", "rows": rows},
    }


def data_quality_card(run, bt: dict) -> dict:
    log = run.log.frame()
    q = run.quality
    gated = int(q["sales_gated"].sum())
    src = q[q["source_change"]]
    wraps = int((log["rule"] == "review_wrap").sum())
    dips = int(log["rule"].isin(["videos_count_dip", "likes_dip"]).sum())
    jump_txt = ""
    if len(src):
        s = src.iloc[0]
        jump_txt = (f" Op {nl.date(s['date'])} veranderde het verkoopcijfer van {nl.num(100 * s['changed_share'])}% van de "
                    f"{s['n_comparable']} vergelijkbare producten tegelijk (normaal 30-40%) en gingen "
                    f"{s['uniform_price_count']} prijzen ×{nl.num(s['uniform_price_ratio'], 2)}: een bronwissel.")
    summary = (
        f"De grootste les: de meeste 'hypes' in deze dataset zijn datafouten. De eerste {gated} dagen bevatten "
        f"afgekapte verkoopcijfers (100% van de waarden had 1 significant cijfer, normaal ~5%)." + jump_txt +
        f" Daarnaast {wraps} review-tellers die van 9 naar 0 springen, {dips} tijdelijke dalingen in "
        "account-tellers, volgers die per 100.000 worden afgerond en ratings van 6 tot 9 op een schaal van 5. "
        f"Daarom draait de radar pas vanaf {nl.date(bt['first_live_day'])} met verkoopsignalen, en checkt de backtest "
        "dat geen enkele dag in de toekomst kijkt "
        f"({'geslaagd' if bt['leakage_check']['passed'] else 'MISLUKT'}: "
        f"{nl.num(bt['leakage_check']['rows_compared'])} product-dagen identiek)."
    )
    return {
        "id": "dq",
        "title": "Eerst de data, dan de hype",
        "hypothesis": "Grote sprongen in volgers, likes of verkoop zijn een hype-signaal.",
        "verdict": "niet bevestigd",
        "summary": summary,
        "numbers": [
            {"label": "Dagen met afgekapte verkoopcijfers", "value": str(gated)},
            {"label": "Bronwissel", "value": nl.date(src.iloc[0]["date"]) if len(src) else "geen"},
            {"label": "Gecorrigeerde review-overlopen", "value": str(wraps)},
        ],
        "chart": None,
    }


def run_hypotheses(run, bt: dict) -> dict:
    pw = product_window(run.products)
    cards = [
        data_quality_card(run, bt),
        h1_video_vs_followers(run, pw, bt),
        h2_reviews(run, bt),
        h3_discounts(run),
        h4_decay(run),
        h5_categories(pw),
    ]
    headline = ("Volgers en losse signalen zeggen weinig. Wat wél werkt: eerst de datafouten eruit, dan de eigen "
                "verkoop van een product volgen en die combineren met merkactiviteit en reviews als bevestiging. "
                "Zo staat elke echte burst op dag 1 op de radar, 1-3 dagen voordat de pakketten bezorgd worden.")
    return {"headline": headline, "cards": cards}
