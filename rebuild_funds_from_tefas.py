#!/usr/bin/env python3
"""
Tefas data import using TEFAS REST API (no Chrome needed).
Fetches: FonBilgiGetir (metadata) + fonFiyatBilgiGetir periyod=1 (latest price date).

REBUILT 2026-05-01: tefas Python package is WRONG (YouTube transcription tool).
fundturkey.com.tr API is permanently shut down (404 as of 2026-04-27).
Now uses TEFAS official REST API at https://www.tefas.gov.tr/api/funds/*

Uses ThreadPoolExecutor for parallel API calls (much faster).
"""
import sqlite3
import time
import json
import warnings
import requests
from pathlib import Path
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from queue import Queue

warnings.filterwarnings('ignore')

DB = Path(__file__).parent / "db" / "fonapp.db"
TEFAS_FIYAT_URL = "https://www.tefas.gov.tr/api/funds/fonFiyatBilgiGetir"
TEFAS_BILGI_URL = "https://www.tefas.gov.tr/api/funds/FonBilgiGetir"

HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json",
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
}


def fetch_fund_data(code: str) -> dict:
    """Fetch both FonBilgiGetir metadata and latest price for one fund."""
    result = {"code": code, "bilgi": None, "price_info": None}

    # Try FonBilgiGetir (metadata)
    try:
        r = requests.post(
            TEFAS_BILGI_URL,
            data=json.dumps({"fonKodu": code, "dil": "TR"}),
            headers=HEADERS,
            timeout=8,
            verify=False
        )
        data = r.json()
        rows = data.get("resultList", [])
        if rows:
            result["bilgi"] = rows[0]
    except Exception:
        pass

    # Try fonFiyatBilgiGetir periyod=1 (latest price date)
    try:
        r = requests.post(
            TEFAS_FIYAT_URL,
            data=json.dumps({"fonKodu": code, "dil": "TR", "periyod": 1}),
            headers=HEADERS, timeout=10,
            verify=False)
        data = r.json()
        rows = data.get("resultList", [])
        if rows:
            last = rows[-1]
            tarih = last.get("tarih", "")
            fiyat = last.get("fiyat")
            if tarih and fiyat:
                # Tarih can be YYYY-MM-DD or DD.MM.YYYY depending on periyod
                if "-" in tarih and tarih.count("-") == 2:
                    iso_date = tarih  # Already YYYY-MM-DD
                elif "." in tarih:
                    parts = tarih.split(".")
                    if len(parts) == 3:
                        iso_date = f"{parts[2]}-{parts[1]}-{parts[0]}"
                    else:
                        iso_date = tarih
                else:
                    iso_date = tarih
                result["price_info"] = (iso_date, float(fiyat))
    except Exception:
        pass  # periyod=1 failed — bilgi.sonFiyat will be used as fallback

    return result


def parse_eu_num(s):
    """Parse EU number format (1.234,56) to float."""
    if s is None:
        return None
    s = str(s).strip()
    if not s:
        return None
    has_dot = '.' in s
    has_comma = ',' in s
    if has_dot and has_comma:
        if s.rfind('.') > s.rfind(','):
            s = s.replace(',', '')
        else:
            s = s.replace('.', '').replace(',', '.')
    elif has_comma and not has_dot:
        s = s.replace(',', '.')
    try:
        return float(s)
    except:
        return None


def guess_type(title: str) -> str:
    if not title:
        return "VFF"
    t = str(title).upper()
    if any(x in t for x in ["DEĞİŞKEN", "VARYANT", "VARİABLE"]): return "VFF"
    if any(x in t for x in ["SERBEST", "FREE"]): return "SRF"
    if any(x in t for x in ["ÖZEL SEKTÖR", "FON SEPETİ", "PORTFÖY SEPETİ"]): return "OKS"
    if any(x in t for x in ["DÖVİZ", "USD", "EUR/", "EURO"]): return "DÖVİZ"
    if any(x in t for x in ["ALTIN", "GOLD", "GRAM"]): return "ALTIN"
    if any(x in t for x in ["BORÇLANMA", "TAHVİL", "BONO"]): return "KFF"
    if any(x in t for x in ["BYF", "ETF", "BORSADA İŞLEM"]): return "BYF"
    return "VFF"


# Get all fund codes from funds table
print("Reading fund codes from SQLite...", flush=True)
conn = sqlite3.connect(str(DB))
cur = conn.cursor()

