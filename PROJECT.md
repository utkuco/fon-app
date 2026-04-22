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
- Mgmt API token: sbp_9843b092bef7b9f182a07b59516c50f6dc421190 (unreliable — rate limited)

## Gotchas
- `[[...category]]` route — Next.js App Router catch-all. `params.category` tipi `string[] | undefined`
- Homepage data source: Supabase only (NOT data.json)
- ETF verisi yfinance'den gelir — USD cinsinden, TRY'ye dönüştürme gerekebilir
- Supabase free plan: max 1000 row/page — ETF fetch 2 sayfa yapar (0-999, 1000-2000)
