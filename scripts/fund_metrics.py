#!/usr/bin/env python3
"""
fund_metrics.py — Risk-adjusted performance metrics for every fund.

Ports the old Vercel route src/app/api/old_files/fund-metrics-cron/route.ts
(deleted in commit c55f37b on 2026-05-08) so the metrics keep refreshing.
The Mac runs this because TEFAS/yfinance traffic from US-hosted Vercel IPs
gets throttled or blocked.

Reads:  system_rates, benchmark_prices, funds.price_history
Writes: fund_metrics (Sharpe/Sortino/Calmar/Beta/Alpha/MaxDD/…)

Schedule (launchd): weekdays at 13:30 UTC (16:30 TR), after fund_cascade.
Usage: python3 scripts/fund_metrics.py
"""

import math
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

import psycopg2
import psycopg2.extras

sys.path.insert(0, str(Path(__file__).parent))

from cron_shared import (
    SUPABASE_URL,
    SUPABASE_DB_URL,
    HEADERS,
    load_env,
    rest_get,
    rest_post,
    upsert_system_status,
    get_logger,
)

load_env()
LOG = get_logger("fund_metrics")

TRADING_DAYS = 252
MIN_HISTORY = 30
MIN_DAILY_RETURNS = 20
BENCHMARK_WINDOW_DAYS = 35
UPSERT_BATCH = 100


# ─── Math helpers ────────────────────────────────────────────────────────────

def daily_returns(price_history: list[dict]) -> list[float]:
    """Convert sorted-by-date price_history into a list of pct returns."""
    sorted_h = sorted(price_history, key=lambda p: p.get("date", ""))
    out: list[float] = []
    for i in range(1, len(sorted_h)):
        prev = sorted_h[i - 1].get("price")
        curr = sorted_h[i].get("price")
        if prev and prev > 0 and curr is not None:
            out.append((curr - prev) / prev)
    return out


def std_dev(values: list[float]) -> float:
    if not values:
        return 0.0
    mean = sum(values) / len(values)
    var = sum((v - mean) ** 2 for v in values) / len(values)
    return math.sqrt(var)


def annualized_return(rets: list[float]) -> float:
    if not rets:
        return 0.0
    return (sum(rets) / len(rets)) * TRADING_DAYS


def annualized_vol(rets: list[float]) -> float:
    return std_dev(rets) * math.sqrt(TRADING_DAYS)


def max_drawdown(price_history: list[dict]) -> float:
    sorted_h = sorted(price_history, key=lambda p: p.get("date", ""))
    if not sorted_h:
        return 0.0
    max_dd = 0.0
    peak = sorted_h[0].get("price") or 0
    for p in sorted_h:
        price = p.get("price")
        if price is None or price <= 0:
            continue
        if price > peak:
            peak = price
        dd = (price - peak) / peak if peak > 0 else 0
        if dd < max_dd:
            max_dd = dd
    return max_dd


def sortino_ratio(rets: list[float], rf: float) -> float:
    if len(rets) < MIN_DAILY_RETURNS:
        return 0.0
    negs = [r for r in rets if r < 0]
    if not negs:
        return 0.0
    # Match the original TS: divide by total n, not negative count.
    mean_neg = sum(negs) / len(rets)
    downside_var = sum((r - mean_neg) ** 2 for r in negs) / len(rets)
    downside_std = math.sqrt(downside_var) * math.sqrt(TRADING_DAYS)
    if downside_std == 0:
        return 0.0
    return (annualized_return(rets) - rf) / downside_std


def pearson_corr(x: list[float], y: list[float]) -> float:
    n = min(len(x), len(y))
    if n < 4:
        return 0.0
    sx = sum(x[:n])
    sy = sum(y[:n])
    sxy = sum(x[i] * y[i] for i in range(n))
    sx2 = sum(v * v for v in x[:n])
    sy2 = sum(v * v for v in y[:n])
    num = n * sxy - sx * sy
    den_sq = (n * sx2 - sx * sx) * (n * sy2 - sy * sy)
    if den_sq <= 0:
        return 0.0
    return num / math.sqrt(den_sq)


