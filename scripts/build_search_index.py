"""Build search index from all data files + NAICS mapping configs."""

import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(__file__))
from utils import JSON_DIR, CONFIG_DIR

# Standard NAICS sector names (2-digit)
NAICS_SECTORS = {
    "11": "Agriculture, Forestry, Fishing and Hunting",
    "21": "Mining, Quarrying, and Oil and Gas Extraction",
    "22": "Utilities",
    "23": "Construction",
    "31": "Manufacturing",
    "32": "Manufacturing",
    "33": "Manufacturing",
    "42": "Wholesale Trade",
    "44": "Retail Trade",
    "45": "Retail Trade",
    "48": "Transportation and Warehousing",
    "49": "Transportation and Warehousing",
    "51": "Information",
    "52": "Finance and Insurance",
    "53": "Real Estate and Rental and Leasing",
    "54": "Professional, Scientific, and Technical Services",
    "55": "Management of Companies and Enterprises",
    "56": "Administrative and Support and Waste Management",
    "61": "Educational Services",
    "62": "Health Care and Social Assistance",
    "71": "Arts, Entertainment, and Recreation",
    "72": "Accommodation and Food Services",
    "81": "Other Services (except Public Administration)",
    "92": "Public Administration",
}

# Data file -> list of pages that show this data
DATA_FILE_PAGES = {
    "ces/employees.json": [
        {"page": "ces/employees_yoy.html", "pageLabel": "Employees YoY",
         "section": "CES", "sectionLabel": "Current Employment Statistics"},
        {"page": "ces/employees_long.html", "pageLabel": "Employees (Long)",
         "section": "CES", "sectionLabel": "Current Employment Statistics"},
    ],
    "ces/employees_pbs.json": [
        {"page": "ces/employees_pbs.html", "pageLabel": "Prof. & Business Services",
         "section": "CES", "sectionLabel": "Current Employment Statistics"},
    ],
    "ces/payrolls.json": [
        {"page": "ces/payrolls.html", "pageLabel": "Aggregate Payrolls",
         "section": "CES", "sectionLabel": "Current Employment Statistics"},
    ],
    "m3/m3.json": [
        {"page": "m3/index.html", "pageLabel": "M3 Survey",
         "section": "M3", "sectionLabel": "M3 - Shipments, Inventories & Orders"},
    ],
    "qss/qss.json": [
        {"page": "qss/index.html", "pageLabel": "Quarterly Services Survey",
         "section": "QSS", "sectionLabel": "Quarterly Services Survey"},
    ],
    "wholesale/wholesale_sales.json": [
        {"page": "wholesale/sales.html", "pageLabel": "Wholesale Sales",
         "section": "Wholesale", "sectionLabel": "Monthly Wholesale Trade"},
    ],
    "wholesale/wholesale_inventory.json": [
        {"page": "wholesale/inventory.html", "pageLabel": "Wholesale Inventories",
         "section": "Wholesale", "sectionLabel": "Monthly Wholesale Trade"},
    ],
    "wholesale/wholesale_ratio.json": [
        {"page": "wholesale/ratio.html", "pageLabel": "Wholesale I/S Ratio",
         "section": "Wholesale", "sectionLabel": "Monthly Wholesale Trade"},
    ],
    "construction/construction.json": [
        {"page": "construction/index.html", "pageLabel": "Construction Spending",
         "section": "Construction", "sectionLabel": "Construction Spending"},
    ],
    "industrial_production/industrial_production.json": [
        {"page": "industrial_production/index.html", "pageLabel": "Industrial Production",
         "section": "IP", "sectionLabel": "Industrial Production"},
    ],
    "unemployment/unemployment.json": [
        {"page": "unemployment/index.html", "pageLabel": "Unemployment by Industry",
         "section": "Unemployment", "sectionLabel": "Unemployment by Industry"},
    ],
    # NIPA tables
    "nipa/1bu.json": [
        {"page": "nipa/1bu.html", "pageLabel": "1BU - Mfg & Trade Inventories",
         "section": "NIPA", "sectionLabel": "NIPA Data"},
    ],
    "nipa/2bu.json": [
        {"page": "nipa/2bu.html", "pageLabel": "2BU - Mfg & Trade Sales",
         "section": "NIPA", "sectionLabel": "NIPA Data"},
    ],
    "nipa/2_4_4u.json": [
        {"page": "nipa/2_4_4u.html", "pageLabel": "2.4.4U - PCE Deflator",
         "section": "NIPA", "sectionLabel": "NIPA Data"},
    ],
    "nipa/2_4_5u.json": [
        {"page": "nipa/2_4_5u.html", "pageLabel": "2.4.5U - Nominal Spending",
         "section": "NIPA", "sectionLabel": "NIPA Data"},
    ],
    "nipa/2_4_6u.json": [
        {"page": "nipa/2_4_6u.html", "pageLabel": "2.4.6U - Real Spending",
         "section": "NIPA", "sectionLabel": "NIPA Data"},
    ],
    "nipa/3bu.json": [
        {"page": "nipa/3bu.html", "pageLabel": "3BU - Inventory-Sales Ratio",
         "section": "NIPA", "sectionLabel": "NIPA Data"},
    ],
    "nipa/3_3.json": [
        {"page": "nipa/3_3.html", "pageLabel": "3.3 - State & Local Govt",
         "section": "NIPA", "sectionLabel": "NIPA Data"},
    ],
    "nipa/4_2_5b.json": [
        {"page": "nipa/4_2_5b.html", "pageLabel": "4.2.5B - Net Exports",
         "section": "NIPA", "sectionLabel": "NIPA Data"},
    ],
    "nipa/4_2_6b.json": [
        {"page": "nipa/4_2_6b.html", "pageLabel": "4.2.6B - Real Imports",
         "section": "NIPA", "sectionLabel": "NIPA Data"},
    ],
    "nipa/5_3_5.json": [
        {"page": "nipa/5_3_5.html", "pageLabel": "5.3.5 - Nonresidential Investment",
         "section": "NIPA", "sectionLabel": "NIPA Data"},
    ],
    "nipa/5_5_5u.json": [
        {"page": "nipa/5_5_5u.html", "pageLabel": "5.5.5U - Equipment Spending",
         "section": "NIPA", "sectionLabel": "NIPA Data"},
    ],
    "nipa/5_7_5bu1.json": [
        {"page": "nipa/5_7_5bu1.html", "pageLabel": "5.7.5BU1 - Private Inventories",
         "section": "NIPA", "sectionLabel": "NIPA Data"},
    ],
    # Fed Regional Surveys
    "fed_surveys/fed_mfg.json": [
        {"page": "fed_surveys/manufacturing.html", "pageLabel": "Manufacturing Surveys",
         "section": "FedSurveys", "sectionLabel": "Fed Regional Surveys"},
    ],
    "fed_surveys/fed_svc.json": [
        {"page": "fed_surveys/services.html", "pageLabel": "Services Surveys",
         "section": "FedSurveys", "sectionLabel": "Fed Regional Surveys"},
    ],
}

