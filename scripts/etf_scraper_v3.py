#!/usr/bin/env python3
"""
Fast ETF scraper using Yahoo Finance.
- Loads ~1200 ETF symbols from Yahoo Finance Most Active page
- Batch downloads price data and info in groups
- Upserts to Supabase every 100 rows
"""
import yfinance as yf
import urllib.request
import json
import time
import sys

SUPABASE_URL = "https://oqkobptbvcazifpvjwfz.supabase.co"
SUPABASE_KEY = "sb_publishable__GPrsdfKRZCMZE8to916iQ_Izv9naG-"

# ETF symbols scraped from Yahoo Finance Most Active (1198 unique)
ETF_SYMBOLS = [
    "BMNU","TZA","BITO","TSLL","SOXS","BMNG","TQQQ","NVD","TSLG","SPDN",
    "SOXL","SQQQ","MSTU","PLTD","DRIP","SPY","UVIX","IBIT","SCO","XLE",
    "QQQ","ETHA","MSTZ","QID","XLF","SMCL","CRCG","IWM","LQD","IONZ",
    "HYG","SLV","MSOS","SGOV","EEM","TSDD","CRWG","EWZ","CONL","SCHD",
    "KWEB","RWM","IGV","AMDD","TLT","USO","BTCZ","FXI","XLU","SPXS",
    "SCHX","EFA","SH","AMZD","EWY","BITX","USHY","PSQ","TSLQ","SPYM",
    "AMDL","GDX","OKLL","SCHG","UVXY","XLP","SCHF","VCIT","VEA","ASTX",
    "FNGU","IEMG","SPIB","XLB","KRE","GLD","GGLS","SPXU","IEFA","NVDX",
    "XLK","BKLN","LABD","BIL","BND","VXX","SCHB","JPST","MSOX","QQQI",
    "UNG","QYLD","INDA","ARKK","VWO","GOVT","MSFU","ETHU","MSTP","VTEB",
    "DRAM","TNA","PDBC","VOO","XLV","TSLZ","IJH","ICLN","VXUS","BOIL",
    "XBI","XLI","RSP","XLY","AAPD","AGG","NVDL","SPYG","EWJ","SNXX",
    "IVV","CORD","EWT","IAU","NBIZ","JEPQ","NOWL","BITU","EMB","IRE",
    "UCO","SSO","QLD","NVDQ","DAPP","USFR","ADBG","JAAA","BAI","ASHR",
    "SPTL","SPHY","VTI","SDOW","JEPI","FIGG","IONX","SDS","SMH","BNDX",
    "FNDX","URA","ETH","VCSH","SPLB","SRLN","SCHV","VIXY","EWH","XLRE",
    "IYR","SCHA","BNO","ZSL","DIA","SJNK","FBTC","PTIR","IEF","SOXX",
    "RKLX","MSTX","CGDV","XLC","IJR","JETS","GLDM","XOVR","JCPB","VT",
    "CRCD","ILF","SPYI","TSLT","SCHH","UPRO","VCLT","MAGS","SPDW","VGK",
    "RKLZ","ETHT","GSY","QQQM","IREZ","DOG","TSLR","XOP","XRT","MINT",
    "ACWI","ETHE","SCHP","TECS","XXRP","VGSH","UDOW","SHV","QBTX","SILJ",
    "IUSB","SMCX","MUB","ORCX","AAPU","SVIX","GDXJ","HIMZ","VTV","SCHO",
    "BIZD","JNK","GRNY","IYZ","SPYU","VNQ","GBTC","TETH","IONL","ITB",
    "LITX","PFF","CGGR","REET","SPSM","KOLD","PLTU","SPYD","METU","IGIB",
    "IVW","ONDL","TBIL","SCHR","FBND","ACWX","NFXL","SPXL","AIQ","BOXX",
    "AMZU","NVDY","PULS","PYLD","FETH","SCHI","GLL","ASTN","URTH","FTGC",
    "DYNF","SPEM","EMXC","ERY","IWX","MUU","DFAC","DXD","SCHE","SPAB",
    "SPSB","VTWO","EWA","XME","EWU","COPX","SHY","ITOT","APLX","IWD",
    "JPIE","TFLO","SPYV","VGIT","SPTS","AGQ","NAIL","VEU","VTIP","CRMG",
    "IWR","PGX","SPTI","SMU","ICSH","VONV","BTC","SGOL","AVEM","SPMO",
    "KBE","IAUM","SDVY","GUNR","BSV","SIL","DRR","FENY","CCUP","IGSB",
    "MSTY","NASA","SIVR","VRIG","LCDL","ROBN","YMAX","MVLL","MSFD","FLOT",
    "SHLD","BMNZ","TMF","USMV","DGRO","IXUS","TIP","ARKG","MRAL","RYLD",
    "ARMG","UGL","HYRM","BITB","CTA","IXC","SPLV","SRTY","CGBL","BIV",
    "DBMF","ONDG","GDXD","BEZ","CIBR","EWG","AAAU","HOOG","SPMD","SOLT",
    "XLG","BINC","ICVT","QBTZ","BULZ","VONG","MCHI","SPMB","FEZ","DAMD",
    "TAN","CGGO","VBIL","TSL","EFV","HGER","SVXY","EWW","IWF","AAOX",
    "UNHG","UUP","SCHZ","ARKB","FENI","BBJP","BEX","EMLC","YINN","IBB",
    "BITI","DBC","VIG","DFIV","XHB","PZA","FNDF","GUSH","DFSV","WCMI",
    "URTY","VYM","CWVX","SCMB","SPHQ","FNDE","FPE","MUD","BUFR","TLTW",
    "DFAI","EZU","BUG","AMLP","AVLV","SBIT","MSFL","ETHW","VUG","VMBS",
    "VNM","CGUS","USGG","FALN","TECL","DBA","IHI","IGLB","VGLT","BKDV",
    "PBW","CGCB","PFFA","USIG","SCZ","PXE","NBIL","EDV","ORCU","DFAR",
    "VUSB","CWB","BSOL","GPIQ","BTCI","IDEV","IWB","EWC","SCYB","FLTR",
    "AVUV","SHYG","DFCF","MBB","IGE","EUFN","HYLB","RGTX","IEI","RDVY",
    "COWZ","CGMM","EPI","DFLV","MORT","FTSM","CGCP","KBWB","XYLD","DIVO",
    "CRCA","DFAX","EVTR","GSOL","VYMI","CGMU","JMST","PAVE","NEAR","DBEF",
    "IQLT","IREX","SYSB","NBIG","IBDR","PVAL","CRMX","SCHM","GBIL","JMTG",
    "CGIE","SOXQ","CORO","GSG","REMX","DFIC","CGMS","FLKR","GDXY","TTDU",
    "HYMB","HODL","IVLU","THRO","DUHP","PLTZ","TAFI","KIE","QUAL","BULG",
    "IVES","DTCR","DFAE","PAAA","AVDE","YANG","DFUS","VRP","IWN","GVAL",
    "DFEM","FCG","VDE","ANGL","RECS","IYW","WTID","SPTM","CRWU","FXN",
    "AIA","IGM","FMDE","ETHD","LVHI","FBL","LIT","SCHK","IAGG","IYE",
    "OMAH","TFI","EWS","TUR","FDVV","EMBX","BABX","IUSG","TSLS","IBHF",
    "PYPG","IUSV","MSBT","USOY","FNDA","ARKX","USD","FLMI","SMBS","BUXX",
    "IBTH","BSCU","CALF","ENOR","FAS","RFIX","VGT","BCI","FLRN","AVS",
    "TSMX","MOAT","UFO","IDV","RLY","SOFX","CQQQ","TLH","EFG","UBND",
    "JMUB","CGXU","KTEC","VFLO","FELC","APLZ","URNM","XEMD","GDXU","RDVI",
    "RETL","CORN","CGGE","GPIX","LUNL","TWM","OUNZ","IBDT","MLPI","JMBS",
    "JQUA","IEUR","CSHI","NEBX","QDTE","BOTZ","NUGT","FDL","AVDV","FTCS",
    "GGLL","STIP","ARTY","IWP","SPBO","TSYY","BTAL","JBND","BKGI","MDY",
    "AMAX","APPX","VWOB","HDV","BILS","ECH","IVE","FTCB","XSW","FUTY",
    "FTHI","IDMO","WEAT","SCHY","ALLW","HEFA","ESGE","NVOX","RWL","IDVO",
    "USAX","TCAF","ULTI","BSCR","IUS","IEZ","SPHB","EIDO","UDN","BLV",
    "SCHC","RPG","CGDG","DUST","AIPO","SPHD","ACYN","CPER","DBO","NYM",
    "FAZ","CHPY","PPLT","OEF","DBB","CRDU","RAAX","CGNG","ETHB","NTSD",
    "DIHP","COHX","UXRP","KORU","VB","AIRR","BSCS","IGF","SKYY","CHAT",
    "EWI","VLUE","RONB","PICK","AOR","NOBL","PRF","XRP","IWY","DGRW",
    "BSCT","SMST","AKRE","KSA","DFAU","COMT","RDWU","FBCG","INTW","PFXF",
    "WCLD","EPOL","ARGT","EUAD","DFSD","LABU","USDU","BAIG","SPUS","AVGX",
    "MTUM","MSTW","SMCY","GSLC","SDIV","REM","VPL","IBDV","FELG","IWMI",
    "VO","UUUG","YMAG","TOPT","NVDU","HYD","IDEF","PSIL","BSCV","PJP",
    "CMF","FXU","NFLU","ITA","CAIE","SNDU","GOVZ","IBDS","BSVO","METD",
    "DFAS","FLJP","IBDU","DJTU","LMBS","RPV","FAPR","IBDW","SGVT","TSLY",
    "FIXD","ERX","AGIX","QTUM","RWR","GOVI","VXF","SCHQ","BLOK","FVD",
    "WGMI","GSIE","JAVA","FESM","JGRO","FPAG","BSCQ","NORW","ZROZ","WEBL",
    "CIFU","JPLD","ESGD","SUB","SHNY","KMLM","CGSD","FDD","DISV","JDST",
    "VOLT","FNGD","FDN","RCAX","UWM","FLXR","PFFD","IWO","SLYV","MMIT",
    "VV","TOTL","SARK","IMTM","DXJ","TIPX","HECA","OKLS","VNLA","JIVE",
    "FLBL","DFIS","CWEB","EWL","GCOW","DFGR","HIPS","FLCB","FTSL","FEOE",
    "OIH","MARO","UCON","CLOA","QDVO","GRID","NLR","BOND","IWLG","BUFD",
    "DFUV","BLCR","CRWL","FTEC","DUOG","HELO","IBTI","VFH","SETM","RING",
    "CONY","NVTX","TMV","MULL","QUBX","CGCV","COWG","SPSK","VIXM","SLVP",
    "IYT","IREG","BALI","LABX","UAE","CWI","DPST","ONEQ","VCRM","JDVI",
    "GARP","SMMD","MGK","SJB","USOI","FTQI","MISL","FREL","PFIX","SLON",
    "BDYN","ESGU","CGHM","VCRB","CRMU","IFV","BUYW","VTEC","USRT","CANE",
    "TEMT","FIDI","HODU","HOOZ","GDE","MUNI","QLTY","VIGI","DBE","ISTB",
    "FSSL","FTNY","OILU","AVL","IWS","ROKT","PREF","TBT","BLOX","ESGV",
    "IGLD","DVY","TSME","BRIE","MLPX","HIMU","QCML","EFZ","FTMH","AMZY",
    "XMMO","IWC","CONI","WDCX","BMOP","VOOG","NYF","JULU","EEMS","PHO",
    "AFK","CATH","OUSM","KORP","BSSX","NUMV","AFLG","IBTO","AMDW","CAOS",
    "IBHG","XBTY","ANEL","LALT","ETHV","MDYV","LRGG","DFSI","EQTY","SPEU",
    "REZ","USVM","FLCA","AMZA","TFLR","LDUR","FBT","IBHH","DUSA","BLTD",
    "PTNQ","QYLG","TDI","OPEG","FTMN","AOHY","BZQ","FQAL","RSHO","BBAG",
    "CEPI","ROUS","ITDD","HIYY","IVEP","PONX","FDEM","SFTY","EFIV","XNTK",
    "SNAG","HEDJ","NUSC","FDLO","LVHD","POW","RDYY","THTA","PBP","VTHR",
    "KXI","VAW","SHYD","KNOV","BLST","BUFH","DBND","FDHY","MSFO","JSMD",
    "SEIM","QCMU","SEIS","JHMD","EPU","VFMO","AQLT","DFSB","SUSA","RAA",
    "HEFT","GREK","FTXO","FEMR","SPGP","PSCE","PJAN","SCUS","QQEW","LDRI",
    "ASMU","PWV","PIE","SNOY","IMCV","GXPC","ITWO","LVLN","TMAT","ROBT",
    "DCRE","QGRD","SMHB","DSCO","IYG","INDS","QUSA","ORCS","GEVG","XSD",
    "VGMS","ESN","KURE","GLGG","LOGO","IAK","CLSZ","CSEX","IGRO","UTWO",
    "PICB","GOLY","DIVP","SAMT","HCMT","PZT","HYGH","CGW","EUSA","HOYY",
    "CRCO","ROCY","BFEB","VTWG","SQS","RDFI","BNDS","XPH","BSJU","ICOI",
    "HCRB","NUGY","EMQQ","IBCB","IDHQ","PLTA","RJDI","KMLI","YCL","APIE",
    "LEUX","DEED","EURL","KQQQ","BRTR","GENT","BOEU","URE","EZM","EWO",
    "APLY","WEEK","KAPR","AVRE","GNMA","EMTL","FCUS","UBT","GUMI","IDX",
    "ATCL","CAAA","FTPA","WEEI","TYD","EVMT","PCMM","PIEQ","BEDY","BTGD",
    "GLTR","CRPT","DWSH","NBCM","LQDH","BKMI","LQDW","GRNI","CGUI","NUDM",
    "VEXC","POCT","ORBX","BBBI","BAIV","MIDU","FPX","EALT","IAI","ILS",
    "METV","NFLT","BCPL","PSP","GAL","FLUD","IVVW","AUSF","IBLC","NRGD",
    "XVV","BSMZ","FNGS","UPW","WCPB","KSTR","DGRS","WIP","XRPR","HFGM",
    "INOV","FLCC","JHPI","DTH","RWO","FUMB","ACII","EWK","BITW","IETC",
    "PFFR","OBIL","APCB","XPAY","SEA","DIG","FLCO","LRGC","QQQT","INCO",
    "FLTB","SMYY","GWX","VCEB","THMR","UYM","SHYL","VALQ","AVGE","BABO",
    "OKTG","CSD","GSSC","EETH","VSDB","SRPU","IYY","MBS","ELCV","BUFC",
    "OSCG","PJUL","BIBL","TCPB","AESR","BOEG","AIBD","JAJL","FGRU","FTC",
    "CVNY","RMOP","IQDG","EQL","APXM","GROZ","EMHC","VBND","MMIN","JUCY",
    "NBSM","WDEF","DFJ","IBTP","LNGX","IQQQ","KCOP","ELFY","TPLC","FDEV",
    "AVGV","BINT","DEUS","DDFA","CSRE","SEIQ","PFM","IBIE","THIR","GJUN",
    "BCTK","DNL","TXXS","ZALT","FVAL","FCTE","OPEX","GPTY","ZVOL","FXL",
    "TERG","FMUN","FEMS","LGLV","FXR","GOAU","VSLU","SIO","FLGB","XSHD",
    "QAI","SCEP","ENZL","PNOV","MNVT","SWP","EPV","DUSL","XTRE","IMCB",
    "PTIN","FDIG","BENJ","VIOV","SPFF","CVNX","TAXF","CPAI","PINK","AMZP",
    "GFLW","MSII","XMPT","SGDM","BLUC","XYLG","FMAG","FCAL","EVLN","STPZ",
    "HBDC","IHE","EMTY","IGBH","ROAM","ELIL","PFEB","PATN","SPUC","JHSC",
    "XOMX","VIDI","XSPI","XLEI","VPX","DWM","CVLC","DOJE","AMJB","TSMZ",
    "IBIG","BAFE","METL","FYEE","DRLL","MGOV","VTP","TRUD","AVMV","FDG",
    "GEVX","EDGU","OEFA","QDF","VDG","OACP","GTAO","XFIV","FFGX","DOL",
    "QEFA","FMAT","VTG","QINT","BUFP","DMXF","SCJ","FDM","FLLA","CTAP",
    "SDSI","STOT","SKF","IBOT","QQQH","SEF","TPHD","FRNW","TGLR","ILDR",
    "FCA","ISHG","HYBB","IBTQ","IMVP","AMZW","PRCS","TMFG","MANA","JEMA",
    "STXT","XBJL","CNXT","AVMC","TPIF","RSPU","OUSA","PDEC","ABLD","PNQI",
    "OSOL","CSCL","BIDD","SOFR","FFOG","NTSI","SPCI","UST","IVOG","PPI",
    "BGRN","PTBD","SEEM","BINV","PID","ASEA","IDNA","SIXO","XYZY","IBHJ",
    "PATX","HTAB","SPBW","RDIV","USSE","EDGH","UMAR","XSVM","BCHG","FLN",
    "SCNM","UFEB","ARCX","FXB","RGLO","ECON","ISCF","BLCV","GUSE","ARP",
    "ZMAR","AGGA","INDL","BOTT","BBC","ALTY","DHS","TRFM","RKNG","HEDG",
    "PSEP","LCAP","OAIM","HEZU","VTWV","AVNM","NANC","SNOV","DOGD","FUTG",
    "PMAR","GOOW","WDTE","OSEA","SDOG","ESUM","SLJY","MEDI","SPBU","FPFD",
    "YMAR","EGGY","IDUB","GMUB","CMBS","HAWX","WXET","QUIZ","AVGW","VUSE",
    "LCOW","SEPU","SEPT","CPSL","QBF","EET","BNDI","GDEC","ESPO","TARK",
    "IMST","GOOP","DGAP","DMAY","NFLW","ILCV","YBIT","DOCT","AVUQ","QLC",
    "VSTL","FMUB","TDV","HYZD","AUGU","CHIQ","DWX","REVS","VDV","DBEU",
    "PIT","BOAT","CEMB","TUSB","FDLS","BDRY","BLGR","UDEC","IBIL","CPLS",
    "FHEQ","DANA","XJH","JMSI","XMAG","SMLL","GINN","IXP","DDV","BVAL",
    "TOAK","WCBR","BUFY","MRSK","NBIE","TXUE","MUSI","TDAX","CAML","LCTU",
    "DJD","CBTO","FBOT","EWV","BGLD","TBFG","BUFB","YCS","KYLD","DLS",
    "COMB","UNOV","GEND","UBOT","LMTL","IBIF","APRJ","VTEL","RAVI","DECU",
    "QVAL","BCIL","JCPI","CAFX","VOTE","KBAB","YSPY","BASV","LQDB","IMTB",
    "FAAR","XRPM","GDOG","AVSU","MAXI","LTL","NNEX","XAIX","PSDM","FHYS",
    "EELV","USL","AWAY","PTL","DIVZ","LDRC","CAPE","ADBU","IVOV","GDMN",
    "VIOG","QSU","PFDE","DDFN","ISCG","GRPM","TAGS","LACG","RVNL","BCHP",
    "BKMS","RTXG","MEXX","GDIV","DFCA","RSSY","MDLV","IMOM","DTD","GBND",
    "TSES","GCAL","MRNX","FDRR","JHEM","GLDI","PFIG","IDOG","GLDW","BNDY",
    "KBA","QUS","PXJ","SLX","ACKY","XSVN","SMIZ","XLUI","CGGG","KCCA",
    "HYFI","UXI","BUFM","QVMT","FEX","ICAP","DDFL","FYT","RWK","DEHP",
    "DDFJ","CHPX","PMAY","SFY","EVUS","OSCV","LODI","XTJA","STBF","IMFL",
    "KLIP","LDSF","IPAY","XTN","SLTY","ILIT","JIG","HEAL","DEXC","EXI",
    "THNQ","QMFE","GQI","FXC","SSUS","GDLC","NANR","MKOR","DUNK","CDIG",
    "OALC","HBR","FNX","DFSE","RSBA","ARMW","REGS","GMAY","WEEL","DHDG",
    "PAUG","GXPS","CCNR","STXV","VEMY","LCF","HUMN","IOYY","IBII","RSPD",
    "IBBQ","FMF","DMAX","NUAG","SPUU","FNGO","SCNM","KNRG","KLAG","PGJ",
    "IBX","EUO","SVAL","IBMR","NUHY","HSCZ","KSPY","FTA","PDDL","FDTX",
    "HYBI","NUMG","GSUI","ROE","PBFR","GRNB","SIXG","INTL","OPPE","QLTI",
    "BRZU","NVDB","UJAN","VPC","TUGN","CNBS","IVVB","HAP","EDOW","FEUZ",
    "DIVN","IDVZ","JHML","REIT","HFGO","TTEQ","EES","BKFI","TPRY","NATO",
    "ABFL","OILT","DXUV","MTYY","NBOS","SBIO","TACK","MSFY","NDAA","ISCV",
    "COTG","NIOG","EQIN","DDLS","IBIH","FTKI","WTMF","CWS","QQMG","SOFA",
    "DDFD","FICS","CEFZ"
]

