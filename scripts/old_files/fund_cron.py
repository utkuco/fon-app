#!/usr/bin/env python3.11
"""
fund_cron.py — Fund daily metrics: benchmark prices, daily_change, sparklines, period returns.

Schedule (launchd):  Mon-Fri 05:15 UTC = 08:15 TR
Usage:               python3 scripts/fund_cron.py

Logic (from fund-cron-lib.ts):
  1. Fetch benchmark prices from Yahoo Finance (GC=F, ^GSPC, ^IXIC, XU100.IS, EURTRY=X, TRY=X)
  2. Backfill benchmark_symbol for funds missing one
  3. Compute daily_change = (todayPrice - yestPrice) / yestPrice * 100  [stored as %]
  4. Compute period returns: 1g, 1h(7d), 1a(30d), 3a(90d), 6a(180d)    [stored as ratio]
  5. Compute sparklines (last 30 days) — written to precomputed_funds
  6. Sync company names to funds table
"""

import sys
import time
import json
import math
from datetime import datetime, date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from cron_shared import (
    load_env, SUPABASE_URL, SUPABASE_KEY, HEADERS, upsert_system_status,
    upsert_table, query_table, query_table_paginated, get_logger,
)
import urllib.request

LOG = get_logger("fund_cron")

# ─── Benchmark Constants ──────────────────────────────────────────────────────

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

SPARKLINE_W = 280
SPARKLINE_H = 40

# ─── Yahoo Finance helpers ────────────────────────────────────────────────────

def fetch_yahoo_json(url: str, timeout: int = 15) -> dict:
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0",
            "Accept": "application/json",
        })
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read())
    except Exception as e:
        LOG(f"Yahoo fetch error: {e}", "WARN")
        return {}


def fetch_benchmark_prices(tickers: list[str], lookback_days: int = 30) -> dict[str, list[dict]]:
    """
    Fetch daily close prices for tickers from Yahoo Finance.
    Returns: { ticker: [{"date": "YYYY-MM-DD", "close": float}, ...] }
    """
    results = {}
    period2 = int(time.time())
    period1 = period2 - lookback_days * 86400

    for ticker in tickers:
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
        timestamps = (
            data.get("chart", {})
            .get("result", [{}])[0]
            .get("timestamp", [])
        )
        if not quotes or not timestamps:
            LOG(f"No quotes for {ticker}", "WARN")
            continue

        points = []
        for close, ts in zip(quotes, timestamps):
            if close is None or math.isnan(close):
                continue
            dt = datetime.utcfromtimestamp(ts)
            points.append({"date": dt.strftime("%Y-%m-%d"), "close": round(close, 4)})

        if points:
            results[ticker] = points
            LOG(f"  {ticker}: {len(points)} points, last_close={points[-1]['close']}")

    return results


def upsert_benchmark_prices(bm_data: dict[str, list[dict]]) -> int:
    total = 0
    for symbol, points in bm_data.items():
        rows = [
            {"symbol": symbol, "date": p["date"], "close_price": p["close"]}
            for p in points
        ]
        ok = upsert_table("benchmark_prices", rows, conflict_col="symbol,date")
        if ok:
            total += len(rows)
    return total


# ─── Date helpers ────────────────────────────────────────────────────────────

def to_date_str(d: datetime) -> str:
    return d.strftime("%Y-%m-%d")


def days_ago(n: int) -> datetime:
    return datetime.utcnow() - timedelta(days=n)


def turkey_now() -> datetime:
    """UTC+3 for Turkey."""
    return datetime.utcnow() + timedelta(hours=3)


# ─── Sparkline ────────────────────────────────────────────────────────────────

def compute_sparkline(closes: list[float], w: int = SPARKLINE_W, h: int = SPARKLINE_H):
    if len(closes) < 2:
        return None
    mn = min(closes)
    mx = max(closes)
    rng = mx - mn or 1
    points = [
        [round(i / (len(closes) - 1) * w, 4), round((c - mn) / rng * h, 4)]
        for i, c in enumerate(closes)
    ]
    positive = closes[-1] >= closes[0]
    return {"points": points, "positive": positive}


# ─── Period returns ──────────────────────────────────────────────────────────

