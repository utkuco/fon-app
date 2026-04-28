# FonRapor — Project Reference (Single Source of Truth)

> Bu döküman kodun kendisiyle birlikte güncellenir. Bir component, API route veya cron eklendiğinde/düzeltildiğinde bu döküman da güncellenir.

---

## Overview

**FonRapor** (fonrapor.com) Türkiye yatırım fonu ve ETF analiz platformudur. TEFAS ve KAP'tan veri çeker, Supabase'de saklar, Next.js frontend ile sunar.

**3 Çalışma Ortamı:**
- **Vercel** — Cron job'lar + web server (vercel.json schedule)
- **Local Mac** — launchd cron job'lar (~/Library/LaunchAgents)
- **GitHub Actions** — Backup pipeline'lar (`.github/workflows/`)

**Supabase Project Ref:** `oqkobptbvcazifpvjwfz`
**URL:** https://fonrapor.com
**Admin panel:** /admin (password: `Yigit-co1`)

---

## Database Schema

### funds (TEFAS fonları)

| Column | Type | Description | Source |
|--------|------|-------------|--------|
| `code` | text PK | Fon kodu (e.g. "OYP.A") | TEFAS |
| `name` | text | Fon adı | TEFAS |
| `fund_type` | text | Type kodu (e.g. "SRF", "VFF", "KFF", "OKS", "BYF", "DÖVİZ") | TEFAS |
| `company` | text | Yönetim şirketi | TEFAS |
| `company_id` | uuid FK | companies tablosuna link | TEFAS |
| `tefas_code` | text | TEFAS'taki kod | TEFAS |
| `nav` | numeric | Net varlık değeri | TEFAS |
| `price` | numeric | Fiyat | TEFAS |
| `price_date` | date | Son fiyat tarihi | TEFAS |
| `daily_change` | numeric | Günlük değişim (%) | TEFAS → `fund-cron` hesaplar |
| `weekly` | numeric | 1 haftalık getiri (%) | TEFAS |
| `monthly` | numeric | 1 aylık getiri (%) | TEFAS |
| `quarterly` | numeric | 3 aylık getiri (%) | TEFAS |
| `market_cap` | numeric | AUM (TL) | TEFAS |
| `number_of_investors` | integer | Yatırımcı sayısı | TEFAS |
| `price_history` | jsonb | `[{date, price, change}]` array — max ~1500 rows | TEFAS |
| `sparkline` | jsonb | `{"points": [[x,y], ...], "positive": bool}` — pre-scaled to SVG space | `fund-cron` (Vercel) |
| `breakdown` | jsonb | `{ticker: weight}` varlık dağılımı | KAP PDF parser |
| `last_tefas_fetch` | timestamptz | Son TEFAS güncellemesi | `tefas_scraper_v2.py` |
| `report_date` | date | Son portföy raporu tarihi | TEFAS |

### foreign_etfs (Uluslararası ETF'ler)

