#!/usr/bin/env python3
"""
Fetch management fees and valour data from TEFAS (tefas.gov.tr).
Uses two sources:
  1. API:  /api/DB/BindComparisonManagementFees  → yönetim ücreti, gider kesintisi
  2. HTML: /FonAnaliz.aspx?FonKod={CODE}        → alış/satış valörü

Usage: python3 fetch_fund_fees.py
       python3 fetch_fund_fees.py --codes BS1 AAK PTP   # specific funds
"""
import sys
import time
import json
import sqlite3
import requests
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from bs4 import BeautifulSoup
from typing import Optional

DB_PATH = Path(__file__).parent / "db" / "fonapp.db"
TEFAS_BASE = "https://www.tefas.gov.tr"

# ── helpers ────────────────────────────────────────────────────────────────────

def get_session() -> requests.Session:
    s = requests.Session()
    s.headers.update({
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "tr-TR,tr;q=0.9",
        "Referer": TEFAS_BASE + "/",
    })
    return s


def parse_turkish_number(val: Optional[str]) -> Optional[float]:
    """Parse '2,9' → 2.9, '1.234,56' → 1234.56"""
    if val is None or str(val).strip() in ("", "-", "N/A"):
        return None
    s = str(val).strip().replace("%", "").replace(" ", "")
    if "," in s and "." in s:
        s = s.replace(".", "").replace(",", ".")
    elif "," in s:
        s = s.replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


# ── API: yönetim ücreti + gider kesintisi ────────────────────────────────────

def fetch_management_fees_api(session: requests.Session) -> dict:
    """
    Fetch management fees and max total expense ratio for ALL funds.
    Returns dict: {FONKODU: {"management_fee": float, "max_total_expense_ratio": float}}
    """
    url = f"{TEFAS_BASE}/api/DB/BindComparisonManagementFees"
    headers = {
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "Origin": TEFAS_BASE,
        "Referer": TEFAS_BASE + "/",
    }

    result = {}

    for fontip in ["YAT", "EMK", "BYF"]:
        payload = {"islemdurum": "1", "fontip": fontip}
        try:
            resp = session.post(url, data=payload, headers=headers, timeout=30)
            items = resp.json().get("data", [])
            for item in items:
                code = item.get("FONKODU")
                if not code:
                    continue
                # FONICTUZUKYU1G = yönetim ücreti yıllık %
                # FONTOPGIDERKESORAN = azami toplam gider kesintisi oranı
                mgmt_fee = parse_turkish_number(item.get("FONICTUZUKYU1G"))
                expense_ratio = parse_turkish_number(item.get("FONTOPGIDERKESORAN"))
                if code not in result:
                    result[code] = {}
                if mgmt_fee is not None:
                    result[code]["management_fee"] = mgmt_fee
                if expense_ratio is not None:
                    result[code]["max_total_expense_ratio"] = expense_ratio
            print(f"  API {fontip}: {len(items)} funds")
        except Exception as e:
            print(f"  ⚠️  API {fontip} failed: {e}")

    return result


# ── HTML: valör ──────────────────────────────────────────────────────────────

def fetch_valour(session: requests.Session, code: str) -> dict:
    """Fetch buy/sell valour from FonAnaliz.aspx page."""
    try:
        resp = session.get(
            f"{TEFAS_BASE}/FonAnaliz.aspx?FonKod={code}",
            timeout=15,
        )
        if resp.status_code != 200:
            return {}
        soup = BeautifulSoup(resp.text, "html.parser")
        table = soup.find("table", id="MainContent_DetailsViewFund")
        if not table:
            return {}
        data = {}
        for row in table.find_all("tr"):
            cells = row.find_all("td")
            if len(cells) != 2:
                continue
            key = cells[0].get_text(strip=True)
            value = cells[1].get_text(strip=True)
            if "Fon Alış Valörü" in key:
                data["buy_valor"] = parse_turkish_number(value)
            elif "Fon Satış Valörü" in key:
                data["sell_valor"] = parse_turkish_number(value)
        return data
    except Exception:
        return {}


def fetch_valour_batch(session: requests.Session, codes: list, max_workers: int = 8) -> dict:
    """Fetch valour for multiple funds in parallel."""
    result = {}

    def _fetch_one(code: str) -> tuple:
        data = fetch_valour(session, code)
        return code, data

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(_fetch_one, code): code for code in codes}
        done = 0
        for future in as_completed(futures):
            code, data = future.result()
            result[code] = data
            done += 1
            if done % 100 == 0:
                print(f"  Valour progress: {done}/{len(codes)}")
            time.sleep(0.1)  # polite delay

    return result


