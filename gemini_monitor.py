#!/usr/bin/env python3
"""
Gemini PDF Parser Monitor
Cron: her saat calisir
- Son parse zamanini kontrol et
- Son 1 saatte islem yoksa uyar
- Rate limit / timeout hatasi coklaysa uyar
- Error varsa bildir
"""
import sqlite3
import time
import sys
import os
from datetime import datetime, timedelta
from pathlib import Path

DB_PATH = Path("db/fonapp.db")
WEBHOOK_URL = None  # Set Slack/Discord webhook URL here

def get_status():
    conn = sqlite3.connect(str(DB_PATH))
    c = conn.cursor()

    # Son parse zamani
    c.execute("SELECT parsed_at FROM gemini_parsed ORDER BY id DESC LIMIT 1")
    row = c.fetchone()
    last_parse = row[0] if row else None

    # Toplam basari
    c.execute("SELECT COUNT(*) FROM gemini_parsed WHERE success=1")
    total_ok = c.fetchone()[0]

    # Toplam basarisiz
    c.execute("SELECT COUNT(*) FROM gemini_parsed WHERE success=0")
    total_fail = c.fetchone()[0]

    # Toplam PDF sayisi
    pdf_dir = Path("pdfs/portfoy_dagilim")
    total_pdfs = len(list(pdf_dir.glob("*.pdf"))) if pdf_dir.exists() else 0

    # Son basarisiz parse
    c.execute("SELECT pdf_filename, error, parsed_at FROM gemini_parsed WHERE success=0 ORDER BY id DESC LIMIT 3")
    recent_fails = c.fetchall()

    # Son basarisiz zaman
    last_fail_time = recent_fails[0][2] if recent_fails else None

    conn.close()
    return {
        "last_parse": last_parse,
        "total_ok": total_ok,
        "total_fail": total_fail,
        "total_pdfs": total_pdfs,
        "recent_fails": recent_fails,
        "last_fail_time": last_fail_time,
    }


def parse_time(ts):
    if ts is None:
        return None
    try:
        return datetime.strptime(ts, "%Y-%m-%d %H:%M:%S")
    except:
        return None


def send_alert(message: str, color: str = "warning"):
    """Send alert via webhook or print to stdout."""
    print(f"[ALERT] {message}", flush=True)

    if not WEBHOOK_URL:
        # Fallback: print to stderr for cron capture
        print(f"[ALERT] {message}", file=sys.stderr)
        return

    # Slack webhook
    try:
        import urllib.request
        import json
        payload = {
            "text": message,
            "attachments": [{"color": color, "text": message}]
        }
        req = urllib.request.Request(
            WEBHOOK_URL,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=10):
            pass
    except Exception as e:
        print(f"Webhook gonderilemedi: {e}", file=sys.stderr)


def main():
    s = get_status()

    now = datetime.now()
    last = parse_time(s["last_parse"])

    messages = []

    # 1) Son 1 saatte islem yoksa uyar
    if last is None:
        messages.append(("Parselenmemis PDF var! Henuz hic islem yapilmamis.", "danger"))
    else:
        diff_min = (now - last).total_seconds() / 60
        if diff_min > 60:
            messages.append((f"⚠️ Son 1 saatte islem yok! Son parse: {s['last_parse']} ({diff_min:.0f} dakika once)", "warning"))

    # 2) Son parse >2 saat once ve hata varsa
    if s["last_fail_time"]:
        fail_diff = (now - parse_time(s["last_fail_time"])).total_seconds() / 3600
        if fail_diff < 2 and s["total_fail"] > 0:
            err_summary = s["recent_fails"][0][1][:60] if s["recent_fails"] else "?"
            messages.append((f"❌ Son basarisiz: {s['recent_fails'][0][0]} — {err_summary}", "danger"))

    # 3) Basarisiz oranı %20'den fazlaysa
    total = s["total_ok"] + s["total_fail"]
    if total > 0 and (s["total_fail"] / total) > 0.2:
        pct = (s["total_fail"] / total) * 100
        messages.append((f"⚠️ Basarisiz oranı %{pct:.0f} — {s['total_fail']}/{total} PDF basarisiz", "warning"))

    # 4) Basari durumu
    progress = f"✅ {s['total_ok']}/{s['total_pdfs']} PDF parse edildi"
    if s["last_parse"]:
        progress += f" | Son islem: {s['last_parse']}"
    print(progress, flush=True)

    for msg, _ in messages:
        send_alert(msg)

    if not messages:
        print("✅ Monitor: Sorun yok, her sey yolunda.", flush=True)


if __name__ == "__main__":
    main()
