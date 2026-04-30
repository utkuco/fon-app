#!/usr/bin/env python3
"""Tefas data import using the tefas Python package (YYYY-MM-DD format)."""
import sqlite3
import time
from pathlib import Path
from datetime import datetime, timedelta

from tefas import Crawler

DB = Path(__file__).parent / "db" / "fonapp.db"

def guess_type(title):
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

# Find most recent trading day that has data (try up to 7 days back)
print("Finding most recent trading day with data...")
crawler = Crawler()
target = None
for back in range(1, 8):
    d = datetime.now() - timedelta(days=back)
    if d.weekday() >= 5:
        continue  # skip weekends
    date_str = d.strftime("%Y-%m-%d")
    try:
        test = crawler.fetch(date_str, date_str, kind='YAT')
        if len(test) > 0:
            target = date_str
            print(f"  Using date: {target} ({len(test)} rows)")
            break
    except Exception as e:
        print(f"  {date_str}: error {e}")
        continue

if target is None:
    print("ERROR: No trading data found in past 7 days!")
    exit(1)

all_funds = {}

for kind in ["YAT", "EMK", "BYF"]:
    print(f"Fetching {kind} for {target}...")
    try:
        data = crawler.fetch(target, target, kind=kind)
        print(f"  Got {len(data)} rows")
        if len(data) == 0:
            continue
        for _, row in data.iterrows():
            code = str(row.get("code", "")).strip()
            if not code or code == "nan" or code in all_funds:
                continue
            all_funds[code] = {
                "code": code,
                "title": str(row.get("title", "")),
                "price": row.get("price"),
                "date": row.get("date", target),
                "market_cap": row.get("market_cap"),
                "number_of_shares": row.get("number_of_shares"),
                "number_of_investors": row.get("number_of_investors"),
            }
        time.sleep(1)  # rate limit
    except Exception as e:
        print(f"  ERROR fetching {kind}: {e}")

print(f"\nTotal unique funds: {len(all_funds)}")

# Create table
conn = sqlite3.connect(str(DB))
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
)
""")

inserted = 0
for code, fund in all_funds.items():
    ft = guess_type(fund["title"])
    conn.execute(f"""INSERT OR REPLACE INTO tefas_funds
        (tefas_code, title, fund_type, price, price_date, market_cap,
         number_of_shares, number_of_investors,
         stock, government_bond, private_sector_bond, eurobond, gold,
         repo, reverse_repo, treasury_bill, bank_bills, commercial_paper,
         term_deposit, etf, derivatives, foreign_equity, foreign_bond,
         precious_metals, participation_account, other)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (code, fund["title"], ft, fund["price"], fund["date"], fund["market_cap"],
         fund["number_of_shares"], fund["number_of_investors"],
         None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None))
    inserted += 1

conn.commit()

# Stats
cur = conn.cursor()
cur.execute("SELECT COUNT(*) FROM tefas_funds")
total = cur.fetchone()[0]
cur.execute("SELECT COUNT(*) FROM funds")
kap_total = cur.fetchone()[0]
cur.execute("SELECT COUNT(*) FROM funds WHERE tefas_code IS NOT NULL")
mapped = cur.fetchone()[0]
conn.close()

print(f"\n{'='*50}")
print(f"✅ Done!")
print(f"  Tefas funds:      {total}")
print(f"  KAP funds:        {kap_total}")
print(f"  KAP→Tefas mapped: {mapped}")
print(f"{'='*50}")
