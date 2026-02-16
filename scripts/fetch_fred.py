"""
Fetch Federal Reserve Industrial Production data via FRED API.
"""

import os
import sys
import time
from datetime import datetime

sys.path.insert(0, os.path.dirname(__file__))
from utils import load_api_keys, write_json, retry_request

FRED_URL = "https://api.stlouisfed.org/fred/series/observations"

# Industrial Production series and their descriptions
IP_SERIES = [
    ("INDPRO", "Industrial Production: Total Index"),
    ("IPMAN", "Industrial Production: Manufacturing (SIC)"),
    ("IPMANSICS", "Industrial Production: Manufacturing (SIC)"),
    ("IPMINE", "Industrial Production: Mining"),
    ("IPUTIL", "Industrial Production: Electric and Gas Utilities"),
    ("IPB50001N", "Industrial Production: Total Index (not seasonally adjusted)"),
    ("IPB50001SQ", "Industrial Production: Total Index"),
    ("IPDMAN", "Industrial Production: Durable Manufacturing"),
    ("IPNMAN", "Industrial Production: Nondurable Manufacturing"),
    ("IPBUSEQ", "Industrial Production: Business Equipment"),
    ("IPCONGD", "Industrial Production: Consumer Goods"),
    ("IPDCONGD", "Industrial Production: Durable Consumer Goods"),
    ("IPNCONGD", "Industrial Production: Nondurable Consumer Goods"),
    ("IPMAT", "Industrial Production: Materials"),
    ("IPB51110SQ", "Industrial Production: Manufacturing - Durable Goods"),
    ("IPB51210SQ", "Industrial Production: Manufacturing - Nondurable Goods"),
    ("IPG211111CS", "Industrial Production: Oil and Gas Extraction"),
    ("IPG2111A0CS", "Industrial Production: Oil Extraction"),
    ("IPG2111A1CS", "Industrial Production: Natural Gas Extraction"),
    ("IPG212CS", "Industrial Production: Mining (except oil and gas)"),
    ("IPG213111CS", "Industrial Production: Drilling Oil and Gas Wells"),
    ("IPG2211A2CS", "Industrial Production: Electric Power Generation"),
    ("IPG2211A3CS", "Industrial Production: Natural Gas Distribution"),
    ("IPG321CS", "Industrial Production: Wood Product"),
    ("IPG327CS", "Industrial Production: Nonmetallic Mineral Product"),
    ("IPG331CS", "Industrial Production: Primary Metal"),
    ("IPG332CS", "Industrial Production: Fabricated Metal Product"),
    ("IPG333CS", "Industrial Production: Machinery"),
    ("IPG334CS", "Industrial Production: Computer and Electronic Product"),
    ("IPG335CS", "Industrial Production: Electrical Equipment and Appliance"),
    ("IPG3361T3CS", "Industrial Production: Motor Vehicles and Parts"),
    ("IPG337CS", "Industrial Production: Furniture and Related Product"),
    ("IPG339CS", "Industrial Production: Miscellaneous Manufacturing"),
    ("IPG311A2CS", "Industrial Production: Food, Beverage, and Tobacco"),
    ("IPG313A4CS", "Industrial Production: Textile and Product Mills"),
    ("IPG315A6CS", "Industrial Production: Apparel and Leather Goods"),
    ("IPG322CS", "Industrial Production: Paper"),
    ("IPG323CS", "Industrial Production: Printing and Support"),
    ("IPG324CS", "Industrial Production: Petroleum and Coal Products"),
    ("IPG325CS", "Industrial Production: Chemical"),
    ("IPG326CS", "Industrial Production: Plastics and Rubber Products"),
]


def fetch_fred_series(api_key, series_id, name):
    """Fetch a single FRED series."""
    params = {
        "series_id": series_id,
        "api_key": api_key,
        "file_type": "json",
        "observation_start": "2000-01-01"
    }

    resp = retry_request(FRED_URL, params=params)
    data = resp.json()
    observations = data.get("observations", [])

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
    print("Fetching Industrial Production data from FRED...")
    keys = load_api_keys()
    api_key = keys["fred"]

    series_list = []
    for i, (series_id, name) in enumerate(IP_SERIES):
        print(f"  Fetching {series_id}...")
        try:
            data = fetch_fred_series(api_key, series_id, name)
        except Exception as e:
            print(f"    Skipping {series_id}: {e}")
            continue
        if data and len(data) >= 2:
            series_list.append({
                "id": series_id,
                "name": name,
                "display_order": i,
                "data": data
            })
            print(f"    {len(data)} observations")
        else:
            print(f"    No data for {series_id}")
        time.sleep(0.5)

    result = {
        "metadata": {
            "title": "Industrial Production",
            "source": "Federal Reserve (FRED)",
            "unit": "Index 2017=100",
            "frequency": "monthly",
            "last_updated": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
        },
        "series": series_list
    }

    write_json(result, "industrial_production/industrial_production.json")
    print(f"  {len(series_list)} series written")


if __name__ == "__main__":
    run()
