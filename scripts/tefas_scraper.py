#!/usr/bin/env python3
"""
TEFAS Fund Data Scraper — günlük cron job (GitHub Actions).
Kaynak: https://www.tefas.gov.tr (Selenium ile JavaScript render)

Veriler:
  - price history (5y Highcharts)
  - 1M/3M/6M/1Y returns (hesaplanan)
  - daily_change (hesaplanan)

Usage:
    python3 scripts/tefas_scraper.py [max_funds]

Environment:
    SUPABASE_KEY   — Supabase anon key
    MGMT_TOKEN     — Supabase management token
"""

import os
import sys
import json
import time
import warnings
import requests
import undetected_chromedriver as uc
from pathlib import Path
from datetime import date, datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed

warnings.filterwarnings('ignore')

SUPABASE_URL = "https://oqkobptbvcazifpvjwfz.supabase.co"
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "sb_publishable__GPrsdfKRZCMZE8to916iQ_Izv9naG-")
SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "sb_secret_PkAEAOU2YO4YS-ELYpwS5w_SsVg2kqi")
MGMT_TOKEN = os.environ.get("MGMT_TOKEN", "sbp_ce308d5b5e2b05c59cbebda49ace62e8e1413fea")
HEADERS = {
    "apikey": SERVICE_KEY,
    "Authorization": f"Bearer {SERVICE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=representation"
}
MGMT_URL = f"https://api.supabase.com/v1/projects/oqkobptbvcazifpvjwfz/database/query"

MAX_FUNDS = int(sys.argv[1]) if len(sys.argv) > 1 else 200


def mgmt(sql, timeout=60):
    """Run a raw SQL query via Supabase Management API."""
    r = requests.post(
        MGMT_URL,
        headers={"Authorization": f"Bearer {MGMT_TOKEN}", "Content-Type": "application/json"},
        json={"query": sql},
        timeout=timeout
    )
    if r.status_code not in (200, 201):
        print(f"  MGMT ERROR ({r.status_code}): {r.text[:200]}")
        return None
    try:
        return r.json()
    except Exception:
        return None


def update_funds(rows: list[dict]) -> int:
    """Update existing fund rows via REST API PATCH (service role bypasses RLS)."""
    if not rows:
        return 0
    updated = 0
    for row in rows:
        code = row.get("code")
        if not code:
            continue
        url = f"{SUPABASE_URL}/rest/v1/funds?code=eq.{code}"
        payload = json.dumps(row)
        req = requests.patch(
            url, data=payload,
            headers={
                **HEADERS,
                "Prefer": "return=minimal"
            },
            timeout=30
        )
        if req.status_code in (200, 204):
            updated += 1
        else:
            print(f"  PATCH ERROR {code}: {req.status_code}")
    return updated


def insert_system_status(key: str, value: str) -> bool:
    """Update system_status table."""
    url = f"{SUPABASE_URL}/rest/v1/system_status"
    payload = json.dumps([{"key": key, "value": value}])
    req = requests.post(
        url, data=payload,
        headers={
            **HEADERS,
            "Prefer": "resolution=merge-duplicates, conflict=key"
        },
        timeout=30
    )
    return req.status_code in (200, 201)


def get_top_funds(limit: int = 1000) -> list[dict]:
    """Fetch fund list from Supabase, sorted by market_cap desc."""
    url = f"{SUPABASE_URL}/rest/v1/funds?market_cap=gt.0&order=market_cap.desc&limit={limit}"
    req = requests.get(url, headers=HEADERS, timeout=30)
    if req.status_code != 200:
        print(f"  ERROR fetching funds: {req.status_code}")
        return []
    return req.json()


def get_funds_with_history(limit: int = 1000) -> tuple[list[dict], dict[str, list]]:
    """Fetch funds + their price_history from Supabase. Returns (funds, history_dict)."""
    url = f"{SUPABASE_URL}/rest/v1/funds?market_cap=gt.0&order=market_cap.desc&limit={limit}&select=code,name,price,price_history,last_tefas_fetch"
    req = requests.get(url, headers=HEADERS, timeout=60)
    if req.status_code != 200:
        print(f"  ERROR fetching funds: {req.status_code}")
        return [], {}
    funds = req.json()

    # Build history dict: {code: price_history_array}
    history_dict = {}
    for f in funds:
        ph = f.get("price_history")
        if isinstance(ph, list):
            history_dict[f["code"]] = ph
        else:
            history_dict[f["code"]] = []

    return funds, history_dict


