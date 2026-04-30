#!/usr/bin/env python3
"""
KAP Portfolio Parser v6 - Fixed Position Arithmetic
===================================================
Uses absolute positions throughout. Key insight:
  Each row has ISIN appearing TWICE with issuer/date between them.
  Bond row: ISIN ISSUER DATE ISIN COUPON% #NOM PRICE DATE ... VALUE GROUP% TOTAL%
"""

import json, os, re, subprocess
from pathlib import Path

PROJECT_DIR = Path(__file__).parent

def run_node(script, args, timeout=60):
    r = subprocess.run(["node", str(script)] + args, capture_output=True, text=True, timeout=timeout)
    return r.stdout

def parse_pdf_text(pdf_path):
    return run_node(PROJECT_DIR / "parse_pdf.mjs", [str(pdf_path)])

def parse_pdf_positions(pdf_path, out_path=None):
    if out_path is None:
        out_path = f"/tmp/pos6f_{Path(pdf_path).stem}.json"
    subprocess.run(["node", str(PROJECT_DIR / "parse_pdf_positions.mjs"), str(pdf_path), out_path],
                   capture_output=True, text=True, timeout=60)
    if os.path.exists(out_path):
        with open(out_path) as f:
            return json.load(f)
    return None


# ─── Helpers ──────────────────────────────────────────────────────

def tl(s):
    if not s: return None
    s = s.strip().replace('%','').replace(' ','')
    s = s.replace('.','').replace(',','.')
    try: return float(s)
    except: return None

def parse_dt(s):
    if not s: return None
    m = re.search(r'(\d{1,2})[/.-](\d{1,2})[/.-](\d{2,4})', s)
    if not m: return None
    d,mo,y = m.group(1),m.group(2),m.group(3)
    if len(y)==2: y='20'+y if int(y)<50 else '19'+y
    return f"{d.zfill(2)}/{mo.zfill(2)}/{y}"

TL_NUM = re.compile(r'[\d]{1,3}(?:[.,][\d]{3})*(?:[.,]\d+)?')

def tl_nums(text, mx=10):
    out=[]
    for m in TL_NUM.finditer(text):
        v=tl(m.group(0))
        if v is not None and abs(v)>=1: out.append(v)
        if len(out)>=mx: break
    return out

def pct_vals(text):
    return [tl(p) for p in re.findall(r'([\d]+[.,]\d{1,3})\s*%', text)]

def isin_type(isin):
    t={'TRA':'stock','TRE':'stock','TRT':'gov_bond','TRB':'treasury_bill',
       'TRS':'corp_bond','TRF':'corp_bond','TRD':'sukuk','TRP':'asset_backed',
       'TRK':'gold','TRX':'stock','TRY':'fund',
       'US':'etf_foreign','IE':'etf_foreign','LU':'etf_foreign','DE':'etf_foreign',
       'FR':'etf_foreign','NL':'etf_foreign','CH':'etf_foreign','GB':'etf_foreign',
       'XAU':'gold','AU995':'gold'}
    for p,at in t.items():
        if isin.startswith(p): return at
    return 'unknown'

def clean_issuer(s):
    return re.sub(r'\s+',' ', s).strip()[:100]


# ─── Section positions (absolute) ────────────────────────────────

def find_sections(text):
    """Find absolute positions of all major sections."""
    sections = {}
    patterns = [
        ('stocks',    re.compile(r'\.?A\.?PAY')),
        ('corp_bonds', re.compile(r'B\.?1\.?\s*[\ÖO]ZEL\s+SEKT', re.I)),
        ('gov_bonds',  re.compile(r'B\.?2\.?\s*KAMU\s+SEKT', re.I)),
        ('sukuk',      re.compile(r'C\.?KİRA\s+SERT', re.I)),
        ('foreign',    re.compile(r'D\.?YABANCI', re.I)),
        ('gold',       re.compile(r'E\.?ALTIN', re.I)),
        ('repo_dep',   re.compile(r'G\.?DİĞER\s+VARLIKLAR', re.I)),
        ('futures',    re.compile(r'FUTURES\s*SÖZLEŞMELERİ', re.I)),
    ]
    for key, pat in patterns:
        m = pat.search(text)
        if m:
            sections[key] = m.start()
    return sections

