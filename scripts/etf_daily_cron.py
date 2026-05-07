#!/usr/bin/env python3.11
"""
ETF Daily Cron Job — runs every day after US market close (~22:00 Turkey).
1. Fetches today's close prices for all ETFs (incremental update)
2. Also fetches prices for any NEW ETFs added since last run
3. Recomputes 1M, 3M, 6M TRY returns and updates foreign_etfs table

Usage:
    python3.11 scripts/etf_daily_cron.py

Cron example (run at 22:00 Turkey daily):
    0 22 * * * cd /Users/admin/Desktop/projects/fon-app && ./venv/bin/python3 scripts/etf_daily_cron.py >> logs/etf_cron.log 2>&1
"""

import os
os.environ['YFINANCE_CACHE_DIR'] = '/tmp/yfinance_cache'

import yfinance as yf
import pandas as pd
import urllib.request
import json
import time
import warnings
import fcntl
import psycopg2
from datetime import date, datetime, timedelta
from typing import Optional

warnings.filterwarnings('ignore')

LOCK_FILE = "/tmp/etf_daily_cron.lock"

W_SPARKLINE = 280  # sparkline SVG width (matches viewBox)

SUPABASE_DB = dict(
    host='db.oqkobptbvcazifpvjwfz.supabase.co',
    port=5432,
    dbname='postgres',
    user='postgres',
    password='rzvfO6ub5F1W6hpR'
)

def acquire_lock():
    """Prevent concurrent cron runs using file-based lock."""
    lock_fd = open(LOCK_FILE, 'w')
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        lock_fd.write(str(os.getpid()))
        return lock_fd
    except BlockingIOError:
        print("ALREADY RUNNING — another instance is active. Exiting.")
        lock_fd.close()
        exit(0)

def release_lock(lock_fd):
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_UN)
        lock_fd.close()
        os.unlink(LOCK_FILE)
    except Exception:
        pass

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


def supabase_query_raw(url: str) -> list:
    """Execute a raw GET URL (for complex queries)."""
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=60) as resp:
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


def calc_return(prices: list[dict], days: int) -> Optional[float]:
    """
    Calculate return over last `days` calendar days using foreign_etf_prices data.

    Args:
        prices: list of {"date": "YYYY-MM-DD", "close": float}, sorted ASC by date
        days: number of calendar days to look back

    Returns:
        Ratio return (e.g. 0.05 = +5%), rounded to 6 decimal places,
        or None if insufficient data.
    """
    if not prices or len(prices) < 2:
        return None

    today_date = prices[-1]["date"]  # newest price date (already sorted desc in fetch)
    target_date = (datetime.fromisoformat(today_date).date() - timedelta(days=days)).isoformat()

    # Find newest price (last row)
    p_today = prices[-1]["close"]
    if p_today is None or p_today == 0:
        return None

    # Find oldest price on or after target_date (binary search)
    p_start = None
    lo, hi = 0, len(prices) - 1
    while lo <= hi:
        mid = (lo + hi) // 2
        d = prices[mid]["date"]
        if d < target_date:
            lo = mid + 1
        else:
            p_start = prices[mid]["close"]
            hi = mid - 1

    if p_start is None or p_start == 0:
        return None
    return round(p_today / p_start - 1, 6)


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
            # Deduplicate column names (can happen when multiple tuples share same symbol)
            if df.columns.duplicated().any():
                df = df.loc[:, ~df.columns.duplicated()]
            for sym in batch_syms:
                if sym not in df.columns:
                    continue
                col = df[sym].dropna()
                if col.empty:
                    continue
                val = col.iloc[-1]
                # Guard: if it's still a Series/DataFrame (duplicate cols), pick first scalar
                while hasattr(val, 'iloc'):
                    val = val.iloc[0] if hasattr(val, 'iloc') else val
                try:
                    result[sym] = round(float(val), 4)
                except (TypeError, ValueError):
                    pass
        except Exception as e:
            print(f"    Batch error: {e}")
        time.sleep(0.5)
    return result


def get_row_id(table: str, symbol: str) -> Optional[int]:
    rows = supabase_query(table, "id", f"symbol=eq.{symbol}&limit=1")
    return rows[0]["id"] if rows else None


