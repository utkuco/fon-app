#!/usr/bin/env python3
"""
Sync management_fee, max_total_expense_ratio, and valors from tefas.gov.tr
to the Supabase funds table.

Usage: python3 sync-tefas-fees.py
"""
import requests
from bs4 import BeautifulSoup
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

SBKEY = "sb_secret_PkAEAOU2YO4YS-ELYpwS5w_SsVg2kqi"
PROJECT_REF = "oqkobptbvcazifpvjwfz"
REST_URL = f"https://{PROJECT_REF}.supabase.co/rest/v1"
MGMT_URL = f"https://api.supabase.com/v1/projects/{PROJECT_REF}/database/query"

PAT = "sbp_2bae75d499f3fdfd5fda3cd865cc33dcdd769e40"

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'tr-TR,tr;q=0.9',
}
API_HEADERS = {
    'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
    'Accept': 'application/json, text/javascript, */*; q=0.01',
    'Origin': 'https://www.tefas.gov.tr',
    'Referer': 'https://www.tefas.gov.tr/',
}


def mgmt(sql, timeout=60):
    r = requests.post(
        MGMT_URL,
        headers={"Authorization": f"Bearer {PAT}", "Content-Type": "application/json"},
        json={"query": sql},
        timeout=timeout
    )
    return r


def supabase_update(rows):
    """Bulk update funds with new fee data via REST API."""
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


def parse_turkish_number(s):
    """Parse Turkish number format: 2,9 -> 2.9"""
    if not s or s.strip() in ('', '-', '—', 'N/A'):
        return None
    s = s.strip().replace('%', '').replace('.', '').replace(',', '.')
    try:
        return float(s)
    except:
        return None


def fetch_api_data():
    """Fetch management fee and expense ratio for all fund types from API."""
    all_data = {}
    for fontip in ['YAT', 'EMK', 'BYF']:
        payload = {"islemdurum": "1", "fontip": fontip}
        try:
            resp = requests.post(
                'https://www.tefas.gov.tr/api/DB/BindComparisonManagementFees',
                data=payload,
                headers=API_HEADERS,
                timeout=30
            )
            items = resp.json().get('data', [])
            print(f"  {fontip}: {len(items)} funds from API")
            for item in items:
                code = item.get('FONKODU')
                if not code:
                    continue
                # Parse Turkish number format
                mgmt_fee = parse_turkish_number(item.get('FONICTUZUKYU1G', ''))
                expense_ratio = parse_turkish_number(item.get('FONTOPGIDERKESORAN', ''))
                all_data[code] = {
                    'management_fee': mgmt_fee,
                    'max_total_expense_ratio': expense_ratio,
                }
        except Exception as e:
            print(f"  {fontip}: ERROR - {e}")
        time.sleep(0.3)
    return all_data


def fetch_valor(session, code):
    """Fetch purchase_valor and sale_valor from FonAnaliz.aspx page."""
    try:
        resp = session.get(
            f'https://www.tefas.gov.tr/FonAnaliz.aspx?FonKod={code}',
            headers=HEADERS,
            timeout=20
        )
        soup = BeautifulSoup(resp.text, 'html.parser')
        profile_table = soup.find('table', id='MainContent_DetailsViewFund')
        if not profile_table:
            return None, None
        data = {}
        for row in profile_table.find_all('tr'):
            cells = row.find_all('td')
            if len(cells) == 2:
                key = cells[0].text.strip()
                value = cells[1].text.strip()
                data[key] = value
        # Parse valors
        alis = parse_turkish_number(data.get('Fon Alış Valörü', ''))
        satis = parse_turkish_number(data.get('Fon Satış Valörü', ''))
        return alis, satis
    except Exception as e:
        return None, None


def main():
    print("=" * 60)
    print("TEFAS Fee & Valor Sync")
    print("=" * 60)

    # Step 1: Fetch API data (management_fee, expense_ratio)
    print("\n[1/3] Fetching management fee data from API...")
    api_data = fetch_api_data()
    print(f"  Total funds with API data: {len(api_data)}")

    # Step 2: Fetch valors from pages (for funds that exist in our DB)
    print("\n[2/3] Fetching valor data from detail pages...")

    # Get ALL fund codes from our Supabase DB (REST API paginates at 1000, so loop)
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
    our_codes = all_codes
    print(f"  Funds in our DB: {len(our_codes)}")

    session = requests.Session()
    session.headers.update(HEADERS)
    # First visit to get cookies
    session.get('https://www.tefas.gov.tr/', timeout=10)
    time.sleep(0.5)

    # Parallel valour fetching (8 workers)
    valor_data = {}
    total = len(our_codes)
    completed = 0

    def _fetch_one(code):
        # Each worker needs its own session to avoid connection sharing issues
        s = requests.Session()
        s.headers.update(HEADERS)
        try:
            resp = s.get(
                f'https://www.tefas.gov.tr/FonAnaliz.aspx?FonKod={code}',
                headers=HEADERS,
                timeout=15
            )
            soup = BeautifulSoup(resp.text, 'html.parser')
            profile_table = soup.find('table', id='MainContent_DetailsViewFund')
            if not profile_table:
                return code, None, None
            data = {}
            for row in profile_table.find_all('tr'):
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

    print(f"  Scraping valör for {total} funds (8 workers)...")
    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = {executor.submit(_fetch_one, code): code for code in our_codes}
        for future in as_completed(futures):
            code, alis, satis = future.result()
            if alis is not None or satis is not None:
                valor_data[code] = {'purchase_valor': alis, 'sale_valor': satis}
            completed += 1
            if completed % 200 == 0:
                print(f"  Progress: {completed}/{total} ({(completed)*100//total}%)")
            time.sleep(0.05)  # rate limit per worker

    print(f"  Funds with valor data: {len(valor_data)}")

    # Step 3: Merge and update Supabase
    print("\n[3/3] Updating Supabase...")

    # Build update payload
    rows_to_update = []
    all_codes = set(list(api_data.keys()) + list(valor_data.keys()))

    for code in all_codes:
        row = {'code': code}
        if code in api_data:
            if api_data[code]['management_fee'] is not None:
                row['management_fee'] = api_data[code]['management_fee']
            if api_data[code]['max_total_expense_ratio'] is not None:
                row['max_total_expense_ratio'] = api_data[code]['max_total_expense_ratio']
        if code in valor_data:
            if valor_data[code]['purchase_valor'] is not None:
                row['purchase_valor'] = int(valor_data[code]['purchase_valor'])
            if valor_data[code]['sale_valor'] is not None:
                row['sale_valor'] = int(valor_data[code]['sale_valor'])
        if len(row) > 1:  # code + at least one field
            rows_to_update.append(row)

    print(f"  Rows to update: {len(rows_to_update)}")

    # Update in batches
    supabase_update(rows_to_update)

    # Verify
    r = mgmt("""
    SELECT
        COUNT(*) as total,
        COUNT(management_fee) as with_mgmt_fee,
        COUNT(purchase_valor) as with_purchase_valor,
        COUNT(sale_valor) as with_sale_valor,
        COUNT(max_total_expense_ratio) as with_expense_ratio
    FROM funds
    """)
    result = r.json()
    if result:
        row = result[0]
        print(f"\n✅ Sync complete!")
        print(f"   Total funds: {row['total']}")
        print(f"   With management_fee: {row['with_mgmt_fee']}")
        print(f"   With max_total_expense_ratio: {row['with_expense_ratio']}")
        print(f"   With purchase_valor: {row['with_purchase_valor']}")
        print(f"   With sale_valor: {row['with_sale_valor']}")


if __name__ == '__main__':
    main()
