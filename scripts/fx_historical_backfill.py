#!/usr/bin/env python3
"""
FX Historical Backfill Script
Fetches historical USD/TRY (and EUR/TRY) exchange rates from Yahoo Finance
and upserts to Supabase exchange_rates table.

Usage: python3 scripts/fx_historical_backfill.py
Requires: pip install yfinance requests
"""
import os
import sys
import time
import tempfile
import requests

# --- Config ---
SUPABASE_URL = "https://oqkobptbvcazifpvjwfz.supabase.co"
SERVICE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im9xa29icHRidmNhemlmcHZqd2Z6Iiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc3NjQzMzI2NCwiZXhwIjoyMDkyMDA5MjY0fQ.MBDbMpmZ39zGlRxErTHnE7oQ7A3CapINpMggFaS9VMI"
HEADERS = {
    "apikey": SERVICE_KEY,
    "Authorization": f"Bearer {SERVICE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=minimal",
}

# How many days of history to fetch (200 days covers 6M ETF returns + buffer)
DAYS = 200


def supabase_upsert(table: str, rows: list[dict], conflict_cols: list[str]) -> bool:
    """
    Upsert rows to Supabase using UPDATE-then-INSERT approach.
    PostgREST On-Conflict only supports single columns, not composite keys.
    """
    updated = 0
    inserted = 0
    errors = 0

    for row in rows:
        # Build filter: eq.col.value for each conflict column
        filters = "&".join(f"eq.{k}.{row[k]}" for k in conflict_cols)
        patch_url = f"{SUPABASE_URL}/rest/v1/{table}?{filters}"

        # Try UPDATE first — Prefer return=representation to know if any rows matched
        patch_resp = requests.patch(
            patch_url,
            headers={**HEADERS, "Prefer": "return=representation"},
            json=row,
            timeout=15,
        )

        if patch_resp.status_code in (200, 204):
            result = patch_resp.json() if patch_resp.status_code == 200 else []
            if result and len(result) > 0:
                updated += 1
                continue  # row existed and was updated

        # No rows matched the filter → INSERT new row
        post_resp = requests.post(
            f"{SUPABASE_URL}/rest/v1/{table}",
            headers=HEADERS,
            json=row,
            timeout=15,
        )
        if post_resp.status_code in (200, 201, 204):
            inserted += 1
        else:
            errors += 1
            if errors <= 3:
                print(f"  INSERT ERROR: {post_resp.status_code} - {post_resp.text[:100]}")

    print(f"    updated={updated}, inserted={inserted}, errors={errors}")
    return errors == 0


def chunks(lst: list, size: int) -> list[list]:
    return [lst[i:i+size] for i in range(0, len(lst), size)]


def main():
    # Set yfinance cache dir BEFORE importing yfinance
    cache_dir = tempfile.gettempdir()
    os.environ["YFINANCE_CACHE_DIR"] = cache_dir

    try:
        import yfinance as yf
    except ImportError:
        print("ERROR: yfinance not installed. Run: pip install yfinance requests")
        sys.exit(1)

    yf.set_tz_cache_location(cache_dir)

    fx_tickers = [
        ("USD", "TRY", "TRY=X"),
        ("EUR", "TRY", "EURTRY=X"),
    ]

    all_rows = []

    for base, quote, ticker_str in fx_tickers:
        print(f"Fetching {base}/{quote} ({DAYS} days) from Yahoo Finance...")
        try:
            ticker = yf.Ticker(ticker_str)
            hist = ticker.history(period=f"{DAYS}d", auto_adjust=True)
        except Exception as e:
            print(f"  ERROR fetching {ticker_str}: {e}")
            continue

        if hist.empty:
            print(f"  WARNING: No data returned for {ticker_str}")
            continue

        for dt, row in hist.iterrows():
            date_str = dt.strftime("%Y-%m-%d")
            close = round(float(row["Close"]), 6)
            all_rows.append({
                "base": base,
                "quote": quote,
                "rate": close,
                "date": date_str,
            })

        print(f"  {len(hist)} rows: {hist.index[0].date()} → {hist.index[-1].date()}")

    if not all_rows:
        print("ERROR: No FX data fetched from Yahoo Finance")
        sys.exit(1)

    print(f"\nTotal FX rows to upsert: {len(all_rows)}")

    # Upsert in chunks
    CHUNK = 100
    total_ok = 0
    for chunk in chunks(all_rows, CHUNK):
        ok = supabase_upsert("exchange_rates", chunk, ["base", "date"])
        if ok:
            total_ok += len(chunk)
        time.sleep(0.3)

    print(f"\nDone: {total_ok}/{len(all_rows)} FX rows written to exchange_rates")


if __name__ == "__main__":
    main()
