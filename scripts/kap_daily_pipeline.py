#!/usr/bin/env python3.11
"""
KAP Daily Portfolio Pipeline
Chrome-free: uses KAP REST API for discovery + PDF download.
Maps disclosures to fund codes via fund_master_data, then parses + upserts.

Usage:
  python3.11 scripts/kap_daily_pipeline.py

Cron (macOS launchd):
  ~/Library/LaunchAgents/com.fonrapor.kap-daily.plist
"""

from __future__ import annotations

import os, sys, json, time, re, signal, logging, requests, pdfminer.high_level
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

# ── Paths ──────────────────────────────────────────────────────────────────────
SCRIPT_DIR = Path(__file__).parent
PDF_DIR    = SCRIPT_DIR.parent / "pdfs" / "portfoy_dagilim"
STATE_FILE = SCRIPT_DIR / "kap_daily_state.json"
LOG_FILE   = SCRIPT_DIR / "kap_daily.log"

# ── Supabase ───────────────────────────────────────────────────────────────────
SUPABASE_URL = "https://oqkobptbvcazifpvjwfz.supabase.co"
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY") or (
    (lambda: next(
        (line.strip().split("=", 1)[1] for line in open(SCRIPT_DIR.parent / "web" / ".env.local")
         if line.startswith("SUPABASE_SERVICE_KEY=")), None))()
)
if not SUPABASE_KEY:
    raise SystemExit("SUPABASE_SERVICE_KEY not set")

SB_HEADERS = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"}

# ── Zhipu GLM ─────────────────────────────────────────────────────────────────
ZHIPU_API_KEY = os.getenv("ZHIPU_API_KEY") or "4ca4188d116c433597f87d6a09e27b71.9lhC8b6VX1l9VM9V"

# ── Logging ────────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.FileHandler(LOG_FILE), logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger(__name__)

# ── Graceful shutdown ─────────────────────────────────────────────────────────
_shutdown = False
def _sigint_handler(sig, frame):
    global _shutdown
    log.warning("SIGINT — finishing current PDF before exit...")
    _shutdown = True
signal.signal(signal.SIGINT, _sigint_handler)

# ── HTTP with retry ───────────────────────────────────────────────────────────
def _http_request(method: str, url: str, max_retries: int = 5, **kwargs) -> requests.Response:
    kwargs.setdefault("timeout", 20)
    for attempt in range(max_retries):
        try:
            r = requests.request(method, url, **kwargs)
            if r.status_code in (429, 500, 502, 503, 504):
                wait = (2 ** attempt) + 1
                log.warning(f"HTTP {r.status_code} for {url}, retry {attempt+1}/{max_retries} in {wait}s")
                time.sleep(wait)
                continue
            return r
        except requests.RequestException as e:
            if attempt == max_retries - 1:
                log.error(f"Request failed after {max_retries} attempts: {e}")
                raise
            log.warning(f"Request error: {e}, retry {attempt+1}")
            time.sleep(2 ** attempt)
    return r

# ── Supabase helpers ──────────────────────────────────────────────────────────
def sb_get(path: str, params: str = "") -> Optional[list | dict]:
    url = f"{SUPABASE_URL}/rest/v1/{path}"
    if params:
        url = f"{url}?{params}"
    r = _http_request("GET", url, headers=SB_HEADERS)
    if r.status_code == 200:
        return r.json()
    log.error(f"SB GET {path} → {r.status_code}: {r.text[:150]}")
    return None

def sb_post(path: str, data: dict) -> bool:
    r = _http_request("POST", f"{SUPABASE_URL}/rest/v1/{path}",
        headers={**SB_HEADERS, "Prefer": "return=representation"},
        json=data)
    if r.status_code not in (200, 201):
        log.error(f"SB POST {path} → {r.status_code}: {r.text[:200]}")
        return False
    return True

