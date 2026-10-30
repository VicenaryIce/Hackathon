# Hype Radar · PostNL Pad A: "De Hype-Radar"

> **Kun je een hype voorspellen voordat die bij je wordt bezorgd?**

This is a hackathon concept (not an official PostNL product), built on the Hackathon for Good TikTok Shop dataset. It has three parts:

1. **Predict.** Per product: normal parcels next week, how many parcels if it goes viral, and the chance that it does (tab "Voorspelling").
2. **Detect.** A detector (Python, pandas) gives every product a hype score (0-100) and a phase per day, and filters out fake hype ("valse alarmen") (tab "Hype Radar").
3. **Explain.** What the data does and doesn't show, with an honest backtest (tab "Inzichten").

## Run it

```bash
# 1. Web app (Vite + React + Tailwind + Recharts). Node 18+
cd web
npm install        # once
npm run dev        # opens http://localhost:5173

# 2. Detector (optional: its output is already in web/src/data/). Python 3.9+ with pandas
pip install -r detector/requirements.txt
python3 -m detector          # about 30 s, including the day-by-day backtest
```

**No wifi or no Node on the demo laptop?** Double-click `demo/hype-radar.html`. It is the whole app in one file and works offline. After changing the data, rebuild it with `cd web && npm run build:demo && mv ../demo/index.html ../demo/hype-radar.html`.

## Why this stack
Vite + React + Recharts was the brief's suggestion. It lets the replay slider drive every panel from one state, and Vite's single-file build gives an offline backup for the projector.

## Repository layout
| Path | What |
|---|---|
| `data/` | the dataset as delivered (CSV files plus the original README/LEESMIJ) |
| `detector/` | the pipeline: `clean.py` → `features.py` → `score.py` → `backtest.py`, `fake.py`, `hypotheses.py`, `export.py`. **All thresholds are in `config.py`.** |
| `detector/output/` | CSVs for the judges: `exclusion_log.csv` (every excluded or corrected value, with a reason), `daily_scores.csv`, `product_account_mapping.csv`, `day_quality.csv` |
| `web/` | the UI. It reads `web/src/data/*.json` |
| `demo/hype-radar.html` | offline single-file build |

## What we found in the data (read this first)
| Quirk | Verified? | What we do |
|---|---|---|
| `sold` on **9-13 Oct is broken** | **Yes, and worse than expected.** 100% of the values have a single significant digit (7000, 3, ...); from 14 Oct it is ~5% | *Precision gate*: `sold` is ignored on those days |
| Mass jump with a uniform price change | **Yes, on 14 Oct.** All 145 comparable products changed `sold` (normally 30-40%) and 22 prices went ×1.30 | Flagged as a data-source change. A new series starts here and the jump is never counted as hype |
| `sold` goes down | Only in the broken window. From 14 Oct it never decreases | We keep a running maximum anyway |
| Big counters rounded to 1,000 | **No: rounded to 100** (and to 100k above 1M) | Noise-aware thresholds: a change has to be more than 2-3 rounding steps |
| >10% drops in likes/videos | **None exist.** There are smaller one-day dips (e.l.f. 18 Oct: 2056 → 2043 videos) and The Ordinary shows 0 followers on 24 Oct | Every dip in a running total is treated as an artifact |
| Not in the brief | `reviews_count` keeps only the **last digit** for 116 of the 134 products that have reviews (all 13 decreases are 9 → 0) | Wraps corrected (9 → 0 = +1) |
| Not in the brief | Followers are rounded to 100k for 7 of the 10 brands, so "+100k" is just the rounded number ticking over | Shown as a valse alarm |
| Not in the brief | `prodct_rating` is 6-9 in 547 rows; 2 rows are priced in SGD; 6 prices of $1-$4 on 26 Oct; `skincarebyhyram` on 9 Oct is a boxing gym in Frankfurt | Ignored or dropped, and logged |

That leaves **14 trustworthy snapshots (14-27 Oct)**. Days 22 and 25 Oct are partial, so every delta is divided by the actual number of days between snapshots.

**Linking products to accounts** (`product_account_mapping.csv`): 176 products link through their own brand store, 5 reseller listings link through the brand name in the title (Unineed, StrawberryNet, FragranceNet), and 18 products from 18 other stores have no TikTok account. The creators are not linked to any product.

