"""
Fetch Census Bureau M3 (Manufacturers' Shipments, Inventories, and Orders) data.

Uses the Census EITS API.
"""

import os
import sys
import time
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(__file__))
from utils import load_api_keys, write_json, retry_request

CENSUS_BASE = "https://api.census.gov/data/timeseries/eits/m3"

DATA_TYPE_NAMES = {
    "SM": "Shipments",
    "NI": "New Orders",
    "NO": "New Orders",
    "UI": "Unfilled Orders",
    "UO": "Unfilled Orders",
    "TI": "Total Inventories",
    "MI": "Materials Inventories",
    "WI": "Work-in-Process Inventories",
    "FI": "Finished Goods Inventories",
    "VS": "Value of Shipments",
    "IS": "Inventory/Shipments Ratio",
    "NS": "New Orders/Shipments Ratio",
    "MPCNO": "Monthly % Change New Orders",
    "MPCVS": "Monthly % Change Value of Shipments",
    "MPCTI": "Monthly % Change Total Inventories",
    "MPCFI": "Monthly % Change Finished Goods Inventories",
    "MPCMI": "Monthly % Change Materials Inventories",
    "MPCWI": "Monthly % Change Work-in-Process Inventories",
    "MPCUO": "Monthly % Change Unfilled Orders",
    "US": "Value of Shipments",
}

# Mapping of Census M3 category codes to readable industry names
# Sources: Census M3 Full Report tables, Advance Durable Goods report
CATEGORY_NAMES = {
    # Aggregate totals
    "MTM": "All Manufacturing",
    "MDM": "Durable Goods",
    "MNM": "Nondurable Goods",
    "MXT": "Manufacturing excl. Transportation",
    "MXD": "Manufacturing excl. Defense",
    "MTU": "Manufacturing with Unfilled Orders",
    "DXT": "Durable Goods excl. Transportation",
    "DXD": "Durable Goods excl. Defense",
    # Capital goods aggregates
    "TCG": "Capital Goods",
    "NDE": "Nondefense Capital Goods",
    "NXA": "Nondefense Capital Goods excl. Aircraft",
    "DEF": "Defense Capital Goods",
    "NAP": "Nondefense Aircraft and Parts",
    "DAP": "Defense Aircraft and Parts",
    # Consumer goods aggregates
    "CDG": "Consumer Durable Goods",
    "CNG": "Consumer Nondurable Goods",
    "COG": "Consumer Goods",
    # Other aggregates
    "ITI": "Information Technology",
    "MVP": "Motor Vehicles and Parts",
    "ODG": "All Other Durable Goods",
    "CRP": "Computers and Related Products",
    "CMS": "Communications Equipment",
    "ANM": "All Manufacturing New Orders",
    "BTP": "Business-Type Products",
    "TGP": "Technology Goods Products",
    "MXD": "Manufacturing excl. Defense",
    # NAICS 321 - Wood Products
    "21S": "Wood Products",
    # NAICS 327 - Nonmetallic Mineral Products
    "27S": "Nonmetallic Mineral Products",
    # NAICS 331 - Primary Metals
    "31S": "Primary Metals",
    "31A": "Iron and Steel Mills",
    "31C": "Aluminum and Nonferrous Metals",
    # NAICS 332 - Fabricated Metal Products
    "32S": "Fabricated Metal Products",
    # NAICS 333 - Machinery
    "33S": "Machinery",
    "33A": "Farm Machinery",
    "33C": "Construction Machinery",
    "33D": "Mining, Oil, and Gas Field Machinery",
    "33E": "Industrial Machinery",
    "33G": "Photographic Equipment",
    "33H": "HVAC and Refrigeration Equipment",
    "33I": "Metalworking Machinery",
    "33M": "Turbines and Power Transmission Equipment",
    # NAICS 334 - Computer and Electronic Products
    "34S": "Computers and Electronic Products",
    "34A": "Computers",
    "34B": "Computer Storage Devices",
    "34C": "Other Peripheral Equipment",
    "34D": "Nondefense Communications Equipment",
    "34E": "Defense Communications Equipment",
    "34F": "Audio and Video Equipment",
    "34H": "Electronic Components",
    "34I": "Nondefense Search and Navigation Equipment",
    "34J": "Defense Search and Navigation Equipment",
    "34K": "Electromedical and Control Instruments",
    "34X": "Computers and Electronic Products Subtotal",
    # NAICS 335 - Electrical Equipment
    "35S": "Electrical Equipment and Components",
    "35A": "Electric Lighting Equipment",
    "35B": "Household Appliances",
    "35C": "Electrical Equipment",
    "35D": "Batteries",
    # NAICS 336 - Transportation Equipment
    "36S": "Transportation Equipment",
    "36A": "Automobiles",
    "36B": "Light Trucks and Utility Vehicles",
    "36C": "Heavy Duty Trucks",
    "36Z": "Motor Vehicle Bodies, Parts, and Trailers",
    # NAICS 337 - Furniture
    "37S": "Furniture and Related Products",
    # NAICS 339 - Miscellaneous
    "39S": "Miscellaneous Manufacturing",
    # NAICS 311 - Food
    "11S": "Food Products",
    "11A": "Grain and Oilseed Milling",
    "11B": "Dairy Products",
    "11C": "Meat, Poultry, and Seafood",
    # NAICS 312 - Beverage and Tobacco
    "12S": "Beverage and Tobacco Products",
    "12A": "Beverages",
    "12B": "Tobacco",
    # NAICS 313 - Textile Mills
    "13S": "Textile Mills",
    # NAICS 314 - Textile Products
    "14S": "Textile Products",
    # NAICS 315 - Apparel
    "15S": "Apparel",
    # NAICS 316 - Leather
    "16S": "Leather and Allied Products",
    # NAICS 322 - Paper
    "22S": "Paper Products",
    "22A": "Pulp, Paper, and Paperboard Mills",
    "22B": "Paperboard Containers",
    # NAICS 323 - Printing
    "23S": "Printing",
    # NAICS 324 - Petroleum and Coal
    "24S": "Petroleum and Coal Products",
    "24A": "Petroleum Refineries",
    # NAICS 325 - Chemicals
    "25S": "Chemical Products",
    "25A": "Pesticides, Fertilizers, and Agricultural Chemicals",
    "25B": "Pharmaceuticals and Medicines",
    "25C": "Paints, Coatings, and Adhesives",
    # NAICS 326 - Plastics and Rubber
    "26S": "Plastics and Rubber Products",
}


