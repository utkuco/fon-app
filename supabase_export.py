#!/usr/bin/env python3
"""
Export SQLite data to Supabase (replaces export_json.py).
Reads from local SQLite, computes returns/breakdowns, upserts to Supabase.

Usage: python3 supabase_export.py
"""
import json, re, os, time, sqlite3
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

DB = Path(__file__).parent / "db" / "fonapp.db"
SUPABASE_URL = "https://oqkobptbvcazifpvjwfz.supabase.co"
ENV_FILE = Path(__file__).parent / "web" / ".env.local"
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY") or "sb_secret_PkAEAOU2YO4YS-ELYpwS5w_SsVg2kqi"

conn = sqlite3.connect(str(DB))
conn.row_factory = sqlite3.Row
cur = conn.cursor()
_lock = threading.Lock()
_counts = {"upserted": 0, "skipped": 0, "errors": 0}

def sb_request(method, path, json_data=None, params=None):
    import urllib.request
    url = f"{SUPABASE_URL}/rest/v1/{path}"
    data = json.dumps(json_data).encode("utf-8") if json_data else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Content-Type", "application/json; charset=utf-8")
    req.add_header("apikey", SUPABASE_KEY)
    req.add_header("Authorization", f"Bearer {SUPABASE_KEY}")
    req.add_header("Prefer", "return=representation")
    if params:
        url_params = "&".join(f"{k}={v}" for k, v in params.items())
        req.full_url = f"{url}?{url_params}"
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = resp.read()
            return json.loads(result) if result else None
    except urllib.request.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        return {"error": f"HTTP {e.code}: {body[:200]}"}
    except Exception as e:
        return {"error": str(e)}

def upsert_fund(fund_data):
    code = fund_data["code"]
    try:
        result = sb_request("PATCH", f"funds?code=eq.{code}", json_data=fund_data)
        if result is None:
            result = sb_request("POST", "funds", json_data=fund_data)
        with _lock:
            if result and "error" not in str(result):
                _counts["upserted"] += 1
            else:
                _counts["errors"] += 1
                if _counts["errors"] <= 5:
                    print(f"  ✗ {code}: {str(result)[:100]}")
    except Exception as e:
        with _lock:
            _counts["errors"] += 1
        if _counts["errors"] <= 5:
            print(f"  ✗ {code}: {e}")

def get_company_map():
    result = sb_request("GET", "companies", params={"select": "id,name"})
    if isinstance(result, list):
        return {c["name"].lower(): c["id"] for c in result if c.get("name")}
    return {}

def translate_title(title: str) -> str:
    if not title: return title
    t = title
    replacements = [
        (r'\bMONEY MARKET\b', 'PARA PİYASASI'), (r'\bGOLD\b', 'ALTIN'),
        (r'\bPARTICIPATION\b', 'KATILIM'), (r'\bPENSION\b', 'EMEKLİLİK'),
        (r'\bMUTUAL FUND\b', 'YATIRIM FONU'), (r'\bPARTICIPATION\b', 'KATILIM'),
        (r'\bSTOCK\b', 'HİSSE'), (r'\bEQUITY\b', 'HİSSE'),
        (r'\bFIXED INCOME\b', 'BORÇLANMA'), (r'\bFOREIGN\b', 'YABANCI'),
        (r'\bETF\b', 'BYF'), (r'\bDEĞİŞKEN', 'DEĞİŞKEN'), (r'\bSERBEST', 'SERBEST'),
        (r'\bÖZEL SEKTÖR', 'ÖZEL SEKTÖR'), (r'\bDÖVİZ', 'DÖVİZ'),
    ]
    for pattern, replacement in replacements:
        t = re.sub(pattern, replacement, t, flags=re.IGNORECASE)
    return re.sub(r'\s+', ' ', t).strip()

def guess_type(title: str) -> str:
    if not title: return "VFF"
    t = str(title).upper()
    if any(x in t for x in ["DEĞİŞKEN", "VARYANT", "VARİABLE"]): return "VFF"
    if any(x in t for x in ["SERBEST", "FREE"]): return "SRF"
    if any(x in t for x in ["ÖZEL SEKTÖR", "FON SEPETİ", "PORTFÖY SEPETİ"]): return "OKS"
    if any(x in t for x in ["DÖVİZ", "USD", "EUR/", "EURO"]): return "DÖVİZ"
    if any(x in t for x in ["ALTIN", "GOLD", "GRAM"]): return "ALTIN"
    if any(x in t for x in ["BORÇLANMA", "TAHVİL", "BONO"]): return "KFF"
    if any(x in t for x in ["BYF", "ETF", "BORSADA İŞLEM"]): return "BYF"
    if any(x in t for x in ["HİSSE", "HİSSE-İNTENSİVE"]): return "HİSSE"
    return "VFF"

# Breakdown field mapping: tefas_funds column → standard key
BREAKDOWN_FIELDS = [
    "stock", "government_bond", "private_sector_bond", "eurobond",
    "gold", "repo", "reverse_repo", "treasury_bill", "bank_bills",
    "commercial_paper", "term_deposit", "etf", "derivatives",
    "foreign_equity", "foreign_bond", "precious_metals", "participation_account", "other"
]

