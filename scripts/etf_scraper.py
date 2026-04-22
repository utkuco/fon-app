#!/usr/bin/env python3
"""
Yahoo Finance ETF Scraper for FonApp
Fetches ETF data and saves to Supabase

Usage:
    python3 etf_scraper.py                    # Full refresh (all ETFs)
    python3 etf_scraper.py --symbol SPY       # Single ETF
    python3 etf_scraper.py --prices-only       # Prices only
    python3 etf_scraper.py --init             # Init + full fetch
"""

import yfinance as yf
import pandas as pd
import urllib.request
import json
import time
import warnings
from datetime import date, datetime
from typing import Optional

warnings.filterwarnings('ignore')

# ─── Config ───────────────────────────────────────────────────────────────────
SUPABASE_URL = "https://oqkobptbvcazifpvjwfz.supabase.co"
SUPABASE_KEY = "sb_publishable__GPrsdfKRZCMZE8to916iQ_Izv9naG-"  # anon/service role key

HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=representation"
}

# ─── ETF List ─────────────────────────────────────────────────────────────────
ETF_LIST = [
    # US Equities — Large Cap
    {"symbol": "SPY",  "region": "US", "asset_type": "EQUITY",    "category": "Large Cap",     "currency": "USD"},
    {"symbol": "IVV",  "region": "US", "asset_type": "EQUITY",    "category": "Large Cap",     "currency": "USD"},
    {"symbol": "VOO",  "region": "US", "asset_type": "EQUITY",    "category": "Large Cap",     "currency": "USD"},
    {"symbol": "QQQ",  "region": "US", "asset_type": "EQUITY",    "category": "Tech/Growth",   "currency": "USD"},
    {"symbol": "QQQM", "region": "US", "asset_type": "EQUITY",    "category": "Large Cap",     "currency": "USD"},
    {"symbol": "VTI",  "region": "US", "asset_type": "EQUITY",    "category": "Total Market",  "currency": "USD"},
    {"symbol": "ITOT", "region": "US", "asset_type": "EQUITY",    "category": "Total Market",  "currency": "USD"},
    # US Equities — Sectors
    {"symbol": "XLK",  "region": "US", "asset_type": "EQUITY",    "category": "Technology",    "currency": "USD"},
    {"symbol": "XLV",  "region": "US", "asset_type": "EQUITY",    "category": "Healthcare",    "currency": "USD"},
    {"symbol": "XLF",  "region": "US", "asset_type": "EQUITY",    "category": "Financials",    "currency": "USD"},
    {"symbol": "XLE",  "region": "US", "asset_type": "EQUITY",    "category": "Energy",        "currency": "USD"},
    {"symbol": "XLY",  "region": "US", "asset_type": "EQUITY",    "category": "Consumer",      "currency": "USD"},
    {"symbol": "XLP",  "region": "US", "asset_type": "EQUITY",    "category": "Staples",       "currency": "USD"},
    {"symbol": "XLI",  "region": "US", "asset_type": "EQUITY",    "category": "Industrials",   "currency": "USD"},
    {"symbol": "XLRE", "region": "US", "asset_type": "REAL_ESTATE","category": "Real Estate",  "currency": "USD"},
    {"symbol": "XLB",  "region": "US", "asset_type": "EQUITY",    "category": "Materials",     "currency": "USD"},
    {"symbol": "XLC",  "region": "US", "asset_type": "EQUITY",    "category": "Comm Services", "currency": "USD"},
    {"symbol": "XLU",  "region": "US", "asset_type": "EQUITY",    "category": "Utilities",     "currency": "USD"},
    # US Bonds
    {"symbol": "BND",  "region": "US", "asset_type": "BOND",      "category": "Agg Bond",      "currency": "USD"},
    {"symbol": "AGG",  "region": "US", "asset_type": "BOND",      "category": "Agg Bond",      "currency": "USD"},
    {"symbol": "TLT",  "region": "US", "asset_type": "BOND",      "category": "Long Treas",    "currency": "USD"},
    {"symbol": "VGLT", "region": "US", "asset_type": "BOND",      "category": "Long Treas",    "currency": "USD"},
    {"symbol": "SHY",  "region": "US", "asset_type": "BOND",      "category": "Short Treas",   "currency": "USD"},
    {"symbol": "TIP",  "region": "US", "asset_type": "BOND",      "category": "TIPS",          "currency": "USD"},
    {"symbol": "LQD",  "region": "US", "asset_type": "BOND",      "category": "Corp Invest",   "currency": "USD"},
    {"symbol": "HYG",  "region": "US", "asset_type": "BOND",      "category": "High Yield",    "currency": "USD"},
    # Commodities
    {"symbol": "GLD",  "region": "US", "asset_type": "COMMODITY", "category": "Gold",          "currency": "USD"},
    {"symbol": "SLV",  "region": "US", "asset_type": "COMMODITY", "category": "Silver",       "currency": "USD"},
    {"symbol": "USO",  "region": "US", "asset_type": "COMMODITY", "category": "Oil",          "currency": "USD"},
    {"symbol": "DJP",  "region": "US", "asset_type": "COMMODITY", "category": "Broad Commod", "currency": "USD"},
    # International
    {"symbol": "VEA",  "region": "US", "asset_type": "EQUITY",    "category": "Intl Developed","currency": "USD"},
    {"symbol": "VWO",  "region": "US", "asset_type": "EQUITY",    "category": "Emerging Mkts","currency": "USD"},
    {"symbol": "EFA",  "region": "US", "asset_type": "EQUITY",    "category": "Intl EAFE",    "currency": "USD"},
    {"symbol": "IEFA", "region": "US", "asset_type": "EQUITY",    "category": "Intl Core",    "currency": "USD"},
]

