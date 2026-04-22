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

### 17. FunLists.tsx Refactor (v1.2)
- **Before:** 495-line monolith (ChampionCard + BenchmarksSection + GainersSection + TopFundsSection + MostHeldStocksSection + StockCard + MiniCard — all in one file)
- **After:**
  - `src/components/ui/benchmarks-section.tsx` — benchmark panel (standalone)
  - `src/components/ui/gainers-section.tsx` — mixed FON+ETF table with period tabs (standalone, exports `Period`, `TurkishGainerEntry`, `EtfGainerEntry`, `getReturn`, `PERIOD_LABELS`)
  - `src/components/FunLists.tsx` — orchestrator (~130 lines, imports BenchmarksSection + GainersSection)
- `ChampionCard.tsx` — created but **unused** (dead code in original), removed
- TS: 0 errors ✓, Build: clean ✓, Deploy: ✓

### 18. Duplicate types removed (d1)
- `HomePageClient.tsx` — inline `HomeFund`/`HomeEtf` removed, imported from `@/types`
- `EtfGrid.tsx` — inline `HomeEtf` removed, imported from `@/types`
- `types/index.ts` already had all shared types — no duplication remaining
- TS: 0 errors ✓, Build: clean ✓

### 19. React.memo FundCard (d3)
- `src/components/ui/fund-card.tsx` — `export function FundCard` → `export const FundCard = React.memo(function FundCard ...)`
- Prevents re-render of all 4 card variants (PureFundItem/MixedEtfItem/MixedFundItem/EtfTabItem) on parent state changes
- TS: 0 errors ✓, Build: clean ✓

### 20. Holdings API → TanStack Query (d4)
- `src/components/providers.tsx` — new `QueryProvider` wrapping `QueryClientProvider` (10-min stale time, 30-min gc, no refetch on window focus)
- `src/app/layout.tsx` — `<QueryProvider>` wraps entire app body
- `src/hooks/useHoldings.ts` — `useHoldings(initialHoldings)` + `useHoldingDetail(isin)` custom hooks
- `src/app/holdings/HoldingsClient.tsx` — `useEffect/useState` → `useQuery` hooks:
  - `holdings` list: `useHoldings(initialHoldings)` with server-side `initialData` (SSR still works, background revalidation added)
  - `detail` modal: `useHoldingDetail(selectedIsin)` — automatic refetch on ISIN change, loading/error states from hook
  - Removed: `useCallback`, `useEffect` for detail, `useState` for `holdings/detail/loading`
  - Added: `refetch` + `refetchDetail` retry buttons
- TS: 0 errors ✓, Build: clean ✓, Deploy: ✓

### 21. Precomputed stats audit (d5)
- `fetchHomePageData` in `src/lib/homepage-data.ts` already uses `homepage_stats` precomputed table
- No redundant aggregate queries found
- **No code changes needed** — already optimal

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
- `src/components/providers.tsx` — TanStack QueryProvider
- `src/hooks/useHoldings.ts` — `useHoldings` + `useHoldingDetail` TanStack Query hooks
- `src/components/ui/flexi-stat-card.tsx` — FlexiStatCard base component
- `src/components/ui/stats-grid.tsx` — shared StatsGrid
- `src/components/ui/fund-card.tsx` — FundCard (4 variants, React.memo)
- `src/components/ui/benchmarks-section.tsx` — benchmark panel
- `src/components/ui/gainers-section.tsx` — FON+ETF gainers table
- `src/app/compare/ChartPanel.tsx` — compare chart
- `src/app/compare/FundSelector.tsx` — fund search + pills
- `src/app/compare/MetricsTable.tsx` — returns table
- `src/app/HomePageClient.tsx` — refactored
- `src/app/holdings/HoldingsClient.tsx` — TanStack Query powered
- `src/app/fon/[code]/FundDetailClient.tsx` — fund detail
- `src/components/BetaAlphaCard.tsx` — Beta/Alpha/R² card (complex multi-metric, as-is)
- `src/components/SharpeRatioCard.tsx` — Sharpe/Sortino/Calmar card (complex multi-metric, as-is)
- `src/components/RiskMetrics.tsx` — risk metrics card (multi-section, as-is)
