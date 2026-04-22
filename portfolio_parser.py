"""
KAP Portfolio Parser v12 - FORMAT-AWARE SPATIAL PARSER
======================================================
Detects PDF format from raw text patterns, then applies
the correct X-position mapping for each format.

Formats:
  Type A (GAH): Ticker.E + ISIN columns, TL at X=517-522
  Type D (GAL): GovBond codes only, no ISIN, TL at X=509-518
  Type F (AN1/APBDL): ISIN-first format
  Type C (GPF): Katılım fon, different structure
"""
import fitz, re
from pathlib import Path
from collections import defaultdict

ISIN_RE = re.compile(r'^[A-Z]{2}[A-Z0-9]{10}$')
TICKER_E_RE = re.compile(r'^[A-Z]{2,8}\.[A-Z]$')
GOV_BOND_RE = re.compile(r'^TRT[0-9]{10}T[0-9]{2}$')

def parse_eu_num(s):
    if not s: return 0.0
    s = str(s).strip()
    has_dot = '.' in s; has_comma = ',' in s
    if has_dot and has_comma:
        dot_idx = s.rfind('.'); comma_idx = s.rfind(',')
        s = s.replace(',','') if dot_idx > comma_idx else s.replace('.','').replace(',','.')
    elif has_comma and not has_dot: s = s.replace(',','.')
    try: return float(s)
    except: return 0.0

def is_valid_num(s): return parse_eu_num(s) != 0.0
def clean(s): return re.sub(r'[\xa0\t]+', ' ', str(s).strip())

def detect_format(pdf_path):
    """Detect PDF format from raw text patterns."""
    doc = fitz.open(pdf_path)
    text = "".join(p.get_text() for p in doc)
    doc.close()

    lines = text.split('\n')

    # Type D: No ISINs, government bond codes (TRT...) appear as primary identifiers
    trt_count = sum(1 for l in lines if GOV_BOND_RE.match(l.strip()))
    isin_count = sum(1 for l in lines if ISIN_RE.match(l.strip()))
    ticker_count = sum(1 for l in lines if TICKER_E_RE.match(l.strip()))

    # Check for ISIN-less format (Type D)
    if trt_count > 5 and isin_count < 5 and ticker_count < 3:
        return 'D'  # Gov bond format

    # Check for ISIN-first format (Type F - AN1/APBDL)
    # These have ISINs but no tickers
    if isin_count > 5 and ticker_count < 3:
        return 'F'  # ISIN-first format

    # Check for ticker-first format (Type A - GAH)
    if ticker_count > 5:
        return 'A'  # Ticker-first format

    # Default to Type A
    return 'A'

# ── Format-specific column positions ──────────────────────────────────────────
# Type A (GAH): Stock tickers + ISIN
COLS_A = {
    'tl_min': 517, 'tl_max': 522,
    'wt_min': 541, 'wt_max': 555,
    'is_isin_based': False,
}

# Type D (GAL): Gov bonds, no ISIN, bond codes at X=18
COLS_D = {
    'tl_min': 509, 'tl_max': 520,
    'wt_min': 539, 'wt_max': 545,
    'is_isin_based': False,
    'bond_code_x': (14, 25),  # Government bond code range
    'issuer_x': (97, 130),
}

# Type F (AN1/APBDL): ISIN-first, no tickers
COLS_F = {
    'is_isin_based': True,
}

SECTION_MAP = {
    'A.PAY SENEDİ': 'A.PAY', 'A.PAY': 'A.PAY', 'PAY SENEDİ': 'A.PAY',
    'ÖZEL SEKTÖR BORÇLANMA': 'B.BORÇLANMA', 'KAMU SEKTÖRÜ BORÇLANMA': 'B.BORÇLANMA',
    'BORÇLANMA ARAÇLARI': 'B.BORÇLANMA',
    'KİRA SERTİFİKALARI': 'C.KİRA', 'KİRA SERTİFİKASI': 'C.KİRA',
    'TÜREV ARAÇLAR': 'Ç.TÜREV',
    'YABANCI SERMAYE': 'D.YABANCI', 'YABANCI MENKUL': 'D.YABANCI',
    'ALTIN': 'E.ALTIN', 'KIYMETLİ MADENLER': 'E.ALTIN',
    'VARANTLAR': 'F.VARANT',
    'DİĞER VARLIKLAR': 'G.DİĞER',
}

def detect_section(text):
    t = text.upper()
    for kw, sec in SECTION_MAP.items():
        if kw in t: return sec
    return None