# ─── Supabase helpers ──────────────────────────────────────────────────────────
def supabase_insert(table: str, rows: list[dict]) -> bool:
    """Insert rows into Supabase table. Upsert if conflict."""
    if not rows:
        return True
    url = f"{SUPABASE_URL}/rest/v1/{table}"
    payload = json.dumps(rows)
    req = urllib.request.Request(url, data=payload.encode(), method="POST",
        headers={**HEADERS, "Prefer": "resolution=merge-duplicates"})
    try:
        with urllib.request.urlopen(req) as resp:
            result = json.loads(resp.read())
            return True
    except Exception as e:
        print(f"  INSERT ERROR {table}: {e}")
        return False

def supabase_upsert(table: str, rows: list[dict], conflict_col: str) -> bool:
    """Upsert rows using ON CONFLICT."""
    if not rows:
        return True
    url = f"{SUPABASE_URL}/rest/v1/{table}"
    payload = json.dumps(rows)
    req = urllib.request.Request(url, data=payload.encode(), method="POST",
        headers={**HEADERS, "Prefer": "resolution=merge-duplicates",
                 "On-Conflict": conflict_col})
    try:
        with urllib.request.urlopen(req) as resp:
            body = resp.read()
            if body:
                result = json.loads(body)
                if isinstance(result, list):
                    print(f"  Upserted {len(result)} rows into {table}")
            return True
    except Exception as e:
        print(f"  UPSERT ERROR {table}: {e}")
        return False

def supabase_update_or_insert(table: str, row: dict, match_cols: list[str]) -> bool:
    """Try update first, insert if not exists. match_cols for WHERE clause."""
    if not row:
        return True
    # For simplicity, always use upsert (merge-duplicates)
    return supabase_upsert(table, [row], match_cols[0] if match_cols else "")

# ─── Fetch currency rates ──────────────────────────────────────────────────────
def fetch_exchange_rates() -> dict[str, float]:
    """Fetch TRY exchange rates for USD, EUR, GBP."""
    rates = {}
    pairs = [("USD", "TRY=X"), ("EUR", "EURTRY=X"), ("GBP", "GBPTRY=X")]
    for base, ticker in pairs:
        try:
            t = yf.Ticker(ticker)
            price = t.info.get("regularMarketPrice")
            if price:
                rates[base] = float(price)
                print(f"  {base}/TRY = {price:.4f}")
        except Exception as e:
            print(f"  {base} rate error: {e}")
    return rates

def save_exchange_rates(rates: dict[str, float]) -> None:
    today = str(date.today())
    rows = [{"base": base, "quote": "TRY", "rate": rate, "date": today} for base, rate in rates.items()]
    supabase_upsert("exchange_rates", rows, "base")

