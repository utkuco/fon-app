# PROJECT — FonApp / FonRapor (fonrapor.com)

> Stable facts about this project. Read at the start of every session.
> Update only when architecture, stack, or conventions change.

## What this is
Türkiye yatırım fonu ve yabancı ETF portföy analiz platformu. Kullanıcılar fonların performansını, portföy dağılımını, gider oranlarını karşılaştırabilir. Supabase (Postgres) + Next.js App Router + Tailwind CSS.

## Stack
- Language: TypeScript 5
- Framework: Next.js 15 (App Router, Turbopack)
- Database: Supabase Postgres (oqkobptbvcazifpvjwfz)
- Package manager: npm (web/), pip (scripts/)
- Build: `npm run build` in web/
- Deploy: `npx vercel --prod --yes` from web/ directory

## Architecture

```
web/src/
├── app/
│   ├── page.tsx                      # Anasayfa (server component)
│   ├── fon/[code]/page.tsx           # Fon detay sayfası
│   ├── etf/
│   │   ├── [[...category]]/page.tsx  # ETF listesi (catch-all: /, /sp500, /nasdaq...)
│   │   └── [symbol]/page.tsx         # Bireysel ETF detay
│   ├── type/[type]/page.tsx          # Fon kategori sayfası
│   └── performes/                    # Karşılaştırma sayfası
├── components/
│   ├── CategoryTypeCards.tsx         # Türk fon + ETF kategori kartları
│   └── ...
└── lib/
    ├── supabase-admin.ts             # Supabase service role client
    ├── etf-categories.ts             # ETF mega-kategorileri (paylaşılan)
    └── ...

scripts/
├── etf_scraper.py                    # yfinance → Supabase ETF verisi
├── sync-tefas.py                     # TEFAS → Supabase fon verisi
└── compute-homepage-stats.ts        # Pre-computed homepage stats
```

