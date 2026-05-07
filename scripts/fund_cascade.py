#!/usr/bin/env python3
"""
fund_cascade.py — Birleşik fund processing script.

Bu script aşağıdaki eski scriptlerin hepsini birleştirir:
  - fund_cron.py     → benchmark prices + fund metrics + sparklines
  - run_cascade.py   → category ranks + homepage_stats

Schedule (launchd): Hafta içi 08:00-08:45 UTC (11:00-11:45 TR)
Usage:             python3 scripts/fund_cascade.py

Logic:
  1. Fetch benchmark prices from Yahoo Finance → benchmark_prices table
  2. Compute daily_change + period returns (1g/7d/30d/90d/180d) from funds.price_history
  3. Compute + upsert sparklines to funds.sparkline
  4. Compute + upsert fund_category_ranks (rank within fund_type by daily_change)
  5. Compute + upsert homepage_stats (top gainers/losers, category averages)
  6. Update system_status

Approximate runtime: ~25-40 min for 2400 funds.
"""

import sys
import math
import time
import json
import psycopg2
import psycopg2.extras
from datetime import datetime, timedelta
from pathlib import Path
import urllib.request
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent))

from cron_shared import (
    load_env,
    SUPABASE_URL,
    SUPABASE_KEY,
    SUPABASE_DB_URL,
    HEADERS,
    upsert_table,
    query_table,
    query_table_paginated,
    upsert_system_status,
    get_logger,
    rest_patch,
)

LOG = get_logger("fund_cascade")

# ─── Constants ────────────────────────────────────────────────────────────────

MAX_ABS_RETURN = 50  # skip outliers > ±50% (likely split or data error)
PAGE_SIZE = 500      # funds per page when fetching with price_history

# ─── Date helpers ────────────────────────────────────────────────────────────

def turkey_now() -> datetime:
    """UTC+3 for Turkey."""
    return datetime.utcnow() + timedelta(hours=3)


def to_date_str(d: datetime) -> str:
    return d.strftime("%Y-%m-%d")


def days_ago(n: int) -> datetime:
    return turkey_now() - timedelta(days=n)


def get_price_at_days_ago(
    sorted_prices: list[dict],
    days: int,
    ref_date: str,
) -> Optional[float]:
    cutoff = (
        datetime.strptime(ref_date, "%Y-%m-%d") - timedelta(days=days)
    ).strftime("%Y-%m-%d")
    for p in reversed(sorted_prices):
        if p["date"] <= cutoff:
            return p["price"]
    return None


# ─── Sparkline ───────────────────────────────────────────────────────────────

SPARKLINE_W = 280
SPARKLINE_H = 40


def compute_sparkline(
    price_history: list[dict],
    days: int = 30,
) -> Optional[dict]:
    """Build sparkline from price history. Returns {points, positive} format (NOT SVG string).
    
    This format matches SparklineMini component in fund-card.tsx which renders
    gradient-filled path sparklines. The old SVG string format is deprecated.
    """
    if len(price_history) < 2:
        return None

    # price_history is stored ASC (oldest→newest) — take last `days` entries
    sorted_ph = sorted(price_history, key=lambda x: x.get("date", ""))
    recent = sorted_ph[-days:] if len(sorted_ph) > days else sorted_ph

    if len(recent) < 2:
        return None

    closes = [p["price"] for p in recent if p.get("price") is not None]
    if len(closes) < 2:
        return None

    lo = min(closes)
    hi = max(closes)
    rng = hi - lo or 1

    # Map prices to SVG coordinate space (x: 0→W, y: 0→H)
    # NOTE: NO H- inversion here. Frontend SparklineSvg applies (height - y) for SVG coords.
    # Price UP → y UP in data → SVG (H - y) → line goes UP visually. Correct!
    W, H = SPARKLINE_W, SPARKLINE_H
    points = [
        [round(idx / (len(closes) - 1) * W, 1), round((c - lo) / rng * H, 1)]
        for idx, c in enumerate(closes)
    ]

    return {
        "points": points,
        "positive": bool(closes[-1] >= closes[0]),
    }


# ─── Benchmark fetching (from fund_cron.py) ─────────────────────────────────