| Column | Type | Description | Source |
|--------|------|-------------|--------|
| `symbol` | text PK | ETF ticker (e.g. "SPY", "GLD") | Manual / yfinance |
| `name` | text | Full name | yfinance |
| `category` | text | Category key (see etf-categories.ts) | Manual mapping |
| `asset_type` | text | EQUITY / BOND / COMMODITY / REAL_ESTATE | Manual mapping |
| `region` | text | gelişmiş / gelişmekte / global | Manual mapping |
| `fund_family` | text | Issuer (e.g. "Vanguard", "iShares") | yfinance |
| `currency` | text | Base currency (USD, EUR, etc.) | yfinance |
| `nav_price` | numeric | NAV price | yfinance |
| `price` | numeric | Market price | yfinance |
| `price_try` | numeric | TL cinsinden fiyat | Computed |
| `change_pct` | numeric | Günlük değişim (%) | yfinance |
| `expense_ratio` | numeric | Yıllık gider oranı (%) | yfinance |
| `dividend_yield` | numeric | Temettü verimi (%) | yfinance |
| `aum` | numeric | AUM (USD) | yfinance |
| `ytd_return` | numeric | YTD return (%) | yfinance |
| `ytd_return_try` | numeric | TL bazlı YTD | Computed |
| `one_month_return_try` | numeric | 1 aylık TL | Computed |
| `three_month_return_try` | numeric | 3 aylık TL | Computed |
| `six_month_return_try` | numeric | 6 aylık TL | Computed |
| `three_yr_return` | numeric | 3 yıllık return (%) | yfinance |
| `five_yr_return` | numeric | 5 yıllık return (%) | yfinance |
| `beta` | numeric | Beta | Computed |
| `currency_rate` | numeric | USD/TRY kuru | Computed |
| `sparkline` | jsonb | `{"points": [[x,y], ...], "positive": bool}` — pre-scaled SVG space | `etf_daily_cron.py` (local) |
| `price_history` | jsonb | `[{date, close, currency}]` array | `etf_daily_cron.py` |
| `returns` | jsonb | `{"1W": x, "1M": x, "3M": x, "6M": x, "1Y": x, "3Y": x}` | `compute_etf_returns.py` |
| `is_active` | boolean | Aktif mi | Manual |
| `updated_at` | timestamptz | Son güncelleme | Cron |

### foreign_etf_prices (ETF fiyat zaman serisi — büyük tablo)

| Column | Type | Description |
|--------|------|-------------|
| `id` | bigint PK | Auto |
| `symbol` | text | ETF ticker |
| `date` | date | Fiyat tarihi |
| `close` | numeric | Kapanış fiyatı |
| `currency` | text | Para birimi |

### foreign_etf_holdings (ETF varlıkları)

| Column | Type | Description |
|--------|------|-------------|
| `etf_symbol` | text PK/FK | ETF ticker |
| `holdings` | jsonb | `[{ticker, name, weight, price}]` |

### foreign_etf_sectors (ETF sektör dağılımı)

| Column | Type | Description |
|--------|------|-------------|
| `etf_symbol` | text PK/FK | ETF ticker |
| `sectors` | jsonb | `[{sector, weight}]` |

### fund_holdings (Fon portföy holdingleri)

| Column | Type | Description | Source |
|--------|------|-------------|--------|
| `fund_code` | text FK | funds.code | `tefas_scraper_v2.py` |
| `isin` | text | Varlık ISIN | TEFAS |
| `ticker` | text | BIST ticker (e.g. "THYAO") | TEFAS |
| `company` | text | Şirket adı | TEFAS (unreliable) |
| `weight` | numeric | Portföy ağırlığı (%) | TEFAS |
| `updated_at` | timestamptz | Son güncelleme | TEFAS |

### homepage_stats (Pre-computed ana sayfa verileri)

| Column | Type | Description | Updated by |
|--------|------|-------------|------------|
| `id` | int PK | Always 1 (singleton) | — |
| `total` | int | Toplam fon sayısı | `homepage-stats-cron` |
| `tefas_total` | int | TEFAS fon sayısı | `homepage-stats-cron` |
| `total_market_cap` | numeric | Toplam AUM (TL) | `homepage-stats-cron` |
| `avg_daily_change` | numeric | Ortalama günlük değişim (%) | `homepage-stats-cron` |
| `latest_date` | date | Son işlem günü | `homepage-stats-cron` |
| `trading_days` | int | İşlem günü sayısı | `homepage-stats-cron` |
| `top5_gainers` | jsonb | `[{code, name, change, market_cap}]` | `homepage-stats-cron` |
| `top5_losers` | jsonb | `[{code, name, change, market_cap}]` | `homepage-stats-cron` |
| `most_invested` | jsonb | `[{code, name, market_cap}]` | `homepage-stats-cron` |
| `most_held_stocks` | jsonb | `[{ticker, company, total_weight, fund_count}]` | `homepage-stats-cron` |
| `category_stats` | jsonb | `{type: {count, avg_change, total_market_cap}}` | `homepage-stats-cron` |
| `category_change` | jsonb | `{type: {change_pct, prev_aum, curr_aum, count}}` | `homepage-stats-cron` |
| `category_sparklines` | jsonb | `{type: {points, positive}}` — DEPRECATED | `homepage-stats-cron` |
| `benchmarks_data` | jsonb | `{LABEL: {data: [{date, price}], change}}` | `benchmarks-cron` |
| `updated_at` | timestamptz | Son güncelleme | Various |

