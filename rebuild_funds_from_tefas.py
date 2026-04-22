#!/usr/bin/env python3
"""Simple Tefas data import — no pandas, fast."""
import sqlite3
import time
import ssl
import json
from pathlib import Path
from datetime import datetime

import requests
from requests.adapters import HTTPAdapter
from urllib3.poolmanager import PoolManager

DB = Path(__file__).parent / "db" / "fonapp.db"

class HA(HTTPAdapter):
    def __init__(self, ssl_ctx=None, **kwargs):
        self.ssl_ctx = ssl_ctx
        super().__init__(**kwargs)
    def init_poolmanager(self, connections, maxsize, block=False):
        self.poolmanager = PoolManager(
            num_pools=connections, maxsize=maxsize, block=block,
            ssl_context=self.ssl_ctx)

def get_session():
    ctx = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)
    ctx.options |= 0x4
    s = requests.session()
    s.mount("https://", HA(ssl_ctx=ctx))
    return s

def fetch_tefas(session, kind, date_str):
    """Fetch raw JSON from tefas API."""
    url = "https://fundturkey.com.tr/api/DB/BindHistoryInfo"
    headers = {
        "X-Requested-With": "XMLHttpRequest",
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        "Origin": "https://fundturkey.com.tr",
        "Referer": "https://fundturkey.com.tr/TarihselVeriler.aspx",
    }
    data = {"fontip": kind, "bastarih": date_str, "bittarih": date_str, "fonkod": ""}
    r = session.post(url, data=data, headers=headers, timeout=30)
    return r.json().get("data", [])

def fetch_breakdown(session, kind, date_str):
    url = "https://fundturkey.com.tr/api/DB/BindHistoryAllocation"
    headers = {
        "X-Requested-With": "XMLHttpRequest",
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    }
    data = {"fontip": kind, "bastarih": date_str, "bittarih": date_str, "fonkod": ""}
    try:
        r = session.post(url, data=data, headers=headers, timeout=30)
        return r.json().get("data", [])
    except:
        return []

def parse_row(row, has_breakdown=False):
    """Parse API row into normalized dict."""
    ts = row.get("TARIH", 0)
    if isinstance(ts, (int, float)) and ts > 0:
        date_str = datetime.fromtimestamp(int(ts) / 1000).strftime("%Y-%m-%d")
    else:
        date_str = "2026-04-16"
    return {
        "code": row.get("FONKODU", ""),
        "title": row.get("FONUNVAN", ""),
        "price": row.get("FIYAT"),
        "date": date_str,
        "market_cap": row.get("PORTFOYBUYUKLUK"),
        "number_of_shares": row.get("TEDPAYSAYISI"),
        "number_of_investors": row.get("KISISAYISI"),
    }

def parse_breakdown(row):
    return {
        "stock": row.get("HS", 0) or 0,
        "government_bond": row.get("DT", 0) or 0,
        "private_sector_bond": row.get("OST", 0) or 0,
        "eurobond": row.get("EUT", 0) or 0,
        "gold": row.get("KM", 0) or 0,
        "repo": row.get("R", 0) or 0,
        "reverse_repo": row.get("TR", 0) or 0,
        "treasury_bill": row.get("HB", 0) or 0,
        "bank_bills": row.get("BB", 0) or 0,
        "commercial_paper": row.get("FB", 0) or 0,
        "term_deposit": row.get("VM", 0) or 0,
        "etf": row.get("BYF", 0) or 0,
        "derivatives": row.get("T", 0) or 0,
        "foreign_equity": row.get("YHS", 0) or 0,
        "foreign_bond": row.get("YBA", 0) or 0,
        "precious_metals": row.get("KM", 0) or 0,
        "participation_account": row.get("KH", 0) or 0,
        "other": row.get("D", 0) or 0,
    }

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

print("Connecting to Tefas API...")
session = get_session()
_ = session.get("https://fundturkey.com.tr", timeout=10)

# Fetch for 3 fund types
from datetime import datetime, timedelta
import sys

# Use last business day: Friday if today is Sat/Sun, else yesterday
today = datetime.now()
if today.weekday() >= 5:  # Saturday=5, Sunday=6
    target = today - timedelta(days=2)  # Friday
elif today.weekday() == 0:  # Monday → use Friday (Sunday has no trading)
    target = today - timedelta(days=3)
else:
    target = today - timedelta(days=1)
DATE = target.strftime("%d.%m.%Y")
all_funds = {}
all_breakdown = {}

for kind in ["YAT", "EMK", "BYF"]:
    print(f"Fetching {kind}...")
    rows = fetch_tefas(session, kind, DATE)
    print(f"  Got {len(rows)} rows")
    for row in rows:
        p = parse_row(row)
        code = p["code"]
        if code and code not in all_funds:
            all_funds[code] = p

    bdata = fetch_breakdown(session, kind, DATE)
    print(f"  Got {len(bdata)} breakdown rows")
    for row in bdata:
        code = row.get("FONKODU", "")
        if code:
            all_breakdown[code] = parse_breakdown(row)

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
)""")

inserted = 0
for code, fund in all_funds.items():
    ft = guess_type(fund["title"])
    bd = all_breakdown.get(code, {})
    conn.execute(f"""INSERT OR REPLACE INTO tefas_funds
        (tefas_code, title, fund_type, price, price_date, market_cap,
         number_of_shares, number_of_investors,
         stock, government_bond, private_sector_bond, eurobond, gold,
         repo, reverse_repo, treasury_bill, bank_bills, commercial_paper,
         term_deposit, etf, derivatives, foreign_equity, foreign_bond,
         precious_metals, participation_account, other)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (code, fund["title"], ft, fund["price"], fund["date"], fund["market_cap"],
         fund["number_of_shares"], fund["number_of_investors"],
         bd.get("stock"), bd.get("government_bond"), bd.get("private_sector_bond"),
         bd.get("eurobond"), bd.get("gold"), bd.get("repo"), bd.get("reverse_repo"),
         bd.get("treasury_bill"), bd.get("bank_bills"), bd.get("commercial_paper"),
         bd.get("term_deposit"), bd.get("etf"), bd.get("derivatives"),
         bd.get("foreign_equity"), bd.get("foreign_bond"),
         bd.get("precious_metals"), bd.get("participation_account"), bd.get("other")))
    inserted += 1

conn.commit()

# Stats
c = conn.cursor()
c.execute("SELECT COUNT(*) FROM tefas_funds")
total = c.fetchone()[0]
c.execute("SELECT COUNT(*) FROM funds")
kap_total = c.fetchone()[0]
c.execute("SELECT COUNT(*) FROM funds WHERE tefas_code IS NOT NULL")
mapped = c.fetchone()[0]
conn.close()

print(f"\n{'='*50}")
print(f"✅ Done!")
print(f"  Tefas funds:      {total}")
print(f"  KAP funds:        {kap_total}")
print(f"  KAP→Tefas mapped: {mapped}")
print(f"{'='*50}")
