"""
Fetch Census QSS advance-release data (NSA) from the API.

Background: the Census QSS publishes an "Advance Report" ~3 weeks before
the full release. On Advance-release day, only Not-Seasonally-Adjusted
estimates are available for industry categories (Table A1 in the XLSX /
seasonally_adj='no' in the API). The Seasonally Adjusted series (Table A3,
the one our regular fetch_qss pipeline uses) is published only for the
"Selected Services Total" row until the Full Report ~3 weeks later.

This fetcher pulls those NSA values for the latest available quarter and
writes them to qss/qss_advance.json. post_process.process_qss then merges
any quarter newer than what SA already has into qss.json / qss_health.json,
tagging those points with is_advance=true so the UI can mark them.

Output: data/json/qss/qss_advance.json
"""

import os
import sys
import time
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(__file__))
from utils import load_api_keys, retry_request, JSON_DIR, write_json

CENSUS_BASE = "https://api.census.gov/data/timeseries/eits/qss"


def _parse_time(t):
    """Convert '2026-Q3' → '2026-07-01'."""
    if not t or "Q" not in str(t):
        return None
    y, q = str(t).split("-Q") if "-Q" in str(t) else str(t).split("Q")
    try:
        month = (int(q) - 1) * 3 + 1
        return f"{int(y)}-{month:02d}-01"
    except ValueError:
        return None


def fetch_qss_advance():
    print("Fetching QSS Advance (NSA) from Census API...")
    api_key = load_api_keys()["census"]

    # Fetch the current and prior year so we can also refresh the handful
    # of revised-quarter NSA values the advance report publishes.
    current_year = datetime.now(timezone.utc).year
    all_rows = []
    headers = None
    for year in [current_year, current_year - 1]:
        params = {
            "get": "cell_value,data_type_code,time_slot_id,category_code,seasonally_adj",
            "time": str(year),
            "for": "us:*",
            "key": api_key,
        }
        try:
            resp = retry_request(CENSUS_BASE, params=params)
            data = resp.json()
        except Exception as e:
            print(f"  {year}: ERROR {e}")
            continue
        if not data or len(data) < 2:
            print(f"  {year}: no data")
            continue
        if headers is None:
            headers = data[0]
        all_rows.extend(data[1:])
        print(f"  {year}: {len(data) - 1} rows")
        time.sleep(0.4)

    if not headers or not all_rows:
        print("  No data fetched")
        return

    ci = {h: i for i, h in enumerate(headers)}

    # Build NSA QREV series by category
    series_map = {}
    for row in all_rows:
        sa = row[ci.get("seasonally_adj", -1)]
        if sa != "no":
            continue
        dtype = row[ci.get("data_type_code", -1)]
        if dtype != "QREV":
            # Advance release: we only care about revenue right now.
            # QEXP (expenses) are not in the advance report.
            continue
        cat = row[ci.get("category_code", -1)]
        date_str = _parse_time(row[ci.get("time", -1)])
        if not date_str:
            continue
        try:
            value = float(str(row[ci.get("cell_value", -1)]).replace(",", "").strip())
        except (ValueError, TypeError, AttributeError):
            continue
        sid = f"{cat}_QREV"
        series_map.setdefault(sid, {"id": sid, "category_code": cat, "data": []})
        series_map[sid]["data"].append({"date": date_str, "value": value})

    # Sort each series by date
    series_list = []
    latest_quarter = None
    for sid in sorted(series_map):
        s = series_map[sid]
        s["data"].sort(key=lambda p: p["date"])
        if not s["data"]:
            continue
        last = s["data"][-1]["date"]
        if latest_quarter is None or last > latest_quarter:
            latest_quarter = last
        series_list.append(s)

    print(f"  Built {len(series_list)} NSA QREV series; latest quarter = {latest_quarter}")

    out = {
        "metadata": {
            "title": "QSS Advance Report (Not Seasonally Adjusted)",
            "source": "Census Bureau QSS API (seasonally_adj=no)",
            "unit": "Millions of dollars",
            "frequency": "quarterly",
            "latest_quarter": latest_quarter,
            "note": "NSA values from the Advance Report API path. The Full Report ~3 weeks later supersedes these with SA values.",
            "last_updated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        },
        "series": series_list,
    }
    write_json(out, "qss/qss_advance.json")
    print(f"  Wrote qss/qss_advance.json")


if __name__ == "__main__":
    fetch_qss_advance()
