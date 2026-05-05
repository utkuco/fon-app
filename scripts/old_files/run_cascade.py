#!/usr/bin/env python3.11
"""
run_cascade.py — Orchestrate fund-cron + homepage-stats logic in one pass.

Computes:
  1. daily_change from price_history (last vs previous trading day)
  2. Period returns: return_1g(1d), return_1h(7d), return_1a(30d),
     return_3a(90d), return_6a(180d) — stored as RATIO
  3. fund_category_ranks (rank within fund_type by daily_change)
  4. homepage_stats (category averages, gainers/losers)

Test mode: processes first 5 funds before doing all 2400.
"""

import sys
import math
import time
import json
from datetime import datetime, timedelta
from pathlib import Path
import urllib.request
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent))

from cron_shared import (
    load_env,
    SUPABASE_URL,
    SUPABASE_KEY,
    upsert_table,
    query_table,
    query_table_paginated,
    upsert_system_status,
    get_logger,
    rest_patch,
)

LOG = get_logger("run_cascade")

# ─── Constants ────────────────────────────────────────────────────────────────

MAX_ABS_RETURN = 50  # skip outliers > ±50% (likely split or data error)
PAGE_SIZE = 500      # funds per page when fetching with price_history

# ─── Date helpers ────────────────────────────────────────────────────────────

def turkey_now() -> datetime:
    """UTC+3 for Turkey."""
    return datetime.utcnow() + timedelta(hours=3)


def to_date_str(d: datetime) -> str:
    return d.strftime("%Y-%m-%d")


def get_price_at_days_ago(
    sorted_prices: list[dict],  # [{"date": "...", "price": ...}] sorted ASC
    days: int,
    ref_date: str,  # "YYYY-MM-DD"
) -> float | None:
    cutoff = (
        datetime.strptime(ref_date, "%Y-%m-%d") - timedelta(days=days)
    ).strftime("%Y-%m-%d")
    for p in reversed(sorted_prices):
        if p["date"] <= cutoff:
            return p["price"]
    return None


# ─── Sparkline ────────────────────────────────────────────────────────────────

SPARKLINE_W = 280
SPARKLINE_H = 40


def compute_sparkline(
    price_history: list[dict],  # [{"date": "YYYY-MM-DD", "price": float}, ...]
    days: int = 30,
) -> Optional[dict]:
    """
    Returns {"points": [[x, y], ...], "positive": bool} or None.
    Mirrors computeSparkline() in fund-cron-lib.ts.
    """
    if not price_history or len(price_history) < 2:
        return None

    sorted_hist = sorted(price_history, key=lambda p: p["date"])
    last_date = sorted_hist[-1]["date"]

    cutoff = to_date_str(
        datetime.strptime(last_date, "%Y-%m-%d") - timedelta(days=days)
    )
    cutoff_idx = next(
        (i for i, p in enumerate(sorted_hist) if p["date"] >= cutoff),
        max(0, len(sorted_hist) - days),
    )
    last30 = sorted_hist[cutoff_idx:]
    if len(last30) < 2:
        return None

    prices = [p["price"] for p in last30 if p.get("price") is not None]
    if len(prices) < 2:
        return None

    mn = min(prices)
    mx = max(prices)
    rng = mx - mn or 1
    points: list[list[float]] = [
        [
            round(i / (len(prices) - 1) * SPARKLINE_W, 4),
            round((p - mn) / rng * SPARKLINE_H, 4),
        ]
        for i, p in enumerate(prices)
    ]
    positive = prices[-1] >= prices[0]
    return {"points": points, "positive": positive}


# ─── Period returns (RATIO) ───────────────────────────────────────────────────

