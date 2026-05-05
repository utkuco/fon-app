#!/usr/bin/env python3
"""Fix broken returns JSONB field where 3M/6M values are extreme outliers (>100%)."""

import psycopg2
import json

DB_URL = "postgresql://postgres:rzvfO6ub5F1W6hpR@db.oqkobptbvcazifpvjwfz.supabase.co:5432/postgres"

def fix_broken_returns():
    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()
    
    # Find funds with broken returns
    cur.execute("""
        SELECT code, returns
        FROM funds
        WHERE returns IS NOT NULL
        LIMIT 20
    """)
    
    broken = []
    for row in cur.fetchall():
        code, ret = row
        if not isinstance(ret, dict):
            try:
                ret = json.loads(ret) if isinstance(ret, str) else {}
            except:
                ret = {}
        
        # Check for extreme values (> 100% or < -50%)
        needs_fix = False
        fixed = dict(ret)
        for period in ['1D', '1W', '1M', '3M', '6M', '1Y']:
            if period in fixed:
                v = fixed[period]
                if v is not None and (v > 100 or v < -50):
                    print(f"  {code}: {period} = {v} (EXTREME)")
                    fixed[period] = None  # null out extreme values
                    needs_fix = True
        
        if needs_fix:
            broken.append((code, json.dumps(fixed)))
    
    print(f"\nFound {len(broken)} funds with broken returns")
    
    for code, new_returns in broken:
        cur.execute(
            "UPDATE funds SET returns = %s WHERE code = %s",
            (new_returns, code)
        )
        print(f"  Fixed: {code}")
    
    conn.commit()
    print(f"\nDone. {len(broken)} records updated.")
    cur.close()
    conn.close()

if __name__ == "__main__":
    fix_broken_returns()