def sb_upsert(path: str, data: list[dict]) -> bool:
    r = _http_request("POST", f"{SUPABASE_URL}/rest/v1/{path}",
        headers={**SB_HEADERS, "Prefer": "return=representation", "Content-Type": "application/json"},
        json=data)
    if r.status_code not in (200, 201):
        log.error(f"SB UPSERT {path} → {r.status_code}: {r.text[:200]}")
        return False
    return True

# ── KAP API ────────────────────────────────────────────────────────────────────
KAP_BASE   = "https://www.kap.org.tr/tr"
KAP_HEADERS = {"Content-Type": "application/json",
               "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
               "Accept": "application/json"}

def kap_discover(from_date: datetime, to_date: datetime) -> list[dict]:
    """Fetch portfolio-distribution-type disclosures between dates."""
    payload = {
        "fromDate": from_date.strftime("%d.%m.%Y"),
        "toDate":   to_date.strftime("%d.%m.%Y"),
        "disclosureTypes": None,
        "fundTypes": ["YF", "BYF", "OKS", "YYF", "VFF", "KFF", "GMF", "GSF", "PFF", "EMK"],
    }
    r = _http_request("POST", f"{KAP_BASE}/api/disclosure/list/main",
        headers=KAP_HEADERS, json=payload)
    if r.status_code != 200:
        log.error(f"KAP discovery → {r.status_code}: {r.text[:200]}")
        return []
    data = r.json()
    results = []
    for item in data:
        basic = item.get("disclosureBasic", {})
        title = basic.get("title", "")
        if "dağılım" not in title.lower() and "ortf" not in title.lower():
            continue
        if basic.get("attachmentCount", 0) == 0:
            continue
        results.append({
            "index":         basic.get("disclosureIndex"),
            "title":         title,
            "company_title": basic.get("companyTitle", ""),
            "publish_date":  basic.get("publishDate", ""),
            "fund_type":     basic.get("fundType", ""),
        })
    log.info(f"KAP discovered {len(results)} portfolio disclosures in {from_date.date()} → {to_date.date()}")
    return results

def kap_download_pdf(disclosure_index: str, fund_code: str) -> Optional[Path]:
    """Duyurunun GERÇEK portföy dağılım dosyasını indir.

    Önemli: /api/BildirimPdf/{index} sadece KAPAK sayfasını döndürür (~0.5KB,
    tablo yok). Asıl dağılım tablosu duyuruya EKLİ dosyadadır
    (/tr/api/file/download/{id}). Bu yüzden önce eki indiriyoruz; ek yoksa
    kapak PDF'ine düşüyoruz (hiç yoktan iyi).
    """
    PDF_DIR.mkdir(parents=True, exist_ok=True)
    out_path = PDF_DIR / f"{fund_code}.pdf"

    # 1) Duyuru sayfasından ek dosya URL'sini çıkar (BİRİNCİL — gerçek tablo)
    # ÖNEMLİ: KAP, header'SIZ (python-requests default) isteğe SSR HTML'i
    # (ek linkli) döndürüyor; tarayıcı User-Agent verilince SPA client-shell'i
    # (linksiz) dönüyor. O yüzden BİLEREK ekstra header GÖNDERME. Boş gelirse
    # birkaç kez tekrar dene (yoğunlukta ara sıra shell dönebiliyor).
    urls: list[str] = []
    for page_try in range(4):
        r2 = _http_request("GET", f"{KAP_BASE}/Bildirim/{disclosure_index}")
        if r2.status_code == 200:
            matches = re.findall(r'/tr/api/file/download/[0-9a-fA-F]+', r2.text)
            seen: set[str] = set()
            urls = [m for m in matches if not (m in seen or seen.add(m))]
            if urls:
                break
        time.sleep(1.5 * (page_try + 1))  # SSR'nin oturması için bekle
    if urls:
        # rel zaten "/tr/..." ile başlıyor; KAP_BASE de "/tr" ile bitiyor →
        # domain KÖKÜNDEN inşa et, yoksa çift /tr olur (404).
        kap_root = KAP_BASE.rsplit("/tr", 1)[0]  # https://www.kap.org.tr
        for rel in urls:
            r3 = _http_request("GET", f"{kap_root}{rel}",
                               headers={"User-Agent": KAP_HEADERS["User-Agent"]})
            # Magic-byte kontrolü yok: ek bazen wrapper'lı geliyor ama pdfminer
            # okuyabiliyor. Boyut eşiği + downstream extract doğrular.
            if r3.status_code == 200 and len(r3.content) > 4000:
                out_path.write_bytes(r3.content)
                log.info(f"Downloaded EK {fund_code} ({len(r3.content)//1024}KB)")
                return out_path
    else:
        log.warning(f"Disclosure page {disclosure_index} → {r2.status_code}")

    # 2) Fallback: kapak PDF (zayıf — genelde tablo içermez)
    r = _http_request("GET", f"{KAP_BASE}/api/BildirimPdf/{disclosure_index}",
                      headers={"User-Agent": KAP_HEADERS["User-Agent"]})
    if r.status_code == 200 and r.content[:4] == b"%PDF":
        out_path.write_bytes(r.content)
        log.info(f"Downloaded KAPAK {fund_code} ({len(r.content)//1024}KB) — ek bulunamadı")
        return out_path

    log.error(f"{fund_code}: ek de kapak da indirilemedi ({disclosure_index})")
    return None