def compute_period_returns(
    sorted_prices: list[dict],  # sorted ASC by date
    latest_price: float,
    ref_date: str,  # "YYYY-MM-DD" — Turkey today
) -> dict:
    """
    Compute return_1g(1d), return_1h(7d), return_1a(30d),
    return_3a(90d), return_6a(180d) as RATIOs.
    """
    returns = {
        "return_1g": 0.0,
        "return_1h": 0.0,
        "return_1a": 0.0,
        "return_3a": 0.0,
        "return_6a": 0.0,
    }

    def try_return(days: int) -> float:
        old_price = get_price_at_days_ago(sorted_prices, days, ref_date)
        if old_price and old_price > 0:
            return round((latest_price - old_price) / old_price, 6)
        return 0.0

    returns["return_1g"] = try_return(1)
    returns["return_1h"] = try_return(7)
    returns["return_1a"] = try_return(30)
    returns["return_3a"] = try_return(90)
    returns["return_6a"] = try_return(180)
    return returns


# ─── Compute daily_change + returns for all funds ────────────────────────────

def compute_fund_metrics(
    all_funds: list[dict],
    today_tr: str,
    yest_tr: str,
) -> tuple[list[dict], list[dict]]:
    """
    Returns (fund_updates, sparkline_updates).
      fund_updates: [{"code": ..., "daily_change": ..., "return_1g": ..., ...}, ...]
      sparkline_updates: [{"code": ..., "sparkline": {...}}, ...]
    """
    fund_updates: list[dict] = []
    sparkline_updates: list[dict] = []

    for fund in all_funds:
        ph = fund.get("price_history") or []
        if isinstance(ph, str):
            try:
                ph = json.loads(ph)
            except Exception:
                continue

        if len(ph) < 2:
            continue

        sorted_ph = sorted(ph, key=lambda x: x.get("date", ""))
        latest_price = sorted_ph[-1].get("price")
        if not latest_price or latest_price <= 0:
            continue

        # ── daily_change: today vs yesterday (Turkey timezone) ──────────────
        # today_price = most recent price on or before today_tr
        # yest_price  = most recent price on or before yest_tr
        today_price: Optional[float] = None
        yest_price: Optional[float] = None
        for p in reversed(sorted_ph):
            if today_price is None and p["date"] <= today_tr:
                today_price = p.get("price")
            if yest_price is None and p["date"] <= yest_tr:
                yest_price = p.get("price")
            if today_price is not None and yest_price is not None:
                break

        # ── Period returns (RATIO) ──────────────────────────────────────────
        period_rets = compute_period_returns(sorted_ph, latest_price, today_tr)

        # ── daily_change: stored as PERCENTAGE (2.34 means 2.34%) ────────────
        if today_price and yest_price and yest_price > 0 and today_price > 0:
            daily_change = round((today_price - yest_price) / yest_price * 100, 4)
            fund_updates.append({
                "code": fund["code"],
                "daily_change": daily_change,
                **period_rets,
            })

        # ── Sparkline ───────────────────────────────────────────────────────
        sparkline = compute_sparkline(sorted_ph, days=30)
        if sparkline:
            sparkline_updates.append({
                "code": fund["code"],
                "sparkline": sparkline,
            })

    return fund_updates, sparkline_updates


# ─── Upsert fund metrics to Supabase ────────────────────────────────────────

def upsert_fund_metrics(fund_updates: list[dict]) -> int:
    """Upsert fund metrics in batches of 100 to avoid timeout."""
    if not fund_updates:
        return 0
    count = 0
    for i in range(0, len(fund_updates), 100):
        batch = fund_updates[i:i + 100]
        ok = upsert_table("funds", batch, conflict_col="code")
        if ok:
            count += len(batch)
        if i % 200 == 0:
            LOG(f"  fund_metrics progress: {i}/{len(fund_updates)}")
    return count


def upsert_sparklines(sparkline_updates: list[dict]) -> int:
    """Upsert sparklines to funds.sparkline in batches of 50 to avoid timeout."""
    if not sparkline_updates:
        return 0
    payload = [{"code": r["code"], "sparkline": r["sparkline"]} for r in sparkline_updates if r.get("sparkline")]
    if not payload:
        return 0
    count = 0
    total_batches = (len(payload) + 24) // 25
    for i in range(0, len(payload), 25):
        batch = payload[i:i + 25]
        ok = upsert_table("funds", batch, conflict_col="code")
        if ok:
            count += len(batch)
        else:
            LOG(f"  sparkline batch {i//25}/{total_batches} failed")
        if i % 125 == 0:
            LOG(f"  sparkline progress: {i}/{len(payload)}")
    return count


