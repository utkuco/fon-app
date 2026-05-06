#!/opt/homebrew/bin/python3.11
"""
ETF Sparkline Fast Backfill — DELETE + INSERT approach.
Bypasses broken merge-duplicates upsert logic.
"""
import os, sys, time, json, logging, tempfile
from datetime import datetime
from pathlib import Path

os.environ['YFINANCE_CACHE_DIR'] = '/tmp/yf_cache5'
os.environ['YF_DATAPATH'] = '/tmp/yf_cache5'
os.makedirs('/tmp/yf_cache5', exist_ok=True)

import warnings
warnings.filterwarnings('ignore')

import requests
import yfinance as yf

# ── Config ──────────────────────────────────────────────────────
SUPABASE_URL = "https://oqkobptbvcazifpvjwfz.supabase.co"
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "sb_secret_PkAEAOU2YO4YS-ELYpwS5w_SsVg2kqi")
REST_URL = f"{SUPABASE_URL}/rest/v1"
HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=minimal",
}
BATCH_SIZE = 25
FETCH_DELAY = 0.25
INSERT_CHUNK = 500
LOG_FILE = "scripts/fast_backfill.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, mode="w", encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger(__name__)

def rest_get(table, params=None):
    url = f"{REST_URL}/{table}"
    if params:
        from urllib.parse import urlencode
        url = f"{url}?{urlencode(params)}"
    resp = requests.get(url, headers=HEADERS, timeout=30)
    if resp.status_code not in (200, 416):
        log.error("GET %s -> %d: %s", url, resp.status_code, resp.text[:200])
    return resp.json() if resp.status_code == 200 else []

def get_all_symbols():
    data = rest_get("foreign_etfs", {"select": "symbol", "limit": 2000})
    if isinstance(data, list):
        return [r['symbol'] for r in data]
    return []

def get_done_symbols():
    data = rest_get("foreign_etf_prices", {"select": "symbol", "limit": 1000})
    if isinstance(data, list):
        return set(d['symbol'] for d in data)
    return set()

def delete_symbol(symbol):
    import urllib.parse
    url = f"{REST_URL}/foreign_etf_prices?symbol=eq.{urllib.parse.quote(symbol)}"
    requests.delete(url, headers=HEADERS, timeout=30)

def insert_rows(rows):
    for i in range(0, len(rows), INSERT_CHUNK):
        chunk = rows[i:i+INSERT_CHUNK]
        resp = requests.post(REST_URL + "/foreign_etf_prices", headers=HEADERS, json=chunk, timeout=60)
        if resp.status_code not in (200, 201):
            log.error("INSERT failed %d: %s", resp.status_code, resp.text[:200])
            return False
    return True

def fetch_and_upsert(symbol):
    try:
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period="1y", auto_adjust=True)
        if hist is None or hist.empty:
            log.info("%s: no data", symbol)
            return 0
        rows = []
        for dt, row in hist.iterrows():
            close_val = row["Close"]
            if close_val and close_val == close_val and close_val > 0 and close_val != float("inf"):
                rows.append({
                    "symbol": symbol,
                    "date": dt.strftime("%Y-%m-%d"),
                    "close": round(float(close_val), 4),
                })
        if not rows:
            log.info("%s: empty after filter", symbol)
            return 0
        delete_symbol(symbol)
        insert_rows(rows)
        return len(rows)
    except Exception as e:
        log.error("%s: ERROR %s", symbol, e)
        return 0

def main():
    start = datetime.now()
    log.info("=== FAST BACKFILL started at %s ===", start.isoformat())

    all_symbols = get_all_symbols()
    done = get_done_symbols()
    remaining = [s for s in all_symbols if s not in done]
    log.info("Total ETFs: %d, Already done: %d, Remaining: %d", len(all_symbols), len(done), len(remaining))

    if not remaining:
        log.info("Nothing to do!")
        return

    total_inserted = 0
    for idx, symbol in enumerate(remaining, 1):
        n = fetch_and_upsert(symbol)
        total_inserted += n
        log.info("[%d/%d] %s -> %d rows (total: %d)", idx, len(remaining), symbol, n, total_inserted)
        time.sleep(FETCH_DELAY)

        if idx % 50 == 0:
            log.info("Checkpoint: processed %d/%d", idx, len(remaining))

    elapsed = (datetime.now() - start).total_seconds()
    log.info("=== DONE in %.1fs ===", elapsed)
    log.info("Total rows inserted: %d", total_inserted)

if __name__ == "__main__":
    main()