# M3 series suffixes excluded from display
M3_EXCLUDE = re.compile(r'_(MPC|IS)')


def load_json(subpath):
    path = os.path.join(JSON_DIR, subpath)
    if not os.path.exists(path):
        return None
    with open(path) as f:
        return json.load(f)


def load_config(name):
    path = os.path.join(CONFIG_DIR, name)
    if not os.path.exists(path):
        return None
    with open(path) as f:
        return json.load(f)


def resolve_naics_ces(series_id, ces_map):
    """Extract NAICS from CES series ID via mapping.
    CES IDs: 'CES' + 8-digit establishment code + 2-digit data type.
    Establishment code = chars 3..11."""
    if len(series_id) < 11:
        return None, None
    est_code = series_id[3:11]
    entry = ces_map.get(est_code)
    if not entry or entry["naics"] == "-":
        return None, None
    return entry["naics"], entry["name"]


def resolve_naics_m3(series_id, m3_map):
    """Extract NAICS from M3 series ID via mapping.
    M3 IDs: 'CODE_METRIC' e.g. '11A_VS'."""
    parts = series_id.split("_", 1)
    if not parts:
        return None, None
    code = parts[0]
    entry = m3_map.get(code)
    if not entry:
        return None, None
    naics = entry["naics"]
    # Skip composites and "(other)" annotations for NAICS matching
    if naics in ("composite", "-") or "(" in naics or "-" in naics:
        return None, entry["name"]
    # May be comma-separated; use the first code for prefix matching
    first_naics = naics.split(",")[0]
    return first_naics, entry["name"]


