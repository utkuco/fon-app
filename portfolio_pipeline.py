#!/usr/bin/env python3
"""
KAP Portföy Dağılım Pipeline v3
=================================
Automated pipeline for fetching fund portfolio data from KAP.

Flow:
  1. KAP API → Fetch fund disclosures
  2. Filter → "Portföy Dağılım Raporu" only
  3. Download → Get PDF from disclosure page
  4. Parse → Hybrid text+position parser extracts holdings
  5. Save → Structured JSON for the fund app

Usage:
  python3 portfolio_pipeline.py --from 01.03.2026 --to 31.03.2026 --max 50
  python3 portfolio_pipeline.py --last-month          # auto-date last month
  python3 portfolio_pipeline.py --today                # today's reports only
"""

import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

PROJECT_DIR = Path(__file__).parent
DATA_DIR = PROJECT_DIR / "data"
PDF_DIR = PROJECT_DIR / "pdfs" / "portfoy_dagilim"
PDF_DIR.mkdir(parents=True, exist_ok=True)
DATA_DIR.mkdir(parents=True, exist_ok=True)

FUND_TYPES = ["BYF", "YF", "EYF", "OKS", "YYF", "VFF", "KFF", "GMF", "GSF", "PFF"]
KAP_BASE = "https://www.kap.org.tr"


def curl_post_json(url, data, timeout=30):
    cmd = ["curl", "-s", "-L", "--max-time", str(timeout),
           "-X", "POST", "-H", "Content-Type: application/json",
           "-d", json.dumps(data), url]
    result = subprocess.run(cmd, capture_output=True, text=True)
    try:
        return json.loads(result.stdout)
    except Exception:
        return []


def curl_get(url, timeout=15):
    cmd = ["curl", "-s", "-L", "--max-time", str(timeout), url]
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.stdout


def get_pdf_uuid(disclosure_index):
    html = curl_get(f"{KAP_BASE}/tr/Bildirim/{disclosure_index}")
    if not html:
        return None
    uuids = re.findall(r'file/download/([a-f0-9]{32})', html)
    return uuids[0] if uuids else None


def download_pdf(uuid, output_path):
    url = f"{KAP_BASE}/tr/api/file/download/{uuid}"
    cmd = ["curl", "-s", "-L", "--max-time", "30",
           "-H", "User-Agent: Mozilla/5.0",
           "-o", str(output_path), url]
    subprocess.run(cmd, capture_output=True)
    return output_path.exists() and output_path.stat().st_size > 1000


def parse_fund(pdf_path):
    """Parse a single fund PDF using the hybrid parser."""
    sys.path.insert(0, str(PROJECT_DIR))
    from portfolio_parser import parse_portfolio_pdf
    return parse_portfolio_pdf(str(pdf_path))


