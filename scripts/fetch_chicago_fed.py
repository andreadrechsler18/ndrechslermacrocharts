"""
Fetch Chicago Fed Survey of Economic Conditions (CFSEC) via FRED API.

Uses FRED as the source rather than scraping chicagofed.org — same reason
as fetch_fred.py (industrial production): FRED serves the full release
reliably from a stable API, while the Chicago Fed site would be another
scrape to babysit.

Release: FRED release_id 372 (CFSEC). Monthly.
"""

import os
import sys
import time
from datetime import datetime

sys.path.insert(0, os.path.dirname(__file__))
from utils import load_api_keys, write_json, retry_request

FRED_URL = "https://api.stlouisfed.org/fred/series/observations"

# Ordered so composite/activity leads, then sector splits, then components.
# Excludes CFSBCWAGECOSTS and CFSBCNWAGECOSTS (both discontinued).
CFSEC_SERIES = [
    ("CFSBCACTIVITY",       "Composite Activity Index"),
    ("CFSBCACTIVITYMFG",    "Manufacturing Activity Index"),
    ("CFSBCACTIVITYNMFG",   "Non-manufacturing Activity Index"),
    ("CFSBCHIRING",         "Current Hiring"),
    ("CFSBCHIRINGEXP",      "Hiring Expectations (12-month)"),
    ("CFSBCCAPX",           "Current Capital Spending"),
    ("CFSBCCAPXEXP",        "Capital Spending Expectations (12-month)"),
    ("CFSBCLABORCOSTS",     "Labor Costs"),
    ("CFSBCNONLABORCOSTS",  "Nonlabor Costs"),
    ("CFSBCOUTLOOK",        "12-month US Economic Outlook"),
]


def fetch_fred_series(api_key, series_id):
    params = {
        "series_id": series_id,
        "api_key": api_key,
        "file_type": "json",
        "observation_start": "2000-01-01",
    }
    resp = retry_request(FRED_URL, params=params)
    observations = resp.json().get("observations", [])
    points = []
    for obs in observations:
        date_str = obs.get("date", "")
        val_str = obs.get("value", "")
        try:
            value = float(val_str) if val_str and val_str != "." else None
        except ValueError:
            value = None
        if date_str:
            points.append({"date": date_str, "value": value})
    return points


def run():
    print("Fetching Chicago Fed Survey of Economic Conditions from FRED...")
    keys = load_api_keys()
    api_key = keys["fred"]

    series_list = []
    for i, (series_id, name) in enumerate(CFSEC_SERIES):
        print(f"  [{i+1}/{len(CFSEC_SERIES)}] {series_id} - {name}...")
        try:
            data = fetch_fred_series(api_key, series_id)
        except Exception as e:
            print(f"    Skipping {series_id}: {e}")
            continue
        if data and len(data) >= 2:
            series_list.append({
                "id": series_id,
                "name": f"Chicago - {name}",
                "display_order": i,
                "data": data,
            })
            print(f"    {len(data)} observations")
        else:
            print(f"    No data for {series_id}")
        time.sleep(0.6)  # FRED rate limit ~120 req/min

    result = {
        "metadata": {
            "title": "Chicago Fed Survey of Economic Conditions",
            "source": "Federal Reserve Bank of Chicago (via FRED, release 372)",
            "unit": "Diffusion Index",
            "frequency": "monthly",
            "last_updated": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        },
        "series": series_list,
    }
    write_json(result, "fed_surveys/fed_chicago.json")
    print(f"  {len(series_list)} series written")


if __name__ == "__main__":
    run()