def parse_date(d: str) -> date:
    """Parse Turkish date format: 'dd.mm.yyyy' → date."""
    try:
        return datetime.strptime(d, "%d.%m.%Y").date()
    except Exception:
        return None


def compute_returns(prices: dict) -> dict:
    """Compute 1M/3M/6M/1Y returns from {date: price} dict.

    For each target period, finds the most recent available price on or before
    the target date (handles holidays/weekends). Falls back to the earliest
    available price if no prior price exists.
    """
    today = date.today()
    one_month = (today - timedelta(days=30)).isoformat()
    three_month = (today - timedelta(days=90)).isoformat()
    six_month = (today - timedelta(days=180)).isoformat()
    one_year = (today - timedelta(days=365)).isoformat()

    today_price = prices.get(today.isoformat()) or prices.get((today - timedelta(days=1)).isoformat())
    if not today_price:
        return {}

    def pct(target_date_str):
        # Find most recent available price on or before target_date
        target = date.fromisoformat(target_date_str)
        best_date = None
        best_price = None
        for d_str, p in prices.items():
            d = date.fromisoformat(d_str)
            if d <= target and (best_date is None or d > best_date):
                best_date = d
                best_price = p
        if best_price is None or best_price == 0:
            return None
        return round((today_price - best_price) / best_price * 100, 2)

    return {
        "one_month_return": pct(one_month),
        "three_month_return": pct(three_month),
        "six_month_return": pct(six_month),
        "one_year_return": pct(one_year),
    }