def classify(isin, section, issuer=''):
    iss = issuer.upper()
    if section == 'A.PAY': return 'stock'
    if section == 'C.KİRA': return 'sukuk'
    if section == 'D.YABANCI': return 'foreign'
    if section == 'E.ALTIN': return 'gold'
    if section == 'Ç.TÜREV': return 'derivatives'
    if section == 'F.VARANT': return 'warrant'
    if section == 'B.BORÇLANMA':
        if isinstance(isin, str) and isin.startswith(('TRT','TRY','TRB')):
            return 'gov_bond'
        return 'corp_bond'
    if section == 'G.DİĞER':
        if any(k in iss for k in ('BIST','BORSA','TAKASBANK')): return 'reverse_repo'
        if 'YATIRIM FONU' in iss or ('FON' in iss and len(iss) < 50): return 'fund'
        if 'MEVDUAT' in iss: return 'deposit'
        if 'YP' in iss: return 'foreign_deposit'
        if 'VARANT' in iss: return 'warrant'
        return 'other'
    return 'other'

def get_largest_val_in_range(row_by_x, x_min, x_max, min_val=1000):
    """Get the largest numeric value within X range."""
    best = ''; best_val = 0.0
    for x in sorted(row_by_x.keys()):
        if x_min <= x <= x_max:
            v = row_by_x[x]
            if is_valid_num(v):
                val = parse_eu_num(v)
                if val >= min_val and val > best_val:
                    best_val = val; best = v
    return best

def get_val_in_range_pct(row_by_x, x_min, x_max):
    """Get the first percentage value within X range. Handles both '12.34%' and raw '12.34'."""
    candidates = []
    for x in sorted(row_by_x.keys()):
        if x_min <= x <= x_max:
            v = row_by_x[x]
            if not v: continue
            # Has % sign
            if '%' in v:
                candidates.append((x, v))
            # Raw decimal that looks like a percentage (0-100)
            else:
                try:
                    val = parse_eu_num(v)
                    if 0 <= val <= 100 and val != 0:
                        candidates.append((x, v))
                except: pass
    return candidates[0][1] if candidates else ''