def fetch_save_exchange_rates_historical() -> dict[str, pd.Series]:
    """
    Fetch 2 years of historical exchange rates and save to Supabase.
    Returns dict of {base: pd.Series(index=dates, values=rates)} for local use.
    """
    print("  Fetching historical FX (2y)...", flush=True)
    pairs = [("USD", "TRY=X"), ("EUR", "EURTRY=X"), ("GBP", "GBPTRY=X")]
    fx_series: dict[str, pd.Series] = {}

    for base, ticker in pairs:
        try:
            t = yf.Ticker(ticker)
            df = t.history(start=str(date.today().replace(year=date.today().year - 2)), progress=False)
            if df is None or df.empty:
                print(f"  {base}: no historical FX data")
                continue
            if isinstance(df.columns, pd.core.indexes.multi.MultiIndex):
                df.columns = [col[0] for col in df.columns]
            series = df["Close"].dropna()
            if series.empty:
                continue
            series.index = series.index.tz_localize(None) if series.index.tz else series.index
            fx_series[base] = series

            # Save to Supabase
            rows = []
            for dt_idx in series.index:
                d = str(dt_idx.date()) if hasattr(dt_idx, "date") else str(dt_idx)[:10]
                rows.append({"base": base, "quote": "TRY", "rate": round(float(series.loc[dt_idx]), 4), "date": d})
            if rows:
                supabase_upsert("exchange_rates", rows, "base")
                print(f"  {base}: saved {len(rows)} FX rows")
            time.sleep(0.3)
        except Exception as e:
            print(f"  {base} historical FX error: {e}")
    return fx_series


def get_fx_rate(fx_series: dict[str, pd.Series], base: str, target_date: str) -> Optional[float]:
    """Get closest FX rate on or before target_date (YYYY-MM-DD)."""
    if base not in fx_series:
        return None
    series = fx_series[base]
    target = pd.Timestamp(target_date)
    available = series.index[series.index <= target]
    if len(available) == 0:
        return None
    closest = available[-1]
    return float(series.loc[closest])


def calc_period_return(start_price: float, end_price: float) -> Optional[float]:
    if not start_price or start_price == 0 or not end_price:
        return None
    return round(end_price / start_price - 1, 6)


def calculate_etf_try_returns(
    ticker_sym: str,
    currency: str,
    prices_df: pd.DataFrame,
    fx_series: dict[str, pd.Series],
) -> dict[str, Optional[float]]:
    """
    Calculate TRY-adjusted returns for YTD, 1mo, 3mo, 6mo periods.
    prices_df: DataFrame with 'Close' column and datetime index.
    Returns dict with keys: ytd_return_try, one_month_return_try, three_month_return_try, six_month_return_try.
    """
    if prices_df is None or prices_df.empty or "Close" not in prices_df.columns:
        return {"ytd_return_try": None, "one_month_return_try": None,
                "three_month_return_try": None, "six_month_return_try": None}

    closes = prices_df["Close"].dropna()
    if closes.empty:
        return {"ytd_return_try": None, "one_month_return_try": None,
                "three_month_return_try": None, "six_month_return_try": None}

    today_dt = closes.index.max()
    today_str = str(today_dt.date()) if hasattr(today_dt, "date") else str(today_dt)[:10]
    today_price = float(closes.iloc[-1])

    def get_price_on(target_date_str: str) -> Optional[float]:
        target = pd.Timestamp(target_date_str)
        available = closes.index[closes.index <= target]
        if len(available) == 0:
            return None
        return float(closes.loc[available[-1]])

    def get_fx(fx_base: str, d: str) -> float:
        r = get_fx_rate(fx_series, fx_base, d)
        return r if r else 1.0

    # Determine FX base for this ETF's currency
    fx_base = "USD"  # default for USD, GBP, etc.
    if currency == "GBp":
        fx_base = "GBP"
    elif currency == "EUR":
        fx_base = "EUR"
    # USD stays as USD

    # Calculate start-of-period prices
    year_start = f"{today_dt.year}-01-01"
    one_month = (today_dt - pd.DateOffset(months=1)).strftime("%Y-%m-%d")
    three_month = (today_dt - pd.DateOffset(months=3)).strftime("%Y-%m-%d")
    six_month = (today_dt - pd.DateOffset(months=6)).strftime("%Y-%m-%d")

    p_today = today_price
    p_ytd = get_price_on(year_start)
    p_1mo = get_price_on(one_month)
    p_3mo = get_price_on(three_month)
    p_6mo = get_price_on(six_month)

    fx_today = get_fx(fx_base, today_str)
    fx_ytd = get_fx(fx_base, year_start)
    fx_1mo = get_fx(fx_base, one_month)
    fx_3mo = get_fx(fx_base, three_month)
    fx_6mo = get_fx(fx_base, six_month)

    def try_return(usd_ret: Optional[float], fx_start: float, fx_end: float) -> Optional[float]:
        if usd_ret is None or fx_start == 0:
            return None
        return round((1 + usd_ret) * (fx_end / fx_start) - 1, 6)

    ytd_try = try_return(calc_period_return(p_ytd, p_today), fx_ytd, fx_today)
    mo1_try = try_return(calc_period_return(p_1mo, p_today), fx_1mo, fx_today)
    mo3_try = try_return(calc_period_return(p_3mo, p_today), fx_3mo, fx_today)
    mo6_try = try_return(calc_period_return(p_6mo, p_today), fx_6mo, fx_today)

    return {
        "ytd_return_try": ytd_try,
        "one_month_return_try": mo1_try,
        "three_month_return_try": mo3_try,
        "six_month_return_try": mo6_try,
    }

