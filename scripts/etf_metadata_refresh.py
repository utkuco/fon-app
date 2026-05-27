#!/usr/bin/env python3
"""
etf_metadata_refresh.py — Refresh slow-changing foreign_etfs columns.

etf_daily_cron handles price/sparkline/returns daily, but never touches
AUM, expense ratio, dividend yield, fund family, name, or category. Those
fields hadn't been refreshed since 2026-05-07 — Yahoo had nulls for most
new ETFs and the wrong AUM for the rest.

Reads:  yfinance Ticker.info for every active foreign_etfs symbol.
Writes: foreign_etfs (name, fund_family, category, aum, expense_ratio,
        dividend_yield, three_yr_return, five_yr_return, beta, updated_at)

Schedule (launchd): Sundays 04:00 UTC (07:00 TR). Weekly is plenty —
these fields rarely change in a day.
Runtime: ~30-50 min for 1.2K ETFs.
"""

import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import psycopg2
import psycopg2.extras

# Quiet yfinance noise
os.environ.setdefault("YFINANCE_CACHE_DIR", "/tmp/yfinance_cache")
import warnings
warnings.filterwarnings("ignore")
import yfinance as yf

sys.path.insert(0, str(Path(__file__).parent))

from cron_shared import (
    SUPABASE_DB_URL,
    load_env,
    upsert_system_status,
    get_logger,
)

load_env()
LOG = get_logger("etf_metadata_refresh")

BATCH_SLEEP_SEC = 0.2  # Yahoo rate-limit cushion


def read_active_symbols() -> list[tuple[int, str]]:
    conn = psycopg2.connect(SUPABASE_DB_URL)
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, symbol FROM foreign_etfs WHERE is_active = true ORDER BY symbol")
            return list(cur.fetchall())
    finally:
        conn.close()


def fetch_info(symbol: str) -> Optional[dict]:
    """Yahoo info → only the fields we care about. Returns None on failure."""
    try:
        info = yf.Ticker(symbol).info
    except Exception as e:  # noqa: BLE001
        LOG(f"  {symbol}: yfinance error: {e}", "WARN")
        return None
    if not info or info.get("regularMarketPrice") is None:
        return None

    return {
        "name": info.get("longName") or info.get("shortName") or None,
        "fund_family": info.get("fundFamily") or None,
        "category": info.get("category") or None,
        # totalAssets comes back in USD; keep raw — UI converts via currency_rate
        "aum": info.get("totalAssets") if isinstance(info.get("totalAssets"), (int, float)) else None,
        "expense_ratio": info.get("netExpenseRatio") or info.get("annualReportExpenseRatio") or None,
        # Yahoo gives yield as ratio (0.018 = 1.8%); keep ratio
        "dividend_yield": info.get("yield") or info.get("trailingAnnualDividendYield") or None,
        "three_yr_return": info.get("threeYearAverageReturn") or None,
        "five_yr_return": info.get("fiveYearAverageReturn") or None,
        "beta": info.get("beta3Year") or info.get("beta") or None,
    }


def update_one(conn, etf_id: int, payload: dict) -> bool:
    """Single-row UPDATE — only writes non-null fields so we don't clobber
    existing values with a temporary yfinance gap."""
    sets = []
    values: list = []
    for col, val in payload.items():
        if val is not None:
            sets.append(f"{col} = %s")
            values.append(val)
    if not sets:
        return False
    sets.append("updated_at = %s")
    values.append(datetime.now(timezone.utc))
    values.append(etf_id)

    sql = f"UPDATE foreign_etfs SET {', '.join(sets)} WHERE id = %s"
    try:
        with conn.cursor() as cur:
            cur.execute(sql, values)
        conn.commit()
        return True
    except Exception as e:  # noqa: BLE001
        LOG(f"  UPDATE id={etf_id} failed: {e}", "WARN")
        conn.rollback()
        return False


def main() -> int:
    start = time.time()
    LOG("Starting etf_metadata_refresh")

    symbols = read_active_symbols()
    LOG(f"  active ETFs: {len(symbols)}")

    conn = psycopg2.connect(SUPABASE_DB_URL)
    updated = 0
    skipped = 0
    errored = 0

    try:
        for i, (etf_id, sym) in enumerate(symbols, 1):
            try:
                info = fetch_info(sym)
                if info is None:
                    skipped += 1
                    if i % 50 == 0:
                        LOG(f"  [{i}/{len(symbols)}] running … updated={updated} skipped={skipped} errored={errored}")
                    continue
                if update_one(conn, etf_id, info):
                    updated += 1
                else:
                    skipped += 1
            except Exception as e:  # noqa: BLE001
                errored += 1
                LOG(f"  {sym}: {e}", "WARN")
            if i % 50 == 0:
                LOG(f"  [{i}/{len(symbols)}] running … updated={updated} skipped={skipped} errored={errored}")
            time.sleep(BATCH_SLEEP_SEC)
    finally:
        conn.close()

    elapsed = round(time.time() - start, 1)
    LOG(f"Done in {elapsed}s — updated={updated} skipped={skipped} errored={errored}")

    upsert_system_status(
        "last_etf_metadata_refresh",
        datetime.now(timezone.utc).isoformat(),
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