# ── Fund name matching ──────────────────────────────────────────────────────────
STOP_WORDS = {
    "PORTFÖY", "YATIRIM", "SERBEST", "HİSSE", "SENEDİ", "FON", "TL", "USD", "EURO",
    "VARLIK", "YÖNETİMİ", "KAR", "PAYI", "ÖDEYEN", "ŞİRKETİ", "A.Ş.", "ARACI",
    "DEĞİŞKEN", "ÖZEL", "İKİNCİ", "ÜÇÜNCÜ", "BİRİNCİ", "DÖRDÜNCÜ",
}

def load_fund_map() -> dict[str, str]:
    """Load all funds from DB, return name→code map."""
    funds = sb_get("funds", "select=code,name&limit=1000")
    if not funds:
        log.error("Could not load fund list from DB")
        return {}
    fwd: dict[str, str] = {}
    for f in funds:
        code = (f.get("code") or "").strip()
        name = (f.get("name") or "").strip().upper()
        if code and name:
            fwd[name] = code
            # Also index first 2 meaningful words
            words = [w for w in name.split() if len(w) > 2 and w not in STOP_WORDS]
            if len(words) >= 2:
                fwd[" ".join(words[:2])] = code
    log.info(f"Loaded {len(fwd)} fund name entries")
    return fwd

def match_fund(disclosure: dict, fund_map: dict[str, str]) -> Optional[str]:
    """Match a KAP disclosure to a fund code."""
    company = disclosure["company_title"].upper()
    words   = [w for w in company.split() if len(w) > 2 and w not in STOP_WORDS]

    # Exact company name
    if company in fund_map:
        return fund_map[company]

    # First 2-3 significant words
    for n in [3, 2]:
        key = " ".join(words[:n])
        if key in fund_map:
            return fund_map[key]

    # Company contains fund name
    for fname, fcode in fund_map.items():
        if len(fname) > 5 and fname in company:
            return fcode

    # Best partial match
    best_match, best_len = None, 0
    for fname, fcode in fund_map.items():
        if len(fname) > best_len and fname in company:
            best_match = fcode
            best_len   = len(fname)

    return best_match

# ── PDF Parsing ────────────────────────────────────────────────────────────────
def extract_text(pdf_path: Path) -> str:
    try:
        return pdfminer.high_level.extract_text(str(pdf_path))
    except Exception as e:
        log.error(f"pdfminer failed for {pdf_path}: {e}")
        return ""

# MiniMax — Anthropic-uyumlu endpoint (haber pipeline'ıyla aynı; Zhipu yerine).
# Key ~/.hermes/.env'den (cron_shared.load_env veya aşağıdaki fallback yükler).
import urllib.request as _urlreq
_MINIMAX_URL = "https://api.minimax.io/anthropic/v1/messages"
_MINIMAX_MODEL = "MiniMax-M2.7"