# Deduplicate
ETF_SYMBOLS = list(dict.fromkeys(ETF_SYMBOLS))
print(f"Total unique ETFs to fetch: {len(ETF_SYMBOLS)}")

def supabase_upsert(records, retries=3):
    """Upsert ETF records to Supabase with retry"""
    import socket
    url = f"{SUPABASE_URL}/rest/v1/foreign_etfs"
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates"
    }
    body = json.dumps(records)
    last_err = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, data=body.encode(), headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=30) as resp:
                return resp.status, resp.read()
        except Exception as e:
            last_err = e
            if attempt < retries - 1:
                time.sleep(2 ** attempt)
    return 0, str(last_err)

def fetch_batch_info(tickers_batch):
    """Fetch info for a batch of tickers"""
    results = {}
    for ticker_str in tickers_batch:
        ticker_str = ticker_str.strip()
        if not ticker_str:
            continue
        try:
            t = yf.Ticker(ticker_str)
            info = t.info
            if info and info.get('quoteType') == 'ETF':
                results[ticker_str] = {
                    'symbol': ticker_str,
                    'name': info.get('longName') or info.get('shortName', ''),
                    'price': info.get('regularMarketPrice') or info.get('navPrice') or info.get('previousClose'),
                    'change_pct': info.get('regularMarketChangePercent', 0),
                    'expense_ratio': info.get('expenseRatio', 0),
                    'dividend_yield': info.get('dividendYield', 0),
                    'aum': info.get('totalAssets', 0),
                    'category': info.get('category', ''),
                    'fund_family': info.get('fundFamily', ''),
                    'currency': info.get('currency', 'USD'),
                    'three_yr_return': info.get('threeYearAverageReturn', 0),
                    'five_yr_return': info.get('fiveYearAverageReturn', 0),
                }
        except Exception as e:
            pass
    return results

