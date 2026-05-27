#!/bin/bash
# Weekly KAP fund_holdings refresh. The KAP PDF download + parse loop takes
# 30-45 minutes for ~2400 funds, so this runs at 04:00 Sunday when nothing
# else competes for the DB or the Mac.
#
# Known issue: the PDF parser leaves fund_holdings.ticker = "" because it
# splits the table column on whitespace and the BIST ticker ends up as the
# first word of `company`. fund_cascade.most_held_stocks recovers the
# ticker from the ISIN; until the parser is rewritten that workaround is
# the source of truth for the widget.
set -euo pipefail

PROJECT_ROOT="/Users/admin/Documents/Projects/fon-app"
LOG_DIR="$PROJECT_ROOT/logs"
mkdir -p "$LOG_DIR"
TS=$(date +%Y-%m-%d_%H-%M)
LOG="$LOG_DIR/holdings-refresh-$TS.log"

cd "$PROJECT_ROOT"
echo "[refresh_holdings] start $(date -u +%FT%TZ)" | tee -a "$LOG"
/opt/homebrew/bin/python3.11 scraper.py full data/fund_holdings.json >> "$LOG" 2>&1 || true
# Snapshot uses the in-tree exporter from the worktree branch where it was
# last touched — keep the working version next to the scraper instead of
# branching deps.
if [ -f .claude/worktrees/magical-darwin-87cdd4/export_holdings_to_supabase.py ]; then
    /opt/homebrew/bin/python3.11 .claude/worktrees/magical-darwin-87cdd4/export_holdings_to_supabase.py >> "$LOG" 2>&1 || true
fi
echo "[refresh_holdings] end   $(date -u +%FT%TZ)" | tee -a "$LOG"
