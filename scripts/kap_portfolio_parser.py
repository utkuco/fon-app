#!/usr/bin/env python3
"""
KAP Portföy Dağılım PDF Parser — Zhipu AI + pdfplumber

Two-layer extraction:
  1. pdfplumber → directly extract table data from PDF (fast, no AI cost)
  2. GLM fallback → for PDFs where table extraction fails

Usage:
  export ZHIPU_API_KEY=...
  export SUPABASE_SERVICE_KEY=...   # sb_secret_... service role key
  python3 scripts/kap_portfolio_parser.py --batch
  python3 scripts/kap_portfolio_parser.py --test AN1_4028328c.pdf
"""

import argparse
import json
import os
import re
import sqlite3
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

import pdfplumber
import requests

# ─── Config ───────────────────────────────────────────────────────────────────
ZHIPU_API_KEY = os.environ.get("ZHIPU_API_KEY") or "4ca4188d116c433597f87d6a09e27b71.9lhC8b6VX1l9VM9V"
ZHIPU_API_BASE   = "https://api.z.ai/api/coding/paas/v4"
SUPABASE_URL     = "https://oqkobptbvcazifpvjwfz.supabase.co"
# Hardcoded publishable key — used for REST API upserts to portfolio_breakdown
SUPABASE_KEY     = "sb_publishable__GPrsdfKRZCMZE8to916iQ_Izv9naG-"
PDF_DIR          = Path(__file__).parent.parent / "pdfs" / "portfoy_dagilim"
DB_PATH          = Path(__file__).parent / "kap_parse_log.db"
LOG_FILE         = Path(__file__).parent / "kap_parse.log"

GLM_MODEL        = "glm-4.5"      # non-reasoning, JSON in `content` field ✅ verified 2026-04-25
GLM_TIMEOUT      = 120            # seconds — complex PDFs need more time


# ─── Logging ──────────────────────────────────────────────────────────────────
def log(msg: str, level: str = "INFO"):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] [{level}] {msg}"
    print(line)
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG_FILE, "a") as f:
        f.write(line + "\n")


# ─── Fund Category Detection ───────────────────────────────────────────────────
def detect_fund_category(text: str) -> str:
    """
    Detect fund category from raw PDF text — fund name takes priority,
    then portfolio composition signals.

    Returns one of:
      HISSE     - hisse senedi ağırlıklı (A.Grup var, detay gerekli)
      PARA      - para piyasası fonu (mevduat/bono, kategori yeterli)
      KIRA      - kira sertifikası / katılım fonları (standart tablo yok)
      SERBEST   - serbest fon (standart tablo yok)
      KARMA     - karma/değişken fon (detay gerekli olabilir)
      UNKNOWN   - bilinmeyen format
    """
    lines = text.split("\n")
    # Fund name is always in the first 5 lines of KAP PDFs
    header = "\n".join(lines[:8]).upper()

    # ── Step 1: Fund NAME patterns (highest priority) ─────────────────────────
    # "KATILIM" in fund name → KIRA (Katılım Fonları are KIRA category)
    # Must be word boundary: "KATILIM" not "KATILMA" or "KATILIMCI"
    if re.search(r"\bKATILIM\b", header):
        return "KIRA"
    # "KİRA SERTİFİKASI" in fund name → KIRA
    if "KİRA SERTİFİKASI" in header:
        return "KIRA"
    # "SERBEST" in fund name → SERBEST
    if re.search(r"\bSERBEST\b", header):
        return "SERBEST"
    # "DEĞİŞKEN" (variable) in fund name → KARMA (not PARA, not HISSE)
    if re.search(r"\bDEĞİŞKEN\b", header):
        return "KARMA"
    # "HİSSE" or "HİSSE FON" in fund name → HISSE
    if re.search(r"\bHİSSE\b", header):
        return "HISSE"

    # ── Step 2: Portfolio composition signals ───────────────────────────────
    t = text.upper()

    # Para piyasası: T.REPO, bono, mevduat ağırlıklı — A.Grup ve A.PAY yok
    if (("A. GRUP" not in t and "A.GRUP" not in t) and "A.PAY" not in t) and any(k in t for k in [
        "T.REPO", "TERS REPO", "ÖZEL SEKTÖR TAHVİL", "DEVLET TAHVİL",
        "MEVDUAT", "VADELİ MEVDUAT", "PARA PİYASASI", "TPP",
        "FON PORTFÖY DEĞERİ TABLOSU"
    ]):
        return "PARA"

    # Hisse: A.Grup veya A.PAY (yeni KAP formatı) — HİSSE veya KARMA döndür
    if any(k in t for k in ["A. GRUP", "A.GRUP", "A.PAY"]):
        if "HİSSE" in t or "PAY" in t:
            return "HISSE"
        return "KARMA"

    # Karma fon: A.Grup yok ama fon portföyü var
    if "FON PORTFÖY DEĞERİ TABLOSU" in t:
        return "KARMA"

    return "UNKNOWN"


def _extract_pct_values(text: str) -> list:
    """Extract all percentage-like numbers from text."""
    return [float(m.group(1).replace(",", "."))
            for m in re.finditer(r"([\d]+[.,]\d+)", text)
            if 0 <= float(m.group(1).replace(",", ".")) <= 100]


def _parse_pct_from_row(row_text: str) -> Optional[float]:
    """Parse percentage from a GRUP TOPLAMI row — find the largest valid %."""
    vals = _extract_pct_values(row_text)
    if not vals:
        return None
    # Filter out nominal values (too large) — GRUP% is always 0-100
    valid = [v for v in vals if v <= 100 and v > 0]
    return max(valid) if valid else None


def parse_portfolio_tables(pdf_path: Path, fund_code: str, category_override: str | None = None) -> Optional[dict]:
    """
    Two-path extraction based on fund category:
      HISSE/KARMA → pdfplumber table + GLM fallback
      PARA         → raw text parsing (Section III GRUP TOPLAMI + Section IV)
      SERBEST      → return None immediately (no standard portfolio)
      category_override: if provided (from DB fund_type), use it instead of detect_fund_category.
    """
    try:
        import pdfminer.high_level as pdfminer

        # ── Extract raw text ───────────────────────────────────────────────────
        raw_text = pdfminer.extract_text(str(pdf_path), maxpages=10)
        if not raw_text:
            return None

        # ── Determine category ─────────────────────────────────────────────────
        category = category_override if category_override else detect_fund_category(raw_text)
        log(f"  Fund category: {category} (override={category_override is not None})")

        # ── SERBEST/KIRA FON: skip (no standard portfolio table) ────────────────
        if category in ("SERBEST", "KIRA"):
            log(f"  Skipping {category} fon — no standard portföy table", "WARN")
            return None

        # ── PARA PİYASASI: text-based extraction ──────────────────────────────
        if category == "PARA":
            # Try Section4 parsing first, then GRUP TOPLAMI
            result = _parse_para_piyasasi_section4(raw_text)
            if not result:
                result = _parse_para_piyasasi(raw_text, fund_code)
            return result

        # ── HISSE/KARMA: table parsing → GLM fallback inside _parse_hisse_tables ──
        return _parse_hisse_tables(pdf_path, raw_text, fund_code)

    except Exception as e:
        log(f"parse_portfolio_tables error {fund_code}: {e}", "WARN")
        return None