def next_section_start(text, after_pos):
    """Find the next section marker after a position."""
    # Section markers are Roman-lettered sections (B., C., Ç., D., E., F., G., etc.)
    m = re.search(r'\n[BCÇDEFGHİI]\.\s', text[after_pos:])
    if m:
        return after_pos + m.start()
    return len(text)


# ─── Build ticker map from positions ─────────────────────────────

def build_ticker_map(pos):
    """ISIN → {ticker, issuer} from layout."""
    if not pos: return {}
    imap={}
    items=pos.get('items',[])
    for pg in range(1,pos.get('pages',0)+1):
        pg_items=[i for i in items if i['p']==pg]
        bands={}
        for it in pg_items:
            k=round(it['y']/4)*4; bands.setdefault(k,[]).append(it)
        for row in bands.values():
            row.sort(key=lambda x:x['x'])
            isin_it=None; tick_it=None; iss_parts=[]
            isin_x=None
            for it in row:
                s=it['s'].strip()
                if not s: continue
                x=it['x']
                if s.startswith(('TRA','TRE')) and len(s)>=6:
                    isin_it=it; isin_x=x
                elif (x<90 and 2<=len(s)<=6 and s.isupper() and
                      s not in ('TL USD EUR GBP CHF JPY CNY TRY AU1 XAU BPP TPP TRT TRB TRF TRS TRD TRP TRK TRX TRM F_ VIOP OTC REP VAR GOS GES VDMK YP'.split())):
                    tick_it=it
                elif isin_x and 90<x<isin_x-10 and len(s)>2:
                    iss_parts.append((x,s))
            if isin_it:
                isin=isin_it['s'][:12]
                issuer=clean_issuer(' '.join(p for _,p in sorted(iss_parts)))
                tick=tick_it['s'] if tick_it else ''
                if isin not in imap: imap[isin]={'ticker':tick,'issuer':issuer}
    return imap


# ─── Bond row parser (FIXED: uses absolute positions) ────────────