def scrape_fund(driver, ticker: str, existing_history: list[dict]) -> dict | None:
    """Scrape a single fund using the shared Selenium driver.

    existing_history: list of {date, price, change} from DB (used to extend price
    history beyond the ~60-day window TEFAS chart provides, so we can compute
    6M and 1Y returns).
    """
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.common.exceptions import TimeoutException, NoSuchElementException

    url = f"https://www.tefas.gov.tr/FonAnaliz.aspx?FonKod={ticker}"
    driver.get(url)

    try:
        # Wait for page to be interactive (UpdatePanel loaded)
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.ID, "MainContent_RadioButtonListPeriod_7"))
        )
    except TimeoutException:
        print(f"    {ticker}: page load timeout")
        return None

    try:
        # Click 5-year radio button
        btn = driver.find_element(By.ID, "MainContent_RadioButtonListPeriod_7")
        btn.click()
    except NoSuchElementException:
        print(f"    {ticker}: 5y button not found")
        return None

    # Wait for chart to update — the async UpdatePanel changes chart data after click
    # Default period has ~253 pts; 5-year period has ~1255 pts.
    # We poll until category count increases (proving the period changed).
    initial_count = None
    def chart_updated(driver):
        nonlocal initial_count
        try:
            cats = driver.execute_script("""
                try {
                    var chart = window.chartMainContent_FonFiyatGrafik;
                    if (!chart || !chart.xAxis || !chart.xAxis[0] || !chart.xAxis[0].categories) return -1;
                    return chart.xAxis[0].categories.length;
                } catch(e) { return -1; }
            """)
            if cats is None or cats == -1:
                return False
            if initial_count is None:
                initial_count = cats
                return False  # First read — record count but keep waiting
            # Wait for count to increase significantly (5-year has >1000 pts)
            return cats > initial_count and cats > 500
        except Exception:
            return False

    try:
        WebDriverWait(driver, 20).until(chart_updated)
    except TimeoutException:
        print(f"    {ticker}: chart update timeout (initial={initial_count})")
        return None

    # Extract dates and prices
    try:
        result = driver.execute_script("""
            var chart = window.chartMainContent_FonFiyatGrafik;
            var dates = chart.xAxis[0].categories;
            var points = chart.series[0].data;
            var prices = points.map(function(p) { return p.y; });
            return { dates: dates, prices: prices };
        """)
    except Exception as e:
        print(f"    {ticker}: JS extract error: {e}")
        return None

    if not result or not result.get("dates"):
        print(f"    {ticker}: no chart data")
        return None

    # Build {date_iso: price} dict
    prices = {}
    for d_str, p in zip(result["dates"], result["prices"]):
        parsed = parse_date(d_str)
        if parsed and p is not None:
            prices[parsed.isoformat()] = round(p, 6)

    if not prices:
        print(f"    {ticker}: no valid price data")
        return None

    # Latest price
    latest_date = max(prices.keys())
    latest_price = prices[latest_date]

    # Daily change: compare to previous trading day
    sorted_dates = sorted(prices.keys(), reverse=True)
    daily_change = None
    if len(sorted_dates) >= 2:
        prev_price = prices[sorted_dates[1]]
        if prev_price and prev_price != 0:
            daily_change = round((latest_price - prev_price) / prev_price * 100, 2)

    # Merge existing price history (from DB) with fresh prices from TEFAS chart.
    # TEFAS only gives ~60 days of data, so 6M/1Y returns need older prices.
    merged_prices = dict(prices)
    for entry in existing_history:
        d = entry["date"]
        p = entry["price"]
        if p is not None and d not in merged_prices:
            merged_prices[d] = p

    # Compute M/Y returns using full merged history
    returns = compute_returns(merged_prices)

    print(f"    {ticker}: {latest_date} price={latest_price:.4f} 1M={returns.get('one_month_return')} 3M={returns.get('three_month_return')} 6M={returns.get('six_month_return')} 1Y={returns.get('one_year_return')} daily_chg={daily_change}")

    # weekly = last 7 days
    today = date.today()
    week_7d = (today - timedelta(days=7)).isoformat()
    weekly_pct = None
    if week_7d in prices:
        weekly_pct = round((latest_price - prices[week_7d]) / prices[week_7d] * 100, 2)

    # Build price_history array (sorted by date asc, like DB format)
    sorted_dates = sorted(prices.keys())
    price_history = []
    for i, d in enumerate(sorted_dates):
        change = None
        if i > 0:
            prev_p = prices[sorted_dates[i - 1]]
            change = round((prices[d] - prev_p) / prev_p * 100, 4)
        price_history.append({
            "date": d,
            "price": prices[d],
            "change": change,
        })

    now_ts = datetime.utcnow().isoformat()

    return {
        "code": ticker,
        "price": latest_price,
        "daily_change": daily_change,
        "weekly": weekly_pct,
        "monthly": returns.get("one_month_return"),
        "quarterly": returns.get("three_month_return"),
        "returns": {
            "1D": round(daily_change, 2) if daily_change else None,
            "1W": weekly_pct,
            "1M": returns.get("one_month_return"),
            "3M": returns.get("three_month_return"),
            "6M": returns.get("six_month_return"),
            "1Y": returns.get("one_year_return"),
        },
        "price_history": price_history,
        "last_tefas_fetch": now_ts,
    }


