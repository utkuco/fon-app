#!/usr/bin/env python3
"""
TEFAS 5-Year Backfill Script — fills missing price_history for all funds.
Designed for retry after timeout failures.

Usage:
    python3 scripts/tefas_5y_backfill.py [max_funds]

Environment:
    SUPABASE_KEY   — Supabase service role key
    FUND_CODE_FILE — Optional: file with specific fund codes to backfill (one per line)
"""
from __future__ import annotations

import os
import sys
import json
import time
import signal
import requests
from pathlib import Path
from datetime import date, datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock

SUPABASE_URL = "https://oqkobptbvcazifpvjwfz.supabase.co"
SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "sb_secret_PkAEAOU2YO4YS-ELYpwS5w_SsVg2kqi")
HEADERS = {
    "apikey": SERVICE_KEY,
    "Authorization": f"Bearer {SERVICE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=representation"
}

PAGE_SIZE = 1000  # Supabase default limit
RETRY_TIMEOUT = 30  # seconds to wait for chart update
MAX_RETRIES = 2    # retries per fund on timeout


# ─── Supabase helpers ──────────────────────────────────────────────────────────

def get_all_funds_with_ph() -> tuple[list[dict], dict]:
    """Fetch ALL funds with pagination, returns (funds, history_dict)."""
    all_funds = []
    page = 0
    while True:
        offset = page * PAGE_SIZE
        url = (
            f"{SUPABASE_URL}/rest/v1/funds"
            f"?market_cap=gt.0&order=market_cap.desc"
            f"&limit={PAGE_SIZE}&offset={offset}"
            f"&select=code,name,price,price_history,last_tefas_fetch"
        )
        req = requests.get(url, headers=HEADERS, timeout=60)
        if req.status_code != 200:
            print(f"  ERROR fetching funds page {page}: {req.status_code} {req.text[:200]}")
            break
        page_funds = req.json()
        if not page_funds:
            break
        all_funds.extend(page_funds)
        if len(page_funds) < PAGE_SIZE:
            break
        page += 1
        print(f"    Fetched page {page} ({len(page_funds)} funds, total so far: {len(all_funds)})")

    history_dict = {}
    for f in all_funds:
        ph = f.get("price_history")
        history_dict[f["code"]] = ph if isinstance(ph, list) else []

    return all_funds, history_dict


def get_target_funds(code_file: str = None, max_funds: int = None) -> list[str]:
    """Get list of fund codes to backfill (sorted by history length, shortest first)."""
    funds, history_dict = get_all_funds_with_ph()
    print(f"Got {len(funds)} funds from Supabase")

    if code_file and os.path.exists(code_file):
        # Backfill only specific codes
        with open(code_file) as f:
            target_codes = {line.strip() for line in f if line.strip()}
        targets = [f for f in funds if f["code"] in target_codes]
        print(f"Backfilling {len(targets)} specific codes from {code_file}")
    else:
        targets = funds

    # Sort by existing history length (shortest first = most need 5Y)
    targets.sort(key=lambda f: len(history_dict.get(f["code"], []) or []))

    if max_funds:
        targets = targets[:max_funds]

    print(f"Target funds for 5Y backfill: {len(targets)}")
    return [f["code"] for f in targets], history_dict


def update_fund_price_history(code: str, price_history: list[dict], last_fetch: str) -> bool:
    """Update a single fund's price_history in Supabase."""
    url = f"{SUPABASE_URL}/rest/v1/funds?code=eq.{code}"
    payload = json.dumps([{
        "code": code,
        "price_history": price_history,
        "last_tefas_fetch": last_fetch,
    }])
    req = requests.patch(url, data=payload, headers={**HEADERS, "Prefer": "return=minimal"}, timeout=30)
    return req.status_code in (200, 204)


def insert_system_status(key: str, value: str) -> bool:
    url = f"{SUPABASE_URL}/rest/v1/system_status"
    payload = json.dumps([{"key": key, "value": value}])
    req = requests.post(url, data=payload, headers={
        **HEADERS, "Prefer": "resolution=merge-duplicates, conflict=key"
    }, timeout=30)
    return req.status_code in (200, 201)


