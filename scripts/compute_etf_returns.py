#!/usr/bin/env python3
"""
Compute TRY returns (1M, 3M, 6M) for all ETFs in foreign_etf_prices table.
Writes back to foreign_etfs.one_month_return_try, three_month_return_try, six_month_return_try.

Usage:
    python3 compute_etf_returns.py
"""

import yfinance as yf
import pandas as pd
import urllib.request
import json
import time
import warnings
from datetime import date, datetime, timedelta
from typing import Optional

warnings.filterwarnings('ignore')

SUPABASE_URL = "https://oqkobptbvcazifpvjwfz.supabase.co"
SUPABASE_KEY = "sb_publishable__GPrsdfKRZCMZE8to916iQ_Izv9naG-"
HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=representation"
}


def supabase_query(table: str, select: str, filters: str = "") -> list:
    url = f"{SUPABASE_URL}/rest/v1/{table}?select={select}"
    if filters:
        url += "&" + filters
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read())


def supabase_rpc(rpc_name: str, params: dict):
    """Call a Supabase RPC function."""
    url = f"{SUPABASE_URL}/rest/v1/rpc/{rpc_name}"
    payload = json.dumps(params)
    req = urllib.request.Request(url, data=payload.encode(), method="POST",
        headers={**HEADERS})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read())


def fetch_exchange_rates() -> dict:
    """Fetch current USD/TRY, EUR/TRY, GBP/TRY rates."""
    rates = {}
    for base, ticker in [("USD", "USDTRY=X"), ("EUR", "EURTRY=X"), ("GBP", "GBPTRY=X")]:
        try:
            t = yf.Ticker(ticker)
            p = t.info.get("regularMarketPrice")
            if p:
                rates[base] = float(p)
        except:
            pass
    print(f"  FX rates: {rates}")
    return rates


def get_price_points(symbol: str, days: int = 730) -> Optional[pd.Series]:
    """Get daily close prices for symbol going back `days` days."""
    try:
        start = date.today() - timedelta(days=days)
        df = yf.download(symbol, start=str(start), interval="1d",
                        progress=False, auto_adjust=True, timeout=15)
        if df is None or df.empty:
            return None
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = [c[1] if isinstance(c, tuple) else c for c in df.columns]
        series = df["Close"].dropna()
        if series.empty:
            return None
        series.index = series.index.tz_localize(None) if series.index.tz else series.index
        series.index = series.index.normalize()
        return series
    except Exception as e:
        return None


def calc_return(series: pd.Series, days: int, fx_today: float, fx_start: float) -> Optional[float]:
    """TL return over the trailing window. Each price is converted to TL with
    the FX rate ON THAT DATE — multiplying the USD return by `fx_today` (the
    bug this replaces) silently mixed dollar and lira and produced numbers
    like +8.7% TL for ONDL while the fund actually fell 29% in TL terms."""
    if series is None or len(series) < 5:
        return None
    today = series.index.max()
    start_dt = today - timedelta(days=days)
    p_today_usd = float(series.iloc[-1])
    p_start_usd = None
    for dt in series.index:
        if dt >= pd.Timestamp(start_dt.date()):
            p_start_usd = float(series.loc[dt])
            break
    if p_start_usd is None or p_start_usd == 0 or fx_start <= 0:
        return None
    p_today_tl = p_today_usd * fx_today
    p_start_tl = p_start_usd * fx_start
    return round((p_today_tl / p_start_tl) - 1, 6)


def upsert_returns(symbol: str, ret_1m: Optional[float],
                   ret_3m: Optional[float], ret_6m: Optional[float]) -> bool:
    url = f"{SUPABASE_URL}/rest/v1/foreign_etfs"
    payload = {
        "symbol": symbol,
        "one_month_return_try": ret_1m,
        "three_month_return_try": ret_3m,
        "six_month_return_try": ret_6m,
    }
    # Remove None values so we don't overwrite with null
    payload = {k: v for k, v in payload.items() if v is not None}
    if not payload:
        return False
    # Use PATCH to update existing row
    # First get the row id
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/foreign_etfs?symbol=eq.{symbol}&limit=1&select=id",
        headers=HEADERS
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        rows = json.loads(resp.read())
    if not rows:
        return False
    row_id = rows[0]["id"]
    patch_payload = json.dumps(payload)
    patch_req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/foreign_etfs?id=eq.{row_id}",
        data=patch_payload.encode(),
        method="PATCH",
        headers={**HEADERS, "Prefer": "return=representation"}
    )
    try:
        with urllib.request.urlopen(patch_req, timeout=15) as resp:
            return resp.status in (200, 206)
    except Exception as e:
        print(f"    PATCH error for {symbol}: {e}")
        return False


