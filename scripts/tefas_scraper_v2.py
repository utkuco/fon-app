#!/usr/bin/env python3
"""
TEFAS Fund Data Scraper v2 — Chrome Remote Debugging + REST API.
Uses CDP (Chrome DevTools Protocol) via websockets for browser control.

Data sources:
  1. GET  /api/funds/fonFiyatBilgiGetir  → periyod=60 → 5Y daily price history
  2. TEXT document.body.innerText         → Son Fiyat, Günlük Getiri, Kategori, ISIN, etc.
  3. GET  /api/funds/fonProfilDtyGetir   → kategori derecesi, benchmark karşılaştırması

Usage:
    python3 scripts/tefas_scraper_v2.py [max_funds]
"""

from __future__ import annotations
import os
import sys
import json
import time
import re
import signal
import warnings
import requests
from datetime import date, datetime, timedelta
from typing import Optional, Dict, List, Any
from bs4 import BeautifulSoup
from websockets.sync import client
import subprocess

warnings.filterwarnings('ignore')


class FundScrapeTimeout(Exception):
    """Per-fund hard deadline tripped — usually CDP socket got wedged."""


def _alarm_handler(signum, frame):  # noqa: ARG001
    raise FundScrapeTimeout("scrape_fund exceeded hard timeout")


# Hard per-fund deadline. scrape_fund makes 3 CDP calls each with a 15s
# inner timeout, plus a 3s page-settle sleep, so the natural ceiling is
# ~50s. Anything past 90s means the CDP websocket is wedged — bail out
# before the whole batch stalls (see GHI hang on 2026-05-07 + 2026-05-26).
PER_FUND_DEADLINE_SECS = 90

SUPABASE_URL = "https://oqkobptbvcazifpvjwfz.supabase.co"
SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "sb_secret_PkAEAOU2YO4YS-ELYpwS5w_SsVg2kqi")
HEADERS = {
    "apikey": SERVICE_KEY,
    "Authorization": f"Bearer {SERVICE_KEY}",
    "Content-Type": "application/json",
}

MAX_FUNDS = int(sys.argv[1]) if len(sys.argv) > 1 else 1000
CHROME_PORT = 9222

# ─── CDP Helpers ──────────────────────────────────────────────────────────────

def get_chrome_tab() -> tuple[Any, int]:
    """Create a new Chrome tab via CDP HTTP and return (ws_url, page_id)."""
    try:
        result = subprocess.run(
            ['curl', '-s', '-X', 'PUT', f'http://localhost:{CHROME_PORT}/json/new'],
            capture_output=True, text=True, timeout=5
        )
        data = json.loads(result.stdout)
        return data["webSocketDebuggerUrl"], data["id"]
    except Exception as e:
        print(f"[CDP ERROR] Failed to create tab: {e}")
        return None, None


def cdp_connect(ws_url: str) -> tuple[Any, callable, callable]:
    """Connect to CDP WebSocket and return (ws, send_fn, eval_fn)."""
    ws = client.connect(ws_url, max_size=20*1024*1024)
    msg_id = [0]

    def next_id():
        msg_id[0] += 1
        return msg_id[0]

    def cdp_send(method: str, params: Optional[Dict] = None, timeout: float = 30) -> Optional[Dict]:
        payload = {"id": next_id(), "method": method, "params": params or {}}
        ws.send(json.dumps(payload))
        start = time.time()
        while time.time() - start < timeout:
            raw = ws.recv(timeout=timeout)
            resp = json.loads(raw)
            if resp.get("id") == payload["id"]:
                return resp
        return None

    def cdp_eval(expr: str, timeout: float = 30) -> Any:
        resp = cdp_send("Runtime.evaluate", {"expression": expr, "returnByValue": True}, timeout)
        if resp and "result" in resp:
            return resp["result"].get("result", {}).get("value")
        return None

    # Enable domains
    cdp_send("Page.enable")
    cdp_send("Runtime.enable")

    return ws, cdp_send, cdp_eval


# ─── TEFAS API Fetchers ───────────────────────────────────────────────────────