def fetch_year(api_key, year):
    """Fetch one year of M3 data."""
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
    print("Fetching M3 data from Census Bureau...")
    keys = load_api_keys()
    api_key = keys["census"]

    all_rows = []
    headers = None

    # Fetch year by year from 2015 to present
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

    # Group by category_code + data_type_code (SA only)
    series_map = {}
    for row in all_rows:
        sa = row[col_idx.get("seasonally_adj", -1)] if "seasonally_adj" in col_idx else ""
        if sa != "yes":
            continue

        cat = row[col_idx.get("category_code", -1)]
        dtype = row[col_idx.get("data_type_code", -1)]
        time_str = row[col_idx.get("time", -1)]
        value_str = row[col_idx.get("cell_value", -1)]

        # Skip error data types
        if dtype and dtype.startswith("E_"):
            continue

        series_key = f"{cat}_{dtype}"

        # Parse date (format: "YYYY-MM")
        date_str = None
        if time_str and "-" in time_str and len(time_str) <= 7:
            date_str = time_str + "-01"

        if date_str is None:
            continue

        try:
            value = float(str(value_str).replace(",", "").strip()) if value_str else None
        except (ValueError, TypeError):
            value = None

        if series_key not in series_map:
            dtype_name = DATA_TYPE_NAMES.get(dtype, dtype)
            display_name = CATEGORY_NAMES.get(cat, cat)
            series_map[series_key] = {
                "name": f"{display_name} - {dtype_name}",
                "data": []
            }
        series_map[series_key]["data"].append({"date": date_str, "value": value})

    # Build output
    series_list = []
    for i, (key, info) in enumerate(sorted(series_map.items())):
        info["data"].sort(key=lambda d: d["date"])
        if len(info["data"]) < 2:
            continue
        series_list.append({
            "id": key,
            "name": info["name"],
            "display_order": i,
            "data": info["data"]
        })

    result = {
        "metadata": {
            "title": "Manufacturers' Shipments, Inventories, and Orders",
            "source": "Census Bureau M3 Survey",
            "unit": "Millions of dollars",
            "frequency": "monthly",
            "last_updated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        },
        "series": series_list
    }

    write_json(result, "m3/m3.json")
    print(f"  {len(series_list)} series written")


if __name__ == "__main__":
    run()
