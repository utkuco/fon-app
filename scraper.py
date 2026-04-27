#!/usr/bin/env python3
"""
KAP Fon Portföy Scraper v3.0
============================
Öğrenilenler:
- KAP public API (/tr/api/search/combined) → fon OID bulur
- Backend (kapsitebackend.mkk.com.tr) → erişilemez (DNS)
- Bildirim tablosu → backend'den dinamik yükleniyor
- PDF: /tr/api/file/download/{UUID} çalışıyor
- Fondetail sayfası → RSC chunk'larda veri yok, backend'e bağlı
- PDF yapısı: 4 sayfa, Sayfa 1 = hisse portföyü (ISIN format: TRE[A-Z0-9]{9})

STRATEJİ:
1. /tr/api/search/combined → tüm fonların OID + kod + isim
2. Fondetail OID ile PDF UUID'lerini çek
3. PDF indir → parse et → holdings çıkar
4. Sonuç: JSON dosyası
"""

import requests
import re
import json
import time
import os
import sys
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed

BASE = "https://www.kap.org.tr"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Accept": "application/json, text/html",
    "Accept-Language": "tr-TR,tr;q=0.9",
    "Referer": BASE,
}
PORTFOY_RAPORU_SUBJECT = "8aca490d502e34b801502e380044002b"
GLG_OID = "4028328c80e9178f0181053760830f04"  # Bildiğimiz OID

_session = requests.Session()
_session.headers.update(HEADERS)

def get(url, timeout=20):
    r = _session.get(url, timeout=timeout)
    r.raise_for_status()
    return r.text

def post(url, json_data, timeout=20):
    r = _session.post(url, json=json_data, timeout=timeout)
    r.raise_for_status()
    return r.json()


# ─── API LAYER ────────────────────────────────────────────────────────────────

def search_fund(query: str) -> list[dict]:
    """KAP search API'den fon ara."""
    try:
        data = post(f"{BASE}/tr/api/search/combined", {"keyword": query}, timeout=20)
        results = []
        for cat in data:
            if cat.get("category") == "companyOrFunds":
                for r in cat.get("results", []):
                    if r.get("searchType") == "F":
                        results.append({
                            "code": r.get("cmpOrFundCode", "").upper(),
                            "name": r.get("searchValue", ""),
                            "oid": r.get("memberOrFundOid", ""),
                        })
        return results
    except Exception as e:
        print(f"  ! search_fund({query}): {e}")
        return []

def search_all_funds_via_api(letter: str = "") -> list[dict]:
    """Alphabetically search all funds via search API."""
    results = []
    # Search common fund name prefixes
    prefixes = []
    if letter:
        prefixes = [letter.upper()]
    else:
        prefixes = [chr(c) for c in range(ord('A'), ord('Z')+1)] + \
                   [f"{chr(c1)}{chr(c2)}" for c1 in range(ord('A'), ord('Z')+1) for c2 in range(ord('A'), ord('J')+1)]

    seen_oids = set()
    for prefix in prefixes:
        try:
            found = search_fund(prefix)
            for f in found:
                if f["oid"] not in seen_oids:
                    seen_oids.add(f["oid"])
                    results.append(f)
        except Exception:
            pass
        time.sleep(0.1)
    return results


# ─── HTML PARSING ─────────────────────────────────────────────────────────────

def get_pdf_uuids_from_fondetail_html(oid: str) -> list[dict]:
    """Fondetail sayfasındaki RSC chunk'lardan PDF UUID'lerini + metadata çıkarır."""
    try:
        html = get(f"{BASE}/tr/fon-bilgileri/ozet/{oid}", timeout=25)
    except Exception as e:
        return []

    # RSC push chunk'larını çıkar
    scripts = re.findall(r'<script>(self\.__next_f\.push\([^<]+)</script>', html)
    all_text = ""
    for s in scripts:
        decoded = s.replace('\\\\n', '\n').replace('\\\\\"', '"').replace('\\\\[', '[').replace('\\\\]', ']').replace('\\\\', '')
        all_text += decoded + "\n"

    pdfs = []
    # UUID pattern: /tr/api/file/download/ + 32 hex chars
    uuid_matches = re.findall(r'/tr/api/file/download/([a-f0-9]{32})', all_text)
    for uuid in uuid_matches:
        pdfs.append({"uuid": uuid, "type": "unknown"})

    # Konu bilgisi çıkar
    # Bildirim tipi dropdown'unda Portföy Dağılım Raporu'nun subject OID'si var
    subject_oids = re.findall(r'"subjectOid"\s*:\s*"([a-f0-9]{32})"', all_text)
    konu_map = {}
    for m in re.finditer(r'"label"\s*:\s*"([^"]+)"[^}]*"value"\s*:\s*"([a-f0-9]{32})"', all_text):
        konu_map[m.group(2)] = m.group(1)

    # PDF'lerin konularını tahmin et
    return pdfs

