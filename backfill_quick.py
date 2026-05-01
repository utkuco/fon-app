#!/usr/bin/env python3.11
"""Quick backfill for ALL ETFs in foreign_etfs. Simple DELETE+INSERT per batch.
Fast: 0.4s delay between symbols, no complex pagination."""
import os, sys, time, json, tempfile, warnings, urllib.parse
warnings.filterwarnings('ignore')

import requests
import yfinance as yf
yf.set_tz_cache_location(tempfile.mkdtemp())

SUPABASE_URL = 'https://oqkobptbvcazifpvjwfz.supabase.co'
SUPABASE_KEY = 'sb_secret_PkAEAOU2YO4YS-ELYpwS5w_SsVg2kqi'
REST_URL = f'{SUPABASE_URL}/rest/v1'
HEADERS = {
    'apikey': SUPABASE_KEY,
    'Authorization': f'Bearer {SUPABASE_KEY}',
    'Content-Type': 'application/json',
    'Prefer': 'return=minimal'
}

BATCH_SIZE = 10
FETCH_DELAY = 0.4
INSERT_CHUNK = 500
PERIOD = '2y'
INTERVAL = '1d'

def get_all_etfs():
    resp = requests.get(f'{REST_URL}/foreign_etfs?select=symbol', headers=HEADERS, timeout=30)
    return [e['symbol'] for e in resp.json()]

def backfill_batch(symbols):
    results = []
    all_rows = []

    for symbol in symbols:
        try:
            t = yf.Ticker(symbol)
            h = t.history(period=PERIOD, interval=INTERVAL)
            if h is None or h.empty:
                results.append(f'{symbol}:no_data')
                time.sleep(FETCH_DELAY)
                continue
            for dt, row in h.iterrows():
                all_rows.append({
                    'symbol': symbol,
                    'date': dt.strftime('%Y-%m-%d'),
                    'open': float(row['Open']),
                    'high': float(row['High']),
                    'low': float(row['Low']),
                    'close': float(row['Close']),
                    'volume': int(row['Volume'])
                })
            results.append(f'{symbol}:{len(h)}rows')
        except Exception as e:
            results.append(f'{symbol}:ERR')
        time.sleep(FETCH_DELAY)

    # DELETE then INSERT for each symbol individually (safer)
    from collections import defaultdict
    by_sym = defaultdict(list)
    for r in all_rows:
        by_sym[r['symbol']].append(r)

    for sym, rows in by_sym.items():
        # Delete existing
        requests.delete(f'{REST_URL}/foreign_etf_prices?symbol=eq.{urllib.parse.quote(sym)}', headers=HEADERS, timeout=30)
        # Insert new
        for i in range(0, len(rows), INSERT_CHUNK):
            chunk = rows[i:i+INSERT_CHUNK]
            r = requests.post(f'{REST_URL}/foreign_etf_prices', headers=HEADERS, data=json.dumps(chunk), timeout=60)
            if r.status_code not in (200, 201):
                print(f'  INSERT_ERR {sym}:{r.status_code}')

    return results

def main():
    print('Fetching ETF list...')
    all_etfs = get_all_etfs()
    print(f'Total ETFs to backfill: {len(all_etfs)}')

    total_batches = (len(all_etfs) + BATCH_SIZE - 1) // BATCH_SIZE
    ok_count = 0
    err_count = 0

    for i in range(0, len(all_etfs), BATCH_SIZE):
        batch = all_etfs[i:i+BATCH_SIZE]
        batch_num = i // BATCH_SIZE + 1
        print(f'Batch {batch_num}/{total_batches}: {batch}', flush=True)

        results = backfill_batch(batch)
        for r in results:
            if 'no_data' in r or 'ERR' in r:
                err_count += 1
            else:
                ok_count += 1

        print(f'  -> {", ".join(results)}', flush=True)

    print(f'\nDONE: OK={ok_count} ERR={err_count}')

if __name__ == '__main__':
    main()