"""
Calendar-aware data pipeline runner.

Reads config/release_calendar.json and only runs fetchers for
datasets that have a release today AND whose release time has passed.
Each source is fetched ~5 minutes after its official release time.

Release times (all Eastern Time):
  BLS (Employment)      - 8:30 AM ET
  BEA (NIPA/GDP)        - 8:30 AM ET
  FRED (Ind. Production) - 9:15 AM ET
  Census (M3, Constr.)  - 10:00 AM ET
"""

import os
import sys
import json
import time
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo

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

ET = ZoneInfo("America/New_York")

# Map calendar keys to (release_hour, release_minute, fetchers)
# Release times are in Eastern Time (handles EST/EDT automatically)
FETCHER_MAP = {
    "bls": {
        "release_time": (8, 30),
        "fetchers": [
            ("CES Employment Data", fetch_ces.run),
            ("Unemployment by Industry", fetch_unemployment.run),
        ],
    },
    "bea": {
        "release_time": (8, 30),
        "fetchers": [
            ("NIPA Tables", fetch_nipa.run),
        ],
    },
    "census_m3": {
        "release_time": (10, 0),
        "fetchers": [
            ("M3 Survey", fetch_m3.run),
        ],
    },
    "census_construction": {
        "release_time": (10, 0),
        "fetchers": [
            ("Construction Spending", fetch_construction.run),
        ],
    },
    "census_wholesale": {
        "release_time": (10, 0),
        "fetchers": [
            ("Monthly Wholesale Trade", fetch_wholesale.run),
        ],
    },
    "census_qss": {
        "release_time": (10, 0),
        "fetchers": [
            ("Quarterly Services Survey", fetch_qss.run),
        ],
    },
    "fred_ip": {
        "release_time": (9, 15),
        "fetchers": [
            ("Industrial Production", fetch_fred.run),
        ],
    },
}

# Minutes to wait after release time before fetching
FETCH_DELAY_MINUTES = 5


def load_calendar():
    path = os.path.join(CONFIG_DIR, 'release_calendar.json')
    if not os.path.exists(path):
        print(f"WARNING: {path} not found. Run fetch_calendar.py first.")
        return None
    with open(path) as f:
        return json.load(f)


def get_ready_fetchers(calendar):
    """Return fetchers for datasets releasing today whose release time has passed."""
    now_et = datetime.now(ET)
    today = now_et.strftime('%Y-%m-%d')
    current_time = (now_et.hour, now_et.minute)
    schedules = calendar.get("schedules", {})
    fetchers = []
    skipped = []

    for cal_key, dates in schedules.items():
        if today in dates and cal_key in FETCHER_MAP:
            entry = FETCHER_MAP[cal_key]
            rh, rm = entry["release_time"]
            fetch_after = (rh, rm + FETCH_DELAY_MINUTES)
            # Handle minute overflow
            if fetch_after[1] >= 60:
                fetch_after = (fetch_after[0] + 1, fetch_after[1] - 60)

            if current_time >= fetch_after:
                fetchers.extend(entry["fetchers"])
            else:
                for name, _ in entry["fetchers"]:
                    skipped.append((name, f"{rh}:{rm:02d} AM ET"))

    return fetchers, skipped, today


def run():
    calendar = load_calendar()
    if not calendar:
        print("No calendar found - running full pipeline as fallback")
        import fetch_all
        return fetch_all.run()

    fetchers, skipped, today = get_ready_fetchers(calendar)
    now_et = datetime.now(ET)

    print("=" * 60)
    print(f"NewCo Charts - Scheduled Update ({today})")
    print(f"  Current time: {now_et.strftime('%I:%M %p %Z')}")
    print("=" * 60)

    if skipped:
        print(f"\nWaiting on {len(skipped)} source(s) (not yet released):")
        for name, release_time in skipped:
            print(f"  - {name} (releases at {release_time})")

    if not fetchers:
        if not skipped:
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
        else:
            print("\nNo sources ready yet. Will run on next scheduled trigger.")
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