def parse_bonds_in_range(text, start, end, tmap, section_key):
    """
    Parse bonds/sukuk in a text range.
    Row format: ISIN ISSUER DATE ISIN COUPON% #NOM PRICE DATE ... VALUE GROUP% TOTAL%
    We extract from AFTER the SECOND ISIN occurrence.
    """
    holdings=[]
    section_text = text[start:end]
    # Find all ISINs
    isin_positions = [(m.start(), m.group(1))
                     for m in re.finditer(r'(TR[A-Z0-9]{10})', section_text)]

    # Find pairs (where ISIN appears twice in a row)
    i = 0
    while i < len(isin_positions):
        pos1_abs = start + isin_positions[i][0]
        isin1 = isin_positions[i][1]
        isin2 = None
        pos2_abs = None

        # Look ahead for second ISIN occurrence (same ISIN, within ~250 chars)
        if i+1 < len(isin_positions):
            pos2_rel = isin_positions[i+1][0]
            pos2_abs = start + pos2_rel
            if (pos2_abs - pos1_abs) < 250 and isin_positions[i+1][1] == isin1:
                isin2 = isin1
                i += 2  # skip both
            else:
                i += 1
        else:
            i += 1

        # Text window: from ~200 before first ISIN to 400 after
        row_start = max(0, pos1_abs - 200)
        row_end = (pos2_abs + 400) if pos2_abs else (pos1_abs + 400)
        row = text[row_start:row_end]

        # After second ISIN (or first if no pair): COUPON% #NOM PRICE DATE ... VALUE GROUP% TOTAL%
        if isin2 and pos2_abs:
            after_isin_text = text[pos2_abs+12:pos2_abs+450]
            between_text = text[pos1_abs+12:pos2_abs]
        else:
            after_isin_text = text[pos1_abs+12:pos1_abs+400]
            between_text = ''

        nums = tl_nums(after_isin_text, 12)
        dts = re.findall(r'\d{2}[/.-]\d{2}[/.-]\d{2,4}', after_isin_text)
        pcts = pct_vals(after_isin_text)

        # Fields from between-ISIN text (issuer, maturity date)
        between_nums = tl_nums(between_text, 6)
        between_dates = re.findall(r'\d{2}[/.-]\d{2}[/.-]\d{2,4}', between_text)
        # Issuer from between text
        iss_m = re.search(r'([A-ZÇĞİÖŞÜ][A-Za-zÇĞİÖŞÜçğıöşü\s\.&,]{3,80}?)(?:\s+(?:TR|\d{2}[/.-]))', between_text)
        issuer = clean_issuer(iss_m.group(1)) if iss_m else ''

        # For bonds: nominal and unit_price are in the between-text or early after
        nominal = between_nums[0] if between_nums else None
        unit_price = between_nums[1] if len(between_nums)>1 else None

        # maturity date from between dates
        maturity = parse_dt(between_dates[0]) if between_dates else None

        # Total value: look for large number after ISIN (usually far right)
        # pcts are coupon%, group%, total% — coupon is first, total weight is last
        coupon = pcts[0] if pcts and pcts[0] and pcts[0]<50 else None
        weight = pcts[-1] if pcts else None

        # total_value: usually one of the large numbers
        total_value = nums[-3] if len(nums)>=3 else None

        atype = isin_type(isin1)
        if atype == 'unknown': atype = 'corp_bond' if section_key in ('corp_bonds','sukuk') else 'gov_bond'

        holdings.append({
            'asset_type': atype,
            'isin': isin1,
            'ticker': '',
            'issuer': issuer,
            'nominal': nominal,
            'unit_price': unit_price,
            'total_value': total_value,
            'weight_pct': weight,
            'currency': 'TL',
            'maturity_date': maturity,
            'coupon_rate': coupon,
            'purchase_date': parse_dt(dts[-1]) if len(dts)>1 else None,
        })

    return holdings


# ─── Stock parser ─────────────────────────────────────────────────

def parse_stocks_in_range(text, start, end, tmap):
    """
    Stock row: TICKER. ISSUER ISIN [no double ISIN for stocks]
    Actually stocks DO have double ISIN — the ISIN appears twice per row.
    TICKER. ISSUER ISIN [fields] ISIN [fields]
    """
    holdings=[]
    section_text = text[start:end]

    # Each unique ISIN starts a new row (first occurrence in that row)
    # Strategy: find all ISIN occurrences, for each see if preceded by ticker
    isin_positions = [(m.start(), m.group(1))
                       for m in re.finditer(r'(TR[A-Z0-9]{10})', section_text)]

    # Find row boundaries: group ISINs that are within 400 chars of each other
    rows = []
    i = 0
    while i < len(isin_positions):
        row_start_abs = start + isin_positions[i][0]
        # Group consecutive ISINs within 400 chars
        row_isins = []
        j = i
        while j < len(isin_positions) and (start + isin_positions[j][0]) - row_start_abs < 400:
            row_isins.append(isin_positions[j])
            j += 1
        row_end_abs = start + isin_positions[j-1][0] + 300 if j < len(isin_positions) else start + isin_positions[-1][0] + 400

        # For stocks: first ISIN is the "key" ISIN
        # Text before it: TICKER. ISSUER
        row_text_before = text[max(0, row_start_abs-150):row_start_abs]
        row_text_after = text[row_start_abs+12:row_end_abs]

        isin = row_isins[0][1]

        # Extract ticker from before ISIN
        ticker = ''
        tmap_info = tmap.get(isin, {})
        ticker = tmap_info.get('ticker','')
        if not ticker:
            tm = re.search(r'\b([A-Z]{2,6})\.[A-Z]\b', row_text_before)
            if tm: ticker = tm.group(1)

        # Issuer from ticker map
        issuer = tmap_info.get('issuer','')
        if not issuer:
            # From before ISIN
            im = re.search(r'[A-Z]{2,6}\.[A-Z]\s+(.+?)\s+'+re.escape(isin[:8]), row_text_before)
            if im: issuer = clean_issuer(im.group(1))

        nums = tl_nums(row_text_after, 8)
        dts = re.findall(r'\d{2}[/.-]\d{2}[/.-]\d{2,4}', row_text_after)
        pcts = pct_vals(row_text_after)

        nominal = nums[0] if len(nums)>0 else None
        unit_price = nums[1] if len(nums)>1 else None
        total_value = nums[2] if len(nums)>2 else None
        weight = pcts[-1] if pcts else None

        holdings.append({
            'asset_type': 'stock',
            'isin': isin,
            'ticker': ticker,
            'issuer': issuer,
            'nominal': nominal,
            'unit_price': unit_price,
            'total_value': total_value,
            'weight_pct': weight,
            'currency': 'TL',
            'maturity_date': None,
            'coupon_rate': None,
            'purchase_date': parse_dt(dts[-1]) if dts else None,
        })
        i = j

    return holdings


