#!/opt/homebrew/bin/python3.11
"""
ETF Sparkline Backfill — Reliable upsert for foreign_etf_prices.

Fixes applied:
1. Removed broken get_existing_counts() that uses limit=100000 (wrong)
2. Removed fallback loop that caused 409 spam
3. Proper upsert with ON CONFLICT DO UPDATE (via merge-duplicates)
4. Per-symbol check: only skip if >= 252 rows (full year)
5. Proper logging to file + stdout

Run: python3.11 scripts/backfill_etf_sparkline.py
"""
import sys
import os
import time
import logging
from datetime import datetime

import requests

# Setup yfinance cache BEFORE importing yfinance
os.environ['YFINANCE_CACHE_DIR'] = '/tmp/yf_cache4'
os.environ['YF_DATAPATH'] = '/tmp/yf_cache4'
os.makedirs('/tmp/yf_cache4', exist_ok=True)

import yfinance as yf

# ── Config ──────────────────────────────────────────────────────────────────
SUPABASE_URL = "https://oqkobptbvcazifpvjwfz.supabase.co"
SUPABASE_KEY = os.environ.get(
    "SUPABASE_SERVICE_KEY",
    "sb_secret_PkAEAOU2YO4YS-ELYpwS5w_SsVg2kqi"
)

HEADERS_BASE = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
}
HEADERS_UPSERT = {
    **HEADERS_BASE,
    "Content-Type": "application/json",
    "Prefer": "resolution=merge-duplicates",
}

# How many trading days = "full year"
FULL_YEAR_ROWS = 252

# ── Logging ───────────────────────────────────────────────────────────────────
LOG_FILE = "scripts/backfill_sparkline.log"

# Reset log file on each run
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, mode="w", encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger(__name__)


# ── Helpers ──────────────────────────────────────────────────────────────────
def get_row_count(symbol: str) -> int:
    """Check how many rows exist for this symbol using Content-Range header."""
    resp = requests.get(
        f"{SUPABASE_URL}/rest/v1/foreign_etf_prices",
        headers={
            **HEADERS_BASE,
            "Range": "0-0",          # request only 1 row in body
            "Prefer": "count=exact",  # get total count in Content-Range header
        },
        params={"symbol": f"eq.{symbol}", "select": "date", "limit": 1},
        timeout=10,
    )
    # Content-Range: <start>-<end>/<total>
    cr = resp.headers.get("Content-Range", "")
    if "/" in cr:
        return int(cr.split("/")[1])
    return 0


def fetch_yf_prices(symbol: str) -> list[dict]:
    """Fetch 1-year daily close prices from Yahoo Finance."""
    try:
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period="1y", auto_adjust=True, back_adjust=True)
        if hist.empty:
            log.warning("%s: no data from yfinance", symbol)
            return []

        records = []
        for dt, row in hist.iterrows():
            close_val = row["Close"]
            if not (close_val and close_val == close_val
                    and close_val != float("inf") and close_val > 0):
                continue
            date_str = dt.strftime("%Y-%m-%d")
            records.append({
                "symbol": symbol,
                "date": date_str,
                "close": round(float(close_val), 4),
            })
        log.info("%s: fetched %d price records", symbol, len(records))
        return records

    except Exception as e:
        log.error("%s: yfinance error: %s", symbol, e)
        return []


def get_existing_dates(symbol: str) -> set[str]:
    """Get all existing dates for a symbol from DB. Returns a set of date strings."""
    resp = requests.get(
        f"{SUPABASE_URL}/rest/v1/foreign_etf_prices",
        headers=HEADERS_BASE,
        params={"symbol": f"eq.{symbol}", "select": "date", "limit": 1000},
        timeout=15,
    )
    if resp.status_code != 200:
        return set()
    data = resp.json()
    if isinstance(data, list):
        return {d["date"] for d in data}
    return set()


