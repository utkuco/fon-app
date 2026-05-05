#!/usr/bin/env python3
"""
etf_returns.py — Compute ETF period returns in TRY.

Schedule (launchd):  Mon-Fri 17:30 UTC = 20:30 TR
Usage:               python3 scripts/etf_returns.py

Logic (from etf-returns-cron/route.ts):
  1. Fetch all ETF metadata (id, symbol)
  2. Fetch price data for last 6 months using direct Postgres (psycopg2)
  3. For each ETF: compute 1w/1m/3m/6m returns vs latest price
  4. Update foreign_etfs table with one_week/month/3month/sixmonth_return_try

Data format: returns are stored as RATIO (e.g. 0.059 = 5.9%), NOT percentage.
"""

import sys
import math
import time
import bisect
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from cron_shared import (
    load_env, SUPABASE_URL, SUPABASE_KEY, SUPABASE_DB_URL, HEADERS,
    upsert_system_status, query_table, get_logger,
    rest_patch,
)
import urllib.request
import json

LOG = get_logger("etf_returns")

# ─── Postgres helpers ────────────────────────────────────────────────────────

def fetch_prices_pg(date_from: str, date_to: str) -> list[dict]:
    """Fetch price rows using direct Postgres connection (psycopg2)."""
    if not SUPABASE_DB_URL:
        LOG("SUPABASE_DB_URL not set — falling back to REST", "WARN")
        return []

    try:
        import psycopg2
    except ImportError:
        LOG("psycopg2 not installed", "WARN")
        return []

    try:
        conn = psycopg2.connect(SUPABASE_DB_URL)
        cur = conn.cursor()
        cur.execute(
            "SELECT symbol, date::text, close FROM foreign_etf_prices "
            "WHERE date >= %s AND date <= %s ORDER BY symbol, date",
            (date_from, date_to),
        )
        rows = [{"symbol": r[0], "date": r[1], "close": float(r[2])} for r in cur.fetchall()]
        cur.close()
        conn.close()
        LOG(f"Postgres fetched {len(rows)} price rows")
        return rows
    except Exception as e:
        LOG(f"Postgres error: {e}", "ERROR")
        return []


def fetch_prices_rest(date_from: str, date_to: str) -> list[dict]:
    """Fallback: fetch price rows using Supabase REST API (paginated)."""
    rows = []
    offset = 0
    page_size = 1000
    while True:
        url = (
            f"{SUPABASE_URL}/rest/v1/foreign_etf_prices"
            f"?date=gte.{date_from}&date=lte.{date_to}"
            f"&select=symbol,date,close&order=symbol,date&offset={offset}&limit={page_size}"
        )
        batch = []
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=60) as resp:
                batch = json.loads(resp.read())
        except Exception as e:
            LOG(f"REST fetch error at offset {offset}: {e}", "WARN")
            break

        if not batch:
            break
        rows.extend([{"symbol": r["symbol"], "date": r["date"], "close": float(r["close"])} for r in batch])
        if len(batch) < page_size:
            break
        offset += page_size
    LOG(f"REST fetched {len(rows)} price rows")
    return rows


# ─── Binary search price lookup ──────────────────────────────────────────────

def find_closest_price_on_or_before(
    sorted_prices: list[dict],  # [{"date": "YYYY-MM-DD", "close": float}], sorted ASC
    target_date: str,
) -> tuple[float | None, int]:
    """
    Binary search for the closest price on or before target_date.
    Returns (price, days_diff). days_diff = target - actual date diff in days.
    """
    if not sorted_prices:
        return None, float("inf")

    dates = [p["date"] for p in sorted_prices]
    target_ms = datetime.strptime(target_date, "%Y-%m-%d").timestamp()

    # Binary search: rightmost date <= target
    lo, hi = 0, len(dates) - 1
    best_idx = -1
    while lo <= hi:
        mid = (lo + hi) // 2
        d_ms = datetime.strptime(dates[mid], "%Y-%m-%d").timestamp()
        if d_ms <= target_ms:
            best_idx = mid
            lo = mid + 1
        else:
            hi = mid - 1

    if best_idx == -1:
        return None, float("inf")

    days_diff = round(
        (datetime.strptime(target_date, "%Y-%m-%d") - datetime.strptime(dates[best_idx], "%Y-%m-%d")).days
    )
    return sorted_prices[best_idx]["close"], days_diff


# ─── Main ────────────────────────────────────────────────────────────────────