def run_pipeline(from_date, to_date, max_funds=None, fund_types=None):
    """Main pipeline."""
    start_time = time.time()
    print(f"\n{'='*60}")
    print(f"KAP Portföy Dağılım Pipeline v3")
    print(f"Date range: {from_date} → {to_date}")
    if max_funds:
        print(f"Max funds: {max_funds}")
    print(f"{'='*60}\n")

    # Step 1: Fetch disclosures
    print("[1/4] Fetching disclosures from KAP API...")
    payload = {
        "fromDate": from_date, "toDate": to_date,
        "disclosureTypes": None,
        "fundTypes": fund_types or FUND_TYPES,
        "mkkMemberOid": None,
    }
    all_disclosures = curl_post_json(f"{KAP_BASE}/tr/api/disclosure/list/main", payload)
    print(f"      Total disclosures: {len(all_disclosures)}")

    # Step 2: Filter
    reports = [d for d in all_disclosures
               if d["disclosureBasic"]["title"] == "Portföy Dağılım Raporu"
               and d["disclosureBasic"]["attachmentCount"] > 0]
    print(f"      Portföy Dağılım Raporu with PDF: {len(reports)}")

    if not reports:
        print("No portfolio reports found!")
        return []

    if max_funds:
        reports = reports[:max_funds]
        print(f"      Limited to {max_funds} reports")

    # Step 3-4: Download + Parse
    print(f"\n[2/4] Processing {len(reports)} reports...")
    results = []
    stats = {'downloaded': 0, 'parsed': 0, 'with_stocks': 0, 'total_holdings': 0}

    for i, report in enumerate(reports):
        basic = report["disclosureBasic"]
        detail = report.get("disclosureDetail", {})
        code = basic["stockCode"]
        idx = basic["disclosureIndex"]

        print(f"  [{i+1}/{len(reports)}] {code}: ", end="", flush=True)

        # Get PDF UUID
        pdf_uuid = get_pdf_uuid(idx)
        if not pdf_uuid:
            print("SKIP (no UUID)")
            continue

        # Download PDF
        pdf_path = PDF_DIR / f"{code}_{pdf_uuid[:8]}.pdf"
        if not pdf_path.exists():
            if not download_pdf(pdf_uuid, pdf_path):
                print("SKIP (download failed)")
                continue
        stats['downloaded'] += 1
        print(f"{pdf_path.stat().st_size//1024}KB ", end="", flush=True)

        # Parse
        try:
            parsed = parse_fund(pdf_path)
        except Exception as e:
            print(f"PARSE ERROR: {e}")
            continue

        if not parsed:
            print("SKIP (parse returned None)")
            continue

        stats['parsed'] += 1
        stock_count = parsed.get('stock_count', 0)
        if stock_count > 0:
            stats['with_stocks'] += 1
            stats['total_holdings'] += stock_count

        print(f"→ {stock_count} stocks")

        results.append({
            "fund_code": code,
            "fund_name": basic["companyTitle"],
            "fund_oid": detail.get("fundOid"),
            "publish_date": basic["publishDate"],
            "report_summary": basic.get("summary", ""),
            "fund_info": parsed.get("fund_info", {}),
            "holdings": parsed.get("holdings", []),
            "stock_count": stock_count,
        })

        time.sleep(0.3)

    # Save output
    date_suffix = f"{from_date.replace('.','')}-{to_date.replace('.','')}"
    output_file = DATA_DIR / f"portfoy_{date_suffix}.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    elapsed = time.time() - start_time
    print(f"\n{'='*60}")
    print(f"DONE in {elapsed:.0f}s")
    print(f"  Downloaded: {stats['downloaded']}")
    print(f"  Parsed: {stats['parsed']}")
    print(f"  With stocks: {stats['with_stocks']}")
    print(f"  Total holdings: {stats['total_holdings']}")
    print(f"  Output: {output_file}")
    print(f"{'='*60}")

    return results


def last_month_range():
    """Get date range for last month."""
    today = datetime.now()
    first_of_this_month = today.replace(day=1)
    last_month_end = first_of_this_month - timedelta(days=1)
    last_month_start = last_month_end.replace(day=1)
    return last_month_start.strftime("%d.%m.%Y"), last_month_end.strftime("%d.%m.%Y")


def today_range():
    """Get today's date range."""
    today = datetime.now().strftime("%d.%m.%Y")
    return today, today


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="KAP Portföy Dağılım Pipeline v3")
    parser.add_argument("--from", dest="from_date", default=None)
    parser.add_argument("--to", dest="to_date", default=None)
    parser.add_argument("--max", type=int, default=None)
    parser.add_argument("--last-month", action="store_true")
    parser.add_argument("--today", action="store_true")
    parser.add_argument("--fund-types", nargs="+", default=None)
    args = parser.parse_args()

    if args.last_month:
        args.from_date, args.to_date = last_month_range()
    elif args.today:
        args.from_date, args.to_date = today_range()

    if not args.from_date or not args.to_date:
        args.from_date = args.from_date or "01.03.2026"
        args.to_date = args.to_date or "31.03.2026"

    run_pipeline(args.from_date, args.to_date, args.max, args.fund_types)
