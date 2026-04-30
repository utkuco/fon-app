#!/usr/bin/env python3
"""
Export DB to JSON for static hosting.
- All Tefas funds with NAV, price, market_cap, breakdown
- Price history: last 30 days only (keeps JSON small)
- Category rankings (rank, percentile)
- Gemini/KAP individual holdings
"""
import json
import re
import sqlite3
from pathlib import Path

DB = Path(__file__).parent / "db" / "fonapp.db"
OUT = Path(__file__).parent / "web" / "public" / "data.json"

HISTORY_DAYS = 365  # Full year for main JSON

conn = sqlite3.connect(str(DB))
conn.row_factory = sqlite3.Row
cur = conn.cursor()

def translate_title(title: str) -> str:
    """Translate common English Tefas fund title patterns to Turkish."""
    if not title:
        return title
    t = title

    # MONEY MARKET → Para Piyasası
    t = re.sub(r'\bMONEY MARKET\b', 'PARA PİYASASI', t, flags=re.IGNORECASE)
    t = re.sub(r'\bMONEY MARKET FUND\b', 'PARA PİYASASI FONU', t, flags=re.IGNORECASE)
    t = re.sub(r'\bMONEY MARKET\b', 'PARA PİYASASI', t, flags=re.IGNORECASE)

    # GOLD → Altın
    t = re.sub(r'\bGOLD\b', 'ALTIN', t, flags=re.IGNORECASE)

    # PARTICIPATION / KATILIM
    t = re.sub(r'\bPARTICIPATION\b', 'KATILIM', t, flags=re.IGNORECASE)

    # PENSION / EMEKLİLİK
    t = re.sub(r'\bPENSION\b', 'EMEKLİLİK', t, flags=re.IGNORECASE)

    # MUTUAL FUND / YATIRIM FONU
    t = re.sub(r'\bMUTUAL FUND\b', 'YATIRIM FONU', t, flags=re.IGNORECASE)
    t = re.sub(r'\bPENSION MUTUAL FUND\b', 'EMEKLİLİK YATIRIM FONU', t, flags=re.IGNORECASE)
    t = re.sub(r'\bMUTUAL\b', 'YATIRIM', t, flags=re.IGNORECASE)

    # LEASE CERTIFICATE / KİRA SERTİFİKASI
    t = re.sub(r'\bLEASE CERTIFICATE\b', 'KİRA SERTİFİKASI', t, flags=re.IGNORECASE)
    t = re.sub(r'\bLEASE CERT\b', 'KİRA SERT', t, flags=re.IGNORECASE)

    # SUKUK
    t = re.sub(r'\bSUKUK\b', 'SUKUK', t, flags=re.IGNORECASE)

    # EQUITY / HİSSE
    t = re.sub(r'\bEQUITY\b', 'HİSSE', t, flags=re.IGNORECASE)
    t = re.sub(r'\bSTOCK\b', 'HİSSE', t, flags=re.IGNORECASE)

    # BOND / TAHVİL / BORÇLANMA
    t = re.sub(r'\bBOND\b', 'TAHVİL', t, flags=re.IGNORECASE)
    t = re.sub(r'\bFIXED INCOME\b', 'BORÇLANMA', t, flags=re.IGNORECASE)

    # DÖVİZ / FX / FOREIGN
    t = re.sub(r'\bFOREIGN\b', 'YABANCI', t, flags=re.IGNORECASE)
    t = re.sub(r'\bFX\b', 'DÖVİZ', t, flags=re.IGNORECASE)
    t = re.sub(r'\bDOLLAR\b', 'DOLAR', t, flags=re.IGNORECASE)
    t = re.sub(r'\bEURO\b', 'AVRO', t, flags=re.IGNORECASE)
    t = re.sub(r'\bUSD\b', 'USD', t, flags=re.IGNORECASE)
    t = re.sub(r'\bEUR\b', 'AVRO', t, flags=re.IGNORECASE)

    # SHORT / SHORT TERM
    t = re.sub(r'\bSHORT TERM\b', 'KISA VADELİ', t, flags=re.IGNORECASE)
    t = re.sub(r'\bLONG TERM\b', 'UZUN VADELİ', t, flags=re.IGNORECASE)

    # DIVIDEND
    t = re.sub(r'\bDIVIDEND\b', 'TEMETTÜ', t, flags=re.IGNORECASE)

    # GROWTH / BÜYÜME
    t = re.sub(r'\bGROWTH\b', 'BÜYÜME', t, flags=re.IGNORECASE)

    # BALANCED / DENGE
    t = re.sub(r'\bBALANCED\b', 'DENGELİ', t, flags=re.IGNORECASE)

    # INDEX
    t = re.sub(r'\bINDEX\b', 'ENDEKS', t, flags=re.IGNORECASE)

    # ETF / BYF
    t = re.sub(r'\bETF\b', 'BYF', t, flags=re.IGNORECASE)

    # MANAGEMENT / YÖNETİM
    t = re.sub(r'\bMANAGEMENT\b', 'YÖNETİM', t, flags=re.IGNORECASE)
    t = re.sub(r'\bASSET MANAGEMENT\b', 'VARLIK YÖNETİMİ', t, flags=re.IGNORECASE)

    # DÖVİZ
    t = re.sub(r'\bDÖVİZ\b', 'DÖVİZ', t, flags=re.IGNORECASE)

    # FIX: ASSET MANAGEMENT before MANAGEMENT to avoid double replace
    # (already done above)

    # ASSET
    t = re.sub(r'\bASSET\b', 'VARLIK', t, flags=re.IGNORECASE)

    # FUND / FONS
    t = re.sub(r'\bFUND\b', 'FON', t, flags=re.IGNORECASE)
    t = re.sub(r'\bFONS\b', 'FON', t, flags=re.IGNORECASE)

    # FIRST / BİRİNCİ
    t = re.sub(r'\bFIRST\b', 'BİRİNCİ', t, flags=re.IGNORECASE)
    t = re.sub(r'\bSECOND\b', 'İKİNCİ', t, flags=re.IGNORECASE)
    t = re.sub(r'\bTHIRD\b', 'ÜÇÜNCÜ', t, flags=re.IGNORECASE)
    t = re.sub(r'\bFOURTH\b', 'DÖRDÜNCÜ', t, flags=re.IGNORECASE)
    t = re.sub(r'\bFIFTH\b', 'BEŞİNCİ', t, flags=re.IGNORECASE)
    t = re.sub(r'\bSIXTH\b', 'ALTINCI', t, flags=re.IGNORECASE)
    t = re.sub(r'\bSEVENTH\b', 'YEDİNCİ', t, flags=re.IGNORECASE)
    t = re.sub(r'\bEIGHTH\b', 'SEKİZİNCİ', t, flags=re.IGNORECASE)
    t = re.sub(r'\bNINTH\b', 'DOKUZUNCU', t, flags=re.IGNORECASE)
    t = re.sub(r'\bTENTH\b', 'ONUNCU', t, flags=re.IGNORECASE)

    # COMPANY / ŞİRKETİ
    t = re.sub(r'\bA\.Ş\.\b', 'A.Ş.', t)
    t = re.sub(r'\bLLC\b', 'A.Ş.', t)

    # CLEANUP: double spaces
    t = re.sub(r'\s+', ' ', t).strip()

    return t


