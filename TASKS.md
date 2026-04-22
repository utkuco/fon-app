# TASKS — FonApp / FonRapor

## ✅ Completed

### 1. formatters.tsx
- `src/lib/formatters.tsx` — centralized: `fmtPct(showSign)`, `fmtAum(n, currency?)`, `fmtPrice`, `SparklineSvg`
- `fmtMoney` REMOVED — all files updated to `fmtAum`
- TL → `fmtAum(n, "TL")` → ₺. USD → `fmtAum(n, "USD")` → $.
- Aggregate stats → plain `fmtAum(n)` → 1.2B (no currency sign)

### 2. FundCard component
- `src/components/ui/fund-card.tsx` — single flexible component for ALL 4 card variants
- Fund: logo + sparkline + price + AUM + monthly %
- ETF: logo-badge + expense_ratio/dividend_yield + price + AUM + daily/ytd %
- TS: 0 errors ✓, Build: clean ✓

### 3. HomePageClient.tsx refactor
- FundList, CategorySection extracted
- TS: 0 errors ✓, Build: clean ✓

### 8. Type definitions centralized
- `src/types/index.ts` — shared types: Fund, CompareFund, HomeFund, HomeEtf, DashboardStats, HomepageStats, CategoryStats, CategoryChange, Stock, Etf, IndexData, ComparePageProps, MostInvested, MostHeldStock, FunListsProps, TopFund, FunListFund, BenchmarkData

### 16. ComparePageClient refactor
- `src/app/compare/ChartPanel.tsx` — normalized price chart + benchmark toggles
- `src/app/compare/FundSelector.tsx` — search + fund pill chips
- `src/app/compare/MetricsTable.tsx` — returns table (1H/1A/3A/6A/YBB/1Y) + quick stat cards
- TS: 0 errors ✓, Build: clean ✓

### 17. DashboardStats + MarketSummary → StatsGrid
- `src/components/ui/stats-grid.tsx` — shared FlexiStatCard-based grid
- `DashboardStats.tsx` updated to use StatsGrid (6 slots: Total Funds, Total AUM, Avg Daily Change, Last Update, Parsed Funds, Top Gainer)
- `MarketSummary.tsx` updated to import types from `@/types`

### 5. FlexiStatCard
- `src/components/ui/flexi-stat-card.tsx` — created and reviewed by user
- BetaAlphaCard and SharpeRatioCard: kept as-is (complex multi-metric cards, not single FlexiStatCard candidates)
- RiskMetrics: kept as-is (multi-section card)

### TL/USD Audit — FIXES APPLIED
- `FundDetailClient.tsx:246` — `fmtAum(fund.market_cap, "USD")` → `"TL"` (fund market caps are TL)
- `metrics-table.tsx:76,104` — `fmtAum(cf.market_cap, "USD")` → `"TL"` (compare page fund market caps)
- `HomePageClient.tsx:544` — `{fmtAum(..., "TL")} ₺ AUM` → `{fmtAum(..., "TL")} AUM` (duplicate ₺ removed)
- `TypePageClient.tsx:205` — same duplicate fix
- `CompanyPageClient.tsx:195` — same duplicate fix
- `CategoryOverview.tsx:84` — `{fmtAum(..., "TL")} TL` → `{fmtAum(..., "TL")}` (duplicate TL removed)
- `CompaniesPageClient.tsx:97,161` — duplicate "TL" text removed
- `CategoryTypeCards.tsx:291` — `formatAUM(stat.total_market_cap) TL` → `fmtAum(stat.total_market_cap, "TL")` (local formatAUM replaced with centralized fmtAum)
- ETF AUM uses `"USD"` correctly (ETFs are USD-denominated)
- Exchange rate API calls (etf-cron, performers) correctly use "USD"/"TRY" strings

### Deployment
- component-test page deleted ✓
- TS: 0 errors ✓, Build: clean ✓, Deploy: ✓

## 📁 Key Files
- `src/lib/formatters.tsx` — centralized formatters
- `src/types/index.ts` — shared type definitions
- `src/components/ui/flexi-stat-card.tsx` — FlexiStatCard base component
- `src/components/ui/stats-grid.tsx` — shared StatsGrid
- `src/components/ui/fund-card.tsx` — FundCard (4 variants)
- `src/app/compare/ChartPanel.tsx` — compare chart
- `src/app/compare/FundSelector.tsx` — fund search + pills
- `src/app/compare/MetricsTable.tsx` — returns table
- `src/app/HomePageClient.tsx` — refactored
- `src/app/fon/[code]/FundDetailClient.tsx` — fund detail
- `src/components/BetaAlphaCard.tsx` — Beta/Alpha/R² card (complex multi-metric, as-is)
- `src/components/SharpeRatioCard.tsx` — Sharpe/Sortino/Calmar card (complex multi-metric, as-is)
- `src/components/RiskMetrics.tsx` — risk metrics card (multi-section, as-is)
