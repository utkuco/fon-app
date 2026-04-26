#!/usr/bin/env python3
"""
KAP Portfolio PDF Discovery + Downloader — GitHub Actions için.

Yapısı:
  1. Chrome (undetected_chromedriver) ile KAP fon listesine git
  2. Her fonun detail sayfasını kontrol et → portföy dağılım dokümanı var mı?
  3. Yeni PDF'leri indir → pdfs/portfoy_dagilim/

Usage:
  python scripts/kap_discover_download.py --batch --limit 50
  python scripts/kap_discover_download.py --test AN1

Environment:
  SUPABASE_URL       — Supabase project URL
  SUPABASE_SERVICE_KEY — Supabase service role key
  ZHIPU_API_KEY      — Zhipu AI key (not used here, but needed by parser)
  GITHUB_ACTIONS    — Set to 'true' if running in GitHub Actions
"""

import argparse
import os
import re
import sys
import time
import json
from datetime import datetime
from pathlib import Path
from typing import Optional

# ── Setup path ─────────────────────────────────────────────────────────────────
SCRIPT_DIR = Path(__file__).parent.resolve()
PDF_DIR = SCRIPT_DIR.parent / "pdfs" / "portfoy_dagilim"
STATE_FILE = SCRIPT_DIR / "kap_discovered_funds.json"
LOG_FILE = SCRIPT_DIR / "kap_discover.log"

PDF_DIR.mkdir(parents=True, exist_ok=True)


def log(msg: str, level: str = "INFO"):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] [{level}] {msg}"
    print(line)
    with open(LOG_FILE, "a") as f:
        f.write(line + "\n")


def load_state() -> dict:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text())
        except Exception:
            pass
    return {"downloaded": {}, "funds": []}


def save_state(state: dict):
    STATE_FILE.write_text(json.dumps(state, indent=2))


def already_downloaded(disclosure_id: str) -> bool:
    """Check if this disclosure ID is already in our local PDF directory."""
    for pdf_file in PDF_DIR.glob("*_*.pdf"):
        if pdf_file.stem.endswith(f"_{disclosure_id}") or disclosure_id in pdf_file.stem:
            return True
    return False


def get_fund_codes_from_supabase() -> list[str]:
    """Fetch all fund codes from Supabase that might have portfolio PDFs."""
    import requests as _req

    supabase_url = os.environ.get("SUPABASE_URL", "https://oqkobptbvcazifpvjwfz.supabase.co")
    service_key = os.environ.get("SUPABASE_SERVICE_KEY", "")

    # We'll use the anon key approach since it should work for reads
    anon_key = os.environ.get("SUPABASE_KEY", "sb_publishable__GPrsdfKRZCMZE8to916iQ_Izv9naG-")

    headers = {
        "apikey": service_key or anon_key,
        "Authorization": f"Bearer {service_key or anon_key}",
    }

    # Fetch all fund codes
    url = f"{supabase_url}/rest/v1/funds?select=code,fund_type&limit=3000"
    try:
        resp = _req.get(url, headers=headers, timeout=30)
        if resp.status_code == 200:
            funds = resp.json()
            log(f"Fetched {len(funds)} fund codes from Supabase")
            return [f["code"] for f in funds if f.get("code")]
    except Exception as e:
        log(f"Supabase fetch failed: {e}", "WARN")

    return []