# === 0b. Get Turkish names from funds table ===
fund_turkish_names = {}
cur.execute("""
    SELECT tefas_code, name FROM funds
    WHERE name IS NOT NULL
    AND name != code
    AND name != 'B. KURUCUNUN ÜNVANI'
""")
for row in cur.fetchall():
    if row["tefas_code"] and row["name"]:
        fund_turkish_names[row["tefas_code"]] = row["name"]

# === 0c. Load all_funds.json for company slug mapping ===
import json as json_lib
with open(Path(__file__).parent / "data" / "all_funds.json") as f:
    all_funds_data = json_lib.load(f)

# Map tefas_code -> company identifier (from slug: {code}-{company}-{rest})
tefas_code_to_company = {}
for code, fund_data in all_funds_data.items():
    slug = fund_data["slug"]
    parts = slug.split("-")
    if len(parts) >= 2:
        tefas_code_to_company[code] = parts[1]

# Company identifier -> logo filename mapping
# (logically derived from TEFAS slug format: AKB=Ak Portföy, DNZ=Deniz, ZRY=Ziraat, etc.)
COMPANY_LOGO_MAP = {
    "ak": "ak-portfoy.svg",
    "akb": "AKB.jpg",
    "akp": "AKP.jpg",
    "akf": "AKF.jpg",
    "akg": "AKG.jpg",
    "akm": "AKM.jpg",
    "akt": "AKT.jpg",
    "ala": "ALA.jpg",
    "alp": "ALP.jpg",
    "anf": "ANF.jpg",
    "ata": "ATA.jpg",
    "atb": "ATB.jpg",
    "atl": "ATL.jpg",
    "atx": "ATX.jpg",
    "ayx": "AYX.jpg",
    "azm": "AZM.jpg",
    "bch": "BCH.jpg",
    "bdf": "BDF.jpg",
    "bgm": "BGM.jpg",
    "bkm": "BKM.jpg",
    "bmk": "BMK.jpg",
    "bnp": "BNP.jpg",
    "bpp": "BPP.jpg",
    "brk": "BRK.jpg",
    "bsk": "BSK.jpg",
    "btb": "BTB.jpg",
    "bur": "BUR.jpg",
    "cek": "CEK.jpg",
    "cgt": "CGT.jpg",
    "dbf": "DBF.jpg",
    "dbn": "DBN.jpg",
    "dnz": "DNZ.jpg",
    "dov": "DOV.jpg",
    "dpy": "DPY.jpg",
    "dti": "DTI.jpg",
    "dvy": "DVY.jpg",
    "dzy": "DZY.jpg",
    "ebg": "EBG.jpg",
    "ebp": "EBP.jpg",
    "efs": "EFS.jpg",
    "efg": "EFG.jpg",
    "ekt": "EKT.jpg",
    "eml": "EML.jpg",
    "enf": "ENF.jpg",
    "epy": "EPY.jpg",
    "fbb": "FBB.jpg",
    "fby": "FBY.jpg",
    "fin": "FIN.jpg",
    "fpy": "FPY.jpg",
    "gab": "GAB.jpg",
    "gac": "GAC.jpg",
    "gcm": "GCM.jpg",
    "gcr": "GCR.jpg",
    "ged": "GED.jpg",
    "gep": "GEP.jpg",
    "gin": "GIN.jpg",
    "glb": "GLB.jpg",
    "gly": "GLY.jpg",
    "gpy": "GPY.jpg",
    "grp": "GRP.jpg",
    "gsp": "GSP.jpg",
    "gym": "GYM.jpg",
    "hfp": "HFP.jpg",
    "hly": "HLY.jpg",
    "hpy": "HPY.jpg",
    "hyp": "HYP.jpg",
    "hzb": "HZB.jpg",
    "iaz": "IAZ.jpg",
    "icb": "ICB.jpg",
    "icp": "ICP.jpg",
    "igf": "IGF.jpg",
    "inf": "INF.jpg",
    "isp": "ISP.jpg",
    "isg": "ISG.jpg",
    "isy": "ISY.jpg",
    "ivb": "IVB.jpg",
    "ivt": "IVT.jpg",
    "iym": "IYM.jpg",
    "jbg": "JBG.jpg",
    "jcr": "JCR.jpg",
    "jmg": "JMG.jpg",
    "jpy": "JPY.jpg",
    "kag": "KAG.jpg",
    "kcp": "KCP.jpg",
    "kig": "KIG.jpg",
    "kln": "KLN.jpg",
    "kmi": "KMI.jpg",
    "kmr": "KMR.jpg",
    "kpy": "KPY.jpg",
    "ksg": "KSG.jpg",
    "ktk": "KTK.jpg",
    "ktp": "KTP.jpg",
    "lpi": "LPI.jpg",
    "lpo": "LPO.jpg",
    "mbk": "MBK.jpg",
    "mby": "MBY.jpg",
    "mdr": "MDR.jpg",
    "mef": "MEF.jpg",
    "mgb": "MGB.jpg",
    "mkg": "MKG.jpg",
    "mlp": "MLP.jpg",
    "mpa": "MPA.jpg",
    "mpg": "MPG.jpg",
    "mpy": "MPY.jpg",
    "msa": "MSA.jpg",
    "msg": "MSG.jpg",
    "msp": "MSP.jpg",
    "mtp": "MTP.jpg",
    "mup": "MUP.jpg",
    "myt": "MYT.jpg",
    "ncl": "NCL.jpg",
    "nta": "NTA.jpg",
    "odb": "ODB.jpg",
    "omd": "OMD.jpg",
    "omg": "OMG.jpg",
    "ong": "ONG.jpg",
    "ons": "ONS.jpg",
    "oyk": "OYK.jpg",
    "pap": "PAP.jpg",
    "pbg": "PBG.jpg",
    "phc": "PHC.jpg",
    "php": "PHP.jpg",
    "pgy": "PGY.jpg",
    "pnb": "PNB.jpg",
    "prg": "PRG.jpg",
    "prk": "PRK.jpg",
    "prl": "PRL.jpg",
    "qnh": "QNH.jpg",
    "qnm": "QNM.jpg",
    "qnv": "QNV.jpg",
    "rap": "RAP.jpg",
    "rbg": "RBG.jpg",
    "rky": "RKY.jpg",
    "rmg": "RMG.jpg",
    "rpy": "RPY.jpg",
    "rvg": "RVG.jpg",
    "sak": "SAK.jpg",
    "sav": "SAV.jpg",
    "sep": "SEP.jpg",
    "sgb": "SGB.jpg",
    "sky": "SKY.jpg",
    "spg": "SPG.jpg",
    "stj": "STJ.jpg",
    "svg": "SVG.jpg",
    "syg": "SYG.jpg",
    "szb": "SZB.jpg",
    "taa": "TAA.jpg",
    "tab": "TAB.jpg",
    "tac": "TAC.jpg",
    "tag": "TAG.jpg",
    "tav": "TAV.jpg",
    "tba": "TBA.jpg",
    "tcr": "TCR.jpg",
    "tcz": "TCZ.jpg",
    "teb": "TEB.jpg",
    "tey": "TEY.jpg",
    "tgb": "TGB.jpg",
    "tgk": "TGK.jpg",
    "thb": "THB.jpg",
    "ths": "THS.jpg",
    "tib": "TIB.jpg",
    "tkg": "TKG.jpg",
    "tky": "TKY.jpg",
    "tmb": "TMB.jpg",
    "tnb": "TNB.jpg",
    "tnv": "TNV.jpg",
    "tpb": "TPB.jpg",
    "tpp": "TPP.jpg",
    "trg": "TRG.jpg",
    "tst": "TST.jpg",
    "tv1": "TV1.jpg",
    "tvb": "TVB.jpg",
    "tvg": "TVG.jpg",
    "tvm": "TVM.jpg",
    "tvt": "TVT.jpg",
    "tvy": "TVY.jpg",
    "unb": "UNB.jpg",
    "uni": "UNI.jpg",
    "unl": "UNL.jpg",
    "uns": "UNS.jpg",
    "vak": "VAK.jpg",
    "vkg": "VKG.jpg",
    "vkf": "VKF.jpg",
    "vkn": "VKN.jpg",
    "vkr": "VKR.jpg",
    "vky": "VKY.jpg",
    "vpg": "VPG.jpg",
    "vvp": "VVP.jpg",
    "vym": "VYM.jpg",
    "yab": "YAB.jpg",
    "ybk": "YBK.jpg",
    "ybt": "YBT.jpg",
    "ykb": "YKB.jpg",
    "ykg": "YKG.jpg",
    "yky": "YKY.jpg",
    "ylb": "YLB.jpg",
    "ymg": "YMG.jpg",
    "ypg": "YPG.jpg",
    "ypk": "YPK.jpg",
    "ypl": "YPL.jpg",
    "ypy": "YPY.jpg",
    "ytd": "YTD.jpg",
    "ytd": "YTD.jpg",
    "zbg": "ZBG.jpg",
    "zka": "ZKA.jpg",
    "zpy": "ZPY.jpg",
    "zra": "ZRA.jpg",
    "zrb": "ZRB.jpg",
    "zrg": "ZRG.jpg",
    "zry": "ZRY.jpg",
    "is-": "is-portfoy.gif",
    "is": "is-portfoy.gif",
    "qnb": "qnb-portfoy.png",
    "qnb-": "qnb-portfoy.png",
    "ziraat": "ziraat-portfoy.png",
    "ziraat-": "ziraat-portfoy.png",
    "ak-": "ak-portfoy.svg",
    "ak": "ak-portfoy.svg",
}