def fetch_price_history(cdp_eval, code: str, periyod: int = 60) -> List[Dict]:
    """Fetch price history from TEFAS API via CDP XHR (cookies + headers available)."""
    script = f"""
    (function() {{
        var xhr = new XMLHttpRequest();
        xhr.open('POST', 'https://www.tefas.gov.tr/api/funds/fonFiyatBilgiGetir', false);
        xhr.setRequestHeader('Content-Type', 'application/json');
        xhr.send(JSON.stringify({{"fonKodu":"{code}","dil":"TR","periyod":{periyod}}}));
        if (xhr.status === 200) {{
            var data = JSON.parse(xhr.responseText);
            var list = data.resultList || [];
            return list.map(function(item) {{ return {{ date: item.tarih, price: item.fiyat }}; }});
        }}
        return null;
    }})()
    """
    result = cdp_eval(script, timeout=15)
    if not result:
        return []
    return result


def fetch_current_price(cdp_eval, code: str) -> Optional[Dict]:
    """Fetch current price info from TEFAS API via CDP XHR."""
    script = f"""
    (function() {{
        var xhr = new XMLHttpRequest();
        xhr.open('POST', 'https://www.tefas.gov.tr/api/funds/fonFiyatBilgiGetir', false);
        xhr.setRequestHeader('Content-Type', 'application/json');
        xhr.send(JSON.stringify({{"fonKodu":"{code}","dil":"TR","periyod":12}}));
        if (xhr.status === 200) {{
            var data = JSON.parse(xhr.responseText);
            var list = data.resultList || [];
            if (list.length > 0) {{
                var latest = list[list.length - 1];
                var prev = list.length > 1 ? list[list.length - 2] : null;
                return {{
                    tarih: latest.tarih,
                    fiyat: latest.fiyat,
                    prev_date: prev ? prev.tarih : null,
                    prev_price: prev ? prev.fiyat : null
                }};
            }}
        }}
        return null;
    }})()
    """
    return cdp_eval(script, timeout=15)


def fetch_profile(cdp_eval, code: str) -> Optional[Dict]:
    """Fetch fund profile + benchmark comparison from TEFAS API via CDP XHR."""
    script = f"""
    (function() {{
        var xhr = new XMLHttpRequest();
        xhr.open('POST', 'https://www.tefas.gov.tr/api/funds/fonProfilDtyGetir', false);
        xhr.setRequestHeader('Content-Type', 'application/json');
        xhr.send(JSON.stringify({{"dil":"TR","fonKodu":"{code}","periyod":"12"}}));
        if (xhr.status === 200) {{
            var data = JSON.parse(xhr.responseText);
            return data.resultList || [];
        }}
        return null;
    }})()
    """
    result = cdp_eval(script, timeout=15)
    if not result or not isinstance(result, list):
        return {}
    # result is list of benchmark comparisons: {fonKodu, fonUnvan, fonTuru, fonTurGetiri}
    profile = {}
    for item in result:
        tur = item.get("fonTuru", "")
        profile[tur] = {
            "unvan": item.get("fonUnvan", ""),
            "getiri": item.get("fonTurGetiri"),
        }
    return profile


# ─── Body Text Parsing ────────────────────────────────────────────────────────

