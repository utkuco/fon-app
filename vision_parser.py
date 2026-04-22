#!/usr/bin/env python3
"""
Vision Parser v3 - Hybrid: Regex (values/ISINs) + Vision (names/tickers)
========================================================================
Combines:
- Node.js parse_pdf.mjs for text extraction (ISINs + values at 99.7% accuracy)
- llama3.2-vision for company names and tickers

Usage:
  python3 vision_parser.py <pdf_path>       # single PDF
  python3 vision_parser.py --batch          # all PDFs
  python3 vision_parser.py --test           # test on 3 sample PDFs
"""

import json, os, re, subprocess, sys, time, base64
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Optional

PROJECT_DIR = Path(__file__).parent
OLLAMA_MODEL = "llama3.2-vision"


# ─── Text Extraction (reuses existing pipeline) ──────────────────────────────

def parse_pdf_text(pdf_path: str) -> str:
    """Extract text using Node.js parse_pdf.mjs."""
    script = PROJECT_DIR / "parse_pdf.mjs"
    result = subprocess.run(
        ["node", str(script), str(pdf_path)],
        capture_output=True, text=True, timeout=30
    )
    return result.stdout


def parse_pdf_positions(pdf_path: str):
    """Extract position data using parse_pdf_positions.mjs."""
    out_path = f"/tmp/pos_{Path(pdf_path).stem}.json"
    script = PROJECT_DIR / "parse_pdf_positions.mjs"
    subprocess.run(
        ["node", str(script), str(pdf_path), out_path],
        capture_output=True, text=True, timeout=30
    )
    if os.path.exists(out_path):
        with open(out_path) as f:
            return json.load(f)
    return None


# ─── Vision API ───────────────────────────────────────────────────────────────

def encode_image(png_path: str) -> str:
    with open(png_path, 'rb') as f:
        return base64.b64encode(f.read()).decode('utf-8')


def pdf_page_to_image(pdf_path: str, page_num: int, scale: float = 1.5) -> str:
    """Convert PDF page to PNG using pypdfium2."""
    import pypdfium2 as pdfium
    pdf = pdfium.PdfDocument(pdf_path)
    if page_num >= len(pdf):
        return None
    page = pdf[page_num]
    pil_img = page.render(scale=scale).to_pil()
    out_path = f"/tmp/vp_{Path(pdf_path).stem}_p{page_num+1}.png"
    pil_img.save(out_path, "PNG")
    return out_path


def call_vision(prompt: str, image_b64: str, timeout: int = 120) -> str:
    """Call Ollama vision API."""
    payload = {
        "model": OLLAMA_MODEL,
        "images": [image_b64],
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0.05}
    }
    result = subprocess.run(
        ["curl", "-s", "http://localhost:11434/api/generate",
         "-X", "POST", "-H", "Content-Type: application/json",
         "-d", json.dumps(payload), "--max-time", str(timeout)],
        capture_output=True, text=True, timeout=timeout + 10
    )
    try:
        resp = json.loads(result.stdout)
        return resp.get("response", "")
    except:
        return ""


VISION_PROMPT = """Bu görsel bir Türk yatırım fonu portföy dağılım tablosudur.

Tabloda hisse senetleri ve diğer varlıklar listelenmiştir. Tüm varlıkları çıkar.

Format: HER SATIRDA "name | ticker | isin" olsun. Boşlukla ayır.

Örnek:
KOC HOLDING | KCHOL | TRAKCHOL91Q8
YAPI KREDİ |YKBNK | TRYKBNK91A4
T.REPO | T.REPO |

Tüm satırları listele. ISIN kodu TR harfi ile başlar."""


# ─── Regex Extraction (proven 99.7% accurate) ─────────────────────────────────

def is_stock_isin(isin: str) -> bool:
    return len(isin) == 12 and isin.startswith('TR') and isin[2] in ('A', 'E')

def is_gov_bond_isin(isin: str) -> bool:
    return len(isin) == 12 and isin.startswith('TRT')

def is_corp_bond_isin(isin: str) -> bool:
    return len(isin) == 12 and isin[:3] in ('TRB', 'TRS', 'TRF')