def needs_5y_data(existing_ph: list) -> tuple[bool, str]:
    """
    Returns (needs_5y, reason).
    Checks existing price_history oldest date — if < 5 years, skip.
    """
    existing_len = len(existing_ph) if existing_ph else 0
    if existing_len >= 1200:
        return False, f"already has {existing_len} pts"

    if existing_ph:
        oldest = min(e["date"] for e in existing_ph)
        cutoff = (date.today() - timedelta(days=5 * 365 + 30)).isoformat()
        if oldest <= cutoff:
            return True, f"oldest={oldest} < 5y cutoff"
        else:
            return False, f"oldest={oldest}, fund is < 5y old — SKIP"

    # No price history at all — scrape anyway (new fund, TEFAS will return what it has)
    return True, "no price_history, will scrape"


# ─── TEFAS scraping ───────────────────────────────────────────────────────────

def parse_date(d: str):
    try:
        return datetime.strptime(d, "%d.%m.%Y").date()
    except Exception:
        return None


def scrape_fund(driver, ticker: str) -> dict | None:
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.common.exceptions import TimeoutException, NoSuchElementException

    url = f"https://www.tefas.gov.tr/FonAnaliz.aspx?FonKod={ticker}"
    driver.get(url)

    try:
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.ID, "MainContent_RadioButtonListPeriod_7"))
        )
    except TimeoutException:
        print(f"    {ticker}: page load timeout")
        return None

    try:
        btn = driver.find_element(By.ID, "MainContent_RadioButtonListPeriod_7")
        btn.click()
    except NoSuchElementException:
        print(f"    {ticker}: 5y button not found")
        return None

    # Poll for chart update — chart must change (more points than before)
    # For funds without 5y data, chart may only show <500 pts — that's their max history
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
                return False
            # Chart must have more points than before (change occurred)
            # If it has >500 pts — definitely 5y. If <500 but changed — that's the fund's max history
            return cats > initial_count
        except Exception:
            return False

    try:
        WebDriverWait(driver, RETRY_TIMEOUT).until(chart_updated)
    except TimeoutException:
        # Chart never changed — 5Y button may not work for this fund
        print(f"    {ticker}: chart update timeout (initial={initial_count})")
        return None

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

    prices = {}
    for d_str, p in zip(result["dates"], result["prices"]):
        parsed = parse_date(d_str)
        if parsed and p is not None:
            prices[parsed.isoformat()] = round(p, 6)

    if not prices:
        print(f"    {ticker}: no valid price data")
        return None

    latest_date = max(prices.keys())
    latest_price = prices[latest_date]

    # Daily change
    sorted_dates = sorted(prices.keys(), reverse=True)
    daily_change = None
    if len(sorted_dates) >= 2:
        prev_price = prices[sorted_dates[1]]
        if prev_price and prev_price != 0:
            daily_change = round((latest_price - prev_price) / prev_price * 100, 2)

    # Compute returns
    today = date.today()
    def pct(days):
        target = (today - timedelta(days=days)).isoformat()
        p = prices.get(target)
        if not p or p == 0:
            return None
        return round((latest_price - p) / p * 100, 2)

    returns = {
        "one_month_return": pct(30),
        "three_month_return": pct(90),
        "six_month_return": pct(180),
        "one_year_return": pct(365),
    }

    # Build price_history array
    sorted_keys = sorted(prices.keys())
    price_history = []
    for i, d in enumerate(sorted_keys):
        change = None
        if i > 0:
            prev_p = prices[sorted_keys[i - 1]]
            if prev_p and prev_p != 0:
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
        "monthly": round(returns.get("one_month_return") * 100, 2) if returns.get("one_month_return") is not None else None,
        "quarterly": round(returns.get("three_month_return") * 100, 2) if returns.get("three_month_return") is not None else None,
        "price_history": price_history,
        "last_tefas_fetch": now_ts,
    }


