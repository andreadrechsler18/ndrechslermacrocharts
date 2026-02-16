"""
Fetch BLS Current Employment Statistics (CES) data.

Downloads bulk flat files from BLS and parses them into JSON.
This is far more efficient than making 800+ individual API calls.

Output files:
  - ces/employees.json       (All employees, thousands - all industries)
  - ces/employees_long.json  (Same data, full time range for "long" view)
  - ces/payrolls.json        (Aggregate weekly payrolls - all industries)
"""

import os
import sys
import pandas as pd
from datetime import datetime

sys.path.insert(0, os.path.dirname(__file__))
from utils import (
    load_api_keys, write_json, retry_request,
    period_to_date, ensure_raw_dir, RAW_DIR
)

BLS_BASE = "https://download.bls.gov/pub/time.series/ce"

FILES_TO_DOWNLOAD = [
    "ce.series",
    "ce.industry",
    "ce.datatype",
    "ce.data.0.AllCESSeries",
]


def download_flat_files():
    """Download BLS CES flat files if not already cached."""
    ensure_raw_dir()
    for filename in FILES_TO_DOWNLOAD:
        local_path = os.path.join(RAW_DIR, filename)
        if os.path.exists(local_path):
            age_hours = (datetime.now().timestamp() - os.path.getmtime(local_path)) / 3600
            if age_hours < 24:
                print(f"  Using cached {filename} ({age_hours:.1f}h old)")
                continue

        url = f"{BLS_BASE}/{filename}"
        print(f"  Downloading {filename}...")
        resp = retry_request(url, stream=True)
        with open(local_path, 'wb') as f:
            for chunk in resp.iter_content(chunk_size=1024 * 1024):
                f.write(chunk)
        size_mb = os.path.getsize(local_path) / (1024 * 1024)
        print(f"  Saved {filename} ({size_mb:.1f} MB)")


def load_metadata():
    """Load series, industry, and datatype metadata."""
    # Load industry lookup
    industry_df = pd.read_csv(
        os.path.join(RAW_DIR, "ce.industry"),
        sep='\t',
        dtype=str
    )
    industry_df.columns = industry_df.columns.str.strip()
    industry_df['industry_code'] = industry_df['industry_code'].str.strip()
    industry_df['industry_name'] = industry_df['industry_name'].str.strip()
    industry_map = dict(zip(industry_df['industry_code'], industry_df['industry_name']))

    # Load datatype lookup
    datatype_df = pd.read_csv(
        os.path.join(RAW_DIR, "ce.datatype"),
        sep='\t',
        dtype=str
    )
    datatype_df.columns = datatype_df.columns.str.strip()
    datatype_df['data_type_code'] = datatype_df['data_type_code'].str.strip()
    datatype_df['data_type_text'] = datatype_df['data_type_text'].str.strip()

    # Load series metadata
    series_df = pd.read_csv(
        os.path.join(RAW_DIR, "ce.series"),
        sep='\t',
        dtype=str
    )
    series_df.columns = series_df.columns.str.strip()
    for col in series_df.columns:
        series_df[col] = series_df[col].str.strip()

    return series_df, industry_map, datatype_df


def filter_series(series_df, data_type_code):
    """
    Filter for seasonally adjusted series of a given data type.
    CES series IDs starting with 'CES' are seasonally adjusted.
    """
    mask = (
        (series_df['data_type_code'] == data_type_code) &
        (series_df['seasonal'] == 'S') &
        (series_df['series_id'].str.startswith('CES'))
    )
    return series_df[mask]


