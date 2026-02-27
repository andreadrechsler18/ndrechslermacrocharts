"""
Fetch Census Bureau Construction Spending - Private Monthly detail.
Downloads the Excel file from the Census historical data page and parses
all private construction categories.
"""

import os
import sys
import io
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(__file__))
from utils import write_json, retry_request, ensure_raw_dir

EXCEL_URL = "https://www.census.gov/construction/c30/xls/privsatime.xlsx"


def run():
    print("Fetching Construction Spending from Census Excel...")
    ensure_raw_dir()

    # Download the Excel file
    print("  Downloading privsatime.xlsx...")
    resp = retry_request(EXCEL_URL, headers={
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    })
    excel_bytes = resp.content
    print(f"  Downloaded {len(excel_bytes) / 1024:.0f} KB")

    # Parse with openpyxl
    import openpyxl
    wb = openpyxl.load_workbook(io.BytesIO(excel_bytes), read_only=True, data_only=True)
    ws = wb.active

    rows = list(ws.iter_rows(values_only=True))
    wb.close()

    if len(rows) < 5:
        print("  Error: Excel has too few rows")
        return

    # Find the header row with category names (contains "Date" in column 0)
    header_row_idx = None
    for i, row in enumerate(rows):
        if row and row[0] and str(row[0]).strip().lower() == 'date':
            header_row_idx = i
            break

    if header_row_idx is None:
        print("  Error: Could not find header row")
        return

    header = rows[header_row_idx]

    # Extract category names from header columns (col 1+)
    categories = {}
    for j in range(1, len(header)):
        if header[j] is not None:
            # Clean up category name (remove embedded newlines, footnote markers)
            name = str(header[j]).replace('\n', ' ').replace('_x000D_', ' ')
            import re
            name = re.sub(r'\s+', ' ', name).strip()
            # Remove trailing footnote numbers like "1" or "2"
            name = re.sub(r'\d+$', '', name).strip()
            if name:
                categories[j] = name

    if len(categories) < 5:
        print(f"  Error: Only found {len(categories)} category columns")
        return

    print(f"  Found {len(categories)} categories")

    # Parse date strings from column 0 (format: "Mon-YY" with optional suffixes like p, r, p+)
    def parse_date_cell(cell):
        if cell is None:
            return None
        s = str(cell).strip()
        if not s:
            return None
        # Strip revision/preliminary suffixes: p, r, p+
        cleaned = re.sub(r'[pr+]+$', '', s)
        if isinstance(cell, datetime):
            return cell.strftime('%Y-%m-01')
        for fmt in ('%b-%y', '%B-%y', '%b-%Y', '%B %Y', '%b %Y', '%Y-%m'):
            try:
                dt = datetime.strptime(cleaned, fmt)
                return dt.strftime('%Y-%m-01')
            except ValueError:
                pass
        return None

    # Build per-category data series from data rows
    # Each row: col 0 = date, cols 1+ = values per category
    series_data = {j: [] for j in categories}

    for i in range(header_row_idx + 1, len(rows)):
        row = rows[i]
        if row is None or len(row) < 2:
            continue

        date_str = parse_date_cell(row[0])
        if not date_str:
            continue

        for j in categories:
            if j < len(row) and row[j] is not None:
                try:
                    val = float(row[j])
                    series_data[j].append({"date": date_str, "value": val})
                except (ValueError, TypeError):
                    pass

    # Build series list
    series_list = []
    for j, name in sorted(categories.items()):
        data_points = sorted(series_data[j], key=lambda d: d["date"])
        if len(data_points) >= 12:
            series_list.append({
                "id": f"CONST_{len(series_list):03d}",
                "name": name,
                "display_order": len(series_list),
                "data": data_points
            })

    sorted_dates = [d["date"] for d in series_list[0]["data"]] if series_list else []
    if sorted_dates:
        print(f"  Date range: {sorted_dates[0]} to {sorted_dates[-1]}")

    result = {
        "metadata": {
            "title": "Private Construction Spending",
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