def resolve_naics_wholesale(series_id):
    """Extract NAICS from wholesale series ID.
    Wholesale IDs: 'NAICS_METRIC' e.g. '4231_SM'."""
    parts = series_id.split("_", 1)
    if not parts:
        return None
    code = parts[0]
    if code.isdigit():
        return code
    return None


def resolve_naics_qss(series_id):
    """Extract NAICS from QSS series ID.
    QSS IDs: 'CATCODE_QREV' e.g. '2211T_QREV'. Strip trailing letters."""
    parts = series_id.split("_", 1)
    if not parts:
        return None
    cat = parts[0]
    # Strip trailing letters: '2211T' -> '2211', '4849YT' -> '4849'
    naics = re.sub(r'[A-Za-z]+$', '', cat)
    if naics and naics != "000000":
        return naics
    return None


def build_naics_names(all_entries):
    """Build NAICS code -> name lookup from all indexed entries + sector names."""
    names = dict(NAICS_SECTORS)
    for entry in all_entries:
        naics = entry.get("naics")
        naics_name = entry.get("naicsName")
        if naics and naics_name and naics not in names:
            names[naics] = naics_name
    return names


def run():
    print("Building search index...")

    ces_map = load_config("ces_naics_map.json") or {}
    m3_map = load_config("m3_naics_map.json") or {}

    entries = []
    stats = {"files": 0, "series": 0, "naics_mapped": 0}

    for data_file, pages in DATA_FILE_PAGES.items():
        data = load_json(data_file)
        if not data:
            print(f"  WARNING: {data_file} not found, skipping")
            continue

        stats["files"] += 1
        section = pages[0]["section"]

        for series in data.get("series", []):
            sid = series["id"]
            name = series.get("name", sid)

            # Skip M3 excluded patterns
            if section == "M3" and M3_EXCLUDE.search(sid):
                continue

            # Resolve NAICS
            naics = None
            naics_name = None

            if section == "CES":
                naics, naics_name = resolve_naics_ces(sid, ces_map)
            elif section == "M3":
                naics, naics_name = resolve_naics_m3(sid, m3_map)
            elif section == "Wholesale":
                naics = resolve_naics_wholesale(sid)
            elif section == "QSS":
                naics = resolve_naics_qss(sid)

            # Use series name as naicsName fallback
            if not naics_name:
                naics_name = name

            # Look up sector name if we have a NAICS code but no specific name
            if naics and naics_name == name:
                sector = naics[:2]
                if sector in NAICS_SECTORS:
                    naics_name = NAICS_SECTORS[sector]

            if naics:
                stats["naics_mapped"] += 1

            # Create one entry per page
            for page_info in pages:
                entry = {
                    "id": sid,
                    "name": name,
                    "section": page_info["section"],
                    "sectionLabel": page_info["sectionLabel"],
                    "page": page_info["page"],
                    "pageLabel": page_info["pageLabel"],
                    "dataFile": data_file,
                }
                if naics:
                    entry["naics"] = naics
                    entry["naicsName"] = naics_name
                entries.append(entry)

            stats["series"] += 1

    # Build NAICS names lookup
    naics_names = build_naics_names(entries)

    # Write outputs
    out_dir = os.path.join(JSON_DIR, "search")
    os.makedirs(out_dir, exist_ok=True)

    index_path = os.path.join(out_dir, "search_index.json")
    with open(index_path, "w") as f:
        json.dump(entries, f, separators=(",", ":"))
    index_kb = os.path.getsize(index_path) / 1024

    names_path = os.path.join(out_dir, "naics_names.json")
    with open(names_path, "w") as f:
        json.dump(naics_names, f, indent=2)
    names_kb = os.path.getsize(names_path) / 1024

    print(f"  Files processed: {stats['files']}")
    print(f"  Unique series: {stats['series']}")
    print(f"  NAICS-mapped: {stats['naics_mapped']}")
    print(f"  Index entries: {len(entries)} (across all pages)")
    print(f"  search_index.json: {index_kb:.0f} KB")
    print(f"  naics_names.json: {names_kb:.0f} KB")
    print(f"  NAICS codes in lookup: {len(naics_names)}")


if __name__ == "__main__":
    run()