# ─── Fetch ETF info ───────────────────────────────────────────────────────────
def fetch_etf_info(ticker_sym: str) -> Optional[dict]:
    """Fetch ETF info from yfinance."""
    try:
        t = yf.Ticker(ticker_sym)
        info = t.info
        if not info or info.get("quoteType") != "ETF":
            print(f"  {ticker_sym}: not an ETF or no data")
            return None
        return info
    except Exception as e:
        print(f"  {ticker_sym}: fetch error {e}")
        return None

def etf_info_to_row(ticker_sym: str, info: dict, rates: dict[str, float], defaults: dict) -> dict:
    """Convert yfinance info dict to foreign_etfs row."""
    price = info.get("regularMarketPrice") or info.get("navPrice")
    currency = info.get("currency", "USD")
    rate = rates.get(currency, 1.0) if currency != "TRY" else 1.0

    # GBp (British pence) to GBP
    if currency == "GBp":
        rate = rates.get("GBP", rate) / 100 if "GBP" in rates else rate / 100

    price_try = round(price * rate, 2) if price else None

    # Convert percentage fields (yfinance often returns as decimal, e.g. 0.014 = 1.4%)
    def pct(val):
        if val is None: return None
        # If > 1, assume it's already a percentage (e.g. 1.14)
        # If <= 1, assume decimal (e.g. 0.0114 = 1.14%)
        if abs(val) > 1:
            return round(val, 4)
        return round(val * 100, 4)

    row = {
        "symbol":        ticker_sym,
        "name":          info.get("longName") or info.get("shortName") or ticker_sym,
        "category":      info.get("category") or defaults.get("category"),
        "fund_family":   info.get("fundFamily"),
        "region":        defaults.get("region", "US"),
        "asset_type":    defaults.get("asset_type", "EQUITY"),
        "currency":      currency,
        "nav_price":     round(info.get("navPrice"), 4) if info.get("navPrice") else None,
        "price":         round(price, 4) if price else None,
        "price_try":     price_try,
        "change_pct":      round(info.get("regularMarketChangePercent", 0) / 100, 4) if info.get("regularMarketChangePercent") else None,
        # netExpenseRatio is already a percentage value from yfinance (e.g. 0.0945 = 0.0945%)
        "expense_ratio": round(float(info.get("netExpenseRatio", 0)), 4) if info.get("netExpenseRatio") else None,
        # dividendYield is already a percentage from yfinance (e.g. 1.14 = 1.14%)
        "dividend_yield": round(float(info.get("dividendYield", 0)), 4) if info.get("dividendYield") else None,
        "aum":           info.get("totalAssets"),
        # ytdReturn etc. are decimals from yfinance (e.g. -0.0434 = -4.34%) — store as-is (ratio)
        "ytd_return":      round(float(info.get("ytdReturn", 0)), 4) if info.get("ytdReturn") else None,
        "three_yr_return": round(float(info.get("threeYearAverageReturn", 0)), 4) if info.get("threeYearAverageReturn") else None,
        "five_yr_return":  round(float(info.get("fiveYearAverageReturn", 0)), 4) if info.get("fiveYearAverageReturn") else None,
        "beta":          round(float(info.get("beta3Year", 0)), 4) if info.get("beta3Year") else None,
        "currency_rate": round(rate, 4) if rate != 1.0 else None,
        "updated_at":    datetime.utcnow().isoformat(),
        "is_active":     True,
    }
    return row

