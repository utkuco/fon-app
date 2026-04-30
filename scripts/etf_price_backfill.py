#!/usr/bin/env python3
"""
ETF Price History Backfill Script (v2)
Fetches 2 years of daily price history from yfinance for all ETFs in foreign_etfs table
and populates the foreign_etf_prices table.

Key fix: For each ETF, first query existing dates in DB, then insert only NEW rows.
Avoids 409 Conflict errors by never trying to insert duplicate (symbol, date) pairs.

Usage:
    /opt/homebrew/bin/python3.11 scripts/etf_price_backfill.py
"""

import yfinance as yf
import pandas as pd
import urllib.request
import json
import time
import warnings
from datetime import date, datetime, timedelta

warnings.filterwarnings('ignore')

SUPABASE_URL = "https://oqkobptbvcazifpvjwfz.supabase.co"
SUPABASE_KEY = "sb_publishable__GPrsdfKRZCMZE8to916iQ_Izv9naG-"
HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=representation"
}
FETCH_BATCH = 10   # ETFs per yfinance download call
INSERT_BATCH = 100  # Rows per Supabase insert


def supabase_query(url: str) -> list:
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read())


def get_existing_dates(symbol: str) -> set[str]:
    """Get set of dates already in DB for this symbol."""
    url = f"{SUPABASE_URL}/rest/v1/foreign_etf_prices?symbol=eq.{symbol}&select=date"
    try:
        rows = supabase_query(url)
        return {r["date"] for r in rows if r.get("date")}
    except Exception:
        return set()


def upsert_rows(rows: list[dict]) -> int:
    """Insert rows to foreign_etf_prices. Returns count of rows returned."""
    if not rows:
        return 0
    url = f"{SUPABASE_URL}/rest/v1/foreign_etf_prices"
    payload = json.dumps(rows)
    req = urllib.request.Request(url, data=payload.encode(), method="POST", headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            body = resp.read()
            if body:
                result = json.loads(body)
                if isinstance(result, list):
                    return len(result)
            return len(rows)
    except urllib.error.HTTPError as e:
        body = e.read()
        if e.code == 409:
            # Some rows conflict — try one at a time
            count = 0
            for row in rows:
                try:
                    req2 = urllib.request.Request(url, data=json.dumps([row]).encode(), method="POST", headers=HEADERS)
                    with urllib.request.urlopen(req2, timeout=30) as resp2:
                        resp2.read()
                        count += 1
                except Exception:
                    pass
            return count
        else:
            print(f"    HTTP {e.code}: {body[:200]}")
            return 0
    except Exception as e:
        print(f"    Insert error: {e}")
        return 0


def fetch_prices_for_symbols(symbols: list[str], days: int = 730) -> dict[str, list[dict]]:
    """Download price history for a batch of symbols."""
    if not symbols:
        return {}
    start = date.today() - timedelta(days=days)
    try:
        df = yf.download(
            symbols, start=str(start), interval="1d",
            progress=False, auto_adjust=True, timeout=30
        )
        if df is None or df.empty:
            return {s: [] for s in symbols}

        if isinstance(df.columns, pd.MultiIndex):
            if "Close" not in df.columns.get_level_values(0):
                return {s: [] for s in symbols}
            close_df = df["Close"]
        else:
            close_df = df["Close"] if "Close" in df.columns else None
            if close_df is None:
                return {s: [] for s in symbols}

        close_df.index = close_df.index.tz_localize(None) if close_df.index.tz else close_df.index
        close_df.index = close_df.index.normalize()

        result = {}
        for sym in symbols:
            if sym not in close_df.columns:
                result[sym] = []
                continue
            sym_series = close_df[sym].dropna()
            rows = []
            for dt, val in sym_series.items():
                dt_str = dt.strftime("%Y-%m-%d") if hasattr(dt, "strftime") else str(dt)[:10]
                rows.append({"symbol": sym, "date": dt_str, "close": round(float(val), 4)})
            result[sym] = rows
        return result

    except Exception as e:
        print(f"    yfinance error for {symbols}: {e}")
        return {s: [] for s in symbols}


def main():
    start_time = datetime.now()
    print(f"\n[{start_time.strftime('%Y-%m-%d %H:%M:%S')}] ETF Price Backfill v2")
    print("=" * 60)

    # Get all ETF symbols
    print("\n[1/4] Fetching ETF list from DB...")
    url = f"{SUPABASE_URL}/rest/v1/foreign_etfs?select=symbol&is_active=eq.true&limit=5000"
    all_symbols = [r["symbol"] for r in supabase_query(url) if r.get("symbol")]
    print(f"  Total active ETFs: {len(all_symbols)}")

    if not all_symbols:
        return

    # Process ETFs in batches
    total_inserted = 0
    total_batches = (len(all_symbols) + FETCH_BATCH - 1) // FETCH_BATCH

    print(f"\n[2/4] Fetching & inserting prices ({FETCH_BATCH} ETFs per batch)...")

    for i in range(0, len(all_symbols), FETCH_BATCH):
        batch_syms = all_symbols[i:i+FETCH_BATCH]
        batch_num = (i // FETCH_BATCH) + 1

        # Download prices
        prices = fetch_prices_for_symbols(batch_syms, days=730)

        batch_inserted = 0
        for sym in batch_syms:
            rows = prices.get(sym, [])
            if not rows:
                print(f"  {batch_num}/{total_batches}: {sym}: NO DATA")
                continue

            # Get existing dates in DB
            existing_dates = get_existing_dates(sym)
            new_rows = [r for r in rows if r["date"] not in existing_dates]

            if not new_rows:
                print(f"  {batch_num}/{total_batches}: {sym}: already up to date ({len(rows)} pts)")
                continue

            # Insert in sub-batches
            inserted = 0
            for j in range(0, len(new_rows), INSERT_BATCH):
                chunk = new_rows[j:j+INSERT_BATCH]
                count = upsert_rows(chunk)
                inserted += count

            batch_inserted += inserted
            total_inserted += inserted
            print(f"  {batch_num}/{total_batches}: {sym}: {len(rows)} pts fetched, {len(new_rows)} new, {inserted} inserted")

        # Progress
        elapsed = (datetime.now() - start_time).total_seconds()
        progress = (i + FETCH_BATCH) / len(all_symbols)
        if elapsed > 10 and progress > 0:
            eta_sec = (elapsed / progress) - elapsed
            print(f"    → Batch done. Progress: {progress*100:.1f}% | Elapsed: {elapsed/60:.1f}min | ETA: {eta_sec/60:.1f}min")
        print()

        time.sleep(0.5)

    # Summary
    elapsed_total = (datetime.now() - start_time).total_seconds()
    print(f"[DONE] Runtime: {elapsed_total/60:.1f} minutes | Total inserted: {total_inserted}")

    # Quick verification
    print("\n[3/4] Verification...")
    sample = all_symbols[:20]
    total_pts = 0
    for sym in sample:
        dates = get_existing_dates(sym)
        total_pts += len(dates)
        print(f"  {sym}: {len(dates)} pts")
    print(f"  Sample avg: {total_pts/len(sample):.0f} pts/ETF")


if __name__ == "__main__":
    main()
