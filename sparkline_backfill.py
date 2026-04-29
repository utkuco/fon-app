#!/usr/bin/env python3.11
"""ETF sparkline backfill - concurrent yfinance fetching."""
import os, sys, time, json, tempfile, warnings, urllib.parse, concurrent.futures
warnings.filterwarnings('ignore')
import requests
import yfinance as yf
yf.set_tz_cache_location(tempfile.mkdtemp())

SUPABASE_URL = 'https://oqkobptbvcazifpvjwfz.supabase.co'
SUPABASE_KEY = 'sb_secret_PkAEAOU2YO4YS-ELYpwS5w_SsVg2kqi'
REST_URL = f'{SUPABASE_URL}/rest/v1'
HEADERS = {'apikey': SUPABASE_KEY, 'Authorization': f'Bearer {SUPABASE_KEY}', 'Content-Type': 'application/json', 'Prefer': 'return=minimal'}

def rest_get(table, params=None):
    url = f'{REST_URL}/{table}'
    if params:
        qs = '&'.join(f'{urllib.parse.quote(k)}={urllib.parse.quote(str(v))}' for k, v in params.items())
        url = f'{url}?{qs}'
    resp = requests.get(url, headers=HEADERS, timeout=30)
    if resp.status_code == 416:
        return []
    if resp.status_code != 200:
        raise Exception(f'GET {url} -> {resp.status_code}')
    return resp.json()

def fetch_etf(symbol):
    """Fetch 2y daily data for one ETF."""
    try:
        t = yf.Ticker(symbol)
        h = t.history(period='2y', interval='1d')
        if h is not None and not h.empty:
            rows = []
            for dt, row in h.iterrows():
                rows.append({
                    'symbol': symbol,
                    'date': dt.strftime('%Y-%m-%d'),
                    'open': float(row['Open']),
                    'high': float(row['High']),
                    'low': float(row['Low']),
                    'close': float(row['Close']),
                    'volume': int(row['Volume'])
                })
            return symbol, rows, len(h)
        return symbol, [], 0
    except Exception as e:
        return symbol, [], -1

def main():
    all_symbols = [r['symbol'] for r in rest_get('foreign_etfs', {'select': 'symbol'})]
    print(f'Total ETFs: {len(all_symbols)}')

    # Check existing
    r = requests.get(f'{REST_URL}/foreign_etf_prices?select=symbol', headers=HEADERS, timeout=15)
    if r.status_code == 200:
        existing = set(d['symbol'] for d in r.json())
        to_fetch = [s for s in all_symbols if s not in existing]
        print(f'Existing: {len(existing)}, Need to fetch: {len(to_fetch)}')
    else:
        to_fetch = all_symbols
        print(f'Could not check existing, fetching all: {len(to_fetch)}')

    # Concurrent fetch
    insert_chunk = 500
    delay = 0.1  # smaller delay between batches
    batch_size = 50
    total_inserted = 0
    total_errors = 0

    for batch_idx in range(0, len(to_fetch), batch_size):
        batch = to_fetch[batch_idx:batch_idx + batch_size]
        results = []

        with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
            futures = {executor.submit(fetch_etf, sym): sym for sym in batch}
            for future in concurrent.futures.as_completed(futures, timeout=120):
                results.append(future.result())

        all_rows = []
        for sym, rows, cnt in results:
            if cnt > 0:
                all_rows.extend(rows)
                print(f'{sym}: {cnt} rows OK')
            elif cnt == 0:
                print(f'{sym}: no data')
            else:
                print(f'{sym}: ERROR')
                total_errors += 1

        if all_rows:
            by_sym = {}
            for r in all_rows:
                by_sym.setdefault(r['symbol'], []).append(r)
            for sym, sym_rows in by_sym.items():
                # Delete existing for this symbol first
                requests.delete(f'{REST_URL}/foreign_etf_prices?symbol=eq.{urllib.parse.quote(sym)}', headers=HEADERS, timeout=30)
                for i in range(0, len(sym_rows), insert_chunk):
                    chunk = sym_rows[i:i + insert_chunk]
                    r = requests.post(f'{REST_URL}/foreign_etf_prices', headers=HEADERS, data=json.dumps(chunk), timeout=60)
                    if r.status_code not in (200, 201):
                        print(f'ERR {sym}: {r.status_code}')
            total_inserted += len(all_rows)
            print(f'Batch {batch_idx // batch_size + 1}: inserted {len(all_rows)} rows')

        time.sleep(delay)

    print(f'DONE. Total inserted: {total_inserted}, Errors: {total_errors}')

if __name__ == '__main__':
    main()