## ETF Kategorileri (src/lib/etf-categories.ts)
6 mega-kategori — sembol pattern'ine göre:
- `sp500` → S&P 500 (SPY, VOO, IVV...)
- `nasdaq` → Nasdaq/Teknoloji (QQQ, ARKK, VGT...)
- `tahvil` → Tahvil & Bono (BND, TLT, AGG, HYG...)
- `altin` → Altın & Emtia (GLD, IAU, SLV...)
- `dunya` → Dünya (VTI, VXUS, EFA, VWO...)
- `diger` → Diğer (yukarıdakilerin dışındaki ETF'ler)

Her anasayfa ETF card'ı `/etf/${cat.key}`e link verir.

## Routing
- `/etf/[[...category]]` → catch-all (hem `/etf` hem `/etf/sp500`)
- `/etf/[symbol]` → bireysel ETF (daha specific route, öncelikli)
- `/type/[type]` → fon kategori sayfası

## DB Schema
- `foreign_etfs` — ETF metadata (symbol, aum, ytd_return, expense_ratio...)
- `foreign_etf_holdings`, `foreign_etf_sectors`, `foreign_etf_prices`
- `exchange_rates` — USD/TRY kuru
- `funds` — Türk fonlar (code, name, fund_type, market_cap...)
- `homepage_stats` — pre-computed JSONB (category_stats, top_gainers, sparklines...)

## Supabase
- Project ID: oqkobptbvcazifpvjwfz
- Anon key (client): sb_publishable__GPrsdfKRZCMZE8to916iQ_Izv9naG-
- Mgmt API token: sbp_ce308d5b5e2b05c59cbebda49ace62e8e1413fea (401 — DDL için kullanılamıyor)

## Gotchas
- `[[...category]]` route — Next.js App Router catch-all. `params.category` tipi `string[] | undefined`
- Homepage data source: Supabase only (NOT data.json)
- ETF verisi yfinance'den gelir — USD cinsinden, TRY'ye dönüştürme gerekebilir
- Supabase free plan: max 1000 row/page — ETF fetch 2 sayfa yapar (0-999, 1000-2000)

## Known Data Gaps (2026-04-24 Audit)
See `DATA-AUDIT.md` for full details. Key points:
- `funds.price_history`: Mevcut veri = fonun TÜM TEFAS geçmişi (~252 pts = ~1 yıl). Tüm 2400 fon < 5 yıl yaşında — TEFAS'ta 5 yıllık veri yok. 5Y backfill gereksiz.
- `funds.sparkline`: 2399/2400 mevcut ✅ (pagination fix sonrası)
- `homepage_stats.total`: 2400 ✅ (pagination fix sonrası)
- `fund_category_ranks`: 2400 satır ✅ (pagination fix sonrası)
- `homepage_stats.benchmarks_data`: 5 benchmark (NASDAQ, SP500, BIST100, USDTRY, GOLD) ✅ (benchmarks-cron, direct Yahoo Finance v8 API)
- `benchmarks` table: 2024-04-18 tarihli eski veri (benchmarks-cron ayrı endpoint, bu tabloyu güncellemiyor)
- `exchange_rates`: 2026-04-21 (3 gün eski)
- `foreign_etfs`: 1000/1176 ETF'in return'ı var (176 eksik)

## Benchmark Data
- **Source**: Yahoo Finance v8 REST API (`https://query1.finance.yahoo.com/v8/finance/chart/{ticker}`)
- **Tickers**: NASDAQ=^IXIC, SP500=^GSPC, BIST100=XU100.IS, USDTRY=TRY=X, GOLD=GC=F
- **NOTE**: yahoo-finance2 npm package Vercel serverless'te ÇALIŞMIYOR (Node.js fetch uyumluluk sorunu). DOĞRU YÖNTEM: direkt `fetch()` ile Yahoo Finance v8 API'sine istek atmak.
- **Cron**: Her gün 07:30 UTC (10:30 TR) — weekdays — `src/app/api/benchmarks-cron/route.ts`
- **Storage**: `homepage_stats.benchmarks_data` JSONB — last 30 data points + change % per benchmark

## TEFAS Scraper (scripts/tefas_scraper.py)
- TEFAS WAF headless Chrome'u engelliyor. Çözüm: `--headless=new` + Mac Chrome user-agent + anti-detect flags
- Script MUST use `python3.11` (homebrew at /opt/homebrew/bin/python3.11) — venv has NO selenium
- Period button ID: `MainContent_RadioButtonListPeriod_7` (value=60 ay = 5 yıl, ~1255 veri noktası)
- Chart race condition: Page load default (1Y≈253pts) → click 5Y → chart async update.
  Fix: `chart_updated()` waits for category count to INCREASE after click (from ~253 to ~1255).
- `parse_date()` expects DD.MM.YYYY format from chart categories

## Cron Jobs
- TEFAS daily: 10:00 TR weekdays — GitHub Actions workflow `.github/workflows/tefas-cron.yml`
- ETF daily: 22:00 TR weekdays — `com.fonapp.etf-daily-cron.plist` → `run_etf_cron.sh` (script has weekday check, runs Mon-Fri)
- Monitor: 11:00 TR weekdays — `com.fonapp.tefas-monitor.plist` → `run_tefas_monitor.sh`
- All use homebrew `python3.11`, NOT the project venv

## KAP Portfolio Parser Pipeline
### Components
- `scripts/kap_portfolio_parser.py` — Python PDF parser (pdfminer + Zhipu GLM)
- `scripts/kap_discover_download.py` — Chrome-based KAP PDF discovery (GitHub Actions only)
- `.github/workflows/kap-cron.yml` — Weekly GitHub Actions workflow
- `web/src/app/api/kap-portfolio-cron/route.ts` — Vercel cron (status updater only)

### How it works
1. **GitHub Actions (weekly, Monday 07:00 UTC)** — Chrome ile KAP'tan yeni PDF'leri keşfeder ve indirir
2. **GitHub Actions (weekly)** — `kap_portfolio_parser.py` batch mode: PDF'leri parse eder → Supabase `portfolio_breakdown` tablosuna yazar
3. **Vercel Cron (weekly, Monday 07:00 UTC)** — Sadece status okur, admin paneli günceller

### Database
- `portfolio_breakdown` — fund_code, report_date, stock_pct, government_bond_pct, byf_pct, extraction_method, ai_model, ai_token_count
- `parse_job_runs` — job tracking (total_funds, success_count, failed_count, categories, status)
- `system_status` — key/value (only columns: key, value, updated_at)

### Key Bugs Fixed
- `_create_job_run` SQL used bare `{total_funds}` instead of f-string → fixed
- `PDFSyntaxError` crash in `parse_single_pdf` fallback path → wrapped with try/except
- SKIP category (ALTIN/DÖVİZ) funds went through extraction → added to skip_categories
- `system_status` table only has key/value/updated_at — `upsertSystemStatus` ignores status/message params

### KAP WAF
- KAP API HTTP 666 on all non-browser requests (including from Vercel serverless)
- Chrome-based discovery MUST run in GitHub Actions, NOT Vercel
- 507 PDFs currently stored locally at `~/Desktop/projects/fon-app/pdfs/portfoy_dagilim/`
- Pending PDFs (not yet parsed): 42 funds
