"""Shared utilities for NewCo Charts data pipeline."""

import json
import os
import time
import requests

CONFIG_DIR = os.path.join(os.path.dirname(__file__), '..', 'config')
DATA_DIR = os.path.join(os.path.dirname(__file__), '..', 'data')
RAW_DIR = os.path.join(DATA_DIR, 'raw')
JSON_DIR = os.path.join(DATA_DIR, 'json')


def load_api_keys():
    path = os.path.join(CONFIG_DIR, 'api_keys.json')
    with open(path) as f:
        return json.load(f)


def write_json(data, output_path):
    """Write data to a JSON file, creating directories as needed."""
    full_path = os.path.join(JSON_DIR, output_path)
    os.makedirs(os.path.dirname(full_path), exist_ok=True)
    with open(full_path, 'w') as f:
        json.dump(data, f, separators=(',', ':'))
    size_mb = os.path.getsize(full_path) / (1024 * 1024)
    print(f"  Wrote {full_path} ({size_mb:.1f} MB)")


HEADERS = {
    'User-Agent': 'NewCoCharts/1.0 (andrea.m.drechsler@gmail.com)',
}


def retry_request(url, params=None, max_retries=3, delay=2, stream=False, headers=None):
    """HTTP GET with retry logic."""
    hdrs = {**HEADERS, **(headers or {})}
    for attempt in range(max_retries):
        try:
            resp = requests.get(url, params=params, headers=hdrs, stream=stream, timeout=120)
            resp.raise_for_status()
            return resp
        except (requests.RequestException, requests.Timeout) as e:
            if attempt < max_retries - 1:
                print(f"  Retry {attempt + 1}/{max_retries} after error: {e}")
                time.sleep(delay * (attempt + 1))
            else:
                raise


def period_to_date(year, period):
    """Convert BLS year + period code to ISO date. 'M01' -> '2024-01-01'."""
    if period.startswith('M') and period != 'M13':
        month = int(period[1:])
        return f"{year}-{month:02d}-01"
    return None


def quarterly_to_date(time_str):
    """Convert quarterly string to ISO date. '2024Q1' -> '2024-01-01'."""
    if 'Q' in time_str:
        year, q = time_str.split('Q')
        month = (int(q) - 1) * 3 + 1
        return f"{int(year)}-{month:02d}-01"
    return None


def monthly_bea_to_date(time_str):
    """Convert BEA monthly string to ISO date. '2024M01' -> '2024-01-01'."""
    if 'M' in time_str:
        year, m = time_str.split('M')
        return f"{int(year)}-{int(m):02d}-01"
    return None


def ensure_raw_dir():
    os.makedirs(RAW_DIR, exist_ok=True)


def ensure_json_dir(subdir):
    os.makedirs(os.path.join(JSON_DIR, subdir), exist_ok=True)
