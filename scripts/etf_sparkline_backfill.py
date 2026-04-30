#!/usr/bin/env python3
"""
ETF Sparkline Backfill Script
Fetches 2-year daily price history from Yahoo Finance for all ETFs in foreign_etfs table,
then inserts into foreign_etf_prices via Supabase REST API.

Usage:
    ulimit -n 4096 && python3 scripts/etf_sparkline_backfill.py
"""

import os
import sys
import time
import json
import tempfile
import warnings
import urllib.parse
from datetime import datetime

warnings.filterwarnings("ignore")

import requests

# yfinance setup
import yfinance as yf
_cache_dir = tempfile.mkdtemp()
yf.set_tz_cache_location(_cache_dir)

# ── Config ──────────────────────────────────────────────────────────────────
SUPABASE_URL = os.environ.get(
    "NEXT_PUBLIC_SUPABASE_URL",
    "https://oqkobptbvcazifpvjwfz.supabase.co"
)
SUPABASE_KEY = os.environ.get(
    "SUPABASE_SERVICE_KEY",
    os.environ.get("NEXT_PUBLIC_SUPABASE_ANON_KEY", "")
)

BATCH_SIZE = 20          # ETFs per batch
FETCH_DELAY = 0.5        # seconds between ETF fetches
INSERT_CHUNK = 500       # rows per insert
PERIOD = "2y"
INTERVAL = "1d"
MAX_RETRIES = 2

REST_URL = f"{SUPABASE_URL}/rest/v1"
HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=minimal",
}

def rest_get(table: str, params: dict = None) -> list:
    """GET rows from a Supabase table."""
    url = f"{REST_URL}/{table}"
    if params:
        qs = "&".join(f"{urllib.parse.quote(k)}={urllib.parse.quote(str(v))}" for k, v in params.items())
        url = f"{url}?{qs}"
    resp = requests.get(url, headers=HEADERS, timeout=30)
    if resp.status_code == 416:  # Range not satisfiable (empty)
        return []
    if resp.status_code != 200:
        raise Exception(f"GET {url} → {resp.status_code}: {resp.text[:200]}")
    return resp.json()

def rest_post(table: str, rows: list[dict]) -> bool:
    """DELETE existing rows for each symbol, then INSERT new ones."""
    if not rows:
        return True
    # Group by symbol
    by_symbol = {}
    for row in rows:
        by_symbol.setdefault(row["symbol"], []).append(row)
    for symbol, symbol_rows in by_symbol.items():
        # Delete existing for this symbol
        requests.delete(
            f"{REST_URL}/{table}?symbol=eq.{urllib.parse.quote(symbol)}",
            headers=HEADERS,
            timeout=30,
        )
        # Insert all rows for this symbol
        for i in range(0, len(symbol_rows), INSERT_CHUNK):
            chunk = symbol_rows[i:i + INSERT_CHUNK]
            resp = requests.post(
                f"{REST_URL}/{table}",
                headers={**HEADERS, "Prefer": "return=minimal"},
                data=json.dumps(chunk),
                timeout=60,
            )
            if resp.status_code not in (200, 201):
                print(f"    insert error for {symbol}: {resp.status_code} {resp.text[:100]}")
    return True

def get_all_etf_symbols() -> list[str]:
    """Fetch all ETF symbols from foreign_etfs table."""
    rows = rest_get("foreign_etfs", {"select": "symbol", "order": "symbol"})
    return [r["symbol"] for r in rows]

def fetch_etf_prices(symbol: str) -> list[dict]:
    """Fetch 2y daily prices for one ETF. Returns list of row dicts."""
    for attempt in range(MAX_RETRIES):
        try:
            ticker = yf.Ticker(symbol)
            hist = ticker.history(period=PERIOD, interval=INTERVAL)
            if hist is None or hist.empty:
                return []
            rows = []
            for dt, row in hist.iterrows():
                rows.append({
                    "symbol": symbol,
                    "date": dt.strftime("%Y-%m-%d"),
                    "open": float(row["Open"]),
                    "high": float(row["High"]),
                    "low": float(row["Low"]),
                    "close": float(row["Close"]),
                    "volume": int(row["Volume"]),
                })
            return rows
        except Exception as e:
            if attempt == MAX_RETRIES - 1:
                print(f"    ✗ {symbol}: {e}")
                return []
            time.sleep(1 * (attempt + 1))
    return []

def main():
    print(f"\nETF Sparkline Backfill")
    print(f"  Supabase: {SUPABASE_URL}")
    print(f"  Period: {PERIOD} | Interval: {INTERVAL}")
    print(f"  Batch size: {BATCH_SIZE} | Fetch delay: {FETCH_DELAY}s")
    print()

    symbols = get_all_etf_symbols()
    print(f"Found {len(symbols)} ETFs in foreign_etfs table\n")

    total_rows = 0
    failed = []
    n_batches = (len(symbols) + BATCH_SIZE - 1) // BATCH_SIZE

    for batch_idx in range(n_batches):
        batch_start = batch_idx * BATCH_SIZE
        batch = symbols[batch_start:batch_start + BATCH_SIZE]
        batch_num = batch_idx + 1

        all_rows = []

        for symbol in batch:
            sys.stdout.write(f"  [{batch_num}/{n_batches}] {symbol}...")
            sys.stdout.flush()

            rows = fetch_etf_prices(symbol)
            if rows:
                all_rows.extend(rows)
                print(f" {len(rows)} rows ✓")
            else:
                failed.append(symbol)
                print(" empty ✗")

            time.sleep(FETCH_DELAY)

        if all_rows:
            rest_post("foreign_etf_prices", all_rows)
            total_rows += len(all_rows)
            print(f"  → Inserted {len(all_rows)} rows into foreign_etf_prices")

        print()

    print(f"{'='*60}")
    print(f"✅ Done!")
    print(f"   ETFs processed: {len(symbols) - len(failed)}/{len(symbols)}")
    print(f"   Failed ETFs: {len(failed)}")
    if failed:
        print(f"   Failed list: {', '.join(failed[:20])}" + (" ..." if len(failed) > 20 else ""))
    print(f"   Total price rows inserted: {total_rows:,}")
    print(f"\nSparklines will be computed by page.tsx on next request.")

if __name__ == "__main__":
    main()