def upsert_prices(symbol: str, rows: list[dict]) -> tuple[int, int]:
    """
    Upsert rows: filter to only new dates first, then batch upsert.
    This avoids 409 conflicts entirely by only inserting rows that don't exist.
    Returns (upserted_count, error_count).
    """
    if not rows:
        return 0, 0

    # Get existing dates from DB
    existing = get_existing_dates(symbol)
    if not existing:
        # No existing data — insert all
        new_rows = rows
    else:
        # Filter out rows whose dates already exist
        new_rows = [r for r in rows if r["date"] not in existing]

    if not new_rows:
        return 0, 0

    resp = requests.post(
        f"{SUPABASE_URL}/rest/v1/foreign_etf_prices",
        headers=HEADERS_UPSERT,
        json=new_rows,
        timeout=30,
    )

    if resp.status_code in (200, 201):
        return len(new_rows), 0

    log.error(
        "%s: upsert failed HTTP %d: %s",
        symbol, resp.status_code, resp.text[:200]
    )
    return 0, len(new_rows)


# ── Main ──────────────────────────────────────────────────────────────────────
def get_all_etf_symbols() -> list[str]:
    """Fetch all ETF symbols from foreign_etfs table."""
    resp = requests.get(
        f"{SUPABASE_URL}/rest/v1/foreign_etfs?select=symbol&limit=2000",
        headers=HEADERS_BASE,
        timeout=30,
    )
    if resp.status_code != 200:
        log.error("Failed to fetch ETFs: %s", resp.text)
        return []
    data = resp.json()
    if isinstance(data, dict) and "message" in data:
        log.error("API error fetching ETFs: %s", data)
        return []
    symbols = [r["symbol"] for r in data]
    log.info("Found %d ETFs in foreign_etfs", len(symbols))
    return symbols


def main():
    start = datetime.now()
    log.info("=== ETF Sparkline Backfill started at %s ===", start.isoformat())
    log.info("Supabase: %s", SUPABASE_URL)

    symbols = get_all_etf_symbols()
    if not symbols:
        log.error("No ETFs found, exiting")
        return

    # Determine which need fetching — only skip if >= FULL_YEAR_ROWS rows
    to_fetch = []
    skip = []
    for sym in symbols:
        # Quick check: use count endpoint
        resp = requests.get(
            f"{SUPABASE_URL}/rest/v1/foreign_etf_prices",
            headers={**HEADERS_BASE, "Range": "0-0", "Prefer": "count=exact"},
            params={"symbol": f"eq.{sym}", "select": "date", "limit": 1},
            timeout=10,
        )
        cr = resp.headers.get("Content-Range", "")
        count = int(cr.split("/")[1]) if "/" in cr and cr.split("/")[1] != "*" else 0
        if count >= FULL_YEAR_ROWS:
            skip.append((sym, count))
        else:
            to_fetch.append((sym, count))

    log.info("Already complete (>=%d rows): %d ETFs", FULL_YEAR_ROWS, len(skip))
    if skip:
        for sym, cnt in sorted(skip)[:5]:
            log.info("  Already have: %s (%d rows)", sym, cnt)
        if len(skip) > 5:
            log.info("  ... and %d more", len(skip) - 5)

    log.info("Need to fetch: %d ETFs", len(to_fetch))
    if to_fetch:
        for sym, cnt in sorted(to_fetch)[:10]:
            log.info("  Will fetch: %s (%d existing rows)", sym, cnt)
        if len(to_fetch) > 10:
            log.info("  ... and %d more", len(to_fetch) - 10)

    if not to_fetch:
        log.info("All ETFs already have full data!")
        return

    total_inserted = 0
    total_errors = 0

    for idx, (symbol, existing_count) in enumerate(to_fetch, 1):
        log.info("[%d/%d] Processing %s (has %d rows)...",
                 idx, len(to_fetch), symbol, existing_count)

        prices = fetch_yf_prices(symbol)
        if not prices:
            total_errors += 1
            time.sleep(0.3)
            continue

        inserted, errors = upsert_prices(symbol, prices)
        total_inserted += inserted
        total_errors += errors

        log.info(
            "  %s: upserted=%d errors=%d (total: inserted=%d errors=%d)",
            symbol, inserted, errors, total_inserted, total_errors
        )

        time.sleep(0.4)  # be nice to yfinance

    elapsed = (datetime.now() - start).total_seconds()
    log.info("=== DONE in %.1fs ===", elapsed)
    log.info("Total upserted: %d, errors: %d", total_inserted, total_errors)


if __name__ == "__main__":
    main()
