#!/usr/bin/env python3
"""
KAP duyuruları çekici — tüm TR fon duyurularını fund_announcements tablosuna
yazar. Mevcut kap_daily_pipeline.py'den farkı:
  - Sadece portföy dağılımı değil, TÜM duyuru tipleri (Önemli Olay, Bilgi
    Notları, vs).
  - Fon koduyla eşleştir (companyTitle prefix'ten + master_data'dan).
  - PDF indirme yok — sadece başlık + KAP linki kaydedilir. Detay isteyen
    KAP'a yönlenir.

Saatte 1 çalışır. AI özetler ayrı script (kap_summarize.py) tarafından
async eklenir.
"""
import json
import os
import re
import ssl
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import psycopg2
import psycopg2.extras
import requests

# certifi bundle — KAP cron'unun SSL hatası buradan kaynaklanıyordu
os.environ.setdefault(
    "SSL_CERT_FILE",
    "/opt/homebrew/lib/python3.11/site-packages/certifi/cacert.pem",
)

DB_URL = os.environ.get(
    "SUPABASE_DB_URL",
    "postgresql://postgres:rzvfO6ub5F1W6hpR@db.oqkobptbvcazifpvjwfz.supabase.co:5432/postgres",
)

KAP_BASE = "https://www.kap.org.tr/tr"
KAP_HEADERS = {
    "Content-Type": "application/json",
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Accept": "application/json",
}

FUND_TYPES_OF_INTEREST = ["YF", "BYF", "OKS", "YYF", "VFF", "KFF", "GMF", "GSF", "PFF", "EMK"]


def log(msg: str) -> None:
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")