def main():
    print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Computing ETF TRY returns")
    print("=" * 60)

    # Get all ETF symbols with current prices
    print("\n[1/2] Fetching ETF list...")
    etfs = supabase_query("foreign_etfs", "symbol, price", "limit=2000")
    print(f"  Total ETFs in DB: {len(etfs)}")

    # Get FX rates — both current and 30/90/180-day-ago for proper TL return.
    # The previous implementation multiplied USD return by today's FX, which
    # silently mixed dollar and lira (ONDL: -29% TL actual, +9% TL written).
    print("\n[2/2] Fetching FX rates (today + historical)...")
    fx_rates = fetch_exchange_rates()
    usd_try_today = fx_rates.get("USD", 1.0)
    # Pull benchmark_prices TRY=X history so we can find the rate on the
    # window's start date. Falls back to today's rate if no history.
    fx_history_rows = supabase_query(
        "benchmark_prices",
        "date,close_price",
        "symbol=eq.TRY=X&order=date.desc&limit=300",
    ) or []
    fx_by_date: dict[str, float] = {}
    for r in fx_history_rows:
        d = str(r.get("date") or "")[:10]
        v = r.get("close_price")
        try:
            v_f = float(v) if v is not None else None
        except (TypeError, ValueError):
            v_f = None
        if d and v_f and v_f > 0:
            fx_by_date[d] = v_f
    sorted_fx = sorted(fx_by_date.keys())

    def fx_at(target_date: str) -> float:
        """Return the FX rate as of target_date (forward-walks if missing)."""
        # Closest date on or before target_date
        for d in reversed(sorted_fx):
            if d <= target_date:
                return fx_by_date[d]
        # Earlier than any rate we have → use the oldest known
        return fx_by_date[sorted_fx[0]] if sorted_fx else usd_try_today

    updated = 0
    skipped = 0
    errors = 0

    for etf in etfs:
        sym = etf.get("symbol")
        if not sym:
            continue

        # Try to get price from DB first
        prices = supabase_query(
            "foreign_etf_prices",
            "date, close",
            f"symbol=eq.{sym}&order=date.desc&limit=730"
        )

        if not prices or len(prices) < 5:
            skipped += 1
            continue

        # Build series from DB prices
        df_prices = pd.DataFrame(prices)
        df_prices['date'] = pd.to_datetime(df_prices['date'])
        df_prices = df_prices.sort_values('date')
        df_prices = df_prices.set_index('date')['close']
        df_prices.index = df_prices.index.normalize()

        # Compute returns by converting each endpoint with its own FX rate.
        today_iso = date.today().isoformat()
        d30 = (date.today() - timedelta(days=30)).isoformat()
        d90 = (date.today() - timedelta(days=90)).isoformat()
        d180 = (date.today() - timedelta(days=180)).isoformat()
        ret_1m = calc_return(df_prices, 30, fx_at(today_iso), fx_at(d30))
        ret_3m = calc_return(df_prices, 90, fx_at(today_iso), fx_at(d90))
        ret_6m = calc_return(df_prices, 180, fx_at(today_iso), fx_at(d180))

        if ret_1m is None and ret_3m is None and ret_6m is None:
            skipped += 1
            continue

        ok = upsert_returns(sym, ret_1m, ret_3m, ret_6m)
        if ok:
            updated += 1
            print(f"  {sym}: 1M={ret_1m*100:.1f}% 3M={ret_3m*100:.1f}% 6M={ret_6m*100:.1f}%" if ret_1m else f"  {sym}: OK (partial)")
        else:
            errors += 1

        time.sleep(0.1)  # Be gentle

    print(f"\nDONE: {updated} updated, {skipped} skipped, {errors} errors")


if __name__ == "__main__":
    main()
