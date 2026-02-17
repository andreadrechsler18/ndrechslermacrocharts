"""
Post-processing: generates all derived JSON files from the raw fetched data.

1. QSS: Apply NAICS labels and filter to QREV (quarterly revenue) only
2. Wholesale: Split into sales, inventory, and ratio files
3. CES PBS: Filter employees to Professional & Business Services subset
4. Analysis: Extract AI-exposed employment series for the analysis page
"""

import os
import sys
import json
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(__file__))
from utils import JSON_DIR, CONFIG_DIR

# Import QSS label mappings from fix_qss_labels
from fix_qss_labels_data import QSS_CATEGORIES, QSS_DTYPES


def load_json(subpath):
    path = os.path.join(JSON_DIR, subpath)
    if not os.path.exists(path):
        print(f"  WARNING: {subpath} not found, skipping")
        return None
    with open(path) as f:
        return json.load(f)


def save_json(data, subpath):
    path = os.path.join(JSON_DIR, subpath)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w') as f:
        json.dump(data, f, separators=(',', ':'))
    size_kb = os.path.getsize(path) / 1024
    print(f"  Wrote {subpath} ({size_kb:.0f} KB)")


def process_qss():
    """Apply NAICS labels to QSS and filter to QREV only."""
    print("Processing QSS labels and filtering to QREV...")
    data = load_json("qss/qss.json")
    if not data:
        return

    filtered = []
    for s in data["series"]:
        parts = s["id"].rsplit("_", 1)
        if len(parts) != 2:
            continue
        cat, dtype = parts

        # Keep only QREV (quarterly revenue)
        if dtype != "QREV":
            continue

        cat_name = QSS_CATEGORIES.get(cat, cat)
        s["name"] = cat_name
        s["display_order"] = len(filtered)
        filtered.append(s)

    data["series"] = filtered
    save_json(data, "qss/qss.json")
    print(f"  {len(filtered)} QREV series")


def process_wholesale():
    """Split wholesale.json into sales, inventory, and ratio files."""
    print("Splitting wholesale data into sales/inventory/ratio...")
    data = load_json("wholesale/wholesale.json")
    if not data:
        return

    sales, inventory, ratio = [], [], []

    for s in data["series"]:
        sid = s["id"]
        parts = sid.rsplit("_", 1)
        if len(parts) != 2:
            continue
        cat, dtype = parts

        if dtype == "SM":
            sales.append(s)
        elif dtype in ("EI", "IM"):
            inventory.append(s)
        elif dtype in ("SI", "IR"):
            ratio.append(s)

    def make_output(series_list, title, unit):
        for i, s in enumerate(series_list):
            s["display_order"] = i
        return {
            "metadata": {
                **data["metadata"],
                "title": title,
                "unit": unit,
            },
            "series": series_list
        }

    if sales:
        save_json(make_output(sales, "Wholesale Trade - Sales",
                              "Millions of dollars"), "wholesale/wholesale_sales.json")
    if inventory:
        save_json(make_output(inventory, "Wholesale Trade - Inventories",
                              "Millions of dollars"), "wholesale/wholesale_inventory.json")
    if ratio:
        save_json(make_output(ratio, "Wholesale Trade - Inventory/Sales Ratio",
                              "Ratio"), "wholesale/wholesale_ratio.json")


def process_ces_pbs():
    """Filter CES employees to PBS (CES60*) subset."""
    print("Filtering CES employees to PBS subset...")
    data = load_json("ces/employees.json")
    if not data:
        return

    pbs = [s for s in data["series"] if s["id"].startswith("CES60")]
    for i, s in enumerate(pbs):
        s["display_order"] = i

    result = {
        "metadata": {
            **data["metadata"],
            "title": "Professional and Business Services - Employees",
            "last_updated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        },
        "series": pbs
    }

    save_json(result, "ces/employees_pbs.json")
    print(f"  {len(pbs)} PBS series")


def process_analysis():
    """Extract key AI-exposed series for the analysis page."""
    print("Generating AI impact analysis JSON...")
    data = load_json("ces/employees.json")
    if not data:
        return

    target_ids = [
        'CES0000000001',   # Total nonfarm
        'CES6000000001',   # Professional and business services
        'CES6054000001',   # Professional, scientific, and technical services
        'CES6054150001',   # Computer systems design and related services
        'CES6054151101',   # Custom computer programming services
        'CES6054151201',   # Computer systems design services
        'CES6054110001',   # Legal services
        'CES6054120001',   # Accounting, tax prep, bookkeeping, payroll
        'CES6054160001',   # Management, scientific, and technical consulting
        'CES6054161001',   # Management consulting services
        'CES6054130001',   # Architectural, engineering, and related services
        'CES6054170001',   # Scientific research and development services
        'CES5051320001',   # Software publishers
        'CES6054140001',   # Specialized design services
        'CES6054180001',   # Advertising, public relations, and related services
        'CES5000000001',   # Information sector total
    ]

    lookup = {s['id']: s for s in data['series']}
    analysis = []
    for i, sid in enumerate(target_ids):
        if sid in lookup:
            s = lookup[sid]
            analysis.append({
                'id': s['id'],
                'name': s['name'],
                'display_order': i,
                'data': s['data']
            })

    result = {
        "metadata": {
            "title": "AI Impact on Professional Services Employment",
            "source": "Bureau of Labor Statistics, Current Employment Statistics",
            "unit": "Thousands",
            "frequency": "monthly"
        },
        "series": analysis
    }

    save_json(result, "analysis/ai_employment.json")
    print(f"  {len(analysis)} series")


def copy_calendar():
    """Copy release calendar to data/json so the website can access it."""
    print("Copying release calendar to data/json...")
    src = os.path.join(CONFIG_DIR, 'release_calendar.json')
    if not os.path.exists(src):
        print("  WARNING: release_calendar.json not found, skipping")
        return
    dst_dir = os.path.join(JSON_DIR, 'calendar')
    os.makedirs(dst_dir, exist_ok=True)
    dst = os.path.join(dst_dir, 'release_calendar.json')
    import shutil
    shutil.copy2(src, dst)
    size_kb = os.path.getsize(dst) / 1024
    print(f"  Wrote calendar/release_calendar.json ({size_kb:.0f} KB)")


def run():
    print("=" * 40)
    print("Post-processing derived data...")
    print("=" * 40)
    process_qss()
    process_wholesale()
    process_ces_pbs()
    process_analysis()
    copy_calendar()
    print("Post-processing complete.")


if __name__ == "__main__":
    run()