def main():
    lock_fd = acquire_lock()
    try:
        print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] ETF Daily Cron")
        print("=" * 60)

        # ── Step 1: FX rates ────────────────────────────────────────────────
        print("\n[1/5] Fetching FX rates...")
        fx_rates = get_fx_rates()
        usd_try = fx_rates.get("USD", 1.0)
        if not fx_rates:
            print("  WARNING: No FX rates fetched, using 1.0")

        # ── Step 2: Get all ETFs from DB ────────────────────────────────────
        print("\n[2/5] Fetching ETF list from DB...")
        etfs = supabase_query("foreign_etfs", "symbol, id", "limit=5000")
        print(f"  Total ETFs in DB: {len(etfs)}")

        if not etfs:
            return

        # ── Step 3: Download latest prices (incremental) ────────────────────
        print("\n[3/5] Fetching latest prices...")
        symbols = [e["symbol"] for e in etfs if e.get("symbol")]
        latest_prices = fetch_latest_prices_batch(symbols)
        print(f"  Got prices for {len(latest_prices)} ETFs")

        # Build price rows to upsert
        today_str = date.today().isoformat()
        price_rows = []
        for sym, price in latest_prices.items():
            price_rows.append({"symbol": sym, "date": today_str, "close": price})

        updated = len(latest_prices)
        errors = []
        if price_rows:
            print(f"  Upserting {len(price_rows)} today's price rows...")
            try:
                supabase_upsert("foreign_etf_prices", price_rows, "symbol,date")
            except Exception as e:
                print(f"  WARNING: Upsert failed ({e}), prices not written to DB")
                errors.append(str(e))
                updated = 0

        # ── Step 4: Fetch ALL price histories (for return calculation) ────────
        print("\n[4/5] Fetching full price history for returns...")
        sym_chunks = [symbols[i:i+100] for i in range(0, len(symbols), 100)]
        all_prices: dict[str, list] = {}

        for chunk in sym_chunks:
            syms_param = ",".join(chunk)
            url = (f"{SUPABASE_URL}/rest/v1/foreign_etf_prices"
                   f"?symbol=in.({syms_param})&order=date.desc&limit=730")
            rows = supabase_query_raw(url)
            for row in rows:
                sym = row.get("symbol")
                if sym not in all_prices:
                    all_prices[sym] = []
                all_prices[sym].append({"date": row.get("date"), "close": row.get("close")})
            time.sleep(0.3)

        print(f"  Fetched price history for {len(all_prices)} ETFs")

        # ── Step 4b: Fetch last 30 days per symbol (for sparklines) ─────────────
        print("  Fetching last 30 days per symbol for sparklines...")
        last30_prices: dict[str, list] = {}
        cutoff_str = (date.today() - timedelta(days=30)).isoformat()

        # Use direct psycopg2 to avoid PostgREST 1000-row hard limit.
        # With 1176 ETFs × ~22 trading days, total rows ≈ 25K — far exceeding the limit.
        try:
            db_conn = psycopg2.connect(**SUPABASE_DB, connect_timeout=30)
            db_cur = db_conn.cursor()
            db_cur.execute("""
                SELECT symbol, date, close FROM foreign_etf_prices
                WHERE date >= %s
                ORDER BY symbol ASC, date ASC
            """, (cutoff_str,))
            rows = db_cur.fetchall()
            for row in rows:
                sym, dt, close = row
                if sym not in last30_prices:
                    last30_prices[sym] = []
                last30_prices[sym].append({"date": str(dt), "close": float(close)})
            db_cur.close()
            db_conn.close()
            print(f"  Got last-30-day prices for {len(last30_prices)} ETFs via direct DB ({len(rows)} total rows)")
        except Exception as e:
            print(f"  WARNING: Direct DB fetch failed ({e}), falling back to PostgREST...")
            for chunk in sym_chunks:
                syms_param = ",".join(chunk)
                url = (f"{SUPABASE_URL}/rest/v1/foreign_etf_prices"
                       f"?symbol=in.({syms_param})&date=gte.{cutoff_str}"
                       f"&order=date.desc&limit=10000")
                rows = supabase_query_raw(url)
                for row in rows:
                    sym = row.get("symbol")
                    if sym not in last30_prices:
                        last30_prices[sym] = []
                    last30_prices[sym].append({"date": row.get("date"), "close": row.get("close")})
                time.sleep(0.3)
            print(f"  Got last-30-day prices for {len(last30_prices)} ETFs via PostgREST fallback")

        # Build id→symbol map and symbol→id map
        sym_to_id = {e["symbol"]: e["id"] for e in etfs if e.get("symbol") and e.get("id")}



        # ── Step 5: Recompute sparklines from last-30-day prices ───────────────
        print("\n[5/5] Recomputing sparklines (last 30 days)...")
        spark_ok, spark_skip, spark_err = recompute_sparklines(last30_prices, sym_to_id)
        print(f"  Sparklines: {spark_ok} updated, {spark_skip} skipped, {spark_err} errors")

        # Update system status — two keys:
        #   last_etf_fetch      → ISO timestamp (for "last run" display)
        #   etf_cron_stats      → JSON with detailed stats for admin panel
        now = datetime.utcnow().isoformat()
        update_key("last_etf_fetch", now)

        stats_json = json.dumps({
            "status": "ok",
            "prices_updated": len(latest_prices),
            "returns_updated": updated,
            "sparklines_updated": spark_ok,
            "sparklines_skipped": spark_skip,
            "sparklines_errors": spark_err,
            "errors": [],
            "fx_usd_try": round(usd_try, 4),
            "finished_at": now,
        })
        update_key("etf_cron_stats", stats_json)

        print(f"\n✅ ETF cron complete — prices={len(latest_prices)}, sparklines={spark_ok}")
    finally:
        release_lock(lock_fd)


