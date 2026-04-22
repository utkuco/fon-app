#!/bin/bash
# ETF Daily Cron — run after US market close
# Cron: 0 22 * * * cd /Users/admin/Desktop/projects/fon-app && ./scripts/run_etf_cron.sh >> /Users/admin/Desktop/projects/fon-app/logs/etf_cron.log 2>&1

SCRIPT_DIR="/Users/admin/Desktop/projects/fon-app"
VENV_PYTHON="$SCRIPT_DIR/venv/bin/python3"
LOG="$SCRIPT_DIR/logs/etf_cron.log"

echo "[$(date)] Starting ETF daily cron" >> "$LOG"
cd "$SCRIPT_DIR"
$VENV_PYTHON scripts/etf_daily_cron.py >> "$LOG" 2>&1
echo "[$(date)] Done" >> "$LOG"
