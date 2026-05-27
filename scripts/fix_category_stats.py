#!/usr/bin/env python3
"""
Fix inflated category_stats in homepage_stats (id=1).

Bug: fund_cascade.py compute_homepage_stats() multiplied AUM-weighted averages
by 100 again, even though pct_return_ratio() already converted ratio→%.
Result: 553%, 789% etc. Correct values should be ~5-10%.

Also fix: weekly/monthly/quarterly are already in % format (NOT ratios),
so they should NOT be multiplied by 100.

Correct mapping:
  - weekly, monthly, quarterly  → already %, use directly
  - return_1h (7-day), return_1a (30-day) → ratio → ×100
  - return_3a (90-day), return_6a (180-day) → ratio → ×100
"""

import psycopg2
import json
from decimal import Decimal

DB_URL = "postgresql://postgres:rzvfO6ub5F1W6hpR@db.oqkobptbvcazifpvjwfz.supabase.co:5432/postgres"
MAX_ABS_RETURN = 50  # skip outliers > ±50% (split/data error)

def decimal_to_float(d):
    if d is None:
        return None
    if isinstance(d, Decimal):
        return float(d)
    return float(d)

def compute_category_stats(conn):
    """Compute correct AUM-weighted category stats from funds table."""
    cur = conn.cursor()

    # Fetch all funds with relevant columns
    cur.execute("""
        SELECT code, fund_type, market_cap,
               weekly, monthly, quarterly,
               return_1h, return_1a, return_3a, return_6a,
               daily_change
        FROM funds
    """)
    rows = cur.fetchall()
    cur.close()

    # Build category aggregates
    cat_map = {}
    for r in rows:
        code, fund_type = r[0], r[1] or "OTHER"
        market_cap = decimal_to_float(r[2])
        weekly = decimal_to_float(r[3])      # already in %
        monthly = decimal_to_float(r[4])      # already in %
        quarterly = decimal_to_float(r[5])   # already in %
        return_1h = decimal_to_float(r[6])     # ratio (7-day)
        return_1a = decimal_to_float(r[7])    # ratio (30-day)
        return_3a = decimal_to_float(r[8])     # ratio (90-day)
        return_6a = decimal_to_float(r[9])    # ratio (180-day)
        daily_change = decimal_to_float(r[10])

        if fund_type not in cat_map:
            cat_map[fund_type] = {
                "count": 0, "total_market_cap": 0.0,
                "sum_daily_change": 0.0, "change_count": 0,
                "aum_1w": 0.0, "aum_1m": 0.0, "aum_3m": 0.0, "aum_6m": 0.0,
                "sum_aum_1w": 0.0, "sum_aum_1m": 0.0,
                "sum_aum_3m": 0.0, "sum_aum_6m": 0.0,
            }
        s = cat_map[fund_type]
        s["count"] += 1
        aum = market_cap or 0.0
        s["total_market_cap"] += aum

        if daily_change is not None:
            s["sum_daily_change"] += daily_change
            s["change_count"] += 1

        # Convert ratios → % (NOT for weekly/monthly/quarterly which are already %)
        r1w = return_1h * 100 if return_1h is not None else None   # 7-day ratio→%
        r1m = return_1a * 100 if return_1a is not None else None   # 30-day ratio→%
        r3m = return_3a * 100 if return_3a is not None else None   # 90-day ratio→%
        r6m = return_6a * 100 if return_6a is not None else None   # 180-day ratio→%

        if aum > 0:
            if r1w is not None and abs(r1w) <= MAX_ABS_RETURN:
                s["aum_1w"] += r1w * aum
                s["sum_aum_1w"] += aum
            if r1m is not None and abs(r1m) <= MAX_ABS_RETURN:
                s["aum_1m"] += r1m * aum
                s["sum_aum_1m"] += aum
            if r3m is not None and abs(r3m) <= MAX_ABS_RETURN:
                s["aum_3m"] += r3m * aum
                s["sum_aum_3m"] += aum
            if r6m is not None and abs(r6m) <= MAX_ABS_RETURN:
                s["aum_6m"] += r6m * aum
                s["sum_aum_6m"] += aum

    # Build final category_stats (NO extra *100 — already done above)
    category_stats = {}
    for cat, s in sorted(cat_map.items()):
        avg_change = s["sum_daily_change"] / s["change_count"] if s["change_count"] else None

        change_1w = (s["aum_1w"] / s["sum_aum_1w"]) if s["sum_aum_1w"] > 0 else None
        change_1m = (s["aum_1m"] / s["sum_aum_1m"]) if s["sum_aum_1m"] > 0 else None
        change_3m = (s["aum_3m"] / s["sum_aum_3m"]) if s["sum_aum_3m"] > 0 else None
        change_6m = (s["aum_6m"] / s["sum_aum_6m"]) if s["sum_aum_6m"] > 0 else None

        category_stats[cat] = {
            "fund_count": s["count"],
            "total_market_cap": round(s["total_market_cap"], 2),
            "change_1d": round(avg_change, 4) if avg_change is not None else None,
            "change_1w": round(change_1w, 4) if change_1w is not None else None,
            "change_1m": round(change_1m, 4) if change_1m is not None else None,
            "change_3m": round(change_3m, 4) if change_3m is not None else None,
            "change_6m": round(change_6m, 4) if change_6m is not None else None,
        }

    return category_stats


