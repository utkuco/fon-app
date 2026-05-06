#!/usr/bin/env python3
"""
market_data.py — Birleşik market data script.

Bu script aşağıdaki eski scriptlerin hepsini birleştirir:
  - risk_free_rates.py  → USD/EUR/TRY faiz oranları → system_rates table
  - fetch_benchmarks.py → BIST100/SP500/NASDAQ/Altın/BTC/ETH → benchmarks table

Schedule (launchd): Hafta içi 07:00-07:30 UTC (10:00-10:30 TR)
Usage:             python3 scripts/market_data.py

Logic:
  1. Fetch USD 3-month T-bill from Yahoo ^IRX → system_rates
  2. Fetch benchmark prices from Yahoo Finance → benchmarks table
     (BIST100, SP500, NASDAQ, USD/TRY, EUR/TRY, Altın, BTC, ETH)
  3. Update system_status

Approximate runtime: ~2-3 min.
"""

import sys
import time
import json
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from cron_shared import (
    load_env,
    SUPABASE_URL,
    SUPABASE_KEY,
    SUPABASE_DB_URL,
    HEADERS,
    upsert_system_status,
    upsert_table,
    get_logger,
)

LOG = get_logger("market_data")

# ─── Yahoo Finance helpers ───────────────────────────────────────────────────

def fetch_yahoo_json(url: str, timeout: int = 15) -> dict:
    try:
        import urllib.request
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0",
            "Accept": "application/json",
        })
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read())
    except Exception as e:
        LOG(f"Yahoo fetch failed: {e}", "WARN")
        return {}


# ─── Risk-Free Rates ────────────────────────────────────────────────────────

def run_risk_free_rates() -> dict:
    """Fetch USD/EUR/TRY risk-free rates → system_rates table."""
    LOG("Fetching risk-free rates...")

    # USD: fetch from Yahoo ^IRX (3-month T-bill)
    ticker = "^IRX"
    period2 = int(time.time())
    period1 = period2 - 7 * 86400
    url = (
        f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
        f"?period1={period1}&period2={period2}&interval=1d&events=history"
    )
    data = fetch_yahoo_json(url)
    quotes = (
        data.get("chart", {})
        .get("result", [{}])[0]
        .get("indicators", {})
        .get("quote", [{}])[0]
        .get("close", [])
    )
    closes = [c for c in quotes if c is not None and c > 0]
    if closes:
        usd_rate = round(closes[-1] / 100, 6)  # e.g. 5.25% → 0.0525
        usd_source = f"yahoo:{ticker}"
        LOG(f"USD ^IRX = {closes[-1]}% → annualized {usd_rate}")
    else:
        usd_rate = 0.0
        usd_source = "fallback"

    # TRY: no reliable free API — use TCMB policy rate proxy
    try_rate = 0.45
    # EUR: no reliable free API — keep at 0
    eur_rate = 0.0

    rows = [
        {
            "currency": "TRY",
            "rate_annualized": try_rate,
            "source": "fallback:tcnb_proxy",
            "updated_at": datetime.utcnow().isoformat(),
        },
        {
            "currency": "USD",
            "rate_annualized": usd_rate,
            "source": usd_source,
            "updated_at": datetime.utcnow().isoformat(),
        },
        {
            "currency": "EUR",
            "rate_annualized": eur_rate,
            "source": "fallback",
            "updated_at": datetime.utcnow().isoformat(),
        },
    ]

    ok = upsert_table("system_rates", rows, conflict_col="currency")
    if ok:
        LOG("system_rates updated successfully")
    else:
        LOG("system_rates upsert FAILED", "ERROR")

    return {"usd_rate": usd_rate, "usd_source": usd_source, "try_rate": try_rate, "eur_rate": eur_rate}


# ─── Benchmarks ──────────────────────────────────────────────────────────────

BENCHMARKS = [
    ("XU100.IS", "BIST100",  "BIST 100",    365),
    ("^GSPC",    "SP500",    "S&P 500",     730),
    ("^IXIC",    "NASDAQ",   "Nasdaq",       730),
    ("TRY=X",    "USDTRY",   "USD/TRY",      730),
    ("EURTRY=X", "EURTRY",   "EUR/TRY",      730),
    ("GC=F",     "GOLD",     "Altın",        730),
    ("BTC-USD",  "BTCUSD",   "Bitcoin",      730),
    ("ETH-USD",  "ETHUSD",   "Ethereum",     730),
]

USD_BASED = {"SP500", "NASDAQ", "GOLD", "BTCUSD", "ETHUSD"}


def run_benchmarks() -> int:
    """Fetch benchmark data from Yahoo Finance → benchmarks table. Returns total rows."""
    LOG("Fetching benchmarks...")

    import yfinance as yf
    import concurrent.futures
    __import__("warnings").filterwarnings("ignore")

    if not SUPABASE_DB_URL:
        LOG("SUPABASE_DB_URL not set — cannot write benchmarks", "ERROR")
        return 0

    try:
        import psycopg2
    except ImportError:
        LOG("psycopg2 not installed", "ERROR")
        return 0

    def fetch_benchmark(sym: str, name: str, days: int) -> list[tuple]:
        try:
            ticker = yf.Ticker(sym)
            hist = ticker.history(period=f"{days}d", auto_adjust=True)
            if hist.empty:
                LOG(f"Benchmark {name}: no data", "WARN")
                return []
            rows = []
            for dt, row in hist.iterrows():
                d = dt.strftime("%Y-%m-%d")
                p = round(float(row["Close"]), 4)
                rows.append((name, d, p))
            LOG(f"Benchmark {name}: {len(rows)} prices")
            return rows
        except Exception as e:
            LOG(f"Benchmark {name} failed: {e}", "WARN")
            return []

    all_rows: list[tuple] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex:
        futures = {ex.submit(fetch_benchmark, sym, name, days): (sym, name)
                   for sym, name, label, days in BENCHMARKS}
        for future in concurrent.futures.as_completed(futures):
            result = future.result()
            all_rows.extend(result)

    if not all_rows:
        LOG("No benchmark data fetched", "WARN")
        return 0

    # Write to benchmarks table using psycopg2 (more reliable for bulk insert)
    conn = psycopg2.connect(SUPABASE_DB_URL)
    try:
        cur = conn.cursor()
        for i in range(0, len(all_rows), 500):
            chunk = all_rows[i:i+500]
            values = ", ".join(f"('{s}', '{d}', {p})" for s, d, p in chunk)
            cur.execute(
                f"INSERT INTO benchmarks (symbol, date, price) VALUES {values} "
                f"ON CONFLICT (symbol, date) DO UPDATE SET price = EXCLUDED.price"
            )
        conn.commit()
        cur.close()
        LOG(f"Benchmarks: {len(all_rows)} rows written")
        return len(all_rows)
    finally:
        conn.close()


# ─── Main ────────────────────────────────────────────────────────────────────

def main():
    load_env()
    LOG("Starting market_data")
    t0 = time.time()

    # 1. Risk-free rates
    rates = run_risk_free_rates()

    # 2. Benchmarks
    bm_count = run_benchmarks()

    elapsed = round(time.time() - t0, 1)
    upsert_system_status(
        "last_market_data",
        datetime.utcnow().isoformat(),
        "success",
        f"USD={rates['usd_rate']:.4f}, benchmarks={bm_count} rows, elapsed={elapsed}s",
    )
    LOG(f"Done in {elapsed}s")


if __name__ == "__main__":
    main()