def fetch_batch_prices(tickers_batch):
    """Fetch current prices for a batch"""
    results = {}
    try:
        data = yf.download(tickers_batch, period='1d', interval='1d', progress=False, auto_adjust=True, group_by='ticker', timeout=15)
        for ticker_str in tickers_batch:
            ticker_str = ticker_str.strip()
            if not ticker_str or ticker_str not in data.columns.get_level_values(0):
                continue
            try:
                close = float(data[ticker_str]['Close'].dropna().tail(1).values[0])
                results[ticker_str] = close
            except:
                pass
    except Exception as e:
        print(f"  Price fetch error: {e}")
    return results

CHECKPOINT_FILE = "/tmp/etf_fetch_checkpoint.json"

def load_checkpoint():
    try:
        with open(CHECKPOINT_FILE) as f:
            return json.load(f)
    except:
        return {'done': [], 'records': []}

def save_checkpoint(done, records):
    with open(CHECKPOINT_FILE, 'w') as f:
        json.dump({'done': done, 'records': records[-200:]}, f)

# Load checkpoint
checkpoint = load_checkpoint()
done_symbols = set(checkpoint['done'])
pending_records = checkpoint['records']

# Filter to only pending ETFs
pending_symbols = [s for s in ETF_SYMBOLS if s not in done_symbols]
print(f"Checkpoint: {len(done_symbols)} already done, {len(pending_symbols)} pending")

