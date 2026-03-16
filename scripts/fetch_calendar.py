"""
Scrape release calendars from BLS, BEA, Census, and FRED to build
a schedule of exact data release dates.

Output: config/release_calendar.json
"""

import os
import sys
import json
import re
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(__file__))
from utils import load_api_keys, retry_request, CONFIG_DIR

# Browser-like headers needed for BLS (blocks simple user-agents)
BLS_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) Gecko/20100101 Firefox/120.0',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.5',
    'Referer': 'https://www.bls.gov/',
    'DNT': '1',
    'Sec-Fetch-Dest': 'document',
    'Sec-Fetch-Mode': 'navigate',
    'Sec-Fetch-Site': 'same-origin',
    'Sec-Fetch-User': '?1',
}

OUTPUT_PATH = os.path.join(CONFIG_DIR, 'release_calendar.json')


def scrape_bls():
    """Scrape BLS CES release dates from schedule page, with first-Friday fallback."""
    print("  Fetching BLS Employment release schedule...")

    # Try scraping the CES news release schedule page
    urls = [
        "https://www.bls.gov/ces/publications/news-release-schedule.htm",
        "https://www.bls.gov/schedule/news_release/empsit.htm",
    ]

    for url in urls:
        try:
            from bs4 import BeautifulSoup
            resp = retry_request(url, headers=BLS_HEADERS)
            if resp.status_code != 200:
                print(f"    {url} returned {resp.status_code}, trying next...")
                continue
            soup = BeautifulSoup(resp.text, 'html.parser')

            # Try multiple table selectors
            table = soup.select_one('table.release-list') or soup.select_one('table')
            if not table:
                print(f"    WARNING: No table found at {url}")
                continue

            dates = []
            for row in table.find_all('tr')[1:]:
                cells = row.find_all(['td', 'th'])
                for cell in cells:
                    text = cell.get_text(strip=True)
                    for fmt in ('%B %d, %Y', '%b. %d, %Y', '%b %d, %Y',
                                '%m/%d/%Y', '%Y-%m-%d'):
                        try:
                            dt = datetime.strptime(text, fmt)
                            dates.append(dt.strftime('%Y-%m-%d'))
                            break
                        except ValueError:
                            continue

            if dates:
                dates = sorted(set(dates))
                print(f"    Found {len(dates)} BLS release dates from {url}")
                return dates
            else:
                print(f"    No dates parsed from {url}, trying next...")

        except Exception as e:
            print(f"    ERROR scraping {url}: {e}")

    # Fallback: compute first Friday of each month for current + next year
    print("    Scraping failed, computing first-Friday-of-month fallback dates...")
    from calendar import monthrange
    now = datetime.now()
    dates = []
    for year in [now.year, now.year + 1]:
        for month in range(1, 13):
            # Find first Friday: day 1's weekday, then offset to Friday (4)
            first_day_weekday = datetime(year, month, 1).weekday()  # 0=Mon
            friday_offset = (4 - first_day_weekday) % 7
            first_friday = 1 + friday_offset
            dates.append(f"{year}-{month:02d}-{first_friday:02d}")
    print(f"    Generated {len(dates)} first-Friday fallback dates")
    return dates


def scrape_bea():
    """Fetch BEA release schedule from their JSON API."""
    print("  Fetching BEA release schedule...")
    url = "https://apps.bea.gov/API/signup/release_dates.json"

    try:
        resp = retry_request(url)
        data = resp.json()

        # Collect dates from relevant BEA releases for NIPA data
        relevant_releases = [
            "Personal Income and Outlays",
            "Gross Domestic Product",
            "GDP by Industry",
        ]

        dates = set()
        for release_name, info in data.items():
            # Check if this release is relevant
            if not any(r.lower() in release_name.lower() for r in relevant_releases):
                continue
            for dt_str in info.get("release_dates", []):
                try:
                    dt = datetime.fromisoformat(dt_str.replace('+00:00', '+00:00'))
                    dates.add(dt.strftime('%Y-%m-%d'))
                except (ValueError, TypeError):
                    continue

        result = sorted(dates)
        print(f"    Found {len(result)} BEA NIPA-relevant release dates")
        return result
    except Exception as e:
        print(f"    ERROR fetching BEA: {e}")
        return []