# === 1. All Tefas funds ===
tefas_funds = {row["tefas_code"]: dict(row) for row in cur.execute("SELECT * FROM tefas_funds")}

# Merge Turkish names into tefas_funds
for code, fund in tefas_funds.items():
    if code in fund_turkish_names:
        fund["turkish_name"] = fund_turkish_names[code]
    else:
        # Translate English title to Turkish
        fund["turkish_name"] = translate_title(fund.get("title") or code)
print(f"Tefas funds: {len(tefas_funds)}")

# === 2. Gemini holdings ===
gemini_holdings = {}
gemini_funds_with_data = set()
cur.execute("""
    SELECT tefas_code, holdings_json FROM gemini_parsed
    WHERE success = 1 AND tefas_code IS NOT NULL
""")
for row in cur.fetchall():
    tefas_code = row["tefas_code"]
    holdings = json.loads(row["holdings_json"])
    gemini_holdings[tefas_code] = holdings
    gemini_funds_with_data.add(tefas_code)

# === 3. Price history (last 30 days only for main JSON) ===
cur.execute(f"""
    SELECT fund_id, date, price, daily_change, market_cap
    FROM price_history
    WHERE date >= date('now', '-{HISTORY_DAYS} days')
    AND daily_change BETWEEN -10 AND 10  -- filter bad data
    ORDER BY fund_id, date
""")
price_history_raw = cur.fetchall()