def align_returns(fund_hist: list[dict], bm_prices: list[dict]) -> tuple[list[float], list[float]]:
    """Match fund and benchmark by date, returning paired daily returns."""
    sorted_fund = sorted(fund_hist, key=lambda p: p.get("date", ""))
    sorted_bm = sorted(bm_prices, key=lambda p: p.get("date", ""))

    bm_map: dict[str, float] = {}
    for i in range(1, len(sorted_bm)):
        prev = sorted_bm[i - 1].get("close")
        curr = sorted_bm[i].get("close")
        if prev and prev > 0 and curr is not None:
            date = (sorted_bm[i].get("date") or "")[:10]
            bm_map[date] = (curr - prev) / prev

    f_rets: list[float] = []
    b_rets: list[float] = []
    for i in range(1, len(sorted_fund)):
        prev = sorted_fund[i - 1].get("price")
        curr = sorted_fund[i].get("price")
        if not prev or prev <= 0:
            continue
        date = (sorted_fund[i].get("date") or "")[:10]
        if date in bm_map:
            f_rets.append((curr - prev) / prev)
            b_rets.append(bm_map[date])
    return f_rets, b_rets


def beta_alpha(fund_hist: list[dict], bm_prices: list[dict], rf: float) -> tuple[float, float]:
    f_rets, b_rets = align_returns(fund_hist, bm_prices)
    if len(f_rets) < MIN_DAILY_RETURNS:
        return 0.0, 0.0
    mean_f = sum(f_rets) / len(f_rets)
    mean_b = sum(b_rets) / len(b_rets)
    cov = sum((f_rets[i] - mean_f) * (b_rets[i] - mean_b) for i in range(len(f_rets))) / len(f_rets)
    var_b = sum((r - mean_b) ** 2 for r in b_rets) / len(b_rets)
    beta = cov / var_b if var_b > 0 else 0.0
    ann_f = mean_f * TRADING_DAYS
    ann_b = mean_b * TRADING_DAYS
    alpha = ann_f - (rf + beta * (ann_b - rf))
    return round(beta, 3), round(alpha, 4)


# ─── DB I/O ──────────────────────────────────────────────────────────────────

def read_risk_free_rates() -> dict[str, float]:
    """system_rates rows → currency → annualized risk-free rate (ratio)."""
    rates = rest_get(f"{SUPABASE_URL}/rest/v1/system_rates?select=currency,rate_annualized")
    out: dict[str, float] = {}
    for r in rates or []:
        cur = r.get("currency")
        if not cur:
            continue
        # PostgREST returns numeric as string
        try:
            out[cur] = float(r.get("rate_annualized") or 0)
        except (TypeError, ValueError):
            out[cur] = 0.0
    out.setdefault("TRY", 0.45)
    out.setdefault("USD", 0.0)
    out.setdefault("EUR", 0.0)
    return out


def read_benchmark_prices() -> dict[str, list[dict]]:
    cutoff = (datetime.now(timezone.utc) - timedelta(days=BENCHMARK_WINDOW_DAYS)).strftime("%Y-%m-%d")
    url = (
        f"{SUPABASE_URL}/rest/v1/benchmark_prices"
        f"?select=symbol,date,close_price&date=gte.{cutoff}"
    )
    rows = rest_get(url)
    out: dict[str, list[dict]] = {}
    for p in rows or []:
        sym = p.get("symbol")
        if not sym:
            continue
        out.setdefault(sym, []).append({"date": p["date"], "close": p["close_price"]})
    return out


