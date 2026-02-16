"""
Fetch Census Bureau Construction Spending (VIP) data.
"""

import os
import sys
import time
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(__file__))
from utils import load_api_keys, write_json, retry_request

CENSUS_BASE = "https://api.census.gov/data/timeseries/eits/vip"


def fetch_year(api_key, year):
    params = {
        "get": "cell_value,data_type_code,time_slot_id,category_code,seasonally_adj",
        "time": str(year),
        "for": "us:*",
        "key": api_key
    }
    resp = retry_request(CENSUS_BASE, params=params)
    data = resp.json()
    if not data or len(data) < 2:
        return []
    return data


def run():
    print("Fetching Construction Spending data from Census Bureau...")
    keys = load_api_keys()
    api_key = keys["census"]

    all_rows = []
    headers = None

    for year in range(2015, 2027):
        print(f"  Fetching {year}...")
        try:
            data = fetch_year(api_key, year)
            if data and len(data) >= 2:
                if headers is None:
                    headers = data[0]
                all_rows.extend(data[1:])
                print(f"    {len(data) - 1} rows")
            else:
                print(f"    No data")
        except Exception as e:
            print(f"    Error: {e}")
        time.sleep(0.5)

    if not all_rows or not headers:
        print("  No data fetched")
        return

    print(f"  Total rows: {len(all_rows)}")
    col_idx = {h: i for i, h in enumerate(headers)}

    series_map = {}
    for row in all_rows:
        sa = row[col_idx.get("seasonally_adj", -1)] if "seasonally_adj" in col_idx else ""
        if sa != "yes":
            continue

        cat = row[col_idx.get("category_code", -1)]
        dtype = row[col_idx.get("data_type_code", -1)]
        time_str = row[col_idx.get("time", -1)]
        value_str = row[col_idx.get("cell_value", -1)]

        if dtype and dtype.startswith("E_"):
            continue

        series_key = f"{cat}_{dtype}"

        date_str = None
        if time_str and "-" in str(time_str) and len(str(time_str)) <= 7:
            date_str = str(time_str) + "-01"

        if date_str is None:
            continue

        try:
            value = float(str(value_str).replace(",", "").strip()) if value_str else None
        except (ValueError, TypeError):
            value = None

        if series_key not in series_map:
            series_map[series_key] = {"name": f"{cat} - {dtype}", "data": []}
        series_map[series_key]["data"].append({"date": date_str, "value": value})

    series_list = []
    for i, (key, info) in enumerate(sorted(series_map.items())):
        info["data"].sort(key=lambda d: d["date"])
        if len(info["data"]) < 2:
            continue
        series_list.append({
            "id": key, "name": info["name"],
            "display_order": i, "data": info["data"]
        })

    result = {
        "metadata": {
            "title": "Construction Spending",
            "source": "Census Bureau Value of Construction Put in Place (VIP)",
            "unit": "Millions of dollars",
            "frequency": "monthly",
            "last_updated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        },
        "series": series_list
    }

    write_json(result, "construction/construction.json")
    print(f"  {len(series_list)} series written")


if __name__ == "__main__":
    run()