# Index by fund_id
price_by_fund = {}
for row in price_history_raw:
    fid = row["fund_id"]
    if fid not in price_by_fund:
        price_by_fund[fid] = []
    price_by_fund[fid].append({
        "date": row["date"],
        "price": row["price"],
        "change": row["daily_change"],
        "market_cap": row["market_cap"],
    })

# Map fund_id -> tefas_code
fund_id_to_tefas = {}
for code, fund in tefas_funds.items():
    fid = fund.get("id")
    if fid:
        fund_id_to_tefas[fid] = code

# === 4. Rankings by fund_type (by latest day's daily_change) ===
# Get latest date's data per fund
cur.execute("""
    SELECT p.fund_id, p.daily_change, p.price, t.tefas_code, t.fund_type, t.market_cap, t.title
    FROM price_history p
    JOIN tefas_funds t ON t.id = p.fund_id
    WHERE p.date = (SELECT MAX(date) FROM price_history)
    AND p.daily_change BETWEEN -10 AND 10
""")
latest_data = cur.fetchall()
latest_by_code = {r["tefas_code"]: r for r in latest_data}

# Build rankings
rankings = {}
for ftype in ["VFF", "OKS", "KFF", "SRF", "DÖVİZ", "ALTIN", "HİSSE", "BYF"]:
    funds_of_type = [
        (row["tefas_code"], row["daily_change"] or 0, row["market_cap"] or 0)
        for row in latest_data
        if row["fund_type"] == ftype
    ]
    total = len(funds_of_type)
    if total == 0:
        continue

    # Rank by daily_change (desc)
    sorted_by_change = sorted(funds_of_type, key=lambda x: -x[1])
    for rank, (code, change, mc) in enumerate(sorted_by_change, 1):
        if code not in rankings:
            rankings[code] = {}
        pct = round((total - rank) / total * 100, 1) if total > 1 else 50
        rankings[code][ftype] = {
            "rank": rank,
            "percentile": pct,
            "total": total,
            "daily_change": round(change, 4),
        }

