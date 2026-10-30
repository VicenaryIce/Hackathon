"""Write everything the UI needs as JSON (web/src/data/) and CSVs for judges
(detector/output/)."""
from __future__ import annotations

import json
import math
from datetime import datetime, timezone

import numpy as np
import pandas as pd

from . import catalog, config, nl
from .mapping import mapping_summary
from .predict import forecast, return_risk
from .score import PHASE_LABELS

HYPE_PHASES = ("burst", "opbouw", "afkoeling")


def _clean(x):
    """Make values JSON-safe (NaN -> None, numpy -> python, dates -> str)."""
    if isinstance(x, dict):
        return {k: _clean(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_clean(v) for v in x]
    if isinstance(x, (pd.Timestamp, datetime)):
        return x.strftime("%Y-%m-%d")
    if isinstance(x, (np.integer,)):
        return int(x)
    if isinstance(x, (np.floating, float)):
        if math.isnan(x) or math.isinf(x):
            return None
        return round(float(x), 2)
    if isinstance(x, (np.bool_,)):
        return bool(x)
    if x is pd.NaT:
        return None
    return x


def _write(path, data) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(_clean(data), ensure_ascii=False, allow_nan=False, separators=(",", ":"))
    path.write_text(text, encoding="utf-8")
    return len(text)


def _short_title(title: str) -> str:
    t = title.replace("[medicube]", "medicube").replace("[COSRX]", "COSRX").replace("[COSRX Official]", "COSRX")
    t = t.replace("[Laka]", "Laka").replace("[LIVE Exclusive]", "").strip()
    for sep in [" - ", " – ", " | ", ", ", " (", " — "]:
        if sep in t and len(t.split(sep)[0]) >= 18:
            t = t.split(sep)[0]
            break
    return t if len(t) <= 52 else t[:50].rstrip() + "…"


# --------------------------------------------------------------------------
# Products: static info + full daily timeline
# --------------------------------------------------------------------------
def product_catalog(run) -> tuple[dict, dict]:
    raw = run.products
    titles = sorted(raw["title"].unique())
    ids = {t: f"p{i + 1:03d}" for i, t in enumerate(titles)}
    links = {m["title"]: m for m in run.mapping}
    info = {}
    for t in titles:
        g = raw[raw["title"] == t]
        cat = str(g["category"].iloc[0])
        ptype = catalog.product_type(t, cat)
        items = catalog.item_count(t)
        colors = g["colors"].dropna()
        n_colors = len([c for c in str(colors.iloc[-1]).split(",") if c.strip()]) if len(colors) else 0
        price = g["final_price"].dropna()
        link = links[t]
        info[ids[t]] = {
            "id": ids[t],
            "title": t,
            "short": _short_title(t),
            "store": link["store_name"],
            "brand": link["brand"] or link["store_name"],
            "handle": link["handle"],
            "match_type": link["match_type"],
            "category": cat,
            "type": ptype,
            "type_label": catalog.TYPE_LABELS.get(ptype, "Overig"),
            "items": items,
            "parcel_size": catalog.parcel_size(t, ptype, items),
            "price": float(price.iloc[-1]) if len(price) else None,
            "n_colors": n_colors,
        }
    return ids, info


def _filled_sales(meas: pd.DataFrame, calendar: list[pd.Timestamp]) -> tuple[list, list]:
    """Spread each measurement's per-day value over the days it covers.
    known_from[i] = index of the day on which that value became known."""
    idx = {d: i for i, d in enumerate(calendar)}
    filled = [None] * len(calendar)
    known = [None] * len(calendar)
    for _, r in meas.iterrows():
        if pd.isna(r["level"]) or pd.isna(r["sales_gap"]):
            continue
        end = idx[r["date"]]
        for k in range(int(r["sales_gap"])):
            i = end - k
            if i >= 0:
                filled[i] = float(r["level"])
                known[i] = end
    return filled, known


def product_timelines(run, ids: dict, calendar: list[pd.Timestamp]) -> dict:
    sc = run.scored.merge(run.panel[["title", "date", "sales_gap", "reviews_corrected", "sold_clean",
                                     "video_cadence", "final_price", "discount"]],
                          on=["title", "date"], how="left", suffixes=("", "_p"))
    out = {}
    for title, g in sc.groupby("title"):
        g = g.sort_values("date").reset_index(drop=True)
        meas = g[g["is_measurement"]]
        filled, known = _filled_sales(meas, calendar)
        out[ids[title]] = {
            "phase": list(g["phase"]),
            "score": [int(s) for s in g["score"]],
            "alert": [bool(a) for a in g["alert"]],
            "confidence": list(g["confidence"]),
            "why": list(g["why"]),
            "prediction": list(g["prediction"]),
            "measured": [bool(m) for m in g["is_measurement"]],
            "stale": list(g["stale_days"]),
            "level": [None if not m else v for m, v in zip(g["is_measurement"], g["level"])],
            "baseline": list(g["baseline"]),
            "sales_filled": filled,
            "known_from": known,
            "sold": list(g["sold_clean"]),
            "reviews": list(g["reviews_corrected"]),
            "reviews_2d": list(g["reviews_2d"]),
            "video_cadence": list(g["video_cadence"]),
            "price": list(g["final_price"]),
            "discount": list(g["discount"]),
            # [sales rising, review jump, brand posts >=1 video/day, likes stepping up]
            "signals": [[int(r["sales_up"]), int(r["review_jump"]), int(r["video_on"]), int(r["likes_on"])]
                        for _, r in g.iterrows()],
            "peak": list(g["peak"]),
            "pre_burst_baseline": list(g["pre_burst_baseline"]),
            "expected_days": list(g["expected_days"]),
        }
    return out


# --------------------------------------------------------------------------
# Replay: what the radar showed on each day (only data up to that day)
# --------------------------------------------------------------------------
def replay(run, ids: dict, info: dict, timelines: dict, alarms: list[dict], calendar: list[pd.Timestamp],
           backtest: dict) -> list[dict]:
    sc = run.scored
    q = run.quality.set_index("date")
    alarm_by_day: dict[str, list[str]] = {}
    for a in alarms:
        alarm_by_day.setdefault(a["date"], []).append(a["id"])
    onsets = {(o["title"], o["date"]) for o in backtest["events"]}
    days_out = []
    for i, day in enumerate(calendar):
        dstr = day.strftime("%Y-%m-%d")
        today = sc[sc["date"] == day].copy()
        today["pid"] = today["title"].map(ids)
        live = today[today["phase"].isin(["stabiel", "opbouw", "burst", "afkoeling"])]
        # first day with sales but no trend yet: show the biggest sellers as "Opwarmen"
        pool = live if len(live) else today[(today["phase"] == "opwarmen") & today["level"].notna()]
        keys = ["score", "level"] if len(live) else ["level"]
        ranked = pool.sort_values(keys, ascending=False)
        watch = []
        for _, r in ranked.head(config.WATCHLIST_SIZE).iterrows():
            fc = forecast(r.to_dict())
            rr = return_risk(r.to_dict(), info[r["pid"]])
            watch.append({
                "id": r["pid"], "score": int(r["score"]), "phase": r["phase"], "alert": bool(r["alert"]),
                "confidence": r["confidence"], "level": r["level"], "baseline": r["baseline"],
                "why": r["why"], "prediction": r["prediction"], "stale_days": int(r["stale_days"]),
                "extra_next": fc["extra"][0], "return_risk": rr,
            })

        # forecast for all products currently in a hype phase (or with an alert)
        hot = today[today["phase"].isin(HYPE_PHASES) | today["alert"]]
        horizon = [(day + pd.Timedelta(days=k)).strftime("%Y-%m-%d") for k in range(1, config.FORECAST_DAYS + 1)]
        tot_normal = [0.0] * config.FORECAST_DAYS
        tot_extra = [0.0] * config.FORECAST_DAYS
        by_size = {"brievenbus": [0.0] * config.FORECAST_DAYS, "pakket": [0.0] * config.FORECAST_DAYS,
                   "groot pakket": [0.0] * config.FORECAST_DAYS}
        contributors = []
        actual = [0.0] * config.FORECAST_DAYS
        actual_known = [True] * config.FORECAST_DAYS
        for _, r in hot.iterrows():
            fc = forecast(r.to_dict())
            size = info[r["pid"]]["parcel_size"]
            for k in range(config.FORECAST_DAYS):
                tot_normal[k] += fc["normal"]
                tot_extra[k] += fc["extra"][k]
                by_size[size][k] += fc["expected"][k]
                j = i + 1 + k
                if j < len(calendar):
                    v = timelines[r["pid"]]["sales_filled"][j]
                    if v is None:
                        actual_known[k] = False
                    else:
                        actual[k] += v
                else:
                    actual_known[k] = False
            contributors.append({"id": r["pid"], "phase": r["phase"], "extra_next": fc["extra"][0],
                                 "expected_next": fc["expected"][0], "normal": fc["normal"]})
        contributors.sort(key=lambda c: -c["extra_next"])

        actions = suggest_actions(day, today, info, ids, tot_extra, contributors, q.loc[day], alarm_by_day.get(dstr, []))
        qd = q.loc[day]
        status = ("afgekapt" if qd["sales_gated"] else "bronwissel" if qd["source_change"]
                  else "opwarmen" if len(live) == 0 or (live["n_history"] == 0).all() else "live")
        days_out.append({
            "date": dstr,
            "index": i,
            "status": status,
            "partial_day": bool(qd["partial_day"]),
            "n_products": int(qd["n_products"]),
            "counts": {p: int((today["phase"] == p).sum()) for p in PHASE_LABELS},
            "watchlist": watch,
            "forecast": {
                "days": horizon,
                "normal": [round(x, 1) for x in tot_normal],
                "extra": [round(x, 1) for x in tot_extra],
                "by_size": {k: [round(x, 1) for x in v] for k, v in by_size.items()},
                "actual": [round(a, 1) if ok else None for a, ok in zip(actual, actual_known)],
                "contributors": contributors[:6],
            },
            "actions": actions,
            "alarms_today": alarm_by_day.get(dstr, []),
            "bursts_today": [ids[t] for (t, d) in onsets if d == dstr],
        })
    return days_out


def suggest_actions(day, today, info, ids, tot_extra, contributors, qd, alarm_ids) -> list[dict]:
    acts = []
    if qd["sales_gated"]:
        acts.append({"kind": "data", "text": "Verkoopcijfers vandaag onbetrouwbaar: geen capaciteitsbeslissingen op basis van deze data."})
        return acts
    if qd["source_change"]:
        acts.append({"kind": "data", "text": "Massale sprong genegeerd (bronwissel): geen extra capaciteit nodig."})
    peak_extra = max(tot_extra) if tot_extra else 0
    if peak_extra >= config.ACTION_MIN_EXTRA_PARCELS:
        drivers = math.ceil(peak_extra / config.PARCELS_PER_DRIVER)
        acts.append({"kind": "sorteren",
                     "text": f"Plan extra sorteercapaciteit voor ~{nl.num(peak_extra)} extra pakketten per dag "
                             f"(piek in de komende {config.FORECAST_DAYS} dagen)."})
        acts.append({"kind": "bezorgers",
                     "text": f"Plan {drivers} extra bezorger{'s' if drivers != 1 else ''} in "
                             f"(aanname: ~{config.PARCELS_PER_DRIVER} pakketten per bezorger per dag)."})
    for c in contributors[:3]:
        p = info[c["id"]]
        if c["phase"] == "burst" and c["extra_next"] >= 1:
            acts.append({"kind": "webshop", "id": c["id"],
                         "text": f"Waarschuw {p['store']}: voorraad '{p['short']}' aanvullen "
                                 f"(+{nl.smart(c['extra_next'])} extra bestellingen per dag verwacht)."})
    for _, r in today[today["alert"]].sort_values("score", ascending=False).head(2).iterrows():
        p = info[ids[r["title"]]]
        acts.append({"kind": "webshop", "id": ids[r["title"]],
                     "text": f"Seintje aan {p['store']}: '{p['short']}' bouwt op "
                             f"({nl.smart(r['level'])} per dag), check de voorraad."})
    if (today["phase"] == "burst").any():
        n_letter = sum(1 for _, r in today[today["phase"] == "burst"].iterrows()
                       if info[ids[r["title"]]]["parcel_size"] == "brievenbus")
        if n_letter:
            acts.append({"kind": "brievenbus",
                         "text": f"{n_letter} van de burst-producten past door de brievenbus: "
                                 "reserveer capaciteit voor brievenbuspakjes."})
    decaying = today[(today["phase"] == "afkoeling") & (today["is_measurement"])]
    for _, r in decaying.sort_values("level", ascending=False).head(2).iterrows():
        p = info[ids[r["title"]]]
        acts.append({"kind": "retour", "id": ids[r["title"]],
                     "text": f"Retourgolf verwacht voor '{p['short']}': plan retourcapaciteit, "
                             "track & trace toont nu gebruikstips."})
    if not acts:
        acts.append({"kind": "rust", "text": "Geen hype in aantocht: normale capaciteit volstaat."})
    return acts


# --------------------------------------------------------------------------
# Main export
# --------------------------------------------------------------------------
def export_all(run, backtest: dict, insights: dict, alarms: list[dict]) -> dict:
    calendar = list(run.quality["date"])
    ids, info = product_catalog(run)
    timelines = product_timelines(run, ids, calendar)
    for pid in info:
        info[pid]["timeline"] = timelines[pid]

    # backtest events/alerts with product ids for the UI
    title_to_id = ids
    for key in ("events", "hits", "false_alarms", "open_alerts"):
        for e in backtest[key]:
            e["id"] = title_to_id.get(e["title"])
    for a in alarms:
        a["product_id"] = title_to_id.get(a["entity"])

    days = replay(run, ids, info, timelines, alarms, calendar, backtest)

    q = run.quality
    meta = {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "dates": [d.strftime("%Y-%m-%d") for d in calendar],
        "first_live_day": backtest["first_live_day"],
        "phase_labels": PHASE_LABELS,
        "day_quality": [
            {"date": r["date"].strftime("%Y-%m-%d"), "n_products": int(r["n_products"]),
             "one_digit_share": r["one_digit_share"], "sales_gated": bool(r["sales_gated"]),
             "changed_share": r["changed_share"], "uniform_price_count": int(r["uniform_price_count"]),
             "source_change": bool(r["source_change"]), "partial_day": bool(r["partial_day"])}
            for _, r in q.iterrows()
        ],
        "exclusions": run.log.summary(),
        "mapping": mapping_summary(run.mapping),
        "assumptions": [
            "1 bestelling = 1 pakket.",
            f"Een bestelling wordt {config.ORDER_TO_DOOR_DAYS[0]}-{config.ORDER_TO_DOOR_DAYS[1]} dagen later bezorgd.",
            f"Eén extra bezorger rijdt ~{config.PARCELS_PER_DRIVER} pakketten per dag.",
            "Dit is data van TikTok Shop VS: de aantallen illustreren de methode, het zijn geen Nederlandse volumes.",
            "Retourrisico is een heuristiek (fase, categorie, prijs, aantal tinten): de dataset heeft geen retourdata.",
            "Na een piek halveert de extra vraag elke dag (gemeten: 5 van de 7 bursts zaten binnen 2 dagen onder "
            "de helft; de vuistregel 'halveren in 5-7 dagen' klopte hier niet).",
        ],
        "config": {
            "burst_ratio": config.BURST_RATIO, "momentum_ratio": config.MOMENTUM_RATIO,
            "review_jump": config.REVIEW_JUMP_MIN, "video_cadence": config.VIDEO_CADENCE_MIN,
            "decay_share": config.DECAY_MAX_SHARE_OF_PEAK, "horizon": config.PREDICTION_HORIZON_DAYS,
            "weights": config.WEIGHTS, "parcels_per_driver": config.PARCELS_PER_DRIVER,
            "order_to_door": list(config.ORDER_TO_DOOR_DAYS),
        },
    }

    out = config.WEB_DATA_DIR
    sizes = {
        "meta.json": _write(out / "meta.json", meta),
        "products.json": _write(out / "products.json", info),
        "replay.json": _write(out / "replay.json", days),
        "backtest.json": _write(out / "backtest.json", backtest),
        "alarms.json": _write(out / "alarms.json", alarms),
        "insights.json": _write(out / "insights.json", insights),
    }

    # CSVs for judges
    od = config.OUTPUT_DIR
    od.mkdir(parents=True, exist_ok=True)
    run.log.frame().to_csv(od / "exclusion_log.csv", index=False)
    pd.DataFrame(run.mapping).to_csv(od / "product_account_mapping.csv", index=False)
    cols = ["date", "title", "phase", "score", "alert", "confidence", "level", "baseline", "ratio", "streak",
            "reviews_2d", "review_jump", "video_cadence", "video_on", "likes_on", "n_signals", "why", "prediction"]
    run.scored[cols].sort_values(["date", "score"], ascending=[True, False]).to_csv(od / "daily_scores.csv", index=False)
    q.to_csv(od / "day_quality.csv", index=False)
    return sizes
