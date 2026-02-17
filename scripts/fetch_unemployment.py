"""
Fetch BLS Current Population Survey (CPS) unemployment rates by industry.
Uses the BLS Public Data API v2.
"""

import os
import sys
import json
import time
import requests
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(__file__))
from utils import load_api_keys, write_json, period_to_date, HEADERS

BLS_API_URL = "https://api.bls.gov/publicAPI/v2/timeseries/data/"

SERIES = [
    ("LNU04000000", "Total Unemployment Rate"),
    ("LNU04032230", "Agriculture"),
    ("LNU04032231", "Mining, Quarrying, and Oil and Gas"),
    ("LNU04032232", "Construction"),
    ("LNU04032233", "Manufacturing"),
    ("LNU04032235", "Wholesale and Retail Trade"),
    ("LNU04032236", "Transportation and Utilities"),
    ("LNU04032237", "Information"),
    ("LNU04032238", "Financial Activities"),
    ("LNU04032239", "Professional and Business Services"),
    ("LNU04032240", "Education and Health Services"),
    ("LNU04032241", "Leisure and Hospitality"),
    ("LNU04032242", "Other Services"),
    ("LNU04032243", "Public Administration"),
    ("LNU04032244", "Armed Forces"),
    ("LNU04032234", "Durable Goods Manufacturing"),
]


def run():
    print("Fetching Unemployment Rate by Industry from BLS...")
    keys = load_api_keys()
    api_key = keys.get("bls", "")

    series_ids = [s[0] for s in SERIES]
    name_map = {s[0]: s[1] for s in SERIES}

    # BLS API allows up to 50 series and 20 years per request
    # Fetch in two decade chunks to get full history
    all_data = {}
    for start_year, end_year in [(2000, 2014), (2015, 2030)]:
        payload = {
            "seriesid": series_ids,
            "startyear": str(start_year),
            "endyear": str(end_year),
            "registrationkey": api_key
        }

        # BLS API v2 requires POST
        resp = requests.post(BLS_API_URL, json=payload,
                             headers={**HEADERS, "Content-Type": "application/json"},
                             timeout=120)
        resp.raise_for_status()
        result = resp.json()

        if result.get("status") != "REQUEST_SUCCEEDED":
            print(f"  BLS API error: {result.get('message', 'Unknown error')}")
            continue

        for series_result in result.get("Results", {}).get("series", []):
            sid = series_result["seriesID"]
            if sid not in all_data:
                all_data[sid] = []
            for dp in series_result.get("data", []):
                date = period_to_date(dp["year"], dp["period"])
                if date is None:
                    continue
                try:
                    value = float(dp["value"])
                except (ValueError, TypeError):
                    continue
                all_data[sid].append({"date": date, "value": value})

        print(f"  Fetched {start_year}-{end_year}")
        time.sleep(2)

    series_list = []
    for i, (sid, name) in enumerate(SERIES):
        points = all_data.get(sid, [])
        points.sort(key=lambda d: d["date"])
        # Deduplicate by date
        seen = set()
        unique = []
        for p in points:
            if p["date"] not in seen:
                seen.add(p["date"])
                unique.append(p)
        if len(unique) < 2:
            print(f"  Skipping {name}: only {len(unique)} data points")
            continue
        series_list.append({
            "id": sid,
            "name": name,
            "display_order": i,
            "data": unique
        })

    result = {
        "metadata": {
            "title": "Unemployment Rate by Industry",
            "source": "Bureau of Labor Statistics, Current Population Survey (CPS)",
            "unit": "Percent",
            "frequency": "monthly",
            "last_updated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        },
        "series": series_list
    }

    write_json(result, "unemployment/unemployment.json")
    print(f"  {len(series_list)} series written")


if __name__ == "__main__":
    run()