def ensure_table(conn) -> None:
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS fund_announcements (
            id            uuid DEFAULT gen_random_uuid() PRIMARY KEY,
            kap_oid       text UNIQUE NOT NULL,
            disclosure_index text,
            fund_code     text,
            fund_name     text,
            company_title text,
            subject       text,
            title         text,
            publish_date  timestamptz,
            kap_url       text,
            fund_type     text,
            related_stocks text[],
            ai_summary    text,
            ai_sentiment  text,
            impact_category text[],
            impact_funds text[],
            importance    text,
            topic         text,
            fetched_at    timestamptz DEFAULT now()
        )
        """
    )
    # Make sure existing tables get the new columns too
    cur.execute("ALTER TABLE fund_announcements ADD COLUMN IF NOT EXISTS related_stocks text[]")
    cur.execute("ALTER TABLE fund_announcements ADD COLUMN IF NOT EXISTS impact_category text[]")
    cur.execute("ALTER TABLE fund_announcements ADD COLUMN IF NOT EXISTS impact_funds text[]")
    cur.execute("ALTER TABLE fund_announcements ADD COLUMN IF NOT EXISTS importance text")
    cur.execute("ALTER TABLE fund_announcements ADD COLUMN IF NOT EXISTS topic text")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_fund_announcements_publish ON fund_announcements (publish_date DESC)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_fund_announcements_fund ON fund_announcements (fund_code)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_fund_announcements_related ON fund_announcements USING GIN (related_stocks)")
    conn.commit()


def fetch_disclosures(from_date: datetime, to_date: datetime) -> list[dict]:
    """All fund disclosures in the date range — no subject filter."""
    payload = {
        "fromDate": from_date.strftime("%d.%m.%Y"),
        "toDate": to_date.strftime("%d.%m.%Y"),
        "disclosureTypes": None,
        "fundTypes": FUND_TYPES_OF_INTEREST,
    }
    r = requests.post(
        f"{KAP_BASE}/api/disclosure/list/main",
        headers=KAP_HEADERS,
        json=payload,
        timeout=60,
    )
    if r.status_code != 200:
        log(f"  KAP {from_date.date()}→{to_date.date()} status={r.status_code} body={r.text[:200]}")
        return []
    return r.json() or []


def load_fund_code_map(cur) -> dict[str, str]:
    """Map company TITLE LIKE → fund_code. KAP company titles are
    structured 'KOD FON YÖNETİM A.Ş. ... FONU' so we match by code
    appearing as first token of name."""
    cur.execute("SELECT code, name FROM funds")
    title_to_code: dict[str, str] = {}
    for code, name in cur.fetchall():
        if not name:
            continue
        # KAP returns titles like "İŞ PORTFÖY..."
        # Funds named "AKP İŞ PORTFÖY ... FONU" — we can map via first token.
        first_token = name.split(" ", 1)[0].strip().upper()
        if first_token == code.upper():
            # KAP companyTitle benzer şekilde olur
            title_to_code[name.upper()] = code
        title_to_code[code.upper()] = code
    return title_to_code


def derive_fund_code(item: dict, title_to_code: dict[str, str]) -> str | None:
    """Try a couple of strategies to attach a fund_code to a disclosure."""
    basic = item.get("disclosureBasic", {})
    title = (basic.get("title") or "").upper()
    company = (basic.get("companyTitle") or "").upper()

    # 1. Look for a fund code embedded in the title (3-5 letter codes appear
    #    as " AK1 ", "(BSE)", etc).
    m = re.search(r"\b([A-Z]{2,5})\b", title)
    if m:
        candidate = m.group(1)
        if candidate in title_to_code.values():
            return candidate

    # 2. Match company → first token of fund name
    if company:
        # "İŞ PORTFÖY..." → "İŞ" — match funds starting with same word
        first = company.split(" ", 1)[0]
        # Many funds have code starting with first letter of company; we
        # need a fuzzier match.
        return None

    return None


def parse_kap_date(s: str | None) -> datetime | None:
    """KAP publishDate gerçek format: 'DD.MM.YYYY HH:mm:ss' (TR locale)."""
    if not s:
        return None
    s = s.strip()
    for fmt in ("%d.%m.%Y %H:%M:%S", "%d.%m.%Y %H:%M", "%d.%m.%Y",
                "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    return None


def split_related_stocks(s: str | None) -> list[str]:
    if not s:
        return []
    parts = [p.strip().upper() for p in re.split(r"[,;\s]+", s) if p.strip()]
    return [p for p in parts if 2 <= len(p) <= 6 and p.isalnum()][:50]


def upsert_announcements(conn, items: list[dict], code_map: dict[str, str]) -> tuple[int, int]:
    cur = conn.cursor()
    inserted = 0
    updated = 0
    for item in items:
        basic = item.get("disclosureBasic") or {}
        oid = basic.get("disclosureIndex") or basic.get("kapDisclosureIndex")
        if not oid:
            continue
        oid = str(oid)
        # KAP semantik: title = disclosure tipi ("Genel Açıklama"),
        # summary = asıl başlık ("TASARRUF SAHİPLERİNE DUYURU")
        kap_title = basic.get("title") or ""
        kap_summary = basic.get("summary") or ""
        # Subject (kategori) = title, gerçek başlık = summary
        subject = kap_title
        title = kap_summary or kap_title
        company = basic.get("companyTitle") or ""
        publish = basic.get("publishDate")
        fund_type = basic.get("fundType") or ""
        related_stocks = split_related_stocks(basic.get("relatedStocks"))
        # KAP duyuru detay sayfası
        kap_url = f"https://www.kap.org.tr/tr/Bildirim/{oid}"
        fund_code = derive_fund_code(item, code_map)
        # Fon kodunu relatedStocks'tan da çıkar (tek fonsa)
        if not fund_code and len(related_stocks) == 1:
            fund_code = related_stocks[0]
        fund_name = company

        publish_dt = parse_kap_date(publish)

        cur.execute(
            """
            INSERT INTO fund_announcements
              (kap_oid, disclosure_index, fund_code, fund_name, company_title,
               subject, title, publish_date, kap_url, fund_type, related_stocks)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (kap_oid) DO UPDATE
              SET title = EXCLUDED.title,
                  subject = EXCLUDED.subject,
                  publish_date = EXCLUDED.publish_date,
                  fund_type = EXCLUDED.fund_type,
                  related_stocks = EXCLUDED.related_stocks
              WHERE fund_announcements.title IS DISTINCT FROM EXCLUDED.title
                 OR fund_announcements.publish_date IS DISTINCT FROM EXCLUDED.publish_date
                 OR fund_announcements.related_stocks IS DISTINCT FROM EXCLUDED.related_stocks
            RETURNING (xmax = 0) AS inserted
            """,
            (
                oid, oid, fund_code, fund_name, company,
                subject, title, publish_dt, kap_url, fund_type, related_stocks,
            ),
        )
        row = cur.fetchone()
        if row and row[0]:
            inserted += 1
        else:
            updated += 1
    conn.commit()
    return inserted, updated


def main() -> int:
    days_back = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    log(f"KAP announcements fetcher — last {days_back}d")

    conn = psycopg2.connect(DB_URL)
    ensure_table(conn)

    cur = conn.cursor()
    code_map = load_fund_code_map(cur)
    log(f"  fund code map: {len(code_map)} entries")

    # Chunk by 7 days to avoid hitting any rate limit
    end = datetime.now()
    cursor = end - timedelta(days=days_back)
    total_ins = 0
    total_upd = 0
    while cursor < end:
        chunk_end = min(end, cursor + timedelta(days=7))
        items = fetch_disclosures(cursor, chunk_end)
        if items:
            ins, upd = upsert_announcements(conn, items, code_map)
            log(f"  {cursor.date()}→{chunk_end.date()}: {len(items)} items ({ins} new, {upd} updated)")
            total_ins += ins
            total_upd += upd
        cursor = chunk_end + timedelta(seconds=1)
        time.sleep(0.5)

    log(f"Total: {total_ins} new, {total_upd} updated")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
