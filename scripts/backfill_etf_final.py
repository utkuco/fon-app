#!/opt/homebrew/bin/python3.11
"""Clean backfill for foreign_etf_prices using direct single-insert approach."""
import requests, yfinance as yf, os, json, sys
from datetime import datetime

os.environ['YFINANCE_CACHE_DIR'] = '/tmp/yf_cache3'
os.makedirs('/tmp/yf_cache3', exist_ok=True)
yf.set_tz_cache_location('/tmp/yf_cache3')

SUPABASE_URL = 'https://oqkobptbvcazifpvjwfz.supabase.co'
KEY = 'sb_secret_PkAEAOU2YO4YS-ELYpwS5w_SsVg2kqi'
HEADERS_R = {'apikey': KEY, 'Authorization': f'Bearer {KEY}'}
HEADERS_W = {
    'apikey': KEY,
    'Authorization': f'Bearer {KEY}',
    'Content-Type': 'application/json',
    'Prefer': 'return=representation'
}

def get_etf_symbols():
    r = requests.get(f'{SUPABASE_URL}/rest/v1/foreign_etfs?select=symbol', headers=HEADERS_R)
    if not r.ok:
        raise Exception(f'Failed to fetch ETFs: {r.text}')
    return [e['symbol'] for e in r.json()]

def get_existing_symbols():
    r = requests.get(
        f'{SUPABASE_URL}/rest/v1/foreign_etf_prices?select=symbol,date',
        headers=HEADERS_R
    )
    if not r.ok:
        return set()
    data = r.json()
    # Group and count
    from collections import defaultdict
    counts = defaultdict(int)
    for row in data:
        counts[row['symbol']] += 1
    return set(s for s, c in counts.items() if c >= 252)

def fetch_yf_history(symbol):
    try:
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period='1y', auto_adjust=True, back_adjust=True)
        prices = []
        for date, row in hist.iterrows():
            c = row['Close']
            if not (c and c > 0):
                continue
            ds = date.strftime('%Y-%m-%d')
            prices.append({'symbol': symbol, 'date': ds, 'close': round(float(c), 4)})
        return prices
    except Exception as e:
        print(f'  [ERR] {symbol}: {e}', file=sys.stderr)
        return []

def insert_rows(rows):
    if not rows:
        return 0
    r = requests.post(
        f'{SUPABASE_URL}/rest/v1/foreign_etf_prices',
        headers=HEADERS_W,
        json=rows
    )
    if r.status_code not in (200, 201):
        return 0
    # Count how many were actually inserted
    resp = r.json()
    if isinstance(resp, list):
        return len(resp)
    return 0

def main():
    # Get all ETF symbols
    all_symbols = get_etf_symbols()
    print(f'Total ETFs in foreign_etfs: {len(all_symbols)}')

    # Check which already have data
    existing = get_existing_symbols()
    print(f'Already have 252+ rows: {len(existing)}')

    # Find ETFs needing backfill (no data OR incomplete)
    to_fetch = [s for s in all_symbols if s not in existing]
    print(f'Need to fetch: {len(to_fetch)}')

    if not to_fetch:
        print('All ETFs already have data!')
        return

    # Process 5 at a time to avoid rate limiting
    BATCH = 5
    total_inserted = 0
    errors = 0

    for i in range(0, len(to_fetch), BATCH):
        batch = to_fetch[i:i+BATCH]
        batch_num = i // BATCH + 1
        total_batches = (len(to_fetch) + BATCH - 1) // BATCH
        print(f'\n[Batch {batch_num}/{total_batches}] Fetching {batch}...')

        for symbol in batch:
            prices = fetch_yf_history(symbol)
            if not prices:
                print(f'  {symbol}: no data')
                errors += 1
                continue

            # Insert in chunks of 50 to avoid payload too large
            chunk_size = 50
            inserted = 0
            for j in range(0, len(prices), chunk_size):
                chunk = prices[j:j+chunk_size]
                n = insert_rows(chunk)
                inserted += n

            total_inserted += inserted
            print(f'  {symbol}: {inserted} prices inserted')

        # Small delay between batches
        import time
        time.sleep(0.5)

    print(f'\n[DONE] Total inserted: {total_inserted}, errors: {errors}')

if __name__ == '__main__':
    main()
