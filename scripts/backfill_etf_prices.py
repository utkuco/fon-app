#!/opt/homebrew/bin/python3.11
"""
Backfill foreign_etf_prices from Yahoo Finance.
Usage: python3.11 scripts/backfill_etf_prices.py [--incremental]
"""
import sys
import os
import time
import requests

# Setup yfinance cache BEFORE importing yfinance
os.environ['YFINANCE_CACHE_DIR'] = '/tmp/yf_cache'
os.environ['YF_DATAPATH'] = '/tmp/yf_cache'
os.makedirs('/tmp/yf_cache', exist_ok=True)

import yfinance as yf

SUPABASE_URL = "https://oqkobptbvcazifpvjwfz.supabase.co"
SUPABASE_SERVICE_KEY = os.environ.get(
    "SUPABASE_SERVICE_KEY",
    "sb_secret_PkAEAOU2YO4YS-ELYpwS5w_SsVg2kqi"
)
HEADERS = {
    "apikey": SUPABASE_SERVICE_KEY,
    "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=minimal",
}

BATCH_SIZE = 50
INCREMENTAL = "--incremental" in sys.argv

def get_all_etf_symbols():
    """Fetch all ETF symbols from foreign_etfs table."""
    url = f"{SUPABASE_URL}/rest/v1/foreign_etfs?select=symbol&limit=2000"
    resp = requests.get(url, headers=HEADERS)
    if resp.status_code != 200:
        print(f"[ERROR] Failed to fetch ETFs: {resp.status_code} {resp.text}")
        return []
    data = resp.json()
    if isinstance(data, dict) and "message" in data:
        print(f"[ERROR] API error: {data}")
        return []
    symbols = [r["symbol"] for r in data]
    print(f"[INFO] Found {len(symbols)} ETFs total")
    return symbols

def get_existing_data():
    """Get existing price data grouped by symbol."""
    url = f"{SUPABASE_URL}/rest/v1/foreign_etf_prices?select=symbol,date&limit=10000"
    resp = requests.get(url, headers=HEADERS)
    if resp.status_code != 200:
        return {}
    data = resp.json()
    if not isinstance(data, list):
        return {}
    result = {}
    for row in data:
        sym = row["symbol"]
        if sym not in result:
            result[sym] = {"dates": set(), "count": 0}
        result[sym]["dates"].add(row["date"])
        result[sym]["count"] += 1
    return result

def upsert_prices(symbol: str, prices: list[dict]) -> int:
    """Upsert prices using ON CONFLICT (symbol, date)."""
    if not prices:
        return 0
    rows = [{"symbol": symbol, "date": p["date"], "close": p["close"]} for p in prices]
    # Prefer: resolution=merge-duplicates = ON CONFLICT DO UPDATE (upsert)
    upsert_headers = {**HEADERS, "Prefer": "resolution=merge-duplicates"}
    ins_resp = requests.post(
        f"{SUPABASE_URL}/rest/v1/foreign_etf_prices",
        headers=upsert_headers,
        json=rows
    )
    if ins_resp.status_code not in (200, 201):
        print(f"  [WARN] {symbol}: upsert failed {ins_resp.status_code}: {ins_resp.text[:100]}")
        return 0
    return len(rows)

def fetch_yf_prices(symbol: str, period: str = "1y") -> list[dict]:
    """Fetch historical daily close prices from Yahoo Finance."""
    try:
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period=period, auto_adjust=True)
        if hist.empty:
            return []
        records = []
        for dt, row in hist.iterrows():
            date_str = dt.strftime("%Y-%m-%d")
            close_val = row["Close"]
            # Skip NaN/Inf values
            if close_val != close_val or close_val == float('inf') or close_val == float('-inf'):
                continue
            close = float(close_val)
            records.append({"date": date_str, "close": close, "symbol": symbol})
        return records
    except Exception as e:
        print(f"  [ERROR] {symbol}: {e}")
        return []

def main():
    print(f"[CONFIG] incremental={INCREMENTAL}, batch_size={BATCH_SIZE}")

    symbols = get_all_etf_symbols()
    if not symbols:
        print("[ERROR] No ETFs found, exiting")
        return

    existing = get_existing_data()
    print(f"[INFO] Already have data for {len(existing)} symbols")
    for sym, info in sorted(existing.items()):
        print(f"  {sym}: {info['count']} rows ({min(info['dates'])} -> {max(info['dates'])})")

    # Determine which symbols need fetching
    if INCREMENTAL:
        # Only fetch symbols with < 30 rows
        needs_fetch = [s for s in symbols if s not in existing or existing[s]['count'] < 30]
        print(f"[INFO] Incremental: {len(needs_fetch)} ETFs need fetching (<30 rows)")
    else:
        # Full refresh: delete all and re-fetch everything
        needs_fetch = [s for s in symbols if s not in existing or existing[s]['count'] < 252]
        print(f"[INFO] Full refresh: {len(needs_fetch)} ETFs need fetching (<252 rows)")

    if not needs_fetch:
        print("[INFO] Nothing to fetch, exiting")
        return

    total_inserted = 0
    errors = 0
    print(f"[INFO] Starting backfill of {len(needs_fetch)} ETFs...")

    for i in range(0, len(needs_fetch), BATCH_SIZE):
        batch = needs_fetch[i:i+BATCH_SIZE]
        batch_num = i // BATCH_SIZE + 1
        total_batches = (len(needs_fetch) + BATCH_SIZE - 1) // BATCH_SIZE
        print(f"\n[Batch {batch_num}/{total_batches}] {len(batch)} ETFs...")

        for j, symbol in enumerate(batch):
            existing_count = existing.get(symbol, {}).get('count', 0)
            print(f"  [{j+1}/{len(batch)}] {symbol} ({existing_count} rows exist)...", end=" ", flush=True)

            prices = fetch_yf_prices(symbol)
            if prices:
                count = upsert_prices(symbol, prices)
                total_inserted += count
                print(f"→ {count} rows")
            else:
                print(f"→ no data")
                errors += 1

            time.sleep(0.3)  # Rate limit

        print(f"  Progress: {min(i+BATCH_SIZE, len(needs_fetch))}/{len(needs_fetch)}")

    print(f"\n[DONE] Inserted {total_inserted} price rows, {errors} ETFs had no data.")

if __name__ == "__main__":
    main()
