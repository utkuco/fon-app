#!/usr/bin/env python3
"""
Backfill foreign_etfs return fields from foreign_etf_prices table.
Uses direct psycopg2 — no HTTP overhead.
"""
import psycopg2
from datetime import date, timedelta

DB_URL = "postgresql://postgres:rzvfO6ub5F1W6hpR@db.oqkobptbvcazifpvjwfz.supabase.co:5432/postgres"

def calc_return_from_rows(rows, days):
    if not rows:
        return None
    end_date = rows[-1][0]
    start_cutoff = end_date - timedelta(days=days)
    start_price = None
    for row in rows:
        if row[0] >= start_cutoff:
            start_price = float(row[1])
            break
    if start_price is None or start_price == 0:
        return None
    end_price = float(rows[-1][1])
    if end_price == 0:
        return None
    return round(end_price / start_price - 1, 6)

def main():
    print("ETF Return Backfill — direct SQL")
    print(f"Started: {date.today()}")
    
    conn = psycopg2.connect(DB_URL, connect_timeout=60)
    conn.autocommit = True
    cur = conn.cursor()
    
    # Get all ETFs with their price history
    cur.execute("SELECT id, symbol FROM foreign_etfs WHERE is_active = true ORDER BY id")
    etfs = cur.fetchall()
    print(f"Total active ETFs: {len(etfs)}")
    
    updated = 0
    skipped = 0
    
    for etf_id, symbol in etfs:
        # Get price history (up to 180 days, DESC so newest is first)
        cur.execute("""
            SELECT date, close FROM foreign_etf_prices
            WHERE symbol = %s
            ORDER BY date DESC
            LIMIT 200
        """, (symbol,))
        rows_desc = cur.fetchall()
        
        if len(rows_desc) < 5:
            skipped += 1
            continue
        
        rows = list(reversed(rows_desc))  # ASC
        
        ret_1m = calc_return_from_rows(rows, 30)
        ret_3m = calc_return_from_rows(rows, 90)
        ret_6m = calc_return_from_rows(rows, 180)
        
        if ret_1m is None and ret_3m is None and ret_6m is None:
            skipped += 1
            continue
        
        cur.execute("""
            UPDATE foreign_etfs
            SET one_month_return_try = %s,
                three_month_return_try = %s,
                six_month_return_try = %s,
                updated_at = NOW()
            WHERE id = %s
        """, (ret_1m, ret_3m, ret_6m, etf_id))
        
        updated += 1
        if updated % 200 == 0:
            print(f"  Updated {updated}/{len(etfs)}...")
    
    print(f"\nDONE: {updated} updated, {skipped} skipped")
    
    # Verify ONDL
    cur.execute("""
        SELECT symbol, one_month_return_try, three_month_return_try, six_month_return_try
        FROM foreign_etfs WHERE symbol IN ('ONDL','SPY','VOO','QQQ')
    """)
    print("\nVerification:")
    print(f"{'Symbol':<8} {'1M':>10} {'3M':>10} {'6M':>10}")
    print("-" * 40)
    for row in cur.fetchall():
        print(f"{row[0]:<8} {row[1]:>10.4f} {row[2]:>10.4f} {row[3]:>10.4f}")
    
    conn.close()

if __name__ == "__main__":
    main()
