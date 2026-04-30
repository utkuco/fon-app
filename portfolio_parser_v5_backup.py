#!/usr/bin/env python3
"""
KAP Portfolio Parser v5 - Hybrid (Text + Position)
====================================================
1. Parse text to find all stock ISINs (TRA/TRE prefix)
2. Parse positions to find tickers (left column, x<30 or x<80)
3. Match ISINs with tickers by proximity
"""

import json
import os
import re
import subprocess
from pathlib import Path

PROJECT_DIR = Path(__file__).parent


def run_node(script, args, timeout=30):
    result = subprocess.run(["node", str(script)] + args,
                          capture_output=True, text=True, timeout=timeout)
    return result.stdout


def parse_pdf_text(pdf_path):
    script = PROJECT_DIR / "parse_pdf.mjs"
    return run_node(script, [str(pdf_path)])


def parse_pdf_positions(pdf_path, out_path=None):
    if out_path is None:
        out_path = f"/tmp/pos_{Path(pdf_path).stem}.json"
    script = PROJECT_DIR / "parse_pdf_positions.mjs"
    subprocess.run(["node", str(script), str(pdf_path), out_path],
                  capture_output=True, text=True, timeout=30)
    if os.path.exists(out_path):
        with open(out_path, 'r') as f:
            return json.load(f)
    return None


def is_stock_isin(isin):
    return len(isin) == 12 and isin.startswith('TR') and isin[2] in ('A', 'E')


def extract_isins_from_text(text):
    """Find all stock ISINs from concatenated text."""
    isins = []
    for m in re.finditer(r'TR[A-Z0-9]{10}', text):
        isin = m.group(0)[:12]
        if is_stock_isin(isin):
            tail = isin[2:]
            if any(c.isdigit() for c in tail) and any(c.isalpha() for c in tail):
                isins.append(isin)
    return list(dict.fromkeys(isins))  # deduplicate preserving order


def extract_ticker_map_from_positions(pos_data):
    """
    Build a map: ISIN → ticker by analyzing position data.
    Finds ticker items (x < 30) and ISIN items in same row.
    """
    if not pos_data:
        return {}

    ticker_map = {}
    items = pos_data.get('items', [])

    for page_num in range(1, pos_data.get('pages', 0) + 1):
        page_items = [i for i in items if i['p'] == page_num]
        if not page_items:
            continue

        # Find ISIN items (x≈190-220, starts with TRA/TRE)
        for item in page_items:
            s = item['s']
            if not ((s.startswith('TRA') or s.startswith('TRE')) and len(s) >= 8):
                continue

            # Try to construct full ISIN from seed + continuation
            y = item['y']
            seed = s

            # Look for continuation items (same y, x slightly larger)
            row = [i for i in page_items if abs(i['y'] - y) <= 3]
            row.sort(key=lambda x: x['x'])

            # Find items close to ISIN x position (within 30px)
            isin_x = item['x']
            isin_parts = [item['s']]
            for ri in row:
                if ri is item:
                    continue
                if isin_x <= ri['x'] <= isin_x + 30 and ri['s']:
                    isin_parts.append(ri['s'])

            combined = ''.join(isin_parts)[:12]

            # Validate
            if not is_stock_isin(combined):
                # Try just the seed (sometimes it's already 12 chars)
                if len(seed) >= 12 and is_stock_isin(seed[:12]):
                    combined = seed[:12]
                else:
                    continue

            # Now find ticker in this row (x < 80)
            ticker = ''
            for ri in row:
                if ri['x'] < 80 and ri['s']:
                    t = ri['s'].strip()
                    if 3 <= len(t) <= 6 and t.isupper() and t not in ('TL', 'USD', 'EUR', 'GBP'):
                        ticker = t
                        break

            if ticker and combined not in ticker_map:
                ticker_map[combined] = ticker

    return ticker_map


