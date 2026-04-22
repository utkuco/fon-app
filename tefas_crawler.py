#!/usr/bin/env python3
"""
Tefas Crawler — Daily fund data from fundturkey.com.tr
Usage: python3 tefas_crawler.py [date]
       python3 tefas_crawler.py 2026-04-16   # specific date
       python3 tefas_crawler.py yesterday    # previous business day
       python3 tefas_crawler.py              # today
"""
import sys
import ssl
import time
import sqlite3
import json
from datetime import date, datetime, timedelta
from pathlib import Path

import requests
import pandas as pd
from requests.adapters import HTTPAdapter
from urllib3.poolmanager import PoolManager

# === CONFIG ===
DB_PATH = Path(__file__).parent / "db" / "fonapp.db"
KIND = "YAT"  # YAT=Securities, EMK=Pension, BYF=ETF
# ==============

# SSL workaround for legacy servers
class CustomHttpAdapter(HTTPAdapter):
    def __init__(self, ssl_context=None, **kwargs):
        self.ssl_context = ssl_context
        super().__init__(**kwargs)
    def init_poolmanager(self, connections, maxsize, block=False):
        self.poolmanager = PoolManager(
            num_pools=connections, maxsize=maxsize, block=block,
            ssl_context=self.ssl_context)

def get_session():
    ctx = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)
    ctx.options |= 0x4  # OP_LEGACY_SERVER_CONNECT
    session = requests.session()
    session.mount("https://", CustomHttpAdapter(ctx))
    return session

def parse_date_str(d):
    if d == "yesterday":
        yesterday = date.today() - timedelta(days=1)
        return yesterday.strftime("%Y-%m-%d")
    try:
        parsed = datetime.strptime(d, "%Y-%m-%d")
        return parsed.strftime("%Y-%m-%d")
    except ValueError:
        raise ValueError(f"Invalid date: {d}. Use YYYY-MM-DD or 'yesterday'")

def format_date_for_api(d):
    """YYYY-MM-DD → DD.MM.YYYY"""
    parsed = datetime.strptime(d, "%Y-%m-%d")
    return parsed.strftime("%d.%m.%Y")

def get_fund_id(conn, code):
    """Get fund id by code, return None if not found."""
    c = conn.cursor()
    c.execute("SELECT id FROM funds WHERE code = ?", (code,))
    r = c.fetchone()
    return r[0] if r else None

def upsert_fund_from_tefas(conn, row):
    """Update funds table with Tefas data for a single fund."""
    c = conn.cursor()
    c.execute("""
        UPDATE funds SET
            price = ?,
            price_date = ?,
            market_cap = ?,
            number_of_shares = ?,
            number_of_investors = ?,
            tefas_title = ?
        WHERE code = ?
    """, (
        row.get("price"),
        row.get("date"),
        row.get("market_cap"),
        row.get("number_of_shares"),
        row.get("number_of_investors"),
        row.get("title"),
        row.get("code"),
    ))
    return c.rowcount > 0

def insert_price_history(conn, fund_id, row):
    c = conn.cursor()
    c.execute("""
        INSERT OR REPLACE INTO price_history
        (fund_id, date, price, daily_change, market_cap, number_of_shares, number_of_investors)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        fund_id,
        row.get("date"),
        row.get("price"),
        row.get("daily_change", 0),
        row.get("market_cap"),
        row.get("number_of_shares"),
        row.get("number_of_investors"),
    ))

def insert_portfolio_breakdown(conn, fund_id, row):
    c = conn.cursor()
    c.execute("""
        INSERT OR REPLACE INTO portfolio_breakdown
        (fund_id, date, stock, government_bond, private_sector_bond, eurobond, gold,
         repo, reverse_repo, treasury_bill, bank_bills, commercial_paper, term_deposit,
         etf, derivatives, foreign_equity, foreign_bond, precious_metals, participation_account,
         government_lease_certificates, private_sector_lease_certificates,
         asset_backed_securities, tmm, fund_participation_certificate, foreign_securities, other)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        fund_id,
        row.get("date"),
        row.get("stock"),
        row.get("government_bond"),
        row.get("private_sector_bond"),
        row.get("eurobond"),
        row.get("gold"),
        row.get("repo"),
        row.get("reverse_repo"),
        row.get("treasury_bill"),
        row.get("bank_bills"),
        row.get("commercial_paper"),
        row.get("term_deposit"),
        row.get("exchange_traded_fund"),  # ETF
        row.get("derivatives"),
        row.get("foreign_equity"),
        row.get("foreign_debt_instruments"),  # foreign bond
        row.get("precious_metals"),
        row.get("participation_account"),
        row.get("government_lease_certificates"),
        row.get("private_sector_lease_certificates"),
        row.get("asset_backed_securities"),
        row.get("tmm"),
        row.get("fund_participation_certificate"),
        row.get("foreign_securities"),
        row.get("other"),
    ))

def calculate_daily_change(df, code):
    """Calculate daily % change for a fund."""
    # Group by code and get previous day's price
    df_sorted = df.sort_values("date")
    prices = df_sorted[df_sorted["code"] == code].set_index("date")["price"]
    if len(prices) >= 2:
        today_price = prices.iloc[-1]
        yesterday_price = prices.iloc[-2]
        if yesterday_price and yesterday_price > 0:
            return (today_price - yesterday_price) / yesterday_price * 100
    return 0

