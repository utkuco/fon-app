#!/usr/bin/env python3
"""
Backfill foreign_etfs.sparkline from foreign_etf_prices (389K rows).
Uses concurrent.futures ThreadPoolExecutor for parallel fetching.

Run:
    ulimit -n 4096 && python3 scripts/backfill_etf_sparkline_precomputed.py
"""

import os
import sys
import time
import json
import datetime
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed

# ── Config ──────────────────────────────────────────────────────────────────
SUPABASE_URL = "https://oqkobptbvcazifpvjwfz.supabase.co"
SUPABASE_KEY = "sb_secret_PkAEAOU2YO4YS-ELYpwS5w_SsVg2kqi"

HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    # PostgREST hard limit is 1000 rows regardless of limit param
}

W = 280
CHUNK = 1000
TOTAL_ROWS = 389798
MAX_WORKERS = 8


# ── Sparkline ────────────────────────────────────────────────────────────────

def compute_sparkline(rows, days=30):
    if not rows or len(rows) < 2:
        return None
    # ── Filter to last `days` calendar days ───────────────────────────────────
    cutoff = datetime.date.today() - datetime.timedelta(days=days)
    cutoff_str = cutoff.isoformat()
    recent = [r for r in rows if r["date"] >= cutoff_str]
    # Fallback: if recent has < 5 pts, use all data
    if len(recent) < 5:
        recent = rows
    if len(recent) < 2:
        return None
    sorted_rows = sorted(recent, key=lambda r: r["date"])
    closes = [r["close"] for r in sorted_rows if r["close"] is not None]
    if len(closes) < 2:
        return None
    mn = min(closes)
    mx = max(closes)
    rng = mx - mn or 1
    step = W / (len(closes) - 1)
    # y in [0, 40] — matches funds.sparkline (H=40 viewBox)
    # x in [0, 280] — matches funds.sparkline (W=280 viewBox)
    points = [
        [round(i * step, 4), round(((c - mn) / rng) * 40, 4)]
        for i, c in enumerate(closes)
    ]
    return {"points": points, "positive": closes[-1] >= closes[0]}


# ── HTTP helpers ─────────────────────────────────────────────────────────────

def fetch_prices_page(offset):
    """Fetch one page of price rows."""
    resp = requests.get(
        f"{SUPABASE_URL}/rest/v1/foreign_etf_prices",
        headers=HEADERS,
        params={
            "select": "symbol,date,close",
            "order": "date.asc",
            "limit": str(CHUNK),
            "offset": str(offset),
        },
        timeout=60,
    )
    resp.raise_for_status()
    return offset, resp.json()


