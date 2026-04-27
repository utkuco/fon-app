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

all_symbols = [r['symbol'] for r in rest_get('foreign_etfs', {'select': 'symbol'})]
print(f"Total ETFs: {len(all_symbols)}")

batch_size = 20
fetch_delay = 0.3
insert_chunk = 500
period = '2y'
interval = '1d'

total_inserted = 0
total_errors = 0

for batch_idx in range((len(all_symbols) + batch_size - 1) // batch_size):
    batch = all_symbols[batch_idx * batch_size:batch_idx * batch_size + batch_size]
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
                print(f'{symbol}: {len(h)} rows OK')
            else:
                print(f'{symbol}: no data')
        except Exception as e:
            print(f'{symbol}: ERROR {e}')
            total_errors += 1
        time.sleep(fetch_delay)

    if all_rows:
        by_sym = {}
        for r in all_rows:
            by_sym.setdefault(r['symbol'], []).append(r)
        for sym, sym_rows in by_sym.items():
            requests.delete(f'{REST_URL}/foreign_etf_prices?symbol=eq.{urllib.parse.quote(sym)}', headers=HEADERS, timeout=30)
            for i in range(0, len(sym_rows), insert_chunk):
                chunk = sym_rows[i:i + insert_chunk]
                r = requests.post(REST_URL + '/foreign_etf_prices', headers={**HEADERS, 'Prefer': 'return=minimal'}, data=json.dumps(chunk), timeout=60)
                if r.status_code not in (200, 201):
                    print(f'ERR {sym}: {r.status_code} {r.text[:100]}')
        total_inserted += len(all_rows)
        print(f'Batch {batch_idx + 1}: inserted {len(all_rows)} rows')

print(f'BACKFILL_COMPLETE — Total inserted: {total_inserted}, Errors: {total_errors}')
