"""
KAP Portfolio Pipeline v12 - Spatial Parser → SQLite
Replaces all holdings with v12 parser output.
"""
import sys, re, json, sqlite3
from pathlib import Path
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).parent))
from portfolio_parser import parse_pdf, parse_fund_info, parse_eu_num

PDF_DIR = Path(__file__).parent / 'pdfs' / 'portfoy_dagilim'
DB_PATH = Path(__file__).parent / 'db' / 'fonapp.db'


def upsert_manager(cursor, name):
    if not name: return None
    cursor.execute("SELECT id FROM managers WHERE name = ?", (name,))
    row = cursor.fetchone()
    if row: return row[0]
    cursor.execute("INSERT INTO managers (name) VALUES (?)", (name,))
    return cursor.lastrowid


def upsert_fund(cursor, code, name, manager_id):
    cursor.execute("SELECT id FROM funds WHERE code = ?", (code,))
    row = cursor.fetchone()
    if row:
        # Update name if we have a better one
        if name and name != '?':
            cursor.execute("UPDATE funds SET name = ? WHERE id = ?", (name, row[0]))
        return row[0]
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

    fund_name = info.get('fund_name', code)
    manager = info.get('manager', '')
    report_date = info.get('report_date', '')
    total_value_str = info.get('total_value', '0')
    nav = parse_eu_num(total_value_str)

    manager_id = upsert_manager(cursor, manager)
    fund_id = upsert_fund(cursor, code, fund_name, manager_id)

    # Asset type summary
    type_counts = defaultdict(int)
    for h in holdings:
        type_counts[h.get('type', 'other')] += 1

    fund_info = json.dumps({
        'total_value': total_value_str,
        'report_date': report_date,
        'asset_types': dict(type_counts),
    }, ensure_ascii=False)

    # Upsert report (fund_id + period unique)
    # period = report_date or derive from pdf filename
    period = report_date.replace('/', '-') if report_date else pdf_path.stem.split('_')[1]

    cursor.execute("""
        INSERT INTO reports (fund_id, report_date, period, pdf_path, nav, fund_info_json)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(fund_id, period) DO UPDATE SET
            report_date = excluded.report_date,
            pdf_path = excluded.pdf_path,
            nav = excluded.nav,
            fund_info_json = excluded.fund_info_json
    """, (fund_id, report_date, period, str(pdf_path), nav, fund_info))

    # Get report_id
    cursor.execute("SELECT id FROM reports WHERE fund_id = ? AND period = ?",
                   (fund_id, period))
    report_id = cursor.fetchone()[0]

    # Delete old holdings for this report
    cursor.execute("DELETE FROM holdings WHERE report_id = ?", (report_id,))

    count = 0
    for h in holdings:
        isin = h.get('isin', '')
        ticker = h.get('ticker', '')
        if not isin and not ticker:
            continue

        total_num = parse_eu_num(h.get('total_value', '0'))
        weight_num = parse_eu_num(h.get('weight_pct', '0').replace('%', ''))
        issuer = h.get('issuer', '')

        cursor.execute("""
            INSERT INTO holdings (report_id, ticker, isin, company, total_value, weight_pct)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (report_id, ticker, isin, issuer, total_num, weight_num))
        count += 1

    return count


def main():
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("PRAGMA journal_mode=WAL")

    pdfs = sorted(PDF_DIR.glob('*.pdf'))
    print(f"📄 İşlenecek PDF: {len(pdfs)}")

    # First, clear ALL existing holdings (we're rebuilding from scratch)
    conn.execute("DELETE FROM holdings")
    conn.commit()
    print("🗑️  Eski holdings silindi")

    ok = skip = err = 0
    total_holdings = 0

    for i, pdf_path in enumerate(pdfs):
        try:
            count = process_pdf(pdf_path, conn)
            code = pdf_path.stem.split('_')[0]

            if count > 0:
                ok += 1
                total_holdings += count
                print(f"  ✅ [{i+1:3d}/{len(pdfs)}] {code:8s} | {count:3d} satır")
            else:
                skip += 1
        except Exception as e:
            err += 1
            print(f"  ❌ [{i+1:3d}/{len(pdfs)}] {pdf_path.stem}: {e}")

    conn.commit()

    # Final stats
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM holdings")
    h_count = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM reports")
    r_count = c.fetchone()[0]
    c.execute("SELECT COUNT(DISTINCT fund_id) FROM reports")
    f_count = c.fetchone()[0]

    print(f"\n{'='*50}")
    print(f"📊 Tamamlandı!")
    print(f"   PDF:  {ok} ✅ | {skip} ⚪ | {err} ❌")
    print(f"   Fon:  {f_count}")
    print(f"   Rapor: {r_count}")
    print(f"   Holdings: {h_count}")

    conn.close()


if __name__ == '__main__':
    main()
