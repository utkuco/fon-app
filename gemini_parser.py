#!/usr/bin/env python3
"""
Gemini 2.5 Flash PDF Parser - KAP Portfolio PDFs
Robust version: rate limit handling, true background, progress tracking.
"""
import os
import sqlite3
import time
import json
import re
import sys
from datetime import datetime
from pathlib import Path

import google.generativeai as genai

# === CONFIG ===
API_KEY = "AIzaSyBA1bj7TgN7qaHJB5k8S87NTX-ojYS3sAQ"
MODEL = "gemini-2.5-flash"
PDF_DIR = Path("pdfs/portfoy_dagilim")
DB_PATH = Path("db/fonapp.db")
DELAY_BETWEEN = 60      # seconds between requests (15 RPM limit, stay safe)
MAX_RETRIES = 5         # max retries per PDF on rate limit
RETRY_WAIT = 120        # seconds to wait on rate limit
REQUEST_TIMEOUT = 0     # no timeout — wait as long as Gemini needs
# ==============

genai.configure(api_key=API_KEY)

PROMPT = """Bu PDF bir KAP fon portföy dağılım tablosudur. Tablodaki TÜM varlıkları JSON array olarak çıkar.

Her varlık için:
- type: "stock", "bond", "sukuk", "gold", "derivatives", "other"
- ticker: Hisse ticker kodu (örn "AKBNK.E"). Yoksa ""
- isin: 12 karakterli ISIN (örn "TRAAKBNK91N6"). Yoksa ""
- issuer: Şirket/tahvil ihraççısı adı (örn "AKBANK T.A.Ş."). Yoksa ""
- total_value: TL değer (string, "89.083.365,00")
- weight_pct: Ağırlık % (string, "12.34")

SADECE JSON array döndür, başka hiçbir şey yazma.
[{"type":"stock","ticker":"AKBNK.E","isin":"TRAAKBNK91N6","issuer":"AKBANK T.A.Ş.","total_value":"89.083.365,00","weight_pct":"12.34"}]"""


