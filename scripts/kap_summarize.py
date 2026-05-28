#!/usr/bin/env python3
"""
KAP duyurularını MiniMax-M2.7 ile özetler.

fund_announcements tablosunda ai_summary IS NULL olan kayıtlar için
MiniMax'a Anthropic-compatible endpoint üzerinden istek atar, JSON yanıt
ister: özet + etkilenen fon tipi + sentiment + önem skoru.

Saat başı çalışır; her run en çok 30 yeni duyuru özetler (rate limiting).
"""
import json
import os
import re
import sys
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

BATCH_SIZE = int(os.environ.get("KAP_SUMMARIZE_BATCH", "30"))


def log(msg: str) -> None:
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")


SYSTEM_PROMPT = """Sen bir Türk yatırım fonu analistisin. Sana KAP'tan gelen
bir duyuru başlığı veriliyor. Aşağıdaki JSON şemasını üret — sadece JSON,
açıklama yok:

{
  "summary": "1-2 cümle Türkçe özet — yatırımcının anlayabileceği sade dilde",
  "impact_category": "HSF / PPF / BAF / KMF / ALTIN / DÖVİZ / KFF / SRF / FSF / OKS / BYF / DGR" listesinden 1-3 kategori,
  "impact_funds": "duyuruda doğrudan adı geçen fon kodları" listesi (1-5),
  "sentiment": "positive / negative / neutral",
  "importance": "high / medium / low",
  "topic": "kısa kategori — örn: portföy değişikliği, vergi, performans, kurucu/yönetici değişikliği, ücret, yeni fon, vs"
}

Önem seviyeleri:
- high: yatırımcının aksiyon alması gereken (yönetim ücreti değişimi,
  fon kapanması, önemli portföy değişikliği, vergi/regülasyon)
- medium: bilgilendirici, portföy raporu, periyodik açıklamalar
- low: rutin operasyonel (denetim, küçük değişiklikler, formaliteler)

Sentiment yorumu yatırımcı açısından: ücret artışı negative, getiri haberi
büyüklüğüne göre, portföy raporu neutral. Önyargı katma.

Yanıt SADECE JSON. Markdown veya başka metin yok."""


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
                    "max_tokens": 600,
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
            # Extract text from response. M2.7 returns 'thinking' + 'text'
            text = ""
            for block in data.get("content", []):
                if block.get("type") == "text":
                    text = block.get("text", "")
                    break
            if not text:
                # Fallback: read 'thinking' as last-resort
                for block in data.get("content", []):
                    if block.get("type") == "thinking":
                        text = block.get("thinking", "")
                        break
            text = text.strip()
            # Strip markdown code fences if present
            text = re.sub(r"^```json\s*", "", text)
            text = re.sub(r"^```\s*", "", text)
            text = re.sub(r"\s*```$", "", text)
            # Extract JSON object from text
            m = re.search(r"\{[\s\S]*\}", text)
            if not m:
                log(f"  no JSON in response: {text[:200]}")
                return None
            try:
                return json.loads(m.group(0))
            except json.JSONDecodeError as e:
                log(f"  JSON parse error: {e}; raw: {text[:200]}")
                return None
        except Exception as e:
            log(f"  request failed (attempt {attempt + 1}): {e}")
            time.sleep(2 + attempt)
    return None


def main() -> int:
    if not MINIMAX_API_KEY:
        log("MINIMAX_API_KEY not set, exiting")
        return 1
    conn = psycopg2.connect(DB_URL)

    # Add columns if missing — idempotent
    cur = conn.cursor()
    cur.execute(
        """
        ALTER TABLE fund_announcements
          ADD COLUMN IF NOT EXISTS impact_category text[],
          ADD COLUMN IF NOT EXISTS impact_funds text[],
          ADD COLUMN IF NOT EXISTS importance text,
          ADD COLUMN IF NOT EXISTS topic text;
        """
    )
    conn.commit()

    # Pull pending rows — most recent first so the homepage updates
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute(
        """
        SELECT id, kap_oid, title, company_title, fund_type, fund_code
        FROM fund_announcements
        WHERE ai_summary IS NULL
          AND title IS NOT NULL
        ORDER BY publish_date DESC NULLS LAST
        LIMIT %s
        """,
        (BATCH_SIZE,),
    )
    rows = cur.fetchall()
    log(f"Pending announcements: {len(rows)}")
    if not rows:
        return 0

    upd_cur = conn.cursor()
    ok = 0
    err = 0
    for r in rows:
        prompt = (
            f"KAP duyurusu — kurum: {r['company_title']}, fon tipi: {r['fund_type']}, "
            f"fon kodu: {r['fund_code'] or '—'}\n\nDuyuru başlığı: {r['title']}"
        )
        result = call_minimax(prompt)
        if not result:
            err += 1
            time.sleep(1)
            continue
        # Defensive normalisation — MiniMax sometimes returns a scalar where
        # we asked for an array; coerce to TEXT[]. The LLM sometimes packs
        # multiple categories into one string ("DÖVİZ / BAF", "KMF, SRF"),
        # so split on common separators and flatten.
        def _as_list(v):
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
                    if p:
                        out.append(p)
            # dedupe, preserve order
            seen: set[str] = set()
            return [x for x in out if not (x in seen or seen.add(x))]

        try:
            upd_cur.execute(
                """
                UPDATE fund_announcements
                SET ai_summary = %s,
                    ai_sentiment = %s,
                    impact_category = %s,
                    impact_funds = %s,
                    importance = %s,
                    topic = %s
                WHERE id = %s
                """,
                (
                    result.get("summary"),
                    result.get("sentiment"),
                    _as_list(result.get("impact_category")),
                    _as_list(result.get("impact_funds")),
                    result.get("importance"),
                    result.get("topic"),
                    r["id"],
                ),
            )
            conn.commit()  # commit per row — bir satır bozulsa diğerleri devam etsin
            ok += 1
            if ok % 5 == 0:
                log(f"  committed {ok} so far")
            time.sleep(0.6)
        except Exception as e:
            log(f"  upsert failed for {r['kap_oid']}: {e}")
            conn.rollback()
            err += 1

    conn.commit()
    log(f"Done — {ok} summarised, {err} errors")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
