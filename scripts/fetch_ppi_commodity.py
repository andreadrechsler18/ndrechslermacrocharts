"""
Fetch BLS Producer Price Index (PPI) data by commodity group.

Covers commodity group 45 "Professional Services" from PPI Table 9,
item codes 1 through 610101 (Legal Services through IT Consulting).

Uses the BLS API v2 to pull monthly, not seasonally adjusted index values.
Series IDs follow pattern: WPU{commodity_group}{item_code} (dashes removed).
"""

import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(__file__))
from utils import load_api_keys, write_json, period_to_date

BLS_API_URL = "https://api.bls.gov/publicAPI/v2/timeseries/data/"

# Series definitions: (BLS series ID, display name)
# Commodity group 45 = Professional Services
SERIES = [
    # --- Group aggregate ---
    ("WPU45",        "Professional Services"),

    # --- 45-1: Legal Services ---
    ("WPU451",       "Legal Services"),
    ("WPU4511",      "Legal Services (4511)"),
    ("WPU451101",    "Legal Services (451101)"),
    ("WPU45110101",  "Legal Services (45110101)"),

    # --- 45-2: Accounting Services ---
    ("WPU452",       "Accounting Services"),
    ("WPU4521",      "Accounting Services, excl. Payroll"),
    ("WPU452101",    "Financial Auditing"),
    ("WPU45210101",  "Financial Auditing (detail)"),
    ("WPU452102",    "Tax Preparation & Planning"),
    ("WPU45210201",  "Tax Preparation & Planning (detail)"),
    ("WPU452104",    "Other Accounting (Billing & Review)"),
    ("WPU45210401",  "Other Accounting (Billing & Review, detail)"),
    ("WPU452105",    "Bookkeeping & Compilation"),
    ("WPU45210501",  "Bookkeeping & Compilation (detail)"),

    # --- 45-3: Architectural & Engineering Services ---
    ("WPU453",       "Architectural & Engineering Services"),
    ("WPU4531",      "Architectural Services"),
    ("WPU453101",    "Architectural Services (453101)"),
    ("WPU45310101",  "Architectural Services (detail)"),
    ("WPU4532",      "Engineering Services"),
    ("WPU453201",    "Engineering Services (453201)"),
    ("WPU45320101",  "Engineering Services (detail)"),

    # --- 45-4: Management, Scientific & Technical Consulting ---
    ("WPU454",       "Management, Scientific & Technical Consulting"),
    ("WPU4541",      "Management Consulting Services"),
    ("WPU454101",    "Administrative & General Management Consulting"),
    ("WPU45410101",  "Administrative & General Management Consulting (detail)"),
    ("WPU454102",    "Human Resources Consulting"),
    ("WPU45410201",  "Human Resources Consulting (detail)"),
    ("WPU454103",    "Marketing Consulting"),
    ("WPU45410301",  "Marketing Consulting (detail)"),
    ("WPU454104",    "Process, Distribution & Logistics Consulting"),
    ("WPU45410401",  "Process, Distribution & Logistics Consulting (detail)"),

    # --- 45-5: Advertising & Related Services ---
    ("WPU455",       "Advertising & Related Services"),
    ("WPU4551",      "Advertising Agency Services"),
    ("WPU455101",    "Advertising Agency Services (455101)"),
    ("WPU45510101",  "Advertising Agency Services (detail)"),

    # --- 45-6: Information Technology Services ---
    ("WPU456",       "IT Technical Support & Consulting"),
    ("WPU4561",      "IT Technical Support & Consulting (4561)"),
    ("WPU456101",    "IT Technical Support & Consulting (456101)"),
    ("WPU45610101",  "IT Technical Support & Consulting (detail)"),
]

# Most commodity 45 series start around Dec 2008 / mid-2009
START_YEAR = 2007
END_YEAR = datetime.now().year


def run():
    print("Fetching PPI Commodity Group 45 from BLS API...")

    keys = load_api_keys()
    bls_key = keys.get('bls', '')
    if not bls_key:
        print("  Warning: No BLS API key found. Limited to 3 years of data.")

    all_series_ids = [s[0] for s in SERIES]
    name_map = {s[0]: s[1] for s in SERIES}

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
            "title": "PPI - By Commodity (Professional Services)",
            "source": "Bureau of Labor Statistics, Producer Price Index (Table 9)",
            "unit": "Index",
            "frequency": "monthly",
            "seasonally_adjusted": False,
            "last_updated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        },
        "series": series_list
    }

    write_json(result, "ppi/ppi_commodity.json")
    print(f"  {len(series_list)} series written")


if __name__ == "__main__":
    run()