# Also rank by market_cap
for ftype in ["VFF", "OKS", "KFF", "SRF", "DÖVİZ", "ALTIN", "HİSSE", "BYF"]:
    funds_of_type = [
        (row["tefas_code"], row["daily_change"] or 0, row["market_cap"] or 0)
        for row in latest_data
        if row["fund_type"] == ftype
    ]
    total = len(funds_of_type)
    if total == 0:
        continue
    sorted_by_mc = sorted(funds_of_type, key=lambda x: -x[2])
    for rank, (code, change, mc) in enumerate(sorted_by_mc, 1):
        if code not in rankings:
            rankings[code] = {}
        rankings[code].setdefault(ftype, {})["rank_mc"] = rank
        rankings[code].setdefault(ftype, {})["total_mc"] = total

# === 5. KAP-only funds ===
cur.execute("""
    SELECT fund_code, holdings_json, name FROM gemini_parsed g
    LEFT JOIN funds f ON f.code = g.fund_code
    WHERE g.success = 1 AND g.tefas_code IS NULL
""")
kap_only = {}
for row in cur.fetchall():
    kap_only[row["fund_code"]] = {
        "holdings": json.loads(row["holdings_json"]),
        "name": row["name"] or row["fund_code"],
    }

# === 6. Compute returns for different periods ===
def compute_returns(price_hist):
    """Compute 1W, 1M, 3M returns from price history list (oldest first)."""
    if not price_hist or len(price_hist) < 2:
        return {}
    returns = {}
    prices = [(h["date"], h["price"]) for h in price_hist if h["price"]]
    if len(prices) < 2:
        return {}
    base = prices[0][1]
    last = prices[-1][1]
    if base and base > 0:
        returns["1D"] = round((last / base - 1) * 100, 2)
    # 1 week (5 trading days)
    if len(prices) >= 6:
        returns["1W"] = round((prices[-1][1] / prices[-6][1] - 1) * 100, 2) if prices[-6][1] else None
    # 1 month (21 trading days)
    if len(prices) >= 22:
        returns["1M"] = round((prices[-1][1] / prices[-22][1] - 1) * 100, 2) if prices[-22][1] else None
    # 3 month (63 trading days)
    if len(prices) >= 64:
        returns["3M"] = round((prices[-1][1] / prices[-64][1] - 1) * 100, 2) if prices[-64][1] else None
    return returns