### category_history (Benchmark index tarihçesi)

| Column | Type | Description | Source |
|--------|------|-------------|--------|
| `id` | serial PK | Auto | — |
| `category` | text | ALTIN / BORSA / DOVİZ / all | Manual |
| `date` | date | Tarih | `benchmarks-cron` |
| `value` | numeric | Index değeri | `benchmarks-cron` |
| `daily_change` | numeric | Günlük değişim (%) | Computed |

### fund_category_ranks (Fon sıralama verileri)

| Column | Type | Description | Updated by |
|--------|------|-------------|------------|
| `fund_code` | text PK | funds.code | `homepage-stats-cron` |
| `category` | text | fund_type | `homepage-stats-cron` |
| `rank` | int | Kategori içi sıra (1=best) | `homepage-stats-cron` |
| `category_count` | int | Kategorideki toplam fon | `homepage-stats-cron` |
| `percentile` | numeric | Yüzdelik (100=best) | `homepage-stats-cron` |
| `computed_at` | timestamptz | Hesaplama zamanı | `homepage-stats-cron` |

### system_status (Cron sağlık takibi)

| Column | Type | Description |
|--------|------|-------------|
| `key` | text PK | Status key (e.g. "last_tefas_fetch") |
| `value` | text | ISO timestamp veya mesaj |
| `updated_at` | timestamptz | Son yazma |

**system_status keys:**
- `last_tefas_fetch` → `tefas_scraper_v2.py` (local launchd)
- `last_fund_cron` → `fund-cron/route.ts` (Vercel)
- `last_homepage_stats_cron` → `homepage-stats-cron/route.ts` (Vercel)
- `last_benchmarks_cron` → `benchmarks-cron/route.ts` (Vercel)
- `last_etf_fetch` → `etf_daily_cron.py` (local launchd)
- `etf_cron_stats` → `etf_daily_cron.py` (local launchd)
- `last_kap_portfolio_cron` → `kap_portfolio_parser.py` (local launchd)
- `tefas_scraper_log` → `tefas_scraper_v2.py` (local launchd)

### content_posts (Blog/icerik yönetimi)

| Column | Type | Description |
|--------|------|-------------|
| `id` | uuid PK | Auto |
| `title` | text | Başlık |
| `slug` | text UNIQUE | URL slug |
| `content` | text | HTML içerik |
| `excerpt` | text | Kısa açıklama |
| `cover_image` | text | Cover image URL |
| `category` | text | Kategori |
| `status` | text | draft / pending / published |
| `published_at` | timestamptz | Yayınlanma tarihi |
| `author_name` | text | Yazar |
| `created_at` | timestamptz | Oluşturma |

### companies (Fon yönetim şirketleri)

| Column | Type | Description |
|--------|------|-------------|
| `id` | uuid PK | Auto |
| `name` | text UNIQUE | Şirket adı |
| `display_name` | text | Display adı |
| `logo` | text | Logo URL |

### kap_portfolio_holdings (KAP portföy holdingleri)

| Column | Type | Description | Source |
|--------|------|-------------|--------|
| `id` | serial PK | Auto | — |
| `isin` | text | Varlık ISIN | `kap_portfolio_parser.py` |
| `ticker` | text | BIST ticker | Parsed from PDF |
| `company` | text | Şirket adı | Parsed from PDF |
| `fund_code` | text FK | funds.code | Parsed from PDF |
| `weight` | numeric | Ağırlık (%) | Parsed from PDF |
| `parsed_at` | timestamptz | Parse zamanı | `kap_portfolio_parser.py` |

