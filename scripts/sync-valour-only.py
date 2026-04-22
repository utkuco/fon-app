#!/usr/bin/env python3
"""
Fetch purchase/sale valour from TEFAS FonAnaliz pages and write to Supabase.
Skips the API step (rate-limited). Fast parallel scraping.

Usage: python3 scripts/sync-valour-only.py
"""
import time
import requests
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed

SBKEY = "sb_secret_PkAEAOU2YO4YS-ELYpwS5w_SsVg2kqi"
PROJECT_REF = "oqkobptbvcazifpvjwfz"
REST_URL = f"https://{PROJECT_REF}.supabase.co/rest/v1"

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'tr-TR,tr;q=0.9',
}


def parse_turkish_number(s):
    if not s or s.strip() in ('', '-', '—', 'N/A'):
        return None
    s = s.strip().replace('%', '').replace('.', '').replace(',', '.')
    try:
        return float(s)
    except:
        return None


def get_all_codes():
    """Get ALL fund codes from Supabase (paginated)."""
    all_codes = []
    LIMIT = 1000
    offset = 0
    while True:
        r = requests.get(
            f"{REST_URL}/funds?select=code&limit={LIMIT}&offset={offset}",
            headers={"apikey": SBKEY, "Authorization": f"Bearer {SBKEY}"},
            timeout=30
        )
        batch = r.json()
        if not batch:
            break
        all_codes.extend([row['code'] for row in batch])
        if len(batch) < LIMIT:
            break
        offset += LIMIT
    return all_codes


def fetch_valour(code):
    """Fetch purchase/sale valour from TEFAS page."""
    try:
        resp = requests.get(
            f'https://www.tefas.gov.tr/FonAnaliz.aspx?FonKod={code}',
            headers=HEADERS,
            timeout=20
        )
        soup = BeautifulSoup(resp.text, 'html.parser')
        table = soup.find('table', id='MainContent_DetailsViewFund')
        if not table:
            return code, None, None
        data = {}
        for row in table.find_all('tr'):
            cells = row.find_all('td')
            if len(cells) == 2:
                key = cells[0].text.strip()
                value = cells[1].text.strip()
                data[key] = value
        alis = parse_turkish_number(data.get('Fon Alış Valörü', ''))
        satis = parse_turkish_number(data.get('Fon Satış Valörü', ''))
        return code, alis, satis
    except Exception:
        return code, None, None


def supabase_update(rows):
    """Bulk update funds via REST API."""
    if not rows:
        return
    for i in range(0, len(rows), 100):
        chunk = rows[i:i+100]
        r = requests.patch(
            f"{REST_URL}/funds",
            headers={
                "apikey": SBKEY,
                "Authorization": f"Bearer {SBKEY}",
                "Content-Type": "application/json",
                "Prefer": "resolution=merge-duplicates"
            },
            json=chunk,
            timeout=30
        )
        print(f"  Updated {len(chunk)} rows: {r.status_code}")
        if r.status_code not in (200, 201, 204):
            print(f"  Error: {r.text[:200]}")


def main():
    print("=" * 60)
    print("TEFAS Valour Sync (valour-only, parallel)")
    print("=" * 60)

    # Step 1: Get all fund codes
    print("\n[1/3] Getting fund codes from Supabase...")
    our_codes = get_all_codes()
    print(f"  Total funds in DB: {len(our_codes)}")

    # Step 2: Scrape valour (parallel, 8 workers)
    print(f"\n[2/3] Scraping valour for {len(our_codes)} funds (8 workers)...")
    valor_data = {}
    total = len(our_codes)
    completed = 0

    # Warm up with a page visit
    requests.get('https://www.tefas.gov.tr/', timeout=10)
    time.sleep(1)

    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = {executor.submit(fetch_valour, code): code for code in our_codes}
        for future in as_completed(futures):
            code, alis, satis = future.result()
            if alis is not None or satis is not None:
                valor_data[code] = {
                    'purchase_valor': int(alis) if alis is not None else None,
                    'sale_valor': int(satis) if satis is not None else None,
                }
            completed += 1
            if completed % 200 == 0:
                print(f"  Progress: {completed}/{total} ({(completed)*100//total}%)")
            time.sleep(0.05)  # per-worker rate limit

    print(f"  Funds with valour data: {len(valor_data)}")

    # Step 3: Write to Supabase
    print("\n[3/3] Writing to Supabase...")
    rows_to_update = [
        {'code': code, **data}
        for code, data in valor_data.items()
    ]
    supabase_update(rows_to_update)

    # Final check via mgmt API
    print("\n✅ Done! Final counts:")
    MGMT_URL = f"https://api.supabase.com/v1/projects/{PROJECT_REF}/database/query"
    PAT = "sbp_2bae75d499f3fdfd5fda3cd865cc33dcdd769e40"
    r = requests.post(
        MGMT_URL,
        headers={"Authorization": f"Bearer {PAT}", "Content-Type": "application/json"},
        json={"query": "SELECT COUNT(*) as total, COUNT(purchase_valor) as with_pv, COUNT(sale_valor) as with_sv FROM funds"},
        timeout=30
    )
    result = r.json()
    if result:
        row = result[0]
        print(f"   Total funds:     {row['total']}")
        print(f"   purchase_valor:   {row['with_pv']}")
        print(f"   sale_valor:      {row['with_sv']}")


if __name__ == '__main__':
    main()
