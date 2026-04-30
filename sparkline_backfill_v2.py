#!/usr/bin/env python3.11
"""ETF sparkline backfill v2 - upsert without delete, with retry."""
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

def insert_chunk(sym_rows):
    """Insert a chunk of rows, return success count or -1 on error."""
    chunk_size = 500
    total_ok = 0
    for i in range(0, len(sym_rows), chunk_size):
        chunk = sym_rows[i:i+chunk_size]
        attempts = 0
        while attempts < 3:
            try:
                r = requests.post(
                    f'{REST_URL}/foreign_etf_prices',
                    headers={**HEADERS, 'Prefer': 'return=minimal'},
                    data=json.dumps(chunk),
                    timeout=60
                )
                if r.status_code in (200, 201):
                    total_ok += len(chunk)
                    break
                elif r.status_code == 429:
                    time.sleep(5)
                    attempts += 1
                    continue
                else:
                    print(f'POST status {r.status_code}: {r.text[:100]}')
                    attempts += 1
                    time.sleep(2)
            except Exception as e:
                print(f'POST exception: {e}')
                attempts += 1
                time.sleep(2)
        else:
            print(f'FAILED after 3 retries for {sym_rows[0]["symbol"]}')
            return -1
    return total_ok

def main():
    all_symbols = [r['symbol'] for r in rest_get('foreign_etfs', {'select': 'symbol'})]
    print(f'Total ETFs in foreign_etfs: {len(all_symbols)}')

    # Check existing distinct symbols
    r = requests.get(f'{REST_URL}/foreign_etf_prices?select=symbol', headers=HEADERS, timeout=15)
    if r.status_code == 200:
        all_price_rows = r.json()
        existing = set(d['symbol'] for d in all_price_rows)
        to_fetch = [s for s in all_symbols if s not in existing]
        print(f'Existing ETFs with data: {len(existing)}, Need to fetch: {len(to_fetch)}')
    else:
        existing = set()
        to_fetch = all_symbols
        print(f'Could not check existing, fetching all {len(to_fetch)}')

    if not to_fetch:
        print('All ETFs already have data.')
        return

    # Sequential fetch with small batches, no delete
    delay = 0.2
    batch_size = 10
    total_inserted = 0
    total_errors = 0
    total_fetched = 0

    for batch_idx in range(0, len(to_fetch), batch_size):
        batch = to_fetch[batch_idx:batch_idx + batch_size]
        results = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = {executor.submit(fetch_etf, sym): sym for sym in batch}
            for future in concurrent.futures.as_completed(futures, timeout=120):
                results.append(future.result())

        all_rows = []
        for sym, rows, cnt in results:
            if cnt > 0:
                all_rows.extend(rows)
                total_fetched += 1
                print(f'{sym}: {cnt} rows fetched')
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
                ok = insert_chunk(sym_rows)
                if ok > 0:
                    total_inserted += ok
                    print(f'{sym}: inserted {ok} rows')
                else:
                    print(f'{sym}: INSERT FAILED')
        time.sleep(delay)

    print(f'DONE. Fetched: {total_fetched}, Inserted: {total_inserted}, Errors: {total_errors}')

if __name__ == '__main__':
    main()