### parse_job_runs (KAP parse logları)

| Column | Type | Description |
|--------|------|-------------|
| `id` | serial PK | Auto |
| `fund_code` | text | Parse edilen fon |
| `status` | text | success / error / skipped |
| `pdf_filename` | text | PDF dosya adı |
| `holdings_count` | int | Bulunan holding sayısı |
| `error_message` | text | Hata mesajı |
| `run_at` | timestamptz | Çalışma zamanı |

---

## Sparkline Data Format

### Storage Format (both funds and ETFs)
```typescript
type Sparkline = {
  points: [number, number][]; // SVG coordinate pairs
  positive: boolean;
};
```

### SVG Coordinate Space
- **x range**: [0, 280] (280 data points for funds, ~30 for ETFs)
- **y range**: [0, 40] (pre-scaled to viewBox height)
- **Last point**: trend direction indicator

### Sources
- **Funds**: `fund-cron/route.ts` (Vercel, 13:00 UTC) — computes from `price_history`
- **ETFs**: `etf_daily_cron.py` (local launchd, 22:00 TR) — computes from `foreign_etf_prices`

### Rendering
`SparklineMini` component (`components/ui/fund-card.tsx`) accepts pre-scaled points directly:
- Auto-detects legacy data: if `maxY <= 1` (normalized), scales to SVG space
- Pre-scaled data (maxY > 28): uses directly without transformation

---

## Pages and Data Sources

### / (Ana Sayfa)
- **Data source**: `fetchHomePageData()` (`lib/homepage-data.ts`)
  1. `funds` table → top 5000 by `market_cap` (sparkline, price, daily_change, etc.)
  2. `homepage_stats` table (id=1) → pre-computed stats, benchmarks_data
- **API route**: `GET /api/homepage-data` → `fetchHomePageData()`
- **Cache**: `cache-control: public, s-maxage=300, stale-while-revalidate=60`
- **Components**: `HomePageClient` → `FunLists`, `CategorySection`, `BlogSection`

### /varliklar (Varlık Bazlı Görünüm)
- **Data source**: `foreign_etfs` table (direct, via `etfs/route.ts`)
  - Selects: symbol, name, category, price, change_pct, aum, ytd_return, sparkline
  - Filters: region, asset_type
  - Sort: aum, price, change, yield, expense, ytd, three_yr
- **Sparklines**: fetched individually per symbol (bypasses 1000-row limit)
- **API route**: `GET /api/etfs`

### /varliklar/[category] (ETF Kategori Sayfası)
- **Data source**: Same `/api/etfs` with `?region=` / `?asset_type=` filters
- **Category routes**: `/varliklar/altin`, `/varliklar/hisseler`, `/varliklar/tahvil`, `/varliklar/gelismekte`

### /etf (ETF Listesi — 3rd party içerik)
- **Data source**: Static / redirects to `/varliklar`

### /etf/[symbol] (ETF Detay Sayfası)
- **Data source**: `GET /api/etfs?symbol=XYZ`
  - Main: `foreign_etfs` row
  - Holdings: `foreign_etf_holdings` (JSONB field)
  - Sectors: `foreign_etf_sectors` (JSONB field)
  - Prices: `foreign_etf_prices` (last 365 days)
- **Components**: `EtfDetailClient` → `EtfSymbolDetailClient`

### /fon (Fon Listesi)
- **Data source**: `funds` table (direct, via `supabaseAdmin`)
- **API route**: `GET /api/funds` (only accepts `?codes=` param — no full list endpoint)
- **No server-side fetch**: Client fetches from `supabase` (anon key) directly

