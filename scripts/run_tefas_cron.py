#!/usr/bin/env python3.11
"""TEFAS günlük fon-NAV scraper orchestrator (run_tefas_cron.sh'ın python karşılığı).

launchd, /bin/bash'e Full Disk Access gerektirmeden /opt/homebrew/bin/python3.11
(FDA'lı) ile bu dosyayı çalıştırır. Adımlar:
  1. Chrome remote-debugging (port 9222) açık mı kontrol et, değilse başlat
  2. tefas_scraper_v2.py 5000 ile tüm fonların güncel NAV'ını çek (CDP üzerinden)

fund_cascade ayrı LaunchAgent ile çalışır (getiri/benchmark cascade).
"""
import os
import subprocess
import sys
import time
import urllib.request
from datetime import datetime, timezone

PROJECT = "/Users/admin/Documents/Projects/fon-app"
PY = "/opt/homebrew/bin/python3.11"
CDP = "http://localhost:9222/json/version"


def log(msg: str) -> None:
    ts = datetime.now(timezone.utc).astimezone().strftime("%a %b %d %H:%M:%S %z %Y")
    print(f"[{ts}] {msg}", flush=True)


def chrome_up() -> bool:
    try:
        urllib.request.urlopen(CDP, timeout=3)
        return True
    except Exception:
        return False


def main() -> int:
    os.chdir(PROJECT)
    log("TEFAS scraper v2 başlatılıyor")

    if not chrome_up():
        log("Chrome debug modda başlatılıyor (port 9222)…")
        subprocess.run([
            "/usr/bin/open", "-a", "Google Chrome", "--args",
            "--remote-debugging-port=9222",
            "--user-data-dir=/tmp/chrome-debug",
        ])
        for _ in range(10):
            time.sleep(2)
            if chrome_up():
                break
        if not chrome_up():
            log("Chrome :9222 açılamadı — scraper atlanıyor")
            return 1

    rc = subprocess.run(
        [PY, "scripts/tefas_scraper_v2.py", "5000"], cwd=PROJECT
    ).returncode
    log(f"TEFAS scraper v2 {'tamamlandı' if rc == 0 else f'BAŞARISIZ (exit={rc})'}")
    return 0  # cron her zaman 0 döner; hata yukarıda loglanır


if __name__ == "__main__":
    raise SystemExit(main())
