import os, sys, time, json, tempfile, warnings, urllib.parse
warnings.filterwarnings('ignore')
import requests
import yfinance as yf
yf.set_tz_cache_location(tempfile.mkdtemp())

SUPABASE_URL = 'https://oqkobptbvcazifpvjwfz.supabase.co'
SUPABASE_KEY = 'sb_secret_PkAEAOU2YO4YS-ELYpwS5w_SsVg2kqi'
REST_URL = f'{SUPABASE_URL}/rest/v1'
HEADERS = {'apikey': SUPABASE_KEY, 'Authorization': f'Bearer {SUPABASE_KEY}', 'Content-Type': 'application/json'}

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

# First check current state
current_prices = rest_get('foreign_etf_prices', {'select': 'symbol'})
current_symbols = set(d['symbol'] for d in current_prices)
print(f'Current symbols with data: {len(current_symbols)}: {sorted(current_symbols)}')

# Check foreign_etfs list
all_etfs_data = rest_get('foreign_etfs', {'select': 'symbol'})
all_symbols = [r['symbol'] for r in all_etfs_data]
print(f'Total ETFs in foreign_etfs: {len(all_symbols)}')

# Only backfill ETFs that don't have data
symbols_to_backfill = [s for s in all_symbols if s not in current_symbols]
print(f'Symbols needing backfill: {len(symbols_to_backfill)}')

if not symbols_to_backfill:
    print('NO_BACKFILL_NEEDED')
    sys.exit(0)

# Use batch_size that works with yfinance rate limits
batch_size = 10
fetch_delay = 0.5
insert_chunk = 500
period = '2y'
interval = '1d'

total_batches = (len(symbols_to_backfill) + batch_size - 1) // batch_size
total_inserted = 0
total_errors = 0

for batch_idx in range(total_batches):
    batch = symbols_to_backfill[batch_idx * batch_size : batch_idx * batch_size + batch_size]
    all_rows = []
    for symbol in batch:
        try:
            t = yf.Ticker(symbol)
            h = t.history(period=period, interval=interval)
            if h is not None and not h.empty:
                rows_count = 0
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
                    rows_count += 1
                print(f'  {symbol}:{rows_count} rows')
            else:
                print(f'  {symbol}: no data')
        except Exception as e:
            print(f'  {symbol}: ERROR {e}')
        time.sleep(fetch_delay)

    # Insert rows grouped by symbol
    if all_rows:
        by_sym = {}
        for r in all_rows:
            by_sym.setdefault(r['symbol'], []).append(r)
        
        batch_inserted = 0
        for sym, sym_rows in by_sym.items():
            # Skip delete - only insert (don't delete existing good data)
            for i in range(0, len(sym_rows), insert_chunk):
                chunk = sym_rows[i:i+insert_chunk]
                r = requests.post(
                    REST_URL + '/foreign_etf_prices',
                    headers={**HEADERS, 'Prefer': 'return=minimal'},
                    data=json.dumps(chunk),
                    timeout=60
                )
                if r.status_code not in (200, 201):
                    print(f'  ERR INSERT {sym}:{r.status_code} {r.text[:100]}')
                    total_errors += 1
                else:
                    batch_inserted += len(chunk)
        
        total_inserted += batch_inserted
        print(f'Batch {batch_idx+1}/{total_batches}: inserted {batch_inserted} rows')

print(f'BACKFILL_COMPLETE: {total_inserted} rows inserted, {total_errors} errors')
