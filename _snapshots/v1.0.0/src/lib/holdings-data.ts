// Holdings data-fetching — reads from Supabase
// Used by /holdings page and /holdings/[isin] detail page
import { supabase } from "@/lib/supabase";

export interface AggregatedHolding {
  isin: string;
  company: string;
  ticker: string;
  fund_count: number;
  updated_at: string | null;
}

export interface HoldingFund {
  fund_code: string;
  fund_name: string | null;
  fund_type: string | null;
  weight_pct: number | null;
  daily_change: number | null;
}

export interface HoldingDetail {
  isin: string;
  ticker: string;
  company: string | null;
  funds: HoldingFund[];
}

// ISIN → display name
// company column in fund_holdings is UNRELIABLE — contains garbled values like
//   "A.Ş.", "ANONİM TÜRK SİGORTA ŞİRKETİ", "SAVUNMA SANAYİ A.Ş."
// For TRA/TRE stock ISINs, extract ticker directly from ISIN (chars 3-7 or 3-8).
// For TRT government bonds, show ISIN suffix (chars -8).
// Only use company column for clean, short values that look like tickers.

export function displayName(isin: string, company?: string | null): string {
  // Known tickers set — used for both ISIN and company lookups
  const KNOWN_TICKERS = new Set([
    // Stocks — exact tickers
    "ADEL","ADGYO","AKBNK","AKSGY","ALARK","ALGYO","ALKA","ALKIM","ALYAG","ARDYZ",
    "AREN","ASELS","AEFES","AGROT","AGESA","AHGAZ","AKASA","AKSUE","ALARKO",
    "ANHYT","ANSGR","ARDES","ARENA","ARSAN","ASUZU","AYDEM","AYGAZ","BAGFS",
    "BASGZ","BASRM","BAYRK","BBSRK","BCCLO","BCHOL","BICO","BIMAS","BKLTO",
    "BMLHX","BNTAS","BORLA","BOSSA","BRISA","BRKOM","BRMEN","BRVIT","BSENE",
    "BSLKR","BTCIM","BUCIM","BURCE","BURVA","BUYKS","BVSAN","CCOLA","CIMSA",
    "CLEBI","CWENE","DAGHL","DANGM","DBRSK","DENGE","DENIZ","DGATE","DGGYO",
    "DMAGK","DOBCE","DOHOL","DYHGY","DZGYO","ECILC","ECZYT","EDATA","EENFA",
    "EERLI","EFORU","EGCYO","EGSER","EMKEL","ENJSA","ENKAI","ENTRA","ERBOS",
    "EREGL","ERSU","ESCAR","ESCOM","ESEN","EUPWR","EUREN","FADE","FENER",
    "FLAP","FONET","FOREN","FRIGO","FROTO","GARAN","GENIL","GIPTA","GLCVY",
    "GOLTS","GOODY","GOZFD","GRTHM","GSRAY","GUBRF","GWIND","HDFGS","HEKTS",
    "HTTIH","HURGZ","ICAEN","ICG","IDGYO","IHEVB","IHGZY","IHLTM","INDES",
    "INTEM","ISBIR","ISBTR","ISCTR","ISDMR","ISFIN","ISGYO","ISMEN","ISSEN",
    "IZEN","JANTS","KAPLM","KARSN","KARTN","KATMR","KAYSE","KCAER","KCHOL",
    "KLVTE","KONTR","KONYA","KRDMA","KRDMB","KRDMD","KRONT","KRVGD","KSTCR",
    "KTOKT","KUTPO","LIDFA","LIGNA","LMKDC","LOGO","MAKTI","MALT","MAVI",
    "MZHLD","NTHOL","NUHCM","OBAMS","OFA","ONGZM","ORMA","OSMEN","OTKAR",
    "OYAK","OYAKC","OZBAL","OZRDN","PAGYO","PAMEL","PANA","PAPIL","PARSN",
    "PATEK","PCILT","PENGD","PETKM","PGSUS","PNRGI","QNBFB","QUAGR","RALYH",
    "REEDR","RUBNS","SAFKR","SAHOL","SAMAT","SANEL","SANKO","SARKY","SASAB",
    "SASA","SATEK","SAYAS","SEKFK","SEKUR","SELEC","SELGD","SELVA","SGSOC",
    "SIBOR","SILTR","SMRTG","SNGYO","SNKAK","SNPAM","SODSN","SOKE","SPCFS",
    "STDGY","STERV","SUPHI","TARAK","TATBS","TBOR","TCDDAS","TDGYO",
    "TEBCO","TEKN","TEZOL","THYAO","TKFEN","TKN","TKOLE","TLMAN","TMPAN",
    "TOASO","TRNAV","TSKB","TSPOR","TTKOM","TUBNG","TURGG","TURKM","TUPRS",
    "UCGZM","UFUK","ULAS","ULPKN","UMET","UNYEC","USAK","UTEK","VAKFN",
    "VAKKO","VAKVN","VANGD","VERUS","VESBE","VESTL","VKFRL","YAPRK","YATAS",
    "YBTAB","Yigido","YKBNK","YKGYO","YUNOG","YYLGD","ZELLV","ZEREN","ZLDN",
    // Govt bonds
    "HAZINE","HAZİNE","HAZİ",
    // Other known
    "ODAS","TCELL","MPARK","KLNSE","SIBOR","SANFM","BMELC","KAREL","BIZIM","PARA",
  ]);

  // 1. Government bond: TRT/TRD prefix → show last 8 chars of ISIN
  if (isin.startsWith("TRT") || isin.startsWith("TRD")) {
    return isin.slice(-8);
  }
  // 2. Stock ISIN: extract ticker from ISIN
  //    Two ISIN formats in BIST:
  //    (a) "000-series": TRA/TRE + 4-char ticker + "000" + check (e.g. TREBIMM00018 → BIMAS)
  //    (b) "A/B-series": TRA/TRE + 5-char ticker + date(3) + check (e.g. TRAKCHOL91Q8 → KCHOL)
  if ((isin.startsWith("TRA") || isin.startsWith("TRE")) && isin.length >= 9) {
    if (isin.slice(8, 11) === "000") {
      // 000-series: 4-char ticker
      const ticker4 = isin.slice(3, 7);
      if (KNOWN_TICKERS.has(ticker4)) return ticker4;
    }
    // A/B-series: 5-char ticker
    const ticker5 = isin.slice(3, 8);
    if (/^[A-ZÇĞİÖŞÜ]{5}$/.test(ticker5)) return ticker5;
    // Fallback for cases like OTOSN (4-char ticker in 5-char slot)
    if (KNOWN_TICKERS.has(isin.slice(3, 7))) return isin.slice(3, 7);
  }
  // 3. Company column: only trust if it's a short, clean ticker-like value
  if (company) {
    const trimmed = company.trim();
    if (/^[A-ZÇĞİÖŞÜ]{4,6}$/.test(trimmed)) {
      return trimmed;
    }
    const first = trimmed.split(" ")[0];
    if (KNOWN_TICKERS.has(first)) return first;
  }
  // 4. Absolute fallback
  return isin;
}