def parse_pdf(pdf_path):
    try:
        fmt = detect_format(pdf_path)
    except Exception:
        return []
    try:
        doc = fitz.open(pdf_path)
    except Exception:
        return []
    all_words = []
    for page in doc:
        for w in page.get_text("words"):
            all_words.append(w)

    lines_by_y = defaultdict(list)
    for w in all_words:
        x0, y0, x1, y1, text, *_ = w
        lines_by_y[round(y0)].append((x0, x1, clean(text)))

    sorted_ys = sorted(lines_by_y.keys())

    # ── Find section regions ──
    section_regions = []
    cur_sec = 'A.PAY'
    for y in sorted_ys:
        line_text = ' '.join(w[2] for w in lines_by_y[y])
        sec = detect_section(line_text)
        if sec:
            if section_regions:
                section_regions[-1] = (section_regions[-1][0], y - 1, section_regions[-1][2])
            cur_sec = sec
            section_regions.append((y, 99999, sec))

    if section_regions:
        section_regions[-1] = (section_regions[-1][0], sorted_ys[-1], section_regions[-1][2])

    # ── Find table start ──
    table_start = 0
    for y in sorted_ys:
        if 'III-FON' in ' '.join(w[2] for w in lines_by_y[y]).upper():
            table_start = y; break
    if table_start == 0:
        table_start = sorted_ys[0] if sorted_ys else 0

    results = []
    seen_ids = set()  # Track unique identifiers

    for y in sorted_ys:
        if y < table_start + 10: continue

        words = sorted(lines_by_y[y], key=lambda w: w[0])
        if not words: continue

        all_text = ' '.join(w[2] for w in words)
        if not all_text.strip(): continue

        word_texts = [w[2] for w in words]
        isins = [t for t in word_texts if ISIN_RE.match(t)]
        tickers = [t for t in word_texts if TICKER_E_RE.match(t)]
        gov_bonds = [t for t in word_texts if GOV_BOND_RE.match(t)]

        # Skip non-data lines
        if not isins and not tickers and not gov_bonds: continue
        if detect_section(all_text): continue

        row_by_x = {w[0]: w[2] for w in words}

        # Determine section
        section = 'A.PAY'
        for sy, ey, sec in section_regions:
            if sy <= y <= ey: section = sec; break

        def scan_for_best_values(row_by_x):
            """Scan all X positions to find TL total and weight %."""
            # Collect all numeric values > 1000 at X > 400
            big_vals = [(x, v) for x, v in sorted(row_by_x.items())
                        if x > 400 and is_valid_num(v) and parse_eu_num(v) > 1000]
            # Collect percentages at X > 400
            pcts = [(x, v) for x, v in sorted(row_by_x.items())
                    if x > 400 and '%' in v]

            tv = max(big_vals, key=lambda item: parse_eu_num(item[1]))[1] if big_vals else ''
            wp = pcts[0][1] if pcts else ''
            return tv, wp

        # ── Type A: Ticker-first (GAH) ──
        if fmt == 'A' and tickers:
            ticker = tickers[0]
            uid = f't:{ticker}'
            if uid in seen_ids: continue
            seen_ids.add(uid)

            isin = next((w[2] for w in words if ISIN_RE.match(w[2])), '')

            # Try known TL column positions for Type A
            tv = get_largest_val_in_range(row_by_x, 517, 522)
            if not tv: tv = get_largest_val_in_range(row_by_x, 510, 530)
            wp = get_val_in_range_pct(row_by_x, 541, 555)
            if not wp: wp = get_val_in_range_pct(row_by_x, 530, 570)

            # Fallback: scan
            if not is_valid_num(tv) or not wp:
                tv2, wp2 = scan_for_best_values(row_by_x)
                if not is_valid_num(tv): tv = tv2
                if not wp: wp = wp2

            if isin and (is_valid_num(tv) or is_valid_num(wp)):
                results.append({
                    'type': 'stock', 'ticker': ticker, 'isin': isin,
                    'total_value': tv, 'weight_pct': wp,
                    'section': section,
                })

        # ── Type D: Gov bond codes (GAL) ──
        elif fmt == 'D' and gov_bonds:
            bond = gov_bonds[0]
            uid = f'b:{bond}'
            if uid in seen_ids: continue
            seen_ids.add(uid)

            tv = get_largest_val_in_range(row_by_x, 509, 520)
            if not tv: tv = get_largest_val_in_range(row_by_x, 500, 530)
            wp = get_val_in_range_pct(row_by_x, 539, 545)
            if not wp: wp = get_val_in_range_pct(row_by_x, 530, 560)

            # Fallback: scan
            if not is_valid_num(tv) or not wp:
                tv2, wp2 = scan_for_best_values(row_by_x)
                if not is_valid_num(tv): tv = tv2
                if not wp: wp = wp2

            if is_valid_num(tv) or is_valid_num(wp):
                asset_t = classify(bond, section, '')

                # Get issuer name
                issuer = ''
                for x in sorted(row_by_x.keys()):
                    if 97 <= x <= 130:
                        v = row_by_x[x]
                        if v and not ISIN_RE.match(v) and v not in ('T','BIST','A.Ş','T.C.'):
                            issuer += v + ' '
                issuer = issuer.strip()

                results.append({
                    'type': asset_t, 'isin': bond,
                    'issuer': issuer[:60] if issuer else bond,
                    'total_value': tv, 'weight_pct': wp,
                    'section': section,
                })

        # ── ISIN-based rows (Type F, GRO, and generic) ──
        elif isins:
            # For GRO: ISIN at X~215, TL at X~494, WT at X~526
            # For AN1: ISIN at X~242, TL at X~424, WT at X~523
            # Determine ISIN position to identify format variant
            isin_word = next(w for w in words if ISIN_RE.match(w[2]))
            isin_x = isin_word[0]

            isin = isins[0]
            uid = f'i:{isin}'
            if uid in seen_ids: continue
            seen_ids.add(uid)

            # Try format-specific positions, then scan
            if 200 <= isin_x <= 230:
                # GRO-style (X~215) and APBDL-style (X~224)
                tv = get_largest_val_in_range(row_by_x, 490, 500)
                if not tv: tv = get_largest_val_in_range(row_by_x, 480, 510)
                wp = get_val_in_range_pct(row_by_x, 470, 560)  # covers GRO (526), GRATIS (480-545)
                if not wp: wp = get_val_in_range_pct(row_by_x, 700, 900)  # GRATIS-style: X=832-896
            elif 230 <= isin_x <= 250:
                # AN1-style: ISIN at X~242, TL at X~424, WT at X~484/523
                tv = get_largest_val_in_range(row_by_x, 410, 430)
                if not tv: tv = get_largest_val_in_range(row_by_x, 400, 450)
                wp = get_val_in_range_pct(row_by_x, 470, 560)  # Weight at X=484 and X=523
                if not wp: wp = get_val_in_range_pct(row_by_x, 700, 900)  # Rare fallback
            else:
                # Generic: scan
                tv, wp = scan_for_best_values(row_by_x)

            # Final fallback: scan all
            if not is_valid_num(tv) or not wp:
                tv2, wp2 = scan_for_best_values(row_by_x)
                if not is_valid_num(tv): tv = tv2
                if not wp: wp = wp2

            if is_valid_num(tv) or is_valid_num(wp):
                asset_t = classify(isin, section, '')

                # Issuer from surrounding words
                issuer = ''
                for w in words:
                    x0 = w[0]
                    txt = w[2]
                    if 90 <= x0 <= 240 and txt and not ISIN_RE.match(txt):
                        if not any(c.isdigit() for c in txt) and len(txt) > 2:
                            issuer += txt + ' '
                issuer = issuer.strip()

                results.append({
                    'type': asset_t, 'isin': isin,
                    'issuer': issuer[:60] if issuer else '',
                    'total_value': tv, 'weight_pct': wp,
                    'section': section,
                })

    doc.close()
    return results