def get_disclosure_uuids_from_bildirimler_page(oid: str) -> list[dict]:
    """Fondetail bildirimler sayfasından Portföy Dağılım Raporu PDF UUID'lerini çıkarır."""
    try:
        html = get(f"{BASE}/tr/fon-bildirimleri/{oid}", timeout=25)
    except Exception:
        return []

    # Bildirimler sayfasındaki RSC chunk'ları → bildirim tablosu verisi
    # Bildirim tablosu backend'den geldiği için boş olacak ama
    # sayfadaki "Konu" dropdown'unda subject OID'ler var
    scripts = re.findall(r'<script>(self\.__next_f\.push\([^<]+)</script>', html)
    all_text = ""
    for s in scripts:
        decoded = s.replace('\\\\n', '\n').replace('\\\\\"', '"').replace('\\\\[', '[').replace('\\\\]', ']').replace('\\\\', '')
        all_text += decoded + "\n"

    # Konu + value mapping
    konular = {}
    for m in re.finditer(r'"label"\s*:\s*"([^"]+)"[^}]{0,200}"value"\s*:\s*"([a-f0-9]{32})"', all_text):
        konular[m.group(2)] = m.group(1)

    # PDF file/download UUID'leri
    uuids = re.findall(r'/tr/api/file/download/([a-f0-9]{32})', all_text)

    results = []
    for uuid in uuids:
        results.append({
            "uuid": uuid,
            "konu": konular.get(uuid, "Bilinmiyor"),
        })
    return results


# ─── PDF DOWNLOAD ────────────────────────────────────────────────────────────

def download_pdf(uuid_or_index: str, dest_path: str) -> bool:
    """PDF'i indirir."""
    # UUID format → /tr/api/file/download/{uuid}
    if re.match(r'^[a-f0-9]{32}$', uuid_or_index):
        url = f"{BASE}/tr/api/file/download/{uuid_or_index}"
    else:
        # Disclosure index → /tr/BildirimPdf/{index}
        url = f"{BASE}/tr/BildirimPdf/{uuid_or_index}"

    try:
        r = _session.get(url, timeout=30, allow_redirects=True)
        if r.status_code == 200 and len(r.content) > 5000 and r.content[:4] == b'%PDF':
            with open(dest_path, 'wb') as f:
                f.write(r.content)
            return True
    except Exception:
        pass
    return False


# ─── PDF PARSING (Node.js + pdfjs-dist) ──────────────────────────────────────

def parse_pdf(pdf_path: str) -> dict:
    """Node.js + pdfjs-dist ile PDF'i parse eder."""
    import subprocess

    script = f"""
import {{ getDocument }} from 'pdfjs-dist/legacy/build/pdf.mjs';
import {{ readFileSync }} from 'fs';

const path = '{pdf_path}';
const data = new Uint8Array(readFileSync(path));
const pdf = await getDocument({{ data }}).promise;
const result = {{ pages: pdf.numPages, text: [] }};

for (let i = 1; i <= pdf.numPages; i++) {{
  const page = await pdf.getPage(i);
  const content = await page.getTextContent();
  result.text.push(content.items.map(item => item.str).join(' '));
}}
console.log(JSON.stringify(result));
"""
    tmp = "/tmp/_parse_pdf.mjs"
    with open(tmp, 'w') as f:
        f.write(script)
    try:
        result = subprocess.run(
            ['node', tmp], capture_output=True, text=True,
            timeout=120
        )
        if result.returncode == 0:
            return json.loads(result.stdout)
        return {"error": result.stderr[:300]}
    except Exception as e:
        return {"error": str(e)}


