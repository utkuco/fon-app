// Paylaşılan ETF mega-kategorileri — hem server component hem client component kullanır
// Key → Set of ticker symbols

export interface EtfCategory {
  key: string;
  label: string;
  color: string;
  bgHover: string;
  symbols: Set<string>;
}

export const ETF_CATEGORIES: EtfCategory[] = [
  {
    key: "sp500",
    label: "S&P 500",
    color: "bg-blue-50 text-blue-700",
    bgHover: "hover:bg-blue-50",
    symbols: new Set(["SPY","VOO","IVV","SPXL","SPXU","SDS","SH","SPDN","SPLG","IVIG","SPGM","SPYQ","VOOQ","VV","IEUR","IVV3","SPAB","VOT","IVLC","SPHD","SPYG","RSP","IWV","ITOT","IJJ","JKJ","IVW","IVOG","SPXT","VLU","FIW","SPTS","SPMB"]),
  },
  {
    key: "nasdaq",
    label: "Nasdaq / Teknoloji",
    color: "bg-violet-50 text-violet-700",
    bgHover: "hover:bg-violet-50",
    symbols: new Set(["QQQ","QQQM","QLD","TQQQ","SQQQ","SOXQ","SOXL","SOXS","ARKK","ARKQ","ARKW","ARKF","ARKX","FNGU","FNGD","FINU","FIDU","CLOU","CGBR","XNTK","SKYY","WOTE","IYZ","XTL","FTEC","VGT","IYQ","XLK","IYW","IGV","SOXX","XSD","PSI","SMH","TSLL","TSLS","KORU"]),
  },
  {
    key: "tahvil",
    label: "Tahvil & Bono",
    color: "bg-green-50 text-green-700",
    bgHover: "hover:bg-green-50",
    symbols: new Set(["BND","AGG","AGGQ","AGGY","AGGZ","TLT","TBT","TBF","VGLT","VGIT","VCSH","VCIT","BSV","SCHZ","SCHO","SPIB","FALN","FLOT","FLRN","FLDB","FUL","USIG","USHY","HYG","HYLD","JNK","SJNK","LQD","SRLN","IGIB","IGLB","PFF","FPE","EMB","EMLC","LEMB","WIP","BWX","IGOV","SIVP","FLTR","VFLO"]),
  },
  {
    key: "altin",
    label: "Altın & Emtia",
    color: "bg-amber-50 text-amber-700",
    bgHover: "hover:bg-amber-50",
    symbols: new Set(["GLD","IAU","SLV","SIVR","GLDM","SGOL","UGL","DGL","PDBC","DJP","DBA","JJG","RJI","USCI","LIT","PICK","URA","XME","REMX","LGLV","VEGI","BCIM","BCI","FTGC","GLTR"]),
  },
  {
    key: "dunya",
    label: "Dünya",
    color: "bg-teal-50 text-teal-700",
    bgHover: "hover:bg-teal-50",
    symbols: new Set(["VTI","VXUS","EFA","VWO","EEM","VEA","IEFA","VSS","IEMG","SPDW","DGT","EIDO","EIS","EEMA","EMXC","EURL","FM","FRG","FTC","FUNC","FYL","GEM","HFXI","HYEM","IADI","IAK","IASI","IBDA","ICOL","IDCE","IDEM","IFAS","IFNG","ILF","INDY","IOFF","IPA","IPFF","IQDF","IQDY","IQIN","ISCF","ISZE","IUIT","IUS","IUSV","IYZ","JPEO","JPI","JPS","JPZ","KEM","KIE","KLD","KRO","LATM","LEAD","LOUP","LRGF","MATH","MATQ","MCRO","MDIV","MEAR","MFDX","MFEM","MFT","MID","MINT","MJ","MLPA","MLPN","MOAT","MORT","MRUD","MSOS","NDG","NFRA","NTZ","OLO","PAF","PALS","PAMC","PASC","PBDM","PBEU","PBSM","PCEF","PCN","PDEC","PDEV","PEY","PFF","PHB","PIN","PIZ","PLAT","PLC","PLK","PML","PMSF","PNF","PPH","PR","PRBL","PRF","PRGF","PTF","PUI","PWC","QAI","QAT","QMOM","QQQ","QUS","RA","RALS","RCD","RFV","RIGS","RLY","RPHS","RSPF","RSX","RUSL","RUSS","SAA","SAEF","SAFM","SAPE","SARR","SCJ","SCZ","SFY","SHM","SIL","SIZ","SLY","SMMD","SNPE","SOCL","SPAX","SPHD","SPHQ","SPLV","SPMO","SPMV","SPSB","SPT","SPTM","SPTS","SPUD","SPWM","SPXB","SPY","SPYC","SPYG","SPYV","SRS","SRTY","SSO","STK","STPZ","SUSB","SUSP","SUSA","SUST","SVOL","SVR","SWIN","SYE","SYG","T","TALF","TALS","TAXI","TBT","TECB","TFI","TFIV","TIP","TIPZ","TMFC","TN","TQI","TRET","TRTY","TSL","TTAI","TUSA","TUSS","TUZ","UCI","UCR","UD","UDI","UFO","UYG","VA","VAL","VB","VBK","VBR","VBW","VCIT","VCLS","VCR","VCSH","VDC","VDE","VEA","VEGI","VEM","VEML","VEO","VEU","VFH","VFIAX","VFSC","VGIT","VGLT","VGR","VGT","VHT","VIDI","VIG","VIGI","VIOG","VIOO","VIOS","VIOV","VIS","VIXY","VLU","VMOT","VN","VNQ","VNQI","VO","VOE","VONG","VONV","VOT","VOX","VPG","VPL","VRA","VRSK","VRSN","VRT","VRTX","VSGX","VT","VTH","VTI","VTIP","VTR","VTW","VUG","VUSE","VV","VWO","VXF","VXUS","VYM","WIP","WM","WOOD","WTA","X","XAR","XBI","XES","XHB","XHS","XIT","XLB","XLE","XLF","XLG","XLI","XLK","XLP","XLRE","XLRN","XLS","XLSR","XME","XMHQ","XML","XMM","XMQQ","XNQ","XNTK","XOG","XONE","XOP","XOUT","XPH","XPP","XRL","XRT","XRX","XSD","XSL","XSO","XSW","XT","XTH","XTL","XTM","XTR","XWEB","XZL","YIELD","Z","ZB","ZPAY","ZRET","ZSL","ZTR","ZUK","ZVV"]),
  },
  {
    key: "diger",
    label: "Diğer ETF",
    color: "bg-neutral-50 text-neutral-700",
    bgHover: "hover:bg-neutral-50",
    symbols: new Set(), // fallback — tümü dışındakiler
  },
];

// Server-side: verilen kategoriyi bazında ETF'leri filtrele
export function filterEtfsByCategory<T extends { symbol: string }>(
  etfs: T[],
  categoryKey: string | undefined
): T[] {
  if (!categoryKey) return etfs; // tümü

  const cat = ETF_CATEGORIES.find((c) => c.key === categoryKey);
  if (!cat) return etfs;

  // "diger" → tanımlı kategorilerin dışındaki tüm ETF'ler
  if (cat.key === "diger") {
    const definedSymbols = new Set(
      ETF_CATEGORIES.filter((c) => c.key !== "diger").flatMap((c) => Array.from(c.symbols))
    );
    return etfs.filter((e) => !definedSymbols.has(e.symbol));
  }

  return etfs.filter((e) => cat.symbols.has(e.symbol));
}

export function getCategoryByKey(key: string) {
  return ETF_CATEGORIES.find((c) => c.key === key);
}