def update_key(key: str, value: str) -> None:
    url = f"{SUPABASE_URL}/rest/v1/system_status"
    payload = json.dumps([{"key": key, "value": value}])
    req = urllib.request.Request(url, data=payload.encode(), method="POST",
        headers={**HEADERS, "Prefer": "resolution=merge-duplicates, conflict=key"})
    try:
        with urllib.request.urlopen(req, timeout=10):
            pass
    except Exception as e:
        print(f"  system_status update failed: {e}")



def recompute_sparklines(
    all_prices: dict[str, list[dict]],
    sym_to_id: dict[str, int],
) -> tuple[int, int, int]:
    """
    Compute sparkline from the already-fetched price data in `all_prices`.
    Filters each symbol to last 30 days, then batch-PATCHes foreign_etfs.sparkline.
    """
    ok, skip, err = 0, 0, 0
    spark_rows = []
    cutoff_dt = date.today() - timedelta(days=30)
    cutoff_str = cutoff_dt.isoformat()

    for sym, prices in all_prices.items():
        row_id = sym_to_id.get(sym)
        if not row_id:
            skip += 1
            continue

        # Filter to last 30 days from whatever data we already have
        recent = [p for p in prices if p.get("date", "") >= cutoff_str]
        # Fallback to all prices if < 2 pts after filter
        if len(recent) < 2:
            recent = prices
        if len(recent) < 2:
            skip += 1
            continue

        sorted_rows = sorted(recent, key=lambda r: r.get("date", ""))
        closes = [r["close"] for r in sorted_rows if r.get("close") is not None]
        if len(closes) < 2:
            skip += 1
            continue

        mn = min(closes)
        mx = max(closes)
        rng = mx - mn or 1
        step = W_SPARKLINE / (len(closes) - 1)
        # y in [0, 40] — matches funds.sparkline (H=40 viewBox)
        # x in [0, 280] — matches funds.sparkline (W=280 viewBox)
        points = [
            [round(i * step, 4), round((1 - (c - mn) / rng) * 40, 4)]
            for i, c in enumerate(closes)
        ]
        positive = closes[-1] >= closes[0]
        spark = {"points": points, "positive": positive}
        spark_rows.append({"id": row_id, "symbol": sym, "sparkline": spark})

    BATCH = 100
    for i in range(0, len(spark_rows), BATCH):
        batch = spark_rows[i:i + BATCH]
        for row in batch:
            row_id = row.pop("id")
            sym = row.pop("symbol")
            ok_patch = supabase_patch("foreign_etfs", row_id, {"sparkline": row["sparkline"]})
            if ok_patch:
                ok += 1
                if ok % 100 == 0:
                    print(f"  ✓ {ok} ETFs updated")
            else:
                err += 1
        time.sleep(0.3)

    return ok, skip, err


if __name__ == "__main__":
    main()