def patch_sparkline(symbol, sparkline):
    """PATCH sparkline for one ETF."""
    url = f"{SUPABASE_URL}/rest/v1/foreign_etfs?symbol=eq.{symbol}"
    resp = requests.patch(url, headers=HEADERS, json={"sparkline": sparkline}, timeout=30)
    ok = resp.status_code in (200, 204)
    if not ok:
        print(f"    PATCH error {symbol}: {resp.status} {resp.text[:100]}")
    return symbol, ok


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("ETF Sparkline Backfill — Precomputed Column")
    print("=" * 60)

    # Step 1: Verify column
    print("\n[1/4] Verifying sparkline column...")
    try:
        resp = requests.get(
            f"{SUPABASE_URL}/rest/v1/foreign_etfs",
            headers=HEADERS,
            params={"select": "symbol,sparkline", "limit": "1"},
            timeout=15,
        )
        resp.raise_for_status()
        print("  ✓ Column exists")
    except Exception as e:
        print(f"  ✗ Error: {e}")
        print("  → ALTER TABLE foreign_etfs ADD COLUMN IF NOT EXISTS sparkline JSONB;")
        return

    # Step 2: Get ETF list
    print("\n[2/4] Fetching ETF symbols...")
    all_etfs = []
    for page in range(20):
        offset = page * 1000
        resp = requests.get(
            f"{SUPABASE_URL}/rest/v1/foreign_etfs",
            headers=HEADERS,
            params={
                "select": "symbol",
                "is_active": "eq.true",
                "order": "symbol.asc",
                "limit": "1000",
                "offset": str(offset),
            },
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        if not data:
            break
        all_etfs.extend([r["symbol"] for r in data])
        if len(data) < 1000:
            break
    print(f"  ✓ Total active ETFs: {len(all_etfs)}")

    # Step 3: Fetch ALL price rows concurrently
    print(f"\n[3/4] Fetching price history ({TOTAL_ROWS} rows, {MAX_WORKERS} workers)...")
    t0 = time.time()

    offsets = list(range(0, TOTAL_ROWS, CHUNK))
    prices_by_sym = {}
    fetched_pages = 0
    fetch_errors = 0

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
        futures = {ex.submit(fetch_prices_page, o): o for o in offsets}
        for future in as_completed(futures):
            try:
                offset, data = future.result()
                for row in data:
                    sym = row["symbol"]
                    if sym not in prices_by_sym:
                        prices_by_sym[sym] = []
                    prices_by_sym[sym].append({"date": row["date"], "close": row["close"]})
                fetched_pages += 1
                if fetched_pages % 20 == 0 or fetched_pages == len(offsets):
                    elapsed = time.time() - t0
                    rate = fetched_pages / elapsed if elapsed > 0 else 0
                    print(f"  [{elapsed:.0f}s] {fetched_pages}/{len(offsets)} pages, "
                          f"{len(prices_by_sym)} ETFs, {rate:.1f} pages/s")
            except Exception as e:
                fetch_errors += 1
                print(f"  Fetch error: {e}")

    elapsed = time.time() - t0
    total_rows = sum(len(v) for v in prices_by_sym.values())
    print(f"  ✓ {total_rows} rows for {len(prices_by_sym)} ETFs in {elapsed:.0f}s")
    if fetch_errors:
        print(f"  ⚠ {fetch_errors} fetch errors")

    # Step 4: Compute sparklines + patch
    print("\n[4/4] Computing sparklines and patching...")
    to_update = [s for s in all_etfs if s in prices_by_sym and len(prices_by_sym[s]) >= 5]
    skipped   = [s for s in all_etfs if s not in prices_by_sym or len(prices_by_sym[s]) < 5]
    print(f"  Will update: {len(to_update)} ETFs")
    print(f"  Skipped: {len(skipped)}")

    sparklines = {sym: compute_sparkline(prices_by_sym[sym]) for sym in to_update}

    t1 = time.time()
    updated = 0
    errors  = 0

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
        futures = {ex.submit(patch_sparkline, sym, sparklines[sym]): sym for sym in to_update}
        for future in as_completed(futures):
            sym, ok = future.result()
            if ok:
                updated += 1
            else:
                errors += 1
            if (updated + errors) % 100 == 0:
                print(f"  Progress: {updated + errors}/{len(to_update)}...")

    patch_elapsed = time.time() - t1
    print(f"\n✅ Done! {updated} updated, {errors} errors in {patch_elapsed:.0f}s")
    print(f"   {len(skipped)} skipped (no/insufficient data)")

    # Verification
    if updated > 0:
        print("\n[Verification] Sample sparklines:")
        for sym in to_update[:5]:
            resp = requests.get(
                f"{SUPABASE_URL}/rest/v1/foreign_etfs",
                headers=HEADERS,
                params={"select": "symbol,sparkline", "symbol": f"eq.{sym}"},
                timeout=15,
            )
            rows = resp.json()
            if rows and rows[0].get("sparkline"):
                sp = rows[0]["sparkline"]
                print(f"  ✓ {sym}: {len(sp['points'])} pts, positive={sp['positive']}")
            else:
                print(f"  ✗ {sym}: null")


if __name__ == "__main__":
    main()