# ─── Fetch holdings ───────────────────────────────────────────────────────────
def fetch_etf_holdings(ticker_sym: str) -> list[dict]:
    """Fetch top holdings from yfinance funds_data."""
    try:
        t = yf.Ticker(ticker_sym)
        fd = t.funds_data
        holdings_df = fd.top_holdings
        if holdings_df is None or holdings_df.empty:
            return []
        rows = []
        for idx, row_data in holdings_df.iterrows():
            sym = str(idx)  # Symbol is the DataFrame index, not a column
            rows.append({
                "etf_symbol":     ticker_sym,
                "holding_symbol": sym,
                "holding_name":   str(row_data.get("Name", ""))[:200],
                # Holding Percent is decimal (0.0641 = 6.41%), store as-is
                "weight":         round(float(row_data.get("Holding Percent", 0)), 4),
                "updated_at":     datetime.utcnow().isoformat(),
            })
        return rows
    except Exception as e:
        print(f"  {ticker_sym} holdings error: {e}")
        return []

def fetch_etf_sectors(ticker_sym: str) -> list[dict]:
    """Fetch sector weightings from yfinance funds_data."""
    try:
        t = yf.Ticker(ticker_sym)
        fd = t.funds_data
        sectors = fd.sector_weightings
        if not sectors:
            return []
        rows = []
        for sector, weight in sectors.items():
            rows.append({
                "etf_symbol": ticker_sym,
                "sector":     sector,
                # yfinance returns weight as decimal (0.3154), store as percentage (31.54)
                "weight":     round(float(weight) * 100, 4),
                "updated_at": datetime.utcnow().isoformat(),
            })
        return rows
    except Exception as e:
        print(f"  {ticker_sym} sectors error: {e}")
        return []

# ─── Fetch prices ─────────────────────────────────────────────────────────────
def fetch_etf_prices(ticker_sym: str, period: str = "1y") -> list[dict]:
    """Fetch historical daily prices."""
    try:
        df = yf.download(ticker_sym, period=period, interval="1d", progress=False, auto_adjust=True)
        if df is None or df.empty:
            return []
        # Flatten MultiIndex columns (newer yfinance returns MultiIndex like [('Close','SPY')])
        if isinstance(df.columns, pd.core.indexes.multi.MultiIndex):
            df.columns = [col[0] for col in df.columns]
        rows = []
        for i in range(len(df)):
            dt = df.index[i]
            d = str(dt.date()) if hasattr(dt, 'date') else str(dt)[:10]
            row = df.iloc[i]
            close_val = row["Close"]
            if hasattr(close_val, 'item'):
                close_val = close_val.item()
            rows.append({
                "symbol":  ticker_sym,
                "date":    d,
                "open":    round(float(row["Open"].item()), 4) if row["Open"] is not None else None,
                "high":    round(float(row["High"].item()), 4) if row["High"] is not None else None,
                "low":     round(float(row["Low"].item()), 4) if row["Low"] is not None else None,
                "close":   round(float(close_val), 4) if close_val is not None else None,
                "volume":  int(row["Volume"].item()) if row["Volume"] is not None else None,
            })
        return rows
    except Exception as e:
        print(f"  {ticker_sym} prices error: {e}")
        return []

