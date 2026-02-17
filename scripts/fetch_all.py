"""
Master orchestrator - runs all data fetchers in sequence, then post-processes.
"""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(__file__))

import fetch_ces
import fetch_nipa
import fetch_m3
import fetch_qss
import fetch_construction
import fetch_wholesale
import fetch_fred
import fetch_unemployment
import post_process


def run():
    steps = [
        ("CES Employment Data (BLS flat files)", fetch_ces.run),
        ("NIPA Tables (BEA API)", fetch_nipa.run),
        ("M3 Survey (Census API)", fetch_m3.run),
        ("Quarterly Services Survey (Census API)", fetch_qss.run),
        ("Construction Spending (Census Excel)", fetch_construction.run),
        ("Monthly Wholesale Trade (Census API)", fetch_wholesale.run),
        ("Industrial Production (FRED API)", fetch_fred.run),
        ("Unemployment by Industry (BLS API)", fetch_unemployment.run),
        ("Post-processing (derived data)", post_process.run),
    ]

    print("=" * 60)
    print("NewCo Charts - Data Pipeline")
    print("=" * 60)

    total_start = time.time()
    errors = []

    for name, func in steps:
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

    total_elapsed = time.time() - total_start
    print(f"\n{'=' * 60}")
    print(f"All done in {total_elapsed:.1f}s")
    if errors:
        print(f"  {len(errors)} errors:")
        for name, err in errors:
            print(f"    - {name}: {err}")
    print(f"{'=' * 60}")

    return len(errors) == 0


if __name__ == "__main__":
    success = run()
    sys.exit(0 if success else 1)