def extract_data_from_text(text, isin):
    """Extract nominal, price, date around an ISIN in the text."""
    # Find the ISIN in text
    idx = text.find(isin)
    if idx == -1:
        # ISIN might be split in text too
        return {}

    after = text[idx + 12:idx + 250]

    # Numbers after ISIN
    nums_comma = re.findall(r'-?[\d]{1,3}(?:\.[\d]{3})*(?:,\d{1,6})?', after)
    nums_dot = re.findall(r'-?[\d]{1,3}(?:,[\d]{3})*(?:\.\d{1,6})?', after)

    # Pick format with better numbers
    v_comma = [n for n in nums_comma if len(n.replace('-','').replace(',','').replace('.','')) >= 3]
    v_dot = [n for n in nums_dot if len(n.replace('-','').replace(',','').replace('.','')) >= 3]

    numbers = v_comma if len(v_comma) >= len(v_dot) else v_dot

    result = {}
    if numbers:
        result['nominal'] = numbers[0]
    if len(numbers) > 1:
        result['unit_price'] = numbers[1]
    if len(numbers) > 2:
        result['total_value'] = numbers[2]

    # Date
    date_match = re.search(r'(\d{2}/\d{2}/\d{2})', after[:100])
    if date_match:
        result['date'] = date_match.group(1)

    return result


def extract_weight_from_positions(pos_data, isin):
    """Find weight percentage for an ISIN in position data."""
    if not pos_data:
        return ''
    items = pos_data.get('items', [])

    for page_num in range(1, pos_data.get('pages', 0) + 1):
        page_items = [i for i in items if i['p'] == page_num]
        for item in page_items:
            if item['s'].startswith(isin[:8]):
                y = item['y']
                row = [i for i in page_items if abs(i['y'] - y) <= 3]
                # Weight is typically in the rightmost columns
                for ri in sorted(row, key=lambda x: -x['x']):
                    s = ri['s'].replace(',', '.').replace('%', '').strip()
                    try:
                        val = float(s)
                        if 0 < val < 100:
                            return f"{val:.2f}"
                    except:
                        pass
    return ''


def parse_portfolio_pdf(pdf_path):
    """Main entry: parse a portfolio PDF using hybrid approach."""
    # Step 1: Get text and extract ISINs
    text = parse_pdf_text(str(pdf_path))
    if not text:
        return None

    stock_isins = extract_isins_from_text(text)
    if not stock_isins:
        return {'fund_info': {}, 'holdings': [], 'stock_count': 0}

    # Step 2: Get positions and build ticker map
    pos_data = parse_pdf_positions(str(pdf_path))
    ticker_map = extract_ticker_map_from_positions(pos_data)

    # Step 3: Build holdings by combining text + position data
    holdings = []
    for isin in stock_isins:
        ticker = ticker_map.get(isin, '')
        data = extract_data_from_text(text, isin)

        holdings.append({
            'ticker': ticker,
            'isin': isin,
            'nominal': data.get('nominal', ''),
            'unit_price': data.get('unit_price', ''),
            'total_value': data.get('total_value', ''),
            'date': data.get('date', ''),
        })

    # Step 4: Fund info from text
    fund_info = {}
    m = re.search(r'A[\-\.\)]\s*Fonun Adı[^:]*:?\s*(.+?)(?:\n|B[\-\.\)])', text)
    if m: fund_info['fund_name'] = m.group(1).strip()
    m = re.search(r'(?:D|Ç)[\-\.\)]\s*(?:Toplam Değer|TOPLAM DEĞER)[^:]*:?\s*([0-9.,]+)', text)
    if m: fund_info['nav'] = m.group(1).strip()
    m = re.search(r'a[\-\.\)]\s*Hisse Senedi\s*:\s*([0-9.,]+)', text)
    if m: fund_info['stock_pct'] = m.group(1).strip()
    m = re.search(r'(Ocak|Şubat|Mart|Nisan|Mayıs|Haziran|Temmuz|Ağustos|Eylül|Ekim|Kasım|Aralık)\s*(\d{4})', text)
    if m: fund_info['period'] = f"{m.group(1)} {m.group(2)}"

    return {
        'fund_info': fund_info,
        'holdings': holdings,
        'stock_count': len(holdings),
    }


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("pdf_path")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    result = parse_portfolio_pdf(args.pdf_path)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        if result:
            fi = result['fund_info']
            print(f"Fund: {fi.get('fund_name', 'N/A')}")
            print(f"NAV: {fi.get('nav', 'N/A')} | Stocks: {result['stock_count']}")
            for h in result['holdings']:
                print(f"  {h['ticker']:6s} | {h['isin']} | n={h['nominal']:>15s} | p={h['unit_price']:>12s} | {h.get('date','')}")