def scrape_census():
    """Scrape Census economic indicators calendar for M3, Construction, Wholesale, QSS."""
    print("  Scraping Census economic indicators calendar...")

    # Map indicator names to our dataset keys
    indicator_map = {
        "Manufacturers' Shipments, Inventories and Orders": "census_m3",
        "Construction Spending": "census_construction",
        "Monthly Wholesale Trade": "census_wholesale",
        "Quarterly Services Survey": "census_qss",
    }

    results = {key: [] for key in indicator_map.values()}

    # Try both current year and next year pages
    for url in [
        "https://www.census.gov/economic-indicators/calendar-listview.html",
    ]:
        try:
            from bs4 import BeautifulSoup
            resp = retry_request(url)
            soup = BeautifulSoup(resp.text, 'html.parser')

            table = soup.select_one('table#calendar')
            if not table:
                print(f"    WARNING: Could not find calendar table at {url}")
                continue

            for row in table.find_all('tr')[1:]:
                cells = row.find_all('td')
                visible = [c for c in cells if 'hiden' not in (c.get('class') or [])]
                if len(visible) < 2:
                    continue

                indicator_text = visible[0].get_text(strip=True)
                date_text = visible[1].get_text(strip=True)

                # Match indicator to our datasets
                matched_key = None
                for pattern, key in indicator_map.items():
                    if pattern.lower() in indicator_text.lower():
                        # Only match "Full Report" for M3 (skip Advance Report)
                        if key == "census_m3" and "advance" in indicator_text.lower():
                            continue
                        matched_key = key
                        break

                if not matched_key:
                    continue

                # Parse date
                try:
                    dt = datetime.strptime(date_text, '%B %d, %Y')
                    results[matched_key].append(dt.strftime('%Y-%m-%d'))
                except ValueError:
                    continue

        except Exception as e:
            print(f"    ERROR scraping Census: {e}")

    for key in results:
        results[key] = sorted(set(results[key]))
        print(f"    {key}: {len(results[key])} dates")

    return results


def scrape_fred_ip():
    """Fetch Industrial Production release dates from FRED API."""
    print("  Fetching FRED Industrial Production schedule...")

    try:
        keys = load_api_keys()
        fred_key = keys.get("fred", "")
        if not fred_key:
            print("    WARNING: No FRED API key, skipping")
            return []

        url = "https://api.stlouisfed.org/fred/release/dates"
        params = {
            "release_id": 13,  # G.17 Industrial Production and Capacity Utilization
            "api_key": fred_key,
            "file_type": "json",
            "include_release_dates_with_no_data": "true",
        }
        resp = retry_request(url, params=params)
        data = resp.json()

        dates = []
        for item in data.get("release_dates", []):
            date_str = item.get("date", "")
            if date_str:
                dates.append(date_str)

        # Only keep future or recent dates (within last month)
        today = datetime.now().strftime('%Y-%m-%d')
        cutoff = datetime.now().replace(month=max(1, datetime.now().month - 1)).strftime('%Y-%m-%d')
        dates = [d for d in dates if d >= cutoff]

        print(f"    Found {len(dates)} IP release dates")
        return sorted(dates)
    except Exception as e:
        print(f"    ERROR fetching FRED: {e}")
        return []


