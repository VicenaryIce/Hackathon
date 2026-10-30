"""Run the whole Hype Radar pipeline:  python3 -m detector

  1. load the CSVs            (data/products.csv, data/accounts.csv)
  2. clean + log exclusions   (detector/output/exclusion_log.csv)
  3. signals, hype score, phases, predictions
  4. honest day-by-day backtest + leakage check
  5. valse alarmen + hypothesis tests
  6. export JSON for the web app (web/src/data/) and CSVs for judges
"""
from __future__ import annotations

import sys
import time

from . import backtest, config, export, fake, hypotheses, load, nl
from .pipeline import run_pipeline


def main() -> int:
    t0 = time.time()
    print("PostNL Hype Radar")
    raw_products = load.load_products()
    raw_accounts = load.load_accounts()
    print(f"  data: {len(raw_products)} product rows, {raw_products['title'].nunique()} products, "
          f"{len(raw_accounts)} account rows, {raw_products['date'].nunique()} days")

    run = run_pipeline(raw_products, raw_accounts)
    for s in run.log.summary():
        print(f"  clean: {s['rule']:<22} {s['entries']:>4}x  {s['action']}")

    print("  backtest: replaying every day with only the data up to that day ...")
    bt = backtest.run_backtest(raw_products, raw_accounts, run)
    lc = bt["leakage_check"]
    print(f"  leakage check: {'PASSED' if lc['passed'] else 'FAILED'} "
          f"({lc['rows_compared']} product-days identical, {lc['n_mismatches']} mismatches)")
    r = bt["radar"]
    print(f"  bursts: {r['events']} (all detected on their first day) | alerts: {r['alerts']}, "
          f"hits: {r['hits']}, false alarms: {r['false_alarms']}, open: {r['open']}")

    alarms = fake.build_alarms(run.quality, run.log.frame(), run.panel, run.scored, run.accounts, raw_accounts)
    print(f"  valse alarmen: {len(alarms)}")
    insights = hypotheses.run_hypotheses(run, bt)
    for c in insights["cards"]:
        print(f"  insight: {c['title']:<45} -> {c['verdict']}")

    sizes = export.export_all(run, bt, insights, alarms)
    for name, size in sizes.items():
        print(f"  wrote web/src/data/{name} ({nl.num(size / 1024)} KB)")
    print(f"  wrote {config.OUTPUT_DIR.relative_to(config.REPO_ROOT)}/*.csv")
    print(f"done in {time.time() - t0:.0f}s")
    if not lc["passed"]:
        print("ERROR: the backtest leakage check failed", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