def merge_price_history(existing: list, new: list) -> list:
    """Merge new price_history into existing, newer data wins for same date."""
    if not existing:
        return new
    if not new:
        return existing
    merged = {}
    for entry in existing:
        merged[entry["date"]] = entry
    for entry in new:
        merged[entry["date"]] = entry
    return sorted(merged.values(), key=lambda x: x["date"])


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    from selenium import webdriver
    from selenium.webdriver.chrome.service import Service
    from selenium.webdriver.chrome.options import Options
    from webdriver_manager.chrome import ChromeDriverManager

    max_funds_arg = int(sys.argv[1]) if len(sys.argv) > 1 else None
    code_file = os.environ.get("FUND_CODE_FILE")

    marker_path = Path(__file__).parent.parent / "logs" / "5y_backfill_last_run.json"
    marker_path.parent.mkdir(exist_ok=True)
    with open(marker_path, "w") as _f:
        json.dump({
            "started_at": datetime.utcnow().isoformat(),
            "finished_at": None,
            "funds_scraped": 0,
            "errors": 0,
            "status": "running",
        }, _f)
    print(f"[5Y BACKFILL] Started — max_funds={max_funds_arg}, code_file={code_file}")

    # Get target funds
    target_codes, existing_history = get_target_funds(code_file=code_file, max_funds=max_funds_arg)

    if not target_codes:
        print("  No funds to backfill — all done!")
        return 0

    # Chrome setup
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)

    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    driver.set_page_load_timeout(30)
    driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
        "source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
    })

    results = []
    errors = 0
    updated = 0

    def handle_interrupt(sig, frame):
        print(f"\n[5Y BACKFILL] Interrupted! Saving progress...")
        driver.quit()
        sys.exit(1)
    signal.signal(signal.SIGINT, handle_interrupt)

    try:
        for i, ticker in enumerate(target_codes):
            existing = existing_history.get(ticker, []) or []
            existing_len = len(existing)

            # Smart skip: already has 5y, or fund is < 5 years old
            needs, reason = needs_5y_data(existing)
            if not needs:
                print(f"  [{i+1}/{len(target_codes)}] {ticker} (existing: {existing_len} pts) — SKIP ({reason})")
                continue

            print(f"  [{i+1}/{len(target_codes)}] {ticker} (existing: {existing_len} pts) — {reason}", end="")

            success = False
            for attempt in range(MAX_RETRIES):
                try:
                    data = scrape_fund(driver, ticker)
                    if data:
                        new_ph = data["price_history"]
                        merged = merge_price_history(existing, new_ph)
                        data["price_history"] = merged

                        # Update Supabase immediately
                        ok = update_fund_price_history(ticker, merged, data["last_tefas_fetch"])
                        if ok:
                            results.append(data)
                            success = True
                            print(f" | merged {existing_len} + {len(new_ph)} = {len(merged)} pts ✅")
                            updated += 1
                        else:
                            print(f" | merged {existing_len} + {len(new_ph)} = {len(merged)} pts, but Supabase PATCH FAILED")
                        break
                    else:
                        if attempt < MAX_RETRIES - 1:
                            print(f" | timeout, retrying...", end="")
                            time.sleep(2)
                except Exception as e:
                    print(f"    EXCEPTION: {e}")
                    if attempt < MAX_RETRIES - 1:
                        time.sleep(2)

            if not success:
                errors += 1
                print()

            time.sleep(0.5)
    finally:
        driver.quit()

    print(f"\n[5Y BACKFILL] Done — {len(results)} funds scraped, {errors} errors, {updated} Supabase updates")

    insert_system_status("last_5y_backfill", datetime.utcnow().isoformat())
    print("[5Y BACKFILL] system_status updated")

    with open(marker_path, "w") as _f:
        json.dump({
            "started_at": datetime.utcnow().isoformat(),
            "finished_at": datetime.utcnow().isoformat(),
            "funds_scraped": len(results),
            "errors": errors,
            "status": "ok" if errors == 0 else "partial",
        }, _f)

    return len(results)


if __name__ == "__main__":
    n = main()