def _parse_para_piyasasi_section4(raw_text: str) -> Optional[dict]:
    """
    Parse para piyasası / bono fund from raw text.
    Strategy: Section IV (FON TOPLAM DEĞERİ TABLOSU) gives the authoritative
    category breakdown. Section III (GRUP TOPLAMI rows) supplements if available.

    Section IV layout:
      FON PORTFÖY DEĞERİ  = total portfolio (should be ~100%)
      HAZIR DEĞERLER     = cash/repo/TPP (usually small %)
      ALACAKLAR          = receivables
      DİĞER VARLIKLAR    = other assets
      BORÇLAR            = liabilities (negative %)
      İHTİYAT / VERGİ    = reserves/tax (usually 0%)

    Section III gives actual instrument-level GRUP TOPLAMI rows, but
    pdfminer may concatenate cells making % extraction unreliable.
    We use Section III only when its GRUP TOPLAMI %'s are clearly valid.
    """
    lines = raw_text.split("\n")

    # ── Extract date ─────────────────────────────────────────────────────────
    # Try Turkish format first: "28 Mart 2025"
    date_match = re.search(r"(\d{1,2})\s+(Ocak|Şubat|Mart|Nisan|Mayıs|Haziran|Temmuz|Ağustos|Eylül|Ekim|Kasım|Aralık)\s+(\d{4})", raw_text)
    if date_match:
        day, month_tr, year = date_match.group(1), date_match.group(2), date_match.group(3)
        month_map = {"Ocak":"01","Şubat":"02","Mart":"03","Nisan":"04","Mayıs":"05",
                     "Haziran":"06","Temmuz":"07","Ağustos":"08","Eylül":"09",
                     "Ekim":"10","Kasım":"11","Aralık":"12"}
        report_date = f"{year}-{month_map[month_tr]}-{day.zfill(2)}"
    else:
        # Fallback: "01/12/2025 - 31/12/2025" European format (DD/MM/YYYY)
        date_match = re.search(r"(\d{2})/(\d{2})/(\d{4})\s*-\s*\d{2}/\d{2}/\d{4}", raw_text)
        if date_match:
            day, month, year = date_match.group(1), date_match.group(2), date_match.group(3)
            report_date = f"{year}-{month}-{day}"
        else:
            report_date = ""

    # ─────────────────────────────────────────────────────────────────────────
    # STEP 1: Section IV — FON TOPLAM DEĞERİ TABLOSU
    # ─────────────────────────────────────────────────────────────────────────
    section4_match = re.search(
        r"IV[.-]?\s*FON TOPLAM DE\u011e\u0130\u0130?\s*TABLOSU.*?(?=V[.-]?\s*AY|YAPILAN G\u0130DERLER|PORTFÖYDEN|\u0130TFALAR|GRUP TOPLAMI\s+GRUP|$)",
        raw_text, re.DOTALL | re.IGNORECASE
    )

    sec4_pct = {}  # category -> pct
    # ── Simple string search: find "IV-FON TOPLAM DEĞERİ TABLOSU" then scan ──
    sec4_start = raw_text.upper().find("IV-FON TOPLAM DEĞERİ TABLOSU")
    if sec4_start < 0:
        sec4_start = raw_text.upper().find("IV-FON TOPLAM")
    if sec4_start >= 0:
        sec4_chunk = raw_text[sec4_start:sec4_start + 8000]
        sec4_lines = sec4_chunk.split("\n")

        # Pass 1: collect ALL "XX,XX %" occurrences with their line indices
        pct_lines = {}  # line_index -> pct_value
        for i, line in enumerate(sec4_lines):
            m = re.match(r"^([\d]+[.,]\d+)\s*%$", line.strip())
            if m:
                pct_lines[i] = float(m.group(1).replace(",", "."))

        # Pass 2: for each description line, find the nearest pct AFTER it
        for i, line in enumerate(sec4_lines):
            line_upper = line.upper().strip()
            if not line_upper:
                continue

            # Find closest pct line after this description
            closest_pct = None
            for pi in sorted(pct_lines.keys()):
                if pi > i:
                    # This pct is after the description — good candidate
                    # Prefer the closest one within 8 lines
                    if pi - i <= 8:
                        closest_pct = pct_lines[pi]
                        break

            if closest_pct is None:
                continue

            if "FON PORTFÖY DEĞERİ" in line_upper and "FON TOPLAM" not in line_upper:
                sec4_pct["_fon_portfoy"] = closest_pct
            elif "HAZIR DEĞERLER" in line_upper or "HAZIR DEĞER" in line_upper:
                sec4_pct["repo"] = max(sec4_pct.get("repo", 0), closest_pct)
            elif "ALACAKLAR" in line_upper:
                sec4_pct["other"] = max(sec4_pct.get("other", 0), closest_pct)
            elif "DİĞER VARLIKLAR" in line_upper:
                sec4_pct["other"] = max(sec4_pct.get("other", 0), closest_pct)
            elif "BORÇLAR" in line_upper or "İHTİYAT" in line_upper or "VERGİ" in line_upper:
                pass  # negative items — not an allocation

    log(f"    Section IV pcts: {sec4_pct}", "INFO")

    # ─────────────────────────────────────────────────────────────────────────
    # STEP 2: Section III — GRUP TOPLAMI (only if pct is clearly valid)
    # Layout: value is 2+ lines BEFORE "GRUP TOPLAMI", group name is 1-2 AFTER
    # ─────────────────────────────────────────────────────────────────────────
    grup_totals = {}

    for i, line in enumerate(lines):
        if "GRUP TOPLAMI" not in line.upper():
            continue

        # The % value is 2-6 lines before GRUP TOPLAMI
        pct = None
        for offset in range(2, 8):
            idx = i - offset
            if idx < 0:
                break
            val_line = lines[idx].strip()
            if not val_line:
                continue
            # Skip header/label lines
            skip_headers = ["GRUP", "ORANI", "TOPLAM", "%", "DEĞER", "(FPD", "(FTD", "GÖRE"]
            if any(h in val_line.upper() for h in skip_headers):
                continue
            try:
                cleaned = val_line.replace(".", "").replace(",", ".")
                if cleaned.replace(".", "").isdigit() or re.match(r"^[\d]+[.,][\d]+$", cleaned):
                    v = float(cleaned)
                    if 0 < v <= 100:
                        pct = v
                        break
            except (ValueError, AttributeError):
                continue

        if pct is None:
            continue

        # Skip the grand-total row (pct >= 99)
        if pct >= 99:
            continue

        # Group type name is 1-3 lines after
        group_type = ""
        for offset in range(1, 4):
            idx = i + offset
            if idx < len(lines):
                next_line = lines[idx].strip()
                if next_line and next_line not in ["", "GRUP TOPLAMI"]:
                    group_type = next_line.upper()
                    break

        gt = group_type.upper()
        if any(k in gt for k in ["ÖZEL SEKTÖR", "KORPORAT", "ÖZEL SEKTÖR BORSA", "ÖZEL SEKTÖR TAHVİL"]):
            grup_totals["private_bond"] = max(grup_totals.get("private_bond", 0), pct)
        elif any(k in gt for k in ["DEVLET TAHVİL", "DİBS", "HAZİNE", "TRT", "KAMU", "Hazine Bonosu"]):
            grup_totals["treasury_bill"] = max(grup_totals.get("treasury_bill", 0), pct)
        elif any(k in gt for k in ["MEVDUAT", "VADELİ MEVDUAT", "BANKA"]):
            grup_totals["term_deposit"] = max(grup_totals.get("term_deposit", 0), pct)
        elif "T.REPO" in gt:
            grup_totals["reverse_repo"] = max(grup_totals.get("reverse_repo", 0), pct)
        elif any(k in gt for k in ["TPP", "PARA PİYASASI", "BPP"]):
            grup_totals["repo"] = max(grup_totals.get("repo", 0), pct)
        elif "BONO" in gt:
            grup_totals["private_bond"] = max(grup_totals.get("private_bond", 0), pct)
        elif "YABANCI" in gt or "YURT DIŞI" in gt:
            grup_totals["foreign_bond"] = max(grup_totals.get("foreign_bond", 0), pct)
        else:
            grup_totals["other"] = max(grup_totals.get("other", 0), pct)

    log(f"    Section III grup_totals: {grup_totals}", "INFO")

    # ─────────────────────────────────────────────────────────────────────────
    # STEP 3: Merge — use Section III values + Section IV total as total_pct
    #   If Section III sum is close to Section IV total → trust Section III
    #   If Section III sum is much smaller → use Section III values + Section IV total
    # ─────────────────────────────────────────────────────────────────────────
    sec3_sum = round(sum(grup_totals.values()), 2)
    sec4_total = round(sec4_pct.get("_fon_portfoy", 0), 2)

    if sec3_sum >= 50 and sec3_sum <= sec4_total + 5:
        # Section III is reliable
        total = sec3_sum
        result = {
            "stock_pct":                 grup_totals.get("stock", 0.0),
            "government_bond_pct":        grup_totals.get("treasury_bill", 0.0),
            "private_bond_pct":           grup_totals.get("private_bond", 0.0),
            "eurobond_pct":              0.0,
            "treasury_bill_pct":         grup_totals.get("treasury_bill", 0.0),
            "commercial_paper_pct":      0.0,
            "bank_bill_pct":             0.0,
            "gold_pct":                  0.0,
            "repo_pct":                  grup_totals.get("repo", 0.0),
            "reverse_repo_pct":          grup_totals.get("reverse_repo", 0.0),
            "byf_pct":                   0.0,
            "etf_pct":                   0.0,
            "term_deposit_pct":          grup_totals.get("term_deposit", 0.0),
            "precious_metals_pct":       0.0,
            "foreign_equity_pct":        0.0,
            "foreign_bond_pct":          grup_totals.get("foreign_bond", 0.0),
            "derivatives_pct":           0.0,
            "participation_account_pct": 0.0,
            "kiracert_pct":              0.0,
            "other_pct":                 grup_totals.get("other", 0.0),
            "total_pct":                 total,
            "extraction_method":         "para_piyasasi_text",
        }
    elif sec3_sum > 0 and sec4_total > 0:
        # Section III is partial — use Section IV as authoritative total
        # Remaining = T.Repo (para piyasası majority is T.Repo + Bono)
        remaining = round(sec4_total - sec3_sum, 2)

        # Apply remaining to reverse_repo (T.Repo — primary para piyasası instrument)
        # If we found private_bond and remaining > 0, remaining is likely T.Repo
        result = {
            "stock_pct":                 grup_totals.get("stock", 0.0),
            "government_bond_pct":        grup_totals.get("treasury_bill", 0.0),
            "private_bond_pct":           grup_totals.get("private_bond", 0.0),
            "eurobond_pct":              0.0,
            "treasury_bill_pct":         grup_totals.get("treasury_bill", 0.0),
            "commercial_paper_pct":      0.0,
            "bank_bill_pct":             0.0,
            "gold_pct":                  0.0,
            "repo_pct":                  grup_totals.get("repo", 0.0),
            "reverse_repo_pct":          remaining,  # T.Repo = the remaining
            "byf_pct":                   0.0,
            "etf_pct":                   0.0,
            "term_deposit_pct":          grup_totals.get("term_deposit", 0.0),
            "precious_metals_pct":       0.0,
            "foreign_equity_pct":        0.0,
            "foreign_bond_pct":          grup_totals.get("foreign_bond", 0.0),
            "derivatives_pct":           0.0,
            "participation_account_pct": 0.0,
            "kiracert_pct":              0.0,
            "other_pct":                 grup_totals.get("other", 0.0),
            "total_pct":                 sec4_total,
            "extraction_method":         "para_piyasasi_text+section4",
        }
    elif sec4_total > 0:
        # Only Section IV available — use fon_portfoy as total
        result = {
            "stock_pct":                 0.0,
            "government_bond_pct":        0.0,
            "private_bond_pct":           0.0,
            "eurobond_pct":              0.0,
            "treasury_bill_pct":         0.0,
            "commercial_paper_pct":      0.0,
            "bank_bill_pct":             0.0,
            "gold_pct":                  0.0,
            "repo_pct":                  0.0,
            "reverse_repo_pct":          0.0,
            "byf_pct":                   0.0,
            "etf_pct":                   0.0,
            "term_deposit_pct":          0.0,
            "precious_metals_pct":       0.0,
            "foreign_equity_pct":        0.0,
            "foreign_bond_pct":          0.0,
            "derivatives_pct":           0.0,
            "participation_account_pct": 0.0,
            "kiracert_pct":              0.0,
            "other_pct":                 0.0,
            "total_pct":                 sec4_total,
            "extraction_method":         "section4_total_only",
        }
    elif sec3_sum == 0 and sec4_total > 0:
        # Section III is empty but Section IV total is available (para piyasası / bono)
        # Allocate 100% to other_pct as a catch-all (real breakdown would need GLM)
        result = {
            "stock_pct":                 0.0,
            "government_bond_pct":        0.0,
            "private_bond_pct":           0.0,
            "eurobond_pct":              0.0,
            "treasury_bill_pct":         0.0,
            "commercial_paper_pct":       0.0,
            "bank_bill_pct":              0.0,
            "gold_pct":                  0.0,
            "repo_pct":                  0.0,
            "reverse_repo_pct":          0.0,
            "byf_pct":                   0.0,
            "etf_pct":                   0.0,
            "term_deposit_pct":           0.0,
            "precious_metals_pct":        0.0,
            "foreign_equity_pct":         0.0,
            "foreign_bond_pct":           0.0,
            "derivatives_pct":            0.0,
            "participation_account_pct":  0.0,
            "kiracert_pct":               0.0,
            "other_pct":                 sec4_total,
            "total_pct":                 sec4_total,
            "extraction_method":          "section4_total_only",
        }
    else:
        return None

    result["report_date"] = report_date
    return result


