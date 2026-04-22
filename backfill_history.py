#!/usr/bin/env python3
"""
Backfill Tefas history — 1 year of daily data.
Inserts immediately after each week chunk (no memory bloat).
~1 year = ~52 weeks × 3 fund types = 156 tasks
With 5 workers @ ~15s each ≈ 8-10 minutes total
"""
import sys
import time
import sqlite3
from pathlib import Path
from datetime import date, datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock

DB = Path(__file__).parent / "db" / "fonapp.db"

# === CONFIG ===
WEEKS = int(sys.argv[1]) if len(sys.argv) > 1 else 52
MAX_WORKERS = 5
SLEEP_BETWEEN_CALLS = 1  # seconds between API calls
# ==============

stats_lock = Lock()
total_fetched = 0
total_inserted = 0
completed = 0
errors = 0
last_report_time = time.time()

def get_fund_id(conn, code):
    r = conn.execute("SELECT id FROM tefas_funds WHERE tefas_code = ?", (code,)).fetchone()
    if r:
        return r[0]
    r = conn.execute("SELECT id FROM funds WHERE code = ? OR tefas_code = ?", (code, code)).fetchone()
    return r[0] if r else None

def fetch_and_insert_week(kind, start_str, end_str, conn):
    """Fetch 1 week, insert immediately. Returns (fetched_count, inserted_count)."""
    global total_fetched, total_inserted, completed, errors, last_report_time

    try:
        from tefas import Crawler
        tefas = Crawler()
        data = tefas.fetch(start=start_str, end=end_str, kind=kind)

        local_inserted = 0
        local_fetched = len(data)

        for _, row in data.iterrows():
            code = row.get("code")
            d = row.get("date")
            if not code or not d:
                continue

            fund_id = get_fund_id(conn, code)
            if not fund_id:
                continue

            try:
                conn.execute("""INSERT OR REPLACE INTO price_history
                    (fund_id, date, price, market_cap, number_of_shares, number_of_investors)
                    VALUES (?, ?, ?, ?, ?, ?)""",
                    (fund_id, d, row.get("price"), row.get("market_cap"),
                     row.get("number_of_shares"), row.get("number_of_investors")))
                local_inserted += 1
            except Exception:
                pass

        conn.commit()

        with stats_lock:
            total_fetched += local_fetched
            total_inserted += local_inserted
            completed += 1
            last_report_time = time.time()

        time.sleep(SLEEP_BETWEEN_CALLS)
        return local_fetched, local_inserted

    except Exception as e:
        with stats_lock:
            errors += 1
            completed += 1
        print(f"  ERROR {kind} {start_str}: {e}", flush=True)
        return 0, 0

def main():
    global completed, errors, total_fetched, total_inserted, last_report_time

    end_date = date.today()
    start_date = end_date - timedelta(weeks=WEEKS)

    print(f"Tefas {WEEKS}-Week Historical Backfill", flush=True)
    print(f"Period: {start_date} → {end_date}", flush=True)
    print(f"Workers: {MAX_WORKERS}, Sleep: {SLEEP_BETWEEN_CALLS}s\n", flush=True)

    # Build week chunks
    work_items = []
    cur = start_date
    while cur <= end_date:
        week_end = min(cur + timedelta(days=6), end_date)
        work_items.append((cur.strftime("%Y-%m-%d"), week_end.strftime("%Y-%m-%d")))
        cur = week_end + timedelta(days=1)

    tasks = []
    for kind in ["YAT", "EMK", "BYF"]:
        for s, e in work_items:
            tasks.append((kind, s, e))

    total_tasks = len(tasks)
    start_time = time.time()

    print(f"Tasks: {total_tasks} ({len(work_items)} weeks × 3 fund types)\n", flush=True)

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {
            executor.submit(fetch_and_insert_week, kind, s, e, sqlite3.connect(str(DB))): (kind, s, e)
            for kind, s, e in tasks
        }

        for fut in as_completed(futures):
            kind, s, e = futures[fut]
            try:
                fetched, inserted = fut.result()
                elapsed = time.time() - start_time
                rate = completed / elapsed if elapsed > 0 else 0
                eta_min = (total_tasks - completed) / rate / 60 if rate > 0 else 0

                if completed % 10 == 0 or completed == total_tasks:
                    print(f"[{completed:3d}/{total_tasks}] {kind} {s} | "
                          f"+{fetched} fetched, +{inserted} ins | "
                          f"total: {total_inserted:,} rows | "
                          f"ETA: {eta_min:.0f}min\n", flush=True)
            except Exception as e:
                errors += 1
                completed += 1

    # Calculate daily_change
    print("\n📊 Calculating daily changes...", flush=True)
    conn = sqlite3.connect(str(DB))
    c = conn.cursor()

    c.execute("""SELECT fund_id, date, price FROM price_history
                 WHERE price IS NOT NULL AND price > 0
                 ORDER BY fund_id, date""")
    rows = c.fetchall()

    prev_fund = None
    prev_price = None
    updates = 0

    for fund_id, d, price in rows:
        if fund_id == prev_fund and prev_price is not None:
            change = (price - prev_price) / prev_price * 100
            c.execute("UPDATE price_history SET daily_change = ? WHERE fund_id = ? AND date = ?",
                     (change, fund_id, d))
            updates += 1
        else:
            c.execute("UPDATE price_history SET daily_change = 0 WHERE fund_id = ? AND date = ?",
                     (fund_id, d))
            updates += 1
        prev_fund = fund_id
        prev_price = price

    conn.commit()

    c.execute("SELECT COUNT(*) FROM price_history")
    total_rows = c.fetchone()[0]
    c.execute("SELECT COUNT(DISTINCT date) FROM price_history")
    trading_days = c.fetchone()[0]
    c.execute("SELECT COUNT(DISTINCT fund_id) FROM price_history")
    funds_with_data = c.fetchone()[0]

    conn.close()

    elapsed_total = time.time() - start_time

    print(f"\n{'='*60}", flush=True)
    print(f"✅ Backfill complete!", flush=True)
    print(f"  Total time:     {elapsed_total/60:.1f} minutes", flush=True)
    print(f"  Price rows:    {total_rows:,}", flush=True)
    print(f"  Funds w/data:  {funds_with_data:,}", flush=True)
    print(f"  Trading days:  {trading_days}", flush=True)
    print(f"  Daily chg:     {updates:,}", flush=True)
    print(f"  Errors:        {errors}", flush=True)
    print(f"{'='*60}", flush=True)

if __name__ == "__main__":
    main()
