"""
Fetch BEA NIPA data for all 10 NIPA tables.

Uses the BEA API to fetch National Income and Product Accounts data.
Each table produces one JSON file.
"""

import os
import sys
import time
from datetime import datetime

sys.path.insert(0, os.path.dirname(__file__))
from utils import load_api_keys, write_json, retry_request

BEA_URL = "https://apps.bea.gov/api/data/"

NIPA_TABLES = [
    {
        "key": "1bu",
        "dataset": "NIUnderlyingDetail",
        "table": "U001B",
        "frequency": "M",
        "title": "Manufacturing and trade inventories",
        "unit": "Millions of dollars"
    },
    {
        "key": "2_4_4u",
        "dataset": "NIUnderlyingDetail",
        "table": "U20404",
        "frequency": "M",
        "title": "PCE price indexes (deflator)",
        "unit": "Index"
    },
    {
        "key": "2_4_5u",
        "dataset": "NIUnderlyingDetail",
        "table": "U20405",
        "frequency": "M",
        "title": "Personal consumption expenditures (nominal)",
        "unit": "Millions of dollars"
    },
    {
        "key": "2_4_6u",
        "dataset": "NIUnderlyingDetail",
        "table": "U20406",
        "frequency": "M",
        "title": "Personal consumption expenditures (real)",
        "unit": "Millions of chained dollars"
    },
    {
        "key": "2bu",
        "dataset": "NIUnderlyingDetail",
        "table": "U002BU",
        "frequency": "M",
        "title": "Manufacturing and trade sales",
        "unit": "Millions of dollars"
    },
    {
        "key": "3bu",
        "dataset": "NIUnderlyingDetail",
        "table": "U003BU",
        "frequency": "M",
        "title": "Manufacturing and trade inventory-sales ratio",
        "unit": "Ratio"
    },
    {
        "key": "4_2_5b",
        "dataset": "NIPA",
        "table": "T40205B",
        "frequency": "Q",
        "title": "Exports and imports of goods by type (nominal)",
        "unit": "Millions of dollars"
    },
    {
        "key": "4_2_6b",
        "dataset": "NIPA",
        "table": "T40206B",
        "frequency": "Q",
        "title": "Exports and imports of goods by type (real)",
        "unit": "Millions of chained dollars"
    },
    {
        "key": "5_5_5u",
        "dataset": "NIUnderlyingDetail",
        "table": "U50505",
        "frequency": "Q",
        "title": "Private fixed investment in equipment",
        "unit": "Millions of dollars"
    },
    {
        "key": "5_7_5bu1",
        "dataset": "NIUnderlyingDetail",
        "table": "U50705BU1",
        "frequency": "Q",
        "title": "Change in private inventories",
        "unit": "Millions of dollars"
    },
]


def fetch_table(api_key, table_config):
    """Fetch a single BEA table and return standardized JSON."""
    params = {
        "UserID": api_key,
        "method": "GetData",
        "DataSetName": table_config["dataset"],
        "TableName": table_config["table"],
        "Frequency": table_config["frequency"],
        "Year": "ALL",
        "ResultFormat": "JSON"
    }

    print(f"  Fetching {table_config['key']} ({table_config['table']})...")
    resp = retry_request(BEA_URL, params=params)
    data = resp.json()

    # Navigate to the results
    results = data.get("BEAAPI", {}).get("Results", {})

    # Handle error responses
    if "Error" in results:
        error = results["Error"]
        if isinstance(error, list):
            error = error[0]
        print(f"    BEA API error: {error.get('APIErrorDescription', error)}")
        return None

    raw_data = results.get("Data", [])
    if not raw_data:
        print(f"    No data returned for {table_config['key']}")
        return None

    print(f"    Got {len(raw_data)} data points")

    # Group by line/series
    series_map = {}
    for row in raw_data:
        line_num = row.get("LineNumber", "")
        line_desc = row.get("LineDescription", "").strip()
        time_period = row.get("TimePeriod", "")
        value_str = row.get("DataValue", "")

        # Build series key
        series_key = f"{line_num}_{line_desc}"

        # Parse date
        if table_config["frequency"] == "M":
            # BEA monthly: "2024M01"
            date_str = None
            if "M" in time_period:
                parts = time_period.split("M")
                if len(parts) == 2:
                    try:
                        date_str = f"{int(parts[0])}-{int(parts[1]):02d}-01"
                    except ValueError:
                        pass
        else:
            # BEA quarterly: "2024Q1"
            date_str = None
            if "Q" in time_period:
                parts = time_period.split("Q")
                if len(parts) == 2:
                    try:
                        month = (int(parts[1]) - 1) * 3 + 1
                        date_str = f"{int(parts[0])}-{month:02d}-01"
                    except ValueError:
                        pass

        if date_str is None:
            continue

        # Parse value
        value_str = value_str.replace(",", "").strip()
        try:
            value = float(value_str)
        except (ValueError, TypeError):
            value = None

        if series_key not in series_map:
            series_map[series_key] = {
                "line_num": line_num,
                "name": line_desc,
                "data": []
            }
        series_map[series_key]["data"].append({"date": date_str, "value": value})

    # Build output
    series_list = []
    for i, (key, info) in enumerate(sorted(series_map.items(), key=lambda x: int(x[1]["line_num"]) if x[1]["line_num"].isdigit() else 9999)):
        info["data"].sort(key=lambda d: d["date"])
        if len(info["data"]) < 2:
            continue
        series_list.append({
            "id": f"{table_config['table']}_{info['line_num']}",
            "name": info["name"],
            "display_order": i,
            "data": info["data"]
        })

    freq_str = "monthly" if table_config["frequency"] == "M" else "quarterly"

    return {
        "metadata": {
            "title": table_config["title"],
            "source": f"BEA {table_config['dataset']} Table {table_config['table']}",
            "unit": table_config["unit"],
            "frequency": freq_str,
            "last_updated": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
        },
        "series": series_list
    }


def run():
    print("Fetching NIPA data from BEA API...")
    keys = load_api_keys()
    api_key = keys["bea"]

    for table_config in NIPA_TABLES:
        result = fetch_table(api_key, table_config)
        if result and result["series"]:
            write_json(result, f"nipa/{table_config['key']}.json")
            print(f"    {len(result['series'])} series written")
        else:
            print(f"    Skipped {table_config['key']} (no data)")
        time.sleep(8)  # BEA rate limit: 100 req/min, but large responses need spacing


if __name__ == "__main__":
    run()
