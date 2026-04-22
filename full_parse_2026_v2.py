#!/usr/bin/env python3
"""
Full 2026 Batch Parser v2
==========================
Fixed: key by (code, period) not just code — captures ALL monthly reports
"""
import json, os, re, subprocess, sys, time
from pathlib import Path

PROJECT_DIR = Path(__file__).parent
sys.path.insert(0, str(PROJECT_DIR))
from portfolio_parser import parse_portfolio_pdf

KAP_BASE = "https://www.kap.org.tr"
PDF_DIR = PROJECT_DIR / "pdfs" / "portfoy_dagilim_full"
PDF_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_FILE = PROJECT_DIR / "data" / "raw" / "full_2026_all.json"
PROGRESS_FILE = PROJECT_DIR / "data" / "raw" / "progress_v2.json"

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
    r = subprocess.run(cmd, capture_output=True, text=True)
    try:
        return json.loads(r.stdout)
    except:
        return []

def get_pdf_uuid(idx):
    r = subprocess.run(["curl", "-s", "-L", "--max-time", "15", f"{KAP_BASE}/tr/Bildirim/{idx}"],
                       capture_output=True, text=True)
    uuids = re.findall(r'file/download/([a-f0-9]{32})', r.stdout)
    return uuids[0] if uuids else None

def download_pdf(uuid, path):
    subprocess.run(["curl", "-s", "-L", "--max-time", "30",
                    "-H", "User-Agent: Mozilla/5.0",
                    "-o", str(path), f"{KAP_BASE}/tr/api/file/download/{uuid}"],
                   capture_output=True)
    return path.exists() and path.stat().st_size > 1000

def load_progress():
    if PROGRESS_FILE.exists():
        with open(PROGRESS_FILE) as f:
            return json.load(f)
    return {"processed": [], "results": [], "errors": [], "skipped": []}

def save_progress(p):
    with open(PROGRESS_FILE, 'w') as f:
        json.dump(p, f, ensure_ascii=False)

def main():
    p = load_progress()
    # Key by (code, period) not just code — each fund publishes monthly reports
    processed_keys = set((x['code'], x['period']) for x in p['processed'])

    for from_d, to_d in MONTHS:
        print(f"\n{'='*50}")
        print(f"Month: {from_d} → {to_d}")
        payload = {"fromDate": from_d, "toDate": to_d, "disclosureTypes": None,
                   "fundTypes": ["BYF","YF","EYF","OKS","YYF","VFF","KFF","GMF","GSF","PFF"],
                   "mkkMemberOid": None}
        data = curl_post(f"{KAP_BASE}/tr/api/disclosure/list/main", payload)
        reports = [d for d in data
                   if d.get("disclosureBasic",{}).get("title") == "Portföy Dağılım Raporu"
                   and d.get("disclosureBasic",{}).get("attachmentCount",0) > 0]
        print(f"  Reports found: {len(reports)}")

        for i, report in enumerate(reports):
            basic = report["disclosureBasic"]
            code = basic["stockCode"]
            idx = basic["disclosureIndex"]
            period = from_d  # unique period key
            key = (code, period)

            if key in processed_keys:
                p['skipped'].append({"code": code, "period": period, "reason": "already"})
                continue

            pdf_uuid = get_pdf_uuid(idx)
            if not pdf_uuid:
                p['errors'].append({"code": code, "period": period, "error": "no_uuid"})
                continue

            pdf_path = PDF_DIR / f"{code}_{period.replace('.','')}_{pdf_uuid[:8]}.pdf"
            if not pdf_path.exists():
                if not download_pdf(pdf_uuid, pdf_path):
                    p['errors'].append({"code": code, "period": period, "error": "dl_failed"})
                    continue

            try:
                parsed = parse_portfolio_pdf(str(pdf_path))
            except Exception as e:
                p['errors'].append({"code": code, "period": period, "error": str(e)[:60]})
                continue

            if not parsed:
                p['errors'].append({"code": code, "period": period, "error": "parse_none"})
                continue

            result = {
                "fund_code": code,
                "fund_name": basic["companyTitle"],
                "publish_date": basic["publishDate"],
                "report_period": period,
                "fund_info": parsed.get("fund_info", {}),
                "holdings": parsed.get("holdings", []),
                "stock_count": parsed.get("stock_count", 0),
            }
            p['processed'].append({"code": code, "period": period, "stocks": result['stock_count']})
            p['results'].append(result)
            processed_keys.add(key)

            if len(p['processed']) % 100 == 0:
                save_progress(p)
                total = sum(r['stock_count'] for r in p['results'])
                print(f"  [{len(p['processed'])} done] {total} holdings")
            time.sleep(0.15)

    save_progress(p)
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(p['results'], f, ensure_ascii=False)

    total = sum(r['stock_count'] for r in p['results'])
    with_stocks = sum(1 for r in p['results'] if r['stock_count'] > 0)
    print(f"\n{'='*50}")
    print(f"DONE! Processed: {len(p['processed'])}, Errors: {len(p['errors'])}, Skipped: {len(p['skipped'])}")
    print(f"With stocks: {with_stocks}, Total holdings: {total}")
    print(f"Output: {OUTPUT_FILE}")

if __name__ == "__main__":
    main()