# ─── Gold ─────────────────────────────────────────────────────────

def parse_gold_range(text, start, end):
    holdings=[]
    section = text[start:end]
    for m in re.finditer(r'(TRKAU\d{8}|XAU\d{3}|AU995\.\w{2})', section):
        isin = m.group(1)
        after = section[m.end():m.end()+200]
        before = section[max(0,m.start()-30):m.start()]
        nums = tl_nums(after, 6)
        pcts = pct_vals(after)
        holdings.append({
            'asset_type':'gold','isin':isin,'ticker':'XAU','issuer':clean_issuer(before),
            'nominal':nums[0] if nums else None,
            'unit_price':nums[1] if len(nums)>1 else None,
            'total_value':nums[2] if len(nums)>2 else None,
            'weight_pct':pcts[-1] if pcts else None,
            'currency':'TL','maturity_date':None,'coupon_rate':None,'purchase_date':None,
        })
    return holdings


# ─── Foreign ETFs ─────────────────────────────────────────────────

def parse_foreign_range(text, start, end):
    holdings=[]
    section = text[start:end]
    for m in re.finditer(r'\b((?:US|IE|LU|DE|FR|NL|CH|GB)[A-Z0-9]{6,10})\b', section):
        isin = m.group(1)
        after = section[m.end():m.end()+200]
        before = section[max(0,m.start()-80):m.start()]
        nums = tl_nums(after, 6)
        pcts = pct_vals(after)
        nm = re.search(r'([A-Z][A-Za-z\s&\.,]+?)\s+'+re.escape(isin[:4]), before)
        holdings.append({
            'asset_type':'etf_foreign','isin':isin,'ticker':'',
            'issuer':clean_issuer(nm.group(1)) if nm else '',
            'nominal':nums[0] if nums else None,
            'unit_price':nums[1] if len(nums)>1 else None,
            'total_value':nums[2] if len(nums)>2 else None,
            'weight_pct':pcts[-1] if pcts else None,
            'currency':'USD','maturity_date':None,'coupon_rate':None,'purchase_date':None,
        })
    return holdings


# ─── Repo / Deposits / Funds ───────────────────────────────────────