def is_fund_isin(isin: str) -> bool:
    return len(isin) == 12 and isin.startswith('TRY')


def extract_all_isins(text: str) -> List[str]:
    """Extract all Turkish ISINs from text."""
    isins = []
    for m in re.finditer(r'TR[A-Z0-9]{10}', text):
        isin = m.group(0)[:12]
        if len(isin) == 12 and isin.startswith('TR'):
            isins.append(isin)
    return list(dict.fromkeys(isins))


def extract_holdings_from_text(text: str, pos_data: dict = None) -> List[Dict]:
    """Extract all holdings using text positions (proven approach)."""
    holdings = []
    
    # Get ISINs
    all_isins = extract_all_isins(text)
    
    # Build ticker map from position data (if available)
    ticker_map = {}
    if pos_data:
        items = pos_data.get('items', [])
        for page_num in range(1, pos_data.get('pages', 0) + 1):
            page_items = [i for i in items if i['p'] == page_num]
            for item in page_items:
                s = item['s']
                if not (s.startswith('TRA') or s.startswith('TRE')):
                    continue
                if len(s) < 8:
                    continue
                y = item['y']
                row = [i for i in page_items if abs(i['y'] - y) <= 3]
                row.sort(key=lambda x: x['x'])
                
                # Find ISIN position
                isin_x = item['x']
                isin_parts = [item['s']]
                for ri in row:
                    if ri is item:
                        continue
                    if isin_x <= ri['x'] <= isin_x + 30 and ri['s']:
                        isin_parts.append(ri['s'])
                combined = ''.join(isin_parts)[:12]
                if not (len(combined) == 12 and combined.startswith('TR') and combined[2] in ('A', 'E')):
                    if len(item['s']) >= 12 and is_stock_isin(item['s'][:12]):
                        combined = item['s'][:12]
                    else:
                        continue
                
                # Find ticker (left side, x < 80)
                ticker = ''
                for ri in row:
                    if ri['x'] < 80 and ri['s']:
                        t = ri['s'].strip()
                        if 3 <= len(t) <= 6 and t.isupper() and t not in ('TL', 'USD', 'EUR', 'GBP', 'TRY'):
                            ticker = t
                            break
                
                if ticker and combined not in ticker_map:
                    ticker_map[combined] = ticker
    
    # Process each ISIN
    for isin in all_isins:
        # Determine category
        if is_stock_isin(isin):
            cat = 'stock'
        elif is_gov_bond_isin(isin):
            cat = 'gov_bond'
        elif is_corp_bond_isin(isin):
            cat = 'corp_bond'
        elif is_fund_isin(isin):
            cat = 'fund'
        else:
            cat = 'other'
        
        # Find values after ISIN in text
        idx = text.find(isin)
        chunk = text[idx + 12:idx + 300]
        
        # Extract numbers (value format: 1,234,567.89 or 1.234.567,89)
        nums = re.findall(r'[\d\.]{1,3}(?:,\d{3})+(?:\.\d+)?', chunk)
        value = 0.0
        for n in nums[:4]:
            try:
                v = float(n.replace('.', '').replace(',', '.'))
                if v > 100:  # likely a monetary value
                    value = v
                    break
            except:
                pass
        
        # Extract percentage
        pct_match = re.search(r'([\d]+[,.]\d+)\s*%', chunk)
        pct = 0.0
        if pct_match:
            try:
                pct = float(pct_match.group(1).replace(',', '.'))
            except:
                pass
        
        # Nominal value
        nominal = 0.0
        nom_matches = re.findall(r'(\d{1,3}(?:[,.]\d{3})+)\s*$', chunk[:100], re.MULTILINE)
        for n in nom_matches[:2]:
            try:
                v = float(n.replace('.', '').replace(',', '.'))
                if v > 0:
                    nominal = v
                    break
            except:
                pass
        
        ticker = ticker_map.get(isin, '')
        
        holdings.append({
            'category': cat,
            'isin': isin,
            'ticker': ticker,
            'name': '',  # will be filled by vision
            'value': value,
            'pct': pct,
            'nominal': nominal
        })
    
    return holdings