def main():
    from selenium import webdriver
    from selenium.webdriver.chrome.service import Service
    from selenium.webdriver.chrome.options import Options
    from webdriver_manager.chrome import ChromeDriverManager

    import json as _json
    marker_path = Path(__file__).parent.parent / "logs" / "scraper_last_run.json"
    marker_path.parent.mkdir(exist_ok=True)
    with open(marker_path, "w") as _f:
        _json.dump({
            "started_at": datetime.utcnow().isoformat(),
            "finished_at": None,
            "funds_scraped": 0,
            "errors": 0,
            "status": "running",
        }, _f)
    print(f"[TEFAS SCRAPER] Wrote start marker to {marker_path}")

    print(f"[TEFAS SCRAPER] Starting — max_funds={MAX_FUNDS}")

    # Fetch funds WITH their existing price_history
    funds, existing_history = get_funds_with_history(MAX_FUNDS)
    if not funds:
        print("  No funds found in DB — using empty list")
        funds = []
    tickers = [f["code"] for f in funds]
    print(f"  Got {len(tickers)} tickers from Supabase")

    # Check which funds need full re-scrape (no history or last_fetch > 1 day ago)
    today_str = date.today().isoformat()
    need_scrape = []
    for f in funds:
        code = f["code"]
        last_fetch = (f.get("last_tefas_fetch") or "")[:10]  # YYYY-MM-DD
        has_history = isinstance(existing_history.get(code), list) and len(existing_history[code]) > 0
        if not has_history or last_fetch != today_str:
            need_scrape.append(code)
        else:
            print(f"  [SKIP {code}] already scraped today ({last_fetch}), history={len(existing_history.get(code, []))} pts")

    print(f"  Need to scrape: {len(need_scrape)}/{len(tickers)}")

    if not need_scrape:
        print("  All funds up to date — nothing to do")
        # Write "all good" marker
        import json as _json
        marker_path = Path(__file__).parent.parent / "logs" / "scraper_last_run.json"
        marker_path.parent.mkdir(exist_ok=True)
        with open(marker_path, "w") as _f:
            _json.dump({
                "started_at": datetime.utcnow().isoformat(),
                "finished_at": datetime.utcnow().isoformat(),
                "funds_scraped": 0,
                "errors": 0,
                "status": "up_to_date",
            }, _f)
        return 0

    # Set up Chrome with undetected-chromedriver (bypasses Cloudflare WAF)
    options = uc.ChromeOptions()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    driver = uc.Chrome(options=options, version_main=None)
    driver.set_page_load_timeout(30)

    results = []
    errors = 0
    skipped = 0

    try:
        for i, ticker in enumerate(need_scrape):
            print(f"  [{i+1}/{len(need_scrape)}] {ticker}", end="")
            try:
                data = scrape_fund(driver, ticker, existing_history.get(ticker, []))
                if data:
                    # Merge with existing price_history (deduplicate by date, sort asc)
                    existing = existing_history.get(ticker, [])
                    new_ph = data["price_history"]
                    merged = merge_price_history(existing, new_ph)
                    data["price_history"] = merged
                    results.append(data)
                    print(f" | merged {len(existing)} + {len(new_ph)} = {len(merged)} pts")
                else:
                    errors += 1
                    print()
            except Exception as e:
                print(f"    EXCEPTION: {e}")
                errors += 1

            # Small delay between requests to be polite
            time.sleep(0.5)
    finally:
        driver.quit()

    print(f"\n[TEFAS SCRAPER] Done — {len(results)} funds scraped, {errors} errors, {skipped} skipped")

    if results:
        updated = update_funds(results)
        print(f"  Upserted {updated} rows to funds table")

    # Update system_status
    insert_system_status("last_tefas_fetch", datetime.utcnow().isoformat())
    print("[TEFAS SCRAPER] system_status updated")

    # Write completion marker for monitoring
    import json as _json
    marker_path = Path(__file__).parent.parent / "logs" / "scraper_last_run.json"
    marker_path.parent.mkdir(exist_ok=True)
    try:
        with open(marker_path) as _f:
            prev = _json.load(_f)
        started_at = prev.get("started_at", datetime.utcnow().isoformat())
    except Exception:
        started_at = datetime.utcnow().isoformat()
    with open(marker_path, "w") as _f:
        _json.dump({
            "started_at": started_at,
            "finished_at": datetime.utcnow().isoformat(),
            "funds_scraped": len(results),
            "errors": errors,
            "status": "ok" if errors == 0 else "partial",
        }, _f)
    print(f"[TEFAS SCRAPER] Wrote marker to {marker_path}")
    return len(results)


def merge_price_history(existing: list[dict], new: list[dict]) -> list[dict]:
    """Merge new price_history into existing, keeping latest data per date."""
    if not existing:
        return new
    if not new:
        return existing

    # Deduplicate: build dict by date, existing takes priority for same date
    merged = {}
    for entry in existing:
        merged[entry["date"]] = entry
    for entry in new:
        merged[entry["date"]] = entry  # new overwrites existing for same date

    # Sort by date asc
    return sorted(merged.values(), key=lambda x: x["date"])


if __name__ == "__main__":
    n = main()
    sys.exit(0 if n > 0 else 1)