def extract_holdings_from_text(text: str) -> list[dict]:
    """PDF text'inden hisse portföyünü çıkarır.
    
    Hisse satırı formatı (Page 1):
    ISIN  ŞIRKET_ADI  NOMİNAL  FİYAT  DEĞER  %  TOPLAM
    TREASELS91H2 ASELSANELEKTRONIK 28439,00 83,75 3.350.000,00 29,50 26,05
    
    ISIN = TRE + 9 alphanumeric = 12 chars total
    Nominal/Değer/Toplam = x.xxx.xxx,xx format (dot=thousands, comma=decimal)
    % = xx,xx or x,xx format
    """
    holdings = []

    # ISIN satırlarını bul
    # Pattern: TRE[A-Z0-9]{9} + rest of line
    isin_lines = re.findall(
        r'(TRE[A-Z0-9]{9})\s+([^\n]+)',
        text,
        re.UNICODE
    )

    for isin, rest in isin_lines:
        rest = rest.strip()
        # Satırdaki sayıları çıkar (virgüllü ondalık, noktalı binlik)
        numbers = re.findall(r'[\d\.]+,\d+|\d+,\d{1,2}', rest)

        # Hisse satırında tipik: 6-7 sayısal alan var
        # (nominal, fiyat, değer, %, toplam değer, [satış fiyatı])
        if len(numbers) >= 5:
            try:
                # Son 2-3 alan %, toplam değer olabilir
                # Format genelde: NOMİNAL FİYAT DEĞER % TOPLAM_DEĞER
                # veya: NOMİNAL FİYAT DEĞER % ORAN (bazı satırlarda farklı)
                last = numbers[-1].replace('.', '').replace(',', '.')
                last2 = numbers[-2].replace('.', '').replace(',', '.') if len(numbers) >= 2 else None

                # Şirket adı: ISIN'den sonra, sayılardan önceki kısım
                company_end = rest.rfind(numbers[-1])
                company = rest[:company_end].strip()

                holdings.append({
                    "isin": isin,
                    "company": company[:100],
                    "raw_numbers": numbers,
                })
            except Exception:
                continue

    return holdings

def parse_holdings_advanced(text: str) -> list[dict]:
    """Gelişmiş holding parser — PDF text'inden detaylı veri çıkarır."""
    holdings = []

    # Sayfa 1'deki hisse tablosunu bul
    # "HİSSE SENEDİ" bölümünden sonra başlar, "GRUP TOPLAMI" ile biter
    hisse_section = re.search(
        r'HİSSE SENEDİ[^\n]*\n(.+?)GRUP TOPLAMI',
        text,
        re.UNICODE | re.DOTALL
    )
    if not hisse_section:
        return holdings

    section = hisse_section.group(1)

    # Her satırı işle
    lines = section.split('\n')
    for line in lines:
        line = line.strip()
        if not line:
            continue

        # ISIN bul
        isin_m = re.search(r'(TRE[A-Z0-9]{9})', line)
        if not isin_m:
            continue

        isin = isin_m.group(1)
        after_isin = line[isin_m.end():].strip()

        # Sayıları çıkar
        numbers = re.findall(r'[\d\.]+,\d{2}', after_isin)
        if len(numbers) < 3:
            continue

        try:
            # Son sayı = toplam değer
            # Sondan 2. = % (pay)
            # Sondan 3. = günlük değer
            # Sondan 4. = birim fiyat
            # Sondan 5. = nominal
            total = float(numbers[-1].replace('.', '').replace(',', '.'))
            # Guard against PDF parsing corruption (e.g. 8.01e+20 for a stock value)
            if total > 1_000_000_000_000:  # > 1 trillion TL — impossibly large for a single holding
                total = None
            pct = float(numbers[-2].replace('.', '').replace(',', '.'))
            daily = float(numbers[-3].replace('.', '').replace(',', '.')) if len(numbers) >= 3 else None
            price = float(numbers[-4].replace('.', '').replace(',', '.')) if len(numbers) >= 4 else None
            nominal = float(numbers[-5].replace('.', '').replace(',', '.')) if len(numbers) >= 5 else None

            # Company name: ISIN'den sonra, ilk sayıya kadar
            first_num_pos = after_isin.find(numbers[0])
            company = after_isin[:first_num_pos].strip() if first_num_pos > 0 else after_isin[:30].strip()

            holdings.append({
                "isin": isin,
                "company": re.sub(r'\s+', ' ', company)[:100],
                "nominal": nominal,
                "price": price,
                "daily_value": daily,
                "pct": pct,
                "total_value": total,
            })
        except (ValueError, IndexError):
            continue

    return holdings