# === 7. Build output ===
funds_data = []
for tefas_code, tefas in tefas_funds.items():
    fid = tefas.get("id")
    fund_rankings = rankings.get(tefas_code, {})
    fund_type = tefas.get("fund_type", "VFF")
    type_rank = fund_rankings.get(fund_type, {})

    # Holdings
    holdings_raw = gemini_holdings.get(tefas_code, [])
    holdings = []
    for h in holdings_raw:
        if not isinstance(h, dict):
            continue
        ticker = h.get("ticker", "")
        is_equity = bool(ticker and ticker.endswith(".E"))
        holdings.append({
            "ticker": ticker,
            "isin": h.get("isin", ""),
            "company": h.get("issuer", "") or h.get("company", ""),
            "total_value": h.get("total_value", ""),
            "weight_pct": h.get("weight_pct", ""),
            "type": h.get("type", "stock" if is_equity else "bond"),
        })

    # Breakdown
    bd_fields = [
        "stock", "government_bond", "private_sector_bond", "eurobond",
        "gold", "repo", "reverse_repo", "treasury_bill", "bank_bills",
        "commercial_paper", "term_deposit", "etf", "derivatives",
        "foreign_equity", "foreign_bond", "precious_metals",
        "participation_account", "other"
    ]
    breakdown = {}
    for f in bd_fields:
        v = tefas.get(f)
        if v and v > 0:
            breakdown[f] = round(v, 2)

    # Price history (last 30 days for JSON)
    hist = price_by_fund.get(fid, [])
    price_history = [
        {"date": h["date"], "price": h["price"], "change": h["change"]}
        for h in hist
    ]
    returns = compute_returns(price_history)

    # Company logo
    company_slug = tefas_code_to_company.get(tefas_code, "")
    company_logo = COMPANY_LOGO_MAP.get(company_slug, "")

    funds_data.append({
        "code": tefas_code,
        "name": tefas.get("turkish_name") or tefas_code,
        "company": company_slug,
        "company_logo": company_logo,
        "fund_type": fund_type,
        "tefas_code": tefas_code,
        "report_date": tefas.get("price_date"),
        "nav": tefas.get("price"),
        "price": tefas.get("price"),
        "price_date": tefas.get("price_date"),
        "market_cap": tefas.get("market_cap"),
        "number_of_investors": tefas.get("number_of_investors"),
        "number_of_shares": tefas.get("number_of_shares"),
        "daily_change": (lambda r: r["daily_change"] if r else None)(latest_by_code.get(tefas_code)),
        "holdings": holdings,
        "holding_count": len(holdings),
        "breakdown": breakdown if breakdown else None,
        "has_gemini": tefas_code in gemini_funds_with_data,
        "price_history": price_history,
        "returns": returns,
        "rank": type_rank,
    })

# Add KAP-only
for code, data in kap_only.items():
    holdings = []
    for h in data["holdings"]:
        if not isinstance(h, dict):
            continue
        ticker = h.get("ticker", "")
        holdings.append({
            "ticker": ticker,
            "isin": h.get("isin", ""),
            "company": h.get("issuer", "") or h.get("company", ""),
            "total_value": h.get("total_value", ""),
            "weight_pct": h.get("weight_pct", ""),
            "type": h.get("type", "stock"),
        })
    funds_data.append({
        "code": code,
        "name": data["name"],
        "company": None,
        "company_logo": None,
        "fund_type": None,
        "tefas_code": None,
        "report_date": None, "nav": None, "price": None,
        "price_date": None, "market_cap": None,
        "number_of_investors": None, "number_of_shares": None,
        "daily_change": None,
        "holdings": holdings,
        "holding_count": len(holdings),
        "breakdown": None,
        "has_gemini": True,
        "price_history": [],
        "returns": {},
        "rank": {},
    })

# === 8. Stats ===
total_tefas = len(tefas_funds)
total_market_cap = sum(f.get("market_cap", 0) or 0 for f in tefas_funds.values())
latest_changes = [r["daily_change"] or 0 for r in latest_data if r["daily_change"] is not None]
avg_daily_change = sum(latest_changes) / len(latest_changes) if latest_changes else 0

top_funds = sorted(tefas_funds.values(), key=lambda x: x.get("market_cap") or 0, reverse=True)[:10]
top_funds_list = [
    {
        "code": f["tefas_code"],
        "name": f.get("turkish_name") or f.get("title"),
        "market_cap": f.get("market_cap"),
        "price": f.get("price"),
        "daily_change": (lambda r: r["daily_change"] if r else None)(latest_by_code.get(f["tefas_code"])),
    }
    for f in top_funds if f.get("market_cap")
]

# Category stats
cat_stats = {}
for ftype in ["VFF", "OKS", "KFF", "SRF", "DÖVİZ", "ALTIN", "HİSSE", "BYF"]:
    funds_of_type = [r for r in latest_data if r["fund_type"] == ftype]
    if funds_of_type:
        changes_cat = [r["daily_change"] for r in funds_of_type if r["daily_change"] is not None]
        avg_cat = sum(changes_cat) / len(changes_cat) if changes_cat else 0
        total_mc = sum(r["market_cap"] or 0 for r in funds_of_type)
        cat_stats[ftype] = {
            "count": len(funds_of_type),
            "avg_change": round(avg_cat, 3),
            "total_market_cap": total_mc,
        }

cur.execute("SELECT COUNT(*) FROM price_history WHERE daily_change BETWEEN -10 AND 10")
price_rows = cur.fetchone()[0]
cur.execute("SELECT COUNT(DISTINCT date) FROM price_history")
trading_days = cur.fetchone()[0]
cur.execute("SELECT MAX(date) FROM price_history")
latest_date = cur.fetchone()[0]