def _parse_hisse_tables(pdf_path: Path, raw_text: str = "", fund_code: str = "") -> Optional[dict]:
    """
    Parse hisse/karma fund from pdfplumber tables.
    Falls back to GLM if pdfplumber returns no data.
    """
    try:
        import pdfminer.high_level as pdfminer
        if not raw_text:
            raw_text = pdfminer.extract_text(str(pdf_path), maxpages=5)

        with pdfplumber.open(pdf_path) as pdf:
            report_date = ""
            total_pct = 0.0
            stock_pct = 0.0
            derivatives_pct = 0.0
            repo_pct = 0.0
            reverse_repo_pct = 0.0
            byf_pct = 0.0
            etf_pct = 0.0
            other_pct = 0.0

            for page in pdf.pages:
                tables = page.extract_tables()
                for table in tables:
                    if not table or not table[0]:
                        continue
                    first_cell = str(table[0][0]).strip() if table[0][0] else ""

                    # Skip non-portfolio tables
                    if not any(k in first_cell.upper() for k in [
                        "FON PORTFÖY DEĞERİ TABLOSU", "PORTFÖY DEĞERİ TABLOSU",
                        "VADEYE", "GRUP TOPLAMI", "A. GRUP", "A.GRUP"
                    ]):
                        continue

                    for row in table:
                        if not row or not row[0]:
                            continue
                        cell0 = str(row[0]).strip()

                        # Date
                        date_match = re.search(r"\((\d{2}/\d{2}/\d{4})\)", cell0)
                        if date_match and report_date == "":
                            day, month, year = date_match.group(1).split("/")
                            if 2000 <= int(year) <= 2099 and 1 <= int(month) <= 12:
                                report_date = f"{year}-{month}-{day}"

                        grup_pct = _parse_pct(_safe_col(row, 5))
                        top_pct  = _parse_pct(_safe_col(row, 6))
                        cell_upper = cell0.upper()

                        if grup_pct is None and top_pct is None:
                            continue

                        if "A.GRUP" in cell_upper and "TOPLAM" in cell_upper:
                            stock_pct = max(stock_pct, grup_pct or top_pct or 0)
                        elif "Ç.GRUP" in cell_upper and "TOPLAM" in cell_upper:
                            derivatives_pct = max(derivatives_pct, grup_pct or top_pct or 0)
                        elif re.search(r"T\.?REPO", cell_upper) and "TOPLAM" in cell_upper:
                            reverse_repo_pct = max(reverse_repo_pct, grup_pct or top_pct or 0)
                        elif "TPP" in cell_upper and "TOPLAM" in cell_upper:
                            repo_pct = max(repo_pct, grup_pct or top_pct or 0)
                        elif re.search(r"\bFON\b", cell_upper) and "TOPLAM" in cell_upper:
                            byf_pct = max(byf_pct, grup_pct or top_pct or 0)
                        elif "G.GRUP" in cell_upper and "TOPLAM" in cell_upper:
                            other_pct = max(other_pct, grup_pct or top_pct or 0)
                        elif "VIOP" in cell_upper and "TOPLAM" in cell_upper:
                            derivatives_pct = max(derivatives_pct, grup_pct or top_pct or 0)

            total_pct = round(stock_pct + derivatives_pct + other_pct, 2)
            if total_pct > 0:
                return {
                    "report_date":               report_date,
                    "stock_pct":                 round(stock_pct, 2),
                    "government_bond_pct":        0.0,
                    "private_bond_pct":           0.0,
                    "eurobond_pct":              0.0,
                    "treasury_bill_pct":         0.0,
                    "commercial_paper_pct":      0.0,
                    "bank_bill_pct":             0.0,
                    "gold_pct":                   0.0,
                    "repo_pct":                   round(repo_pct, 2),
                    "reverse_repo_pct":          round(reverse_repo_pct, 2),
                    "byf_pct":                    round(byf_pct, 2),
                    "etf_pct":                    0.0,
                    "term_deposit_pct":          0.0,
                    "precious_metals_pct":        0.0,
                    "foreign_equity_pct":         0.0,
                    "foreign_bond_pct":           0.0,
                    "derivatives_pct":            round(derivatives_pct, 2),
                    "participation_account_pct":  0.0,
                    "kiracert_pct":               0.0,
                    "other_pct":                  round(other_pct, 2),
                    "total_pct":                 total_pct,
                    "extraction_method":          "pdfplumber",
                }

        return None  # pdfplumber failed, let GLM handle it

    except Exception as e:
        log(f"_parse_hisse_tables error {fund_code}: {e}", "WARN")
        return None