# ─── Main fetch ───────────────────────────────────────────────────────────────
def fetch_all_etfs(prices_only: bool = False) -> None:
    """Main function: fetch all ETFs."""
    print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Starting ETF fetch...")

    # 1. Exchange rates (current)
    print("\n[1/6] Fetching exchange rates...")
    rates = fetch_exchange_rates()
    if rates:
        save_exchange_rates(rates)
    else:
        print("  No rates fetched, using defaults")

    # 2. Historical exchange rates (for TRY return calculation)
    print("\n[2/6] Fetching historical exchange rates for TRY-adjusted returns...")
    fx_series = fetch_save_exchange_rates_historical()

    # 3. ETFs (with TRY return calculation)
    print("\n[3/6] Fetching ETF info + TRY returns...")
    info_rows = []
    for etf in ETF_LIST:
        sym = etf["symbol"]
        currency = etf.get("currency", "USD")
        print(f"  {sym}...", end=" ", flush=True)

        # Fetch info
        info = fetch_etf_info(sym)
        if not info:
            print("FAILED")
            time.sleep(0.3)
            continue

        row = etf_info_to_row(sym, info, rates, etf)

        # Fetch prices and calculate TRY returns + USD ytd_return from historical prices
        try:
            prices_df = yf.download(sym, period="2y", interval="1d", auto_adjust=True)
            if prices_df is not None and not prices_df.empty:
                if isinstance(prices_df.columns, pd.core.indexes.multi.MultiIndex):
                    prices_df.columns = [col[0] for col in prices_df.columns]
                try_returns = calculate_etf_try_returns(sym, currency, prices_df, fx_series)
                row.update(try_returns)
                # Compute ytd_return (USD) from historical prices — more reliable than yfinance info
                closes = prices_df["Close"].dropna()
                closes.index = closes.index.tz_localize(None) if closes.index.tz else closes.index
                closes.index = closes.index.normalize()
                today_dt = closes.index.max()
                year_start_str = f"{today_dt.year}-01-01"
                today_price = float(closes.iloc[-1])
                p_ytd = None
                for dt in closes.index:
                    if str(dt.date()) <= year_start_str:
                        p_ytd = float(closes.loc[dt])
                if p_ytd and p_ytd > 0:
                    row["ytd_return"] = round(today_price / p_ytd - 1, 4)
                print(f"OK (price={row.get('price')}, ytd={row.get('ytd_return')}, ytd_try={try_returns.get('ytd_return_try')})")
            else:
                print(f"OK (no prices, price={row.get('price')})")
        except Exception as e:
            print(f"OK (prices error: {e})")

        info_rows.append(row)
        time.sleep(0.3)

    if info_rows:
        print(f"\n  Upserting {len(info_rows)} ETFs with TRY returns...")
        supabase_upsert("foreign_etfs", info_rows, "symbol")

    if prices_only:
        print("\nPrices-only mode, skipping holdings.")
        return

    # 4. Holdings (only for equity ETFs with full data)
    print("\n[4/6] Fetching top holdings...")
    equity_etfs = [e["symbol"] for e in ETF_LIST if e["asset_type"] == "EQUITY"][:15]
    for sym in equity_etfs:
        print(f"  {sym}...", end=" ", flush=True)
        holdings = fetch_etf_holdings(sym)
        if holdings:
            supabase_upsert("foreign_etf_holdings", holdings, "etf_symbol")
            print(f"OK ({len(holdings)} holdings)")
        else:
            print("N/A")
        time.sleep(0.3)

    # 5. Sectors
    print("\n[5/6] Fetching sector weightings...")
    for sym in equity_etfs:
        print(f"  {sym}...", end=" ", flush=True)
        sectors = fetch_etf_sectors(sym)
        if sectors:
            supabase_upsert("foreign_etf_sectors", sectors, "etf_symbol")
            print(f"OK ({len(sectors)} sectors)")
        else:
            print("N/A")
        time.sleep(0.3)

    print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Done!")

def fetch_prices() -> None:
    """Fetch prices for all ETFs."""
    print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Fetching ETF prices...")
    for etf in ETF_LIST:
        sym = etf["symbol"]
        print(f"  {sym}...", end=" ", flush=True)
        prices = fetch_etf_prices(sym)
        if prices:
            supabase_upsert("foreign_etf_prices", prices, "symbol")
            print(f"OK ({len(prices)} days)")
        else:
            print("FAILED")
        time.sleep(0.2)
    print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Prices done!")

# ─── CLI ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys
    if "--prices-only" in sys.argv:
        fetch_prices()
    elif "--symbol" in sys.argv:
        idx = sys.argv.index("--symbol")
        sym = sys.argv[idx + 1]
        print(f"Single ETF: {sym}")
        info = fetch_etf_info(sym)
        if info:
            print(json.dumps({k: v for k, v in info.items() if v is not None}, indent=2, default=str)[:3000])
    else:
        fetch_all_etfs()