def extract_summary_from_text(text: str) -> Dict:
    """Extract fund summary info from text."""
    info = {}
    
    # Fund name
    m = re.search(r'(STRATEJ[İIİ]\s+.*FON[^\n]*)', text)
    if m:
        info['fund_name'] = m.group(1).strip()[:100]
    
    # Report date
    m = re.search(r'(\d{2}/\d{2}/\d{4})\s*-\s*(\d{2}/\d{2}/\d{4})', text)
    if m:
        info['report_start'] = m.group(1)
        info['report_end'] = m.group(2)
    
    # Total value
    m = re.search(r'FON TOPLAM DEĞER[İIİ\s]+\s*([\d\.]{1,3}(?:,\d{3})+)', text)
    if m:
        try:
            info['total_value'] = float(m.group(1).replace('.', '').replace(',', '.'))
        except:
            pass
    
    # Other asset totals from page 2
    cat_patterns = {
        'viop': r'VIOP\s+(?:Toplam\s+)?([\d\.]{1,3}(?:,\d{3})+)',
        'repo': r'T\.?REPO\s+(?:Toplam\s+)?([\d\.]{1,3}(?:,\d{3})+)',
        'tpp': r'TPP\s+(?:Toplam\s+)?([\d\.]{1,3}(?:,\d{3})+)',
        'fund': r'FON\s+Toplam\s+([[\d\.]{1,3}(?:,\d{3})+)',
        'fx': r'DVZ\s+(?:Toplam\s+)?([\d\.]{1,3}(?:,\d{3})+)',
    }
    
    for cat, pattern in cat_patterns.items():
        m = re.search(pattern, text)
        if m:
            try:
                info[f'{cat}_value'] = float(m.group(1).replace('.', '').replace(',', '.'))
            except:
                pass
    
    return info


# ─── Vision Name Extraction ───────────────────────────────────────────────────

def extract_names_with_vision(pdf_path: str, holdings: List[Dict]) -> List[Dict]:
    """Use vision model to fill in company names for holdings."""
    if not holdings:
        return holdings
    
    # Get first 2 pages as images
    images = []
    for page_num in [0, 1]:
        png_path = pdf_page_to_image(pdf_path, page_num, scale=1.5)
        if png_path:
            images.append(png_path)
    
    if not images:
        return holdings
    
    # Call vision for name extraction
    img_b64 = encode_image(images[0])
    response = call_vision(VISION_PROMPT, img_b64, timeout=150)
    
    # Clean up temp images
    for p in images:
        if os.path.exists(p):
            os.remove(p)
    
    # Parse response to build ticker→name map
    name_map = {}
    for line in response.split('\n'):
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        parts = line.split('|')
        if len(parts) >= 2:
            name = parts[0].strip()
            ticker = parts[1].strip()
            if ticker and name and len(name) > 2:
                name_map[ticker] = name
    
    # Match holdings with names
    for h in holdings:
        ticker = h.get('ticker', '')
        if ticker and ticker in name_map:
            h['name'] = name_map[ticker]
    
    return holdings


# ─── Main Parser ──────────────────────────────────────────────────────────────

def parse_single_pdf(pdf_path: str, use_vision: bool = False) -> Dict:
    """Parse a single PDF: text extraction + optional vision for names."""
    pdf_path = Path(pdf_path)
    
    # Extract text
    text = parse_pdf_text(str(pdf_path))
    
    # Extract summary info
    summary = extract_summary_from_text(text)
    
    # Extract holdings with positions
    pos_data = parse_pdf_positions(str(pdf_path))
    holdings = extract_holdings_from_text(text, pos_data)
    
    # Dedupe by ISIN
    seen = set()
    deduped = []
    for h in holdings:
        if h['isin'] not in seen:
            seen.add(h['isin'])
            deduped.append(h)
    holdings = deduped
    
    # Optionally use vision to fill names
    if use_vision and holdings:
        holdings = extract_names_with_vision(str(pdf_path), holdings)
    
    # Separate by category
    stocks = [h for h in holdings if h['category'] == 'stock']
    other = [h for h in holdings if h['category'] != 'stock']
    
    return {
        'fund_code': pdf_path.stem.split('_')[0],
        'fund_name': summary.get('fund_name', ''),
        'report_start': summary.get('report_start', ''),
        'report_end': summary.get('report_end', ''),
        'total_value': summary.get('total_value', 0),
        'stock_count': len(stocks),
        'holdings': stocks,
        'other_assets': other,
        'viop_value': summary.get('viop_value', 0),
        'repo_value': summary.get('repo_value', 0),
        'tpp_value': summary.get('tpp_value', 0),
        'fund_value': summary.get('fund_value', 0),
        'fx_value': summary.get('fx_value', 0),
    }