cur.execute("SELECT code, name, fund_type FROM funds WHERE code IS NOT NULL")
fund_rows = cur.fetchall()
fund_codes = [(row[0], row[1], row[2]) for row in fund_rows]
print(f"  Total funds in DB: {len(fund_codes)}", flush=True)

# Create/recreate tefas_funds table
conn.execute("DROP TABLE IF EXISTS tefas_funds")
conn.execute("""CREATE TABLE tefas_funds (
    id INTEGER PRIMARY KEY,
    tefas_code TEXT UNIQUE NOT NULL,
    title TEXT,
    fund_type TEXT,
    price REAL,
    price_date TEXT,
    daily_change REAL,
    market_cap REAL,
    number_of_shares REAL,
    number_of_investors REAL,
    stock REAL, government_bond REAL, private_sector_bond REAL,
    eurobond REAL, gold REAL, repo REAL, reverse_repo REAL,
    treasury_bill REAL, bank_bills REAL, commercial_paper REAL,
    term_deposit REAL, etf REAL, derivatives REAL,
    foreign_equity REAL, foreign_bond REAL, precious_metals REAL,
    participation_account REAL, other REAL,
    fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)""")
conn.commit()

print(f"\nFetching TEFAS data with 20 parallel workers...", flush=True)

inserted = 0
errors = 0
results_map = {}

with ThreadPoolExecutor(max_workers=20) as executor:
    future_to_code = {executor.submit(fetch_fund_data, code): code for code, _, _ in fund_codes}
    done = 0
    for future in as_completed(future_to_code):
        done += 1
        if done % 100 == 0:
            print(f"  Progress: {done}/{len(fund_codes)}...", flush=True)
        try:
            result = future.result()
            results_map[result["code"]] = result
        except Exception as e:
            code = future_to_code[future]
            errors += 1
            if errors <= 3:
                print(f"  {code}: error {e}", flush=True)

print(f"  Fetched {len(results_map)} results, {errors} errors", flush=True)

# Now write all results to DB
print("Writing to SQLite...", flush=True)
for code, name, existing_type in fund_codes:
    result = results_map.get(code)
    if result is None:
        errors += 1
        continue

    bilgi = result.get("bilgi")
    price_info = result.get("price_info")

    if bilgi is None and price_info is None:
        errors += 1
        if errors <= 5:
            print(f"  {code}: No data from TEFAS API (bilgi={'YES' if bilgi else 'NO'}, price={'YES' if price_info else 'NO'})", flush=True)
        continue

    title = bilgi.get("fonUnvan", name) if bilgi else name
    fund_type = existing_type or guess_type(title)

    price = None
    price_date = None
    daily_change = None
    if price_info:
        price_date, price = price_info
    if bilgi:
        daily_change = parse_eu_num(str(bilgi.get("gunlukGetiri", "")))
        market_cap = parse_eu_num(str(bilgi.get("portBuyukluk", "")))
        number_of_shares = parse_eu_num(str(bilgi.get("payAdet", "")))
        number_of_investors = parse_eu_num(str(bilgi.get("yatirimciSayi", "")))
        # If no price from periyod=1, use sonFiyat from bilgi
        if price is None:
            price_raw = bilgi.get("sonFiyat")
            if price_raw is not None:
                price = parse_eu_num(str(price_raw))
    else:
        market_cap = None
        number_of_shares = None
        number_of_investors = None

    conn.execute(f"""INSERT OR REPLACE INTO tefas_funds
        (tefas_code, title, fund_type, price, price_date, daily_change,
         market_cap, number_of_shares, number_of_investors,
         stock, government_bond, private_sector_bond, eurobond, gold,
         repo, reverse_repo, treasury_bill, bank_bills, commercial_paper,
         term_deposit, etf, derivatives, foreign_equity, foreign_bond,
         precious_metals, participation_account, other)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (code, title, fund_type, price, price_date, daily_change,
         market_cap, number_of_shares, number_of_investors,
         None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None))
    inserted += 1

    # Also update the funds table with price data
    if price is not None:
        conn.execute(f"""UPDATE funds SET
            price = ?, price_date = ?, daily_change = ?, market_cap = ?,
            number_of_shares = ?, number_of_investors = ?, tefas_title = ?
            WHERE code = ?""",
            (price, price_date, daily_change, market_cap,
             number_of_shares, number_of_investors, title, code))

conn.commit()
conn.close()

print(f"\n{'='*50}", flush=True)
print(f"✅ Done! TEFAS API fetch complete.", flush=True)
print(f"  Inserted/updated: {inserted}", flush=True)
print(f"  Not found/delisted: {errors}", flush=True)
print(f"{'='*50}", flush=True)
