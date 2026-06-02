#!/usr/bin/env python3.11
"""Haber Terminali pipeline — saatte bir çalışır (run_kap_news.sh'ın python karşılığı).

Bash wrapper yerine python orchestrator: launchd, /bin/bash'e Full Disk Access
gerektirmeden /opt/homebrew/bin/python3.11 (FDA'lı) ile bu dosyayı çalıştırır.
Her adım bağımsız — biri patlasa diğeri devam eder (set -e yok davranışı).

Adımlar:
  1. kap_announcements_fetcher.py 2   — son 2 günün KAP duyuruları
  2. kap_summarize.py                 — MiniMax AI özet (KAP_SUMMARIZE_BATCH=25)
  3. etf_news_fetcher.py              — Yahoo Finance anchor ETF haberleri
  4. etf_news_translate.py            — TR çeviri/özet (ETF_NEWS_BATCH=25)
  5. market_digest.py                 — Günün Piyasa Özeti (AI digest)
"""
import os
import subprocess
import sys
from datetime import datetime, timezone

PROJECT = "/Users/admin/Documents/Projects/fon-app"
PY = "/opt/homebrew/bin/python3.11"

STEPS = [
    ("kap_fetch", ["scripts/kap_announcements_fetcher.py", "2"], {}),
    ("kap_sum", ["scripts/kap_summarize.py"], {"KAP_SUMMARIZE_BATCH": "25"}),
    ("etf_fetch", ["scripts/etf_news_fetcher.py"], {}),
    ("etf_sum", ["scripts/etf_news_translate.py"], {"ETF_NEWS_BATCH": "25"}),
    ("digest", ["scripts/market_digest.py"], {}),
]


def main() -> int:
    os.chdir(PROJECT)
    ts = datetime.now(timezone.utc).astimezone().strftime("%a %b %d %H:%M:%S %z %Y")
    print(f"[{ts}] news pipeline başlıyor", flush=True)

    results = {}
    for name, args, extra_env in STEPS:
        env = {**os.environ, **extra_env}
        try:
            rc = subprocess.run([PY, *args], cwd=PROJECT, env=env).returncode
        except Exception as e:  # noqa: BLE001 — bir adım patlasa diğeri devam etsin
            print(f"[{name}] EXC {e}", file=sys.stderr, flush=True)
            rc = -1
        results[name] = rc

    ts = datetime.now(timezone.utc).astimezone().strftime("%a %b %d %H:%M:%S %z %Y")
    summary = " ".join(f"{k}={v}" for k, v in results.items())
    print(f"[{ts}] bitti — {summary}", flush=True)
    return 0  # pipeline her zaman 0 döner (adım hataları yukarıda raporlanır)


if __name__ == "__main__":
    raise SystemExit(main())