def parse_repo_dep_range(text, start, end):
    holdings=[]
    section = text[start:end]

    # TERS REPO: TRT ISIN followed by BIST, then value/weight
    for m in re.finditer(r'TRT[A-Z0-9]{10}', section):
        isin = m.group(1)
        after = section[m.end():m.end()+300]
        nums = tl_nums(after, 6)
        dts = re.findall(r'\d{2}[/.-]\d{2}[/.-]\d{2,4}', after)
        pcts = pct_vals(after)
        holdings.append({'asset_type':'repo','isin':isin,'ticker':'','issuer':'HAZİNE/BIST',
            'nominal':nums[0] if len(nums)>0 else None,
            'unit_price':nums[1] if len(nums)>1 else None,
            'total_value':nums[2] if len(nums)>2 else None,
            'weight_pct':pcts[-1] if pcts else None,
            'currency':'TL','maturity_date':parse_dt(dts[0]) if dts else None,
            'coupon_rate':None,'purchase_date':None})

    # VADELI MEVDUAT: bank name before date
    for m in re.finditer(r'VADE[LİI]?\s*T\s+([A-ZÇĞİÖŞÜ\s\.]+?)\s+(\d{2}[/.-]\d{2}[/.-]\d{2,4})', section):
        bank = m.group(1).strip()
        block = section[m.start():m.start()+400]
        nums = tl_nums(block, 6)
        dts = re.findall(r'\d{2}[/.-]\d{2}[/.-]\d{2,4}', block)
        pcts = pct_vals(block)
        holdings.append({'asset_type':'deposit','isin':'','ticker':'','issuer':bank,
            'nominal':nums[0] if len(nums)>0 else None,
            'unit_price':nums[1] if len(nums)>1 else None,
            'total_value':nums[2] if len(nums)>2 else None,
            'weight_pct':pcts[-1] if pcts else None,
            'currency':'TL','maturity_date':parse_dt(dts[0]) if dts else None,
            'coupon_rate':None,'purchase_date':parse_dt(dts[1]) if len(dts)>1 else None})

    # YATIRIM FONLARI
    fm = re.search(r'YATIRIM\s+FONU', section, re.I)
    if fm:
        fsec = section[fm.start():fm.start()+800]
        for j, fim in enumerate(re.finditer(r'(TRY[A-Z0-9]{10}|TR[A-Z0-9]{10})', fsec)):
            fb = fsec[fim.end():fim.end()+200]
            fnm2 = tl_nums(fb, 6)
            fpcts = pct_vals(fb)
            fb_before = fsec[max(0,fim.start()-60):fim.start()]
            fnm = re.search(r'([A-ZÇĞİÖŞÜ][A-Za-zÇĞİÖŞÜçğıöşü\s\.&,]{3,60})', fb_before)
            holdings.append({'asset_type':'fund','isin':fim.group(1)[:12],'ticker':'',
                'issuer':clean_issuer(fnm.group(1)) if fnm else '',
                'nominal':fnm2[0] if fnm2 else None,
                'unit_price':fnm2[1] if len(fnm2)>1 else None,
                'total_value':fnm2[2] if len(fnm2)>2 else None,
                'weight_pct':fpcts[-1] if fpcts else None,
                'currency':'TL','maturity_date':None,'coupon_rate':None,'purchase_date':None})

    return holdings


# ─── Futures ──────────────────────────────────────────────────────

def parse_futures_range(text, start, end):
    holdings=[]
    section = text[start:end]
    fre = re.compile(r'(F_[A-Z0-9]{6,}(?:-[A-Z]+)?)\s+VIOP[-\s]*(\d{2}[/.-]\d{2}[/.-]\d{4})?\s*([\d]+[.,]\d+)?\s+(\d+)\s+([\d]+[.,][\d]+)')
    for m in fre.finditer(section):
        qty = int(m.group(4).replace('.','').replace(',','')) if m.group(4) else None
        holdings.append({'asset_type':'future','isin':m.group(1)[:20],'ticker':m.group(1)[:12],
            'issuer':'','nominal':float(qty) if qty else None,
            'unit_price':tl(m.group(3)),'total_value':tl(m.group(5)),
            'weight_pct':None,'currency':'TL',
            'maturity_date':parse_dt(m.group(2)),'coupon_rate':None,'purchase_date':None})
    return holdings