def parse_fund_info(pdf_path):
    try:
        doc = fitz.open(pdf_path)
        text = "".join(p.get_text() for p in doc)
        doc.close()
    except Exception:
        return {}
    info = {}

    m = re.search(r'FONUN ADI:\s*\n?\s*(.+?)(?=\n\s*[A-ZÇ]\.)', text, re.S)
    if not m: m = re.search(r'FONUN\s+ADI[:\s]+(.+?)(?=\n|$)', text, re.S)
    if m: info['fund_name'] = m.group(1).strip().split('\n')[0]

    m = re.search(r'KURUCUNUN ÜNVANI:\s*\n?\s*(.+?)(?=\n\s*[A-ZÇ]\.)', text, re.S)
    if not m: m = re.search(r'KURUCUNUN\s+ÜNVANI[:\s]+(.+?)(?=\n|$)', text, re.S)
    if m: info['manager'] = m.group(1).strip().split('\n')[0]

    m = re.search(r'(\d{2}/\d{2}/\d{4})\s*ve\s*(\d{2}/\d{2}/\d{4})', text)
    if m: info['report_date'] = m.group(2).strip()

    m = re.search(r'TOPLAM DEĞER:\s*\(TL\)\s*\n?\s*([\d,.]+)', text)
    if not m: m = re.search(r'TOPLAM DEĞER:\s*\n?\s*([\d,.]+)', text)
    if m: info['total_value'] = m.group(1).strip()

    return info

if __name__ == '__main__':
    import sys
    from collections import defaultdict

    pdf_dir = Path(__file__).parent / 'pdfs' / 'portfoy_dagilim'
    verbose = '--verbose' in sys.argv

    if len(sys.argv) > 1 and not sys.argv[1].startswith('--'):
        pdfs = [Path(a) for a in sys.argv[1:] if not a.startswith('--')]
    else:
        pdfs = sorted(pdf_dir.glob('*.pdf'))

    ok, fail = 0, 0
    for pdf in pdfs:
        try:
            fmt = detect_format(str(pdf))
            info = parse_fund_info(str(pdf))
            holdings = parse_pdf(str(pdf))
        except Exception as e:
            fail += 1; continue

        by_type = defaultdict(list)
        for h in holdings: by_type[h.get('type','?')].append(h)

        grand = sum(parse_eu_num(h.get('total_value','0')) for h in holdings)
        types_str = ' '.join(f'[{t}]{len(v)}' for t,v in sorted(by_type.items()))
        status = '✓' if len(holdings) > 0 else '✗'

        print(f'{status} [{fmt}] {pdf.name[:25]:25s} | {len(holdings):3d} | {grand:>18,.0f} TL | {types_str}')
        if verbose and len(holdings) > 0:
            print(f'  → {info.get("fund_name","?")[:40]} | {info.get("report_date","?")}')
            for t, items in sorted(by_type.items()):
                for h in items[:2]:
                    key = (h.get('ticker') or h.get('isin') or '')[:12]
                    tv = h.get('total_value','')[:18]
                    wp = h.get('weight_pct','')[:10]
                    print(f'    [{t}] {key:14s} TL={tv:20s} WT={wp}')
        if len(holdings) > 0: ok += 1

    print(f'\n{ok} OK, {fail} failed')