def _minimax_key() -> str:
    k = os.environ.get("MINIMAX_API_KEY", "")
    if k:
        return k
    # fallback: ~/.hermes/.env
    try:
        with open(os.path.expanduser("~/.hermes/.env")) as f:
            for line in f:
                if line.strip().startswith("MINIMAX_API_KEY"):
                    return line.partition("=")[2].strip().strip('"').strip("'")
    except Exception:
        pass
    return ""


def parse_with_glm(text: str, fund_code: str) -> Optional[dict]:
    """Portföy dağılımını metinden MiniMax ile JSON olarak çıkarır.
    (İsim geriye-uyumluluk için korundu; motor artık MiniMax.)"""
    key = _minimax_key()
    if not key:
        log.error(f"MINIMAX_API_KEY yok — {fund_code} atlanıyor")
        return None
    system = (
        "Verilen metinden fonun portföy dağılımını JSON olarak çıkar.\n"
        'Format: {"report_date":"YYYY-MM-DD","categories":[{"name":"HİSSE SENEDİ","percentage":45.5}]}\n'
        'Eğer portföy verisi yoksa {"error":"no_data"} döndür. Sadece JSON döndür.'
    )
    payload = json.dumps({
        "model": _MINIMAX_MODEL,
        "max_tokens": 1200,
        "system": system,
        "messages": [{"role": "user", "content": text[:8000]}],
    }).encode()
    for attempt in range(3):
        try:
            req = _urlreq.Request(_MINIMAX_URL, data=payload, method="POST", headers={
                "x-api-key": key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            })
            with _urlreq.urlopen(req, timeout=60) as resp:
                data = json.loads(resp.read())
            raw = ""
            for block in data.get("content", []):
                if block.get("type") == "text":
                    raw = block.get("text", ""); break
            raw = (raw or "").strip()
            raw = re.sub(r"^```(?:json)?\s*", "", raw)
            raw = re.sub(r"\s*```$", "", raw)
            m = re.search(r"\{[\s\S]*\}", raw)
            if not m:
                return None
            result = json.loads(m.group(0))
            if "error" in result:
                return None
            return result
        except Exception as e:
            log.error(f"MiniMax failed for {fund_code} (deneme {attempt + 1}): {e}")
            time.sleep(2 + attempt)
    return None

def extract_categories_from_text(text: str) -> list[dict]:
    """Rule-based category extraction."""
    import re
    CATS = [
        "HİSSE SENEDİ", "DEVLET BORÇLANMA ARAÇLARI", "BORÇLANMA ARAÇLARI",
        "DÖVİZ", "ALTIN", "EMEKLİLİK YATIRIM", "KATILIM", "YABANCI",
        "PARA PİYASASI", "LİKİT", "TİCARİ", "KIRA SERTİFİKALARI", "VARLIK",
    ]
    results = []
    for cat in CATS:
        for pat in [
            rf"{re.escape(cat)}\s+(\d+[.,]\d+)\s*%",
            rf"(\d+[.,]\d+)\s*%\s+{re.escape(cat)}",
        ]:
            m = re.search(pat, text, re.IGNORECASE)
            if m:
                pct = float(m.group(1).replace(",", "."))
                if 0 <= pct <= 100:
                    results.append({"name": cat, "percentage": pct})
                    break
    return results

def parse_and_upsert(pdf_path: Path, fund_code: str, report_date: str) -> bool:
    text = extract_text(pdf_path)
    if not text.strip():
        log.warning(f"Empty PDF for {fund_code}")
        return False

    categories = extract_categories_from_text(text)
    method     = "text_extract"

    if not categories:
        glm_result = parse_with_glm(text, fund_code)
        if glm_result and "categories" in glm_result:
            report_date = glm_result.get("report_date", report_date)
            categories  = glm_result["categories"]
            method      = "glm_air"
        else:
            method = "no_data"

    if not categories:
        log.warning(f"No categories for {fund_code}")
        return False

    rows = [{"fund_code": fund_code, "report_date": report_date,
             "category": c["name"], "percentage": float(c["percentage"]),
             "extraction_method": method, "source": "kap_daily"} for c in categories]

    if sb_upsert("portfolio_breakdown", rows):
        log.info(f"Upserted {len(categories)} categories for {fund_code} ({method})")
        return True
    log.error(f"Upsert failed for {fund_code}")
    return False