### /fon/[code] (Fon Detay Sayfası)
- **Data source**: `funds` table row by code (server-side via `supabaseAdmin`)
- **Fields**: code, name, company, fund_type, nav, price, market_cap, daily_change, weekly, monthly, quarterly, breakdown, price_history, sparkline, number_of_investors
- **Components**: `FundDetailClient` → `FundChart`, `ReturnsTable`, `CategoryRankCard`, `RiskMetrics`, `BetaAlphaCard`, `SharpeRatioCard`, `BenchmarkCompareCard`, `BreakdownChart`
- **Category data**: `fund_category_ranks` table → rank, percentile per category

### /holdings (Hisse Tercihleri)
- **Data source**: `fund_holdings` table aggregated by ISIN
- **API**: `fetchTopHoldings()` (`lib/holdings-data.ts`) → groups by ISIN, counts funds
- **Display name logic**: `displayName()` function parses ISIN to extract BIST ticker
  - 000-series: TRA/TRE + 4-char ticker + "000" (e.g. TREBIMM00018 → BIMAS)
  - A/B-series: TRA/TRE + 5-char ticker (e.g. TRAKCHOL91Q8 → KCHOL)
  - TRT government bonds: last 8 chars of ISIN

### /holdings/[isin] (Hisse Detay)
- **Data source**: `fetchHoldingDetail()` (`lib/holdings-data.ts`)
  1. Gets ISIN's ticker/company from `fund_holdings`
  2. Gets all fund_codes holding this ISIN
  3. Enriches with fund names/types/daily_change from `funds` table

### /companies (Şirketler)
- **Data source**: `companies` table
- **Client component**: `CompaniesPageClient`

### /company/[slug] (Şirket Detay)
- **Data source**: `companies` table by slug
- **Funds by company**: filtered from `funds` table by `company_id`

### /compare (Fon Karşılaştırma)
- **Data source**: Multiple `funds` by codes (via `/api/funds?codes=...`)
- **Components**: `ComparePageClient` → chart-panel, fund-selector, metrics-table

### /performers (Performans Sayfaları)
- **Data source**: `funds` table sorted by daily_change (gainers/losers)

### /type/[type] (Fon Tipi Sayfası)
- **Data source**: `funds` filtered by `fund_type`
- **Types**: VFF, SRF, OKS, KFF, DÖVİZ, ALTIN, BYF

### /blog (Blog Listesi)
- **Data source**: `content_posts` table filtered by `status = 'published'`
- **API route**: `GET /api/blogs`

### /blog/[slug] (Blog Post Detay)
- **Data source**: `content_posts` by slug

### /admin (Admin Dashboard)
- **Auth**: Cookie-based session (`admin_session`)
- **Components**: `Sidebar`, `DashboardStats`

### /admin/content (İçerik Yönetimi)
- **Data source**: `content_posts` table
- **Features**: List, create, edit, delete posts, change status (draft/pending/published)

### /admin/blog (Blog Yönetimi)
- **Data source**: `content_posts` filtered by `category = 'blog'`

### /admin/system (Sistem Durumu)
- **Data source**: `system_status` table via `getSystemStatus()`
- **Cron definitions**: Defined inline in `page.tsx` (JOBS array)
- **Status keys displayed**: last_tefas_fetch, last_fund_cron, last_homepage_stats_cron, last_benchmarks_cron, last_etf_fetch, last_kap_portfolio_cron

### /admin/kap-portfolio (KAP Portföy Dashboard)
- **Data source**: `parse_job_runs` table + `kap_portfolio_holdings` count per fund
- **Stats**: total PDFs, parsed count, pending count, error count

### /guides/[term] (Rehber Sayfaları)
- Static content pages

---

## Components and Their Data

### Layout
- `layout.tsx` (root) — wraps all pages with SiteNavbar + Footer + CookieBanner
- `admin/layout.tsx` — hides SiteNavbar/Footer/CookieBanner, shows admin Sidebar

### Navigation
- `SiteNavbar` — Logo, nav links, search bar, dark mode toggle
- `Sidebar` (admin) — fixed left sidebar with nav items