# ─── Portfolio summary & fund info ────────────────────────────────

def extract_summary(text):
    s={}
    for p,k in [
        (r'PAY\s*(?:Hisse)?[^%]*?\s*([\d.,]+)\s*%','stocks'),
        (r'ÖZEL\s+SEKTÖR\s+(?:TAHVİLİ|BORÇLANMA)[^%]*?\s*([\d.,]+)\s*%','private_bonds'),
        (r'KAMU\s+(?:SEKTÖRÜ?\s+)?(?:TAHVİLİ|BORÇLANMA)[^%]*?\s*([\d.,]+)\s*%','gov_bonds'),
        (r'TERS\s+REPO[^%]*?\s*([\d.,]+)\s*%','repo'),
        (r'(?<!YABANCI\s)MEVDUAT[^%]*?\s*([\d.,]+)\s*%','deposits'),
        (r'YABANCI\s+(?:BORSA\s+)?YATIRIM[^%]*?\s*([\d.,]+)\s*%','foreign_stocks'),
        (r'YABANCI\s+Tahvil[^%]*?\s*([\d.,]+)\s*%','foreign_bonds'),
        (r'(?<!DİĞER\s)ALTIN[^%]*?\s*([\d.,]+)\s*%','gold'),
        (r'KİRA\s+SERTİFİKASI[^%]*?\s*([\d.,]+)\s*%','sukuk'),
        (r'TÜREV\s+(?:TEMİNAT)?[^%]*?\s*([\d.,]+)\s*%','derivatives'),
        (r'YATIRIM\s+FONU[^%]*?\s*([\d.,]+)\s*%','funds'),
    ]:
        m=re.search(p,text,re.I)
        if m:
            v=tl(m.group(1))
            if v and 0<v<100: s[k]=v
    return s

def extract_fund_info(text):
    info={}
    m=re.search(r'FONUN ADI:\s*(.+?)(?:\n|B[\.\)])',text,re.I)
    if not m: m=re.search(r'Fonun Adı[^:]*:?\s*(.+?)(?:\n|B[\.\)])',text,re.I)
    if m: info['fund_name']=m.group(1).strip()[:200]
    m=re.search(r'FON TOPLAM DEĞERİ:\s*([\d\. \d]+)',text)
    if m: info['nav']=tl(m.group(1))
    m=re.search(r'Rapor Dönemi\s*(\d{2}/\d{2}/\d{4})\s*(?:ve|–|-)\s*(\d{2}/\d{2}/\d{4})',text)
    if m: info['period_start'],info['period_end']=m.group(1),m.group(2)
    m=re.search(r'YÖNETİCİNİN\s*ÜNVANI[^:]*:\s*(.+?)(?:\n|D[\.\)])',text,re.I)
    if m: info['manager']=m.group(1).strip()[:200]
    m=re.search(r'AY\s*SONU\s*KATILMA\s*PAYI\s*FİYATI[^:]*:\s*([\d.,]+)',text,re.I)
    if m: info['share_price']=tl(m.group(1))
    return info


# ─── Main ─────────────────────────────────────────────────────────

