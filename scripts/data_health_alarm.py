#!/usr/bin/env python3
"""Data freshness watchdog. Runs every 30 min via cron; pings Telegram if any
of the following are stale or empty:
  - homepage_stats.latest_date older than 6 h
  - funds count below 2000
  - foreign_etfs latest updated_at older than 24 h
  - fund_holdings stalest record older than 3 days (cron likely down)
  - homepage_stats.most_held_stocks empty
  - benchmarks_data latest date older than 2 days

Without this, when a TEFAS scraper / Yahoo cron silently fails the homepage
gradually drifts into a state nobody notices for days (see fund_holdings
which sat stale for 37 d before audit caught it)."""
import os
import sys
import json
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

PROJECT_ROOT = "/Users/admin/Documents/Projects/fon-app"
ENV_FILE = f"{PROJECT_ROOT}/web/.env"

# Bootstrap env so SUPABASE_DB_URL / telegram creds are reachable.
if os.path.exists(ENV_FILE):
    for line in open(ENV_FILE):
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "2065333086")  # Utku
DB_URL = os.environ.get("SUPABASE_DB_URL", "")


def telegram(msg: str) -> None:
    if not TELEGRAM_BOT_TOKEN:
        print(f"[no-tg] {msg}")
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    # Skip parse_mode — `_` and `*` in messages routinely fail Markdown parse;
    # plain text is fine for a 3-line alert.
    data = urllib.parse.urlencode({
        "chat_id": TELEGRAM_CHAT_ID,
        "text": msg,
    }).encode()
    try:
        with urllib.request.urlopen(url, data=data, timeout=10) as r:
            r.read()
    except Exception as e:
        print(f"telegram failed: {e}")


def main() -> int:
    if not DB_URL:
        print("SUPABASE_DB_URL missing — skipping")
        return 0
    import psycopg2
    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()
    now = datetime.now(timezone.utc)
    alarms: list[str] = []

    # latest_date freshness — TEFAS scrape cadence is hourly so >6h = problem
    cur.execute("SELECT updated_at FROM homepage_stats WHERE id=1")
    row = cur.fetchone()
    if row and row[0]:
        age = (now - row[0]).total_seconds() / 3600
        if age > 6:
            alarms.append(f"⚠️ homepage_stats.updated_at {age:.1f}h eski")

    cur.execute("SELECT count(*) FROM funds")
    total = cur.fetchone()[0]
    if total < 2000:
        alarms.append(f"⚠️ funds count {total} < 2000 — TEFAS scraper düşmüş olabilir")

    cur.execute("SELECT max(updated_at) FROM foreign_etfs WHERE is_active=true")
    etf_latest = cur.fetchone()[0]
    if etf_latest:
        age_h = (now - etf_latest).total_seconds() / 3600
        if age_h > 24:
            alarms.append(f"⚠️ ETF veri {age_h:.0f}h eski (Yahoo cron)")

    cur.execute("SELECT max(updated_at) FROM fund_holdings")
    holdings_latest = cur.fetchone()[0]
    if holdings_latest:
        age_d = (now - holdings_latest).total_seconds() / 86400
        if age_d > 3:
            alarms.append(f"⚠️ fund_holdings {age_d:.0f} gün eski — parser kapalı")

    cur.execute("SELECT most_held_stocks FROM homepage_stats WHERE id=1")
    mhs = cur.fetchone()
    if not mhs or not mhs[0] or len(mhs[0]) == 0:
        alarms.append("⚠️ most_held_stocks boş")

    cur.execute(
        "SELECT max(date) FROM benchmark_prices WHERE symbol IN ('TRY=X','XU100.IS','GC=F')"
    )
    bench_latest = cur.fetchone()[0]
    if bench_latest:
        # bench_latest is a date, compare to today
        bench_age = (now.date() - bench_latest).days
        if bench_age > 2:
            alarms.append(f"⚠️ benchmark_prices son {bench_age} gün öncesi")

    if alarms:
        body = "FonRapor veri sağlık alarmı\n" + "\n".join(alarms) + f"\n\n{now.strftime('%Y-%m-%d %H:%M UTC')}"
        telegram(body)
        print(body)
        return 1
    print(f"[{now.isoformat()}] all checks OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
