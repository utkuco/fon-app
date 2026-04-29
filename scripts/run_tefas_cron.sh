#!/bin/bash
# TEFAS Fund Daily Scraper v2 — CDP tabanlı (Chrome Remote Debugging)
# Her iş günü saat 10:00'da (TR) çalışır
# Chrome remote debugging port 9222 üzerinden TEFAS'tan fon verilerini çeker

set -e

cd /Users/admin/Desktop/projects/fon-app

# Ortam değişkenleri
export SUPABASE_SERVICE_KEY="sb_secret_PkAEAOU2YO4YS-ELYpwS5w_SsVg2kqi"

LOG="/Users/admin/Desktop/projects/fon-app/logs/tefas_cron.log"
ERR="/Users/admin/Desktop/projects/fon-app/logs/tefas_cron.err"

echo "[$(date '+%a %b %d %H:%M:%S %z %Y')] TEFAS scraper v2 başlatılıyor" >> "$LOG"

# Chrome çalışıyor mu kontrol et, yoksa başlat
if ! curl -s --max-time 3 http://localhost:9222/json/version > /dev/null 2>&1; then
    echo "[$(date)] Chrome debug modda başlatılıyor..." >> "$LOG"
    open -a "Google Chrome" --args --remote-debugging-port=9222 --user-data-dir=/tmp/chrome-debug
    sleep 5
fi

# 1000 fon = tüm fonlar
/opt/homebrew/bin/python3.11 scripts/tefas_scraper_v2.py 1000 >> "$LOG" 2>> "$ERR"
SCRAPER_EXIT=$?

if [ $SCRAPER_EXIT -eq 0 ]; then
    echo "[$(date '+%a %b %d %H:%M:%S %z %Y')] TEFAS scraper v2 tamamlandi — cascade tetikleniyor" >> "$LOG"

    # Cascade: Vercel /api/tefas-cascade cron'u otomatik 15:00 UTC'de çalışır
    # ama scraper başarılıysa hemen şimdi tetikleyelim (site erken güncellenir)
    cd /Users/admin/Desktop/projects/fon-app/web
    CASCADE_URL="https://web-brmfvldc6.vercel.app/api/tefas-cascade"
    CASCADE_RESP=$(curl -s -o /dev/null -w "%{http_code}" \
        -H "x-vercel-cron: true" \
        "$CASCADE_URL" 2>> "$ERR" || echo "000")
    echo "[$(date '+%a %b %d %H:%M:%S %z %Y')] Cascade HTTP $CASCADE_RESP" >> "$LOG"
else
    echo "[$(date '+%a %b %d %H:%M:%S %z %Y')] TEFAS scraper v2 BASARISIZ (exit=$SCRAPER_EXIT)" >> "$LOG"
fi

exit 0
