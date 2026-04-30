#!/usr/bin/env python3
"""
DB Migration: Add Tefas fields and tables.
Run once: python3 migrate_tefas.py
"""
import sqlite3
from pathlib import Path

DB = Path(__file__).parent / "db" / "fonapp.db"

conn = sqlite3.connect(str(DB))
c = conn.cursor()

print("=== DB Migration: Adding Tefas fields ===\n")

# 1. Add new columns to funds table
new_cols = [
    ("price", "REAL"),
    ("price_date", "TEXT"),
    ("market_cap", "REAL"),
    ("number_of_shares", "REAL"),
    ("number_of_investors", "REAL"),
    ("daily_change", "REAL"),
    ("tefas_title", "TEXT"),
]

for col_name, col_type in new_cols:
    try:
        c.execute(f"ALTER TABLE funds ADD COLUMN {col_name} {col_type}")
        print(f"  ✅ Added: funds.{col_name}")
    except sqlite3.OperationalError as e:
        if "duplicate column" in str(e).lower():
            print(f"  ⏭️  Already exists: funds.{col_name}")
        else:
            print(f"  ❌ Error: {e}")

# 2. Create price_history table
c.execute("""CREATE TABLE IF NOT EXISTS price_history (
    id INTEGER PRIMARY KEY,
    fund_id INTEGER REFERENCES funds(id),
    date TEXT,
    price REAL,
    daily_change REAL,
    market_cap REAL,
    number_of_shares REAL,
    number_of_investors REAL,
    UNIQUE(fund_id, date)
)""")
print("  ✅ Created: price_history table")

# 3. Create portfolio_breakdown table (Tefas asset allocation %)
c.execute("""CREATE TABLE IF NOT EXISTS portfolio_breakdown (
    id INTEGER PRIMARY KEY,
    fund_id INTEGER REFERENCES funds(id),
    date TEXT,
    -- Core asset types
    stock REAL,           -- HS: Hisse Senedi
    government_bond REAL, -- DT: Devlet Tahvili
    private_sector_bond REAL, -- OST: Özel Sektör Tahvili
    eurobond REAL,        -- EUT: Eurobond
    gold REAL,            -- KM: Kıymetli Madenler
    repo REAL,            -- R: Repo
    reverse_repo REAL,    -- TR: Ters Repo
    treasury_bill REAL,   -- HB: Hazine Bonosu
    bank_bills REAL,      -- BB: Banka Bonosu
    commercial_paper REAL, -- FB: Finansman Bonosu
    term_deposit REAL,    -- VM: Vadeli Mevduat
    etf REAL,             -- BYF: Borsa Yönetilen Fon
    derivatives REAL,     -- T: Türev Araçları
    foreign_equity REAL,  -- YHS: Yabancı Hisse
    foreign_bond REAL,    -- YBA: Yabancı Borçlanma
    precious_metals REAL, -- KM: Kıymetli Madenler
    participation_account REAL, -- KH: Katılma Hesabı
    other REAL,           -- D: Diğer
    -- Additional
    government_lease_certificates REAL, -- KKS
    private_sector_lease_certificates REAL, -- OSKS
    asset_backed_securities REAL, -- VDM
    tmm REAL,             -- TPP: Takasbank Para Piyasası
    fund_participation_certificate REAL, -- FKB
    foreign_securities REAL, -- YMK
    UNIQUE(fund_id, date)
)""")
print("  ✅ Created: portfolio_breakdown table")

# 4. Create index for faster lookups
c.execute("CREATE INDEX IF NOT EXISTS idx_price_history_fund_date ON price_history(fund_id, date)")
c.execute("CREATE INDEX IF NOT EXISTS idx_portfolio_breakdown_fund_date ON portfolio_breakdown(fund_id, date)")
print("  ✅ Created indexes")

conn.commit()
conn.close()

print("\n✅ Migration complete!")
