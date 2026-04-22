#!/usr/bin/env python3
"""
Yahoo Finance ALL ETF Scraper — OPTIMIZED v2
Uses NASDAQ symbol list as source of truth, batch downloads for prices,
individual info fetches with rate-limit handling.

Usage:
    python3 etf_scraper_all.py              # Full fetch
    python3 etf_scraper_all.py --prices-only # Prices only
"""

import yfinance as yf
import pandas as pd
import urllib.request
import json
import time
import csv
import io
import warnings
from datetime import date, datetime, timedelta
from typing import Optional

warnings.filterwarnings('ignore')

# ─── Config ───────────────────────────────────────────────────────────────────
SUPABASE_URL = "https://oqkobptbvcazifpvjwfz.supabase.co"
SUPABASE_KEY = "sb_publishable__GPrsdfKRZCMZE8to916iQ_Izv9naG-"
HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=representation"
}

# ─── NASDAQ ETF list ───────────────────────────────────────────────────────────
def get_nasdaq_etf_tickers() -> list[str]:
    """Fetch all NASDAQ-listed ETF tickers."""
    url = "https://www.nasdaqtrader.com/dynamic/symdir/nasdaqlisted.txt"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        content = resp.read().decode()
    lines = content.strip().split('\n')
    # Header: Symbol|Security Name|Market Category|Test Issue|Financial Status|Round Lot Size|ETF|NextShares
    etfs = []
    for line in lines[1:]:
        parts = line.split('|')
        if len(parts) >= 7 and parts[6] == 'Y':
            etfs.append(parts[0])
    print(f"  NASDAQ ETFs: {len(etfs)}")
    return etfs

# ─── NYSE ETF list ─────────────────────────────────────────────────────────────
def get_nyse_etf_tickers() -> list[str]:
    """Fetch NYSE/ARCA listed ETF tickers."""
    url = "https://www.nasdaqtrader.com/dynamic/symdir/otherlisted.txt"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        content = resp.read().decode()
    lines = content.strip().split('\n')
    # Header: ACT Symbol|Security Name|Exchange|CQS Symbol|ETF|Round Lot Size|Test Issue|NASDAQ Symbol
    etfs = set()
    for line in lines[1:]:
        parts = line.split('|')
        if len(parts) >= 5 and parts[4] == 'Y':
            etfs.add(parts[0])
    print(f"  NYSE/ARCA ETFs: {len(etfs)}")
    return list(etfs)

def get_all_us_etf_tickers() -> list[str]:
    """Get combined US ETF tickers from NASDAQ + NYSE."""
    nasdaq = set(get_nasdaq_etf_tickers())
    nyse = set(get_nyse_etf_tickers())
    all_etfs = sorted(nasdaq | nyse)
    print(f"  Combined US ETFs: {len(all_etfs)} (deduped)")
    return all_etfs

# ─── Supabase helpers ──────────────────────────────────────────────────────────
def supabase_upsert(table: str, rows: list[dict], conflict_col: str) -> bool:
    if not rows:
        return True
    url = f"{SUPABASE_URL}/rest/v1/{table}"
    payload = json.dumps(rows)
    req = urllib.request.Request(url, data=payload.encode(), method="POST",
        headers={**HEADERS, "Prefer": "resolution=merge-duplicates",
                 "On-Conflict": conflict_col})
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            body = resp.read()
            if body:
                result = json.loads(body)
                if isinstance(result, list):
                    print(f"    → {table}: {len(result)} rows")
            return True
    except Exception as e:
        print(f"    → {table} ERROR: {e}")
        return False

# ─── Exchange rates ────────────────────────────────────────────────────────────
def fetch_exchange_rates() -> dict[str, float]:
    rates = {}
    for base, ticker in [("USD","USDTRY=X"),("EUR","EURTRY=X"),("GBP","GBPTRY=X")]:
        try:
            t = yf.Ticker(ticker)
            p = t.info.get("regularMarketPrice")
            if p:
                rates[base] = float(p)
                print(f"  {base}/TRY = {p:.4f}")
        except Exception as e:
            print(f"  {base} rate error: {e}")
    return rates

def fetch_historical_fx() -> dict[str, pd.Series]:
    fx_series = {}
    for base, ticker in [("USD","USDTRY=X"),("EUR","EURTRY=X"),("GBP","GBPTRY=X")]:
        try:
            start = date.today() - timedelta(days=730)
            df = yf.download(ticker, start=str(start), interval="1d", progress=False, auto_adjust=True)
            if df is None or df.empty:
                continue
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = [c[1] if isinstance(c, tuple) else c for c in df.columns]
            series = df["Close"].dropna()
            if series.empty:
                continue
            series.index = series.index.tz_localize(None) if series.index.tz else series.index
            fx_series[base] = series
            print(f"  {base} FX: {len(series)} points")
        except Exception as e:
            print(f"  {base} FX error: {e}")
        time.sleep(1)
    return fx_series

