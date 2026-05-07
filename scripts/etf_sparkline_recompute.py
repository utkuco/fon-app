#!/usr/bin/env python3
"""
Recompute ETF sparklines from DB — fixes 10-point bug where cron was writing
incorrect sparse sparklines due to PostgREST limit issues.
"""
import psycopg2, json, time, sys
from datetime import date, timedelta

SUPABASE = dict(
    host='db.oqkobptbvcazifpvjwfz.supabase.co',
    port=5432,
    dbname='postgres',
    user='postgres',
    password='rzvfO6ub5F1W6hpR'
)
W, H = 280, 40

def compute_sparkline(closes: list[float]) -> dict:
    if len(closes) < 2:
        return None
    mn, mx = min(closes), max(closes)
    rng = mx - mn or 1
    step = W / (len(closes) - 1)
    points = [[round(i * step, 4), round((1 - (c - mn) / rng) * H, 4)] for i, c in enumerate(closes)]
    return {"points": points, "positive": bool(closes[-1] >= closes[0])}

def main():
    conn = psycopg2.connect(**SUPABASE, connect_timeout=30)
    cur = conn.cursor()

    cutoff = (date.today() - timedelta(days=30)).isoformat()
    today = date.today().isoformat()
    print(f"[{time.strftime('%H:%M:%S')}] ETF sparkline recompute — cutoff: {cutoff}")
    print(f"  Today: {today}")

    # Get all ETFs
    cur.execute("SELECT id, symbol FROM foreign_etfs WHERE is_active = true AND sparkline IS NOT NULL")
    etfs = cur.fetchall()
    print(f"  Total ETFs: {len(etfs)}")

    updated, skipped, errors = 0, 0, 0

    for etf_id, symbol in etfs:
        try:
            # Fetch last 30 days of prices directly via psycopg2
            cur.execute("""
                SELECT close FROM foreign_etf_prices
                WHERE symbol = %s AND date >= %s
                ORDER BY date ASC
            """, (symbol, cutoff))
            rows = cur.fetchall()
            closes = [float(r[0]) for r in rows if r[0] is not None]

            if len(closes) < 2:
                skipped += 1
                continue

            spark = compute_sparkline(closes)
            if not spark:
                skipped += 1
                continue

            # Check if update needed
            cur.execute("SELECT sparkline FROM foreign_etfs WHERE id = %s", (etf_id,))
            row = cur.fetchone()
            raw = row[0] if row else None
            if raw is None:
                skipped += 1
                continue
            existing = raw if isinstance(raw, dict) else json.loads(raw) if isinstance(raw, str) else {}
            # Always update if point count is wrong (10 instead of 22 = broken sparkline)
            if len(existing.get('points', [])) != len(spark['points']):
                # Point count mismatch — force update
                pass  # falls through to update below
            elif existing.get('points') == spark['points']:
                # Same point count AND same values — skip
                continue

            cur.execute("""
                UPDATE foreign_etfs
                SET sparkline = %s, updated_at = NOW()
                WHERE id = %s
            """, (json.dumps(spark), etf_id))
            updated += 1

        except Exception as e:
            errors += 1
            print(f"  ERROR {symbol}: {e}")

    conn.commit()
    conn.close()
    print(f"\n✅ Done — updated={updated}, skipped={skipped}, errors={errors}")

if __name__ == '__main__':
    main()
