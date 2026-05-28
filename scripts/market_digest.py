#!/usr/bin/env python3
"""
Günün Piyasa Özeti — anasayfadaki "Günün Özeti" kartını besler.

Son 48 saatin en önemli KAP + küresel ETF haberlerini toplar, MiniMax-M2.7 ile
2-3 cümlelik Türkçe bir "piyasa gündemi özeti" sentezler ve market_digest
tablosuna (gün başına 1 kayıt) yazar.

Benchmark verisi güncel olmadığında bile çalışır — özet haber akışından üretilir.
"""
import json
import os
import re
import time
from datetime import datetime

import psycopg2
import psycopg2.extras
import requests

HERMES_ENV = "/Users/admin/.hermes/.env"
if os.path.exists(HERMES_ENV):
    for line in open(HERMES_ENV):
        line = line.strip()
        if line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        os.environ.setdefault(k.strip(), v.strip().strip('"'))

DB_URL = os.environ.get(
    "SUPABASE_DB_URL",
    "postgresql://postgres:rzvfO6ub5F1W6hpR@db.oqkobptbvcazifpvjwfz.supabase.co:5432/postgres",
)
MINIMAX_API_KEY = os.environ.get("MINIMAX_API_KEY", "")
MINIMAX_URL = "https://api.minimax.io/anthropic/v1/messages"
MINIMAX_MODEL = "MiniMax-M2.7"


def log(msg: str) -> None:
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")


def ensure_table(conn) -> None:
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS market_digest (
            digest_date  date PRIMARY KEY,
            headline     text,
            summary      text,
            based_on     int,
            generated_at timestamptz DEFAULT now()
        )
        """
    )
    conn.commit()


SYSTEM_PROMPT = """Sen Türk yatırımcılar için çalışan bir finans editörüsün. Sana
bugünün en önemli yatırım haberlerinin başlıkları/özetleri veriliyor (hem Türk
fonları/KAP hem küresel ETF/borsa). Bunlardan kısa bir "günün piyasa gündemi"
üret. Sadece JSON döndür:

{
  "headline": "Tek cümlelik, dikkat çekici Türkçe başlık (max 70 karakter)",
  "summary": "2-3 cümlelik Türkçe özet: bugün piyasaların/fonların gündeminde ne var, yatırımcı neye dikkat etmeli. Genel ve dengeli ol, tekil hisse tavsiyesi verme."
}

Abartma, clickbait yapma. Yatırım tavsiyesi verme — sadece gündemi özetle.
Yanıt SADECE JSON."""


def call_minimax(prompt: str, retries: int = 3):
    if not MINIMAX_API_KEY:
        return None
    for attempt in range(retries):
        try:
            r = requests.post(
                MINIMAX_URL,
                headers={
                    "x-api-key": MINIMAX_API_KEY,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": MINIMAX_MODEL,
                    "max_tokens": 600,
                    "system": SYSTEM_PROMPT,
                    "messages": [{"role": "user", "content": prompt}],
                },
                timeout=60,
            )
            if r.status_code != 200:
                log(f"  MiniMax HTTP {r.status_code}: {r.text[:160]}")
                time.sleep(2 + attempt)
                continue
            data = r.json()
            text = ""
            for block in data.get("content", []):
                if block.get("type") == "text":
                    text = block.get("text", "")
                    break
            if not text:
                for block in data.get("content", []):
                    if block.get("type") == "thinking":
                        text = block.get("thinking", "")
                        break
            text = re.sub(r"^```json\s*", "", text.strip())
            text = re.sub(r"^```\s*", "", text)
            text = re.sub(r"\s*```$", "", text)
            m = re.search(r"\{[\s\S]*\}", text)
            if not m:
                return None
            return json.loads(m.group(0))
        except Exception as e:
            log(f"  request failed ({attempt+1}): {e}")
            time.sleep(2 + attempt)
    return None


def gather_news(conn) -> list[str]:
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    lines: list[str] = []
    # Küresel — önem sırasına göre son haberler
    cur.execute(
        """
        SELECT COALESCE(title_tr, title_en) AS t, ai_summary, importance
        FROM etf_news
        WHERE ai_summary IS NOT NULL
          AND publish_date >= now() - interval '3 days'
        ORDER BY (importance = 'high') DESC, publish_date DESC
        LIMIT 6
        """
    )
    for r in cur.fetchall():
        lines.append(f"[Küresel] {r['t']} — {r['ai_summary']}")
    # KAP — sadece önemli olanlar
    cur.execute(
        """
        SELECT title, ai_summary
        FROM fund_announcements
        WHERE ai_summary IS NOT NULL
          AND importance = 'high'
          AND publish_date >= now() - interval '4 days'
        ORDER BY publish_date DESC
        LIMIT 4
        """
    )
    for r in cur.fetchall():
        lines.append(f"[Türk Fonları] {r['title']} — {r['ai_summary']}")
    return lines


def main() -> int:
    if not MINIMAX_API_KEY:
        log("MINIMAX_API_KEY not set, exiting")
        return 1
    conn = psycopg2.connect(DB_URL)
    ensure_table(conn)

    news = gather_news(conn)
    if not news:
        log("Yeterli haber yok — digest atlanıyor")
        return 0

    prompt = "Bugünün öne çıkan yatırım haberleri:\n\n" + "\n".join(f"- {n}" for n in news)
    result = call_minimax(prompt)
    if not result:
        log("MiniMax digest üretemedi")
        return 1

    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO market_digest (digest_date, headline, summary, based_on, generated_at)
        VALUES (CURRENT_DATE, %s, %s, %s, now())
        ON CONFLICT (digest_date) DO UPDATE
          SET headline = EXCLUDED.headline,
              summary = EXCLUDED.summary,
              based_on = EXCLUDED.based_on,
              generated_at = now()
        """,
        (result.get("headline"), result.get("summary"), len(news)),
    )
    conn.commit()
    log(f"Digest güncellendi — {len(news)} habere dayalı")
    log(f"  başlık: {result.get('headline')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