BENCHMARK_DEFAULTS = {
    "ALTIN":   "GC=F",
    "BYF":     "^GSPC",
    "KFF":     "^IXIC",
    "OKS":     "XU100.IS",
    "OKS_B":   "XU100.IS",
    "DÖVİZ":   "TRY=X",
    "SRF":     "XU100.IS",
    "VFF":     "XU100.IS",
    "DEFAULT": "XU100.IS",
}

ALWAYS_FETCH = ["EURTRY=X", "TRY=X"]


def fetch_yahoo_json(url: str, timeout: int = 15) -> dict:
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0",
            "Accept": "application/json",
        })
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read())
    except Exception as e:
        LOG(f"Yahoo fetch failed: {e}", "WARN")
        return {}


def fetch_benchmark_prices(symbols: list[str], lookback_days: int = 35) -> dict[str, list[dict]]:
    """Fetch benchmark prices from Yahoo Finance. Returns {symbol: [{"date": "YYYY-MM-DD", "close": float}, ...]}"""
    result: dict[str, list[dict]] = {}
    period2 = int(time.time())
    period1 = period2 - (lookback_days + 10) * 86400

    for sym in symbols:
        url = (
            f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}"
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
        timestamps = (
            data.get("chart", {})
            .get("result", [{}])[0]
            .get("timestamp", [])
        )
        if not quotes or not timestamps:
            LOG(f"Benchmark {sym}: no data", "WARN")
            continue

        rows: list[dict] = []
        for i, (ts, close) in enumerate(zip(timestamps, quotes)):
            if close is None:
                continue
            d = datetime.utcfromtimestamp(ts).strftime("%Y-%m-%d")
            rows.append({"date": d, "close": round(float(close), 4)})
        result[sym] = rows
        LOG(f"Benchmark {sym}: {len(rows)} prices")
    return result


def upsert_benchmark_prices(bm_prices: dict[str, list[dict]]) -> int:
    """Upsert benchmark prices to benchmark_prices table. Uses PostgreSQL directly for multi-column upsert."""
    _db_url = SUPABASE_DB_URL
    total = 0
    if not bm_prices:
        return 0
    try:
        conn = psycopg2.connect(_db_url)
        cur = conn.cursor()
        for sym, points in bm_prices.items():
            if not points:
                continue
            for p in points:
                cur.execute("""
                    INSERT INTO benchmark_prices (symbol, date, close_price)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (symbol, date) DO UPDATE SET close_price = EXCLUDED.close_price
                """, (sym, p["date"], p["close"]))
                total += 1
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        LOG(f"upsert_benchmark_prices DB error: {e}", "ERROR")
    return total


# ─── Period returns ──────────────────────────────────────────────────────────

def compute_period_returns(
    sorted_prices: list[dict],
    latest_price: float,
    today_tr: str,
) -> dict:
    """Compute period returns as RATIO (not percentage)."""
    p1g = get_price_at_days_ago(sorted_prices, 1, today_tr)
    p1h = get_price_at_days_ago(sorted_prices, 7, today_tr)
    p1a = get_price_at_days_ago(sorted_prices, 30, today_tr)
    p3a = get_price_at_days_ago(sorted_prices, 90, today_tr)
    p6a = get_price_at_days_ago(sorted_prices, 180, today_tr)

    return {
        "return_1g": round((latest_price - p1g) / p1g, 6) if p1g and p1g > 0 else 0.0,
        "return_1h": round((latest_price - p1h) / p1h, 6) if p1h and p1h > 0 else 0.0,
        "return_1a": round((latest_price - p1a) / p1a, 6) if p1a and p1a > 0 else 0.0,
        "return_3a": round((latest_price - p3a) / p3a, 6) if p3a and p3a > 0 else 0.0,
        "return_6a": round((latest_price - p6a) / p6a, 6) if p6a and p6a > 0 else 0.0,
    }