def parse_data_file(wanted_series_ids):
    """
    Parse the large data file, extracting only wanted series.
    Uses chunked reading to keep memory bounded.
    """
    data_path = os.path.join(RAW_DIR, "ce.data.0.AllCESSeries")
    wanted_set = set(wanted_series_ids)

    print(f"  Parsing data file for {len(wanted_set)} series...")
    series_data = {}

    chunks = pd.read_csv(
        data_path,
        sep='\t',
        dtype=str,
        chunksize=500000
    )

    rows_read = 0
    rows_matched = 0

    for chunk in chunks:
        chunk.columns = chunk.columns.str.strip()
        for col in chunk.columns:
            chunk[col] = chunk[col].str.strip()

        # Filter to wanted series
        mask = chunk['series_id'].isin(wanted_set)
        matched = chunk[mask]
        rows_matched += len(matched)
        rows_read += len(chunk)

        for _, row in matched.iterrows():
            sid = row['series_id']
            year = int(row['year'])
            period = row['period']
            date_str = period_to_date(year, period)
            if date_str is None:
                continue

            try:
                value = float(row['value'])
            except (ValueError, TypeError):
                value = None

            if sid not in series_data:
                series_data[sid] = []
            series_data[sid].append({'date': date_str, 'value': value})

    print(f"  Read {rows_read:,} rows, matched {rows_matched:,} rows across {len(series_data)} series")
    return series_data


def build_json(series_data, series_df, industry_map, title, unit, output_path):
    """Build standardized JSON output from parsed data."""
    series_list = []
    order = 0

    # Sort series by their supersector, then industry code for consistent ordering
    sorted_ids = sorted(
        series_data.keys(),
        key=lambda sid: series_df.loc[series_df['series_id'] == sid, 'industry_code'].values[0]
        if len(series_df.loc[series_df['series_id'] == sid]) > 0 else sid
    )

    for sid in sorted_ids:
        data_points = series_data[sid]
        if len(data_points) < 2:
            continue

        # Sort by date
        data_points.sort(key=lambda d: d['date'])

        # Get industry name
        row = series_df[series_df['series_id'] == sid]
        if len(row) == 0:
            continue
        industry_code = row.iloc[0]['industry_code']
        name = industry_map.get(industry_code, f"Industry {industry_code}")

        series_list.append({
            'id': sid,
            'name': name,
            'display_order': order,
            'data': data_points
        })
        order += 1

    output = {
        'metadata': {
            'title': title,
            'source': 'BLS Current Employment Statistics',
            'unit': unit,
            'frequency': 'monthly',
            'last_updated': datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')
        },
        'series': series_list
    }

    write_json(output, output_path)
    print(f"  {len(series_list)} series written")


def run():
    """Main entry point."""
    print("Fetching CES data from BLS flat files...")

    # Step 1: Download flat files
    download_flat_files()

    # Step 2: Load metadata
    print("  Loading metadata...")
    series_df, industry_map, datatype_df = load_metadata()
    print(f"  Total series in catalog: {len(series_df):,}")

    # Step 3: Filter for employee series (data_type_code = 01)
    emp_series = filter_series(series_df, '01')
    print(f"  Employee series (SA, type 01): {len(emp_series)}")

    # Step 4: Filter for payroll series (data_type_code = 11)
    pay_series = filter_series(series_df, '11')
    print(f"  Payroll series (SA, type 11): {len(pay_series)}")

    # Step 5: Combine all wanted series IDs
    all_wanted = set(emp_series['series_id'].tolist() + pay_series['series_id'].tolist())

    # Step 6: Parse the big data file once for all wanted series
    all_data = parse_data_file(all_wanted)

    # Step 7: Split data by type and write JSON files
    emp_ids = set(emp_series['series_id'].tolist())
    pay_ids = set(pay_series['series_id'].tolist())

    emp_data = {k: v for k, v in all_data.items() if k in emp_ids}
    pay_data = {k: v for k, v in all_data.items() if k in pay_ids}

    print("\nBuilding employee JSON...")
    build_json(
        emp_data, series_df, industry_map,
        title="Employees on nonfarm payrolls",
        unit="Thousands",
        output_path="ces/employees.json"
    )

    print("\nBuilding payroll JSON...")
    build_json(
        pay_data, series_df, industry_map,
        title="Aggregate weekly payrolls",
        unit="Millions of dollars",
        output_path="ces/payrolls.json"
    )


if __name__ == '__main__':
    run()