def parse_body_text(body_text: str) -> Dict:
    """Parse fund data from rendered page body text."""
    d = {}
    text = body_text

    # Son Fiyat (TL)
    m = re.search(r'Son Fiyat\s*\(TL\)\s*\n?\s*([\d.,]+)', text)
    if m:
        d['price'] = float(m.group(1).replace('.', '').replace(',', '.'))

    # Günlük Getiri (%)
    m = re.search(r'Günlük Getiri\s*\(%\)\s*\n?\s*%([-\d.,]+)', text)
    if m:
        d['daily_change'] = float(m.group(1).replace('.', '').replace(',', '.'))

    # Return periods
    for label, key in [
        ('Son 1 Ay Getirisi', 'one_month'),
        ('Son 3 Ay Getirisi', 'three_month'),
        ('Son 6 Ay Getirisi', 'six_month'),
        ('Son 1 Yıl Getirisi', 'one_year'),
        ('Son 3 Yıl Getirisi', 'three_year'),
        ('Son 5 Yıl Getirisi', 'five_year'),
    ]:
        m = re.search(rf'{re.escape(label)}\s*\n?\s*%([-\d.,]+)', text)
        if m:
            d[key] = float(m.group(1).replace('.', '').replace(',', '.'))

    # Toplam Değer
    m = re.search(r'Fon Toplam Değer\s*\(TL\)\s*\n?\s*([\d.,]+)', text)
    if m:
        d['toplam_deger'] = float(m.group(1).replace('.', '').replace(',', '.'))

    # Kategori
    m = re.search(r'Kategorisi\s*\n?\s*(.+?)(?:\n|$)', text)
    if m:
        d['kategori'] = m.group(1).strip()

    # ISIN Kodu
    m = re.search(r'ISIN Kodu\s*\n?\s*([A-Z0-9]{10,12})', text)
    if m:
        d['isin'] = m.group(1).strip()

    # Yatırımcı Sayısı
    m = re.search(r'Yatırımcı Sayısı\s*\n?\s*([\d.,]+)', text)
    if m:
        d['yatirimci_sayisi'] = int(m.group(1).replace('.', '').replace(',', ''))

    # Pazar Payı
    m = re.search(r'Pazar Payı\s*\n?\s*%?([\d.,]+)', text)
    if m:
        d['pazar_payi'] = float(m.group(1).replace('.', '').replace(',', '.'))

    # Fon Kodu
    m = re.search(r'Fon Kodu\s*\n?\s*([A-Z0-9]+)', text)
    if m:
        d['code'] = m.group(1).strip()

    return d


# ─── Price History Processing ─────────────────────────────────────────────────

def build_price_history(price_rows: List[Dict]) -> List[Dict]:
    """Convert API price rows [{date, price}] into DB format [{date, price, change}]."""
    if not price_rows:
        return []
    sorted_rows = sorted(price_rows, key=lambda x: x["date"])
    result = []
    for i, row in enumerate(sorted_rows):
        change = None
        if i > 0:
            prev = sorted_rows[i - 1]["price"]
            curr = row["price"]
            if prev and prev != 0:
                change = round((curr - prev) / prev * 100, 4)
        result.append({
            "date": row["date"],
            "price": row["price"],
            "change": change
        })
    return result


def compute_returns(price_rows: List[Dict]) -> Dict:
    """Compute weekly/monthly/quarterly/semi-annual/annual returns from price rows."""
    if not price_rows:
        return {}
    today = date.today()
    price_map = {r["date"]: r["price"] for r in price_rows}

    def pct(days_ago):
        target = (today - timedelta(days=days_ago)).isoformat()
        latest_date = max(price_map.keys())
        latest_price = price_map.get(latest_date)
        past_price = price_map.get(target)
        if not latest_price or not past_price or past_price == 0:
            return None
        return round((latest_price - past_price) / past_price * 100, 2)

    return {
        "daily": compute_daily_change(price_rows),
        "weekly": pct(7),
        "one_month": pct(30),
        "three_month": pct(90),
        "six_month": pct(180),
        "one_year": pct(365),
    }


def compute_daily_change(price_rows: List[Dict]) -> Optional[float]:
    """Compute daily % change from latest two price entries."""
    if len(price_rows) < 2:
        return None
    sorted_rows = sorted(price_rows, key=lambda x: x["date"], reverse=True)
    latest = sorted_rows[0]["price"]
    prev = sorted_rows[1]["price"]
    if not latest or not prev or prev == 0:
        return None
    return round((latest - prev) / prev * 100, 2)


def merge_price_history(existing: List[Dict], new: List[Dict]) -> List[Dict]:
    """Merge new prices into existing, existing takes priority for same date."""
    if not existing:
        return new
    if not new:
        return existing
    merged = {e["date"]: e for e in existing}
    for entry in new:
        merged[entry["date"]] = entry
    return sorted(merged.values(), key=lambda x: x["date"])


# ─── Supabase ────────────────────────────────────────────────────────────────