# ─── Compute fund metrics ────────────────────────────────────────────────────

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

        # daily_change: today vs yesterday (Turkey timezone)
        today_price: Optional[float] = None
        yest_price: Optional[float] = None
        for p in reversed(sorted_ph):
            if today_price is None and p["date"] <= today_tr:
                today_price = p.get("price")
            if yest_price is None and p["date"] <= yest_tr:
                yest_price = p.get("price")
            if today_price is not None and yest_price is not None:
                break

        # Period returns (RATIO)
        period_rets = compute_period_returns(sorted_ph, latest_price, today_tr)

        # daily_change: stored as PERCENTAGE
        if today_price and yest_price and yest_price > 0 and today_price > 0:
            daily_change = round((today_price - yest_price) / yest_price * 100, 4)
            fund_updates.append({
                "code": fund["code"],
                "daily_change": daily_change,
                **period_rets,
            })

        # Sparkline
        sparkline = compute_sparkline(sorted_ph, days=30)
        if sparkline:
            sparkline_updates.append({
                "code": fund["code"],
                "sparkline": sparkline,
            })

    return fund_updates, sparkline_updates


def upsert_fund_metrics(fund_updates: list[dict]) -> int:
    """Upsert fund metrics using PostgreSQL batch INSERT with ON CONFLICT."""
    if not fund_updates:
        return 0
    METRIC_COLS = [
        "daily_change", "return_1g", "return_1h", "return_1a",
        "return_3a", "return_6a",
    ]
    try:
        conn = psycopg2.connect(SUPABASE_DB_URL)
        cur = conn.cursor()
        codes = [r["code"] for r in fund_updates]
        cur.execute(f"SELECT code, name FROM funds WHERE code = ANY(%s)", (codes,))
        name_map = {row[0]: row[1] for row in cur.fetchall()}
        values = []
        for r in fund_updates:
            code = r.get("code")
            name = name_map.get(code)
            if not code or name is None:
                continue
            row_vals = [code, name] + [r.get(k) for k in METRIC_COLS]
            values.append(row_vals)
        if not values:
            cur.close()
            conn.close()
            return 0
        keys = ["code", "name"] + METRIC_COLS
        set_clause = ", ".join([f"{k}=EXCLUDED.{k}" for k in METRIC_COLS])
        psycopg2.extras.execute_values(
            cur,
            f"INSERT INTO funds ({','.join(keys)}) VALUES %s ON CONFLICT (code) DO UPDATE SET {set_clause}",
            values,
            page_size=500,
        )
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        LOG(f"upsert_fund_metrics DB error: {e}", "ERROR")
        return 0
    return len(values)


def upsert_sparklines(sparkline_updates: list[dict]) -> int:
    """Upsert sparklines using PostgreSQL batch UPDATE (all funds exist after upsert_fund_metrics)."""
    if not sparkline_updates:
        return 0
    try:
        import json
        conn = psycopg2.connect(SUPABASE_DB_URL)
        cur = conn.cursor()
        values = [
            (json.dumps(r["sparkline"]), r["code"])
            for r in sparkline_updates
            if r.get("code") and r.get("sparkline")
        ]
        if not values:
            cur.close()
            conn.close()
            return 0
        psycopg2.extras.execute_values(
            cur,
            "UPDATE funds SET sparkline = data.sparkline::jsonb FROM (VALUES %s) AS data(sparkline, code) WHERE funds.code = data.code",
            values,
            page_size=500,
        )
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        LOG(f"upsert_sparklines DB error: {e}", "ERROR")
        return 0
    return len(values)

# ─── Category ranks ──────────────────────────────────────────────────────────

def compute_category_ranks(funds: list[dict]) -> list[dict]:
    """Rank funds within each fund_type by daily_change DESC (nulls last)."""
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
    """Upsert category ranks using PostgreSQL batch INSERT with ON CONFLICT."""
    if not rank_rows:
        return 0
    try:
        conn = psycopg2.connect(SUPABASE_DB_URL)
        cur = conn.cursor()
        now = datetime.utcnow().isoformat()
        values = [
            (r["fund_code"], r["category"], r["rank"], r["category_count"], r["percentile"], now)
            for r in rank_rows
        ]
        # Batch insert using execute_values for speed
        psycopg2.extras.execute_values(
            cur,
            """
            INSERT INTO fund_category_ranks (fund_code, category, rank, category_count, percentile, computed_at)
            VALUES %s
            ON CONFLICT (fund_code) DO UPDATE SET
                category = EXCLUDED.category,
                rank = EXCLUDED.rank,
                category_count = EXCLUDED.category_count,
                percentile = EXCLUDED.percentile,
                computed_at = EXCLUDED.computed_at
            """,
            values,
            page_size=500,
        )
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        LOG(f"upsert_category_ranks DB error: {e}", "ERROR")
        return 0
    return len(rank_rows)