def get_price_at_days_ago(
    sorted_prices: list[dict],  # [{"date": "...", "price": ...}] sorted ASC
    days: int,
    ref_date: str,  # "YYYY-MM-DD"
) -> float | None:
    cutoff = (datetime.strptime(ref_date, "%Y-%m-%d") - timedelta(days=days)).strftime("%Y-%m-%d")
    # Find last price on or before cutoff
    result = None
    for p in reversed(sorted_prices):
        if p["date"] <= cutoff:
            result = p["price"]
            break
    return result


# ─── Main ────────────────────────────────────────────────────────────────────

def main():
    load_env()
    LOG("Starting fund_cron")
    t0 = time.time()

    # ── 1. Fetch all benchmark symbols from DB ──────────────────────────────
    funds = query_table_paginated("funds", "code,fund_type,benchmark_symbol")
    LOG(f"Funds: {len(funds)}")

    # Backfill missing benchmark_symbols
    for fund in funds:
        if not fund.get("benchmark_symbol") and fund.get("fund_type"):
            bm = BENCHMARK_DEFAULTS.get(fund["fund_type"]) or BENCHMARK_DEFAULTS["DEFAULT"]
            # Update inline via REST
            from cron_shared import rest_patch
            url = f"{SUPABASE_URL}/rest/v1/funds?code=eq.{fund['code']}"
            rest_patch(url, {"benchmark_symbol": bm})
    LOG("benchmark_symbol backfill done")

    # Collect unique benchmark symbols
    unique_symbols = set()
    for fund in funds:
        bm = fund.get("benchmark_symbol")
        if bm:
            unique_symbols.add(bm)
    for sym in ALWAYS_FETCH:
        unique_symbols.add(sym)
    unique_symbols = sorted(unique_symbols)

    # ── 2. Fetch benchmark prices ────────────────────────────────────────────
    LOG(f"Fetching {len(unique_symbols)} benchmark symbols...")
    bm_prices = fetch_benchmark_prices(list(unique_symbols), lookback_days=30)
    bm_total = upsert_benchmark_prices(bm_prices)
    LOG(f"Benchmark prices: {bm_total} rows written")

    # Build benchmark map: symbol → {date: close}
    bm_map: dict[str, dict[str, float]] = {}
    for sym, points in bm_prices.items():
        bm_map[sym] = {p["date"]: p["close"] for p in points}

    upsert_system_status(
        "last_benchmark_prices_cron",
        datetime.utcnow().isoformat(),
        "success",
        f"{len(unique_symbols)} symbols, {bm_total} prices",
    )

    # ── 3. Load system_rates ─────────────────────────────────────────────────
    rates_rows = query_table("system_rates", "currency,rate_annualized")
    rate_map = {r["currency"]: r.get("rate_annualized", 0) for r in rates_rows}
    if "USD" not in rate_map:
        rate_map["USD"] = 0.0
    if "TRY" not in rate_map:
        rate_map["TRY"] = 0.45
    LOG(f"system_rates: {rate_map}")

    # ── 4. Fetch benchmark prices for the lookback window ───────────────────
    cutoff_35 = to_date_str(days_ago(35))
    bm_prices_35: dict[str, list[dict]] = {}
    for sym in unique_symbols:
        rows = query_table(
            "benchmark_prices", "date,close_price",
            filters={"symbol": f"eq.{sym}", "date": f"gte.{cutoff_35}"},
            order="date.asc",
        )
        if rows:
            bm_prices_35[sym] = [{"date": r["date"], "close": float(r["close_price"])} for r in rows]

    # ── 5. Fetch all funds with price_history ────────────────────────────────
    all_funds = query_table_paginated(
        "funds",
        "id,code,price_history,currency",
        filters={"price_history": "not.is.null"},
    )
    LOG(f"Funds with price_history: {len(all_funds)}")

    today_tr = to_date_str(turkey_now())
    yest_tr = to_date_str(turkey_now() - timedelta(days=1))

    daily_updates = []
    sparkline_updates = []

    for fund in all_funds:
        ph = fund.get("price_history", [])
        if not ph or len(ph) < 2:
            continue

        # Parse price_history: [{"date": "YYYY-MM-DD", "price": ...}, ...]
        if isinstance(ph, str):
            try:
                ph = json.loads(ph)
            except Exception:
                continue

        # Sort by date ASC
        sorted_ph = sorted(ph, key=lambda x: x.get("date", ""))
        latest_price = sorted_ph[-1].get("price")
        if not latest_price or latest_price <= 0:
            continue

        today_price = None
        yest_price = None
        for p in reversed(sorted_ph):
            if today_price is None and p["date"] <= today_tr:
                today_price = p.get("price")
            if yest_price is None and p["date"] <= yest_tr:
                yest_price = p.get("price")
            if today_price is not None and yest_price is not None:
                break

        # ── Period returns ─────────────────────────────────────────────────
        return_1g = 0.0
        return_1h = 0.0
        return_1a = 0.0
        return_3a = 0.0
        return_6a = 0.0

        p1g = get_price_at_days_ago(sorted_ph, 1, today_tr)
        if p1g and p1g > 0:
            return_1g = round((latest_price - p1g) / p1g, 6)
        p1h = get_price_at_days_ago(sorted_ph, 7, today_tr)
        if p1h and p1h > 0:
            return_1h = round((latest_price - p1h) / p1h, 6)
        p1a = get_price_at_days_ago(sorted_ph, 30, today_tr)
        if p1a and p1a > 0:
            return_1a = round((latest_price - p1a) / p1a, 6)
        p3a = get_price_at_days_ago(sorted_ph, 90, today_tr)
        if p3a and p3a > 0:
            return_3a = round((latest_price - p3a) / p3a, 6)
        p6a = get_price_at_days_ago(sorted_ph, 180, today_tr)
        if p6a and p6a > 0:
            return_6a = round((latest_price - p6a) / p6a, 6)

        # ── daily_change (stored as %) ──────────────────────────────────────
        if today_price and yest_price and yest_price > 0 and today_price > 0:
            change_pct = round((today_price - yest_price) / yest_price * 100, 4)
            daily_updates.append({
                "code": fund["code"],
                "daily_change": change_pct,
                "return_1g": return_1g,
                "return_1h": return_1h,
                "return_1a": return_1a,
                "return_3a": return_3a,
                "return_6a": return_6a,
            })

        # ── Sparkline (last 30 days from latest date) ───────────────────────
        last_date = sorted_ph[-1]["date"]
        cutoff_30 = to_date_str(datetime.strptime(last_date, "%Y-%m-%d") - timedelta(days=30))
        recent = [p for p in sorted_ph if p["date"] >= cutoff_30]
        if len(recent) >= 2:
            closes = [p["price"] for p in recent if p.get("price") is not None]
            if len(closes) >= 2:
                sparkline = compute_sparkline(closes)
                if sparkline:
                    sparkline_updates.append({
                        "code": fund["code"],
                        "sparkline": sparkline,
                    })

    # ── 6. Batch update funds table ──────────────────────────────────────────
    daily_count = 0
    for row in daily_updates:
        from cron_shared import rest_patch
        url = f"{SUPABASE_URL}/rest/v1/funds?code=eq.{row['code']}"
        ok = rest_patch(url, {
            "daily_change": row["daily_change"],
            "return_1g": row["return_1g"],
            "return_1h": row["return_1h"],
            "return_1a": row["return_1a"],
            "return_3a": row["return_3a"],
            "return_6a": row["return_6a"],
        })
        if ok:
            daily_count += 1

    LOG(f"funds table updated: {daily_count}/{len(daily_updates)}")

    # ── 7. Upsert precomputed_funds (sparklines) ─────────────────────────────
    precomputed_count = 0
    for row in sparkline_updates:
        url = f"{SUPABASE_URL}/rest/v1/precomputed_funds?code=eq.{row['code']}"
        from cron_shared import rest_patch
        ok = rest_patch(url, {"sparkline": row["sparkline"]})
        if not ok:
            # Try insert
            upsert_table("precomputed_funds", [{
                "code": row["code"],
                "sparkline": row["sparkline"],
            }], conflict_col="code")
        precomputed_count += 1

    LOG(f"precomputed_funds sparklines: {precomputed_count}")

    elapsed = round(time.time() - t0, 1)
    upsert_system_status(
        "last_fund_cron",
        datetime.utcnow().isoformat(),
        "success",
        f"funds_updated={daily_count}, sparklines={precomputed_count}, elapsed={elapsed}s",
    )
    LOG(f"Done in {elapsed}s")


if __name__ == "__main__":
    main()