def test_parser(n: int = 3):
    """Test on n sample PDFs."""
    pdf_dir = PROJECT_DIR / "pdfs" / "portfoy_dagilim"
    pdfs = sorted(pdf_dir.glob("*.pdf"))[:n]
    
    print(f"Testing on {len(pdfs)} PDFs...\n")
    for pdf in pdfs:
        result = parse_single_pdf(str(pdf), use_vision=False)
        print(f"{'='*50}")
        print(f"Fund: {result['fund_code']} | {result['fund_name'][:40]}")
        print(f"Period: {result['report_start']} - {result['report_end']}")
        print(f"Total value: {result['total_value']:>20,.0f}" if result['total_value'] else "Total value: N/A")
        print(f"Stocks: {result['stock_count']}")
        for h in result['holdings'][:3]:
            print(f"  {h['ticker'] or '???':6} | {h['isin']} | {h['value']:>15,.0f}" if h['value'] else f"  {h['ticker'] or '???':6} | {h['isin']}")
        if result['other_assets']:
            print(f"  Other: {[a['category'] for a in result['other_assets']]}")
        print()


def batch_process(output_file: str = None, max_workers: int = 3, use_vision: bool = False):
    """Process all PDFs."""
    pdf_dir = PROJECT_DIR / "pdfs" / "portfoy_dagilim"
    pdfs = sorted(pdf_dir.glob("*.pdf"))
    
    if output_file is None:
        output_file = PROJECT_DIR / "data" / "vision_parse_results.json"
    output_file = Path(output_file)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    
    print(f"Found {len(pdfs)} PDFs")
    print(f"Workers: {max_workers} | Vision: {use_vision}")
    
    results = []
    
    def process_one(pdf_path):
        try:
            return parse_single_pdf(str(pdf_path), use_vision=use_vision)
        except Exception as e:
            return {'fund_code': Path(pdf_path).stem.split('_')[0], 'error': str(e)}
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(process_one, p): p for p in pdfs}
        for i, future in enumerate(as_completed(futures)):
            result = future.result()
            status = "ERR" if 'error' in result else "OK"
            sc = result.get('stock_count', 0)
            tv = result.get('total_value', 0)
            print(f"[{i+1:3d}/{len(pdfs)}] {result.get('fund_code','?'):6} [{status}] stocks={sc:2d} total={tv:>18,.0f}" if tv else f"[{i+1:3d}/{len(pdfs)}] {result.get('fund_code','?'):6} [{status}] stocks={sc:2d} total=N/A")
            results.append(result)
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    
    success = sum(1 for r in results if 'error' not in r)
    print(f"\nDone! {success}/{len(results)} succeeded")
    print(f"Saved: {output_file}")
    return results


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("pdf_path", nargs="?", help="Single PDF")
    parser.add_argument("--batch", action="store_true", help="All PDFs")
    parser.add_argument("--test", action="store_true", help="Test 3 PDFs")
    parser.add_argument("--vision", action="store_true", help="Use vision for names")
    parser.add_argument("-o", "--output", help="Output file")
    parser.add_argument("-w", "--workers", type=int, default=3)
    args = parser.parse_args()
    
    if args.test:
        test_parser(3)
    elif args.batch:
        batch_process(args.output, args.workers, args.vision)
    elif args.pdf_path:
        result = parse_single_pdf(args.pdf_path, use_vision=args.vision)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        parser.print_help()
