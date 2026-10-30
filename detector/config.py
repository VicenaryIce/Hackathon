"""All thresholds of the Hype Radar in one place.

Every number here was set *before* looking at the backtest results and is
meant to be explainable to a judge in one sentence. If you change one,
re-run `python3 -m detector` and check the backtest again.
"""
from __future__ import annotations

from pathlib import Path

# --------------------------------------------------------------------------
# Paths
# --------------------------------------------------------------------------
REPO_ROOT = Path(__file__).resolve().parent.parent
# The CSVs are looked up in data/ first, then in the repo root.
DATA_DIR_CANDIDATES = [REPO_ROOT / "data", REPO_ROOT]
OUTPUT_DIR = REPO_ROOT / "detector" / "output"          # logs + CSVs for judges
WEB_DATA_DIR = REPO_ROOT / "web" / "src" / "data"        # JSON read by the UI

# --------------------------------------------------------------------------
# Data-quality rules (clean.py)
# --------------------------------------------------------------------------
# Precision gate: on a healthy day only ~5% of `sold` values have a single
# significant digit (like 7000 or 3). If more than half do, the source sent
# truncated numbers that day and we do not use `sold` from it.
PRECISION_GATE_MAX_ONE_DIGIT_SHARE = 0.50

# Mass-jump rule: normally 30-40% of products change `sold` from one day to
# the next. If >= 80% change on the same day (with at least 20 comparable
# products), the data source changed: deltas into that day are not real.
MASS_JUMP_CHANGED_SHARE = 0.80
MASS_JUMP_MIN_COMPARABLE = 20
# ...or if many products get the *same* price multiplier on one day
# (e.g. everything x1.30), that is a currency/source change, not a sale.
UNIFORM_PRICE_MIN_PRODUCTS = 10

# A price below 30% of the previous price for the same listing is a glitch
# (e.g. pimple patches suddenly "$1.00").
PRICE_GLITCH_MAX_RATIO = 0.30

# Account counters (likes, videos) should never go down. Any dip is treated
# as a scraping artifact; dips larger than this are logged as hard errors.
ACCOUNT_HARD_DROP_SHARE = 0.10

# --------------------------------------------------------------------------
# Signal + phase rules (features.py / score.py)
# --------------------------------------------------------------------------
BASELINE_WINDOW = 4        # previous valid measurements used for the baseline
MIN_BASELINE_OBS = 2       # fewer than this -> "not enough history"

# A change only counts when it is bigger than the counter's noise:
#  - rounded counters (>= 1,000 sold, shown per 100): N rounding steps
#  - exact counters (< 1,000 sold): N x sqrt(baseline) (Poisson noise), with a minimum
# Burst: daily sales at least 2x the product's own baseline AND above 3x noise.
BURST_RATIO = 2.0
BURST_NOISE_MULT = 3
BURST_MIN_EXCESS_UNITS = 5     # minimum for exact (unrounded) counters

# Build-up (Opbouw) sales signal: 1.3x baseline and above 2x noise,
# or sales rising for 2+ measurements in a row by more than 2x noise in total.
MOMENTUM_RATIO = 1.3
MOMENTUM_NOISE_MULT = 2
MOMENTUM_MIN_EXCESS_UNITS = 3
RISING_STREAK_MIN = 2

# Review jump: at least +2 reviews within 2 days on a quiet product
# (quiet = at most 1 review/day before).
REVIEW_JUMP_MIN = 2
REVIEW_JUMP_WINDOW_DAYS = 2
REVIEW_QUIET_MAX_PER_DAY = 1.0

# Brand video cadence over the last 3 days.
VIDEO_WINDOW_DAYS = 3
VIDEO_CADENCE_MIN = 1.0        # >= 1 new video per day

# Decay (Afkoeling): within 7 days after a burst, sales fall to <= 60% of the peak.
DECAY_LOOKBACK_DAYS = 7
DECAY_MAX_SHARE_OF_PEAK = 0.60

# Prediction: build-up seen on >= 2 of the last 3 measurements -> alert
# "explosion within 1-3 days".
ALERT_PERSISTENCE = 2
ALERT_LOOKBACK_OBS = 3
PREDICTION_HORIZON_DAYS = 3

# Hype score = 100 x signal strength x impact.
#  signal strength (0-1): weighted signals below (weights sum to 1). Brand
#  signals (video, likes) only count when the product's own sales move:
#  brand buzz alone is not hype.
#  impact (0.4-1): bigger sellers matter more for parcels (log scale,
#  1/day -> 0.46, 10/day -> 0.61, 100/day -> 0.80, 1000/day -> 1.0).
WEIGHTS = {
    "sales": 0.55,
    "reviews": 0.20,
    "video": 0.15,
    "likes": 0.10,
}
IMPACT_FLOOR = 0.4
IMPACT_FULL_AT = 1000          # sales/day that counts as full impact
DECAY_SCORE_CAP = 35           # a decaying product is never shown as hype

# --------------------------------------------------------------------------
# Forecast + return risk (predict.py)
# --------------------------------------------------------------------------
PARCELS_PER_ORDER = 1.0        # ASSUMPTION: 1 order = 1 parcel
ORDER_TO_DOOR_DAYS = (1, 3)    # ASSUMPTION: an order reaches the customer 1-3 days later
PARCELS_PER_DRIVER = 150       # ASSUMPTION: one extra delivery driver handles ~150 parcels/day
ACTION_MIN_EXTRA_PARCELS = 100 # suggest extra sorting capacity from this many extra parcels/day
FORECAST_DAYS = 7
# Durations from the brief's rule of thumb (checked against the data in insights.json).
BIG_PRODUCT_MIN_PER_DAY = 100  # >= 100/day baseline counts as a "big" product
MICRO_PULSE_DAYS = 3           # small products: 2-4 days elevated
BIG_PEAK_DAYS = 5              # big products: 4-7 days while videos continue
# After the peak the extra demand halves every N days. The brief said 5-7
# days; in this data it fell 60-75% within ONE day (e.l.f., see insights),
# so we use the measured value.
DECAY_HALF_LIFE_DAYS = 1.0

# Calibrated confidence: start at the a-priori estimate (number of signals)
# with the weight of this many pseudo-alerts, then move towards the measured
# hit rate of alerts that were already resolved on that day.
CONFIDENCE_PRIOR_WEIGHT = 2

# --------------------------------------------------------------------------
# UI selection
# --------------------------------------------------------------------------
WATCHLIST_SIZE = 10