## The signals
Every signal on day D uses only data up to day D.

| Signal | Meaning |
|---|---|
| **Daily sales** | difference in `sold` between snapshots ÷ number of days in between |
| **Baseline** | median daily sales over the product's previous 4 measurements |
| **Sales rising** | ≥1.3× baseline and above 2× noise, or rising 2+ measurements in a row (noise = 1 rounding step of 100, or √baseline for exact small counts) |
| **Review jump** | ≥ +2 wrap-corrected reviews in 2 days on a product that normally gets ≤1 per day |
| **Brand posts** | the linked account posted ≥1 new video per day over the last 3 days |
| **Likes rising** | the account's likes went up at least one rounding step in 3 days |

**Phases:** *Stabiel* · *Opbouw* (the product's own sales are rising **plus** at least one other signal) · *Burst* (daily sales ≥2× its own baseline and above 3× noise) · *Afkoeling* (after a burst, sales fall to ≤60% of the peak; this is never labelled as new hype). There are also two data states: *Geen data* and *Opwarmen*.

**Hype score** = 100 × signal strength × impact. Signal strength is 55% sales, 20% reviews, 15% videos and 10% likes. Brand signals only count when the product's own sales move. Impact scales on a log scale from 0.4 for tiny sellers to 1.0 at 1,000+ per day.

**Prediction:** if Opbouw shows up on 2 of the last 3 measurements, or with 3 or more signals, the radar says "explosie binnen 1-3 dagen". The confidence starts from a prior based on the number of signals and then moves towards the hit rate of earlier alerts that have already resolved, so the radar learns from its own mistakes.

## Backtest (honest)
`backtest.py` reruns the **whole pipeline once per day using only the data up to that day**. A leakage check confirms the result is identical to the full run: **passed, 3,757 product-days identical**.

| | |
|---|---|
| Bursts in the clean window | **7** (e.l.f. Lip Oil Stick 16 Oct and 25 Oct, e.l.f. Melting Lip Balm 17 Oct and 25 Oct, Sol de Janeiro Shower Oil 18 Oct, CeraVe Night Cream 22 Oct, Starface Star Treatment 23 Oct) |
| Detected on their first day | **7 of 7** |
| Predicted 1-3 days ahead | **0 of 7** |
| Opbouw alerts | 4, all on small products, none followed by a burst |
| Lead over delivery | **1-3 days**, because orders placed on the burst day are delivered 1-3 days later (assumption) |

Single-signal rules on the same bursts: followers rising predicted 0 of 7 bursts (533 alerts). "Brand posts ≥1 video per day" was on before 3 of 7 bursts, but fired 723 times (1% hit rate). A review jump predicted 0 of 14.

**Takeaway:** in 13 days of clean data, no signal reliably appeared *before* a burst. The radar's value is that it sees a burst on day 1, filters out the artifacts and forecasts the parcel wave before it reaches the network. Real forward prediction needs months of data, and this backtest is ready to test it. We **did not add an ML model**: with 7 bursts and no leading signal, a trained model would only learn noise.

## Hypotheses tested (details are on the Inzichten page)
| Hypothesis | Verdict | Numbers |
|---|---|---|
| Video cadence beats followers | **Partly** | Followers: 0 of 7 bursts. But NYX posts the most (2.1 per day) and sells the least; brands with more videos sell *less* (Spearman ρ = −0.55); daily posters grew 1.5×, not 5-10×. The one case that fits: e.l.f. resumed daily posting on 14 Oct and its line exploded 2 days later |
| Reviews are the earliest signal | **Not confirmed** | Reviews averaged 0.3 per day before a burst and 0.8 per day from the burst day on; strongest correlation on the same day; the rule went 0 for 14 |
| Discounts don't reliably lift sales | **Confirmed** | 29 discounts or price drops: 0 followed by a clear increase (normal days: 1%) |
| Hype fades when posting stops (halving in 5-7 days) | **Partly** | Much faster: 5 of 7 bursts were below half within 2 days. e.l.f. kept posting (1.3 per day) and cooled down anyway |
| Viral categories and sets | **Partly** | Lip products and K-beauty sets make up 51% of sales; gummies and patches were *not* viral; 4+ item sets sell 91 per day per listing vs 30; cheap single items did *not* grow fastest |

## Assumptions and limitations
- 1 order = 1 parcel. An order is delivered 1-3 days later. One extra delivery driver handles ~150 parcels per day.
- This is **US** TikTok Shop data, so the volumes illustrate the method and are not Dutch parcel numbers.
- **Return risk is a heuristic** (phase, category, price, number of shades). The dataset has no returns.
- After a peak, the forecast halves the extra demand every day (measured here; the brief's 5-7 days did not hold).
- Only 14 usable days and 7 bursts: every percentage above is a small sample.
- Product type and parcel size come from keyword rules (`detector/catalog.py`).

## Hype scenario per product (`detector/scenario.py`, tab "Voorspelling", the first tab)
The first tab is about the future, per product: **normal parcels → parcels if it goes viral → chance and timing**.

1. **Normaal:** the momentum model's forecast for next week (see above).
2. **Als het viraal gaat:** learned from the 4 big hypes in the data (e.l.f. Lip Oil Stick and Melting Lip Balm, two waves each, all selling ≥50/day before the hype). Orders peaked at **2.0-2.7× normal (median 2.2×)** for **2-4 days**, adding **1.25-4.5 days' worth of normal sales (median 2.9)** in extra orders. The 3 bursts on tiny products (0-3 per day) are left out of these multipliers, because ratios like "16×" on 1 order a day are noise.
3. **Wanneer:** a date cannot be predicted (no signal showed up before a burst, see the backtest). Instead:
   - **live status** from the radar (Nu viraal / Signaal / Koelt af / Rustig), and
   - **chance of a hype in the next 7 days**: how often this product type, and this product itself, went viral in the clean days (16-27 Oct). Rates are smoothed towards the overall rate (2.6% per week), so a type without hypes gets a small chance instead of 0%. Lip products: ~10% per week; most other types: 1-2%.
   - Once the radar sees a burst, the parcels reach PostNL **1-3 days later**: that is PostNL's preparation time.

The list is ranked by **chance × extra parcels**. The scenario chart shows an example hype starting in 2 days, with the parcels arriving ~2 days after the orders.

Limitation: 7 hypes (4 big ones, all from one brand) in 12 clean days. Treat the multipliers and chances as a first estimate that should be re-fitted on more data.

## Deploy (Vercel)
`vercel.json` builds only the static web app (`web/` → `web/dist`). The Python detector is not deployed: its output is committed in `web/src/data/`.

## Momentum model: orders next week (`detector/momentum.py`, tab "Voorspelling")
Built from `hype-radar-findings-report.md`. Social signals did not predict orders; a product's own last week did.

- **Fit** (one complete week pair, 14→20 vs 20→27 Oct, 181 products): `log(1 + next week) = 0.78 × log(1 + this week) + 0.21`, R² **0.64** (the report said 0.78 / 0.22 / 0.63).
- **For parcels we use the simple version: next week ≈ 0.80× this week**, range 0.32-1.06× (quartiles). The log version underestimates big sellers: total 2,550 predicted vs 4,715 actual orders/day. The ratio version predicts 5,115 (+8%).
- **Validation** (same week pair, ratio version): 65% of products selling ≥1/day within 2× (the report said 76%), top-10 overlap 7/10 (report: 8/10).
- **Honest out-of-sample check:** forecast made on 21 Oct with only data up to then: 53% within 2×, median 0.59× of actual (it underestimated, because e.l.f.'s cooldown made the short-window ratio low).
- **Rolling forecasts** for 21-27 Oct use only data up to that day. Before 28 Oct there is no complete earlier week pair, so the rolling fit compares two half-windows (e.g. 15-18 vs 18-21 Oct).
- **Phases:** Groeiend (week-over-week >1.2), Stabiel (0.8-1.2), Afkoelend (<0.8, flagged for return risk, an estimate). Products under 1 order/day: "te weinig data".
- `hype_boost` slot in `predict_ratio()` for future creator-video data, default 0 (no effect size invented).
- Limitation: only one week-to-week test in 13 clean days, so this is a first estimate.