# ─── Homepage stats ──────────────────────────────────────────────────────────

def pct_return_ratio(val: Optional[float]) -> Optional[float]:
    """Convert stored RATIO to percentage (×100)."""
    if val is None:
        return None
    return val * 100


def compute_homepage_stats(funds: list[dict], funds_with_history: Optional[list[dict]] = None) -> dict:
    """Compute homepage_stats payload."""
    # Fetch existing benchmarks_data AND category_sparklines to preserve them
    existing = query_table("homepage_stats", "benchmarks_data,category_sparklines", filters={"id": "eq.1"})
    benchmarks_data = None
    existing_category_sparklines = None
    if existing and existing[0]:
        benchmarks_data = existing[0].get("benchmarks_data")
        existing_category_sparklines = existing[0].get("category_sparklines")

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
    for cat, s in sorted(cat_map.items()):
        avg_change = s["sum_daily_change"] / s["change_count"] if s["change_count"] else None
        category_stats[cat] = {
            "fund_count": s["count"],
            "total_market_cap": round(s["total_market_cap"], 2),
            "avg_daily_change": round(avg_change, 4) if avg_change is not None else None,
            "avg_return_1w": round(s["aum_1w"] / s["sum_aum_1w"] * 100, 4) if s["sum_aum_1w"] > 0 else None,
            "avg_return_1m": round(s["aum_1m"] / s["sum_aum_1m"] * 100, 4) if s["sum_aum_1m"] > 0 else None,
            "avg_return_3m": round(s["aum_3m"] / s["sum_aum_3m"] * 100, 4) if s["sum_aum_3m"] > 0 else None,
            "avg_return_6m": round(s["aum_6m"] / s["sum_aum_6m"] * 100, 4) if s["sum_aum_6m"] > 0 else None,
        }

    total_market_cap = sum(f.get("market_cap") or 0 for f in funds)
    avg_daily_change = sum(
        f["daily_change"] for f in funds if f.get("daily_change") is not None
    ) / len(with_change) if with_change else None

    latest_date = (
        query_table("funds", "last_tefas_fetch", order="last_tefas_fetch.desc", limit=1, filters={"last_tefas_fetch": "not.is.null"})[0]["last_tefas_fetch"]
        if query_table("funds", "last_tefas_fetch", order="last_tefas_fetch.desc", limit=1, filters={"last_tefas_fetch": "not.is.null"}) else None
    )

    # ── Category sparklines (Turkish fund types from price_history) ─────────────
    # Preserve existing ETF sparklines from homepage_stats, compute Turkish fund sparklines from price_history
    category_sparklines: dict[str, dict] = {}
    if existing_category_sparklines:
        category_sparklines = existing_category_sparklines if isinstance(existing_category_sparklines, dict) else {}

    if funds_with_history:
        # Group funds with price_history by fund_type
        type_prices: dict[str, list[tuple[float, list[dict]]]] = {}  # fund_type -> [(aum, price_history)]
        for f in funds_with_history:
            ph = f.get("price_history")
            if not ph or not isinstance(ph, list) or len(ph) < 2:
                continue
            aum = f.get("market_cap") or 0
            if aum <= 0:
                continue
            ft = f.get("fund_type") or "OTHER"
            if ft not in type_prices:
                type_prices[ft] = []
            type_prices[ft].append((aum, ph))

        # Compute AUM-weighted average sparkline per Turkish fund type
        SPARKLINE_POINTS = 30
        for fund_type, fund_list in type_prices.items():
            # Sort all price_history entries by date, take last 30 data points
            # Build a common date grid from all funds
            all_dates: set[str] = set()
            for aum, ph in fund_list:
                for p in ph:
                    if isinstance(p, dict) and p.get("date") and p.get("price") is not None:
                        all_dates.add(p["date"])
            if not all_dates:
                continue
            sorted_dates = sorted(all_dates)[-SPARKLINE_POINTS:]
            if len(sorted_dates) < 2:
                continue

            # For each date, compute AUM-weighted average price
            weighted_prices: list[float] = []
            for d in sorted_dates:
                total_weighted_price = 0.0
                total_aum = 0.0
                for aum, ph in fund_list:
                    # Find closest price on or before this date
                    price_val = None
                    for p in sorted(ph, key=lambda x: x.get("date", ""), reverse=True):
                        if isinstance(p, dict) and p.get("date", "") <= d and p.get("price") is not None:
                            price_val = float(p["price"])
                            break
                    if price_val is not None:
                        total_weighted_price += price_val * aum
                        total_aum += aum
                if total_aum > 0:
                    weighted_prices.append(total_weighted_price / total_aum)

            if len(weighted_prices) < 2:
                continue

            # Determine positive/negative from weighted average price change
            first_price = weighted_prices[0]
            last_price = weighted_prices[-1]
            positive = last_price >= first_price

            # Normalize to 0-100 range for sparkline display
            lo = min(weighted_prices)
            hi = max(weighted_prices)
            rng = hi - lo if hi != lo else 1
            points = [
                [round(i / (len(weighted_prices) - 1) * 280), round(40 - (p - lo) / rng * 40)]
                for i, p in enumerate(weighted_prices)
            ]
            category_sparklines[fund_type] = {
                "sparkline": points,
                "positive": positive,
            }

    return {
        "id": 1,
        "latest_date": latest_date,
        "total_market_cap": round(total_market_cap, 2),
        "fund_count": len(funds),
        "avg_daily_change": round(avg_daily_change, 4) if avg_daily_change is not None else None,
        "top5_gainers": top5_gainers,
        "top5_losers": top5_losers,
        "top_funds": top_funds,
        "category_stats": category_stats,
        "category_sparklines": category_sparklines,
        "benchmarks_data": benchmarks_data,
    }


