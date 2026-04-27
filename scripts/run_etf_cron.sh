#!/bin/bash
# ETF Daily Cron — run after US market close (weekdays only)
# Cron: 0 22 * * 1-5 cd /Users/admin/Desktop/projects/fon-app && ./scripts/run_etf_cron.sh >> /Users/admin/Desktop/projects/fon-app/logs/etf_cron.log 2>&1

SCRIPT_DIR="/Users/admin/Desktop/projects/fon-app"
VENV_PYTHON="$SCRIPT_DIR/venv/bin/python3"
LOG="$SCRIPT_DIR/logs/etf_cron.log"

# Only run on weekdays (Mon=1 ... Fri=5)
DAY=$(date +%u)
if [ "$DAY" -gt 5 ] || [ "$DAY" -lt 1 ]; then
    echo "[$(date)] Weekend — skipping ETF cron" >> "$LOG"
    exit 0
fi

echo "[$(date)] Starting ETF daily cron (weekday $DAY)" >> "$LOG"
cd "$SCRIPT_DIR"
$VENV_PYTHON scripts/etf_daily_cron.py >> "$LOG" 2>&1
echo "[$(date)] Done" >> "$LOG"
