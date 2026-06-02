#!/usr/bin/env python3.11
"""Günlük blog üretici — MiniMax ile fonrapor.com/blog için özgün TR yazı.

Her gün çalışır:
  1. Mevcut blog başlıklarını/slug'larını çeker (tekrar etmemek için)
  2. MiniMax'a "bunlardan farklı yeni bir konu seç ve yaz" der → HTML içerik
  3. `blogs` tablosuna insert eder (is_published=true)

İçerik HTML (<p>,<h2>,<ul>) — /blog/[slug] prose ile dangerouslySetInnerHTML.
AI: MiniMax-M2.7 (Anthropic-uyumlu), key ~/.hermes/.env veya web/.env.
"""
import os
import re
import sys
import json
import time
import unicodedata
import urllib.request
from datetime import datetime, timezone

PROJECT = "/Users/admin/Documents/Projects/fon-app"
MINIMAX_URL = "https://api.minimax.io/anthropic/v1/messages"
MINIMAX_MODEL = "MiniMax-M2.7"


def log(msg: str) -> None:
    ts = datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


def load_env() -> None:
    for p in [f"{PROJECT}/web/.env", os.path.expanduser("~/.hermes/.env")]:
        try:
            with open(p) as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, _, v = line.partition("=")
                        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
        except FileNotFoundError:
            pass


def rest(path: str, method: str = "GET", payload=None):
    url = f"{os.environ['NEXT_PUBLIC_SUPABASE_URL'].rstrip('/')}/rest/v1/{path}"
    key = os.environ["SUPABASE_SERVICE_KEY"]
    headers = {
        "apikey": key, "Authorization": f"Bearer {key}",
        "content-type": "application/json", "Prefer": "return=representation",
    }
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    with urllib.request.urlopen(req, timeout=30) as r:
        body = r.read()
        return json.loads(body) if body else None


def slugify(title: str) -> str:
    t = unicodedata.normalize("NFKD", title)
    t = t.replace("ı", "i").replace("İ", "i").replace("ş", "s").replace("ğ", "g")
    t = t.replace("ü", "u").replace("ö", "o").replace("ç", "c")
    t = t.encode("ascii", "ignore").decode().lower()
    t = re.sub(r"[^a-z0-9]+", "-", t).strip("-")
    return t[:80] or "yazi"


def call_minimax(system: str, user: str, retries: int = 3):
    key = os.environ.get("MINIMAX_API_KEY", "")
    if not key:
        log("MINIMAX_API_KEY yok"); return None
    payload = json.dumps({
        "model": MINIMAX_MODEL, "max_tokens": 4000,
        "system": system, "messages": [{"role": "user", "content": user}],
    }).encode()
    for attempt in range(retries):
        try:
            req = urllib.request.Request(MINIMAX_URL, data=payload, method="POST", headers={
                "x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json",
            })
            with urllib.request.urlopen(req, timeout=120) as r:
                data = json.loads(r.read())
            raw = ""
            for block in data.get("content", []):
                if block.get("type") == "text":
                    raw = block.get("text", ""); break
            raw = re.sub(r"^```(?:json)?\s*", "", (raw or "").strip())
            raw = re.sub(r"\s*```$", "", raw)
            m = re.search(r"\{[\s\S]*\}", raw)
            return json.loads(m.group(0)) if m else None
        except Exception as e:
            log(f"MiniMax hata (deneme {attempt + 1}): {e}")
            time.sleep(3 + attempt * 2)
    return None


SYSTEM = (
    "Sen FonRapor'un (fonrapor.com — Türk yatırım fonu ve ETF analiz platformu) "
    "blog yazarısın. Türk bireysel yatırımcılara yönelik, özgün, bilgilendirici, "
    "SEO uyumlu yazılar yazarsın. Yatırım tavsiyesi VERMEZSİN; eğitici ve tarafsızsın. "
    "Çıktıyı SADECE şu JSON formatında ver (başka metin yok):\n"
    '{"title":"...","excerpt":"1-2 cümle özet","category":"egitim|karsilastirma|analiz|genel",'
    '"content":"<p>...</p><h2>...</h2><p>...</p>"}\n'
    "content alanı geçerli HTML olmalı (yalnız <p>,<h2>,<h3>,<ul>,<li>,<strong> etiketleri; "
    "başlık <h1> KULLANMA). 600-900 kelime. Türkçe. Somut, güncel ve okunabilir."
)


def main() -> int:
    load_env()
    if not os.environ.get("NEXT_PUBLIC_SUPABASE_URL"):
        log("Supabase env yok — çıkılıyor"); return 1

    existing = rest("blogs?select=title,slug&limit=100") or []
    titles = [b["title"] for b in existing]
    slugs = {b["slug"] for b in existing}
    log(f"mevcut {len(titles)} yazı — yeni konu üretiliyor")

    user = (
        "Aşağıdaki başlıklar SİTEDE ZATEN VAR. Bunlardan farklı, yeni ve değerli "
        "bir konu seç ve tam bir blog yazısı yaz (fon, ETF, TEFAS, risk, portföy, "
        "vergi, tasarruf, piyasa kavramları gibi). Tekrarlama.\n\nMevcut başlıklar:\n"
        + "\n".join(f"- {t}" for t in titles)
    )
    post = call_minimax(SYSTEM, user)
    if not post or not post.get("title") or not post.get("content"):
        log("MiniMax geçerli yazı döndürmedi — bugün atlanıyor (yarın tekrar denenir)")
        return 0  # cron 0 döner; ertesi gün yeni deneme

    title = post["title"].strip()
    slug = slugify(post.get("slug") or title)
    if slug in slugs:
        slug = f"{slug}-{datetime.now(timezone.utc).strftime('%Y%m%d')}"
    cat = post.get("category", "genel")
    if cat not in ("egitim", "karsilastirma", "analiz", "genel"):
        cat = "genel"

    row = {
        "title": title,
        "slug": slug,
        "excerpt": (post.get("excerpt") or "").strip()[:300],
        "content": post["content"],
        "author_name": "FonRapor",
        "category": cat,
        "is_published": True,
        "published_at": datetime.now(timezone.utc).isoformat(),
    }
    try:
        rest("blogs", "POST", row)
        log(f"✓ yayımlandı: {title}  (/blog/{slug}, {cat})")
    except Exception as e:
        log(f"insert hatası: {e}")
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
