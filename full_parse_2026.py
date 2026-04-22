#!/usr/bin/env python3
"""
Full 2026 Batch Parser
=======================
Processes all 4540 portfolio reports from Jan-Apr 2026.
Runs in background, saves progress as it goes.
"""
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

PROJECT_DIR = Path(__file__).parent
sys.path.insert(0, str(PROJECT_DIR))

from portfolio_parser import parse_portfolio_pdf

KAP_BASE = "https://www.kap.org.tr"
PDF_DIR = PROJECT_DIR / "pdfs" / "portfoy_dagilim"
PDF_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR = PROJECT_DIR / "data" / "raw"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

PROGRESS_FILE = OUTPUT_DIR / "progress.json"

MONTHS = [
    ("01.01.2026", "31.01.2026"),
    ("01.02.2026", "28.02.2026"),
    ("01.03.2026", "31.03.2026"),
    ("01.04.2026", "15.04.2026"),
]


def curl_post(url, payload, timeout=60):
    cmd = ["curl", "-s", "-L", "--max-time", str(timeout),
           "-X", "POST", "-H", "Content-Type: application/json",
           "-d", json.dumps(payload), url]
    result = subprocess.run(cmd, capture_output=True, text=True)
    try:
        return json.loads(result.stdout)
    except:
        return []


def get_pdf_uuid(idx):
    cmd = ["curl", "-s", "-L", "--max-time", "15", f"{KAP_BASE}/tr/Bildirim/{idx}"]
    result = subprocess.run(cmd, capture_output=True, text=True)
    uuids = re.findall(r'file/download/([a-f0-9]{32})', result.stdout)
    return uuids[0] if uuids else None


def download_pdf(uuid, path):
    cmd = ["curl", "-s", "-L", "--max-time", "30",
           "-H", "User-Agent: Mozilla/5.0",
           "-o", str(path), f"{KAP_BASE}/tr/api/file/download/{uuid}"]
    subprocess.run(cmd, capture_output=True)
    return path.exists() and path.stat().st_size > 1000


def load_progress():
    if PROGRESS_FILE.exists():
        with open(PROGRESS_FILE) as f:
            return json.load(f)
    return {"processed": [], "results": [], "errors": []}


def save_progress(progress):
    with open(PROGRESS_FILE, 'w') as f:
        json.dump(progress, f, ensure_ascii=False)


def main():
    progress = load_progress()
    processed_codes = set(p['code'] for p in progress['processed'])

    for from_d, to_d in MONTHS:
        label = f"{from_d}-{to_d}"
        print(f"\n{'='*60}")
        print(f"Fetching: {label}")
        
        payload = {
            "fromDate": from_d, "toDate": to_d,
            "disclosureTypes": None,
            "fundTypes": ["BYF","YF","EYF","OKS","YYF","VFF","KFF","GMF","GSF","PFF"],
            "mkkMemberOid": None,
        }
        data = curl_post(f"{KAP_BASE}/tr/api/disclosure/list/main", payload)
        reports = [d for d in data 
                   if d.get("disclosureBasic",{}).get("title") == "Portföy Dağılım Raporu" 
                   and d.get("disclosureBasic",{}).get("attachmentCount",0) > 0]
        
        print(f"  Found {len(reports)} reports")
        
        for i, report in enumerate(reports):
            basic = report["disclosureBasic"]
            detail = report.get("disclosureDetail", {})
            code = basic["stockCode"]
            idx = basic["disclosureIndex"]
            
            # Skip if already processed
            if code in processed_codes:
                continue
            
            # Get PDF UUID
            pdf_uuid = get_pdf_uuid(idx)
            if not pdf_uuid:
                progress['errors'].append({"code": code, "error": "no_uuid"})
                save_progress(progress)
                continue
            
            # Download
            pdf_path = PDF_DIR / f"{code}_{pdf_uuid[:8]}.pdf"
            if not pdf_path.exists():
                if not download_pdf(pdf_uuid, pdf_path):
                    progress['errors'].append({"code": code, "error": "download_failed"})
                    save_progress(progress)
                    continue
            
            # Parse
            try:
                parsed = parse_portfolio_pdf(str(pdf_path))
            except Exception as e:
                progress['errors'].append({"code": code, "error": str(e)[:50]})
                save_progress(progress)
                continue
            
            if not parsed:
                progress['errors'].append({"code": code, "error": "parse_none"})
                save_progress(progress)
                continue
            
            result = {
                "fund_code": code,
                "fund_name": basic["companyTitle"],
                "publish_date": basic["publishDate"],
                "report_period": from_d,
                "fund_info": parsed.get("fund_info", {}),
                "holdings": parsed.get("holdings", []),
                "stock_count": parsed.get("stock_count", 0),
            }
            
            progress['processed'].append({"code": code, "stocks": result['stock_count']})
            progress['results'].append(result)
            processed_codes.add(code)
            
            # Save every 50
            if len(progress['processed']) % 50 == 0:
                save_progress(progress)
                total_stocks = sum(r['stock_count'] for r in progress['results'])
                print(f"  [{len(progress['processed'])} done] {total_stocks} total holdings extracted")
            
            time.sleep(0.2)
    
    # Final save
    save_progress(progress)
    
    # Save final results
    output_file = OUTPUT_DIR / "full_2026.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(progress['results'], f, ensure_ascii=False)
    
    total_stocks = sum(r['stock_count'] for r in progress['results'])
    with_stocks = sum(1 for r in progress['results'] if r['stock_count'] > 0)
    print(f"\n{'='*60}")
    print(f"DONE!")
    print(f"  Processed: {len(progress['processed'])}")
    print(f"  With stocks: {with_stocks}")
    print(f"  Total holdings: {total_stocks}")
    print(f"  Errors: {len(progress['errors'])}")
    print(f"  Output: {output_file}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