# ─── Main ────────────────────────────────────────────────────────────────────

def main():
    load_env()
    LOG("Starting fund_cascade")
    t0 = time.time()
    today_tr = to_date_str(turkey_now())
    yest_tr = to_date_str(turkey_now() - timedelta(days=1))
    LOG(f"today={today_tr}, yesterday={yest_tr}")

    test_mode = "--test" in sys.argv or "-t" in sys.argv

    # ── 1. Fetch all benchmark symbols from DB ──────────────────────────────
    funds_meta = query_table_paginated("funds", "code,fund_type,benchmark_symbol")
    LOG(f"Funds: {len(funds_meta)}")

    # Backfill missing benchmark_symbols
    for fund in funds_meta:
        if not fund.get("benchmark_symbol") and fund.get("fund_type"):
            bm = BENCHMARK_DEFAULTS.get(fund["fund_type"]) or BENCHMARK_DEFAULTS["DEFAULT"]
            url = f"{SUPABASE_URL}/rest/v1/funds?code=eq.{fund['code']}"
            rest_patch(url, {"benchmark_symbol": bm})
    LOG("benchmark_symbol backfill done")

    # Collect unique benchmark symbols
    unique_symbols = set()
    for fund in funds_meta:
        bm = fund.get("benchmark_symbol")
        if bm:
            unique_symbols.add(bm)
    for sym in ALWAYS_FETCH:
        unique_symbols.add(sym)
    unique_symbols = sorted(unique_symbols)

    # ── 2. Fetch + upsert benchmark prices ────────────────────────────────
    LOG(f"Fetching {len(unique_symbols)} benchmark symbols from Yahoo...")
    bm_prices = fetch_benchmark_prices(list(unique_symbols), lookback_days=35)
    bm_total = upsert_benchmark_prices(bm_prices)
    LOG(f"Benchmark prices: {bm_total} rows written")
    upsert_system_status(
        "last_benchmark_prices_cron",
        datetime.utcnow().isoformat(),
        "success",
        f"{len(unique_symbols)} symbols, {bm_total} prices",
    )

    # ── 3. Fetch all funds with price_history ─────────────────────────────
    LOG("Fetching funds with price_history...")
    conn = psycopg2.connect(SUPABASE_DB_URL)
    conn.cursor().execute("SET statement_timeout = '120000'")
    cur = conn.cursor()
    cur.execute("""
        SELECT id, code, name, fund_type, market_cap, price_history, currency
        FROM funds
        WHERE price_history IS NOT NULL
    """)
    rows = cur.fetchall()
    all_funds_raw = []
    for r in rows:
        all_funds_raw.append({
            "id": r[0], "code": r[1], "name": r[2], "fund_type": r[3],
            "market_cap": r[4], "price_history": r[5], "currency": r[6]
        })
    cur.close()
    conn.close()
    LOG(f"Total funds with price_history: {len(all_funds_raw)}")

    if test_mode:
        all_funds_raw = all_funds_raw[:5]
        LOG(f"TEST MODE: limiting to first {len(all_funds_raw)} funds")

    # ── 4. Compute fund metrics + sparklines ───────────────────────────────
    LOG("Computing fund metrics...")
    fund_updates, sparkline_updates = compute_fund_metrics(all_funds_raw, today_tr, yest_tr)
    LOG(f"  fund_updates: {len(fund_updates)}, sparkline_updates: {len(sparkline_updates)}")

    # ── 5. Upsert fund metrics ─────────────────────────────────────────────
    LOG("Upserting fund metrics...")
    fund_count = upsert_fund_metrics(fund_updates)
    LOG(f"  funds updated: {fund_count}/{len(fund_updates)}")

    # ── 6. Upsert sparklines ──────────────────────────────────────────────
    LOG("Upserting sparklines...")
    sparkline_count = upsert_sparklines(sparkline_updates)
    LOG(f"  sparklines upserted: {sparkline_count}/{len(sparkline_updates)}")

    # ── 7. Reload funds for stats computation ─────────────────────────────
    LOG("Reloading funds for homepage_stats...")
    # Fetch funds for stats using PostgreSQL directly
    LOG("Reloading funds for homepage_stats via PostgreSQL...")
    conn = psycopg2.connect(SUPABASE_DB_URL)
    cur = conn.cursor()
    cur.execute("""
        SELECT code, name, fund_type, market_cap, daily_change,
               return_1g, return_1h, return_1a, return_3a, return_6a
        FROM funds
    """)
    rows = cur.fetchall()
    cur.close()
    conn.close()
    funds_for_stats = []
    for r in rows:
        funds_for_stats.append({
            "code": r[0],
            "name": r[1] or "",
            "fund_type": r[2] or "OTHER",
            "market_cap": float(r[3]) if r[3] else 0.0,
            "daily_change": float(r[4]) if r[4] is not None else None,
            "return_1g": float(r[5]) if r[5] is not None else None,
            "return_1h": float(r[6]) if r[6] is not None else None,
            "return_1a": float(r[7]) if r[7] is not None else None,
            "return_3a": float(r[8]) if r[8] is not None else None,
            "return_6a": float(r[9]) if r[9] is not None else None,
        })
    LOG(f"  funds_for_stats: {len(funds_for_stats)}")

    # ── 8. Compute + upsert category ranks ─────────────────────────────────
    LOG("Computing category ranks...")
    rank_rows = compute_category_ranks(funds_for_stats)
    rank_count = upsert_category_ranks(rank_rows)
    LOG(f"  category ranks upserted: {rank_count}")

    # ── 9. Compute + upsert homepage_stats ────────────────────────────────
    LOG("Computing homepage_stats...")
    stats_payload = compute_homepage_stats(funds_for_stats, all_funds_raw)
    ok = upsert_table("homepage_stats", [stats_payload], conflict_col="id")
    if ok:
        LOG("  homepage_stats upserted OK")
    else:
        LOG("  homepage_stats upsert FAILED", "ERROR")

    # ── 10. Update system_status ───────────────────────────────────────────
    elapsed = round(time.time() - t0, 1)
    upsert_system_status(
        "last_fund_cascade",
        datetime.utcnow().isoformat(),
        "success",
        f"funds={len(fund_updates)}, sparklines={sparkline_count}, ranks={rank_count}, elapsed={elapsed}s",
    )
    LOG(f"Done in {elapsed}s")


if __name__ == "__main__":
    main()
