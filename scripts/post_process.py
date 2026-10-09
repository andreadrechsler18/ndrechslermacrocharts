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
    """Split raw QSS (from fetch_qss) into two web files:
       - qss/qss.json          revenue-only across all categories
       - qss/qss_health.json   NAICS 62 revenue + expenses + computed profit/margin
    Input is qss/qss_raw.json so this function is non-destructive and safe to
    rerun on days when fetch_qss hasn't fired (which would otherwise strip
    QEXP out of our only copy of the raw data).
    """
    print("Processing QSS labels: revenue-all + health care rev/exp/profit...")
    data = load_json("qss/qss_raw.json")
    if not data:
        # No raw fetch available (e.g. first-run or non-QSS day on CI before
        # we migrated); skip quietly rather than wrecking existing outputs.
        print("  qss/qss_raw.json not found — skipping (keeping existing outputs)")
        return

    # Index raw series by (category, dtype)
    by_cat_dt = {}
    for s in data["series"]:
        parts = s["id"].rsplit("_", 1)
        if len(parts) != 2:
            continue
        cat, dtype = parts
        by_cat_dt[(cat, dtype)] = s

    # --- Revenue-only file (unchanged behavior) ---
    rev_series = []
    for (cat, dtype), s in sorted(by_cat_dt.items()):
        if dtype != "QREV":
            continue
        rev_series.append({
            "id": s["id"],
            "name": QSS_CATEGORIES.get(cat, cat),
            "display_order": len(rev_series),
            "data": s["data"],
        })
    save_json({
        "metadata": data["metadata"],
        "series": rev_series,
    }, "qss/qss.json")
    print(f"  qss.json: {len(rev_series)} QREV series")

    # --- NAICS 62 health file with rev / exp / profit ---
    # Include categories starting with "62". Rename dtype suffixes for clarity:
    # QREV -> _REV, QEXP -> _EXP; profit is computed where both exist.
    def is_health(cat):
        return cat.startswith("62")

    def points_to_map(pts):
        return {p["date"]: p["value"] for p in pts if p.get("value") is not None}

    health_series = []
    display_order = 0

    # Sort categories once; render each category's rev, exp, profit contiguously
    all_cats = sorted({cat for (cat, _dtype) in by_cat_dt if is_health(cat)})
    for cat in all_cats:
        cat_name = QSS_CATEGORIES.get(cat, cat)
        rev = by_cat_dt.get((cat, "QREV"))
        exp = by_cat_dt.get((cat, "QEXP"))

        if rev:
            health_series.append({
                "id": f"{cat}_REV",
                "name": f"{cat_name} - Revenue",
                "display_order": display_order,
                "data": rev["data"],
            })
            display_order += 1

        if exp:
            health_series.append({
                "id": f"{cat}_EXP",
                "name": f"{cat_name} - Expenses",
                "display_order": display_order,
                "data": exp["data"],
            })
            display_order += 1

        if rev and exp:
            rev_map = points_to_map(rev["data"])
            exp_map = points_to_map(exp["data"])
            common_dates = sorted(set(rev_map) & set(exp_map))
            profit_data = [
                {"date": d, "value": rev_map[d] - exp_map[d]}
                for d in common_dates
            ]
            if profit_data:
                health_series.append({
                    "id": f"{cat}_PROFIT",
                    "name": f"{cat_name} - Profit",
                    "display_order": display_order,
                    "data": profit_data,
                })
                display_order += 1

            # Quarterly margin = (rev - exp) / rev, expressed as %
            margin_data = [
                {"date": d, "value": (rev_map[d] - exp_map[d]) / rev_map[d] * 100}
                for d in common_dates
                if rev_map[d] and rev_map[d] > 0
            ]
            if margin_data:
                health_series.append({
                    "id": f"{cat}_MARGIN",
                    "name": f"{cat_name} - Margin",
                    "display_order": display_order,
                    "data": margin_data,
                })
                display_order += 1

            # TTM margin = (sum of 4 quarters of profit) / (sum of 4 quarters of rev)
            # Requires 4 consecutive quarters with both rev and exp non-null.
            def _next_q(y, m):
                nm = m + 3
                return (y + (nm - 1) // 12, ((nm - 1) % 12) + 1)
            margin_ttm_data = []
            for i in range(3, len(common_dates)):
                window = common_dates[i - 3:i + 1]
                # Verify the window is 4 consecutive quarters
                ok = True
                y, m, _ = window[0].split("-")
                cy, cm = int(y), int(m)
                for j in range(1, 4):
                    cy, cm = _next_q(cy, cm)
                    wy, wm, _ = window[j].split("-")
                    if (cy, cm) != (int(wy), int(wm)):
                        ok = False
                        break
                if not ok:
                    continue
                rev_sum = sum(rev_map[d] for d in window)
                exp_sum = sum(exp_map[d] for d in window)
                if rev_sum > 0:
                    margin_ttm_data.append({
                        "date": window[-1],
                        "value": (rev_sum - exp_sum) / rev_sum * 100,
                    })
            if margin_ttm_data:
                health_series.append({
                    "id": f"{cat}_MARGIN_TTM",
                    "name": f"{cat_name} - TTM Margin",
                    "display_order": display_order,
                    "data": margin_ttm_data,
                })
                display_order += 1

    save_json({
        "metadata": {
            **data["metadata"],
            "title": "QSS Health Care (NAICS 62) - Revenue, Expenses, Profit",
        },
        "series": health_series,
    }, "qss/qss_health.json")
    print(f"  qss_health.json: {len(health_series)} series (rev + exp + profit for NAICS 62)")


def process_wholesale():
    """Split wholesale.json into sales, inventory, and ratio files."""
    print("Splitting wholesale data into sales/inventory/ratio...")
    data = load_json("wholesale/wholesale.json")
    if not data:
        return

    sales, inventory, ratio = [], [], []

    from fetch_wholesale import CATEGORY_NAMES as WS_NAMES, DATA_TYPE_NAMES as WS_DTYPES

    for s in data["series"]:
        sid = s["id"]
        parts = sid.rsplit("_", 1)
        if len(parts) != 2:
            continue
        cat, dtype = parts

        # Apply industry names (replaces raw NAICS codes)
        cat_name = WS_NAMES.get(cat, cat)
        dtype_name = WS_DTYPES.get(dtype, dtype)
        s["name"] = f"{cat_name} - {dtype_name}"

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

    # Compute "Other Professional Equipment" = 4234 minus 42343
    def compute_diff(series_a, series_b):
        """Subtract series_b data from series_a, matched by date."""
        b_map = {d["date"]: d["value"] for d in series_b["data"]}
        points = []
        for d in series_a["data"]:
            a_val = d["value"]
            b_val = b_map.get(d["date"])
            if a_val is not None and b_val is not None:
                points.append({"date": d["date"], "value": round(a_val - b_val, 1)})
            else:
                points.append({"date": d["date"], "value": None})
        return points

    sales_4234 = next((s for s in sales if s["id"] == "4234_SM"), None)
    sales_42343 = next((s for s in sales if s["id"] == "42343_SM"), None)
    inv_4234 = next((s for s in inventory if s["id"] == "4234_IM"), None)
    inv_42343 = next((s for s in inventory if s["id"] == "42343_IM"), None)

    if sales_4234 and sales_42343:
        other_sales = compute_diff(sales_4234, sales_42343)
        sales.append({"id": "4234X_SM", "name": "Other Professional Equipment - Sales", "data": other_sales})

    if inv_4234 and inv_42343:
        other_inv = compute_diff(inv_4234, inv_42343)
        inventory.append({"id": "4234X_IM", "name": "Other Professional Equipment - Inventories", "data": other_inv})

    if sales_4234 and sales_42343 and inv_4234 and inv_42343:
        # Ratio = other inventory / other sales
        other_s_map = {d["date"]: d["value"] for d in other_sales}
        other_i_map = {d["date"]: d["value"] for d in other_inv}
        ratio_pts = []
        for d in other_sales:
            s_val = other_s_map.get(d["date"])
            i_val = other_i_map.get(d["date"])
            if s_val and i_val is not None and s_val != 0:
                ratio_pts.append({"date": d["date"], "value": round(i_val / s_val, 2)})
            else:
                ratio_pts.append({"date": d["date"], "value": None})
        ratio.append({"id": "4234X_IR", "name": "Other Professional Equipment - Inventories/Sales Ratio", "data": ratio_pts})

    if sales:
        save_json(make_output(sales, "Wholesale Trade - Sales",
                              "Millions of dollars"), "wholesale/wholesale_sales.json")
    if inventory:
        save_json(make_output(inventory, "Wholesale Trade - Inventories",
                              "Millions of dollars"), "wholesale/wholesale_inventory.json")
    if ratio:
        save_json(make_output(ratio, "Wholesale Trade - Inventory/Sales Ratio",
                              "Ratio"), "wholesale/wholesale_ratio.json")

    # Compute implied purchases: Sales × 0.7 + ΔInventory (month-over-month)
    inv_by_cat = {}
    for s in inventory:
        parts = s["id"].rsplit("_", 1)
        if len(parts) == 2 and parts[1] == "IM":
            inv_by_cat[parts[0]] = s

    implied = []
    for s in sales:
        parts = s["id"].rsplit("_", 1)
        if len(parts) != 2:
            continue
        cat = parts[0]
        inv_s = inv_by_cat.get(cat)
        if not inv_s:
            continue

        # Build inventory lookup by date
        inv_map = {d["date"]: d["value"] for d in inv_s["data"]}

        # Sort all dates to determine previous month for each date
        all_dates = sorted(set(d["date"] for d in s["data"]) | set(inv_map.keys()))
        prev_inv_map = {}
        for i, dt in enumerate(all_dates):
            if i > 0:
                prev_inv_map[dt] = inv_map.get(all_dates[i - 1])

        points = []
        for d in s["data"]:
            sales_val = d["value"]
            inv_val = inv_map.get(d["date"])
            prev_inv_val = prev_inv_map.get(d["date"])

            if sales_val is not None and inv_val is not None and prev_inv_val is not None:
                delta_inv = inv_val - prev_inv_val
                ip_val = round(sales_val * 0.7 + delta_inv, 1)
                points.append({"date": d["date"], "value": ip_val})
            else:
                points.append({"date": d["date"], "value": None})

        cat_name = s["name"].rsplit(" - ", 1)[0]
        implied.append({
            "id": f"{cat}_IP",
            "name": f"{cat_name} - Implied Purchases",
            "data": points
        })

    if implied:
        save_json(make_output(implied, "Wholesale Trade - Implied Purchases",
                              "Millions of dollars"), "wholesale/wholesale_implied_purchases.json")
        print(f"  {len(implied)} implied purchases series")


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


def process_ces_split():
    """Split CES employees into preliminary (current month) and detailed (lagged)."""
    print("Splitting CES employees by release timing...")
    data = load_json("ces/employees.json")
    if not data:
        return

    # Find the latest date across all series
    max_date = max(
        s["data"][-1]["date"]
        for s in data["series"]
        if s["data"]
    )

    preliminary = []
    detailed = []
    for s in data["series"]:
        if not s["data"]:
            continue
        last = s["data"][-1]["date"]
        if last == max_date:
            preliminary.append(s)
        else:
            detailed.append(s)

    # The detailed page uses totalSeriesIndex: 0 for "% of Total" charts, but
    # "Total nonfarm" is a current-month (preliminary-timing) series and would
    # otherwise be missing from the detailed file — leaving whatever detailed
    # industry sorts first at index 0 (e.g. Surface coal mining). Prepend it
    # so the % of Total math is meaningful.
    total_nonfarm = next(
        (s for s in data["series"] if s.get("id") == "CES0000000001"),
        None
    )
    if total_nonfarm and not any(s.get("id") == "CES0000000001" for s in detailed):
        # Copy the series (don't mutate the preliminary copy)
        detailed.insert(0, {**total_nonfarm})

    for i, s in enumerate(preliminary):
        s["display_order"] = i
    for i, s in enumerate(detailed):
        s["display_order"] = i

    meta = data["metadata"]

    if preliminary:
        save_json({
            "metadata": {**meta, "title": "Employees - Preliminary (Current Month)"},
            "series": preliminary
        }, "ces/employees_preliminary.json")
    if detailed:
        save_json({
            "metadata": {**meta, "title": "Employees - Detailed (1-Month Lag)"},
            "series": detailed
        }, "ces/employees_detailed.json")

    print(f"  {len(preliminary)} preliminary, {len(detailed)} detailed")


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


def build_search():
    """Build search index from all data files + NAICS mappings."""
    print("Building search index...")
    import build_search_index
    build_search_index.run()


def run():
    print("=" * 40)
    print("Post-processing derived data...")
    print("=" * 40)
    process_qss()
    process_wholesale()
    process_ces_pbs()
    process_ces_split()
    process_analysis()
    copy_calendar()
    build_search()
    print("Post-processing complete.")


if __name__ == "__main__":
    run()
