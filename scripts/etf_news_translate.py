#!/usr/bin/env python3
"""
ETF haberlerini MiniMax-M2.7 ile Türkçeye çevirir + özetler + sınıflandırır.

etf_news tablosunda ai_summary IS NULL olan kayıtlar için İngilizce başlığı
Türkçeye çevirir, kısa Türkçe özet üretir, etkilediği tema(ları), sentiment ve
önem skorunu çıkarır.

Saat başı çalışır; KAP_SUMMARIZE_BATCH benzeri ETF_NEWS_BATCH ile sınırlanır.
"""
import json
import os
import re
import time
from datetime import datetime
from typing import Optional

import psycopg2
import psycopg2.extras
import requests

# ─── Env bootstrap ─────────────────────────────────────────────────────
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
BATCH_SIZE = int(os.environ.get("ETF_NEWS_BATCH", "30"))

# etf-themes.ts ile uyumlu tema slug'ları (sınıflandırma için)
THEME_SLUGS = [
    "kahve", "yapay-zeka", "savunma", "su", "elektrikli-arac", "temiz-enerji",
    "nukleer", "biyoteknoloji", "siber-guvenlik", "madencilik", "cannabis",
    "yuksek-temettu",
]
# Geniş bucket'lar (tema dışı genel piyasa haberleri için)
BUCKET_SLUGS = ["us-hisse", "kuresel-hisse", "gelismekte-olan", "sektor", "tahvil", "emtia", "kripto"]


def log(msg: str) -> None:
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")


SYSTEM_PROMPT = f"""Sen Türk yatırımcılar için çalışan bir finans editörüsün. Sana
İngilizce bir ETF/borsa haber başlığı (ve varsa ilgili semboller) veriliyor.
Aşağıdaki JSON şemasını üret — sadece JSON, açıklama yok:

{{
  "title_tr": "Başlığın akıcı Türkçe çevirisi (terimleri Türk yatırımcının anlayacağı şekilde)",
  "summary": "1-2 cümle Türkçe özet — neden önemli, yatırımcıyı nasıl etkiler",
  "detail": "3-4 cümlelik Türkçe açıklama: haberde ne anlatılıyor, hangi sektör/varlık etkileniyor, Türk yatırımcı açısından (USD/TL etkisi dahil) ne anlama geliyor. Yatırım tavsiyesi verme.",
  "impact_themes": "şu temalardan etkilenenler" listesi (0-3): {', '.join(THEME_SLUGS)}. Tema yoksa boş liste.
  "impact_buckets": "şu geniş kategorilerden uygun olanlar" listesi (1-2): {', '.join(BUCKET_SLUGS)}
  "sentiment": "positive / negative / neutral" (yatırımcı açısından),
  "importance": "high / medium / low",
  "topic": "kısa Türkçe kategori — örn: faiz kararı, kazanç raporu, sektör rotasyonu, jeopolitik, emtia fiyatı, kripto"
}}

Önem: high = piyasayı geniş etkileyen (Fed, enflasyon, büyük teknoloji, jeopolitik
şok); medium = sektör/tema bazlı; low = tekil şirket/rutin.

Yanıt SADECE JSON. Markdown veya başka metin yok. Türkçe karakter kullan."""


def call_minimax(prompt: str, retries: int = 3) -> Optional[dict]:
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
                    "max_tokens": 700,
                    "system": SYSTEM_PROMPT,
                    "messages": [{"role": "user", "content": prompt}],
                },
                timeout=60,
            )
            if r.status_code != 200:
                log(f"  MiniMax HTTP {r.status_code}: {r.text[:200]}")
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
            text = text.strip()
            text = re.sub(r"^```json\s*", "", text)
            text = re.sub(r"^```\s*", "", text)
            text = re.sub(r"\s*```$", "", text)
            m = re.search(r"\{[\s\S]*\}", text)
            if not m:
                log(f"  no JSON: {text[:150]}")
                return None
            return json.loads(m.group(0))
        except json.JSONDecodeError as e:
            log(f"  JSON parse error: {e}")
            return None
        except Exception as e:
            log(f"  request failed (attempt {attempt + 1}): {e}")
            time.sleep(2 + attempt)
    return None


def _as_list(v, allowed: list[str] | None = None):
    if v is None:
        return []
    raw = v if isinstance(v, list) else [v]
    out: list[str] = []
    for item in raw:
        s = str(item).strip()
        if not s:
            continue
        for part in re.split(r"[/,;]+", s):
            p = part.strip()
            if p and (allowed is None or p in allowed):
                out.append(p)
    seen: set[str] = set()
    return [x for x in out if not (x in seen or seen.add(x))]


def main() -> int:
    if not MINIMAX_API_KEY:
        log("MINIMAX_API_KEY not set, exiting")
        return 1
    conn = psycopg2.connect(DB_URL)

    cur = conn.cursor()
    cur.execute("ALTER TABLE etf_news ADD COLUMN IF NOT EXISTS ai_detail text")
    conn.commit()

    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute(
        """
        SELECT id, source_uid, title_en, publisher, related_tickers
        FROM etf_news
        WHERE ai_detail IS NULL AND title_en IS NOT NULL
        ORDER BY publish_date DESC NULLS LAST
        LIMIT %s
        """,
        (BATCH_SIZE,),
    )
    rows = cur.fetchall()
    log(f"Pending ETF news: {len(rows)}")
    if not rows:
        return 0

    upd = conn.cursor()
    ok = err = 0
    for r in rows:
        tickers = ", ".join((r["related_tickers"] or [])[:10]) or "—"
        prompt = (
            f"Yayıncı: {r['publisher']}\nİlgili semboller: {tickers}\n\n"
            f"Haber başlığı (EN): {r['title_en']}"
        )
        result = call_minimax(prompt)
        if not result:
            err += 1
            time.sleep(1)
            continue
        try:
            upd.execute(
                """
                UPDATE etf_news
                SET title_tr = %s,
                    ai_summary = %s,
                    ai_detail = %s,
                    ai_sentiment = %s,
                    impact_themes = %s,
                    importance = %s,
                    topic = %s
                WHERE id = %s
                """,
                (
                    result.get("title_tr"),
                    result.get("summary"),
                    result.get("detail") or result.get("summary"),
                    result.get("sentiment"),
                    _as_list(result.get("impact_themes"), THEME_SLUGS),
                    result.get("importance"),
                    result.get("topic"),
                    r["id"],
                ),
            )
            conn.commit()
            ok += 1
            if ok % 5 == 0:
                log(f"  committed {ok}")
            time.sleep(0.6)
        except Exception as e:
            log(f"  update failed for {r['source_uid']}: {e}")
            conn.rollback()
            err += 1

    conn.commit()
    log(f"Done — {ok} translated, {err} errors")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
