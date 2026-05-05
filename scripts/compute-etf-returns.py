#!/usr/bin/env python3
"""
Compute and update ETF returns for foreign_etfs table.
Runs locally with direct Postgres connection — single round-trip update.
Usage: python3 scripts/compute-etf-returns.py
"""
import psycopg2
import psycopg2.extras
from datetime import date, timedelta
import sys

# Direct Postgres connection
DB_URL = "postgresql://postgres:rzvfO6ub5F1W6hpR@db.oqkobptbvcazifpvjwfz.supabase.co:5432/postgres"

def compute_returns():
    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()

    # Today's date (use latest available in DB if needed)
    cur.execute("SELECT MAX(date) FROM foreign_etf_prices")
    today_str = cur.fetchone()[0]
    today = date.fromisoformat(str(today_str))

    d1m = today - timedelta(days=30)
    d3m = today - timedelta(days=90)
    d6m = today - timedelta(days=195)

    print(f"Computing returns: today={today}, 1m={d1m}, 3m={d3m}, 6m={d6m}")

    # ── Detect stock splits ─────────────────────────────────────────────────
    # If any ETF had a >50% single-day price change, mark returns as NULL
    cur.execute(f"""
        WITH daily_changes AS (
            SELECT
                symbol,
                date,
                close,
                LAG(close) OVER (PARTITION BY symbol ORDER BY date) as prev_close,
                close / NULLIF(LAG(close) OVER (PARTITION BY symbol ORDER BY date), 0) - 1 as daily_change
            FROM foreign_etf_prices
            WHERE date <= '{today}' AND date >= '{d6m}'
        ),
        splits AS (
            SELECT DISTINCT symbol FROM daily_changes
            WHERE ABS(daily_change) > 0.5
        )
        SELECT symbol FROM splits;
    """)
    split_etfs = [row[0] for row in cur.fetchall()]
    print(f"Stock splits detected: {split_etfs}")
    split_set = set(split_etfs)

    # ── Build split symbol list for SQL ────────────────────────────────────────
    if split_set:
        split_placeholder = "(" + ",".join([cur.mogrify("%s", (s,)).decode() for s in split_set]) + ")"
    else:
        split_placeholder = "(NULL)"  # never matches → no false splits

    sql = f"""
    WITH latest AS (
        SELECT DISTINCT ON (symbol) symbol, close
        FROM foreign_etf_prices
        WHERE date <= '{today}'
        ORDER BY symbol, date DESC
    ),
    p1m AS (
        SELECT DISTINCT ON (symbol) symbol, close
        FROM foreign_etf_prices
        WHERE date <= '{d1m}'
        ORDER BY symbol, date DESC
    ),
    p3m AS (
        SELECT DISTINCT ON (symbol) symbol, close
        FROM foreign_etf_prices
        WHERE date <= '{d3m}'
        ORDER BY symbol, date DESC
    ),
    p6m AS (
        SELECT DISTINCT ON (symbol) symbol, close
        FROM foreign_etf_prices
        WHERE date <= '{d6m}'
        ORDER BY symbol, date DESC
    ),
    combined AS (
        SELECT
            e.id,
            e.symbol,
            lp.close as pt,
            p1.close as p1,
            p3.close as p3,
            p6.close as p6,
            e.symbol IN {split_placeholder} as is_split
        FROM foreign_etfs e
        LEFT JOIN latest lp ON lp.symbol = e.symbol
        LEFT JOIN p1m p1 ON p1.symbol = e.symbol
        LEFT JOIN p3m p3 ON p3.symbol = e.symbol
        LEFT JOIN p6m p6 ON p6.symbol = e.symbol
    )
    UPDATE foreign_etfs f SET
        one_month_return_try   = CASE WHEN c.is_split THEN NULL WHEN c.pt IS NULL OR c.p1 IS NULL OR c.p1 = 0 THEN NULL ELSE (c.pt / c.p1) - 1 END,
        three_month_return_try = CASE WHEN c.is_split THEN NULL WHEN c.pt IS NULL OR c.p3 IS NULL OR c.p3 = 0 THEN NULL ELSE (c.pt / c.p3) - 1 END,
        six_month_return_try   = CASE WHEN c.is_split THEN NULL WHEN c.pt IS NULL OR c.p6 IS NULL OR c.p6 = 0 THEN NULL ELSE (c.pt / c.p6) - 1 END
    FROM combined c
    WHERE f.id = c.id;
    """

    cur.execute(sql)
    updated = cur.rowcount
    conn.commit()

    # Verify
    cur.execute("SELECT COUNT(*) FROM foreign_etfs WHERE one_month_return_try IS NOT NULL")
    with_1m = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM foreign_etfs WHERE three_month_return_try IS NOT NULL")
    with_3m = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM foreign_etfs WHERE six_month_return_try IS NOT NULL")
    with_6m = cur.fetchone()[0]

    # Sample checks
    for sym in ['SPY', 'QQQ', 'VOO', 'BND', 'ARKK', 'MSTP']:
        cur.execute(f"""
            SELECT symbol, one_month_return_try, three_month_return_try, six_month_return_try
            FROM foreign_etfs WHERE symbol = '{sym}'
        """)
        row = cur.fetchone()
        if row:
            m1 = f"{row[1]*100:+.2f}%" if row[1] else "NULL"
            m3 = f"{row[2]*100:+.2f}%" if row[2] else "NULL"
            m6 = f"{row[3]*100:+.2f}%" if row[3] else "NULL"
            print(f"  {sym}: 1A={m1}, 3A={m3}, 6A={m6}")

    print(f"\nDone. Updated {updated} rows.")
    print(f"With 1A: {with_1m}, 3A: {with_3m}, 6A: {with_6m}")

    cur.close()
    conn.close()

if __name__ == "__main__":
    compute_returns()