def build_breakdown_from_row(row):
    """Build breakdown dict from tefas_funds row (which has breakdown as columns)."""
    breakdown = {}
    for f in BREAKDOWN_FIELDS:
        v = row[f] if f in row.keys() else None
        if v and float(v) > 0:
            breakdown[f] = round(float(v), 2)
    return breakdown if breakdown else None

def load_price_history(fund_id, limit_days=252):
    cur.execute("""
        SELECT date, price, daily_change, market_cap, number_of_investors, number_of_shares
        FROM price_history WHERE fund_id = ? ORDER BY date DESC LIMIT ?
    """, (fund_id, limit_days))
    rows = cur.fetchall()
    return [dict(r) for r in reversed(rows)]

def compute_returns(price_hist):
    if not price_hist or len(price_hist) < 2: return {}
    prices = [(h["date"], h["price"]) for h in price_hist if h["price"]]
    if len(prices) < 2: return {}
    last_price = prices[-1][1]
    returns = {}
    if prices[0][1] and prices[0][1] > 0:
        returns["1D"] = round((last_price / prices[0][1] - 1) * 100, 2)
    if len(prices) >= 6 and prices[-6][1]:
        returns["1W"] = round((prices[-1][1] / prices[-6][1] - 1) * 100, 2)
    if len(prices) >= 22 and prices[-22][1]:
        returns["1M"] = round((prices[-1][1] / prices[-22][1] - 1) * 100, 2)
    if len(prices) >= 64 and prices[-64][1]:
        returns["3M"] = round((prices[-1][1] / prices[-64][1] - 1) * 100, 2)
    return returns

def load_tefas_funds():
    # Join tefas_funds with its latest price_history row to get daily_change
    cur.execute("""
        SELECT t.*,
               p.price as latest_price, p.date as latest_date,
               p.daily_change as price_daily_change,
               p.market_cap as latest_market_cap,
               f.management_fee,
               f.max_total_expense_ratio,
               f.buy_valor,
               f.sell_valor
        FROM tefas_funds t
        LEFT JOIN price_history p ON p.fund_id = t.id
            AND p.date = (SELECT MAX(p2.date) FROM price_history p2 WHERE p2.fund_id = t.id)
        LEFT JOIN funds f ON f.code = t.tefas_code OR f.tefas_code = t.tefas_code
        ORDER BY t.tefas_code
    """)
    return cur.fetchall()

def main():
    print("=" * 60)
    print("Supabase Export — SQLite → Supabase (with breakdown)")
    print("=" * 60)

    print("\n📡 Fetching company map from Supabase...")
    company_map = get_company_map()
    print(f"   Found {len(company_map)} companies")

    print("\n📂 Loading tefas_funds from SQLite...")
    tefas_rows = load_tefas_funds()
    print(f"   {len(tefas_rows)} funds")

    funds_data = []
    for i, row in enumerate(tefas_rows):
        code = row["tefas_code"]
        if not code: continue

        price_hist = load_price_history(row["id"], 252)
        price_history_simple = [{
            "date": h["date"],
            "price": h["price"],
            "change": h["daily_change"],
            "market_cap": h["market_cap"],
            "investors": h["number_of_investors"],
            "shares": h["number_of_shares"],
        } for h in price_hist]
        returns = compute_returns(price_hist)

        # Build breakdown from tefas_funds row columns (NOT portfolio_breakdown table)
        breakdown = build_breakdown_from_row(row)

        # Company matching
        slug = code[:3].lower()
        company_id = company_map.get(slug)

        turkish_name = translate_title(row["title"]) if row["title"] else code

        fund_dict = {
            "code": code,
            "name": turkish_name,
            "fund_type": row["fund_type"] or guess_type(turkish_name),
            "company_id": company_id,
            "daily_change": row["price_daily_change"],
            "market_cap": row["latest_market_cap"] or row["market_cap"],
            "price": row["latest_price"] or row["price"],
            # number_of_investors and number_of_shares stored in price_history, not as fund columns
            "weekly": returns.get("1W"),
            "monthly": returns.get("1M"),
            "quarterly": returns.get("3M"),
            "returns": returns if returns else None,
            "breakdown": breakdown,
            "price_history": price_history_simple if price_history_simple else None,
            # Fund fees & valour
            "management_fee": row["management_fee"] if "management_fee" in row.keys() else None,
            "max_total_expense_ratio": row["max_total_expense_ratio"] if "max_total_expense_ratio" in row.keys() else None,
            "purchase_valor": row["buy_valor"] if "buy_valor" in row.keys() else None,
            "sale_valor": row["sell_valor"] if "sell_valor" in row.keys() else None,
        }
        funds_data.append(fund_dict)
        if (i + 1) % 200 == 0:
            print(f"   Processed {i+1}/{len(tefas_rows)}...")

    print(f"\n✅ Processed {len(funds_data)} funds")
    print(f"   Breakdown populated: {sum(1 for f in funds_data if f['breakdown'])}")

    print("\n🚀 Upserting to Supabase (parallel)...")
    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = [executor.submit(upsert_fund, f) for f in funds_data]
        done = 0
        for f in as_completed(futures):
            done += 1
            if done % 200 == 0:
                print(f"   {done}/{len(funds_data)} — upserted: {_counts['upserted']}, errors: {_counts['errors']}")

    print("\n" + "=" * 60)
    print(f"✅ Done! Upserted: {_counts['upserted']}, Errors: {_counts['errors']}")
    print("=" * 60)
    conn.close()

if __name__ == "__main__":
    main()
