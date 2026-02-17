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

    # Find the header row with dates (row that has datetime or month-year values)
    header_row_idx = None
    date_columns = {}

    for i, row in enumerate(rows):
        date_count = 0
        for j, cell in enumerate(row):
            if cell is None:
                continue
            if isinstance(cell, datetime):
                date_count += 1
            elif isinstance(cell, str) and len(cell) >= 6:
                # Try to parse as date string
                for fmt in ('%b-%y', '%B %Y', '%b %Y', '%Y-%m'):
                    try:
                        datetime.strptime(cell, fmt)
                        date_count += 1
                        break
                    except ValueError:
                        pass
        if date_count >= 10:
            header_row_idx = i
            break

    if header_row_idx is None:
        print("  Error: Could not find date header row")
        return

    # Parse dates from header row
    header = rows[header_row_idx]
    for j, cell in enumerate(header):
        if cell is None:
            continue
        dt = None
        if isinstance(cell, datetime):
            dt = cell
        elif isinstance(cell, str):
            for fmt in ('%b-%y', '%B %Y', '%b %Y', '%Y-%m'):
                try:
                    dt = datetime.strptime(cell, fmt)
                    break
                except ValueError:
                    pass
        if dt:
            date_columns[j] = dt.strftime('%Y-%m-01')

    if len(date_columns) < 10:
        print(f"  Error: Only found {len(date_columns)} date columns")
        return

    print(f"  Found {len(date_columns)} date columns")
    sorted_dates = sorted(date_columns.values())
    print(f"  Date range: {sorted_dates[0]} to {sorted_dates[-1]}")

    # Parse data rows (rows after the header)
    series_list = []
    for i in range(header_row_idx + 1, len(rows)):
        row = rows[i]
        if row is None or len(row) < 2:
            continue

        name = row[0]
        if name is None or not str(name).strip():
            continue
        name = str(name).strip()

        # Skip footnote/header rows
        if name.startswith('(') or name.startswith('Note') or name.startswith('Source'):
            continue

        # Collect data points
        data_points = []
        for j, date_str in sorted(date_columns.items()):
            if j < len(row) and row[j] is not None:
                try:
                    val = float(row[j])
                    data_points.append({"date": date_str, "value": val})
                except (ValueError, TypeError):
                    pass

        if len(data_points) >= 12:
            series_list.append({
                "id": f"CONST_{len(series_list):03d}",
                "name": name,
                "display_order": len(series_list),
                "data": data_points
            })

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