def discover_with_chrome(fund_codes: list[str], limit: int = 0) -> list[tuple[str, str, str]]:
    """
    Use undetected_chromedriver to navigate KAP and discover portfolio PDF URLs.
    
    Returns: [(fund_code, disclosure_id, pdf_url), ...]
    """
    import requests as _req
    import undetected_chromedriver as _uc

    discovered: list[tuple[str, str, str]] = []
    processed = 0
    errors = 0

    options = _uc.ChromeOptions()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    options.add_argument(
        "--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )

    log("Starting Chrome (undetected)...")
    driver = _uc.Chrome(options=options, version_main=None)
    driver.set_page_load_timeout(30)

    funds_to_check = fund_codes[:limit] if limit else fund_codes
    log(f"Checking {len(funds_to_check)} funds for portfolio PDFs...")

    try:
        for i, fund_code in enumerate(funds_to_check):
            processed += 1
            if processed % 20 == 0:
                log(f"  Progress: {processed}/{len(funds_to_check)} funds checked...")

            try:
                # Navigate to fund detail page
                url = f"https://www.kap.org.tr/tr/fon-bilgileri/ozet/{fund_code}"
                driver.get(url)
                time.sleep(2)

                # Look for portfolio distribution disclosure
                # KAP fund pages have a "Portföy Dağılım Raporu" section
                page_text = driver.page_source

                # Try to find disclosure IDs in the page
                # Pattern: disclosure IDs in data attributes or links
                disclosure_pattern = re.findall(r'/tr/Bildirim/(\w{8})', page_text)
                pdf_pattern = re.findall(r'/tr/BildirimPdf/(\w{8})', page_text)

                # Alternative: look for portfolio-related disclosures
                # "Portföy Dağılım" keyword search
                if "portföy" in page_text.lower() or "portfoy" in page_text.lower():
                    # Look for PDF links
                    pdf_links = re.findall(r'href="(/tr/BildirimPdf/\w{8}/tr)"', page_text)
                    for link in pdf_links:
                        disclosure_id = re.search(r'/BildirimPdf/(\w{8})', link)
                        if disclosure_id:
                            did = disclosure_id.group(1)
                            if not already_downloaded(did):
                                full_url = f"https://www.kap.org.tr{tr}"
                                discovered.append((fund_code, did, full_url))
                                log(f"  Found: {fund_code} → {did}")

                # Also check for XHR/fetch requests that might have loaded data
                # The fund detail page loads disclosures via API calls

                time.sleep(1)

            except Exception as e:
                errors += 1
                if errors <= 5:
                    log(f"  Error checking {fund_code}: {e}", "WARN")
                continue

    finally:
        driver.quit()

    log(f"Discovery complete: {len(discovered)} new PDFs found, {errors} errors")
    return discovered


def download_pdf(fund_code: str, disclosure_id: str, pdf_url: str, cookies: str = "") -> Optional[Path]:
    """Download a single PDF from KAP."""
    import requests as _req

    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/pdf,text/html,*/*",
        "Referer": f"https://www.kap.org.tr/tr/fon-bilgileri/ozet/{fund_code}",
    }

    try:
        resp = _req.get(pdf_url, headers=headers, timeout=30, allow_redirects=True)
        if resp.status_code == 200 and len(resp.content) > 1000:
            filename = PDF_DIR / f"{fund_code}_{disclosure_id}.pdf"
            filename.write_bytes(resp.content)
            log(f"  Downloaded: {filename.name} ({len(resp.content)} bytes)")
            return filename
        else:
            log(f"  Failed download {fund_code}/{disclosure_id}: HTTP {resp.status_code}", "WARN")
    except Exception as e:
        log(f"  Download error {fund_code}/{disclosure_id}: {e}", "WARN")

    return None


def test_single_fund(fund_code: str):
    """Test discovery for a single fund."""
    import undetected_chromedriver as _uc

    log(f"Testing fund: {fund_code}")

    options = _uc.ChromeOptions()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    options.add_argument(
        "--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )

    driver = _uc.Chrome(options=options, version_main=None)
    driver.set_page_load_timeout(30)

    try:
        url = f"https://www.kap.org.tr/tr/fon-bilgileri/ozet/{fund_code}"
        driver.get(url)
        time.sleep(3)

        # Get page source
        page_source = driver.page_source
        print(f"Page length: {len(page_source)} chars")

        # Look for relevant patterns
        if "portföy" in page_source.lower() or "portfoy" in page_source.lower():
            print("Found 'portföy' on page!")
            # Find PDF links
            pdf_links = re.findall(r'href="(/tr/BildirimPdf/\w{8}/tr)"', page_source)
            print(f"PDF links found: {pdf_links}")
        else:
            print("No 'portföy' found on page")

        # Check for disclosure IDs
        disc_ids = re.findall(r'/tr/Bildirim/(\w{8})', page_source)
        print(f"Disclosure IDs: {disc_ids[:5]}")

        # Print first 2000 chars of page source
        print("\n--- PAGE SOURCE PREVIEW ---")
        print(page_source[:3000])

    finally:
        driver.quit()


def main():
    parser = argparse.ArgumentParser(description="KAP Portfolio PDF Discovery")
    parser.add_argument("--batch", action="store_true", help="Run in batch mode")
    parser.add_argument("--test", type=str, help="Test single fund code")
    parser.add_argument("--limit", type=int, default=0, help="Limit number of funds to check")
    parser.add_argument("--force", type=str, default="false", help="Force re-check even if cached")
    args = parser.parse_args()

    log(f"Starting KAP discover — batch={args.batch}, test={args.test}, limit={args.limit}")

    if args.test:
        test_single_fund(args.test)
        return

    if args.batch:
        state = load_state()

        # Get fund codes from Supabase (or use cached)
        if not state["funds"]:
            fund_codes = get_fund_codes_from_supabase()
            state["funds"] = fund_codes
            save_state(state)
        else:
            fund_codes = state["funds"]

        log(f"Total funds to check: {len(fund_codes)}")

        # Run discovery
        discovered = discover_with_chrome(fund_codes, limit=args.limit)

        # Download discovered PDFs
        downloaded = 0
        for fund_code, disclosure_id, pdf_url in discovered:
            path = download_pdf(fund_code, disclosure_id, pdf_url)
            if path:
                state["downloaded"][disclosure_id] = {
                    "fund_code": fund_code,
                    "path": str(path),
                    "timestamp": datetime.now().isoformat(),
                }
                downloaded += 1

        save_state(state)
        log(f"Batch complete: {downloaded} new PDFs downloaded")


if __name__ == "__main__":
    main()