### Homepage Components
- `FunLists` (`HomePageClient`) — tabbed view: Tümü/VFF/SRF/etc., fund list with sparklines
- `CategorySection` — category cards with sparklines and stats
- `BlogSection` — latest 3 blog posts
- `TopMovers` — top gainers/losers list
- `MarketSummary` — total funds, AUM, avg change
- `DashboardStats` — homepage stats strip

### Fund Components
- `FundCard` — card with sparkline SVG, price, change, fund type badge, company logo
  - **Data**: `PureFundItem` type: code, name, fund_type, daily_change, monthly, price, market_cap, company, company_logo, sparkline, breakdown
- `FundChart` — price history line chart
- `ReturnsTable` — weekly/monthly/quarterly returns table
- `CategoryRankCard` — fund's rank within its category (from `fund_category_ranks`)
- `RiskMetrics` — standard deviation, max drawdown
- `BetaAlphaCard` — beta/alpha calculation with category benchmark
- `SharpeRatioCard` — Sharpe ratio
- `BenchmarkCompareCard` — compare against benchmark index
- `CategoryCompareCard` — compare category performance
- `InvestorTrendCard` — net investor flow (number_of_investors change)
- `BreakdownChart` — portfolio breakdown pie/bar chart (from `funds.breakdown`)
- `MostHeldStocks` — top stocks held by funds (from `homepage_stats.most_held_stocks`)
- `MostInvestedFunds` — top funds by AUM

### ETF Components
- `EtfGrid` — grid of ETF cards
- `EtfMiniCard` — compact ETF card with sparkline
- `EtfListClient` — filterable/sortable ETF list
- `EtfPageClient` — main ETF page tabs (Hisse/Tahvil/Emtia/Altın)

### Holding Components
- `HoldingsClient` — ISIN list with fund count, search/filter
- `HoldingsDetailClient` — funds holding a specific ISIN

### UI Primitives
- `card` — Card, CardContent
- `badge` — Status/category badge
- `button` — Button variants
- `input` — Text input
- `table` — Data table
- `tabs` — Tab navigation
- `skeleton` — Loading placeholder
- `separator` — Divider

### Blog Components
- `BlogCard` — blog post preview card
- `BlogListClient` — paginated blog list

---

## API Routes

### Public API (frontend uses these)

| Route | Method | Description | Data Source |
|-------|--------|-------------|-------------|
| `/api/homepage-data` | GET | Homepage stats + funds | `homepage_stats` + `funds` |
| `/api/funds` | GET | Fund details by codes | `funds` (requires `?codes=` param) |
| `/api/etfs` | GET | ETF list/detail | `foreign_etfs`, `foreign_etf_prices` |
| `/api/holdings` | GET | Top holdings aggregated | `fund_holdings` |
| `/api/blogs` | GET | Published blog posts | `content_posts` |
| `/api/content-posts` | GET/POST/PATCH/DELETE | Content CRUD (admin) | `content_posts` |
| `/api/content-calendar` | GET | Posts by month (admin) | `content_posts` |
| `/api/search` | GET | Search funds/ETFs | `funds` + `foreign_etfs` |
| `/api/feed` | GET | RSS/Atom feed | `content_posts` |

### Internal / Cron API

| Route | Method | Auth | Description |
|-------|--------|------|-------------|
| `/api/fund-cron` | GET | `x-vercel-cron: true` | Compute daily_change + sparklines for funds |
| `/api/homepage-stats-cron` | GET | `x-vercel-cron: true` + `x-cron-secret` | Compute homepage_stats + category ranks |
| `/api/benchmarks-cron` | GET | `x-vercel-cron: true` or Bearer token | Fetch Yahoo Finance benchmarks → homepage_stats |
| `/api/etf-cron` | GET | `x-vercel-cron: true` | Fetch ETF prices via yfinance |
| `/api/etf-returns-cron` | GET | `x-vercel-cron: true` | Compute ETF return metrics |
| `/api/kap-portfolio-cron` | GET | `x-vercel-cron: true` | Parse KAP portfolio PDFs |

