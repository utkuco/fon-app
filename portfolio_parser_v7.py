"""
KAP Portfolio Parser v7 - Multi-Format Support
Format A: III-FON PORTFÖY DEĞERİ TABLOSU → A.PAY section'lı (hisse+tahvil+sukuk)
Format B: Doğrudan ISIN'li (sadece hisse, farklı kolon düzeni)
Format C: Yabancı hisse içeren (foreign stocks, tickers)
"""
import fitz, re, json
from pathlib import Path

def is_isin(s):
    return bool(re.match(r'^TR[A-Z0-9]{8,11}$', str(s).strip()))
def is_ticker(s):
    return bool(re.match(r'^[A-Z]{2,8}\.[A-Z]$', str(s).strip()))
def is_pct(s):
    return bool(re.match(r'^[\d,.]+%$', str(s).strip()))
def is_date(s):
    return bool(re.match(r'^\d{2}\.\d{2}\.\d{4}$', str(s).strip()))

def parse_eu_num(s):
    if not s: return 0.0
    s = str(s).strip()
    has_dot = '.' in s
    has_comma = ',' in s
    if has_dot and has_comma:
        dot_idx = s.rfind('.')
        comma_idx = s.rfind(',')
        if dot_idx > comma_idx:
            s = s.replace(',', '')
        else:
            s = s.replace('.', '').replace(',', '.')
    elif has_comma and not has_dot:
        s = s.replace(',', '.')
    try: return float(s)
    except: return 0.0

def is_valid_num(s):
    return parse_eu_num(s) != 0.0

def gf(lines, base, off):
    return lines[base+off].strip() if base+off < len(lines) else ''

SKIP_WORDS = {'TAHVIL','KIRA SERTIFIKASI','Kıymetli Maden',
              'YABANCI TAHVIL','YABANCI KIRA SER','YP HİSSE',
              'BORSA YATIRIM FONLARI','VARANT',
              '0','0.00%','TERS REPO','REPO','MEVDUAT','VADELI',
              'YP MEVDUAT','YATIRIM FONU',
              'B.1.ÖZEL SEKTÖR BORÇLANMA ARAÇLARI',
              'B.2.KAMU SEKTÖRÜ BORÇLANMA ARAÇLARI',
              'ÖZEL SEKTÖR BORÇLANMA ARAÇLARI',
              'KAMU SEKTÖRÜ BORÇLANMA ARAÇLARI',
              'C.KİRA SERTİFİKALARI', 'G.DİĞER VARLIKLAR',
              'F.VARANTLAR', 'E.ALTIN VE DİĞER KIYMETLİ MADENLER'}

def detect_section(line):
    l = line.strip()
    if l == 'A.PAY': return 'A.PAY'
    if 'B.BORÇLANMA' in l: return 'B.BORÇLANMA'
    if 'C.KİRA' in l and 'SERTİFİKA' in l: return 'C.KİRA'
    if 'Ç.TÜREV' in l: return 'Ç.TÜREV'
    if 'D.YABANCI' in l: return 'D.YABANCI'
    if 'E.ALTIN' in l: return 'E.ALTIN'
    if l == 'F.VARANTLAR': return 'F.VARANT'
    if l == 'G.DİĞER VARLIKLAR': return 'G.DİĞER'
    return None