export async function fetchTopHoldings(limit = 200): Promise<AggregatedHolding[]> {
  const { data, error } = await supabase
    .from("fund_holdings")
    .select("isin, company, ticker, fund_code, updated_at")
    .not("isin", "ilike", "TEST%")
    .not("fund_code", "ilike", "TEST%")
    .order("fund_code");

  if (error) throw error;
  if (!data) return [];

  // Aggregate by ISIN: count distinct funds, pick first company (ticker)
  const isinMap = new Map<
    string,
    {
      company: string;
      ticker: string;
      fund_codes: Set<string>;
      updated_at: string | null;
    }
  >();

  for (const row of data) {
    const isin = row.isin;
    if (!isin) continue;

    if (!isinMap.has(isin)) {
      isinMap.set(isin, {
        company: row.company || "",
        ticker: row.ticker || "",
        fund_codes: new Set(),
        updated_at: row.updated_at || null,
      });
    }
    isinMap.get(isin)!.fund_codes.add(row.fund_code);
  }

  const result: AggregatedHolding[] = Array.from(isinMap.entries())
    .map(([isin, v]) => ({
      isin,
      company: v.company,
      ticker: v.ticker,
      fund_count: v.fund_codes.size,
      updated_at: v.updated_at,
    }))
    .sort((a, b) => b.fund_count - a.fund_count)
    .slice(0, limit);

  return result;
}

export async function fetchHoldingDetail(
  isin: string
): Promise<HoldingDetail | null> {
  // Get ticker and company from first holding
  const { data: holdings, error } = await supabase
    .from("fund_holdings")
    .select("ticker, company")
    .eq("isin", isin)
    .limit(1);

  if (error) throw error;
  if (!holdings || holdings.length === 0) return null;

  const ticker = holdings[0]?.ticker || "";
  const company = holdings[0]?.company || null;

  // Get all funds holding this ISIN
  const { data: fundHoldings, error: fhError } = await supabase
    .from("fund_holdings")
    .select("fund_code")
    .eq("isin", isin)
    .not("fund_code", "ilike", "TEST%")
    .order("fund_code");

  if (fhError) throw fhError;

  // Dedupe by fund_code
  const fundMap = new Map<string, HoldingFund>();
  for (const fh of fundHoldings || []) {
    if (!fundMap.has(fh.fund_code)) {
      fundMap.set(fh.fund_code, {
        fund_code: fh.fund_code,
        fund_name: null,
        fund_type: null,
        weight_pct: null,
        daily_change: null,
      });
    }
  }

  // Enrich with fund names, types, daily_change from funds table
  const fundCodes = Array.from(fundMap.keys());
  if (fundCodes.length > 0) {
    const { data: fundData } = await supabase
      .from("funds")
      .select("code, name, fund_type, daily_change")
      .in("code", fundCodes);

    for (const f of fundData || []) {
      if (fundMap.has(f.code)) {
        const entry = fundMap.get(f.code)!;
        entry.fund_name = f.name;
        entry.fund_type = f.fund_type;
        entry.daily_change = f.daily_change;
      }
    }
  }

  return {
    isin,
    ticker,
    company,
    funds: Array.from(fundMap.values()),
  };
}