def crawl_date(session, target_date, kind=KIND, max_retries=3):
    """Fetch all funds for a specific date from Tefas API."""
    formatted = format_date_for_api(target_date)

    headers = {
        "Connection": "keep-alive",
        "X-Requested-With": "XMLHttpRequest",
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "Origin": "https://fundturkey.com.tr",
        "Referer": "https://fundturkey.com.tr/TarihselVeriler.aspx",
    }

    # Fetch info + breakdown in parallel-ish (sequential, same date)
    results = []

    # First get info
    info_payload = {
        "fontip": kind,
        "bastarih": formatted,
        "bittarih": formatted,
        "fonkod": "",
    }

    for attempt in range(max_retries):
        try:
            # Get session cookie first
            _ = session.get("https://fundturkey.com.tr", timeout=10)
            cookies = session.cookies.get_dict()

            r_info = session.post(
                "https://fundturkey.com.tr/api/DB/BindHistoryInfo",
                data=info_payload,
                headers=headers,
                cookies=cookies,
                timeout=30,
            )
            info_data = r_info.json().get("data", [])

            # Convert timestamps to date strings
            for row in info_data:
                if "TARIH" in row and isinstance(row["TARIH"], (int, float)):
                    seconds = int(row["TARIH"]) / 1000
                    row["date"] = datetime.fromtimestamp(seconds).strftime("%Y-%m-%d")
                row["price"] = row.get("FIYAT")
                row["market_cap"] = row.get("PORTFOYBUYUKLUK")
                row["number_of_shares"] = row.get("TEDPAYSAYISI")
                row["number_of_investors"] = row.get("KISISAYISI")
                row["title"] = row.get("FONUNVAN")

            results = info_data
            break
        except Exception as e:
            print(f"  ⚠️  Attempt {attempt+1} failed: {e}")
            if attempt < max_retries - 1:
                time.sleep(5 * (attempt + 1))
            else:
                raise

    # Get breakdown
    breakdown_payload = {
        "fontip": kind,
        "bastarih": formatted,
        "bittarih": formatted,
        "fonkod": "",
    }

    try:
        r_break = session.post(
            "https://fundturkey.com.tr/api/DB/BindHistoryAllocation",
            data=breakdown_payload,
            headers=headers,
            cookies=cookies,
            timeout=30,
        )
        breakdown_data = r_break.json().get("data", [])
        breakdown_by_code = {
            row.get("FONKODU"): row for row in breakdown_data
        }
    except Exception as e:
        print(f"  ⚠️  Breakdown fetch failed: {e}")
        breakdown_by_code = {}

    # Merge info + breakdown
    enriched = []
    for row in results:
        code = row.get("FONKODU")
        breakdown = breakdown_by_code.get(code, {})
        merged = {**row, **breakdown}
        enriched.append(merged)

    return enriched

def main():
    # Determine target date
    if len(sys.argv) > 1:
        target_date = parse_date_str(sys.argv[1])
    else:
        target_date = date.today().strftime("%Y-%m-%d")

    print(f"{'='*60}")
    print(f"Tefas Crawler — {target_date} ({KIND})")
    print(f"{'='*60}\n")

    session = get_session()

    # Check existing funds in DB
    conn = sqlite3.connect(str(DB_PATH))
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM funds")
    total_funds = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM price_history WHERE date = ?", (target_date,))
    already_done = c.fetchone()[0]
    conn.close()

    print(f"DB has {total_funds} funds")
    print(f"Already have price data for {target_date}: {already_done}")

    if already_done > 0:
        print(f"\n⚠️  Data for {target_date} already exists. Re-fetching anyway...")

    print(f"\n📡 Fetching from Tefas API...")

    try:
        funds_data = crawl_date(session, target_date, KIND)
    except Exception as e:
        print(f"❌ Failed to fetch data: {e}")
        return

    print(f"✅ Received {len(funds_data)} funds from API")

    # Calculate daily change using price history
    if len(funds_data) > 0:
        conn = sqlite3.connect(str(DB_PATH))
        yesterday = (datetime.strptime(target_date, "%Y-%m-%d") - timedelta(days=1)).strftime("%Y-%m-%d")

        for row in funds_data:
            code = row.get("code")
            if not code:
                continue
            fund_id = get_fund_id(conn, code)
            if not fund_id:
                continue

            # Get yesterday's price for daily change
            c = conn.cursor()
            c.execute("SELECT price FROM price_history WHERE fund_id = ? AND date = ?", (fund_id, yesterday))
            prev_row = c.fetchone()
            prev_price = prev_row[0] if prev_row else None

            if prev_price and prev_price > 0 and row.get("price"):
                row["daily_change"] = (row["price"] - prev_price) / prev_price * 100
            else:
                row["daily_change"] = 0

        conn.close()

    # Store in DB
    conn = sqlite3.connect(str(DB_PATH))
    stats = {"updated": 0, "inserted": 0, "breakdown": 0, "skipped": 0}

    for row in funds_data:
        code = row.get("code")
        if not code:
            stats["skipped"] += 1
            continue

        fund_id = get_fund_id(conn, code)
        if not fund_id:
            stats["skipped"] += 1
            continue

        # Update funds table (latest price data)
        updated = upsert_fund_from_tefas(conn, row)
        if updated:
            stats["updated"] += 1
        else:
            stats["inserted"] += 1

        # Insert price history
        insert_price_history(conn, fund_id, row)

        # Insert portfolio breakdown
        if any(row.get(k) for k in ["stock", "government_bond", "eurobond", "gold", "repo"]):
            insert_portfolio_breakdown(conn, fund_id, row)
            stats["breakdown"] += 1

        # Rate limit protection
        time.sleep(0.01)

    conn.commit()
    conn.close()

    print(f"\n{'='*60}")
    print(f"Done! {target_date}")
    print(f"  Funds updated:    {stats['updated']}")
    print(f"  Funds skipped:   {stats['skipped']}")
    print(f"  Price history:  {stats['updated'] + stats['inserted']}")
    print(f"  Breakdown:       {stats['breakdown']}")
    print(f"{'='*60}")

if __name__ == "__main__":
    main()
