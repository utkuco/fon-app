#!/usr/bin/env python3
"""
ETF Price Backfill — fetches 2 years of daily prices for ALL 1000 ETFs in foreign_etfs table.
Saves to foreign_etf_prices table in Supabase.

Usage:
    python3 etf_price_backfill.py        # Full backfill
    python3 etf_price_backfill.py --dry-run  # Test with 10 ETFs
"""

import yfinance as yf
import pandas as pd
import urllib.request
import json
import time
import warnings
from datetime import date, datetime, timedelta
from typing import Optional

warnings.filterwarnings('ignore')

SUPABASE_URL = "https://oqkobptbvcazifpvjwfz.supabase.co"
SUPABASE_KEY = "sb_publishable__GPrsdfKRZCMZE8to916iQ_Izv9naG-"
HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=representation"
}


def supabase_query(table: str, select: str, filters: str = "") -> list:
    import urllib.parse
    params = [("select", select)]
    if filters:
        for f in filters.split("&"):
            if "=" in f:
                k, v = f.split("=", 1)
                params.append((k, v))
    encoded = urllib.parse.urlencode(params)
    url = f"{SUPABASE_URL}/rest/v1/{table}?{encoded}"
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read())


def supabase_delete_and_insert(rows: list[dict]) -> bool:
    """Delete existing rows for each symbol/date combo, then insert fresh data."""
    if not rows:
        return True
    # Group by symbol for efficient deletes
    from collections import defaultdict
    by_symbol = defaultdict(list)
    for row in rows:
        by_symbol[row["symbol"]].append(row["date"])
    
    deleted = 0
    for sym, dates in by_symbol.items():
        # Delete existing rows for this symbol (we're doing full refresh)
        del_url = f"{SUPABASE_URL}/rest/v1/foreign_etf_prices?symbol=eq.{sym}"
        del_req = urllib.request.Request(del_url, method="DELETE", headers=HEADERS)
        try:
            with urllib.request.urlopen(del_req, timeout=60) as resp:
                deleted += resp.read().count(b"id")
        except Exception as e:
            print(f"    Delete error for {sym}: {e}")
    
    # Now insert all rows fresh in batches of 4000
    BATCH = 4000
    total = len(rows)
    inserted = 0
    for i in range(0, total, BATCH):
        batch = rows[i:i+BATCH]
        url = f"{SUPABASE_URL}/rest/v1/foreign_etf_prices"
        payload = json.dumps(batch)
        req = urllib.request.Request(
            url, data=payload.encode(), method="POST",
            headers={**HEADERS}
        )
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                body = resp.read()
                result = json.loads(body) if body else []
                count = len(result) if isinstance(result, list) else BATCH
                inserted += count
                print(f"    → batch {i//BATCH + 1}: {count} rows (total: {inserted}/{total})")
        except Exception as e:
            print(f"    → INSERT ERROR at batch {i//BATCH + 1}: {e}")
    return inserted


def get_all_etf_symbols(dry_run: bool = False) -> list[str]:
    """Get all ETF symbols from foreign_etfs table."""
    etfs = supabase_query("foreign_etfs", "symbol", "limit=5000")
    symbols = [e["symbol"] for e in etfs if e.get("symbol")]
    print(f"  Total ETFs in DB: {len(symbols)}")
    return symbols


def download_batch_prices(symbols: list[str], period: str = "2y") -> dict[str, pd.Series]:
    """Download price series for multiple symbols using yfinance batch."""
    result = {}
    BATCH = 50
    for i in range(0, len(symbols), BATCH):
        batch_syms = symbols[i:i+BATCH]
        batch_label = f"{batch_syms[0]}...{batch_syms[-1]}" if len(batch_syms) > 1 else batch_syms[0]
        print(f"    Downloading {batch_label} ({i+1}/{len(symbols)})...")
        try:
            df = yf.download(
                " ".join(batch_syms),
                period=period,
                interval="1d",
                progress=False,
                auto_adjust=True,
                timeout=30
            )
            if df is None or df.empty:
                print(f"      No data for {batch_label}")
                time.sleep(2)
                continue
            if isinstance(df.columns, pd.MultiIndex):
                # Flatten (Close, AGG) -> AGG for that column
                df.columns = [c[1] if isinstance(c, tuple) else c for c in df.columns]
            for sym in batch_syms:
                if sym in df.columns:
                    col = df[sym].dropna()
                    if not col.empty:
                        result[sym] = col
        except Exception as e:
            print(f"      Batch error at {batch_label}: {e}")
        time.sleep(1)  # Be gentle with rate limits
    return result


def prices_to_rows(price_data: dict[str, pd.Series]) -> list[dict]:
    """Convert price series dict to rows for foreign_etf_prices table."""
    rows = []
    for sym, series in price_data.items():
        if series is None or series.empty:
            continue
        for dt_idx in series.index:
            d = str(dt_idx.date()) if hasattr(dt_idx, "date") else str(dt_idx)[:10]
            cv = series.loc[dt_idx]
            # Handle both scalar and array (in case of duplicate index entries)
            if hasattr(cv, 'item'):
                try:
                    cv = cv.item()
                except ValueError:
                    cv = float(cv.iloc[0]) if hasattr(cv, 'iloc') else float(cv)
            if cv is not None and not pd.isna(cv):
                rows.append({
                    "symbol": sym,
                    "date": d,
                    "close": round(float(cv), 4)
                })
    return rows


def main():
    dry_run = "--dry-run" in __import__("sys").argv

    print(f"\n[{datetime.now().strftime('%H:%M:%S')}] ETF Price Backfill")
    print("=" * 60)
    print(f"  Mode: DRY RUN" if dry_run else "  Mode: LIVE")

    # Get all symbols
    print("\n[1/2] Fetching ETF list from Supabase...")
    symbols = get_all_etf_symbols()
    if dry_run:
        symbols = symbols[:10]
        print(f"  Dry run: only {len(symbols)} symbols")

    # Download prices
    print(f"\n[2/2] Downloading 2-year price history for {len(symbols)} ETFs...")
    price_data = download_batch_prices(symbols, "2y")
    print(f"  Got price data for {len(price_data)} ETFs")

    if not price_data:
        print("  ERROR: No price data downloaded!")
        return

    # Convert to rows
    rows = prices_to_rows(price_data)
    print(f"  Total price rows: {len(rows)}")

    if dry_run:
        print(f"  Dry run — skipping Supabase upsert")
        print(f"  Would insert {len(rows)} rows")
        return

    # Save to Supabase (delete existing + insert fresh)
    print("\n  Saving to Supabase (delete + insert)...")
    ok = supabase_delete_and_insert(rows)
    if not ok:
        print("  FAILED to save data")

    print(f"\n[{datetime.now().strftime('%H:%M:%S')}] DONE!")
    print(f"  ETFs processed: {len(price_data)}")
    print(f"  Total rows: {len(rows)}")


if __name__ == "__main__":
    main()