# ─── FORMAT A: III-FON PORTFÖY DEĞERİ TABLOSU ───────────────────────────────
def parse_format_a(lines):
    """Standard format with section headers (A.PAY, B.BORÇLANMA, etc.)"""
    results = []
    section = 'A.PAY'
    i = 0
    
    while i < len(lines):
        line = lines[i].strip()
        new_section = detect_section(line)
        if new_section:
            section = new_section; i += 1; continue
        if not line or line in SKIP_WORDS: i += 1; continue
        
        # A.PAY: Hisse senedi (ticker.ISIN)
        if section == 'A.PAY' and is_ticker(line):
            if i + 13 < len(lines):
                isin = lines[i+2].strip()
                total = lines[i+11].strip()
                if is_isin(isin) and is_valid_num(total):
                    results.append({
                        'type': 'stock', 'ticker': line, 'isin': isin,
                        'issuer': lines[i+1].strip(),
                        'nominal': lines[i+5].strip(),
                        'unit_price': lines[i+10].strip(),
                        'total_value': lines[i+11].strip(),
                        'group_pct': lines[i+12].strip(),
                        'weight_pct': lines[i+13].strip(),
                        'maturity_date': lines[i+6].strip()
                    })
            i += 1; continue
        
        # ISIN satırı: tahvil/sukuk/yabancı/diğer
        if is_isin(line):
            next3 = lines[i+3].strip() if i+3 < len(lines) else ''
            
            if next3 == line:
                # Duplicate block: ISIN(i), issuer(i+1), date(i+2), dup(i+3)...
                issuer = lines[i+1].strip() if i+1 < len(lines) else ''
                
                coupon   = gf(lines, i, 4)
                nominal  = gf(lines, i, 6)
                mkt      = gf(lines, i, 11)
                total    = gf(lines, i, 12)
                grup_pct = gf(lines, i, 13)
                top_pct  = gf(lines, i, 14)
                vade     = gf(lines, i, 2)
                
                if is_valid_num(total):
                    if section == 'B.BORÇLANMA':
                        t = 'gov_bond' if any(x in line for x in ['TRT','TRY','TRS','TRB']) else 'corp_bond'
                    elif section == 'C.KİRA': t = 'sukuk'
                    elif section == 'D.YABANCI': t = 'foreign'
                    elif section == 'G.DİĞER':
                        u = issuer.upper()
                        if 'YATIRIM FONU' in u or ('FON' in u and len(u) < 40): t = 'fund'
                        elif 'MEVDUAT' in u: t = 'deposit'
                        elif 'YP' in u: t = 'foreign_deposit'
                        elif 'VARANT' in u: t = 'warrant'
                        else: t = 'other'
                    else: t = 'other'
                    
                    results.append({
                        'type': t, 'isin': line, 'issuer': issuer,
                        'coupon_pct': coupon, 'nominal': nominal,
                        'unit_price': mkt, 'total_value': total,
                        'group_pct': grup_pct, 'weight_pct': top_pct,
                        'maturity_date': vade
                    })
                
                i += 15; continue
            else:
                # Standalone ISIN
                issuer = lines[i-1].strip() if i > 0 and not is_isin(lines[i-1].strip()) else \
                         lines[i-2].strip() if i > 1 else ''
                total = gf(lines, i, 12)
                if is_valid_num(total):
                    t = 'other'
                    if section == 'B.BORÇLANMA':
                        t = 'gov_bond' if any(x in line for x in ['TRT','TRY','TRS','TRB']) else 'corp_bond'
                    elif section == 'C.KİRA': t = 'sukuk'
                    results.append({
                        'type': t, 'isin': line, 'issuer': issuer,
                        'total_value': total, 'weight_pct': gf(lines, i, 14)
                    })
                i += 1; continue
        
        # Ç.TÜREV
        if section == 'Ç.TÜREV' and ('VIOP' in line.upper() or 'TÜREV TEMİNAT' in line.upper()):
            total = gf(lines, i, 8)
            neg = gf(lines, i, 12)
            if is_valid_num(total):
                results.append({'type': 'derivatives', 'name': line,
                              'total_value': total, 'negotiable_value': neg})
            i += 1; continue
        
        # E.ALTIN
        if section == 'E.ALTIN' and 'KIYMETLİ MADEN' in line.upper():
            total = gf(lines, i, 1)
            if is_valid_num(total):
                results.append({'type': 'gold', 'name': line, 'total_value': total})
            i += 1; continue
        
        i += 1
    
    return results

# ─── FORMAT B: Minimal format (ISIN+number pairs, no section headers) ───────────
def parse_format_b(lines):
    """Minimal format: only ISIN + nominal pairs for stocks"""
    results = []
    # In this format, lines look like:
    # [company+ISIN merged], [nominal], [issuer name], [ISIN], [0.xxx], [next company+ISIN], ...
    # We look for ISIN patterns and try to extract nominal before them
    
    for i, line in enumerate(lines):
        if is_isin(line):
            # Try to find nominal before this ISIN
            nominal = ''
            for back in range(1, 6):
                if i - back < 0: break
                candidate = lines[i - back].strip()
                # Nominals look like "500,000.000" or "2,500,000.000"
                if re.match(r'^[\d,.]+\.\d{3}$', candidate):
                    nominal = candidate
                    break
            
            issuer = lines[i-1].strip() if i > 0 and not is_isin(lines[i-1].strip()) else \
                     lines[i-3].strip() if i > 2 else ''
            
            if is_valid_num(nominal):
                # This is likely a stock
                results.append({
                    'type': 'stock', 'isin': line,
                    'issuer': issuer, 'nominal': nominal,
                    'total_value': nominal
                })
    
    return results