def extract_fund_summary(text: str) -> dict:
    """PDF'den fon özet bilgilerini çıkarır."""
    summary = {}

    # Dönem: "Şubat-2025" formatı
    m = re.search(r'(Ocak|Şubat|Mart|Nisan|Mayıs|Haziran|Temmuz|Ağustos|Eylül|Ekim|Kasım|Aralık)-(\d{4})', text)
    if m:
        summary['period'] = f"{m.group(1)} {m.group(2)}"

    # Fon toplam değeri
    m = re.search(r'FON TOPLAM DEĞERİ\s*([\d\.]+,\d+)', text)
    if m:
        summary['total_value'] = float(m.group(1).replace('.', '').replace(',', '.'))

    # Katılma payı sayısı
    m = re.search(r'Katılma Payı Sayısı\s*([\d\.]+,\d+)', text)
    if m:
        summary['participation_shares'] = float(m.group(1).replace('.', '').replace(',', '.'))

    # Pay fiyatı
    m = re.search(r'Ay Sonu Pay Fiyatı \(TL\)\s*([\d\.]+,\d+)', text)
    if m:
        summary['nav_per_share'] = float(m.group(1).replace('.', '').replace(',', '.'))

    # Kurucu
    m = re.search(r'Kurucunun Ünvanı\s*([^\n]+)', text)
    if m:
        summary['founder'] = m.group(1).strip()

    # Yönetici
    m = re.search(r'Yöneticinin Ünvanı\s*([^\n]+)', text)
    if m:
        summary['manager'] = m.group(1).strip()

    return summary


# ─── FULL PIPELINE ───────────────────────────────────────────────────────────

def scrape_fund_by_oid(oid: str, code: str = None) -> dict:
    """Bir fonu OID ile çeker."""
    result = {
        "oid": oid,
        "code": code or "UNKNOWN",
        "status": "pending",
        "holdings": [],
        "summary": {},
        "pdfs_found": 0,
    }

    # 1. Bildirimler sayfasından PDF UUID'lerini çek
    print(f"  [{code or oid[:8]}] Bildirimler sayfası çekiliyor...")
    disclosures = get_disclosure_uuids_from_bildirimler_page(oid)
    portofoy_uuids = [d for d in disclosures if 'portföy' in d.get('konu', '').lower() or 'dağılım' in d.get('konu', '').lower()]
    print(f"  → {len(disclosures)} PDF UUID, {len(portofoy_uuids)} portföy raporu")

    if not portofoy_uuids:
        # Fallback: doğrudan fondetail'dan UUID dene
        fondetail_uuids = get_pdf_uuids_from_fondetail_html(oid)
        if fondetail_uuids:
            print(f"  → Fondetail'dan {len(fondetail_uuids)} UUID")
            portofoy_uuids = fondetail_uuids[:1]  # İlkini dene

    if not portofoy_uuids:
        result["status"] = "no_portfoy_uuid"
        return result

    result["pdfs_found"] = len(portofoy_uuids)

    # 2. İlk portföy raporunu indir
    target = portofoy_uuids[0]
    uuid = target.get("uuid", "")
    print(f"  → UUID: {uuid[:16]}...")

    pdf_dir = "data/pdfs"
    os.makedirs(pdf_dir, exist_ok=True)
    pdf_path = f"{pdf_dir}/{oid}_{uuid[:16]}.pdf"

    if not os.path.exists(pdf_path) or os.path.getsize(pdf_path) < 5000:
        ok = download_pdf(uuid, pdf_path)
        if not ok:
            result["status"] = "download_failed"
            return result
        print(f"  ✓ PDF indirildi: {os.path.getsize(pdf_path):,} bytes")
    else:
        print(f"  ✓ PDF cached: {os.path.getsize(pdf_path):,} bytes")

    # 3. Parse et
    print(f"  → Parsing...")
    parsed = parse_pdf(pdf_path)
    if "error" in parsed:
        result["status"] = f"parse_error: {parsed['error'][:80]}"
        return result

    text = parsed.get("text", [])
    if not text:
        result["status"] = "empty_pdf"
        return result

    # 4. Hisse portföyünü çıkar
    holdings = parse_holdings_advanced(text[0])
    summary = extract_fund_summary(text[0])

    result["status"] = "success"
    result["holdings"] = holdings
    result["summary"] = summary
    result["pages"] = parsed.get("pages", len(text))
    result["pdf_path"] = pdf_path

    print(f"  ✓ {len(holdings)} hisse, {parsed.get('pages',0)} sayfa")
    if summary.get('period'):
        print(f"    Dönem: {summary['period']}, Toplam: {summary.get('total_value', 'N/A')}")
    for h in holdings[:3]:
        print(f"    {h['isin']} {h['company'][:25]:<25} %{h['pct']:.2f} {h.get('total_value', 0):>15,.0f}")

    return result