def _safe_col(row, idx):
    """Safely get column value, return None if out of range or empty."""
    try:
        val = row[idx]
        if val is None:
            return None
        val = str(val).strip()
        return val if val else None
    except (IndexError, TypeError):
        return None


def _parse_pct(val: Optional[str]) -> Optional[float]:
    """Parse a percentage string like '74.01' or '74,01' or '' to float."""
    if val is None:
        return None
    val = val.strip().replace(",", ".").replace(" ", "")
    if not val or val == "-":
        return None
    try:
        return float(val)
    except ValueError:
        return None


# ─── Fund Summary Generator ──────────────────────────────────────────────────
def generate_fund_summary(raw_text: str, portfolio_data: dict, fund_code: str, fund_name: str = "") -> str:
    """
    Generate a 4-5 sentence Turkish summary of what the fund invests in.
    Called after portfolio extraction succeeds.
    """
    if not ZHIPU_API_KEY:
        return ""

    # Build allocation summary from portfolio data
    def _num(v):
        """Safely convert to float, defaulting to 0."""
        try:
            return float(v)
        except (TypeError, ValueError):
            return 0.0

    allocations = []
    p = portfolio_data
    if _num(p.get("stock_pct", 0)) > 1:
        allocations.append(f"hisse senedi (%{_num(p['stock_pct']):.1f})")
    if _num(p.get("government_bond_pct", 0)) > 1:
        allocations.append(f"devlet tahvili (%{_num(p['government_bond_pct']):.1f})")
    if _num(p.get("private_bond_pct", 0)) > 1:
        allocations.append(f"özel sektör tahvili (%{_num(p['private_bond_pct']):.1f})")
    if _num(p.get("eurobond_pct", 0)) > 1:
        allocations.append(f"eurobond (%{_num(p['eurobond_pct']):.1f})")
    if _num(p.get("treasury_bill_pct", 0)) > 1:
        allocations.append(f"hazine bonnosu (%{_num(p['treasury_bill_pct']):.1f})")
    if _num(p.get("reverse_repo_pct", 0)) > 1:
        allocations.append(f"ters repo (%{_num(p['reverse_repo_pct']):.1f})")
    if _num(p.get("repo_pct", 0)) > 1:
        allocations.append(f"repo (%{_num(p['repo_pct']):.1f})")
    if _num(p.get("term_deposit_pct", 0)) > 1:
        allocations.append(f"vadeli mevduat (%{_num(p['term_deposit_pct']):.1f})")
    if _num(p.get("byf_pct", 0)) > 1:
        allocations.append(f"yatırım fonu (%{_num(p['byf_pct']):.1f})")
    if _num(p.get("etf_pct", 0)) > 1:
        allocations.append(f"ETF (%{_num(p['etf_pct']):.1f})")
    if _num(p.get("derivatives_pct", 0)) > 1:
        allocations.append(f"türev araç (%{_num(p['derivatives_pct']):.1f})")
    if _num(p.get("foreign_equity_pct", 0)) > 1:
        allocations.append(f"yabancı hisse (%{_num(p['foreign_equity_pct']):.1f})")
    if _num(p.get("foreign_bond_pct", 0)) > 1:
        allocations.append(f"yabancı tahvil (%{_num(p['foreign_bond_pct']):.1f})")
    if _num(p.get("gold_pct", 0)) > 1:
        allocations.append(f"altın (%{_num(p['gold_pct']):.1f})")
    if _num(p.get("precious_metals_pct", 0)) > 1:
        allocations.append(f"değerli metal (%{_num(p['precious_metals_pct']):.1f})")
    if _num(p.get("other_pct", 0)) > 1:
        allocations.append(f"diğer (%{_num(p['other_pct']):.1f})")

    alloc_str = ", ".join(allocations) if allocations else "çeşitli varlıklar"

    prompt = f"""Bu Türk yatırım fonu hakkında 4-5 cümle yatırım özeti yaz. Türkçe olmalı.

Fon: {fund_code} {f'- {fund_name}' if fund_name else ''}
Öncelikli yatırımları: {alloc_str}
Rapor tarihi: {p.get('report_date', 'bilinmiyor')}

Her cümle farklı bir yatırım kategorisini açıklasın. Kısa ve öz ol. Toplam 4-5 cümle.

Örnek: "Bu fon, portföyünün %60'ını BIST'te işlem gören Türk şirket hisselerine yatırmaktadır. Yatırım stratejisi orta-vadeli sermaye artışı hedeflemektedir."

Sadece özet cümleleri yaz, başlık veya etiket ekleme."""

    headers = {"Authorization": f"Bearer {ZHIPU_API_KEY}", "Content-Type": "application/json"}
    payload = {
        "model": GLM_MODEL,
        "messages": [
            {"role": "system", "content": "You write Turkish fund investment summaries. Return ONLY the summary text. No JSON, no markdown, no explanation."},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.5,
        "max_tokens": 600,
    }

    try:
        resp = requests.post(
            f"{ZHIPU_API_BASE}/chat/completions",
            headers=headers,
            json=payload,
            timeout=GLM_TIMEOUT,
        )
        if resp.status_code == 200:
            data = resp.json()
            content = data["choices"][0]["message"].get("content", "").strip()
            if content:
                log(f"  📝 Fund summary generated ({len(content)} chars)")
                return content
    except Exception as e:
        log(f"  ⚠️ Fund summary generation failed: {e}", "WARN")

    return ""


# ─── Zhipu AI Fallback ─────────────────────────────────────────────────────────
def _normalize_pct(value) -> float:
    """Normalize stock_pct from GLM — handles string '74.66%', number 88.49, None."""
    if value is None:
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    s = str(value).strip().replace("%", "").replace(",", ".")
    try:
        return float(s)
    except (ValueError, TypeError):
        return 0.0


def _parse_turkish_number(s: str) -> Optional[float]:
    """
    Parse Turkish number string to float.
    Handles: 1.234.567,89 (binlik nokta, ondalık virgül)
    Also handles: 1234567.89 or 1234567,89 (English)
    Returns None for values > 1_000_000 (likely nominal, not %).
    """
    if not s:
        return None
    s = s.strip()
    # Turkish format: dots are thousand sep, comma is decimal
    if s.count(".") > 0 and "," in s:
        # Likely Turkish: remove dots, replace comma with dot
        s = s.replace(".", "").replace(",", ".")
    elif "," in s and s.count(",") == 1:
        # Could be Turkish decimal comma or English thousand
        parts = s.split(",")
        if len(parts[1]) <= 2:
            # Likely Turkish decimal
            s = s.replace(",", ".")
        else:
            # Likely English thousand with comma
            s = s.replace(",", "")
    try:
        val = float(s)
        # Reject very large values (nominal amounts, not %)
        return val if val <= 10_000_000_000 else None
    except (ValueError, TypeError):
        return None


def _parse_para_piyasasi(raw_text: str, fund_code: str) -> Optional[dict]:
    """
    Parse para piyasası / bono / diğer fonlarda GRUP TOPLAMI satırlarından
    kategori yüzdelerini çıkar. Bu fonlarda standart A.Grup tablosu YOKTUR —
    sadece Section III (GRUP TOPLAMI) vardır.
    
    Her GRUP TOPLAMI satırında 5 sayısal değer var:
    [NOMİNAL DEĞER, TOPLAM DEĞER, 100.00, GRUP1%, GRUP2%]
    veya
    [NOMİNAL DEĞER, TOPLAM DEĞER, 100.00, GRUP%]
    
    Son 3 değer yüzdelerdir (0-100 arasında).
    Returns: dict with stock_pct=0, other_pct=total_grupo_pct, extraction_method="para_piyasasi_parse"
    """
    grups = []
    for line in raw_text.split("\n"):
        if "GRUP TOPLAMI" not in line.upper():
            continue

        # Extract ALL numbers from this line (Turkish format)
        raw_nums = re.findall(r"[\d]+[.\d]*[,.]?\d*", line)
        vals = []
        for n in raw_nums:
            parsed = _parse_turkish_number(n)
            if parsed is not None:
                vals.append(parsed)

        # Partition into groups of 5 (or more) — last 3 of each group are %
        # Each GRUP TOPLAMI line has 5 values: NOMINAL, TOPLAM, 100, PCT1, PCT2
        # For 2 groups per line: 10 values → last 3 from each group
        # We process in reverse: take last 3, then skip back 2, take last 3
        i = len(vals)
        line_groups = []
        while i >= 3:
            pct1, pct2, pct3 = vals[i - 3], vals[i - 2], vals[i - 1]
            if all(0 <= v <= 100 for v in [pct1, pct2, pct3]):
                total = round(pct1 + pct2 + pct3, 2)
                if total > 0:
                    line_groups.append((pct1, pct2, pct3, total))
            i -= 5 if i >= 5 else 3  # skip back 5 if possible, else 3

        # Also try simple last-3 approach for lines with just one group
        if not line_groups and len(vals) >= 3:
            pct_vals = [v for v in vals if 0 <= v <= 100]
            if len(pct_vals) >= 3:
                p1, p2, p3 = pct_vals[-3], pct_vals[-2], pct_vals[-1]
                total = round(p1 + p2 + p3, 2)
                if total > 0:
                    grups.append((p1, p2, p3, total))
        else:
            grups.extend(line_groups)

    if not grups:
        return None

    # Use the largest group total
    best = max(grups, key=lambda x: x[3])
    total_pct = best[3]

    # Report date
    date_match = re.search(r"\((\d{2}/\d{2}/\d{4})\)", raw_text)
    report_date = ""
    if date_match:
        day, month, year = date_match.group(1).split("/")
        report_date = f"{year}-{month}-{day}"

    log(f"  Para piyasası parse: grups={grups}, using={best}", "INFO")
    return {
        "report_date": report_date,
        "stock_pct": 0.0,
        "government_bond_pct": 0.0,
        "private_bond_pct": 0.0,
        "eurobond_pct": 0.0,
        "treasury_bill_pct": 0.0,
        "commercial_paper_pct": 0.0,
        "bank_bill_pct": 0.0,
        "gold_pct": 0.0,
        "repo_pct": 0.0,
        "reverse_repo_pct": 0.0,
        "byf_pct": 0.0,
        "etf_pct": 0.0,
        "term_deposit_pct": 0.0,
        "precious_metals_pct": 0.0,
        "foreign_equity_pct": 0.0,
        "foreign_bond_pct": 0.0,
        "derivatives_pct": 0.0,
        "participation_account_pct": 0.0,
        "kiracert_pct": 0.0,
        "other_pct": total_pct,
        "total_pct": total_pct,
        "extraction_method": "para_piyasasi_parse",
    }


def extract_with_glm(raw_text: str, fund_code: str, fund_name: str = "") -> Optional[dict]:
    """
    GLM-4.5-air fallback for PDFs where pdfplumber extraction failed.
    Uses response_format: json_object for reliable JSON output.

    IMPORTANT: glm-4.5-air is a THINKING model — it uses reasoning_content for
    thought process and content for actual output. response_format: json_object
    ensures JSON appears in content field.
    """
    if not ZHIPU_API_KEY:
        log("ZHIPU_API_KEY not set!", "ERROR")
        return None

    # Very short, directive-style prompt to minimize thinking
    user_prompt = f"""Extract portfolio allocation percentages from this KAP fund report.

Fund: {fund_code}
Date: Look for date in format DD/MM/YYYY

Return ONLY valid JSON:
{{"report_date":"YYYY-MM-DD","stock_pct":0,"government_bond_pct":0,"private_bond_pct":0,"eurobond_pct":0,"treasury_bill_pct":0,"commercial_paper_pct":0,"bank_bill_pct":0,"gold_pct":0,"repo_pct":0,"reverse_repo_pct":0,"byf_pct":0,"etf_pct":0,"term_deposit_pct":0,"precious_metals_pct":0,"foreign_equity_pct":0,"foreign_bond_pct":0,"derivatives_pct":0,"participation_account_pct":0,"kiracert_pct":0,"other_pct":0,"total_pct":0}}

PDF text:
{raw_text[:5000]}

Return ONLY the JSON. No explanation."""

    headers = {"Authorization": f"Bearer {ZHIPU_API_KEY}", "Content-Type": "application/json"}

    payload = {
        "model": GLM_MODEL,
        "messages": [
            {"role": "system", "content": "You extract structured data. Return ONLY RFC 8259 JSON. No markdown, no explanation."},
            {"role": "user",   "content": user_prompt},
        ],
        "temperature": 0.02,
        "max_tokens": 2000,
        "response_format": {"type": "json_object"},
    }

    for attempt in range(3):
        try:
            resp = requests.post(
                f"{ZHIPU_API_BASE}/chat/completions",
                headers=headers,
                json=payload,
                timeout=GLM_TIMEOUT,
            )

            if resp.status_code == 200:
                data = resp.json()
                msg  = data["choices"][0]["message"]
                content = (msg.get("content") or "").strip()

                if not content:
                    # GLM reasoning models put JSON in reasoning_content
                    reasoning_content = (msg.get("reasoning_content") or "").strip()
                    if reasoning_content:
                        # Find ALL JSON objects in reasoning_content, try each
                        import re as _re
                        json_matches = list(_re.finditer(r'\{[^{}]*\}', reasoning_content))
                        for m in json_matches:
                            try:
                                candidate = m.group(0)
                                # Validate it looks like portfolio data before parsing
                                if '"stock"' in candidate or '"report_date"' in candidate or '"stock_pct"' in candidate:
                                    parsed = json.loads(candidate)
                                    if "stock_pct" in parsed or "report_date" in parsed:
                                        log(f"  ✅ JSON from reasoning_content for {fund_code} (attempt {attempt+1})")
                                        parsed["ai_model"] = GLM_MODEL
                                        parsed["ai_token_count"] = data.get("usage", {}).get("total_tokens", 0)
                                        parsed["extraction_method"] = "glm_fallback"
                                        return parsed
                            except json.JSONDecodeError:
                                continue
                        # Last resort: find last '{' and last '}'
                        js = reasoning_content.rfind('{')
                        je = reasoning_content.rfind('}')
                        if js >= 0 and je > js:
                            try:
                                parsed = json.loads(reasoning_content[js:je+1])
                                if "stock_pct" in parsed or "report_date" in parsed:
                                    log(f"  ✅ JSON from reasoning_content (last resort) for {fund_code}")
                                    parsed["ai_model"] = GLM_MODEL
                                    parsed["ai_token_count"] = data.get("usage", {}).get("total_tokens", 0)
                                    parsed["extraction_method"] = "glm_fallback"
                                    return parsed
                            except json.JSONDecodeError:
                                pass
                    log(f"GLM empty content for {fund_code} (attempt {attempt+1})", "WARN")
                    time.sleep(2)
                    continue

                # Try to find JSON object in content
                json_start = content.find("{")
                json_end   = content.rfind("}") + 1
                if json_start == -1 or json_end == 0:
                    log(f"No JSON in GLM response for {fund_code}", "WARN")
                    log(f"Response: {content[:300]}", "WARN")
                    continue

                content = content[json_start:json_end]
                result  = json.loads(content)
                result["ai_model"]        = GLM_MODEL
                result["ai_token_count"]  = data.get("usage", {}).get("total_tokens", 0)
                result["extraction_method"] = "glm_fallback"
                return result

            elif resp.status_code in (401, 403):
                log(f"Zhipu API auth error {resp.status_code}", "ERROR")
                return None
            elif resp.status_code == 429:
                wait = 2 ** attempt * 5
                log(f"Rate limited, waiting {wait}s...", "WARN")
                time.sleep(wait)
            else:
                log(f"Zhipu API error {resp.status_code}: {resp.text[:200]}", "ERROR")

        except requests.exceptions.Timeout:
            log(f"Timeout attempt {attempt+1}/3 for {fund_code}", "WARN")
            time.sleep(5)
        except Exception as e:
            log(f"GLM exception: {e}", "ERROR")
            break

    return None


# ─── Supabase Upsert ──────────────────────────────────────────────────────────
def _validate_date(date_str: str) -> str:
    """Validate and fix impossible dates like 2026-02-29 → 2026-02-28.
    Also fixes incomplete dates like "2026-02" or "2026" → fallback.
    Returns a fallback date if date_str is empty/invalid.
    """
    if not date_str:
        return "2025-12-31"  # fallback when GLM can't extract date
    import calendar
    try:
        from datetime import date
        parts = date_str.split("-")
        if len(parts) != 3:
            return "2025-12-31"  # incomplete date like "2026-02" → fallback
        year, month, day = int(parts[0]), int(parts[1]), int(parts[2])
        max_day = calendar.monthrange(year, month)[1]
        if day > max_day:
            return f"{year:04d}-{month:02d}-{max_day:02d}"
        # Sanity check: reject future dates or absurd years
        if year > 2100 or year < 1900 or month < 1 or month > 12 or day < 1:
            return "2025-12-31"
        return f"{year:04d}-{month:02d}-{day:02d}"
    except (ValueError, AttributeError, IndexError):
        return "2025-12-31"


def upsert_breakdown(data: dict) -> bool:
    """Upsert portfolio breakdown into Supabase via PostgREST REST API."""
    if not SUPABASE_KEY:
        log("SUPABASE_SERVICE_KEY not set!", "ERROR")
        return False

    try:
        report_date = _validate_date(data.get("report_date", "") or "")

        record = {
            "fund_code": data["fund_code"],
            "report_date": report_date,

            "stock_pct":               data.get("stock_pct", 0) or 0,
            "government_bond_pct":     data.get("government_bond_pct", 0) or 0,
            "private_bond_pct":       data.get("private_bond_pct", 0) or 0,
            "eurobond_pct":           data.get("eurobond_pct", 0) or 0,
            "treasury_bill_pct":      data.get("treasury_bill_pct", 0) or 0,
            "commercial_paper_pct":   data.get("commercial_paper_pct", 0) or 0,
            "bank_bill_pct":          data.get("bank_bill_pct", 0) or 0,
            "gold_pct":               data.get("gold_pct", 0) or 0,
            "repo_pct":               data.get("repo_pct", 0) or 0,
            "reverse_repo_pct":       data.get("reverse_repo_pct", 0) or 0,
            "byf_pct":                data.get("byf_pct", 0) or 0,
            "etf_pct":                data.get("etf_pct", 0) or 0,
            "term_deposit_pct":       data.get("term_deposit_pct", 0) or 0,
            "precious_metals_pct":    data.get("precious_metals_pct", 0) or 0,
            "foreign_equity_pct":     data.get("foreign_equity_pct", 0) or 0,
            "foreign_bond_pct":       data.get("foreign_bond_pct", 0) or 0,
            "derivatives_pct":        data.get("derivatives_pct", 0) or 0,
            "participation_account_pct": data.get("participation_account_pct", 0) or 0,
            "kiracert_pct":           data.get("kiracert_pct", 0) or 0,
            "other_pct":              data.get("other_pct", 0) or 0,

            "total_pct":              data.get("total_pct", 0) or 0,
            "fund_summary":           data.get("fund_summary", ""),
            "extraction_method":      data.get("extraction_method", ""),
            "ai_model":               data.get("ai_model"),
            "ai_token_count":         data.get("ai_token_count"),
        }

        headers = {
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "apikey": SUPABASE_KEY,
            "Content-Type": "application/json",
            "Prefer": "resolution=update",
        }

        resp = requests.post(
            f"{SUPABASE_URL}/rest/v1/portfolio_breakdown",
            headers=headers,
            json=record,
            timeout=15,
        )

        if resp.status_code not in (200, 201, 204, 406, 409):
            log(f"Supabase upsert error: {resp.status_code} — {resp.text[:200]}", "ERROR")
            return False

        return True

    except Exception as e:
        log(f"Supabase upsert exception: {e}", "ERROR")
        return False


# ─── SQLite Tracking ───────────────────────────────────────────────────────────
def mark_parsed(fund_code: str, success: bool, error: str = ""):
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS kap_parse_log (
            fund_code TEXT PRIMARY KEY,
            parsed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            success INTEGER,
            error TEXT
        )
    """)
    c.execute("INSERT OR REPLACE INTO kap_parse_log (fund_code, success, error) VALUES (?, ?, ?)",
              (fund_code, 1 if success else 0, error))
    conn.commit()
    conn.close()


def _create_job_run(total_funds: int) -> int | None:
    """Create a parse_job_runs record via Management API, return job id."""
    MANAGEMENT_TOKEN = "sbp_b5c8f969b5955ca8c8a2e1ae1a109c9e9ee183fc"
    try:
        resp = requests.post(
            "https://api.supabase.com/v1/projects/oqkobptbvcazifpvjwfz/database/query",
            headers={
                "Authorization": f"Bearer {MANAGEMENT_TOKEN}",
                "Content-Type": "application/json",
            },
            json={
                "query": f"INSERT INTO parse_job_runs (total_funds, status, started_at) "
                         f"VALUES ({total_funds}, 'running', NOW()) "
                         f"RETURNING id"
            },
            timeout=15,
        )
        if resp.status_code == 201:
            data = resp.json()
            if isinstance(data, list) and data:
                return data[0].get("id")
            elif isinstance(data, dict):
                return data.get("id")
        log(f"_create_job_run failed: {resp.status_code} {resp.text[:200]}", "WARN")
    except Exception as e:
        log(f"_create_job_run exception: {e}", "WARN")
    return None


def _update_job_run(job_id: int | None, status: str, success: int, failed: int, categories: dict):
    """Update parse_job_runs record at end of batch via Management API."""
    if not job_id:
        return
    MANAGEMENT_TOKEN = "sbp_b5c8f969b5955ca8c8a2e1ae1a109c9e9ee183fc"
    try:
        from datetime import datetime as dt
        resp = requests.post(
            "https://api.supabase.com/v1/projects/oqkobptbvcazifpvjwfz/database/query",
            headers={
                "Authorization": f"Bearer {MANAGEMENT_TOKEN}",
                "Content-Type": "application/json",
            },
            json={
                "query": f"UPDATE parse_job_runs SET status='{status}', ended_at=NOW(), "
                         f"success_count={success}, failed_count={failed}, "
                         f"categories='{json.dumps(categories)}' "
                         f"WHERE id={job_id}"
            },
            timeout=15,
        )
        if resp.status_code != 201:
            log(f"_update_job_run failed: {resp.status_code} {resp.text[:200]}", "WARN")
    except Exception as e:
        log(f"_update_job_run exception: {e}", "WARN")


def get_parsed_codes() -> set:
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT fund_code FROM kap_parse_log WHERE success=1")
        return {row[0] for row in c.fetchall()}
    except:
        return set()


# ─── Fund Type → Category Mapping ───────────────────────────────────────────────
# TEFAS fund_type (DB) → KAP parse category
FUND_TYPE_MAP = {
    "BYF": "HISSE",    # Hisse fonları
    "VFF": "KARMA",    # Değişken/karma fonlar
    "OKS": "KIRA",     # Kira sertifikası / katılım fonları
    "SRF": "HISSE",    # Yabancı fonlar — yabancı hisse senedi portföyü, HISSE formatında parse et
    "KFF": "PARA",     # Para piyasası / borçlanma
    "ALTIN": "SKIP",   # Altın fonları — standart portföy tablosu yok
    "DÖVİZ": "SKIP",  # Döviz fonları — standart portföy tablosu yok
}

def _fund_type_to_category(fund_type: str) -> str:
    """Map TEFAS fund_type to KAP parse category."""
    if not fund_type:
        return "UNKNOWN"
    return FUND_TYPE_MAP.get(fund_type.upper(), "UNKNOWN")


def _get_fund_type_from_db(fund_codes: list[str]) -> dict[str, str]:
    """
    Fetch fund_type for a list of fund codes from Supabase DB (Management API).
    Returns {fund_code: fund_type}.
    """
    if not fund_codes:
        return {}
    # Management API token — hardcoded (no env var needed)
    MANAGEMENT_TOKEN = "sbp_b5c8f969b5955ca8c8a2e1ae1a109c9e9ee183fc"
    codes_str = ",".join(f"'{c}'" for c in fund_codes)
    try:
        resp = requests.post(
            "https://api.supabase.com/v1/projects/oqkobptbvcazifpvjwfz/database/query",
            headers={
                "Authorization": f"Bearer {MANAGEMENT_TOKEN}",
                "Content-Type": "application/json",
            },
            json={"query": f"SELECT code, fund_type FROM funds WHERE code IN ({codes_str})"},
            timeout=30,
        )
        if resp.status_code in (200, 201):
            return {row["code"]: row["fund_type"] for row in resp.json()}
    except Exception as e:
        log(f"_get_fund_type_from_db failed: {e}", "WARN")
    return {}


# ─── Get Fund Name via REST ───────────────────────────────────────────────────
def get_fund_name_from_supabase(fund_code: str) -> str:
    """Supabase funds tablosundan fon adını al (REST API)."""
    if not SUPABASE_KEY:
        return ""
    try:
        headers = {"Authorization": f"Bearer {SUPABASE_KEY}", "apikey": SUPABASE_KEY}
        resp = requests.get(
            f"{SUPABASE_URL}/rest/v1/funds?code=eq.{fund_code}&select=name&limit=1",
            headers=headers,
            timeout=10,
        )
        if resp.status_code == 200 and resp.json():
            return resp.json()[0].get("name", "")
    except:
        pass
    return ""


# ─── Parse Single PDF ─────────────────────────────────────────────────────────
def parse_single_pdf(pdf_path: Path, fund_code: str, category_override: str | None = None) -> Optional[dict]:
    """
    Parse a single PDF using category-aware extraction.

    KARMA   → GLM directly (no pdfplumber)
    HISSE   → parse_portfolio_tables → _parse_hisse_karma_glm → GLM
    PARA    → parse_portfolio_tables → text-based parsing
    SERBEST/KIRA → skip (return None)
    UNKNOWN → try parse_portfolio_tables → GLM fallback
    """
    import pdfminer.high_level

    # ── KARMA: skip pdfplumber, go straight to GLM ──────────────────────────
    if category_override == "KARMA":
        log(f"  KARMA fund: GLM directly (no pdfplumber)", "INFO")
        raw_text = None
        for mp in [3, 1]:  # Try maxpages=3 first, then 1
            try:
                raw_text = pdfminer.high_level.extract_text(str(pdf_path), maxpages=mp)
                if raw_text and len(raw_text.strip()) > 50:
                    break
            except Exception as e:
                log(f"  PDF read (maxpages={mp}) failed for {fund_code}: {e}", "WARN")
                raw_text = None
        if not raw_text:
            log(f"  ❌ PDF read failed for {fund_code} (all attempts)", "ERROR")
            mark_parsed(fund_code, success=False, error=f"PDF read failed (all attempts)")
            return None
        fund_name = get_fund_name_from_supabase(fund_code)
        result = extract_with_glm(raw_text, fund_code, fund_name) if raw_text else None
        if not result:
            log(f"  ❌ KARMA GLM failed", "ERROR")
            mark_parsed(fund_code, success=False, error="KARMA GLM extraction failed")
            return None
        if "stock_pct" in result:
            result["stock_pct"] = _normalize_pct(result["stock_pct"])
        log(f"  ✅ KARMA GLM success: stock={result.get('stock_pct', '?')}%", "INFO")
        result["fund_code"] = fund_code
        ok = upsert_breakdown(result)
        if ok:
            log(f"  ✅ Upserted {fund_code}", "INFO")
            mark_parsed(fund_code, success=True)
        else:
            log(f"  ❌ Supabase upsert failed for {fund_code}", "ERROR")
            mark_parsed(fund_code, success=False, error="Supabase upsert failed")
        return result

    # ── HISSE/PARA/UNKNOWN → parse_portfolio_tables ──────────────────────────
    result = parse_portfolio_tables(pdf_path, fund_code, category_override)

    # ── Fallback: HISSE/UNKNOWN → GLM ─────────────────────────────────────
    if not result:
        # category_override may be None (direct call without DB lookup) — treat as UNKNOWN
        cat = category_override if category_override else "UNKNOWN"
        if cat in ("HISSE", "UNKNOWN", "KARMA", "PARA"):
            log(f"  Fallback: attempting GLM for {cat}...", "WARN")
            try:
                raw_text = pdfminer.high_level.extract_text(str(pdf_path), maxpages=5)
            except Exception as e:
                log(f"  Fallback PDF read failed for {fund_code}: {e}", "WARN")
                raw_text = None
            fund_name = get_fund_name_from_supabase(fund_code)
            result = extract_with_glm(raw_text, fund_code, fund_name) if raw_text else None
            if result and "stock_pct" in result:
                result["stock_pct"] = _normalize_pct(result["stock_pct"])
        if not result:
            log(f"  ❌ {category_override or 'UNKNOWN'} extraction failed", "ERROR")
            mark_parsed(fund_code, success=False, error=f"Extraction failed")
            return None

    # ── Determine final category ─────────────────────────────────────────────
    if category_override:
        category = category_override
    else:
        try:
            raw_text = pdfminer.high_level.extract_text(str(pdf_path), maxpages=5)
        except Exception as e:
            log(f"  Category detection PDF read failed for {fund_code}: {e}", "WARN")
            raw_text = None
        category = detect_fund_category(raw_text) if raw_text else "UNKNOWN"

    log(f"  {category} fund: {result.get('extraction_method', '?')}", "INFO")

    # ── Post-process ─────────────────────────────────────────────────────────
    result["fund_code"] = fund_code
    ok = upsert_breakdown(result)
    if ok:
        log(f"  ✅ Upserted {fund_code} — total={result.get('total_pct', '?')}%", "INFO")
        mark_parsed(fund_code, success=True)
    else:
        log(f"  ❌ Supabase upsert failed for {fund_code}", "ERROR")
        mark_parsed(fund_code, success=False, error="Supabase upsert failed")
    return result


# ─── Batch Process ─────────────────────────────────────────────────────────────
def batch_process(limit: int = 0, resume: bool = False):
    """Process all pending PDFs.

    For each fund, fetches fund_type from DB (Supabase Management API),
    maps it to KAP category via _fund_type_to_category(), and passes it
    to parse_single_pdf as category_override (skipping detect_fund_category).
    """
    if not ZHIPU_API_KEY:
        log("ZHIPU_API_KEY not set! Cannot use GLM fallback.", "WARN")

    pdfs = sorted(PDF_DIR.glob("*.pdf"))
    log(f"Found {len(pdfs)} PDF files in {PDF_DIR}")

    already_parsed = get_parsed_codes() if not resume else set()

    pending = []
    for pdf_path in pdfs:
        fund_code = pdf_path.stem.split("_")[0]
        if fund_code in already_parsed and not resume:
            continue
        pending.append((pdf_path, fund_code))

    log(f"Pending: {len(pending)} PDFs (resume={resume})")
    if not pending:
        log("No pending PDFs to process.")
        return

    # ── Pre-fetch fund_type from DB for all pending funds ─────────────────────
    fund_codes = [code for _, code in pending]
    fund_types = _get_fund_type_from_db(fund_codes)
    log(f"DB fund_type lookup: {len(fund_types)}/{len(fund_codes)} found")

    # ── Pre-filter: skip SERBEST/KIRA/SKIP before processing ───────────────────
    skip_categories: dict[str, int] = {"SERBEST": 0, "KIRA": 0, "SKIP": 0}
    filtered: list[tuple[Path, str, str]] = []  # (pdf_path, fund_code, category)
    for pdf_path, fund_code in pending:
        fund_type = fund_types.get(fund_code, "")
        category = _fund_type_to_category(fund_type) if fund_type else ""
        if category in ("SERBEST", "KIRA", "SKIP"):
            skip_categories[category] += 1
            log(f"  Skipping {fund_code} (DB fund_type={fund_type}) → {category}", "WARN")
            continue
        filtered.append((pdf_path, fund_code, category))

    # Apply limit AFTER filtering (so limit controls actual processing, not skips)
    if limit > 0:
        filtered = filtered[:limit]

    log(f"Skipped: {skip_categories} | Processing: {len(filtered)} funds")

    # ── Supabase Job Run tracking ───────────────────────────────────────────
    job_id = _create_job_run(len(filtered))
    categories: dict[str, int] = {}
    success = 0
    failed  = 0

    for i, (pdf_path, fund_code, category) in enumerate(filtered, 1):
        category_override = category if category not in ("", "UNKNOWN") else None
        log(f"[{i}/{len(filtered)}] Processing {fund_code} ({pdf_path.name})")
        if category_override:
            log(f"  DB → KAP category={category_override}")
        result = parse_single_pdf(pdf_path, fund_code, category_override)
        cat = result.get("category", "UNKNOWN") if result else "FAILED"
        categories[cat] = categories.get(cat, 0) + 1
        if result:
            success += 1
        else:
            failed += 1
        time.sleep(1.0)  # rate limit

    _update_job_run(job_id, "completed", success, failed, categories)
    log(f"=== BATCH COMPLETE: {success} ✅  {failed} ❌ ===")


def resume_failed():
    """Retry failed parses."""
    if not ZHIPU_API_KEY:
        log("ZHIPU_API_KEY not set!", "ERROR")
        return

    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT fund_code FROM kap_parse_log WHERE success=0")
        failed_codes = [row[0] for row in c.fetchall()]
        conn.close()

        pending = []
        for code in failed_codes:
            matches = list(PDF_DIR.glob(f"{code}_*.pdf"))
            if matches:
                pending.append((matches[0], code))

        log(f"Retrying {len(pending)} failed PDFs...")
        success = failed = 0

        for i, (pdf_path, fund_code) in enumerate(pending, 1):
            log(f"[{i}/{len(pending)}] Retrying {fund_code}")
            result = parse_single_pdf(pdf_path, fund_code)
            if result:
                success += 1
            else:
                failed += 1
            time.sleep(1.0)

        log(f"=== RESUME COMPLETE: {success} ✅  {failed} ❌ ===")

    except Exception as e:
        log(f"Resume error: {e}", "ERROR")


# ─── CLI ──────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="KAP Portfolio PDF Parser")
    parser.add_argument("--test",  metavar="FILE",          help="Test with single PDF file")
    parser.add_argument("--batch", action="store_true",     help="Process all pending PDFs")
    parser.add_argument("--fund",  metavar="CODE",           help="Process specific fund code")
    parser.add_argument("--resume", action="store_true",     help="Retry failed parses")
    parser.add_argument("--limit",  type=int, default=0,     help="Limit batch to N PDFs")

    args = parser.parse_args()

    log("=" * 60)
    log("KAP Portfolio Parser — pdfplumber + GLM fallback")
    log(f"PDF dir: {PDF_DIR}")
    log(f"Zhipu key: {'SET' if ZHIPU_API_KEY else 'NOT SET ⚠️'}")
    log(f"Supabase key: {'SET' if SUPABASE_KEY else 'NOT SET ⚠️'}")
    log("=" * 60)

    if args.test:
        pdf_path = PDF_DIR / args.test
        if not pdf_path.exists():
            pdf_path = Path(args.test)
        fund_code = pdf_path.stem.split("_")[0]
        result = parse_single_pdf(pdf_path, fund_code)
        if result:
            print(json.dumps(result, indent=2, default=str))

    elif args.fund:
        matches = list(PDF_DIR.glob(f"{args.fund}_*.pdf"))
        if not matches:
            log(f"No PDF for fund: {args.fund}", "ERROR")
            sys.exit(1)
        result = parse_single_pdf(matches[0], args.fund)
        if result:
            print(json.dumps(result, indent=2, default=str))

    elif args.batch:
        batch_process(limit=args.limit)

    elif args.resume:
        resume_failed()

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