# latest_data already has daily_change from price_history
# (latest_by_code already built at top)

# Top gainer and loser (from price_history daily_change)
gainers = sorted(
    [r for r in latest_data if r["daily_change"] is not None],
    key=lambda x: x["daily_change"] or 0,
    reverse=True
)
top_gainer = None
if gainers:
    g = gainers[0]
    turkish = tefas_funds.get(g["tefas_code"], {}).get("turkish_name") or g.get("title", "")
    top_gainer = {
        "code": g["tefas_code"],
        "name": turkish,
        "change": g["daily_change"]
    }

losers = sorted(
    [r for r in latest_data if r["daily_change"] is not None],
    key=lambda x: x["daily_change"] or 0
)
top_loser = None
if losers:
    l = losers[0]
    turkish = tefas_funds.get(l["tefas_code"], {}).get("turkish_name") or l.get("title", "")
    top_loser = {
        "code": l["tefas_code"],
        "name": turkish,
        "change": l["daily_change"]
    }

# --- Historical market cap comparison ---
# Get market caps from 1 week, 1 month, 3 months ago
def get_market_cap_at_date(target_date_str):
    """Get total market cap at a specific date."""
    cur.execute("""
        SELECT COALESCE(SUM(p.market_cap), 0) as total_aum
        FROM price_history p
        JOIN tefas_funds t ON t.id = p.fund_id
        WHERE p.date = ?
    """, (target_date_str,))
    row = cur.fetchone()
    return row[0] if row else 0

# Calculate date offsets
import datetime
today = datetime.date.today()
try:
    week_ago = (today - datetime.timedelta(weeks=1)).strftime("%Y-%m-%d")
    month_ago = (today - datetime.timedelta(weeks=4)).strftime("%Y-%m-%d")
    quarter_ago = (today - datetime.timedelta(weeks=13)).strftime("%Y-%m-%d")
except:
    week_ago, month_ago, quarter_ago = None, None, None

aum_week_ago = get_market_cap_at_date(week_ago) if week_ago else 0
aum_month_ago = get_market_cap_at_date(month_ago) if month_ago else 0
aum_quarter_ago = get_market_cap_at_date(quarter_ago) if quarter_ago else 0

current_aum = sum(f.get("market_cap") or 0 for f in tefas_funds.values() if f.get("market_cap"))

aum_change_week = ((current_aum - aum_week_ago) / aum_week_ago * 100) if aum_week_ago > 0 else None
aum_change_month = ((current_aum - aum_month_ago) / aum_month_ago * 100) if aum_month_ago > 0 else None
aum_change_quarter = ((current_aum - aum_quarter_ago) / aum_quarter_ago * 100) if aum_quarter_ago > 0 else None

# --- Most invested funds (by number_of_investors) ---
cur.execute("""
    SELECT tefas_code, title, number_of_investors, market_cap
    FROM tefas_funds
    WHERE number_of_investors > 0
    ORDER BY number_of_investors DESC
    LIMIT 10
""")
most_invested = []
for row in cur.fetchall():
    code = row["tefas_code"]
    most_invested.append({
        "code": code,
        "name": tefas_funds.get(code, {}).get("turkish_name") or row["title"],
        "investors": int(row["number_of_investors"]) if row["number_of_investors"] else 0,
        "market_cap": row["market_cap"]
    })

# --- Most held stocks across all funds ---
# Only Type B stocks (.E suffix) — ticker is clean and reliable
# Type A stocks (no .E ticker) have dirty company names due to PDF parsing artifacts — skip them
SKIP_PREFIXES = ('XS', 'IE00', 'US', 'TRY', 'TRT', 'CH', 'LU', 'NL', 'JE', 'IL', 'FR', 'DE',
                 'AT', 'CA', 'AU', 'IE', 'GB', 'KY')

cur.execute("""
    SELECT 
        h.ticker,
        COALESCE(NULLIF(TRIM(h.company), ''), REPLACE(h.ticker, '.E', '')) as company,
        SUM(h.weight_pct) as total_weight, 
        COUNT(DISTINCT r.fund_id) as fund_count
    FROM holdings h
    JOIN reports r ON r.id = h.report_id
    WHERE h.ticker IS NOT NULL AND h.ticker != '' AND h.ticker LIKE '%_.E'
      AND h.ticker NOT LIKE 'TRY%'
    GROUP BY h.ticker
    HAVING total_weight > 10
    ORDER BY total_weight DESC
    LIMIT 20
""")
most_held_stocks = []
for row in cur.fetchall():
    ticker, company, tw, fc = row["ticker"], row["company"] or "", row["total_weight"], row["fund_count"]
    # Skip USD/EUR/CHF ETFs that somehow have .E tickers
    if any(ticker.upper().startswith(p) for p in SKIP_PREFIXES):
        continue
    # Clean company name — truncate if too long
    company_out = company.strip() if company else ticker.replace('.E', '')
    if len(company_out) > 45:
        company_out = company_out[:42] + "..."
    most_held_stocks.append({
        "ticker": ticker,
        "company": company_out,
        "total_weight": round(tw, 2),
        "fund_count": fc
    })