# Process in batches
BATCH_SIZE = 50
UPSERT_SIZE = 100
records = list(pending_records)
count_ok = 0
total = len(pending_symbols)

for i in range(0, total, BATCH_SIZE):
    batch = pending_symbols[i:i+BATCH_SIZE]
    batch_str = ",".join(batch)
    print(f"[{i+1}-{min(i+BATCH_SIZE,total)}/{total}] Fetching info for {len(batch)} ETFs...", end=" ", flush=True)
    
    # Fetch info
    infos = fetch_batch_info(batch)
    print(f"got {len(infos)} ETF info, ", end="", flush=True)
    
    # Fetch prices
    prices = fetch_batch_prices(batch)
    print(f"got {len(prices)} prices, ", end="", flush=True)
    
    # Merge
    for sym, info in infos.items():
        price = prices.get(sym, info.get('price'))
        record = {
            'symbol': sym,
            'name': info.get('name', ''),
            'price': price,
            'change_pct': info.get('change_pct', 0),
            'expense_ratio': info.get('expense_ratio', 0),
            'dividend_yield': info.get('dividend_yield', 0),
            'aum': info.get('aum', 0),
            'category': info.get('category', ''),
            'fund_family': info.get('fund_family', ''),
            'currency': info.get('currency', 'USD'),
            'three_yr_return': info.get('three_yr_return', 0),
            'five_yr_return': info.get('five_yr_return', 0),
        }
        records.append(record)
        done_symbols.add(sym)
    
    count_ok += len(infos)
    
    # Save checkpoint
    save_checkpoint(list(done_symbols), records)
    
    # Upsert when we have enough
    if len(records) >= UPSERT_SIZE:
        print(f"\nUpserting {len(records)} records...", end=" ", flush=True)
        status, resp = supabase_upsert(records)
        print(f"status={status}")
        records = []
    
    time.sleep(0.5)  # Small delay between batches

# Final upsert
if records:
    print(f"\nFinal upsert: {len(records)} records...", end=" ", flush=True)
    status, resp = supabase_upsert(records)
    print(f"status={status}")

print(f"\n\nDone! Fetched {count_ok}/{total} valid ETF records")
