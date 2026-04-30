#!/usr/bin/env python3
"""
fetch_etf_prices_yfinance.py
────────────────────────────
Her gün çalışarak yfinance'dan ETF fiyat verilerini çeker ve
`foreign_etf_prices` tablosuna UPSERT eder.

Run: python3 scripts/fetch_etf_prices_yfinance.py

Cron schedule önerisi: her gün 09:05 TR (piyasalar kapandıktan sonra)
"""
from __future__ import annotations

import os
import sys
import time
import json
import datetime
import requests
import yfinance as yf
from concurrent.futures import ThreadPoolExecutor, as_completed

# ── Paths ──────────────────────────────────────────────────────────────────────
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

SUPABASE_URL = "https://oqkobptbvcazifpvjwfz.supabase.co"
SUPABASE_KEY = os.environ.get(
    "SUPABASE_SERVICE_ROLE_KEY",
    "sb_secret_PkAEAOU2YO4YS-ELYpwS5w_SsVg2kqi",
)
HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=minimal",
}

BATCH_SIZE = 50          # yfinance batch size
DAYS_HISTORY = 35        # fetch last 35 days to ensure 30-day sparkline
MAX_WORKERS = 10         # concurrent yfinance fetches


def get_etf_symbols() -> list[str]:
    """Supabase'den tüm ETF symbol listesini alır."""
    resp = requests.get(
        f"{SUPABASE_URL}/rest/v1/foreign_etfs",
        headers=HEADERS,
        params={"select": "symbol", "order": "symbol.asc"},
        timeout=30,
    )
    resp.raise_for_status()
    return [r["symbol"] for r in resp.json()]


def upsert_price_rows(symbol: str, rows: list[dict]) -> int:
    """foreign_etf_prices tablosuna UPSERT yapar. Inserted/updated row sayısını döner."""
    if not rows:
        return 0
    payload = [{"symbol": symbol, "date": r["date"], "close": r["close"]} for r in rows]
    # Use PUT to upsert: match on (symbol, date) — RLS bypass via service key
    resp = requests.post(
        f"{SUPABASE_URL}/rest/v1/foreign_etf_prices",
        headers={**HEADERS, "Prefer": "resolution=merge-duplicates"},
        json=payload,
        timeout=30,
    )
    if resp.status_code not in (200, 201):
        print(f"  [!] {symbol} upsert error: {resp.status_code} {resp.text[:100]}")
        return 0
    return len(rows)


def fetch_etf_price(symbol: str) -> list[dict]:
    """
    yfinance'dan tek ETF'in son `DAYS_HISTORY` günlük kapanış fiyatlarını alır.
    Yalnızca market günlerini (Mon-Fri) döner.
    """
    try:
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period=f"{DAYS_HISTORY}d", auto_adjust=True)
        if hist.empty:
            return []
        rows = []
        for dt, row in hist.iterrows():
            # yfinance timezone-aware datetime → date string
            date_str = dt.strftime("%Y-%m-%d")
            close = float(row["Close"])
            rows.append({"date": date_str, "close": close})
        return rows
    except Exception as exc:
        print(f"  [!] {symbol} fetch error: {exc}")
        return []


def process_batch(symbols: list[str]) -> dict[str, int]:
    """Bir batch ETF için parallel fetch + upsert yapar."""
    results = {}
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
        future_to_sym = {ex.submit(fetch_etf_price, s): s for s in symbols}
        for future in as_completed(future_to_sym):
            symbol = future_to_sym[future]
            try:
                rows = future.result()
                n = upsert_price_rows(symbol, rows)
                results[symbol] = n
                if n > 0:
                    print(f"  ✓ {symbol}: {n} rows upserted")
                else:
                    print(f"  – {symbol}: no data")
            except Exception as exc:
                print(f"  [!] {symbol} exception: {exc}")
                results[symbol] = 0
    return results


def main():
    print(f"\n{'='*60}")
    print(f"ETF Price Fetcher  |  {datetime.date.today().isoformat()}")
    print(f"{'='*60}\n")

    # 1. Get all ETF symbols
    print("[1/3] Fetching ETF symbol list from Supabase...")
    symbols = get_etf_symbols()
    print(f"    → {len(symbols)} ETFs found\n")

    # 2. Batch process
    total_upserted = 0
    total_symbols = len(symbols)
    today_str = datetime.date.today().isoformat()

    print(f"[2/3] Fetching prices from yfinance (batch={BATCH_SIZE})...")
    for i in range(0, total_symbols, BATCH_SIZE):
        batch = symbols[i:i + BATCH_SIZE]
        batch_num = i // BATCH_SIZE + 1
        total_batches = (total_symbols + BATCH_SIZE - 1) // BATCH_SIZE
        print(f"\n  Batch {batch_num}/{total_batches} ({len(batch)} ETFs)...")
        results = process_batch(batch)
        batch_ok = sum(1 for v in results.values() if v > 0)
        total_upserted += sum(results.values())
        print(f"  → {batch_ok}/{len(batch)} ETFs updated ({sum(results.values())} rows)")

    print(f"\n[3/3] Done!")
    print(f"    Total rows upserted: {total_upserted}")
    print(f"    Total ETFs:          {total_symbols}")
    print(f"    Date fetched:        {today_str}\n")

    return total_upserted


if __name__ == "__main__":
    ok = main()
    sys.exit(0 if ok > 0 else 1)