# ─── Batch price download ───────────────────────────────────────────────────────
def batch_download_prices(symbols: list[str], period: str = "2y") -> dict[str, pd.Series]:
    """Download price series for multiple symbols. Returns {symbol: close_series}."""
    result = {}
    BATCH = 50
    for i in range(0, len(symbols), BATCH):
        batch_syms = symbols[i:i+BATCH]
        try:
            df = yf.download(" ".join(batch_syms), period=period, interval="1d",
                           progress=False, auto_adjust=True, timeout=30)
            if df is None or df.empty:
                continue
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = [c[1] if isinstance(c, tuple) else c for c in df.columns]
            for sym in batch_syms:
                if sym in df.columns:
                    col = df[sym].dropna()
                    if not col.empty:
                        result[sym] = col
        except Exception as e:
            print(f"    Batch error at {batch_syms[0]}: {e}")
            time.sleep(5)
    return result

# ─── Price → TRY return ────────────────────────────────────────────────────────
def calc_ytd_return_usd(series: pd.Series) -> Optional[float]:
    """Calculate YTD USD return from close series."""
    if series is None or len(series) < 5:
        return None
    closes = series.dropna()
    if closes.empty:
        return None
    closes.index = closes.index.tz_localize(None) if closes.index.tz else closes.index
    closes.index = closes.index.normalize()
    today_dt = closes.index.max()
    year_start = f"{today_dt.year}-01-01"
    p_today = float(closes.iloc[-1])
    p_ytd = None
    for dt in closes.index:
        if str(dt.date()) <= year_start:
            p_ytd = float(closes.loc[dt])
    if p_ytd and p_ytd > 0:
        return round(p_today / p_ytd - 1, 6)
    return None

def calc_try_return(series: pd.Series, currency: str, fx_series: dict) -> Optional[float]:
    """Calculate YTD TRY return from close series and FX rates."""
    if series is None or len(series) < 5 or not fx_series:
        return None
    closes = series.dropna()
    if closes.empty:
        return None
    closes.index = closes.index.tz_localize(None) if closes.index.tz else closes.index
    closes.index = closes.index.normalize()
    today_dt = closes.index.max()
    today_str = str(today_dt.date()) if hasattr(today_dt, "date") else str(today_dt)[:10]
    year_start = f"{today_dt.year}-01-01"
    p_today = float(closes.iloc[-1])
    p_ytd = None
    for dt in closes.index:
        if str(dt.date()) <= year_start:
            p_ytd = float(closes.loc[dt])
    if not p_ytd or p_ytd == 0:
        return None
    fx_base = "USD"
    if currency == "GBp":
        fx_base = "GBP"
    elif currency == "EUR":
        fx_base = "EUR"
    fx = fx_series.get(fx_base)
    if fx is None:
        return None
    fx.index = fx.index.tz_localize(None) if fx.index.tz else fx.index
    fx = fx.dropna()
    fx_today_str = today_str
    fx_ytd_str = year_start
    fx_today = None
    fx_ytd = None
    for dt in fx.index:
        if str(dt.date()) <= fx_today_str:
            fx_today = float(fx.loc[dt])
        if str(dt.date()) <= fx_ytd_str:
            fx_ytd = float(fx.loc[dt])
    if not fx_today or not fx_ytd:
        return None
    usd_ret = p_today / p_ytd - 1
    return round((1 + usd_ret) * (fx_today / fx_ytd) - 1, 6)

# ─── Save price rows ───────────────────────────────────────────────────────────
def save_prices(price_data: dict[str, pd.Series]):
    """Convert price series to rows and upsert."""
    all_rows = []
    for sym, series in price_data.items():
        if series is None or series.empty:
            continue
        for dt_idx in series.index:
            d = str(dt_idx.date()) if hasattr(dt_idx, "date") else str(dt_idx)[:10]
            cv = series.loc[dt_idx]
            if hasattr(cv, 'item'):
                cv = cv.item()
            if cv is not None and not pd.isna(cv):
                all_rows.append({"symbol": sym, "date": d, "close": round(float(cv), 4)})
    BATCH = 10000
    total = len(all_rows)
    print(f"  Total price rows: {total}")
    for i in range(0, total, BATCH):
        batch = all_rows[i:i+BATCH]
        print(f"    Rows {i+1}-{i+len(batch)} of {total}")
        supabase_upsert("foreign_etf_prices", batch, "symbol")

# ─── Fetch ETF info with retry ─────────────────────────────────────────────────
def fetch_etf_info_with_retry(sym: str, retries: int = 3, delay: float = 2.0) -> Optional[dict]:
    """Fetch ETF info with rate-limit retry."""
    for attempt in range(retries):
        try:
            info = yf.Ticker(sym).info
            if info and info.get("quoteType") == "ETF":
                return info
            return None
        except Exception as e:
            err_str = str(e)
            if "Rate Limit" in err_str or "429" in err_str:
                wait = delay * (attempt + 1) * 2
                print(f"    Rate limited, waiting {wait:.0f}s...")
                time.sleep(wait)
            else:
                return None
    return None