# --- Top 5 gainers and losers ---
top5_gainers = [
    {
        "code": g["tefas_code"],
        "name": tefas_funds.get(g["tefas_code"], {}).get("turkish_name") or g.get("title", ""),
        "change": g["daily_change"],
        "market_cap": tefas_funds.get(g["tefas_code"], {}).get("market_cap")
    }
    for g in gainers[:5]
]
top5_losers = [
    {
        "code": l["tefas_code"],
        "name": tefas_funds.get(l["tefas_code"], {}).get("turkish_name") or l.get("title", ""),
        "change": l["daily_change"],
        "market_cap": tefas_funds.get(l["tefas_code"], {}).get("market_cap")
    }
    for l in losers[:5]
]

# --- Category change (previous day comparison via price_history) ---
# Get yesterday's data
cur.execute("SELECT DISTINCT date FROM price_history ORDER BY date DESC LIMIT 2")
dates = [r[0] for r in cur.fetchall()]
yesterday_date = dates[1] if len(dates) > 1 else None

category_yesterday = {}
if yesterday_date:
    cur.execute("""
        SELECT t.fund_type, SUM(p.market_cap) as total_aum
        FROM price_history p
        JOIN tefas_funds t ON t.id = p.fund_id
        WHERE p.date = ?
        GROUP BY t.fund_type
    """, (yesterday_date,))
    for row in cur.fetchall():
        if row["fund_type"]:
            category_yesterday[row["fund_type"]] = row["total_aum"]

# Build category_change
category_change = {}
for cat, aum in cat_stats.items():
    prev = category_yesterday.get(cat, 0)
    curr = aum["total_market_cap"]
    if prev > 0:
        category_change[cat] = {
            "change_pct": round((curr - prev) / prev * 100, 3),
            "prev_aum": prev,
            "curr_aum": curr,
            "count": aum["count"]
        }

stats = {
    "total": len(funds_data),
    "tefas_total": total_tefas,
    "gemini_funds": len(gemini_holdings),
    "gemini_holdings": sum(len(v) for v in gemini_holdings.values()),
    "kap_only": len(kap_only),
    "total_market_cap": total_market_cap,
    "avg_daily_change": avg_daily_change,
    "price_history_rows": price_rows,
    "trading_days": trading_days,
    "latest_date": latest_date,
    "top_funds": top_funds_list,
    "top_gainer": top_gainer,
    "top_loser": top_loser,
    "category_stats": cat_stats,
    # Historical AUM changes
    "aum_change_week": aum_change_week,
    "aum_change_month": aum_change_month,
    "aum_change_quarter": aum_change_quarter,
    # Most invested funds
    "most_invested": most_invested,
    # Most held stocks across all funds
    "most_held_stocks": most_held_stocks,
    # Top 5 gainers/losers
    "top5_gainers": top5_gainers,
    "top5_losers": top5_losers,
    # Category day-over-day changes
    "category_change": category_change,
}

output = {"stats": stats, "funds": funds_data}

# Load and include benchmark data
BENCH_FILE = Path(__file__).parent / "data" / "benchmarks.json"
if BENCH_FILE.exists():
    with open(BENCH_FILE, "r") as f:
        benchmarks = json.load(f)
    output["benchmarks"] = benchmarks
    print(f"   Benchmarks:    {sum(len(v) for v in benchmarks.values())} records")

OUT.parent.mkdir(parents=True, exist_ok=True)
with open(OUT, "w", encoding="utf-8") as f:
    json.dump(output, f, ensure_ascii=False, indent=2, default=str)

conn.close()

print(f"\n✅ Exported: {len(funds_data)} funds → {OUT}")
print(f"   Price history:  {price_rows:,} rows total, {trading_days} trading days")
print(f"   Latest date:   {latest_date}")
print(f"   Market cap:   {total_market_cap/1e9:.1f}B TL")
print(f"   File size:    {OUT.stat().st_size // 1024}KB")
print(f"\nCategory breakdown:")
for ftype, cs in sorted(cat_stats.items(), key=lambda x: -x[1]["count"]):
    print(f"  {ftype}: {cs['count']} funds, avg: {cs['avg_change']:+.3f}%")
