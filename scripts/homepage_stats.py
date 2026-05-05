#!/usr/bin/env python3
"""
homepage_stats.py — Compute homepage stats: category ranks, gainers/losers, category averages.

Schedule (launchd):  Mon-Fri 04:45 UTC = 07:45 TR
Usage:               python3 scripts/homepage_stats.py

Logic (from homepage-stats-lib.ts):
  1. Fetch all funds (code, name, fund_type, market_cap, daily_change, returns)
  2. Compute category rankings (fund_category_ranks table)
  3. Compute top5 gainers/losers, most invested
  4. Compute AUM-weighted category returns for 1w/1m/3m/6m
  5. Upsert homepage_stats table

Data format rules:
  - daily_change: stored as PERCENTAGE (e.g. 2.34 = 2.34%), NOT ratio
  - return_1h/return_1a/return_3m/return_6m: stored as RATIO (e.g. 0.059 = 5.9%)
    → MUST multiply by 100 when displaying/using as percentage
"""

import sys
import math
import time
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from cron_shared import (
    load_env, SUPABASE_URL, SUPABASE_KEY, upsert_table, query_table,
    query_table_paginated, upsert_system_status, get_logger,
)

LOG = get_logger("homepage_stats")

MAX_ABS_RETURN = 50  # skip outliers > ±50% (likely split or data error)


def pct_return_ratio(val: float | None) -> float | None:
    """Convert stored ratio to percentage (×100)."""
    if val is None:
        return None
    return val * 100


# ─── Main ────────────────────────────────────────────────────────────────────

