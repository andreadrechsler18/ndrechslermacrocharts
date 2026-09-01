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
    """Load API keys from config file, falling back to environment variables."""
    path = os.path.join(CONFIG_DIR, 'api_keys.json')
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    # Fall back to environment variables (for GitHub Actions)
    return {
        'bls': os.environ.get('BLS_API_KEY', ''),
        'bea': os.environ.get('BEA_API_KEY', ''),
        'census': os.environ.get('CENSUS_API_KEY', ''),
        'fred': os.environ.get('FRED_API_KEY', ''),
    }


def _strip_last_updated(payload):
    """Return a copy of a fetcher payload with metadata.last_updated removed.

    Used by write_json to compare the new payload against the on-disk file
    without letting a fresh timestamp mask an otherwise-unchanged fetch.
    """
    if not isinstance(payload, dict):
        return payload
    out = dict(payload)
    md = out.get('metadata')
    if isinstance(md, dict):
        out['metadata'] = {k: v for k, v in md.items() if k != 'last_updated'}
    return out


def write_json(data, output_path):
    """Write data to a JSON file, creating directories as needed.

    If the new payload is identical to the on-disk file (ignoring the
    metadata.last_updated timestamp), skip the write entirely so a stale
    upstream fetch doesn't produce a phantom no-op commit. Fetchers that
    hit an upstream source before it actually publishes (FRED release-date
    entries fire before data lands; Census xlsx cache serves last month)
    return unchanged series but with a fresh timestamp — without this
    guard those get committed as "Auto-update economic data ..." even
    though nothing new arrived, hiding the fact that we never picked up
    the new release.
    """
    full_path = os.path.join(JSON_DIR, output_path)
    os.makedirs(os.path.dirname(full_path), exist_ok=True)

    if os.path.exists(full_path):
        try:
            with open(full_path) as f:
                existing = json.load(f)
        except (OSError, ValueError) as e:
            print(f"  WARNING: could not read existing {full_path} ({e}); writing anyway")
        else:
            if _strip_last_updated(existing) == _strip_last_updated(data):
                size_mb = os.path.getsize(full_path) / (1024 * 1024)
                print(f"  No data change vs on-disk {full_path} ({size_mb:.1f} MB) — skipping write to avoid phantom commit")
                return

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
