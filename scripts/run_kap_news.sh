#!/bin/bash
# Haber Terminali pipeline — saatte bir çalışır.
#   KAP (Türk fonları):
#     1. Son 2 günün KAP duyurularını çeker (fund_announcements upsert)
#     2. ai_summary IS NULL olan en yeni duyuruları MiniMax ile özetler
#   ETF (küresel):
#     3. Yahoo Finance'ten anchor ETF haberlerini çeker (etf_news upsert)
#     4. ai_summary IS NULL olan haberleri MiniMax ile TR'ye çevirir/özetler
#
# MINIMAX_API_KEY ~/.hermes/.env'den okunur (özet scriptleri otomatik yükler).
# Her adım kendi exit kodunu izler; biri patlasa diğeri devam etsin diye `set -e` yok.

cd /Users/admin/Documents/Projects/fon-app

PY=/opt/homebrew/bin/python3.11
LOG=/Users/admin/Documents/Projects/fon-app/logs/kap_news.log
ERR=/Users/admin/Documents/Projects/fon-app/logs/kap_news.err

echo "[$(date '+%a %b %d %H:%M:%S %z %Y')] news pipeline başlıyor" >> "$LOG"

# ── KAP ──
$PY scripts/kap_announcements_fetcher.py 2 >> "$LOG" 2>> "$ERR"
KAP_FETCH=$?
KAP_SUMMARIZE_BATCH=25 $PY scripts/kap_summarize.py >> "$LOG" 2>> "$ERR"
KAP_SUM=$?

# ── ETF ──
$PY scripts/etf_news_fetcher.py >> "$LOG" 2>> "$ERR"
ETF_FETCH=$?
ETF_NEWS_BATCH=25 $PY scripts/etf_news_translate.py >> "$LOG" 2>> "$ERR"
ETF_SUM=$?

# ── Günün Piyasa Özeti (AI digest) ──
$PY scripts/market_digest.py >> "$LOG" 2>> "$ERR"
DIGEST=$?

echo "[$(date '+%a %b %d %H:%M:%S %z %Y')] bitti — kap(fetch=$KAP_FETCH,sum=$KAP_SUM) etf(fetch=$ETF_FETCH,sum=$ETF_SUM) digest=$DIGEST" >> "$LOG"
exit 0