### Admin API

| Route | Method | Auth | Description |
|-------|--------|------|-------------|
| `/api/admin-auth` | POST | Password body | Set `admin_session` cookie |
| `/api/admin-login` | POST | Password body | Login handler |
| `/api/admin-logout` | POST | Cookie | Clear session |
| `/api/admin-debug` | GET | Cookie | Debug endpoint |
| `/api/setup-blog` | POST | ? | Seed blog posts |

---

## Cron Jobs

### Vercel Cron Routes (`vercel.json`)

| Route | Schedule (UTC) | Schedule (TR) | Primary Write | Status Key |
|-------|---------------|---------------|---------------|------------|
| `fund-cron` | `0 13 * * 1-5` | 15:00 Pazartesi–Cuma | `funds.daily_change`, `funds.sparkline` | `last_fund_cron` |
| `homepage-stats-cron` | `0 14 * * 1-5`, `30 23 * * 1-5` | 16:00 & 02:30 Pazartesi–Cuma | `homepage_stats`, `fund_category_ranks` | `last_homepage_stats_cron` |
| `benchmarks-cron` | `30 7 * * 1-5` | 09:30 Pazartesi–Cuma | `category_history`, `homepage_stats.benchmarks_data` | `last_benchmarks_cron` |
| `etf-cron` | `0 21 * * 1-5` | 23:00 Pazartesi–Cuma | `foreign_etfs` | (no status key) |
| `etf-returns-cron` | `0 22 * * 1-5` | 00:00 Pazartesi–Cuma | `foreign_etfs.returns` | (no status key) |

### Local Launchd Jobs

| Job Name | Script | Schedule (TR) | Primary Write | Status Key |
|----------|--------|---------------|---------------|------------|
| `com.fonapp.tefas-daily-cron` | `tefas_scraper_v2.py` | 10:00 Pazartesi–Cuma | `funds`, `fund_holdings`, `system_status` | `last_tefas_fetch` |
| `com.fonapp.etf-daily-cron` | `etf_daily_cron.py` | 22:00 Her gün | `foreign_etfs`, `foreign_etf_prices`, `system_status` | `last_etf_fetch` |
| `com.fonapp.tefas-monitor` | `tefas_monitor.py` | 11:00 Pazartesi–Cuma | None (Slack alert only) | — |
| `com.fonapp.kap-portfolio-cron` | `kap_portfolio_parser.py` | 09:00 Pazartesi | `kap_portfolio_holdings`, `parse_job_runs` | `last_kap_portfolio_cron` |

### GitHub Actions (Backup)

| Workflow | Schedule (TR) | Trigger | Notes |
|----------|---------------|---------|-------|
| `tefas-cron.yml` | 10:00 Pazartesi–Cuma | schedule + workflow_dispatch | PyPI `tefas` package fallback |
| `kap-cron.yml` | — | **DISABLED** | Local launchd is primary |

---

## Local Scripts

### Active (Production)

| Script | Purpose | Trigger |
|--------|---------|---------|
| `tefas_scraper_v2.py` | TEFAS CDP API scraper — undetected-chromedriver | Local launchd |
| `etf_daily_cron.py` | ETF prices via yfinance, sparkline computation | Local launchd |
| `kap_discover_download.py` | Discover + download KAP portfolio PDFs | Local launchd |
| `kap_portfolio_parser.py` | Parse KAP PDFs via Zhipu GLM | Local launchd |
| `tefas_monitor.py` | Monitor TEFAS freshness, Slack alert | Local launchd |

### Backfill / One-time

| Script | Purpose |
|--------|---------|
| `tefas_5y_backfill.py` | 5Y historical fund data |
| `backfill_etf_sparkline_precomputed.py` | Backfill ETF sparklines in y=[0-40] format |
| `compute_etf_returns.py` | Compute ETF return metrics |
| `kap_discover_download.py` | Also used for one-time PDF discovery |

---

## Key Code Patterns

