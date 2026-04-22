#!/usr/bin/env python3
"""
ETF Daily Cron Job — runs every day after US market close (~22:00 Turkey).
1. Fetches today's close prices for all ETFs (incremental update)
2. Also fetches prices for any NEW ETFs added since last run
3. Recomputes 1M, 3M, 6M TRY returns and updates foreign_etfs table

Usage:
    python3 etf_daily_cron.py

Cron example (run at 22:00 Turkey daily):
    0 22 * * * cd /Users/admin/Desktop/projects/fon-app && ./venv/bin/python3 scripts/etf_daily_cron.py >> logs/etf_cron.log 2>&1
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
    import urllib.parse
    params = [("select", select)]
    if filters:
        for f in filters.split("&"):
            if "=" in f:
                k, v = f.split("=", 1)
                params.append((k, v))
    encoded = urllib.parse.urlencode(params)
    url = f"{SUPABASE_URL}/rest/v1/{table}?{encoded}"
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read())


def supabase_upsert(table: str, rows: list[dict], conflict_col: str) -> bool:
    if not rows:
        return True
    url = f"{SUPABASE_URL}/rest/v1/{table}"
    payload = json.dumps(rows)
    req = urllib.request.Request(
        url, data=payload.encode(), method="POST",
        headers={**HEADERS, "Prefer": f"resolution=merge-duplicates, conflict={conflict_col}"}
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            body = resp.read()
            if body:
                result = json.loads(body)
                if isinstance(result, list):
                    print(f"    → {len(result)} rows upserted")
            return True
    except Exception as e:
        print(f"    → {table} ERROR: {e}")
        return False


def supabase_patch(table: str, row_id: int, payload: dict) -> bool:
    """Update a row by ID."""
    url = f"{SUPABASE_URL}/rest/v1/{table}?id=eq.{row_id}"
    data = json.dumps(payload)
    req = urllib.request.Request(url, data=data.encode(), method="PATCH",
        headers={**HEADERS})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status in (200, 204)
    except Exception as e:
        print(f"    PATCH ERROR: {e}")
        return False


def fetch_exchange_rate(ticker: str) -> Optional[float]:
    """Fetch a single FX rate."""
    try:
        t = yf.Ticker(ticker)
        p = t.info.get("regularMarketPrice")
        if p:
            return float(p)
    except:
        pass
    return None


def get_fx_rates() -> dict:
    """Get USD/TRY, EUR/TRY, GBP/TRY."""
    rates = {}
    for base, ticker in [("USD", "USDTRY=X"), ("EUR", "EURTRY=X"), ("GBP", "GBPTRY=X")]:
        r = fetch_exchange_rate(ticker)
        if r:
            rates[base] = r
            print(f"  {base}/TRY = {r:.4f}")
    return rates


def get_price_series(symbol: str, days: int = 730) -> Optional[pd.Series]:
    """Download price series for one symbol."""
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


def calc_return(series: pd.Series, days: int, fx_rate: float) -> Optional[float]:
    """Calculate return over last `days` calendar days, converted to TRY."""
    if series is None or len(series) < 5:
        return None
    today = series.index.max()
    start_dt = today - timedelta(days=days)
    p_today = float(series.iloc[-1])
    p_start = None
    for dt in series.index:
        if dt >= pd.Timestamp(start_dt.date()):
            p_start = float(series.loc[dt])
            break
    if p_start is None or p_start == 0:
        return None
    return round((p_today / p_start - 1) * fx_rate, 6)


def fetch_latest_prices_batch(symbols: list[str]) -> dict[str, float]:
    """Get latest close price for each symbol using yfinance batch download."""
    result = {}
    BATCH = 50
    for i in range(0, len(symbols), BATCH):
        batch_syms = symbols[i:i+BATCH]
        try:
            df = yf.download(" ".join(batch_syms), period="5d", interval="1d",
                           progress=False, auto_adjust=True, timeout=30)
            if df is None or df.empty:
                continue
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = [c[1] if isinstance(c, tuple) else c for c in df.columns]
            for sym in batch_syms:
                if sym in df.columns:
                    col = df[sym].dropna()
                    if not col.empty:
                        result[sym] = round(float(col.iloc[-1]), 4)
        except Exception as e:
            print(f"    Batch error: {e}")
        time.sleep(0.5)
    return result


def get_row_id(table: str, symbol: str) -> Optional[int]:
    rows = supabase_query(table, "id", f"symbol=eq.{symbol}&limit=1")
    return rows[0]["id"] if rows else None


def main():
    print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] ETF Daily Cron")
    print("=" * 60)

    # ── Step 1: FX rates ────────────────────────────────────────────────
    print("\n[1/4] Fetching FX rates...")
    fx_rates = get_fx_rates()
    usd_try = fx_rates.get("USD", 1.0)
    if not fx_rates:
        print("  WARNING: No FX rates fetched, using 1.0")

    # ── Step 2: Get all ETFs from DB ────────────────────────────────────
    print("\n[2/4] Fetching ETF list from DB...")
    etfs = supabase_query("foreign_etfs", "symbol, id", "limit=5000")
    print(f"  Total ETFs in DB: {len(etfs)}")

    # ── Step 3: Download latest prices (incremental) ────────────────────
    print("\n[3/4] Fetching latest prices...")
    symbols = [e["symbol"] for e in etfs if e.get("symbol")]
    latest_prices = fetch_latest_prices_batch(symbols)
    print(f"  Got prices for {len(latest_prices)} ETFs")

    # Build price rows to upsert
    today_str = date.today().isoformat()
    price_rows = []
    for sym, price in latest_prices.items():
        price_rows.append({"symbol": sym, "date": today_str, "close": price})

    if price_rows:
        print(f"  Upserting {len(price_rows)} today's price rows...")
        supabase_upsert("foreign_etf_prices", price_rows, "symbol")

    # ── Step 4: Compute returns for all ETFs ────────────────────────────
    print("\n[4/4] Computing 1M/3M/6M TRY returns...")
    updated = 0
    skipped = 0
    errors = 0

    for etf in etfs:
        sym = etf["symbol"]
        row_id = etf.get("id") or get_row_id("foreign_etfs", sym)
        if not row_id:
            continue

        # Get price history from DB
        prices = supabase_query(
            "foreign_etf_prices", "date, close",
            f"symbol=eq.{sym}&order=date.desc&limit=730"
        )

        if not prices or len(prices) < 5:
            skipped += 1
            continue

        df_prices = pd.DataFrame(prices)
        df_prices['date'] = pd.to_datetime(df_prices['date'])
        df_prices = df_prices.sort_values('date')
        df_prices = df_prices.set_index('date')['close']
        df_prices.index = df_prices.index.normalize()

        ret_1m = calc_return(df_prices, 30, usd_try)
        ret_3m = calc_return(df_prices, 90, usd_try)
        ret_6m = calc_return(df_prices, 180, usd_try)

        # Only update fields that have data
        patch_data = {}
        if ret_1m is not None:
            patch_data["one_month_return_try"] = ret_1m
        if ret_3m is not None:
            patch_data["three_month_return_try"] = ret_3m
        if ret_6m is not None:
            patch_data["six_month_return_try"] = ret_6m
        patch_data["updated_at"] = datetime.utcnow().isoformat()

        if patch_data:
            ok = supabase_patch("foreign_etfs", row_id, patch_data)
            if ok:
                updated += 1
                if updated <= 20:
                    m1 = f"{ret_1m*100:.1f}%" if ret_1m else "—"
                    m3 = f"{ret_3m*100:.1f}%" if ret_3m else "—"
                    m6 = f"{ret_6m*100:.1f}%" if ret_6m else "—"
                    print(f"  {sym}: 1M={m1} 3M={m3} 6M={m6}")
            else:
                errors += 1
        else:
            skipped += 1

        time.sleep(0.05)  # Be gentle with DB

    print(f"\nDONE: {updated} updated, {skipped} skipped, {errors} errors")
    print(f"  FX: USD/TRY={usd_try:.4f}")


if __name__ == "__main__":
    main()