# ── Main ───────────────────────────────────────────────────────────────────────
def run():
    started_at     = datetime.utcnow().isoformat()
    success_count  = 0
    failed_count   = 0
    failed_funds   = []
    processed      = []

    log.info("=" * 60)
    log.info("KAP Daily Pipeline started")

    # Load state
    state = json.loads(STATE_FILE.read_text()) if STATE_FILE.exists() else {}
    last_run = state.get("last_run")
    if last_run:
        from_date = datetime.fromisoformat(last_run)
        log.info(f"Resuming from last run: {last_run}")
    else:
        from_date = datetime.now() - timedelta(days=7)
        log.info("No state — scanning last 7 days")

    to_date = datetime.now()

    # Discover new disclosures
    disclosures = kap_discover(from_date, to_date)
    if not disclosures:
        log.info("No new disclosures — done")
        _save_state(state, to_date)
        return

    # Load fund map
    fund_map = load_fund_map()
    if not fund_map:
        log.error("Cannot proceed without fund map")
        return

    # Match + filter already-processed
    new_disclosures = []
    for disc in disclosures:
        code = match_fund(disc, fund_map)
        if not code:
            log.debug(f"No match: {disc['company_title'][:60]}")
            continue
        disc["fund_code"] = code
        new_disclosures.append(disc)
        log.info(f"  [{code}] {disc['title'][:60]}")

    if not new_disclosures:
        log.info("All disclosures matched to known funds")
        _save_state(state, to_date)
        return

    log.info(f"Processing {len(new_disclosures)} new disclosures...")

    for disc in new_disclosures:
        if _shutdown:
            log.warning("Shutdown requested")
            break

        fund_code  = disc["fund_code"]
        disc_index = disc["index"]

        try:
            pub_date = datetime.strptime(disc["publish_date"][:10], "%d.%m.%Y").strftime("%Y-%m-%d")
        except:
            pub_date = datetime.now().strftime("%Y-%m-%d")

        log.info(f"Processing [{fund_code}] from {pub_date}")

        pdf_path = kap_download_pdf(disc_index, fund_code)
        if not pdf_path:
            failed_count += 1
            failed_funds.append(fund_code)
            continue

        time.sleep(1.5)  # polite delay

        if parse_and_upsert(pdf_path, fund_code, pub_date):
            success_count += 1
        else:
            failed_count += 1
            failed_funds.append(fund_code)

        processed.append(fund_code)
        time.sleep(0.5)

    ended_at = datetime.utcnow().isoformat()

    # Record job run
    job_record = {
        "started_at":   started_at,
        "ended_at":     ended_at,
        "status":       "failed" if success_count == 0 else "completed",
        "total_funds":  len(new_disclosures),
        "success_count": success_count,
        "failed_count":  failed_count,
        "categories":   {"source": "kap_daily", "failed_funds": failed_funds,
                         "processed": processed},
        "created_by":   "kap_daily_cron",
    }
    sb_post("parse_job_runs", job_record)

    # Update system status
    sb_upsert("system_status", [{
        "key": "last_kap_portfolio_cron", "value": ended_at,
        "updated_at": ended_at,
    }])

    _save_state(state, to_date)
    log.info(f"Done: {success_count} ✓ / {failed_count} ✗")
    log.info("=" * 60)

def _save_state(state: dict, to_date: datetime):
    state["last_run"] = to_date.isoformat()
    STATE_FILE.write_text(json.dumps(state, indent=2))

if __name__ == "__main__":
    run()