def upsert_funds(rows: List[Dict]) -> int:
    """Upsert fund rows to Supabase funds table.

    Allowed columns: code, name, fund_type, daily_change, market_cap, price,
    weekly, monthly, quarterly, returns, price_history, last_tefas_fetch.
    """
    ALLOWED = {
        "code", "name", "fund_type", "daily_change", "market_cap", "price",
        "weekly", "monthly", "quarterly", "returns", "price_history",
        "last_tefas_fetch", "sparkline",
    }
    if not rows:
        return 0
    updated = 0
    for row in rows:
        code = row.get("code")
        if not code:
            continue
        # Filter to only allowed columns
        filtered = {k: v for k, v in row.items() if k in ALLOWED and v is not None}
        if not filtered:
            continue
        url = f"{SUPABASE_URL}/rest/v1/funds?code=eq.{code}"
        payload = json.dumps(filtered)
        req = requests.patch(
            url, data=payload,
            headers={**HEADERS, "Prefer": "return=minimal"},
            timeout=30
        )
        if req.status_code in (200, 204):
            updated += 1
        else:
            print(f"    PATCH {code}: {req.status_code} {req.text[:150]}")
    return updated


def get_funds_from_db(limit: int = 1000) -> tuple[List[Dict], Dict]:
    """Fetch funds and their existing price_history from Supabase.
    
    price_history is fetched separately to avoid URL length limits with large JSONB.
    """
    # Fetch metadata without price_history (avoid URL length issues)
    # Sadece aktif fonları çek — is_active=false olanlar atlanır
    # Kaldırılan filter: market_cap=gt.0 — tüm fonlar güncellenmeli (sıfır olanlar dahil)
    # Supabase REST caps each response at 1000 rows (max_rows server-side).
    # Range header lifts client-side caps but not the server cap, so we have
    # to paginate explicitly. ~2400 active funds → 3 pages.
    PAGE_SIZE = 1000
    funds_all = []
    for offset in range(0, max(limit, 1), PAGE_SIZE):
        page_end = min(offset + PAGE_SIZE, limit) - 1
        url = (f"{SUPABASE_URL}/rest/v1/funds?"
               f"is_active=eq.true"
               f"&order=market_cap.desc"
               f"&offset={offset}&limit={PAGE_SIZE}"
               f"&select=code,name,price,last_tefas_fetch")
        req = requests.get(url, headers=HEADERS, timeout=60)
        if req.status_code != 200:
            print(f"  DB ERROR fetching funds (offset={offset}): {req.status_code} {req.text[:300]}")
            return [], {}
        batch = req.json()
        funds_all.extend(batch)
        if len(batch) < PAGE_SIZE:
            break
    # Reassemble pseudo-req-like for downstream code
    class _Req:
        status_code = 200
        def json(_):
            return funds_all
    req = _Req()

    funds = req.json()
    
    # Fetch price_history separately per fund (batched)
    history: Dict[str, List] = {}
    if funds:
        codes = [f["code"] for f in funds]
        # Fetch in batches of 50
        for i in range(0, len(codes), 50):
            batch = codes[i:i+50]
            codes_param = ",".join(batch)
            hist_url = (f"{SUPABASE_URL}/rest/v1/funds?code=in.({codes_param})"
                       f"&select=code,price_history")
            hr = requests.get(hist_url, headers=HEADERS, timeout=60)
            if hr.status_code == 200:
                for row in hr.json():
                    ph = row.get("price_history")
                    history[row["code"]] = ph if isinstance(ph, list) else []
            else:
                print(f"  DB WARN: price_history batch {i}: {hr.status_code}")

    return funds, history


def update_system_status(key: str, value: str) -> None:
    """Update a single key in system_status table.

    Always set updated_at — system_status has no DEFAULT-NOW trigger, so
    without this the row's audit timestamp stays at the original insert.
    """
    url = f"{SUPABASE_URL}/rest/v1/system_status"
    payload = json.dumps([{
        "key": key,
        "value": value,
        "updated_at": datetime.utcnow().isoformat(),
    }])
    requests.post(
        url, data=payload,
        headers={**HEADERS, "Prefer": "resolution=merge-duplicates, conflict=key"},
        timeout=10
    )


# ─── Single Fund Scraper ─────────────────────────────────────────────────────

