"""
KAP Portfolio Pipeline v7 - Multi-format PDF → SQLite (Existing Schema)
"""
import sys, re, json, sqlite3
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from portfolio_parser import parse_pdf, parse_fund_info, parse_eu_num

PDF_DIR = Path(__file__).parent / 'pdfs' / 'portfoy_dagilim'
DB_PATH = Path(__file__).parent / 'db' / 'fonapp.db'

def ensure_manager(cursor, name):
    if not name: return None
    cursor.execute("SELECT id FROM managers WHERE name = ?", (name,))
    row = cursor.fetchone()
    if row: return row[0]
    cursor.execute("INSERT INTO managers (name) VALUES (?)", (name,))
    return cursor.lastrowid

def ensure_fund(cursor, code, name, manager_id):
    cursor.execute("SELECT id FROM funds WHERE code = ?", (code,))
    row = cursor.fetchone()
    if row: return row[0]
    cursor.execute("INSERT INTO funds (code, name, manager_id) VALUES (?,?,?)", 
                   (code, name, manager_id))
    return cursor.lastrowid

def process_pdf(pdf_path, conn):
    code = pdf_path.stem.split('_')[0]
    cursor = conn.cursor()
    
    info = parse_fund_info(str(pdf_path))
    holdings = parse_pdf(str(pdf_path))
    
    if not holdings:
        return 0
    
    manager_id = ensure_manager(cursor, info.get('manager', ''))
    fund_id = ensure_fund(cursor, code, info.get('fund_name', ''), manager_id)
    
    report_date = info.get('report_date', '')
    nav = parse_eu_num(info.get('total_value', '0'))
    
    # fund_info_json stores extra data
    fund_info = json.dumps({
        'total_value': info.get('total_value', ''),
        'report_date': report_date,
        'asset_types': list(set(h.get('type','other') for h in holdings))
    })
    
    cursor.execute("""
        INSERT OR IGNORE INTO reports (fund_id, report_date, nav, pdf_path, fund_info_json)
        VALUES (?, ?, ?, ?, ?)
    """, (fund_id, report_date, nav, str(pdf_path), fund_info))
    
    # Get report_id (may already exist)
    cursor.execute("SELECT id FROM reports WHERE fund_id = ? AND report_date = ?",
                   (fund_id, report_date))
    row = cursor.fetchone()
    if not row:
        return 0
    report_id = row[0]
    
    # Delete old holdings for this report
    cursor.execute("DELETE FROM holdings WHERE report_id = ?", (report_id,))
    
    count = 0
    for h in holdings:
        isin = h.get('isin', '')
        ticker = h.get('ticker', '')
        if not isin and not ticker:
            continue
        
        total_num = parse_eu_num(h.get('total_value', '0'))
        nominal_num = parse_eu_num(h.get('nominal', '0'))
        weight_num = parse_eu_num(h.get('weight_pct', '0'))
        
        cursor.execute("""
            INSERT INTO holdings (report_id, ticker, isin, nominal, unit_price,
                company, total_value, weight_pct, date)
            VALUES (?,?,?,?,?,?,?,?,?)
        """, (report_id, ticker, isin, nominal_num,
              parse_eu_num(h.get('unit_price', '0')),
              h.get('issuer', '') or h.get('name', ''),
              total_num, weight_num,
              h.get('maturity_date', '')))
        count += 1
    
    conn.commit()
    return count

def main():
    conn = sqlite3.connect(str(DB_PATH))
    
    pdfs = list(PDF_DIR.glob('*.pdf'))
    print(f"İşlenecek PDF sayısı: {len(pdfs)}")
    
    ok = skip = err = 0
    for pdf_path in sorted(pdfs):
        try:
            holdings = parse_pdf(str(pdf_path))
            count = len(holdings)
            code = pdf_path.stem.split('_')[0]
            info = parse_fund_info(str(pdf_path))
            fund_name = info.get('fund_name', '?')[:40]
            
            if count > 0:
                process_pdf(pdf_path, conn)
                print(f"  ✅ {code} | {count:3d} satır | {fund_name}")
                ok += 1
            else:
                print(f"  ⚪ {code} |   0 satır (skip)")
                skip += 1
        except Exception as e:
            print(f"  ❌ {pdf_path.stem}: {e}")
            err += 1
    
    conn.close()
    print(f"\nTamamlandı! ✅{ok} ⚪{skip} ❌{err}")

if __name__ == '__main__':
    main()