# ─── Category ranks ──────────────────────────────────────────────────────────

def compute_category_ranks(funds: list[dict]) -> list[dict]:
    """
    Rank funds within each fund_type by daily_change DESC (nulls last).
    Returns rows for fund_category_ranks table.
    """
    # Group by fund_type
    groups: dict[str, list[dict]] = {}
    for f in funds:
        t = f.get("fund_type") or "OTHER"
        groups.setdefault(t, []).append(f)

    rank_rows: list[dict] = []
    for cat, cat_funds in groups.items():
        ranked = sorted(
            cat_funds,
            key=lambda f: (f.get("daily_change") is None, -(f.get("daily_change") or 0)),
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
    return rank_rows


def upsert_category_ranks(rank_rows: list[dict]) -> int:
    """Upsert category ranks using conflict_col (fund_code is unique)."""
    if not rank_rows:
        return 0
    ok = upsert_table("fund_category_ranks", rank_rows, conflict_col="fund_code")
    return len(rank_rows) if ok else 0


# ─── Homepage stats ───────────────────────────────────────────────────────────

def pct_return_ratio(val: Optional[float]) -> Optional[float]:
    """Convert stored RATIO to percentage (×100)."""
    if val is None:
        return None
    return val * 100


def compute_homepage_stats(funds: list[dict]) -> dict:
    """
    Compute homepage_stats payload:
      - top5_gainers, top5_losers (by daily_change %)
      - category_stats (AUM-weighted 1w/1m/3m/6m from ratio columns)
      - total_market_cap, avg_daily_change
    """
    # Fetch existing benchmarks_data to preserve it
    existing = query_table("homepage_stats", "benchmarks_data", filters={"id": "eq.1"})
    benchmarks_data = None
    if existing and existing[0].get("benchmarks_data"):
        benchmarks_data = existing[0]["benchmarks_data"]

    # ── Gainers / losers ──────────────────────────────────────────────────
    with_change = [f for f in funds if f.get("daily_change") is not None]
    sorted_by_change = sorted(with_change, key=lambda f: f["daily_change"], reverse=True)

    top5_gainers = [
        {
            "code": f["code"],
            "name": f.get("name", ""),
            "change": f["daily_change"],
            "market_cap": f.get("market_cap") or 0,
        }
        for f in sorted_by_change[:5]
    ]
    top5_losers = [
        {
            "code": f["code"],
            "name": f.get("name", ""),
            "change": f["daily_change"],
            "market_cap": f.get("market_cap") or 0,
        }
        for f in sorted_by_change[-5:][::-1]
    ]

    # ── Most invested ─────────────────────────────────────────────────────
    top_invested = sorted(funds, key=lambda f: f.get("market_cap") or 0, reverse=True)[:5]
    top_funds = [
        {
            "code": f["code"],
            "name": f.get("name", ""),
            "market_cap": f.get("market_cap") or 0,
            "daily_change": f.get("daily_change"),
        }
        for f in top_invested
    ]

    # ── Category stats (AUM-weighted) ─────────────────────────────────────
    cat_map: dict[str, dict] = {}
    for f in funds:
        t = f.get("fund_type") or "OTHER"
        if t not in cat_map:
            cat_map[t] = {
                "count": 0,
                "total_market_cap": 0.0,
                "sum_daily_change": 0.0,
                "change_count": 0,
                "aum_1w": 0.0, "aum_1m": 0.0, "aum_3m": 0.0, "aum_6m": 0.0,
                "sum_aum_1w": 0.0, "sum_aum_1m": 0.0,
                "sum_aum_3m": 0.0, "sum_aum_6m": 0.0,
            }
        s = cat_map[t]
        s["count"] += 1
        aum = f.get("market_cap") or 0
        s["total_market_cap"] += aum
        if f.get("daily_change") is not None:
            s["sum_daily_change"] += f["daily_change"]
            s["change_count"] += 1

        # Period returns stored as RATIO → convert to %
        r1w = pct_return_ratio(f.get("return_1h"))   # 7-day
        r1m = pct_return_ratio(f.get("return_1a"))   # 30-day
        r3m = pct_return_ratio(f.get("return_3a"))   # 90-day
        r6m = pct_return_ratio(f.get("return_6a"))   # 180-day

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
    for t, s in cat_map.items():
        category_stats[t] = {
            "change_1d": round(s["sum_daily_change"] / s["change_count"], 4)
            if s["change_count"] > 0 else 0.0,
            "total_market_cap": s["total_market_cap"],
            "count": s["count"],
            "change_1w": round(s["aum_1w"] / s["sum_aum_1w"], 4)
            if s["sum_aum_1w"] > 0 else 0.0,
            "change_1m": round(s["aum_1m"] / s["sum_aum_1m"], 4)
            if s["sum_aum_1m"] > 0 else 0.0,
            "change_3m": round(s["aum_3m"] / s["sum_aum_3m"], 4)
            if s["sum_aum_3m"] > 0 else 0.0,
            "change_6m": round(s["aum_6m"] / s["sum_aum_6m"], 4)
            if s["sum_aum_6m"] > 0 else 0.0,
        }

    category_change = {
        t: {
            "change_pct": stat["change_1d"],
            "prev_aum": stat["total_market_cap"] * 0.99,
            "curr_aum": stat["total_market_cap"],
            "count": stat["count"],
        }
        for t, stat in category_stats.items()
    }

    # ── Totals ─────────────────────────────────────────────────────────────
    total_market_cap = sum(f.get("market_cap") or 0 for f in funds)
    funds_with_change = [f for f in funds if f.get("daily_change") is not None]
    avg_daily_change = (
        sum(f["daily_change"] for f in funds_with_change) / len(funds_with_change)
        if funds_with_change else 0.0
    )

    latest_date = to_date_str(turkey_now())

    return {
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


# ─── Main ────────────────────────────────────────────────────────────────────

def main():
    load_env()
    LOG("Starting run_cascade")

    # Check for test mode flag
    test_mode = "--test" in sys.argv or "-t" in sys.argv

    t0 = time.time()
    today_tr = to_date_str(turkey_now())
    yest_tr = to_date_str(turkey_now() - timedelta(days=1))
    LOG(f"today={today_tr}, yesterday={yest_tr}")

    # ── 1. Fetch all funds with price_history (paginated) ─────────────────
    LOG("Fetching funds with price_history...")
    all_funds_raw: list[dict] = []
    page = 0
    has_more = True
    while has_more:
        start = page * PAGE_SIZE
        rows = query_table(
            "funds",
            "id,code,name,fund_type,market_cap,price_history,currency",
            filters={"price_history": "not.is.null"},
            offset=start,
            limit=PAGE_SIZE,
        )
        if not rows:
            has_more = False
            break
        all_funds_raw.extend(rows)
        has_more = len(rows) == PAGE_SIZE
        page += 1
        LOG(f"  page {page}: {len(rows)} rows, total so far: {len(all_funds_raw)}")
        if page >= 20:  # safety cap
            break

    LOG(f"Total funds fetched: {len(all_funds_raw)}")

    if test_mode:
        all_funds_raw = all_funds_raw[:5]
        LOG(f"TEST MODE: limiting to first {len(all_funds_raw)} funds")

    # ── 2. Compute daily_change + period returns + sparklines ───────────────
    LOG("Computing fund metrics from price_history...")
    fund_updates, sparkline_updates = compute_fund_metrics(all_funds_raw, today_tr, yest_tr)
    LOG(f"  fund_updates (daily_change + returns): {len(fund_updates)}")
    LOG(f"  sparkline_updates: {len(sparkline_updates)}")

    # ── 3. Upsert funds table ───────────────────────────────────────────────
    LOG("Upserting fund metrics to funds table...")
    fund_count = upsert_fund_metrics(fund_updates)
    LOG(f"  funds updated: {fund_count}/{len(fund_updates)}")

    # ── 4. Upsert sparklines to precomputed_funds ──────────────────────────
    LOG("Upserting sparklines to precomputed_funds...")
    sparkline_count = upsert_sparklines(sparkline_updates)
    LOG(f"  sparklines upserted: {sparkline_count}/{len(sparkline_updates)}")

    # ── 5. Reload funds (now with daily_change + returns populated) ────────
    LOG("Reloading funds for category ranks + homepage_stats...")
    reload_cols = (
        "code,name,fund_type,market_cap,daily_change,"
        "return_1g,return_1h,return_1a,return_3a,return_6a"
    )
    if test_mode:
        # In test mode just use the already-loaded funds (they have code,name,fund_type,market_cap)
        # but need to add daily_change/returns from fund_updates
        funds_for_stats: list[dict] = []
        updates_map = {u["code"]: u for u in fund_updates}
        for f in all_funds_raw:
            code = f["code"]
            if code in updates_map:
                u = updates_map[code]
                funds_for_stats.append({
                    "code": code,
                    "name": f.get("name", ""),
                    "fund_type": f.get("fund_type") or "OTHER",
                    "market_cap": f.get("market_cap") or 0,
                    "daily_change": u["daily_change"],
                    "return_1g": u["return_1g"],
                    "return_1h": u["return_1h"],
                    "return_1a": u["return_1a"],
                    "return_3a": u["return_3a"],
                    "return_6a": u["return_6a"],
                })
            else:
                funds_for_stats.append({
                    "code": code,
                    "name": f.get("name", ""),
                    "fund_type": f.get("fund_type") or "OTHER",
                    "market_cap": f.get("market_cap") or 0,
                    "daily_change": None,
                    "return_1g": None,
                    "return_1h": None,
                    "return_1a": None,
                    "return_3a": None,
                    "return_6a": None,
                })
    else:
        # Full reload
        funds_for_stats = query_table_paginated(
            "funds",
            reload_cols,
        )
        # Normalize
        normalized: list[dict] = []
        for f in funds_for_stats:
            normalized.append({
                "code": f["code"],
                "name": f.get("name") or "",
                "fund_type": f.get("fund_type") or "OTHER",
                "market_cap": float(f["market_cap"]) if f.get("market_cap") else 0.0,
                "daily_change": float(f["daily_change"]) if f.get("daily_change") is not None else None,
                "return_1g": float(f["return_1g"]) if f.get("return_1g") is not None else None,
                "return_1h": float(f["return_1h"]) if f.get("return_1h") is not None else None,
                "return_1a": float(f["return_1a"]) if f.get("return_1a") is not None else None,
                "return_3a": float(f["return_3a"]) if f.get("return_3a") is not None else None,
                "return_6a": float(f["return_6a"]) if f.get("return_6a") is not None else None,
            })
        funds_for_stats = normalized

    LOG(f"  funds_for_stats: {len(funds_for_stats)}")

    # ── 6. Compute + upsert fund_category_ranks ─────────────────────────────
    LOG("Computing fund_category_ranks...")
    rank_rows = compute_category_ranks(funds_for_stats)
    rank_count = upsert_category_ranks(rank_rows)
    LOG(f"  fund_category_ranks upserted: {rank_count}")

    # ── 7. Compute + upsert homepage_stats ─────────────────────────────────
    LOG("Computing homepage_stats...")
    stats_payload = compute_homepage_stats(funds_for_stats)
    ok = upsert_table("homepage_stats", [stats_payload], conflict_col="id")
    if ok:
        LOG("  homepage_stats upserted OK")
    else:
        LOG("  homepage_stats upsert FAILED", "ERROR")

    # ── 8. Update system_status ────────────────────────────────────────────
    elapsed = round(time.time() - t0, 1)
    upsert_system_status(
        "last_cascade_run",
        datetime.utcnow().isoformat(),
        "success",
        (
            f"funds={len(fund_updates)}, sparklines={sparkline_count}, "
            f"ranks={rank_count}, elapsed={elapsed}s"
        ),
    )
    LOG(f"Done in {elapsed}s — funds={len(fund_updates)}, "
        f"sparklines={sparkline_count}, ranks={rank_count}")


if __name__ == "__main__":
    main()