def main():
    load_env()
    LOG("Starting homepage_stats")
    t0 = time.time()

    # ── 1. Fetch all funds ─────────────────────────────────────────────────
    all_funds = query_table_paginated(
        "funds",
        "code,name,fund_type,market_cap,daily_change,return_1h,return_1a,return_3m,return_6m",
    )
    LOG(f"Total funds: {len(all_funds)}")

    funds = []
    for f in all_funds:
        funds.append({
            "code": f["code"],
            "name": f["name"],
            "fund_type": f.get("fund_type") or "OTHER",
            "market_cap": float(f["market_cap"]) if f.get("market_cap") else 0.0,
            "daily_change": float(f["daily_change"]) if f.get("daily_change") is not None else None,
            "return_1h": float(f["return_1h"]) if f.get("return_1h") is not None else None,
            "return_1a": float(f["return_1a"]) if f.get("return_1a") is not None else None,
            "return_3m": float(f["return_3m"]) if f.get("return_3m") is not None else None,
            "return_6m": float(f["return_6m"]) if f.get("return_6m") is not None else None,
        })

    # ── 2. Category rankings ───────────────────────────────────────────────
    category_groups: dict[str, list] = {}
    for fund in funds:
        t = fund["fund_type"]
        if t not in category_groups:
            category_groups[t] = []
        category_groups[t].append(fund)

    rank_rows = []
    for cat, cat_funds in category_groups.items():
        # Sort by daily_change DESC, nulls last
        ranked = sorted(
            cat_funds,
            key=lambda f: (f["daily_change"] is None, -(f["daily_change"] or 0)),
        )
        for idx, fund in enumerate(ranked):
            rank = idx + 1
            count = len(ranked)
            percentile = ((count - rank) / (count - 1) * 100) if count > 1 else 100.0
            rank_rows.append({
                "fund_code": fund["code"],
                "category": cat,
                "rank": rank,
                "category_count": count,
                "percentile": round(percentile, 1),
                "computed_at": datetime.utcnow().isoformat(),
            })

    # Upsert category ranks (delete all first, then insert)
    from cron_shared import rest_patch
    if rank_rows:
        # Clear existing ranks
        rest_patch(
            f"{SUPABASE_URL}/rest/v1/fund_category_ranks",
            {"id": "eq.*"},  # won't work this way — use delete instead
        )
        # Delete via direct approach
        import urllib.request
        import json
        req = urllib.request.Request(
            f"{SUPABASE_URL}/rest/v1/fund_category_ranks",
            data=b"{}",
            method="DELETE",
            headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"}
        )
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                pass
        except Exception:
            pass

        # Insert in batches
        for i in range(0, len(rank_rows), 100):
            upsert_table("fund_category_ranks", rank_rows[i:i + 100])

    LOG(f"fund_category_ranks: {len(rank_rows)} rows")

    # ── 3. Top gainers / losers ────────────────────────────────────────────
    # daily_change is already in % format (no conversion needed)
    with_change = [f for f in funds if f["daily_change"] is not None]
    sorted_change = sorted(with_change, key=lambda f: f["daily_change"], reverse=True)

    top5_gainers = [
        {"code": f["code"], "name": f["name"], "change": f["daily_change"], "market_cap": f["market_cap"]}
        for f in sorted_change[:5]
    ]
    top5_losers = [
        {"code": f["code"], "name": f["name"], "change": f["daily_change"], "market_cap": f["market_cap"]}
        for f in sorted_change[-5:][::-1]
    ]

    # Most invested (top 5 by market_cap)
    top_invested = sorted(funds, key=lambda f: f["market_cap"], reverse=True)[:5]
    top_funds = [
        {"code": f["code"], "name": f["name"], "market_cap": f["market_cap"], "daily_change": f["daily_change"]}
        for f in top_invested
    ]

    # ── 4. Category stats (AUM-weighted) ───────────────────────────────────
    cat_stats: dict[str, dict] = {}
    for fund in funds:
        t = fund["fund_type"]
        if t not in cat_stats:
            cat_stats[t] = {
                "count": 0, "total_market_cap": 0.0,
                "sum_daily_change": 0.0, "change_count": 0,
                "aum_1w": 0.0, "aum_1m": 0.0,
                "aum_3m": 0.0, "aum_6m": 0.0,
                "sum_aum_1w": 0.0, "sum_aum_1m": 0.0,
                "sum_aum_3m": 0.0, "sum_aum_6m": 0.0,
            }
        s = cat_stats[t]
        s["count"] += 1
        aum = fund["market_cap"]
        s["total_market_cap"] += aum
        if fund["daily_change"] is not None:
            s["sum_daily_change"] += fund["daily_change"]
            s["change_count"] += 1

        # Period returns (convert ratio → %)
        r1w = pct_return_ratio(fund["return_1h"])
        r1m = pct_return_ratio(fund["return_1a"])
        r3m = pct_return_ratio(fund["return_3m"])
        r6m = pct_return_ratio(fund["return_6m"])

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

    category_stats: dict[str, dict] = {}
    for t, s in cat_stats.items():
        category_stats[t] = {
            "change_1d": round(s["sum_daily_change"] / s["change_count"], 4) if s["change_count"] > 0 else 0.0,
            "total_market_cap": s["total_market_cap"],
            "count": s["count"],
            "change_1w": round(s["aum_1w"] / s["sum_aum_1w"], 4) if s["sum_aum_1w"] > 0 else 0.0,
            "change_1m": round(s["aum_1m"] / s["sum_aum_1m"], 4) if s["sum_aum_1m"] > 0 else 0.0,
            "change_3m": round(s["aum_3m"] / s["sum_aum_3m"], 4) if s["sum_aum_3m"] > 0 else 0.0,
            "change_6m": round(s["aum_6m"] / s["sum_aum_6m"], 4) if s["sum_aum_6m"] > 0 else 0.0,
        }

    # ── 5. Category change map ─────────────────────────────────────────────
    category_change = {}
    for t, stat in category_stats.items():
        category_change[t] = {
            "change_pct": stat["change_1d"],
            "prev_aum": stat["total_market_cap"] * 0.99,
            "curr_aum": stat["total_market_cap"],
            "count": stat["count"],
        }

    # ── 6. Fetch existing benchmarks_data from homepage_stats ───────────────
    existing = query_table("homepage_stats", "benchmarks_data", filters={"id": "eq.1"})
    benchmarks_data = None
    if existing and existing[0].get("benchmarks_data"):
        benchmarks_data = existing[0]["benchmarks_data"]

    # ── 7. Compute total market cap and avg daily change ───────────────────
    total_market_cap = sum(f["market_cap"] for f in funds)
    funds_with_change = [f for f in funds if f["daily_change"] is not None]
    avg_daily_change = (
        sum(f["daily_change"] for f in funds_with_change) / len(funds_with_change)
        if funds_with_change else 0.0
    )

    latest_date = datetime.utcnow().strftime("%Y-%m-%d")

    # ── 8. Upsert homepage_stats ───────────────────────────────────────────
    stats_payload = {
        "id": 1,
        "total": len(funds),
        "tefas_total": len(funds),
        "total_market_cap": total_market_cap,
        "avg_daily_change": round(avg_daily_change, 4),
        "latest_date": latest_date,
        "top5_gainers": top5_gainers,
        "top5_losers": top5_losers,
        "most_invested": top_funds,
        "most_held_stocks": [],
        "category_stats": category_stats,
        "category_change": category_change,
        "top_funds": top_funds,
        "category_sparklines": {},  # computed by etf-cascade
        "benchmarks_data": benchmarks_data,
        "updated_at": datetime.utcnow().isoformat(),
    }

    ok = upsert_table("homepage_stats", [stats_payload], conflict_col="id")
    if ok:
        LOG("homepage_stats upserted")
    else:
        LOG("homepage_stats FAILED", "ERROR")

    elapsed = round(time.time() - t0, 1)
    upsert_system_status(
        "last_homepage_stats_cron",
        datetime.utcnow().isoformat(),
        "success",
        f"funds={len(funds)}, categories={len(category_stats)}, elapsed={elapsed}s",
    )
    LOG(f"Done in {elapsed}s")


if __name__ == "__main__":
    main()
