#!/usr/bin/env python3
"""
ETF haber çekici — Yahoo Finance'ten yabancı ETF haberlerini çeker,
etf_news tablosuna upsert eder. AI çeviri/özet ayrı script
(etf_news_translate.py) tarafından async eklenir.

Strateji: Her ETF için ayrı ayrı çekmek yerine, geniş piyasayı temsil eden
"anchor" ETF setinden haber toplar (AUM lideri + tematik), URL'e göre tekilleştirir.
relatedTickers ile hangi ETF'leri etkilediğini saklar.
"""
import hashlib
import os
import sys
import time
from datetime import datetime, timezone
from urllib.parse import urlparse

import psycopg2
import requests

os.environ.setdefault(
    "SSL_CERT_FILE",
    "/opt/homebrew/lib/python3.11/site-packages/certifi/cacert.pem",
)

DB_URL = os.environ.get(
    "SUPABASE_DB_URL",
    "postgresql://postgres:rzvfO6ub5F1W6hpR@db.oqkobptbvcazifpvjwfz.supabase.co:5432/postgres",
)

YF_SEARCH = "https://query2.finance.yahoo.com/v1/finance/search"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Accept": "application/json",
}

# Tematik anchor'lar — etf-themes.ts ile uyumlu. Geniş piyasa + sektör + tema.
THEMATIC_ANCHORS = [
    # Broad / sektör
    "SPY", "QQQ", "VTI", "XLK", "XLE", "XLF", "XLV", "SMH",
    # Emtia / tahvil
    "GLD", "AGG", "TLT",
    # Tema (etf-themes tickers'tan birer temsilci)
    "BOTZ", "AIQ",       # yapay zeka
    "PPA", "ITA",        # savunma
    "ICLN", "TAN",       # temiz enerji
    "URA", "NLR",        # nükleer
    "IBB", "XBI",        # biyoteknoloji
    "CIBR", "HACK",      # siber güvenlik
    "LIT", "DRIV",       # elektrikli araç
    "PHO", "FIW",        # su
    "DBA", "JO",         # kahve / soft emtia
    "PICK", "GDX",       # madencilik
    "MJ",                # cannabis
    "VYM", "SCHD",       # yüksek temettü
    "IBIT", "GBTC",      # kripto (bitcoin ETF)
]


def log(msg: str) -> None:
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")


def ensure_table(conn) -> None:
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS etf_news (
            id            uuid DEFAULT gen_random_uuid() PRIMARY KEY,
            source_uid    text UNIQUE NOT NULL,
            title_en      text,
            title_tr      text,
            publisher     text,
            link          text,
            publish_date  timestamptz,
            related_tickers text[],
            ai_summary    text,
            ai_sentiment  text,
            impact_themes text[],
            impact_etfs   text[],
            importance    text,
            topic         text,
            fetched_at    timestamptz DEFAULT now()
        )
        """
    )
    cur.execute("CREATE INDEX IF NOT EXISTS idx_etf_news_publish ON etf_news (publish_date DESC)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_etf_news_tickers ON etf_news USING GIN (related_tickers)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_etf_news_themes ON etf_news USING GIN (impact_themes)")
    conn.commit()


def load_known_symbols(cur) -> set[str]:
    cur.execute("SELECT symbol FROM foreign_etfs WHERE is_active")
    return {r[0].upper() for r in cur.fetchall()}


def fetch_news_for(symbol: str) -> list[dict]:
    try:
        r = requests.get(
            YF_SEARCH,
            params={"q": symbol, "newsCount": 8, "quotesCount": 0, "enableFuzzyQuery": "false"},
            headers=HEADERS,
            timeout=20,
        )
        if r.status_code != 200:
            log(f"  {symbol}: HTTP {r.status_code}")
            return []
        return r.json().get("news", []) or []
    except Exception as e:
        log(f"  {symbol}: error {e}")
        return []


def uid_for(item: dict) -> str | None:
    link = item.get("link") or ""
    uuid = item.get("uuid") or ""
    base = uuid or link
    if not base:
        return None
    return hashlib.sha1(base.encode("utf-8")).hexdigest()[:24]


def upsert_news(conn, items: list[dict], known: set[str]) -> tuple[int, int]:
    cur = conn.cursor()
    ins = upd = 0
    for it in items:
        uid = uid_for(it)
        if not uid:
            continue
        title = (it.get("title") or "").strip()
        if not title:
            continue
        publisher = it.get("publisher") or ""
        link = it.get("link") or ""
        ptime = it.get("providerPublishTime")
        publish_dt = (
            datetime.fromtimestamp(ptime, tz=timezone.utc) if isinstance(ptime, (int, float)) else None
        )
        related = [t.upper() for t in (it.get("relatedTickers") or []) if isinstance(t, str)]
        # Bizdeki ETF'lerle kesişen ticker'lar (impact_etfs ön-doldurma)
        impact_etfs = [t for t in related if t in known]

        cur.execute(
            """
            INSERT INTO etf_news
              (source_uid, title_en, publisher, link, publish_date, related_tickers, impact_etfs)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (source_uid) DO UPDATE
              SET related_tickers = EXCLUDED.related_tickers,
                  impact_etfs = EXCLUDED.impact_etfs,
                  publish_date = EXCLUDED.publish_date
              WHERE etf_news.related_tickers IS DISTINCT FROM EXCLUDED.related_tickers
            RETURNING (xmax = 0) AS inserted
            """,
            (uid, title, publisher, link, publish_dt, related, impact_etfs),
        )
        row = cur.fetchone()
        if row and row[0]:
            ins += 1
        else:
            upd += 1
    conn.commit()
    return ins, upd


def main() -> int:
    log("ETF news fetcher başlıyor")
    conn = psycopg2.connect(DB_URL)
    ensure_table(conn)
    cur = conn.cursor()
    known = load_known_symbols(cur)
    log(f"  bilinen ETF sembolü: {len(known)}")

    # AUM lideri 25 + tematik anchor'lar (tekil)
    cur.execute("SELECT symbol FROM foreign_etfs WHERE is_active ORDER BY aum DESC NULLS LAST LIMIT 25")
    top = [r[0].upper() for r in cur.fetchall()]
    anchors = list(dict.fromkeys(top + THEMATIC_ANCHORS))
    log(f"  {len(anchors)} anchor sembol için haber çekiliyor")

    seen_uids: set[str] = set()
    all_items: list[dict] = []
    for sym in anchors:
        news = fetch_news_for(sym)
        for it in news:
            uid = uid_for(it)
            if uid and uid not in seen_uids:
                seen_uids.add(uid)
                all_items.append(it)
        time.sleep(0.3)

    log(f"  toplam tekil haber: {len(all_items)}")
    ins, upd = upsert_news(conn, all_items, known)
    log(f"Bitti — {ins} yeni, {upd} güncellendi")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