def read_funds_paginated() -> list[dict]:
    """Pull all funds with price_history via direct Postgres.

    PostgREST times out on this query because price_history (5Y daily JSONB)
    can run 30-100KB per row. Direct PG keeps the whole 2400-fund pull under
    10 seconds.
    """
    conn = psycopg2.connect(SUPABASE_DB_URL)
    funds: list[dict] = []
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                SELECT id, code, price_history, benchmark_symbol, currency
                  FROM funds
                 WHERE price_history IS NOT NULL
                """
            )
            for row in cur:
                funds.append({
                    "id": row["id"],
                    "code": row["code"],
                    "price_history": row["price_history"],
                    "benchmark_symbol": row["benchmark_symbol"],
                    "currency": row["currency"],
                })
    finally:
        conn.close()
    return funds


def round_r(value: float, places: int) -> float:
    return round(value, places)


def compute_for_fund(fund: dict, rates: dict[str, float], bm_map: dict[str, list[dict]]) -> Optional[dict]:
    history = fund.get("price_history") or []
    if len(history) < MIN_HISTORY:
        return None
    currency = fund.get("currency") or "TRY"
    rf = rates.get(currency, rates.get("TRY", 0.45))
    rets = daily_returns(history)
    if len(rets) < MIN_DAILY_RETURNS:
        return None

    ann_ret = annualized_return(rets)
    ann_vol = annualized_vol(rets)
    mdd = max_drawdown(history)
    sharpe = (ann_ret - rf) / ann_vol if ann_vol > 0 else 0.0
    sortino = sortino_ratio(rets, rf)
    calmar = ann_ret / abs(mdd) if abs(mdd) > 0 else 0.0

    beta = alpha = tracking_err = info_ratio = r_sq = 0.0
    bm_sym = fund.get("benchmark_symbol")
    if bm_sym and bm_sym in bm_map:
        bm_prices = bm_map[bm_sym]
        beta, alpha = beta_alpha(history, bm_prices, rf)
        f_rets, b_rets = align_returns(history, bm_prices)
        if len(f_rets) >= MIN_DAILY_RETURNS:
            corr = pearson_corr(f_rets, b_rets)
            r_sq = corr * corr
            te_series = [f_rets[i] - b_rets[i] for i in range(len(f_rets))]
            mean_te = sum(te_series) / len(te_series)
            tracking_err = math.sqrt(
                sum((e - mean_te) ** 2 for e in te_series) / len(te_series)
            ) * math.sqrt(TRADING_DAYS)
            ann_excess = annualized_return(f_rets) - annualized_return(b_rets)
            info_ratio = ann_excess / tracking_err if tracking_err > 0 else 0.0

    best = max(rets) if rets else 0.0
    worst = min(rets) if rets else 0.0
    negs = [r for r in rets if r < 0]
    mean_neg = sum(negs) / len(rets) if negs else 0.0
    downside_dev = math.sqrt(
        sum((r - mean_neg) ** 2 for r in negs) / len(rets)
    ) if negs else 0.0

    return {
        "fund_id": fund["id"],
        "fund_code": fund["code"],
        "sharpe_ratio": round_r(sharpe, 3),
        "sortino_ratio": round_r(sortino, 3),
        "calmar_ratio": round_r(calmar, 3),
        "beta": beta,
        "alpha": alpha,
        "max_drawdown": round_r(mdd, 5),
        "annualized_return": round_r(ann_ret, 5),
        "annualized_volatility": round_r(ann_vol, 5),
        "risk_free_rate": round_r(rf, 5),
        "downside_deviation": round_r(downside_dev, 5),
        "best_day": round_r(best, 5),
        "worst_day": round_r(worst, 5),
        "tracking_error": round_r(tracking_err, 3),
        "info_ratio": round_r(info_ratio, 3),
        "r_squared": round_r(r_sq, 3),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }


def main() -> int:
    start = time.time()
    LOG("Starting fund_metrics")

    rates = read_risk_free_rates()
    LOG(f"  risk_free_rates: {rates}")

    bm_map = read_benchmark_prices()
    LOG(f"  benchmark series loaded: {len(bm_map)} symbols")

    funds = read_funds_paginated()
    LOG(f"  funds with price_history: {len(funds)}")

    metrics: list[dict] = []
    errors = 0
    for f in funds:
        try:
            m = compute_for_fund(f, rates, bm_map)
            if m:
                metrics.append(m)
        except Exception as e:  # noqa: BLE001
            errors += 1
            LOG(f"  fund {f.get('code')}: {e}", "WARN")

    LOG(f"  computed metrics: {len(metrics)} (errors={errors})")

    upserted = 0
    upsert_url = f"{SUPABASE_URL}/rest/v1/fund_metrics?on_conflict=fund_id"
    for i in range(0, len(metrics), UPSERT_BATCH):
        batch = metrics[i:i + UPSERT_BATCH]
        if rest_post(upsert_url, batch, conflict_col="fund_id"):
            upserted += len(batch)
        else:
            LOG(f"  upsert batch {i} FAILED", "ERROR")

    elapsed = round(time.time() - start, 1)
    LOG(f"Done in {elapsed}s — upserted {upserted}/{len(metrics)}, errors={errors}")

    upsert_system_status(
        "last_fund_metrics_cron",
        datetime.now(timezone.utc).isoformat(),
    )

    return 0


if __name__ == "__main__":
    sys.exit(main())