def scrape_fed_surveys():
    """Fetch Fed regional survey release dates from FRED API + computed fallbacks."""
    print("  Fetching Fed regional survey release schedules...")

    # FRED release IDs for surveys that have them
    FRED_RELEASES = {
        "fed_ny": 321,       # Empire State Manufacturing
        "fed_philly": 351,   # Manufacturing Business Outlook Survey
        "fed_dallas": 374,   # Texas Manufacturing Outlook Survey
    }

    results = {}
    try:
        keys = load_api_keys()
        fred_key = keys.get("fred", "")

        if fred_key:
            today = datetime.now().strftime('%Y-%m-%d')
            cutoff = datetime.now().replace(month=max(1, datetime.now().month - 1)).strftime('%Y-%m-%d')

            for cal_key, release_id in FRED_RELEASES.items():
                try:
                    url = "https://api.stlouisfed.org/fred/release/dates"
                    params = {
                        "release_id": release_id,
                        "api_key": fred_key,
                        "file_type": "json",
                        "include_release_dates_with_no_data": "true",
                    }
                    resp = retry_request(url, params=params)
                    data = resp.json()
                    dates = [item["date"] for item in data.get("release_dates", []) if item.get("date")]
                    dates = [d for d in dates if d >= cutoff]
                    results[cal_key] = sorted(dates)
                    print(f"    {cal_key}: {len(results[cal_key])} dates from FRED")
                except Exception as e:
                    print(f"    ERROR fetching {cal_key} from FRED: {e}")
        else:
            print("    WARNING: No FRED API key, skipping FRED-based survey dates")
    except Exception as e:
        print(f"    ERROR loading API keys: {e}")

    # Compute dates for Richmond (4th Tuesday) and KC (last Thursday)
    from calendar import monthrange
    now = datetime.now()

    def nth_weekday(year, month, weekday, n):
        """Return the nth occurrence of weekday (0=Mon) in given month."""
        first_day = datetime(year, month, 1).weekday()
        offset = (weekday - first_day) % 7
        day = 1 + offset + (n - 1) * 7
        if day > monthrange(year, month)[1]:
            return None
        return f"{year}-{month:02d}-{day:02d}"

    def last_weekday(year, month, weekday):
        """Return the last occurrence of weekday (0=Mon) in given month."""
        last_day = monthrange(year, month)[1]
        dt = datetime(year, month, last_day)
        offset = (dt.weekday() - weekday) % 7
        return f"{year}-{month:02d}-{last_day - offset:02d}"

    for cal_key, compute_fn in [
        ("fed_richmond", lambda y, m: nth_weekday(y, m, 1, 4)),   # 4th Tuesday
        ("fed_kc", lambda y, m: last_weekday(y, m, 3)),           # Last Thursday
    ]:
        if cal_key not in results:
            dates = []
            for year in [now.year, now.year + 1]:
                for month in range(1, 13):
                    d = compute_fn(year, month)
                    if d:
                        dates.append(d)
            results[cal_key] = sorted(dates)
            print(f"    {cal_key}: {len(results[cal_key])} computed dates")

    return results


def run():
    print("Fetching release calendars...")

    calendar = {
        "last_updated": datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
        "schedules": {}
    }

    # BLS (Employment Situation = CES + CPS)
    bls_dates = scrape_bls()
    calendar["schedules"]["bls"] = bls_dates

    # BEA (NIPA tables)
    bea_dates = scrape_bea()
    calendar["schedules"]["bea"] = bea_dates

    # Census (M3, Construction, Wholesale, QSS)
    census = scrape_census()
    calendar["schedules"].update(census)

    # FRED (Industrial Production)
    fred_dates = scrape_fred_ip()
    calendar["schedules"]["fred_ip"] = fred_dates

    # Fed Regional Surveys
    fed_surveys = scrape_fed_surveys()
    calendar["schedules"].update(fed_surveys)

    # Write calendar
    os.makedirs(CONFIG_DIR, exist_ok=True)
    with open(OUTPUT_PATH, 'w') as f:
        json.dump(calendar, f, indent=2)

    print(f"\nWrote {OUTPUT_PATH}")
    total = sum(len(v) for v in calendar["schedules"].values())
    print(f"Total: {total} release dates across {len(calendar['schedules'])} datasets")


if __name__ == "__main__":
    run()
