import os, sys, time, json, tempfile, warnings
warnings.filterwarnings('ignore')
import yfinance as yf
yf.set_tz_cache_location(tempfile.mkdtemp())
from supabase import create_client, Client

SUPABASE_URL = 'https://oqkobptbvcazifpvjwfz.supabase.co'
SUPABASE_KEY = 'sb_secret_PkAEAOU2YO4YS-ELYpwS5w_SsVg2kqi'

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Get all ETF symbols
response = supabase.table('foreign_etfs').select('symbol').execute()
all_symbols = [r['symbol'] for r in response.data]
print(f"Total ETFs: {len(all_symbols)}", flush=True)

batch_size = 20
fetch_delay = 0.3
period = '2y'
interval = '1d'

total_fetched = 0
total_upserted = 0

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
                print(f'{symbol}:{len(h)} rows fetched', flush=True)
                total_fetched += len(h)
            else:
                print(f'{symbol}: no data', flush=True)
        except Exception as e:
            print(f'{symbol}: ERROR {e}', flush=True)
        time.sleep(fetch_delay)

    if all_rows:
        # Upsert in chunks using supabase python client
        chunk_size = 500
        for i in range(0, len(all_rows), chunk_size):
            chunk = all_rows[i:i + chunk_size]
            try:
                result = supabase.table('foreign_etf_prices').upsert(
                    chunk,
                    on_conflict='symbol,date'
                ).execute()
                total_upserted += len(chunk)
            except Exception as e:
                print(f'UPSERT ERR: {e}', flush=True)
        print(f'Batch {batch_idx + 1}: upserted {len(all_rows)} rows', flush=True)

print(f'BACKFILL_COMPLETE: fetched={total_fetched} upserted={total_upserted}', flush=True)