def scrape_fund(ws, cdp_eval, code: str) -> Optional[Dict]:
    """
    Scrape all data for a single fund using CDP.

    1. Navigate to TEFAS fund page and wait for hydration
    2. Extract price history from API (periyod=60 = 5Y)
    3. Extract current price from API (periyod=12)
    4. Extract fund profile (benchmark comparison)
    5. Compute returns and build price_history
    6. Return structured dict
    """
    # Navigate
    url = f"https://www.tefas.gov.tr/tr/fund-detail/{code}"
    ws.send(json.dumps({"id": 9999, "method": "Page.navigate", "params": {"url": url}}))
    # Wait for network to settle — use shorter sleep for recently-visited pages
    time.sleep(3)

    # Step 1: Fetch price history (5Y)
    price_rows = fetch_price_history(cdp_eval, code, periyod=60)

    # Step 2: Fetch current price (12-day)
    current = fetch_current_price(cdp_eval, code)

    # Step 3: Fetch profile/benchmark
    profile = fetch_profile(cdp_eval, code)

    # Step 4: Build price_history
    price_history = build_price_history(price_rows)

    # Step 5: Compute returns
    returns = compute_returns(price_rows)

    # Latest price from API — also compute daily change from prev_price (most reliable)
    latest_price = None
    latest_date = None
    daily_change_from_api = None
    if price_rows:
        latest_row = sorted(price_rows, key=lambda x: x["date"])[-1]
        latest_price = latest_row["price"]
        latest_date = latest_row["date"]
    elif current:
        latest_price = current.get("fiyat")
        latest_date = current.get("tarih")

    # compute_daily_change from 5Y history (unreliable if <2 data points)
    daily_from_history = compute_daily_change(price_rows) if price_rows else None

    # Compute from API's prev_price (most reliable — direct from TEFAS)
    api_prev_price = current.get("prev_price") if current else None
    api_fiyat = current.get("fiyat") if current else None
    if api_fiyat and api_prev_price and api_prev_price > 0:
        daily_from_api = round((api_fiyat - api_prev_price) / api_prev_price * 100, 2)
    else:
        daily_from_api = daily_from_history  # fallback

    # DB columns: daily_change, weekly, monthly, quarterly, price, market_cap
    result = {
        "code": code,
        "price": latest_price,
        "daily_change": daily_from_api,
        "weekly": returns.get("weekly"),
        "monthly": returns.get("one_month"),
        "quarterly": returns.get("three_month"),
        "price_history": price_history,
        "last_tefas_fetch": datetime.utcnow().isoformat(),
    }

    if latest_date:
        result["last_price_date"] = latest_date

    return result


# ─── Log Writer ─────────────────────────────────────────────────────────────

def write_log(status: str, funds_scraped: int, errors: int, details: str = "") -> None:
    """Write scraper run log to system_status."""
    value = json.dumps({
        "status": status,
        "funds_scraped": funds_scraped,
        "errors": errors,
        "details": details,
        "finished_at": datetime.utcnow().isoformat(),
    })
    update_system_status("tefas_scraper_log", value)


# ─── Main ───────────────────────────────────────────────────────────────────