### Supabase Client Usage
- **Server-side (API routes, server components)**: `supabaseAdmin` from `@/lib/supabase-admin` — uses `SUPABASE_SERVICE_KEY`
- **Client-side (browser)**: `supabase` from `@/lib/supabase` — uses `NEXT_PUBLIC_SUPABASE_ANON_KEY`
- **Admin client creation**: `createClient(supabaseUrl, supabaseServiceKey!, { auth: { persistSession: false } })` — **no fallback for empty key** (crashes loudly if missing, which is correct)

### system_status Writes
- Uses direct REST API (`fetch` to `${supabaseUrl}/rest/v1/system_status`) with `Prefer: resolution=merge-duplicates`
- **Not** via `supabaseAdmin` (avoids Edge runtime issues)
- Function: `upsertSystemStatus(key, value, status?, message?)` in `lib/system-status.ts`

### Sparkline Computation
- `fund-cron`: computes from `price_history` JSONB (last 30 days), writes to `funds.sparkline`
- `etf_daily_cron.py`: computes from `foreign_etf_prices`, writes to `foreign_etfs.sparkline`
- Format: `{points: [[x,y], ...], positive: bool}` where x=[0,280], y=[0,40]

### Homepage Stats Flow
1. `benchmarks-cron` (09:30 TR) → `homepage_stats.benchmarks_data`
2. `fund-cron` (15:00 TR) → `funds.sparkline`, `funds.daily_change`
3. `homepage-stats-cron` (16:00 TR) → reads `funds` (lightweight cols), computes `homepage_stats` + `fund_category_ranks`

---

## Environment Variables

### Vercel
```
NEXT_PUBLIC_SUPABASE_URL=https://oqkobptbvcazifpvjwfz.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=sb_publishable__GPrsdfKRZCMZE8to916iQ_Izv9naG-
SUPABASE_SERVICE_KEY=sb_service__FPrsdfKRZCMZE8to916iQ_Izv9naG-8jK  (secret)
CRON_SECRET=FonRapor2025!  (secret)
ADMIN_PASSWORD=Yigit-co1  (secret)
```

### Local Mac (.env in scripts/)
```
SUPABASE_URL=https://oqkobptbvcazifpvjwfz.supabase.co
SUPABASE_SERVICE_KEY=sb_service__FPrsdfKRZCMZE8to916iQ_Izv9naG-8jK
ZHIPU_API_KEY=glm-...
TEFAS_EMAIL=...
TEFAS_PASSWORD=...
SLACK_WEBHOOK_URL=...
```

---

## Known Issues

1. **`last_homepage_stats_cron` not written before Apr 2026 fix**: `supabase-admin.ts` had `|| "***"` fallback causing 401 errors. Fixed by removing fallback.

2. **`homepage-stats-cron` statement timeout**: Fetching 2400+ funds with `price_history` JSONB column causes Supabase free tier timeout. Fixed by removing `price_history` from SELECT.

3. **TEFAS unreachable from Vercel**: TEFAS DNS/connection fails from Vercel serverless. `fund-cron/route.ts` notes this — local `tefas_scraper_v2.py` is primary source.

4. **`fund_holdings.company` unreliable**: Contains garbled values. Use `displayName()` in `holdings-data.ts` to extract ticker from ISIN instead.

5. **Duplicate KAP pipeline**: GitHub Actions `kap-cron.yml` disabled. Local launchd is primary.

6. **Duplicate ETF pipelines**: Both `etf_daily_cron.py` (local, 22:00) and `etf-cron` (Vercel, 23:00) write to `foreign_etfs`.

7. **Vercel logs often empty**: Vercel cron logs only appear after real traffic or dashboard interaction.

---

## Deployment

- **Vercel token**: `***` (see Vercel dashboard)
- **Deploy command**: `npx vercel --prod --token ***`
- **Git author**: `utkuozercoskun@gmail.com` / `Utku Özer Coşkun`
- **Admin panel**: /admin (password: `Yigit-co1`)