# ── DB update ─────────────────────────────────────────────────────────────────

def get_all_fund_codes(conn: sqlite3.Connection) -> list:
    """Return list of (code, tefas_code) tuples for all funds."""
    rows = conn.execute(
        "SELECT code, tefas_code FROM funds WHERE code IS NOT NULL"
    ).fetchall()
    return [(r[0], r[1]) for r in rows]


def update_funds_in_db(conn: sqlite3.Connection, api_data: dict, valour_data: dict) -> dict:
    """
    Update funds in DB. API code (FONKODU) can match either the 'code' column
    or the 'tefas_code' column in SQLite.
    """
    stats = {"updated": 0, "skipped": 0}

    for code in api_data.keys():
        api_row = api_data.get(code, {})
        val_row = valour_data.get(code, {})

        mgmt = api_row.get("management_fee")
        expense = api_row.get("max_total_expense_ratio")
        buy_v = val_row.get("buy_valor")
        sell_v = val_row.get("sell_valor")

        has_api = mgmt is not None or expense is not None
        has_val = buy_v is not None or sell_v is not None

        if not has_api and not has_val:
            stats["skipped"] += 1
            continue

        # Match by code OR by tefas_code
        rows_affected = conn.execute("""
            UPDATE funds SET
                management_fee = COALESCE(?, management_fee),
                max_total_expense_ratio = COALESCE(?, max_total_expense_ratio),
                buy_valor = COALESCE(?, buy_valor),
                sell_valor = COALESCE(?, sell_valor)
            WHERE code = ?
               OR (tefas_code = ? AND tefas_code IS NOT NULL AND tefas_code != '')
        """, (mgmt, expense, buy_v, sell_v, code, code)).rowcount

        if rows_affected > 0:
            stats["updated"] += 1
        else:
            stats["skipped"] += 1

    conn.commit()
    return stats


# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("TEFAS Fund Fees & Valour Fetcher")
    print("=" * 60)

    # Optional: specific codes passed as args
    specific_codes = None
    if len(sys.argv) > 1 and sys.argv[1] != "--codes":
        specific_codes = sys.argv[1:]
    elif "--codes" in sys.argv:
        idx = sys.argv.index("--codes")
        specific_codes = sys.argv[idx + 1:]

    session = get_session()
    # Warm up session with base request
    session.get(TEFAS_BASE + "/", timeout=10)

    # ── Step 1: Fetch management fees from API ────────────────────────────────
    print("\n📡 Step 1: Fetching management fees from TEFAS API...")
    api_data = fetch_management_fees_api(session)
    print(f"   ✅ Got fee data for {len(api_data)} funds")

    # ── Step 2: Fetch valör from HTML pages ───────────────────────────────────
    print("\n📡 Step 2: Fetching valör from TEFAS FonAnaliz pages...")

    # Get fund codes to scrape — use API FONKODU as the canonical code
    if specific_codes:
        codes_to_scrape = specific_codes
    else:
        # For valour, we need to scrape pages — use a sample of API codes
        # (TEFAS page scraping is slow, so limit to 500)
        codes_to_scrape = list(api_data.keys())[:500]


    print(f"   Scraping valör for {len(codes_to_scrape)} funds...")
    valour_data = fetch_valour_batch(session, codes_to_scrape)
    valour_count = sum(1 for v in valour_data.values() if v)
    print(f"   ✅ Got valör data for {valour_count} funds")

    # ── Step 3: Write to SQLite ───────────────────────────────────────────────
    print("\n💾 Step 3: Writing to SQLite...")
    conn = sqlite3.connect(str(DB_PATH))
    stats = update_funds_in_db(conn, api_data, valour_data)
    conn.close()
    print(f"   ✅ Updated: {stats['updated']}, Skipped: {stats['skipped']}")

    # ── Summary ───────────────────────────────────────────────────────────────
    mgmt_count = sum(1 for v in api_data.values() if v.get("management_fee") is not None)
    expense_count = sum(1 for v in api_data.values() if v.get("max_total_expense_ratio") is not None)
    print(f"\n📊 Summary:")
    print(f"   Management fee data: {mgmt_count}")
    print(f"   Max expense ratio data: {expense_count}")
    print(f"   Valör data: {valour_count}")
    print("=" * 60)


if __name__ == "__main__":
    main()