def parse_portfolio_pdf(pdf_path):
    text = parse_pdf_text(str(pdf_path))
    if not text or len(text)<200: return None
    pos = parse_pdf_positions(str(pdf_path))
    tmap = build_ticker_map(pos)

    fund_info = extract_fund_info(text)
    portfolio_summary = extract_summary(text)

    sections = find_sections(text)

    all_h = []

    # Stocks
    if 'stocks' in sections:
        s_start = sections['stocks']
        s_end = next_section_start(text, s_start+1)
        all_h.extend(parse_stocks_in_range(text, s_start, s_end, tmap))

    # Corporate bonds
    if 'corp_bonds' in sections:
        s_start = sections['corp_bonds']
        s_end = next_section_start(text, s_start+1)
        all_h.extend(parse_bonds_in_range(text, s_start, s_end, tmap, 'corp_bonds'))

    # Government bonds
    if 'gov_bonds' in sections:
        s_start = sections['gov_bonds']
        s_end = next_section_start(text, s_start+1)
        all_h.extend(parse_bonds_in_range(text, s_start, s_end, tmap, 'gov_bonds'))

    # Sukuk
    if 'sukuk' in sections:
        s_start = sections['sukuk']
        s_end = next_section_start(text, s_start+1)
        all_h.extend(parse_bonds_in_range(text, s_start, s_end, tmap, 'sukuk'))

    # Foreign ETFs
    if 'foreign' in sections:
        s_start = sections['foreign']
        s_end = next_section_start(text, s_start+1)
        all_h.extend(parse_foreign_range(text, s_start, s_end))

    # Gold
    if 'gold' in sections:
        s_start = sections['gold']
        s_end = next_section_start(text, s_start+1)
        all_h.extend(parse_gold_range(text, s_start, s_end))

    # Repo / Deposits / Funds
    if 'repo_dep' in sections:
        s_start = sections['repo_dep']
        s_end = next_section_start(text, s_start+1)
        all_h.extend(parse_repo_dep_range(text, s_start, s_end))

    # Futures
    if 'futures' in sections:
        s_start = sections['futures']
        s_end = next_section_start(text, s_start+1)
        all_h.extend(parse_futures_range(text, s_start, s_end))

    # Deduplicate by (isin, nominal)
    seen=set(); uniq=[]
    for h in all_h:
        k=(h.get('isin',''), str(h.get('nominal','')))
        if k not in seen: seen.add(k); uniq.append(h)

    by_type={}
    for h in uniq:
        by_type.setdefault(h['asset_type'],[]).append(h)

    return {
        'fund_info': fund_info,
        'portfolio_summary': portfolio_summary,
        'holdings': uniq,
        'holdings_by_type': by_type,
        'asset_counts': {k:len(v) for k,v in by_type.items()},
        'total_holdings': len(uniq),
    }


if __name__=="__main__":
    import argparse
    ap=argparse.ArgumentParser()
    ap.add_argument("pdf_path"); ap.add_argument("--json",action="store_true")
    ap.add_argument("--summary",action="store_true")
    args=ap.parse_args()
    res=parse_portfolio_pdf(args.pdf_path)
    if not res: print("ERROR"); exit(1)
    if args.json:
        print(json.dumps(res,ensure_ascii=False,indent=2,default=str))
    elif args.summary:
        fi=res['fund_info']; ps=res['portfolio_summary']
        print(f"\n{'='*60}")
        print(f"Fund: {fi.get('fund_name','N/A')}")
        print(f"NAV: {fi.get('nav')} | {fi.get('period_start','')} - {fi.get('period_end','')}")
        print(f"\nPortfolio Summary (%):")
        for k,v in sorted(ps.items(),key=lambda x:-x[1]): print(f"  {k:20s}: {v:.2f}%")
        print(f"\nAsset Counts: {res['asset_counts']}")
        print(f"Total: {res['total_holdings']}")
        for at,hlist in res['holdings_by_type'].items():
            print(f"\n  [{at}] ({len(hlist)})")
            for h in hlist[:5]:
                print(f"    tick={h.get('ticker',''):8s} isin={h.get('isin',''):14s} "
                      f"nom={str(h.get('nominal',''))[:15]:15s} val={str(h.get('total_value',''))[:15]:15s} "
                      f"wt={str(h.get('weight_pct',''))[:8]:8s} iss={h.get('issuer','')[:30]}")
    else:
        fi=res['fund_info']
        print(f"Fund: {fi.get('fund_name','N/A')} | NAV: {fi.get('nav')} | Total: {res['total_holdings']}")
        print(f"Counts: {res['asset_counts']}")
