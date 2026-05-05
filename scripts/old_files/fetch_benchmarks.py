#!/usr/bin/env python3
"""
Fetch benchmark data (stocks, crypto, FX) from Yahoo Finance → Supabase benchmarks table.

Benchmarks: BIST100, SP500, NASDAQ, USD/TRY, GOLD, BTC/USD, ETH/USD

Usage: python scripts/fetch-benchmarks.py
"""

import yfinance as yf
import psycopg2
import concurrent.futures
import warnings
import json
from datetime import datetime

warnings.filterwarnings("ignore")

DB_URL = "postgresql://postgres:rzvfO6ub5F1W6hpR@db.oqkobptbvcazifpvjwfz.supabase.co:5432/postgres"

BENCHMARKS = [
    ("XU100.IS", "BIST100",  "BIST 100",    365),
    ("^GSPC",    "SP500",    "S&P 500",     730),
    ("^IXIC",    "NASDAQ",   "Nasdaq",      730),
    ("TRY=X",    "USDTRY",   "USD/TRY",     730),
    ("EURTRY=X", "EURTRY",   "EUR/TRY",     730),
    ("GC=F",     "GOLD",     "Altın",        730),
    ("BTC-USD",  "BTCUSD",   "Bitcoin",      730),
    ("ETH-USD",  "ETHUSD",   "Ethereum",     730),
]

# Symbols fetched in USD — will be converted to TL using USD/TRY rate
USD_BASED = {"SP500", "NASDAQ", "GOLD", "BTCUSD", "ETHUSD"}


def db():
    return psycopg2.connect(DB_URL)


def upsert_benchmark_rows(rows: list[tuple]):
    """Insert rows into benchmarks table."""
    if not rows:
        return
    conn = db()
    try:
        cur = conn.cursor()
        for i in range(0, len(rows), 500):
            chunk = rows[i:i+500]
            values = ", ".join(f"('{s}', '{d}', {p})" for s, d, p in chunk)
            cur.execute(
                f"INSERT INTO benchmarks (symbol, date, price) VALUES {values} "
                f"ON CONFLICT (symbol, date) DO UPDATE SET price = EXCLUDED.price"
            )
        conn.commit()
        cur.close()
    finally:
        conn.close()


def update_homepage_stats(benchmarks_data: dict):
    """Update homepage_stats.benchmarks_data with pre-processed benchmark summary."""
    json_val = json.dumps(benchmarks_data)
    conn = db()
    try:
        cur = conn.cursor()
        cur.execute(
            "UPDATE homepage_stats SET benchmarks_data = %s WHERE id = 1",
            (json_val,)
        )
        conn.commit()
        cur.close()
    finally:
        conn.close()


def process_benchmarks(symbol: str, rows: list):
    """Return {symbol: [{date, price}]} with base-normalized change for UI."""
    if not rows:
        return None
    sorted_rows = sorted(rows, key=lambda x: x[0])
    return {
        "data": [{"date": d, "price": p} for d, p in sorted_rows],
        "change": round(((sorted_rows[-1][1] - sorted_rows[0][1]) / sorted_rows[0][1]) * 100, 1),
    }


def fetch_symbol(args):
    """Fetch from Yahoo Finance, return list of (symbol, date, price)."""
    yf_sym, db_sym, label, days = args
    print(f"  {label} ({db_sym})...", end=" ", flush=True)
    try:
        ticker = yf.Ticker(yf_sym)
        hist = ticker.history(period=f"{days}d", auto_adjust=True, timeout=30)
        if hist.empty:
            print("⚠ no data")
            return (db_sym, [])
        rows = []
        for dt, row in hist.iterrows():
            price = float(row["Close"])
            if price > 0:
                rows.append((dt.strftime("%Y-%m-%d"), price))
        print(f"✓ {len(rows)} rows ({hist.index[0].strftime('%Y-%m-%d')} → {hist.index[-1].strftime('%Y-%m-%d')})")
        return (db_sym, rows)
    except Exception as e:
        print(f"✗ {e}")
        return (db_sym, [])


def main():
    t0 = datetime.now()
    print(f"\n{'='*60}")
    print(f"Benchmark Fetcher — {t0.strftime('%Y-%m-%d %H:%M')}")
    print(f"{'='*60}\n")

    # Fetch all symbols in parallel
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex:
        results = list(ex.map(fetch_symbol, BENCHMARKS))

    # Build dict for easy lookup
    results_dict = {db_sym: rows for db_sym, rows in results}

    # ── Upsert individual rows into benchmarks table (original currency) ───────
    all_rows = []
    for db_sym, rows in results:
        all_rows.extend([(db_sym, d, p) for d, p in rows])

    if all_rows:
        upsert_benchmark_rows(all_rows)
        print(f"\n  ✓ {len(all_rows)} rows upserted to benchmarks table")

    # ── Build benchmarks_data for homepage_stats (all in TL) ──────────────────
    # Build USD/TRY time series for historical conversion
    usd_try_series = {}  # date -> rate
    for d, p in results_dict.get("USDTRY", []):
        usd_try_series[d] = p

    if not usd_try_series:
        print("\n  ⚠ USD/TRY rate not available — skipping TL conversion!\n")

    def to_tl(db_sym, rows):
        """Convert USD-based rows to TL using each day's own USD/TRY rate."""
        if db_sym not in USD_BASED:
            return rows
        # Build date->rate dict with datetime keys for range queries
        usd_try_dt = {}
        for d, p in usd_try_series.items():
            usd_try_dt[datetime.strptime(d, "%Y-%m-%d")] = p

        converted = []
        for d, p in rows:
            d_dt = datetime.strptime(d, "%Y-%m-%d")
            rate = usd_try_series.get(d)
            if rate:
                converted.append((d, p * rate))
            else:
                # Fall back to nearest available rate
                nearest = min(usd_try_dt.keys(), key=lambda x: abs((x - d_dt).days), default=None)
                if nearest:
                    converted.append((d, p * usd_try_dt[nearest]))
        return converted

    benchmarks_data = {}
    for db_sym, rows in results:
        tl_rows = to_tl(db_sym, rows)
        processed = process_benchmarks(db_sym, tl_rows)
        if processed:
            benchmarks_data[db_sym] = processed

    if benchmarks_data:
        update_homepage_stats(benchmarks_data)
        print(f"  ✓ benchmarks_data updated in homepage_stats (TL)")
        if usd_try_series:
            latest = sorted(usd_try_series.items(), key=lambda x: x[0])[-1]
            print(f"  ✓ USD/TRY range used: {len(usd_try_series)} days ({latest[0]}: {latest[1]:.4f})")

    elapsed = (datetime.now() - t0).total_seconds()
    print(f"\n{'='*60}")
    print(f"✓ Done in {elapsed:.1f}s — {len(all_rows)} rows, {len(benchmarks_data)} symbols")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