# ─── MAIN PARSER ───────────────────────────────────────────────────────────────
def parse_pdf(pdf_path):
    doc = fitz.open(pdf_path)
    full_text = "".join(p.get_text() for p in doc)
    
    ts = full_text.find("III-FON PORTFÖY DEĞERİ TABLOSU")
    if ts >= 0:
        te = full_text.find("FON TOPLAM DEĞERİ", ts)
        table = full_text[ts:te if te > 0 else ts+40000]
        lines = table.split('\n')
        return parse_format_a(lines)
    
    # Try alternate header
    alt_marker = full_text.find("III-FON PORTFOY DEGERI TABLOSU")
    if alt_marker >= 0:
        lines = full_text[alt_marker:].split('\n')
        return parse_format_b(lines)
    
    # Fallback: try to find A.PAY section
    apay_idx = full_text.find("A.PAY")
    if apay_idx >= 0:
        lines = full_text[apay_idx:apay_idx+30000].split('\n')
        return parse_format_a(lines)
    
    # Last resort: format B (ISIN-based)
    if is_isin(full_text.split('\n')[0] if full_text.split('\n') else ''):
        lines = full_text.split('\n')
        return parse_format_b(lines)
    
    return []

def parse_fund_info(pdf_path):
    doc = fitz.open(pdf_path)
    text = "".join(p.get_text() for p in doc)
    info = {}
    m = re.search(r'FONUN ADI:\s*\n?\s*(.+?)(?=\n\s*[A-ZÇ]\.|\n\s*\n|$)', text, re.S)
    if m: info['fund_name'] = m.group(1).strip().split('\n')[0]
    m = re.search(r'KURUCUNUN ÜNVANI:\s*\n?\s*(.+?)(?=\n\s*[A-ZÇ]\.|\n\s*\n|$)', text, re.S)
    if m: info['manager'] = m.group(1).strip().split('\n')[0]
    m = re.search(r'(\d{2}/\d{2}/\d{4})\s*ve\s*(\d{2}/\d{2}/\d{4})', text)
    if m: info['report_date'] = m.group(2).strip()
    m = re.search(r'TOPLAM DEĞER:\s*\(TL\)\s*\n?\s*([\d,.]+)', text)
    if m: info['total_value'] = m.group(1).strip()
    return info

if __name__ == '__main__':
    pdf_dir = Path(__file__).parent / 'pdfs' / 'portfoy_dagilim'
    output_dir = Path(__file__).parent / 'parsed_v7'
    output_dir.mkdir(exist_ok=True)
    
    pdf = pdf_dir / 'GAH_4028328d.pdf'
    info = parse_fund_info(str(pdf))
    holdings = parse_pdf(str(pdf))
    
    print(f"✅ {pdf.name}")
    print(f"   Fon: {info.get('fund_name', '?')}")
    print(f"   Tarih: {info.get('report_date', '?')} | Toplam: {info.get('total_value', '?')} TL")
    
    by_type = {}
    for h in holdings:
        by_type.setdefault(h['type'], []).append(h)
    
    print(f"\n   Varlıklar ({len(holdings)} satır):")
    grand_total = 0
    for t in sorted(by_type.keys()):
        vals = sum(parse_eu_num(h.get('total_value','0')) for h in by_type[t])
        grand_total += vals
        print(f"     [{t}] {len(by_type[t]):3d} adet | {vals:>20,.2f} TL")
        for h in by_type[t][:3]:
            key = h.get('isin') or h.get('ticker') or h.get('name','')
            issuer = h.get('issuer','') or h.get('name','')
            print(f"       {str(key):16s} | {str(issuer)[:30]:30s} | {h.get('total_value',''):>18s}")
    
    print(f"\n   📊 Parse edilen toplam: {grand_total:,.2f} TL")
    
    out = output_dir / 'GAH_4028328d.json'
    with open(out, 'w') as f:
        json.dump({'info': info, 'holdings': holdings}, f, ensure_ascii=False, indent=2)
    print(f"\n   💾 Kaydedildi: {out}")
