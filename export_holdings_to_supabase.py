#!/usr/bin/env python3
"""
Export holdings data from SQLite to Supabase fund_holdings.
Uses Supabase REST API (PostgREST) - POST array of objects works.
"""
import json, sqlite3
from pathlib import Path
import urllib.request

DB = Path(__file__).parent / "db" / "fonapp.db"
SUPABASE_URL = "https://oqkobptbvcazifpvjwfz.supabase.co"
SUPABASE_KEY = "sb_publishable__GPrsdfKRZCMZE8to916iQ_Izv9naG-"

def post_to_supabase(records):
    """POST an array of records to Supabase fund_holdings."""
    url = f"{SUPABASE_URL}/rest/v1/fund_holdings"
    data = json.dumps(records).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("Content-Type", "application/json; charset=utf-8")
    req.add_header("apikey", SUPABASE_KEY)
    req.add_header("Authorization", f"Bearer {SUPABASE_KEY}")
    req.add_header("Prefer", "return=representation")
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            return len(result) if isinstance(result, list) else 0
    except urllib.request.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        return {"error": f"HTTP {e.code}: {body[:200]}"}
    except Exception as e:
        return {"error": str(e)}

def main():
    print("=" * 60)
    print("Holdings Export — SQLite → Supabase fund_holdings")
    print("=" * 60)

    # Load from SQLite
    conn = sqlite3.connect(str(DB))
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    print("\n📂 Loading holdings from SQLite...")
    cur.execute("""
        SELECT
            f.code as fund_code,
            h.ticker,
            h.isin,
            h.total_value
        FROM holdings h
        JOIN reports r ON r.id = h.report_id
        JOIN funds f ON f.id = r.fund_id
        WHERE f.code IS NOT NULL
        ORDER BY f.code, h.weight_pct DESC
    """)
    rows = cur.fetchall()

    # Dedupe: keep latest per fund+ticker+isin
    seen = {}
    for h in rows:
        key = (h["fund_code"], h["ticker"] or "", h["isin"] or "")
        if key not in seen:
            seen[key] = h

    records = [
        {
            "fund_code": str(h["fund_code"]),
            "ticker": str(h["ticker"] or ""),
            "isin": str(h["isin"] or ""),
            "total_value": float(h["total_value"]) if h["total_value"] is not None else 0.0,
        }
        for h in seen.values()
    ]
    conn.close()

    print(f"   Total rows: {len(rows)}")
    print(f"   Unique records: {len(records)}")
    print(f"   Sample: {records[0]}")

    # Insert in batches
    batch_size = 100
    total_inserted = 0
    total_errors = 0

    print(f"\n🚀 Inserting to Supabase (batches of {batch_size})...")
    for i in range(0, len(records), batch_size):
        batch = records[i : i + batch_size]
        result = post_to_supabase(batch)
        batch_num = i // batch_size + 1
        total_batches = (len(records) + batch_size - 1) // batch_size

        if isinstance(result, dict) and "error" in result:
            total_errors += len(batch)
            print(f"   Batch {batch_num}/{total_batches}: ERROR — {result['error']}")
        else:
            total_inserted += result
            if batch_num % 10 == 0 or batch_num == total_batches:
                print(f"   Batch {batch_num}/{total_batches}: OK ({result} inserted)")

    print("\n" + "=" * 60)
    print(f"✅ Done! Inserted: {total_inserted}, Errors: {total_errors}")
    print("=" * 60)

if __name__ == "__main__":
    main()
