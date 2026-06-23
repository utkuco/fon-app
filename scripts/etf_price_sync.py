#!/usr/bin/env python3
"""
ETF fiyat senkronu — günlük, yfinance'siz, hızlı (sadece DB).

Neden var: foreign_etfs.price/price_try/ytd_return'ü güncel tutan ayrı bir job
yoktu (etf_scraper/metadata düzenli koşmuyor) ve exchange_rates (USD/TRY) güncel
kalmıyordu → ETF fiyatları haftalarca bayatlıyordu. Bu script iki boşluğu kapatır:

  1. exchange_rates'i benchmarks.USDTRY'den (taze; com.fonapp.benchmarks yazıyor)
     eksik günler için doldurur.
  2. foreign_etfs.price/price_try/ytd_return'ü, taze foreign_etf_prices (günlük
     etf-daily-cron yazıyor) + güncel kurdan DB içinde senkronlar.

Çalışma sırası: benchmarks (23:30) → etf-daily-cron (07:01) → BU (07:45).
"""
import os
import sys
import psycopg2


def db_url() -> str:
    url = os.environ.get("SUPABASE_DB_URL")
    if url:
        return url
    # web/.env'den ayrıştır (launchd env vermezse)
    env_path = os.path.join(os.path.dirname(__file__), "..", "web", ".env")
    for line in open(env_path):
        if line.startswith("SUPABASE_DB_URL="):
            return line.split("=", 1)[1].strip().strip('"')
    raise RuntimeError("SUPABASE_DB_URL bulunamadı")


def main() -> int:
    conn = psycopg2.connect(db_url(), connect_timeout=30)
    conn.autocommit = True
    cur = conn.cursor()

    # ── 1. exchange_rates'i benchmarks.USDTRY'den doldur (eksik günler) ──────
    cur.execute(
        "SELECT COALESCE(MAX(date), '2000-01-01') FROM exchange_rates "
        "WHERE base='USD' AND quote='TRY'"
    )
    last_fx = cur.fetchone()[0]
    cur.execute(
        """
        INSERT INTO exchange_rates (base, quote, rate, date, updated_at)
        SELECT 'USD', 'TRY', round(price::numeric, 4), date, now()
        FROM benchmarks
        WHERE symbol = 'USDTRY' AND date > %s
        ON CONFLICT (base, quote, date) DO UPDATE SET rate = EXCLUDED.rate, updated_at = now()
        """,
        (last_fx,),
    )
    print(f"exchange_rates: {cur.rowcount} gün eklendi/güncellendi (önceki son: {last_fx})")

    # ── 2. Güncel USD/TRY ────────────────────────────────────────────────────
    cur.execute(
        "SELECT rate FROM exchange_rates WHERE base='USD' AND quote='TRY' "
        "ORDER BY date DESC LIMIT 1"
    )
    row = cur.fetchone()
    if not row:
        print("USD/TRY kuru yok — çıkılıyor", file=sys.stderr)
        return 1
    rate = float(row[0])

    # ── 3. foreign_etfs.price/price_try/ytd_return'ü taze geçmişten senkronla ─
    cur.execute(
        """
        WITH latest AS (
          SELECT DISTINCT ON (symbol) symbol, close
          FROM foreign_etf_prices ORDER BY symbol, date DESC
        ),
        ytd AS (
          SELECT DISTINCT ON (symbol) symbol, close AS ytd_close
          FROM foreign_etf_prices
          WHERE date >= date_trunc('year', now())::date
          ORDER BY symbol, date ASC
        )
        UPDATE foreign_etfs fe SET
          price      = l.close,
          price_try  = round((l.close * %s)::numeric, 2),
          ytd_return = CASE WHEN y.ytd_close > 0
                            THEN round((((l.close - y.ytd_close) / y.ytd_close) * 100)::numeric, 4)
                            ELSE fe.ytd_return END,
          updated_at = now()
        FROM latest l LEFT JOIN ytd y ON y.symbol = l.symbol
        WHERE fe.symbol = l.symbol
        """,
        (rate,),
    )
    print(f"foreign_etfs: {cur.rowcount} ETF senkronlandı (USD/TRY={rate})")

    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
