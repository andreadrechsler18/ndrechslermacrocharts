"""
Master orchestrator - runs all data fetchers in sequence.
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


def run():
    steps = [
        ("CES Employment Data (BLS flat files)", fetch_ces.run),
        ("NIPA Tables (BEA API)", fetch_nipa.run),
        ("M3 Survey (Census API)", fetch_m3.run),
        ("Quarterly Services Survey (Census API)", fetch_qss.run),
        ("Construction Spending (Census API)", fetch_construction.run),
        ("Monthly Wholesale Trade (Census API)", fetch_wholesale.run),
        ("Industrial Production (FRED API)", fetch_fred.run),
    ]

    print("=" * 60)
    print("NewCo Charts - Data Pipeline")
    print("=" * 60)

    total_start = time.time()

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

    total_elapsed = time.time() - total_start
    print(f"\n{'=' * 60}")
    print(f"All done in {total_elapsed:.1f}s")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    run()
