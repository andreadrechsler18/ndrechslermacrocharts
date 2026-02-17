"""
Calendar-aware data pipeline runner.

Reads config/release_calendar.json and only runs fetchers for
datasets that have a release today. Always runs post_process
if any fetcher ran.
"""

import os
import sys
import json
import time
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(__file__))
from utils import CONFIG_DIR

import fetch_ces
import fetch_nipa
import fetch_m3
import fetch_qss
import fetch_construction
import fetch_wholesale
import fetch_fred
import fetch_unemployment
import post_process

# Map calendar keys to fetcher functions
FETCHER_MAP = {
    "bls": [
        ("CES Employment Data", fetch_ces.run),
        ("Unemployment by Industry", fetch_unemployment.run),
    ],
    "bea": [
        ("NIPA Tables", fetch_nipa.run),
    ],
    "census_m3": [
        ("M3 Survey", fetch_m3.run),
    ],
    "census_construction": [
        ("Construction Spending", fetch_construction.run),
    ],
    "census_wholesale": [
        ("Monthly Wholesale Trade", fetch_wholesale.run),
    ],
    "census_qss": [
        ("Quarterly Services Survey", fetch_qss.run),
    ],
    "fred_ip": [
        ("Industrial Production", fetch_fred.run),
    ],
}


def load_calendar():
    path = os.path.join(CONFIG_DIR, 'release_calendar.json')
    if not os.path.exists(path):
        print(f"WARNING: {path} not found. Run fetch_calendar.py first.")
        return None
    with open(path) as f:
        return json.load(f)


def get_todays_fetchers(calendar):
    """Return list of (name, func) for datasets releasing today."""
    today = datetime.now(timezone.utc).strftime('%Y-%m-%d')
    schedules = calendar.get("schedules", {})
    fetchers = []

    for cal_key, dates in schedules.items():
        if today in dates:
            if cal_key in FETCHER_MAP:
                fetchers.extend(FETCHER_MAP[cal_key])

    return fetchers, today


def run():
    calendar = load_calendar()
    if not calendar:
        print("No calendar found - running full pipeline as fallback")
        import fetch_all
        return fetch_all.run()

    fetchers, today = get_todays_fetchers(calendar)

    print("=" * 60)
    print(f"NewCo Charts - Scheduled Update ({today})")
    print("=" * 60)

    if not fetchers:
        print(f"\nNo data releases scheduled for {today}. Nothing to do.")
        # Show next upcoming releases
        schedules = calendar.get("schedules", {})
        upcoming = []
        for key, dates in schedules.items():
            future = [d for d in dates if d > today]
            if future:
                upcoming.append((future[0], key))
        upcoming.sort()
        if upcoming:
            print("\nNext upcoming releases:")
            for date, key in upcoming[:5]:
                print(f"  {date}: {key}")
        return True

    print(f"\n{len(fetchers)} fetcher(s) to run today:")
    for name, _ in fetchers:
        print(f"  - {name}")

    total_start = time.time()
    errors = []

    for name, func in fetchers:
        print(f"\n{'─' * 40}")
        print(f"▶ {name}")
        print(f"{'─' * 40}")
        start = time.time()
        try:
            func()
            elapsed = time.time() - start
            print(f"  Done in {elapsed:.1f}s")
        except Exception as e:
            elapsed = time.time() - start
            print(f"  ERROR after {elapsed:.1f}s: {e}")
            errors.append((name, str(e)))

    # Always run post-processing if any fetcher ran
    print(f"\n{'─' * 40}")
    print(f"▶ Post-processing")
    print(f"{'─' * 40}")
    try:
        post_process.run()
    except Exception as e:
        print(f"  Post-processing ERROR: {e}")
        errors.append(("Post-processing", str(e)))

    total_elapsed = time.time() - total_start
    print(f"\n{'=' * 60}")
    print(f"Done in {total_elapsed:.1f}s")
    if errors:
        print(f"  {len(errors)} errors:")
        for name, err in errors:
            print(f"    - {name}: {err}")
    print(f"{'=' * 60}")

    return len(errors) == 0


if __name__ == "__main__":
    success = run()
    sys.exit(0 if success else 1)
