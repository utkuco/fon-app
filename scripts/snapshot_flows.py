#!/usr/bin/env python3.11
"""Günlük yatırımcı/büyüklük snapshot'ı — "Para Nereye Gidiyor" verisi.

Her gün çalışır: TR fonların (num_investors, market_cap) ve yabancı ETF'lerin
(aum) o günkü değerini fund_flow_snapshots tablosuna yazar. Birikince günlük
DEĞİŞİM (para girişi/çıkışı) hesaplanabilir.

Tablo ilk çalıştırmada otomatik oluşturulur (idempotent). Bugünkü değerlerle
baseline tohumlar; ertesi günlerden itibaren delta anlamlı olur.
"""
import os
import sys
from datetime import datetime, timezone

import psycopg2
import psycopg2.extras

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))


def load_env():
    for p in [os.path.join(SCRIPT_DIR, "..", "web", ".env"),
              os.path.expanduser("~/.hermes/.env")]:
        try:
            with open(p) as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, _, v = line.partition("=")
                        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
        except FileNotFoundError:
            pass


def log(m):
    print(f"[{datetime.now(timezone.utc).astimezone():%Y-%m-%d %H:%M:%S}] {m}", flush=True)


DDL = """
CREATE TABLE IF NOT EXISTS fund_flow_snapshots (
    id            BIGSERIAL PRIMARY KEY,
    asset_code    TEXT NOT NULL,
    kind          TEXT NOT NULL CHECK (kind IN ('fund','etf')),
    snapshot_date DATE NOT NULL,
    num_investors BIGINT,
    total_value   NUMERIC,          -- fon: market_cap (TL), etf: aum (USD)
    created_at    TIMESTAMPTZ DEFAULT now(),
    UNIQUE (asset_code, snapshot_date)
);
CREATE INDEX IF NOT EXISTS idx_fund_flow_date ON fund_flow_snapshots (snapshot_date);
CREATE INDEX IF NOT EXISTS idx_fund_flow_code ON fund_flow_snapshots (asset_code);
"""


def main() -> int:
    load_env()
    dsn = os.environ.get("SUPABASE_DB_URL", "")
    if not dsn:
        log("SUPABASE_DB_URL yok — çıkılıyor")
        return 1
    today = datetime.now(timezone.utc).astimezone().date().isoformat()

    conn = psycopg2.connect(dsn)
    conn.autocommit = True
    cur = conn.cursor()
    cur.execute(DDL)

    rows = []
    # TR fonlar
    cur.execute("SELECT code, num_investors, market_cap FROM funds WHERE is_active IS NOT FALSE")
    for code, inv, mcap in cur.fetchall():
        if inv is None and mcap is None:
            continue
        rows.append((code, "fund", today, inv, mcap))
    n_fund = len(rows)
    # Yabancı ETF'ler
    cur.execute("SELECT symbol, aum FROM foreign_etfs WHERE is_active IS NOT FALSE")
    for sym, aum in cur.fetchall():
        if aum is None:
            continue
        rows.append((sym, "etf", today, None, aum))
    n_etf = len(rows) - n_fund

    psycopg2.extras.execute_values(
        cur,
        """INSERT INTO fund_flow_snapshots (asset_code, kind, snapshot_date, num_investors, total_value)
           VALUES %s
           ON CONFLICT (asset_code, snapshot_date) DO UPDATE
           SET num_investors = EXCLUDED.num_investors,
               total_value   = EXCLUDED.total_value""",
        rows,
    )
    log(f"snapshot {today}: {n_fund} fon + {n_etf} ETF = {len(rows)} kayıt")
    cur.close()
    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