# ─── Main ──────────────────────────────────────────────────────────────────────
def fetch_all_etfs():
    print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Starting FULL ETF fetch v2")
    print("="*60)

    # Step 1: Get tickers
    print("\n[1/5] Fetching US ETF ticker lists...")
    all_tickers = get_all_us_etf_tickers()
    print(f"  Total unique US ETFs: {len(all_tickers)}")

    # Step 2: Exchange rates
    print("\n[2/5] Fetching exchange rates...")
    rates = fetch_exchange_rates()

    print("\n[3/5] Fetching historical FX for TRY returns...")
    fx_series = fetch_historical_fx()

    # Step 3: Fetch ETF info in batches (with rate-limit handling)
    print(f"\n[4/5] Fetching ETF info for {len(all_tickers)} ETFs...")
    print("  (Using NASDAQ+NYSE as source of truth, skipping individual validation)")
    info_rows = []
    failed = 0

    # Process in batches of 100, with delay between batches
    BATCH = 100
    for i in range(0, len(all_tickers), BATCH):
        batch = all_tickers[i:i+BATCH]
        batch_num = i // BATCH + 1
        total_batches = (len(all_tickers) + BATCH - 1) // BATCH
        print(f"\n  Batch {batch_num}/{total_batches} ({batch[0]}...{batch[-1]})")
        for sym in batch:
            info = fetch_etf_info_with_retry(sym, retries=3, delay=2.0)
            if info:
                price = info.get("regularMarketPrice") or info.get("navPrice")
                currency = info.get("currency", "USD")
                rate = rates.get(currency, 1.0) if currency != "TRY" else 1.0
                if currency == "GBp":
                    rate = rates.get("GBP", rate) / 100 if "GBP" in rates else rate / 100
                price_try = round(price * rate, 2) if price else None

                row = {
                    "symbol":          sym,
                    "name":            info.get("longName") or info.get("shortName") or sym,
                    "category":        info.get("category"),
                    "fund_family":     info.get("fundFamily"),
                    "region":          "US",
                    "asset_type":      info.get("category") or "ETF",
                    "currency":        currency,
                    "nav_price":       round(info.get("navPrice"), 4) if info.get("navPrice") else None,
                    "price":           round(price, 4) if price else None,
                    "price_try":       price_try,
                    "change_pct":      round(info.get("regularMarketChangePercent", 0) / 100, 4)
                                      if info.get("regularMarketChangePercent") else None,
                    "expense_ratio":   round(float(info.get("netExpenseRatio", 0)), 4)
                                      if info.get("netExpenseRatio") else None,
                    "dividend_yield":  round(float(info.get("dividendYield", 0)), 4)
                                      if info.get("dividendYield") else None,
                    "aum":             info.get("totalAssets"),
                    "ytd_return":      round(float(info.get("ytdReturn", 0)), 4)
                                      if info.get("ytdReturn") else None,
                    "three_yr_return": round(float(info.get("threeYearAverageReturn", 0)), 4)
                                      if info.get("threeYearAverageReturn") else None,
                    "five_yr_return":  round(float(info.get("fiveYearAverageReturn", 0)), 4)
                                      if info.get("fiveYearAverageReturn") else None,
                    "beta":            round(float(info.get("beta3Year", 0)), 4)
                                      if info.get("beta3Year") else None,
                    "currency_rate":   round(rate, 4) if rate != 1.0 else None,
                    "updated_at":      datetime.utcnow().isoformat(),
                    "is_active":       True,
                }
                info_rows.append(row)
                print(f"    {sym}: OK (price={row.get('price')}, aum={row.get('aum')})")
            else:
                failed += 1
                if failed % 50 == 0:
                    print(f"  ({failed} failed so far)")
            time.sleep(0.3)  # 300ms between info calls

        print(f"  Batch done: {len(info_rows)} valid, {failed} failed")

        # Upsert every 500
        if len(info_rows) >= 500:
            print(f"  Upserting {len(info_rows)} rows...")
            supabase_upsert("foreign_etfs", info_rows, "symbol")
            info_rows = []

    # Final upsert
    if info_rows:
        print(f"  Final upsert: {len(info_rows)} rows")
        supabase_upsert("foreign_etfs", info_rows, "symbol")

    # Step 4: Download prices (batch)
    print(f"\n[5/5] Downloading price data for all ETFs...")
    price_data = batch_download_prices(all_tickers, "2y")
    print(f"  Got prices for {len(price_data)} ETFs")
    save_prices(price_data)

    print(f"\n[{datetime.now().strftime('%H:%M:%S')}] DONE!")
    print(f"  Valid ETFs: {len(all_tickers) - failed}")
    print(f"  Failed: {failed}")

def fetch_prices_only():
    print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Fetching ETF prices only...")
    url = f"{SUPABASE_URL}/rest/v1/foreign_etfs?select=symbol&is_active=eq.true"
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req) as resp:
        existing = json.loads(resp.read())
    symbols = [e["symbol"] for e in existing]
    print(f"  {len(symbols)} active ETFs in DB")
    fx_series = fetch_historical_fx()
    price_data = batch_download_prices(symbols, "2y")
    save_prices(price_data)

if __name__ == "__main__":
    import sys
    if "--prices-only" in sys.argv:
        fetch_prices_only()
    else:
        fetch_all_etfs()