def build_fund_list_from_search() -> list[dict]:
    """Search API ile tüm fonların OID + kod + isim listesi."""
    print("  Search API ile fonlar aranıyor...")
    all_funds = []

    # Tek harfli prefix'ler + yaygın 2 harfli
    prefixes = [chr(c) for c in range(ord('A'), ord('Z')+1)]
    prefixes += [f"{c1}{c2}" for c1 in 'ABCDEFGHI' for c2 in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ']

    seen = set()
    for i, prefix in enumerate(prefixes):
        try:
            results = search_fund(prefix)
            for r in results:
                if r["oid"] not in seen:
                    seen.add(r["oid"])
                    all_funds.append(r)
            if (i + 1) % 10 == 0:
                print(f"    {i+1}/{len(prefixes)}: {len(all_funds)} fon")
        except Exception:
            pass
        time.sleep(0.08)

    print(f"  → {len(all_funds)} benzersiz fon bulundu")
    return all_funds


def run_pipeline(limit: int = None, output: str = "data/fund_holdings.json"):
    """Tam pipeline."""
    print("=" * 60)
    print("KAP FON PORTFÖY SCRAPER v3.0")
    print("=" * 60)

    # 1. Fon listesini search API'den çek
    print("\n[1/3] Fon listesi çekiliyor (search API)...")
    funds = build_fund_list_from_search()
    if limit:
        funds = funds[:limit]

    print(f"\n[2/3] {len(funds)} fon işleniyor...")
    os.makedirs("data", exist_ok=True)
    results = []

    for i, fund in enumerate(funds):
        print(f"\n[{i+1}/{len(funds)}]", end="")
        try:
            r = scrape_fund_by_oid(fund["oid"], fund["code"])
            r["name"] = fund["name"]
            results.append(r)
        except Exception as e:
            print(f"  ! HATA: {e}")
            results.append({"code": fund.get("code"), "oid": fund.get("oid"), "status": f"error: {e}"})
        time.sleep(0.3)

        # Ara kayıt
        if (i + 1) % 10 == 0:
            with open(output, 'w', encoding='utf-8') as f:
                json.dump(results, f, ensure_ascii=False, indent=2)
            success = sum(1 for r in results if r.get("status") == "success")
            pf = sum(1 for r in results if r.get("holdings"))
            print(f"\n  >> Ara kayıt: {success} başarılı, {pf} portföylü")

    # 3. Final
    with open(output, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    success = sum(1 for r in results if r.get("status") == "success")
    pf = sum(1 for r in results if r.get("holdings"))
    print(f"\n{'='*60}")
    print(f"Bitti: {success}/{len(results)} başarılı, {pf} portföylü")
    print(f"Çıktı: {output}")
    return results


# ─── SINGLE FUND TEST ────────────────────────────────────────────────────────

def test_glg():
    """GLG fonunu test et."""
    print("=" * 50)
    print("TEST: GLG Fonu")
    print("=" * 50)

    oid = GLG_OID
    result = scrape_fund_by_oid(oid, "GLG")

    print("\n--- SONUÇ ---")
    print(json.dumps({
        "status": result["status"],
        "holdings_count": len(result["holdings"]),
        "summary": result["summary"],
        "pages": result.get("pages", 0),
    }, ensure_ascii=False, indent=2))

    return result


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "test":
        test_glg()
    elif len(sys.argv) > 1 and sys.argv[1] == "test-parse":
        # Sadece mevcut PDF'i parse et
        pdf_path = sys.argv[2] if len(sys.argv) > 2 else "glg_portfolio.pdf"
        parsed = parse_pdf(pdf_path)
        if "error" not in parsed:
            holdings = parse_holdings_advanced(parsed["text"][0])
            summary = extract_fund_summary(parsed["text"][0])
            print(json.dumps({
                "pages": parsed["pages"],
                "holdings": holdings,
                "summary": summary,
            }, ensure_ascii=False, indent=2))
        else:
            print(json.dumps(parsed))
    else:
        limit = int(sys.argv[1]) if len(sys.argv) > 1 else None
        output = sys.argv[2] if len(sys.argv) > 2 else "data/fund_holdings.json"
        run_pipeline(limit=limit, output=output)