def main():
    load_env()
    LOG("Starting etf_returns")
    t0 = time.time()

    # ── 1. Determine date range ─────────────────────────────────────────────
    # Try to get latest FX date from exchange_rates table
    fx_rows = query_table("exchange_rates", "date", order="date.desc", limit=1)
    if fx_rows:
        latest_fx_date = fx_rows[0]["date"]
    else:
        latest_fx_date = datetime.utcnow().strftime("%Y-%m-%d")

    today = datetime.strptime(latest_fx_date, "%Y-%m-%d")
    date_6m = today - timedelta(days=182)  # 6 months ≈ 182 days
    date_3m = today - timedelta(days=90)
    date_1m = today - timedelta(days=30)
    date_1w = today - timedelta(days=7)

    today_str = today.strftime("%Y-%m-%d")
    date_6m_str = date_6m.strftime("%Y-%m-%d")
    date_3m_str = date_3m.strftime("%Y-%m-%d")
    date_1m_str = date_1m.strftime("%Y-%m-%d")
    date_1w_str = date_1w.strftime("%Y-%m-%d")

    LOG(f"Dates: today={today_str}, 1w={date_1w_str}, 1m={date_1m_str}, 3m={date_3m_str}, 6m={date_6m_str}")

    # ── 2. Fetch all ETF metadata ───────────────────────────────────────────
    etfs = query_table("foreign_etfs", "id,symbol", limit=5000)
    LOG(f"Total ETFs: {len(etfs)}")

    # ── 3. Fetch price data ─────────────────────────────────────────────────
    prices = fetch_prices_pg(date_6m_str, today_str)
    if not prices:
        prices = fetch_prices_rest(date_6m_str, today_str)

    if not prices:
        LOG("No price data fetched — exiting", "WARN")
        return

    # ── 4. Build symbol → sorted prices map ────────────────────────────────
    price_map: dict[str, list[dict]] = {}
    for row in prices:
        sym = row["symbol"]
        if sym not in price_map:
            price_map[sym] = []
        price_map[sym].append({"date": row["date"], "close": row["close"]})

    # Sort each symbol's prices by date ASC
    for sym in price_map:
        price_map[sym].sort(key=lambda x: x["date"])

    LOG(f"Price map built for {len(price_map)} symbols")

    # ── 5. Compute returns ─────────────────────────────────────────────────
    updates: list[dict] = []
    processed = 0
    skipped = 0

    for etf in etfs:
        sym = etf["symbol"]
        row_id = etf["id"]
        prices_sym = price_map.get(sym, [])
        if len(prices_sym) < 15:
            skipped += 1
            continue

        today_price, today_diff = find_closest_price_on_or_before(prices_sym, today_str)
        if today_price is None:
            skipped += 1
            continue

        p1w, d1w = find_closest_price_on_or_before(prices_sym, date_1w_str)
        p1m, d1m = find_closest_price_on_or_before(prices_sym, date_1m_str)
        p3m, d3m = find_closest_price_on_or_before(prices_sym, date_3m_str)
        p6m, d6m = find_closest_price_on_or_before(prices_sym, date_6m_str)

        # Apply tolerance
        price_1w = p1w if d1w <= 7 else None
        price_1m = p1m if d1m <= 30 else None
        price_3m = p3m if d3m <= 30 else None
        price_6m = p6m if d6m <= 45 else None

        def pct(latest, baseline):
            if latest is None or baseline is None or baseline == 0:
                return None
            r = latest / baseline - 1
            return r if math.isfinite(r) else None

        r1w = pct(today_price, price_1w)
        r1m = pct(today_price, price_1m)
        r3m = pct(today_price, price_3m)
        r6m = pct(today_price, price_6m)

        # Outlier rejection: ±200%
        MAX_ABS = 2.0
        valid = lambda r: r is not None and abs(r) <= MAX_ABS

        updates.append({
            "id": row_id,
            "one_week_return_try": round(r1w, 6) if valid(r1w) else None,
            "one_month_return_try": round(r1m, 6) if valid(r1m) else None,
            "three_month_return_try": round(r3m, 6) if valid(r3m) else None,
            "six_month_return_try": round(r6m, 6) if valid(r6m) else None,
        })
        processed += 1

    LOG(f"Computed: {processed} ETFs, {skipped} skipped")

    # ── 6. Batch update foreign_etfs ───────────────────────────────────────
    updated = 0
    for row in updates:
        row_id = row.pop("id")
        patch_data = {k: v for k, v in row.items() if v is not None}
        if not patch_data:
            continue
        ok = rest_patch(
            f"{SUPABASE_URL}/rest/v1/foreign_etfs?id=eq.{row_id}",
            patch_data,
        )
        if ok:
            updated += 1

    LOG(f"Updated: {updated}/{len(updates)} ETFs")

    elapsed = round(time.time() - t0, 1)
    upsert_system_status(
        "last_etf_returns_cron",
        datetime.utcnow().isoformat(),
        "success",
        f"{updated}/{processed} ETFs in {elapsed}s",
    )
    LOG(f"Done in {elapsed}s")


if __name__ == "__main__":
    main()
