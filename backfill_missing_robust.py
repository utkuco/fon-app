import os, sys, time, json, tempfile, warnings, urllib.parse
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

# Get all ETF symbols
all_symbols = set(r['symbol'] for r in rest_get('foreign_etfs', {'select': 'symbol'}))
print(f"Total ETFs: {len(all_symbols)}", flush=True)

# Get all symbols that already have data (using offset pagination)
symbols_with_data = set()
for offset in range(0, 10000, 1000):
    r = rest_get('foreign_etf_prices', {'select': 'symbol', 'limit': 1000, 'offset': offset})
    if not r:
        break
    for e in r:
        symbols_with_data.add(e['symbol'])
    if len(r) < 1000:
        break

missing_symbols = sorted(all_symbols - symbols_with_data)
print(f"Already have data: {len(symbols_with_data)}", flush=True)
print(f"Missing: {len(missing_symbols)}", flush=True)

if not missing_symbols:
    print("No missing ETFs - backfill not needed", flush=True)
    sys.exit(0)

# Process in small batches with retries
batch_size = 10
fetch_delay = 0.5
insert_chunk = 250
period = '2y'
interval = '1d'
max_retries = 3

total_inserted = 0
total_errors = 0

for batch_idx in range((len(missing_symbols) + batch_size - 1) // batch_size):
    batch = missing_symbols[batch_idx * batch_size:batch_idx * batch_size + batch_size]
    all_rows = []
    
    for symbol in batch:
        try:
            t = yf.Ticker(symbol)
            h = t.history(period=period, interval=interval)
            if h is not None and not h.empty:
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
                print(f'OK {symbol}: {len(h)} rows', flush=True)
            else:
                print(f'NO_DATA {symbol}', flush=True)
        except Exception as e:
            print(f'ERROR {symbol}: {e}', flush=True)
            total_errors += 1
        time.sleep(fetch_delay)

    if all_rows:
        by_sym = {}
        for r in all_rows:
            by_sym.setdefault(r['symbol'], []).append(r)
        
        for sym, sym_rows in by_sym.items():
            # Delete existing rows for this symbol
            delete_url = f'{REST_URL}/foreign_etf_prices?symbol=eq.{urllib.parse.quote(sym)}'
            del_resp = requests.delete(delete_url, headers=HEADERS, timeout=30)
            
            # Insert new rows with retry
            for i in range(0, len(sym_rows), insert_chunk):
                chunk = sym_rows[i:i + insert_chunk]
                for attempt in range(max_retries):
                    try:
                        json_data = json.dumps(chunk, allow_nan=False)
                        r = requests.post(REST_URL + '/foreign_etf_prices', 
                                         headers={**HEADERS, 'Prefer': 'return=minimal'}, 
                                         data=json_data, timeout=60)
                        if r.status_code in (200, 201):
                            break
                        print(f'RETRY {sym} attempt {attempt+1}: status={r.status_code} body={r.text[:100]}', flush=True)
                    except Exception as e:
                        print(f'RETRY {sym} attempt {attempt+1}: {e}', flush=True)
                    time.sleep(1 * (attempt + 1))
                else:
                    print(f'FAIL {sym}: all {max_retries} attempts failed', flush=True)
                    total_errors += 1
        
        total_inserted += len(all_rows)
        print(f'Batch {batch_idx + 1}: inserted {len(all_rows)} rows | total: {total_inserted}', flush=True)

print(f'BACKFILL_COMPLETE: inserted={total_inserted} errors={total_errors}', flush=True)
