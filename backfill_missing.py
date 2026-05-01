#!/usr/bin/env python3.11
"""Backfill sparkline data for missing ETFs in foreign_etf_prices.
Only backfills ETFs that are in foreign_etfs but missing from foreign_etf_prices.
Uses DELETE + INSERT per symbol (idempotent per symbol).
"""
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

INSERT_CHUNK = 500
FETCH_DELAY = 0.5  # seconds between yfinance calls
PERIOD = '2y'
INTERVAL = '1d'

def rest_get(table, params=None):
    url = f'{REST_URL}/{table}'
    if params:
        qs = '&'.join(f'{urllib.parse.quote(k)}={urllib.parse.quote(str(v))}' for k, v in params.items())
        url = f'{url}?{qs}'
    resp = requests.get(url, headers=HEADERS, timeout=30)
    if resp.status_code == 416:
        return []
    if resp.status_code != 200:
        raise Exception(f'GET {url} -> {resp.status_code}: {resp.text[:200]}')
    return resp.json()

def rest_delete(table, params=None):
    url = f'{REST_URL}/{table}'
    if params:
        qs = '&'.join(f'{urllib.parse.quote(k)}={urllib.parse.quote(str(v))}' for k, v in params.items())
        url = f'{url}?{qs}'
    resp = requests.delete(url, headers=HEADERS, timeout=30)
    return resp.status_code

def rest_post(table, data):
    resp = requests.post(
        f'{REST_URL}/{table}',
        headers=HEADERS,
        data=json.dumps(data),
        timeout=60
    )
    return resp.status_code, resp.text[:200] if resp.text else ''

def get_missing_etfs():
    """Get ETFs in foreign_etfs that have no sparkline data yet."""
    print('Fetching ETF lists...')
    all_etfs = set(r['symbol'] for r in rest_get('foreign_etfs', {'select': 'symbol'}))
    print(f'foreign_etfs count: {len(all_etfs)}')

    # Collect all symbols that have sparkline data (paginate through foreign_etf_prices)
    seen = set()
    offset = 0
    while True:
        data = rest_get('foreign_etf_prices', {
            'select': 'symbol',
            'order': 'symbol',
            'limit': 1000,
            'offset': offset
        })
        if not data:
            break
        for d in data:
            seen.add(d['symbol'])
        offset += 1000
        if offset >= 500000:  # safety limit
            break
        if offset % 10000 == 0:
            print(f'  ...offset {offset}, seen {len(seen)} unique symbols')

    print(f'Symbols in foreign_etf_prices: {len(seen)}')
    missing = sorted(all_etfs - seen)
    print(f'Missing (need to backfill): {len(missing)}')
    return missing

def backfill_etf(symbol):
    """Fetch sparkline data for a single ETF and insert into DB."""
    try:
        t = yf.Ticker(symbol)
        h = t.history(period=PERIOD, interval=INTERVAL)
        if h is None or h.empty:
            return None, f'{symbol}: no data from yfinance'
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
        return rows, f'{symbol}:{len(h)} rows OK'
    except Exception as e:
        return None, f'{symbol}: ERROR {e}'

def run():
    missing = get_missing_etfs()
    if not missing:
        print('No missing ETFs — all done!')
        return

    print(f'\nStarting backfill for {len(missing)} ETFs...')
    print(f'BATCH_SIZE=20, DELAY={FETCH_DELAY}s, CHUNK={INSERT_CHUNK}\n')

    total_inserted = 0
    total_errors = 0
    batch_size = 20

    for batch_idx in range((len(missing) + batch_size - 1) // batch_size):
        batch = missing[batch_idx * batch_size : batch_idx * batch_size + batch_size]
        all_rows = []
        batch_results = []

        for symbol in batch:
            rows, msg = backfill_etf(symbol)
            batch_results.append(msg)
            if rows:
                all_rows.extend(rows)
            time.sleep(FETCH_DELAY)

        # DELETE existing rows for each symbol in batch (clean slate)
        # This ensures we don't get duplicates even if backfill ran before
        for symbol in batch:
            status = rest_delete('foreign_etf_prices', {'symbol': f'eq.{symbol}'})
            if status not in (204, 200):
                print(f'  WARN: DELETE {symbol} returned {status}')

        # INSERT new rows
        if all_rows:
            # Group by symbol for clean inserts
            by_sym = {}
            for r in all_rows:
                by_sym.setdefault(r['symbol'], []).append(r)

            for sym, sym_rows in by_sym.items():
                for i in range(0, len(sym_rows), INSERT_CHUNK):
                    chunk = sym_rows[i:i + INSERT_CHUNK]
                    status, text = rest_post('foreign_etf_prices', chunk)
                    if status not in (200, 201):
                        print(f'  ERR {sym}: status={status} text={text}')
            total_inserted += len(all_rows)

        # Print batch summary
        good = [m for m in batch_results if 'ERROR' not in m and 'no data' not in m]
        bad = [m for m in batch_results if 'ERROR' in m or 'no data' in m]
        print(f'Batch {batch_idx+1}/{(len(missing)+batch_size-1)//batch_size}: '
              f'OK={len(good)} ERR={len(bad)} rows={len(all_rows)} '
              f'({", ".join(batch_results[:3])}{"..." if len(batch_results)>3 else ""})')

        if bad:
            total_errors += len(bad)

    print(f'\nBACKFILL_COMPLETE')
    print(f'Total rows inserted: {total_inserted}')
    print(f'ETFs with errors: {total_errors}')

if __name__ == '__main__':
    run()