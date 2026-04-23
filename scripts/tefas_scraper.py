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


def supabase_upsert(table: str, rows: list[dict], conflict_col: str) -> int:
    """Upsert rows via raw SQL using Management API (bypasses RLS)."""
    if not rows:
        return 0

    if table == "funds":
        # All scraped funds already exist in DB — use UPDATE only
        updated = 0
        for row in rows:
            code = row.get("code", "")
            price = row.get("price")
            daily_change = row.get("daily_change")
            weekly = row.get("weekly")
            monthly = row.get("monthly")
            quarterly = row.get("quarterly")
            returns_json = json.dumps(row.get("returns", {}))
            last_fetch = row.get("last_tefas_fetch", "")

            def fmt(v):
                if v is None:
                    return "NULL"
                if isinstance(v, dict):
                    escaped = json.dumps(v).replace("'", "''")
                    return f"'{escaped}'::jsonb"
                if isinstance(v, (int, float)):
                    return str(v)
                return f"'{str(v).replace(chr(39), chr(39)+chr(39))}'"

            sql = f"""
            UPDATE funds SET
                price = {fmt(price)},
                daily_change = {fmt(daily_change)},
                weekly = {fmt(weekly)},
                monthly = {fmt(monthly)},
                quarterly = {fmt(quarterly)},
                returns = {fmt(returns_json)},
                last_tefas_fetch = {fmt(last_fetch)}
            WHERE code = {fmt(code)}
            """
            result = mgmt(sql)
            if result is not None:
                updated += 1
        return updated

    # Default: use REST API (for other tables)
    url = f"{SUPABASE_URL}/rest/v1/{table}"
    payload = json.dumps(rows)
    req = requests.post(
        url, data=payload,
        headers={
            **HEADERS,
            "Prefer": f"resolution=merge-duplicates, conflict={conflict_col}"
        },
        timeout=60
    )
    if req.status_code not in (200, 201):
        print(f"  UPSERT ERROR {table}: {req.status_code} {req.text[:200]}")
        return 0
    return len(rows)


def get_top_funds(limit: int = 200) -> list[dict]:
    """Get top funds by market_cap (AUM) from Supabase."""
    result = mgmt(f"""
        SELECT code, name, market_cap
        FROM funds
        WHERE market_cap IS NOT NULL AND market_cap > 0
        ORDER BY market_cap DESC NULLS LAST
        LIMIT {limit}
    """)
    if not result:
        print("  Could not fetch top funds from Supabase")
        return []
    return result


def parse_date(d: str) -> date:
    """Parse Turkish date format: 'dd.mm.yyyy' → date."""
    try:
        return datetime.strptime(d, "%d.%m.%Y").date()
    except Exception:
        return None


def compute_returns(prices: dict) -> dict:
    """Compute 1M/3M/6M/1Y returns from {date: price} dict."""
    today = date.today()
    one_month = (today - timedelta(days=30)).isoformat()
    three_month = (today - timedelta(days=90)).isoformat()
    six_month = (today - timedelta(days=180)).isoformat()
    one_year = (today - timedelta(days=365)).isoformat()

    today_price = prices.get(today.isoformat()) or prices.get((today - timedelta(days=1)).isoformat())
    if not today_price:
        return {}

    def pct(target_date_str):
        p = prices.get(target_date_str)
        if not p:
            return None
        return round((today_price - p) / p * 100, 2)

    return {
        "one_month_return": pct(one_month),
        "three_month_return": pct(three_month),
        "six_month_return": pct(six_month),
        "one_year_return": pct(one_year),
    }


def scrape_fund(driver, ticker: str) -> dict | None:
    """Scrape a single fund using the shared Selenium driver."""
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

    # Wait for chart to update — check that chart data is non-zero
    # The chart data is a Highcharts series; we poll for up to 20 seconds
    def chart_loaded(driver):
        try:
            data = driver.execute_script("""
                try {
                    var chart = window.chartMainContent_FonFiyatGrafik;
                    if (!chart || !chart.series || !chart.series[0]) return false;
                    var d = chart.series[0].data;
                    if (!d || d.length === 0) return false;
                    // Check that at least the last entry has a non-zero y value
                    for (var i = d.length - 1; i >= 0; i--) {
                        if (d[i].y !== null && d[i].y !== 0) return true;
                    }
                    return false;
                } catch(e) { return false; }
            """)
            return data is True
        except Exception:
            return False

    try:
        WebDriverWait(driver, 20).until(chart_loaded)
    except TimeoutException:
        print(f"    {ticker}: chart load timeout")
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
        daily_change = round((latest_price - prev_price) / prev_price * 100, 2)

    # Compute M/Y returns
    returns = compute_returns(prices)

    print(f"    {ticker}: {latest_date} price={latest_price:.4f} 1M={returns.get('one_month_return')} daily_chg={daily_change}")

    # weekly = last 7 days
    today = date.today()
    week_7d = (today - timedelta(days=7)).isoformat()
    weekly_pct = None
    if week_7d in prices:
        weekly_pct = round((latest_price - prices[week_7d]) / prices[week_7d] * 100, 2)

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
        "last_tefas_fetch": now_ts,
    }


def main():
    from selenium import webdriver
    from selenium.webdriver.chrome.service import Service
    from selenium.webdriver.chrome.options import Options
    from webdriver_manager.chrome import ChromeDriverManager

    print(f"[TEFAS SCRAPER] Starting — max_funds={MAX_FUNDS}")

    # Get fund list from Supabase
    funds = get_top_funds(MAX_FUNDS)
    if not funds:
        print("  No funds found in DB — using empty list")
        funds = []
    tickers = [f["code"] for f in funds]
    print(f"  Got {len(tickers)} tickers from Supabase")

    # Set up Chrome (headless)
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    # Spoof user-agent to avoid WAF
    options.add_argument("--user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    driver.set_page_load_timeout(30)

    results = []
    errors = 0

    try:
        for i, ticker in enumerate(tickers):
            print(f"  [{i+1}/{len(tickers)}] {ticker}", end="")
            try:
                data = scrape_fund(driver, ticker)
                if data:
                    results.append(data)
                else:
                    errors += 1
            except Exception as e:
                print(f"    EXCEPTION: {e}")
                errors += 1

            # Small delay between requests to be polite
            time.sleep(0.5)
    finally:
        driver.quit()

    print(f"\n[TEFAS SCRAPER] Done — {len(results)} funds scraped, {errors} errors")

    if results:
        updated = supabase_upsert("funds", results, "code")
        print(f"  Upserted {updated} rows to funds table")

    # Update system_status
    mgmt(f"""
        INSERT INTO system_status (key, value, updated_at)
        VALUES ('last_tefas_fetch', '{datetime.utcnow().isoformat()}', NOW())
        ON CONFLICT (key) DO UPDATE SET
            value = EXCLUDED.value,
            updated_at = NOW()
    """)

    print("[TEFAS SCRAPER] system_status updated")
    return len(results)


if __name__ == "__main__":
    n = main()
    sys.exit(0 if n > 0 else 1)