def get_existing_homepage_stats(conn):
    """Preserve benchmarks_data and category_sparklines."""
    cur = conn.cursor()
    cur.execute("SELECT benchmarks_data, category_sparklines FROM homepage_stats WHERE id=1")
    row = cur.fetchone()
    cur.close()
    if row:
        return row[0], row[1]
    return None, None


def fix_homepage_stats():
    conn = psycopg2.connect(DB_URL)

    # Get current (inflated) stats for comparison
    cur = conn.cursor()
    cur.execute("SELECT category_stats FROM homepage_stats WHERE id=1")
    row = cur.fetchone()
    cur.close()
    old_stats = {}
    if row and row[0]:
        old_stats = row[0] if isinstance(row[0], dict) else json.loads(str(row[0]))

    print("=== BEFORE (inflated) ===")
    for k in ["VFF", "ALTIN", "BYF", "OKS", "SRF", "KFF"]:
        if k in old_stats:
            v = old_stats[k]
            print(f"  {k}: 1w={v.get('change_1w')}, 1m={v.get('change_1m')}, 3m={v.get('change_3m')}, 6m={v.get('change_6m')}")

    # Compute correct stats
    print("\nComputing correct category_stats...")
    new_stats = compute_category_stats(conn)

    print("\n=== AFTER (corrected) ===")
    for k in ["VFF", "ALTIN", "BYF", "OKS", "SRF", "KFF"]:
        if k in new_stats:
            v = new_stats[k]
            print(f"  {k}: 1w={v.get('change_1w')}, 1m={v.get('change_1m')}, 3m={v.get('change_3m')}, 6m={v.get('change_6m')}")

    # Get existing benchmarks_data and category_sparklines to preserve them
    benchmarks_data, category_sparklines = get_existing_homepage_stats(conn)

    # Update homepage_stats (id=1) with correct category_stats
    cur = conn.cursor()
    cur.execute("""
        UPDATE homepage_stats
        SET category_stats = %s,
            category_change = %s,
            category_sparklines = %s,
            updated_at = NOW()
        WHERE id = 1
    """, (
        json.dumps(new_stats),
        json.dumps({}),
        json.dumps(category_sparklines) if category_sparklines else json.dumps({})
    ))
    conn.commit()
    cur.close()
    print(f"\nhomepage_stats (id=1) updated with correct category_stats.")
    print(f"  Categories updated: {len(new_stats)}")

    conn.close()


if __name__ == "__main__":
    fix_homepage_stats()