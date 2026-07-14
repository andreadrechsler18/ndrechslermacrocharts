"""
Fetch JOLTS (Job Openings and Labor Turnover Survey) via FRED API.

Uses FRED release 192 as the source. Fetches all seasonally-adjusted (JTS*)
series across the 5 measures × 20 categories × Level + Rate = ~180 series.
Skips the not-seasonally-adjusted JTU* series.
"""

import os
import sys
import time
from datetime import datetime

sys.path.insert(0, os.path.dirname(__file__))
from utils import load_api_keys, write_json, retry_request

FRED_URL = "https://api.stlouisfed.org/fred/series/observations"
FRED_RELEASE_SERIES_URL = "https://api.stlouisfed.org/fred/release/series"
JOLTS_RELEASE_ID = 192

# FRED suffix -> (display measure, is_rate)
MEASURE_SUFFIXES = {
    "JOL": ("Job Openings", False),
    "JOR": ("Job Openings Rate", True),
    "HIL": ("Hires", False),
    "HIR": ("Hires Rate", True),
    "TSL": ("Total Separations", False),
    "TSR": ("Total Separations Rate", True),
    "QUL": ("Quits", False),
    "QUR": ("Quits Rate", True),
    "LDL": ("Layoffs & Discharges", False),
    "LDR": ("Layoffs & Discharges Rate", True),
}


def list_sa_series(api_key):
    """Enumerate all JTS* series (seasonally-adjusted) in the JOLTS release."""
    params = {
        "release_id": JOLTS_RELEASE_ID,
        "api_key": api_key,
        "file_type": "json",
        "limit": 1000,
    }
    resp = retry_request(FRED_RELEASE_SERIES_URL, params=params)
    data = resp.json()
    seriess = data.get("seriess", [])
    return [s for s in seriess if s["id"].startswith("JTS")]


def category_from_title(title):
    """Extract the industry/region label from a FRED title like
    'Job Openings: Manufacturing' or 'Hires Rate: Total Nonfarm in West Census Region'.
    """
    if ":" not in title:
        return title.strip()
    return title.split(":", 1)[1].strip()


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
    print("Fetching JOLTS data from FRED (release 192)...")
    keys = load_api_keys()
    api_key = keys["fred"]

    catalog = list_sa_series(api_key)
    print(f"  {len(catalog)} seasonally-adjusted JOLTS series to fetch")

    series_list = []
    for i, meta in enumerate(catalog):
        sid = meta["id"]
        title = meta.get("title", sid)
        # Identify measure suffix
        measure_suffix = None
        for suf in MEASURE_SUFFIXES:
            if sid.endswith(suf):
                measure_suffix = suf
                break
        if not measure_suffix:
            print(f"  [{i+1}/{len(catalog)}] Skipping {sid} — no known measure suffix")
            continue

        measure_label, _ = MEASURE_SUFFIXES[measure_suffix]
        category = category_from_title(title)
        display_name = f"{category} - {measure_label}"

        # Site-standard series ID: <category-code>_<measure_suffix>
        # Uses the FRED middle segment (between JTS and the measure). For total
        # nonfarm the FRED ID has no middle segment (bare "JTSJOL"), so we use "TOTAL".
        middle = sid[3:-3] if len(sid) > 6 else "TOTAL"
        site_id = f"JOLTS_{middle}_{measure_suffix}" if middle else f"JOLTS_TOTAL_{measure_suffix}"

        print(f"  [{i+1}/{len(catalog)}] {sid} - {display_name}...")
        try:
            data = fetch_fred_series(api_key, sid)
        except Exception as e:
            print(f"    Skipping {sid}: {e}")
            continue
        if data and len(data) >= 2:
            series_list.append({
                "id": site_id,
                "name": display_name,
                "display_order": i,
                "data": data,
            })
        else:
            print(f"    No data for {sid}")
        time.sleep(0.6)  # FRED rate limit ~120 req/min

    result = {
        "metadata": {
            "title": "Job Openings and Labor Turnover (JOLTS)",
            "source": "BLS JOLTS (via FRED, release 192)",
            "unit": "Thousands of persons / Rate (%)",
            "frequency": "monthly",
            "last_updated": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        },
        "series": series_list,
    }
    write_json(result, "jolts/jolts.json")
    print(f"  {len(series_list)} series written")


if __name__ == "__main__":
    run()
