"""
Fetch BLS Producer Price Index (PPI) data for selected professional services.

Covers NAICS 5413 (Architectural, Engineering & Related Services) through
541610-5 (Human Resources Consulting Services) from PPI Table 11.

Uses the BLS API v2 to pull monthly, not seasonally adjusted index values.
"""

import os
import sys
import json
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(__file__))
from utils import load_api_keys, write_json, period_to_date

BLS_API_URL = "https://api.bls.gov/publicAPI/v2/timeseries/data/"

# Series definitions: (BLS series ID, display name)
# Series IDs follow pattern: PCU{industry_code}{product_code}
# Dashes in product codes are removed.
SERIES = [
    # --- Architectural, Engineering & Related Services (5413) ---
    ("PCU5413--5413--", "Architectural, Engineering & Related Services"),

    # Architectural Services (541310)
    ("PCU541310541310",    "Architectural Services"),
    ("PCU541310541310P",   "Architectural - Primary Services"),
    ("PCU5413105413101",   "Architectural - Residential Building"),
    ("PCU5413105413107",   "Architectural - Nonresidential Building"),
    ("PCU54131054131071",  "Architectural - Commercial & Industrial Building"),
    ("PCU54131054131072",  "Architectural - Institutional Building"),
    ("PCU5413105413108",   "Architectural - Other (Historic Restoration, Consulting)"),

    # Engineering Services (541330)
    ("PCU541330541330",    "Engineering Services"),
    ("PCU541330541330P",   "Engineering - Primary Services"),
    ("PCU5413305413301",   "Engineering - Building Related"),
    ("PCU541330541330101", "Engineering - Residential Building"),
    ("PCU541330541330102", "Engineering - Commercial, Public & Institutional Building"),
    ("PCU541330541330103", "Engineering - Industrial & Manufacturing Plant"),
    ("PCU5413305413302",   "Engineering - Non-Building Related"),
    ("PCU541330541330201", "Engineering - Transportation"),
    ("PCU54133054133020101", "Engineering - Highway & Roadway"),
    ("PCU54133054133020102", "Engineering - Other Transportation (Mass Transit)"),
    ("PCU541330541330202", "Engineering - Municipal Utility & Power Generation"),
    ("PCU541330541330203", "Engineering - All Other Non-Building"),
    ("PCU541330541330SM",  "Engineering - Other Receipts"),

    # --- Management & Technical Consulting Services (5416) ---
    ("PCU5416--5416--", "Management & Technical Consulting Services"),

    # Management Consulting Services (541610)
    ("PCU541610541610",    "Management Consulting Services"),
    ("PCU541610541610P",   "Management Consulting - Primary Services"),
    ("PCU5416105416101",   "Management Consulting - Administrative & General"),
    ("PCU5416105416103",   "Management Consulting - Marketing"),
    ("PCU5416105416104",   "Management Consulting - Process, Distribution & Logistics"),
    ("PCU5416105416105",   "Management Consulting - Human Resources"),
]

# BLS API v2 with a registration key allows 20 years per request
# and up to 50 series. We have ~28 series, fits in one request.
START_YEAR = 2006  # Most series start around 06/2006
END_YEAR = datetime.now().year


def run():
    print("Fetching PPI Selected Services from BLS API...")

    keys = load_api_keys()
    bls_key = keys.get('bls', '')
    if not bls_key:
        print("  Warning: No BLS API key found. Limited to 3 years of data.")

    all_series_ids = [s[0] for s in SERIES]
    name_map = {s[0]: s[1] for s in SERIES}

    # BLS API allows 20 years per request with a key.
    # We may need multiple requests to cover the full range.
    all_data = {}  # series_id -> list of {date, value}

    # Fetch in 20-year windows
    year = START_YEAR
    while year <= END_YEAR:
        end = min(year + 19, END_YEAR)
        print(f"  Fetching {year}-{end} ({len(all_series_ids)} series)...")

        payload = {
            "seriesid": all_series_ids,
            "startyear": str(year),
            "endyear": str(end),
        }
        if bls_key:
            payload["registrationkey"] = bls_key

        import requests
        resp = requests.post(BLS_API_URL, json=payload,
                             headers={"Content-Type": "application/json"},
                             timeout=120)
        resp.raise_for_status()
        result = resp.json()

        if result.get("status") != "REQUEST_SUCCEEDED":
            print(f"  BLS API error: {result.get('message', 'Unknown error')}")
            return

        for series in result.get("Results", {}).get("series", []):
            sid = series["seriesID"]
            if sid not in all_data:
                all_data[sid] = []
            for obs in series.get("data", []):
                date_str = period_to_date(int(obs["year"]), obs["period"])
                if date_str and obs["value"] not in ("-", ""):
                    try:
                        val = float(obs["value"])
                        all_data[sid].append({"date": date_str, "value": val})
                    except ValueError:
                        pass

        year = end + 1

    # Build output series list
    series_list = []
    for sid, display_name in SERIES:
        data_points = sorted(all_data.get(sid, []), key=lambda d: d["date"])
        # Deduplicate by date (overlapping windows)
        seen = set()
        unique = []
        for d in data_points:
            if d["date"] not in seen:
                seen.add(d["date"])
                unique.append(d)
        data_points = unique

        if len(data_points) < 6:
            print(f"  Skipping {sid} ({display_name}): only {len(data_points)} data points")
            continue

        series_list.append({
            "id": sid,
            "name": display_name,
            "display_order": len(series_list),
            "data": data_points
        })

    if not series_list:
        print("  Error: No series with sufficient data")
        return

    date_range = f"{series_list[0]['data'][0]['date']} to {series_list[0]['data'][-1]['date']}"
    print(f"  Date range: {date_range}")

    result = {
        "metadata": {
            "title": "PPI - Selected Professional Services",
            "source": "Bureau of Labor Statistics, Producer Price Index (Table 11)",
            "unit": "Index",
            "frequency": "monthly",
            "seasonally_adjusted": False,
            "last_updated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        },
        "series": series_list
    }

    write_json(result, "ppi/ppi_services.json")
    print(f"  {len(series_list)} series written")


if __name__ == "__main__":
    run()