def main():
    print(f"[TEFAS SCRAPER v2] Starting at {datetime.utcnow():%H:%M:%S} — max_funds={MAX_FUNDS}")

    # Step 1: Get funds from DB
    funds, existing_history = get_funds_from_db(MAX_FUNDS)
    if not funds:
        print("  No funds in DB — exiting")
        return 0
    print(f"  {len(funds)} funds in DB")

    # Step 2: Determine which need scraping
    today_str = date.today().isoformat()
    need_scrape = []
    skip_count = 0
    for f in funds:
        code = f["code"]
        last_fetch = (f.get("last_tefas_fetch") or "")[:10]
        hist = existing_history.get(code, [])
        has_history = isinstance(hist, list) and len(hist) > 10
        if not has_history or last_fetch != today_str:
            need_scrape.append(code)
        else:
            skip_count += 1

    print(f"  Need to scrape: {len(need_scrape)}/{len(funds)} ({skip_count} up-to-date, skipping)")

    # ─── 30 gün stale фонları otomatik is_active=false yap ───────────────────────
    cutoff = (date.today() - timedelta(days=30)).isoformat()
    stale = []
    for f in funds:
        code = f["code"]
        hist = existing_history.get(code, [])
        if isinstance(hist, list) and len(hist) > 0:
            last_date = hist[-1].get("date", "")
            if last_date and last_date < cutoff:
                stale.append(code)
    if stale:
        print(f"  ⚠️  {len(stale)} fon 30 gündür verisiz — is_active=false yapılıyor: {stale[:10]}{'...' if len(stale) > 10 else ''}")
        for batch in [stale[i:i+100] for i in range(0, len(stale), 100)]:
            codes_param = ",".join(batch)
            patch_url = f"{SUPABASE_URL}/rest/v1/funds?code=in.({codes_param})"
            requests.patch(patch_url, headers=HEADERS,
                           data=json.dumps({"is_active": False}),
                           timeout=30)
        # Bunları need_scrape'den çıkar
        need_scrape = [c for c in need_scrape if c not in stale]
        print(f"  → Scrapable fon kaldı: {len(need_scrape)}")

    if not need_scrape:
        print("  All funds up-to-date")
        write_log("up_to_date", 0, 0)
        return 0

    # Step 3: Create Chrome tab
    print(f"  Creating Chrome tab on port {CHROME_PORT}...")
    ws_url, page_id = get_chrome_tab()
    if not ws_url:
        print("  FATAL: Could not create Chrome tab. Is Chrome running with remote debugging?")
        write_log("error", 0, len(need_scrape), "Chrome tab creation failed")
        return 0
    print(f"  Tab created: {page_id}")

    ws, cdp_send, cdp_eval = cdp_connect(ws_url)
    print("  CDP connected")

    results = []
    errors = 0
    last_ok_code = None
    consecutive_ws_errors = 0
    reconnect_attempts = 0
    MAX_RECONNECTS = 3

    signal.signal(signal.SIGALRM, _alarm_handler)
    try:
        for i, code in enumerate(need_scrape):
            print(f"  [{i+1}/{len(need_scrape)}] {code}", end="", flush=True)
            signal.alarm(PER_FUND_DEADLINE_SECS)
            try:
                data = scrape_fund(ws, cdp_eval, code)
                if data and data.get("price") is not None:
                    existing = existing_history.get(code, [])
                    merged = merge_price_history(existing, data.get("price_history", []))
                    data["price_history"] = merged
                    results.append(data)
                    last_ok_code = code
                    consecutive_ws_errors = 0
                    print(f" → {data['price']} | {len(merged)} pts")
                else:
                    errors += 1
                    print(" → FAILED (no price)")
            except FundScrapeTimeout:
                errors += 1
                print(f" → TIMEOUT (>{PER_FUND_DEADLINE_SECS}s, skipping)")
            except Exception as e:
                errors += 1
                msg = str(e)
                print(f" → EXCEPTION: {msg}")
                # A dead Chrome tab keeps raising "no close frame received or sent"
                # for every subsequent fund. Detect that and rebuild the CDP session.
                if "close frame" in msg or "ConnectionClosed" in msg or "WebSocket" in msg:
                    consecutive_ws_errors += 1
                    if consecutive_ws_errors >= 2 and reconnect_attempts < MAX_RECONNECTS:
                        reconnect_attempts += 1
                        print(f"  >>> WebSocket dead, reconnecting (attempt {reconnect_attempts}/{MAX_RECONNECTS})...")
                        try:
                            ws.close()
                        except Exception:
                            pass
                        time.sleep(2)
                        new_ws_url, new_page_id = get_chrome_tab()
                        if new_ws_url:
                            ws, cdp_send, cdp_eval = cdp_connect(new_ws_url)
                            consecutive_ws_errors = 0
                            print(f"  >>> Reconnected to tab {new_page_id}")
                        else:
                            print("  >>> Reconnect FAILED, aborting batch")
                            break
            finally:
                signal.alarm(0)

            time.sleep(0.5)  # Be polite to TEFAS

    finally:
        signal.alarm(0)
        try:
            ws.close()
        except Exception:
            pass
        print(f"  Chrome tab closed")

    print(f"\n[TEFAS SCRAPER v2] Done — {len(results)} scraped, {errors} errors, last_ok={last_ok_code}")

    # Step 4: Upsert to DB
    if results:
        updated = upsert_funds(results)
        print(f"  Upserted {updated}/{len(results)} rows to funds table")

    # Step 5: Update system_status
    status = "ok" if errors == 0 else "partial"
    update_system_status("last_tefas_fetch", datetime.utcnow().isoformat())
    write_log(status, len(results), errors)
    print(f"  system_status updated")

    return len(results)


if __name__ == "__main__":
    n = main()
    sys.exit(0 if n > 0 else 1)