def ensure_db_columns(conn):
    """Ensure gemini_parsed table exists."""
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS gemini_parsed (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        pdf_filename TEXT UNIQUE NOT NULL,
        fund_code TEXT NOT NULL,
        parsed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        success INTEGER DEFAULT 0,
        error TEXT,
        holdings_json TEXT,
        holdings_count INTEGER DEFAULT 0,
        total_weight REAL DEFAULT 0
    )""")
    conn.commit()


def parse_gemini_json(text):
    """Extract JSON array from Gemini response."""
    start = text.find('[')
    end = text.rfind(']') + 1
    if start >= 0 and end > start:
        try:
            return json.loads(text[start:end])
        except json.JSONDecodeError:
            pass
    # Try cleaning markdown
    cleaned = re.sub(r'```json\s*', '', text)
    cleaned = re.sub(r'```\s*', '', cleaned)
    start = cleaned.find('[')
    end = cleaned.rfind(']') + 1
    if start >= 0 and end > start:
        try:
            return json.loads(cleaned[start:end])
        except json.JSONDecodeError:
            pass
    return None


def notify(title, msg):
    """Send macOS desktop notification."""
    import subprocess
    script = f'display notification "{msg}" with title "{title}"'
    subprocess.run(['osascript', '-e', script], capture_output=True)


def parse_one_pdf(pdf_path, attempt=1):
    """Parse a single PDF with Gemini. Returns (holdings, error)."""
    model = genai.GenerativeModel(MODEL)

    try:
        # Upload PDF
        pdf_file = genai.upload_file(str(pdf_path))

        # Generate with timeout
        response = model.generate_content(
            [pdf_file, PROMPT],
            generation_config=genai.GenerationConfig(
                response_mime_type="application/json",
                temperature=0.1
            ),
            request_options={"timeout": REQUEST_TIMEOUT}
        )

        # Cleanup upload
        try:
            genai.delete_file(pdf_file.name)
        except:
            pass

        raw = response.text.strip()
        if not raw:
            return None, "Empty response from Gemini"

        holdings = parse_gemini_json(raw)
        if holdings is None:
            return None, f"JSON parse failed. Raw: {raw[:150]}"

        return holdings, None

    except Exception as e:
        err = str(e)

        # Cleanup on error
        try:
            genai.delete_file(pdf_file.name)
        except:
            pass

        # Rate limit
        if "429" in err or "RESOURCE_EXHAUSTED" in err or "quota" in err.lower():
            return None, "RATE_LIMITED"

        # thinking_budget error (SDK/API mismatch - don't retry)
        if "thinking_budget" in err:
            return None, "THINKING_BUDGET_ERROR"

        # Timeout
        if "504" in err or "timeout" in err.lower() or "deadline" in err.lower():
            return None, "TIMEOUT"

        # Other error
        return None, err[:200]


def main():
    conn = sqlite3.connect(str(DB_PATH))
    ensure_db_columns(conn)
    c = conn.cursor()

    # Get already done
    c.execute("SELECT pdf_filename FROM gemini_parsed WHERE success=1")
    done = set(row[0] for row in c.fetchall())

    # Get all PDFs
    all_pdfs = sorted([f for f in os.listdir(PDF_DIR) if f.endswith('.pdf')])
    todo = [f for f in all_pdfs if f not in done]

    print(f"{'='*60}")
    print(f"Gemini 2.5 Flash PDF Parser (Robust)")
    print(f"{'='*60}")
    print(f"Total PDFs:     {len(all_pdfs)}")
    print(f"Already done:   {len(done)}")
    print(f"To process:     {len(todo)}")
    print(f"Delay:          {DELAY_BETWEEN}s between requests")
    print(f"Rate limit wait: {RETRY_WAIT}s (fixed)")
    print(f"Timeout:        {REQUEST_TIMEOUT}s per request")
    print(f"{'='*60}\n", flush=True)

    if not todo:
        print("Nothing to do! All PDFs processed.")
        conn.close()
        return

    stats = {"success": 0, "failed": 0, "rate_limited": 0, "timeout_retries": 0}
    start_time = time.time()

    for i, pdf_file in enumerate(todo):
        pdf_path = PDF_DIR / pdf_file
        fund_code = pdf_file.split('_')[0]

        print(f"[{i+1}/{len(todo)}] {fund_code} ({pdf_file})", end=" ", flush=True)

        # Retry loop for this PDF
        holdings = None
        error = None

        for retry in range(MAX_RETRIES):
            holdings, error = parse_one_pdf(pdf_path, retry + 1)

            if error is None:
                # Success!
                break

            elif error == "RATE_LIMITED":
                stats["rate_limited"] += 1
                print(f"\n  ⏳ Rate limited (retry {retry+1}/{MAX_RETRIES}). Waiting {RETRY_WAIT}s...", flush=True)
                notify("FonRapor Gemini", f"⚠️ Rate limited — {RETRY_WAIT}sn bekleniyor ({retry+1}/{MAX_RETRIES})")
                time.sleep(RETRY_WAIT)
                continue

            elif error == "THINKING_BUDGET_ERROR":
                # SDK/API mismatch - don't retry, just fail
                stats["failed"] += 1
                print(f"\n  ❌ thinking_budget error — skipping (retry {retry+1}/{MAX_RETRIES})", flush=True)
                notify("FonRapor Gemini", f"HATA: thinking_budget — {fund_code} atlanıyor")
                break

            elif error == "TIMEOUT":
                stats["timeout_retries"] += 1
                print(f"\n  ⏳ Timeout (retry {retry+1}/{MAX_RETRIES}). Retrying...", flush=True)
                notify("FonRapor Gemini", f"⏳ Timeout: {fund_code} — yeniden deneniyor ({retry+1}/{MAX_RETRIES})")
                time.sleep(60)
                continue

            else:
                # Real error - don't retry this PDF
                notify("FonRapor Gemini", f"❌ HATA: {fund_code} — {error[:60]}")
                break

        # Record result
        if error is None and holdings is not None and len(holdings) > 0:
            total_weight = 0
            for h in holdings:
                try:
                    w = h.get('weight_pct', '0').replace('%', '').replace(',', '.')
                    total_weight += float(w)
                except:
                    pass

            holdings_json = json.dumps(holdings, ensure_ascii=False)
            c.execute("""INSERT OR REPLACE INTO gemini_parsed
                (pdf_filename, fund_code, success, holdings_json, holdings_count, total_weight)
                VALUES (?,?,1,?,?,?)""",
                (pdf_file, fund_code, holdings_json, len(holdings), total_weight))
            conn.commit()

            stats["success"] += 1
            elapsed = time.time() - start_time
            rate = (i+1) / (elapsed / 3600) if elapsed > 0 else 0
            print(f"✅ {len(holdings)} holdings ({total_weight:.1f}%) | {rate:.1f} PDF/hr | {stats['rate_limited']} rate limits", flush=True)

            # Notify every 10 successes
            if stats["success"] % 10 == 0:
                notify("FonRapor Gemini", f"🎉 {stats['success']} PDF tamamlandı! {len(todo) - i - 1} kaldı.")

        elif error is None and holdings is not None and len(holdings) == 0:
            c.execute("""INSERT OR REPLACE INTO gemini_parsed
                (pdf_filename, fund_code, success, holdings_json, holdings_count, total_weight)
                VALUES (?,?,1,'[]',0,0)""",
                (pdf_file, fund_code))
            conn.commit()
            stats["success"] += 1
            print(f"📭 No holdings (empty fund)", flush=True)

        else:
            stats["failed"] += 1
            c.execute("""INSERT OR REPLACE INTO gemini_parsed
                (pdf_filename, fund_code, success, error)
                VALUES (?,?,0,?)""",
                (pdf_file, fund_code, error[:500] if error else "Unknown"))
            conn.commit()
            print(f"❌ {error[:80] if error else 'Unknown error'}", flush=True)

        # Delay between PDFs
        if i < len(todo) - 1:
            time.sleep(DELAY_BETWEEN)

    # Summary
    elapsed = total_time = time.time() - start_time
    c.execute("SELECT COUNT(*) FROM gemini_parsed WHERE success=1")
    total_done = c.fetchone()[0]
    c.execute("SELECT SUM(holdings_count) FROM gemini_parsed WHERE success=1")
    total_holdings = c.fetchone()[0] or 0

    notify("FonRapor Gemini", f"🎉 TÜM {stats['success']} PDF tamamlandı! {stats['failed']} hata, {stats['rate_limited']} rate limit.")
    print(f"\n{'='*60}")
    print(f"DONE in {elapsed/60:.1f} minutes!")
    print(f"  Success:   {stats['success']}")
    print(f"  Failed:    {stats['failed']}")
    print(f"  Rate limited (recovered): {stats['rate_limited']}")
    print(f"  Timeouts:  {stats['timeout_retries']}")
    print(f"  Total in DB: {total_done} PDFs, {total_holdings} holdings")
    print(f"  Average speed: {stats['success'] / (elapsed/3600):.1f} PDF/hr")
    print(f"{'='*60}")

    conn.close()


if __name__ == "__main__":
    main()
