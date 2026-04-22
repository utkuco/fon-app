"use client";

import { useEffect, useState, useMemo, useRef } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Logo } from "@/components/Logo";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent } from "@/components/ui/card";
import { CompanyLogo } from "@/components/CompanyLogo";
import { FundCardSkeleton } from "@/components/ui/skeleton";
import {
  TrendingUp, TrendingDown, Search, ArrowUpDown, PieChart, Heart, BarChart2,
  ChevronDown, X, SlidersHorizontal, ArrowUp, ArrowDown
} from "lucide-react";
import { TYPE_LABELS, TYPE_COLORS, ASSET_LABELS, ASSET_COLORS } from "@/lib/shared-config";
import { FunLists } from "@/components/FunLists";
import { CategoryTypeCards } from "@/components/CategoryTypeCards";
import { EtfGrid } from "@/components/EtfGrid";

// HomepageStats: partial stats — server computes a subset, rest are undefined
type HomepageStats = {
  total?: number;
  total_market_cap?: number;
  avg_daily_change?: number;
  [key: string]: any;
};

interface HomePageProps {
  initialData?: { funds: HomeFund[]; stats?: HomepageStats | null; benchmarks?: Record<string, Array<{ date: string; price: number }>> } | null;
  initialEtfs?: HomeEtf[];
  etfTopGainers?: Array<{ symbol: string; name: string; change_pct: number; aum: number | null; ret_1m: number; ret_3m: number; ret_6m: number }>;
  etfTopLosers?: Array<{ symbol: string; name: string; change_pct: number; aum: number | null }>;
  turkishGainers?: Array<{
    code: string;
    name: string;
    market_cap: number;
    ret_1d: number;
    ret_1w: number;
    ret_1m: number;
    ret_3m: number | null;
    ret_6m: number | null;
  }>;
}

type HomeEtf = {
  symbol: string;
  name: string;
  price: number | null;
  price_try: number | null;
  currency: string | null;
  change_pct: number | null;
  expense_ratio: number | null;
  dividend_yield: number | null;
  aum: number | null;
  ytd_return: number | null;        // USD/ETF base currency
  ytd_return_try: number | null;   // TRY-adjusted
  one_month_return_try: number | null;
  three_month_return_try: number | null;
  six_month_return_try: number | null;
  three_yr_return: number | null;
  five_yr_return: number | null;
  beta: number | null;
  asset_type: string | null;
  fund_family: string | null;
  updated_at: string | null;
};

// Homepage uses a subset of fund fields — server query maps to this
type HomeFund = {
  code: string;
  name: string;
  fund_type: string | null;
  company_id: string | null;
  market_cap: number | null;
  daily_change: number | null;
  price: number | null;
  weekly: number | null;
  monthly: number | null;
  quarterly: number | null;
  breakdown: Record<string, number> | null;
  // Optional fields — available from other tables or future DB columns
  company?: string | null;
  company_logo?: string | null;
  manager?: string | null;
  holding_count?: number | null;
  sparkline?: { points: Array<[number, number]>; positive: boolean } | null;
};

interface Stats {
  total: number;
  total_market_cap: number;
  avg_daily_change: number;
  latest_date: string | null;
  trading_days: number;
  top5_gainers: Array<{ code: string; name: string; change: number; market_cap: number | null }>;
  top5_losers: Array<{ code: string; name: string; change: number; market_cap: number | null }>;
  most_invested: Array<{ code: string; name: string; market_cap: number | null; daily_change: number | null }>;
  most_held_stocks: Array<{ ticker: string; company: string; total_weight: number; fund_count: number }>;
  category_stats: Record<string, { count: number; avg_change: number; total_market_cap: number }>;
  category_change: Record<string, { change_pct: number; prev_aum: number; curr_aum: number; count: number }>;
  category_sparklines: Record<string, { points: Array<[number, number]>; positive: boolean }>;
}

const ALL_TYPES = ["Tümü", "VFF", "SRF", "OKS", "KFF", "DÖVİZ", "ALTIN", "BYF"];

function fmtNum(n: number | null | undefined, decimals = 0): string {
  if (n == null) return "—";
  return n.toLocaleString("tr-TR", { maximumFractionDigits: decimals });
}

function fmtMoney(n: number | null | undefined): string {
  if (n == null) return "—";
  if (n >= 1e9) return `${(n / 1e9).toFixed(1)}B`;
  if (n >= 1e6) return `${(n / 1e6).toFixed(1)}M`;
  if (n >= 1e3) return `${(n / 1e3).toFixed(0)}K`;
  return n.toLocaleString("tr-TR", { maximumFractionDigits: 0 });
}

function fmtDate(s: string | null | undefined): string {
  if (!s) return "—";
  return s.split(" ")[0];
}

function ChangeBadge({ value }: { value: number | null }) {
  if (value == null) return null;
  const positive = value >= 0;
  return (
    <span className={`inline-flex items-center gap-0.5 text-xs font-semibold px-1.5 py-0.5 rounded ${positive ? "bg-green-100 text-green-700" : "bg-red-100 text-red-700"}`}>
      {positive ? <TrendingUp className="w-3 h-3" /> : <TrendingDown className="w-3 h-3" />}
      {Math.abs(value).toFixed(2)}%
    </span>
  );
}

function BreakdownBar({ breakdown }: { breakdown: Record<string, number> | null }) {
  if (!breakdown || Object.keys(breakdown).length === 0) return null;

  const entries = Object.entries(breakdown)
    .filter(([, v]) => v > 0)
    .sort(([, a], [, b]) => b - a)
    .slice(0, 5);

  const COLORS = ["bg-blue-500", "bg-amber-500", "bg-yellow-400", "bg-green-500", "bg-orange-400"];

  return (
    <div className="flex items-center gap-1 mt-2">
      {entries.map(([key, value], i) => (
        <div
          key={key}
          className={`h-1.5 rounded-full ${COLORS[i] || "bg-gray-300"}`}
          style={{ width: `${Math.min(value, 100)}%`, minWidth: value > 5 ? "4px" : "2px" }}
          title={`${key}: ${value.toFixed(1)}%`}
        />
      ))}
    </div>
  );
}

type SortKey = "price" | "market_cap" | "daily_change" | "holding_count" | "weekly" | "monthly" | "quarterly";
type SortDir = "asc" | "desc";
type EtfSortKey = "aum" | "daily_change" | "ytd" | "expense_ratio" | "dividend_yield" | "name";

const PAGE_SIZE = 50;
const ETF_PAGE_SIZE = 25;

export default function HomepageClient({ initialData, initialEtfs, etfTopGainers, etfTopLosers, turkishGainers }: HomePageProps) {
  const pathname = usePathname();
  const [data, setData] = useState(initialData ?? null);
  // loading is always false since server provides initialData;
  // kept for any future client-side refetch scenarios
  const [loading, setLoading] = useState(false);
  // Asset type tab: "all" | "turkish" | "etf" — replaces the two-column layout
  const [assetTab, setAssetTab] = useState<"all" | "turkish" | "etf">("all");
  const [etfSearch, setEtfSearch] = useState("");
  const [etfQ, setEtfQ] = useState("");
  const [etfSortKey, setEtfSortKey] = useState<EtfSortKey>("aum");
  const [etfSortDir, setEtfSortDir] = useState<SortDir>("desc");
  const [etfPage, setEtfPage] = useState(1);

  // Server-side rendering provides initialData via props
  // No client-side fallback fetch needed.

  const [search, setSearch] = useState("");
  const [q, setQ] = useState("");
  const [typeFilter, setTypeFilter] = useState("Tümü");
  const [sortKey, setSortKey] = useState<SortKey>("market_cap");
  const [sortDir, setSortDir] = useState<SortDir>("desc");
  const [page, setPage] = useState(1);
  const [showDropdown, setShowDropdown] = useState(false);
  const [aumRange, setAumRange] = useState<[number, number]>([0, 750000]); // 0–750B TL range
  const [changeRange, setChangeRange] = useState<[number, number]>([-10, 10]);

  // Reset to page 1 when filters change
  useEffect(() => { setPage(1); }, [q, typeFilter, sortKey, sortDir, aumRange, changeRange, assetTab]);
  useEffect(() => { setEtfPage(1); }, [etfQ, etfSortKey, etfSortDir, assetTab]);

  // Autocomplete suggestions
  const suggestions = useMemo(() => {
    if (!search || search.length < 2) return [];
    const fundList = data?.funds || [];
    const lower = search.toLowerCase();
    return fundList
      .filter(f =>
        f.code.toLowerCase().includes(lower) ||
        (f.name || "").toLowerCase().includes(lower) ||
        (f.manager || "").toLowerCase().includes(lower)
      )
      .slice(0, 8);
  }, [search, data]);

  // Update page title with data freshness
  useEffect(() => {
    if (!data?.stats) return;
    const date = data.stats.latest_date
      ? new Date(data.stats.latest_date + "T00:00:00").toLocaleDateString("tr-TR", { day: "2-digit", month: "2-digit", year: "numeric" })
      : null;
    const title = date
      ? `FonRapor — ${data.stats.total} fon, ${date}`
      : `FonRapor — ${data.stats.total} yatırım fonu`;
    document.title = title;
  }, [data]);

  const funds = data?.funds || [];
  const stats = data?.stats;

  const filtered = useMemo(() => {
    let result = funds;

    if (q) {
      const lower = q.toLowerCase();
      result = result.filter(f =>
        f.code.toLowerCase().includes(lower) ||
        f.name?.toLowerCase().includes(lower) ||
        (f.manager || "").toLowerCase().includes(lower)
      );
    }

    if (typeFilter !== "Tümü") {
      result = result.filter(f => f.fund_type === typeFilter);
    }

    // AUM filter (in millions)
    result = result.filter(f => {
      const mc = (f.market_cap || 0) / 1e6;
      return mc >= aumRange[0] && mc <= aumRange[1];
    });

    // Daily change filter
    result = result.filter(f => {
      const ch = f.daily_change || 0;
      return ch >= changeRange[0] && ch <= changeRange[1];
    });

    return [...result].sort((a, b) => {
      let cmp = 0;
      if (sortKey === "price") cmp = (a.price || 0) - (b.price || 0);
      else if (sortKey === "market_cap") cmp = (a.market_cap || 0) - (b.market_cap || 0);
      else if (sortKey === "daily_change") cmp = (a.daily_change || 0) - (b.daily_change || 0);
      else if (sortKey === "holding_count") cmp = (a.holding_count || 0) - (b.holding_count || 0);
      else {
        // Sort by return: use pre-computed weekly/monthly/quarterly fields
        if (sortKey === "weekly") cmp = (a.weekly ?? 0) - (b.weekly ?? 0);
        else if (sortKey === "monthly") cmp = (a.monthly ?? 0) - (b.monthly ?? 0);
        else if (sortKey === "quarterly") cmp = (a.quarterly ?? 0) - (b.quarterly ?? 0);
      }
      return sortDir === "asc" ? cmp : -cmp;
    });
  }, [funds, q, typeFilter, sortKey, sortDir, aumRange, changeRange]);

  // Reset to page 1 when filters change
  const paginated = useMemo(() => {
    const start = (page - 1) * PAGE_SIZE;
    return filtered.slice(start, start + PAGE_SIZE);
  }, [filtered, page]);

  const totalPages = Math.ceil(filtered.length / PAGE_SIZE);

  // ETF filtered + sorted
  const etfFiltered = useMemo(() => {
    let result = initialEtfs || [];
    if (etfQ) {
      const lower = etfQ.toLowerCase();
      result = result.filter(e =>
        e.symbol.toLowerCase().includes(lower) ||
        (e.name || "").toLowerCase().includes(lower)
      );
    }
    return [...result].sort((a, b) => {
      let cmp = 0;
      if (etfSortKey === "name") cmp = (a.name || "").localeCompare(b.name || "");
      else if (etfSortKey === "aum") cmp = (a.aum || 0) - (b.aum || 0);
      else if (etfSortKey === "daily_change") cmp = (a.change_pct || 0) - (b.change_pct || 0);
      else if (etfSortKey === "ytd") cmp = (a.ytd_return_try || 0) - (b.ytd_return_try || 0);
      else if (etfSortKey === "expense_ratio") cmp = (a.expense_ratio || 0) - (b.expense_ratio || 0);
      else if (etfSortKey === "dividend_yield") cmp = (a.dividend_yield || 0) - (b.dividend_yield || 0);
      return etfSortDir === "asc" ? cmp : -cmp;
    });
  }, [initialEtfs, etfQ, etfSortKey, etfSortDir]);

  const etfPaginated = useMemo(() => {
    const start = (etfPage - 1) * ETF_PAGE_SIZE;
    return etfFiltered.slice(start, start + ETF_PAGE_SIZE);
  }, [etfFiltered, etfPage]);
  const etfTotalPages = Math.ceil(etfFiltered.length / ETF_PAGE_SIZE);

  // Mixed items for "all" tab: FON + ETF together, top 12 by daily change
  const mixedItems = useMemo(() => {
    const fundEntries = (data?.funds || []).map(f => ({
      kind: "fund" as const,
      code: f.code,
      name: f.name || "",
      fund_type: f.fund_type,
      daily_change: f.daily_change ?? 0,
      monthly: f.monthly ?? 0,
      price: f.price ?? null,
      market_cap: f.market_cap ?? null,
      company: f.company ?? null,
      company_logo: f.company_logo ?? null,
      sparkline: f.sparkline ?? null,
      href: `/fon/${f.code}`,
    }));
    const etfEntries = (initialEtfs || []).map(e => ({
      kind: "etf" as const,
      code: e.symbol,
      name: e.name || "",
      daily_change: e.change_pct ?? 0,
      price: e.price ?? null,
      aum: e.aum ?? null,
      currency: e.currency ?? "USD",
      asset_type: e.asset_type ?? null,
      href: `/etf/${e.symbol}`,
    }));
    return [...fundEntries, ...etfEntries]
      .sort((a, b) => b.daily_change - a.daily_change)
      .slice(0, 12);
  }, [data, initialEtfs]);

  function toggleSort(key: SortKey) {
    if (sortKey === key) setSortDir(d => d === "asc" ? "desc" : "asc");
    else { setSortKey(key); setSortDir("desc"); }
  }

  function toggleEtfSort(key: EtfSortKey) {
    if (etfSortKey === key) setEtfSortDir(d => d === "asc" ? "desc" : "asc");
    else { setEtfSortKey(key); setEtfSortDir("desc"); }
  }

  function SortIcon({ k }: { k: SortKey }) {
    if (sortKey !== k) return <ArrowUpDown className="w-3 h-3 opacity-30" />;
    return <ArrowUpDown className="w-3 h-3" />;
  }

  return (
    <div className="min-h-screen bg-neutral-50">
      {/* ─── Top Nav ─── */}
      <header className="bg-white border-b border-neutral-200 sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-3 sm:px-4 h-16 flex items-center gap-3">
          {/* Brand */}
          <div className="flex items-center gap-2 shrink-0">
            <Logo variant="full" className="h-8 w-auto" />
          </div>

          {/* Nav Links */}
          <nav className="hidden md:flex items-center gap-0.5 ml-2">
            <Link
              href="/"
              className={`px-3 py-1.5 text-sm font-medium rounded-lg transition ${
                pathname === "/" ? "text-blue-600 bg-blue-50" : "text-neutral-600 hover:text-blue-600 hover:bg-blue-50"
              }`}
            >
              Fonlar
            </Link>
            <Link
              href="/etf"
              className={`px-3 py-1.5 text-sm font-medium rounded-lg transition ${
                pathname === "/" || pathname?.startsWith("/etf") ? "text-blue-600 bg-blue-50" : "text-neutral-600 hover:text-blue-600 hover:bg-blue-50"
              }`}
            >
              ETF'ler
            </Link>
            <Link
              href="/performers"
              className={`px-3 py-1.5 text-sm font-medium rounded-lg transition ${
                pathname === "/performers" ? "text-blue-600 bg-blue-50" : "text-neutral-600 hover:text-blue-600 hover:bg-blue-50"
              }`}
            >
              Performanslar
            </Link>
            <Link
              href="/companies"
              className={`px-3 py-1.5 text-sm font-medium rounded-lg transition ${
                pathname === "/companies" ? "text-blue-600 bg-blue-50" : "text-neutral-600 hover:text-blue-600 hover:bg-blue-50"
              }`}
            >
              Şirketler
            </Link>
          </nav>

          {/* Search */}
          <div className="relative flex-1 min-w-0 max-w-xs sm:max-w-none">
            <Search className="absolute left-2 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-neutral-400 pointer-events-none" />
            <Input
              value={search}
              onChange={e => { setSearch(e.target.value); setShowDropdown(true); }}
              onKeyDown={e => {
                if (e.key === "Enter") { setQ(search); setShowDropdown(false); }
                if (e.key === "Escape") setShowDropdown(false);
              }}
              onFocus={() => setShowDropdown(true)}
              onBlur={() => setTimeout(() => setShowDropdown(false), 150)}
              placeholder="Fon ara..."
              className="pl-7 pr-3 h-8 text-sm bg-neutral-100 border-transparent focus:bg-white focus:border-blue-300 w-full"
            />
            {showDropdown && suggestions.length > 0 && (
              <div className="absolute top-full left-0 right-0 mt-1 bg-white border border-neutral-200 rounded-lg shadow-xl z-[9999] max-h-72 overflow-y-auto">
                {suggestions.map(f => (
                  <Link
                    key={f.code}
                    href={`/fon/${f.code}`}
                    className="flex items-center gap-2 px-3 py-2 hover:bg-neutral-50 text-left transition"
                    onClick={() => setShowDropdown(false)}
                  >
                    <span className="font-mono font-bold text-blue-600 text-xs w-10 shrink-0">{f.code}</span>
                    <span className="text-xs text-neutral-700 truncate">{f.name}</span>
                  </Link>
                ))}
              </div>
            )}
          </div>

          {/* CTAs */}
          <div className="flex items-center gap-1.5 shrink-0">
            <Link
              href="/favorites"
              className="flex items-center justify-center w-8 h-8 sm:w-auto sm:h-8 sm:px-2.5 text-red-600 bg-red-50 sm:rounded-lg hover:bg-red-100 transition"
              title="Favorilerim"
            >
              <Heart className="w-3.5 h-3.5 sm:w-3.5 sm:h-3.5" />
              <span className="hidden sm:inline text-xs font-medium ml-1">Favoriler</span>
            </Link>
            <Link
              href="/compare"
              className="flex items-center justify-center w-8 h-8 sm:w-auto sm:h-8 sm:px-2.5 text-xs font-medium text-white bg-blue-600 sm:rounded-lg hover:bg-blue-700 transition"
              title="Karşılaştır"
            >
              <BarChart2 className="w-3.5 h-3.5 sm:w-3.5 sm:h-3.5" />
              <span className="hidden sm:inline ml-1">Karşılaştır</span>
            </Link>
          </div>
        </div>
      </header>

      {/* ─── Main Content ─── */}
      <main className="max-w-7xl mx-auto px-4 py-6 space-y-6">

        {/* Tür Kategorileri Kartları */}
        <CategoryTypeCards
          categoryStats={stats?.category_stats || {}}
          categoryChange={stats?.category_change || {}}
          categorySparklines={stats?.category_sparklines || {}}
          etfData={initialEtfs}
        />

        {/* Section divider */}
        <div className="flex items-center gap-3 py-1">
          <div className="flex-1 h-px bg-neutral-200" />
        </div>

        {/* Fun Lists */}
        <FunLists
          top5Gainers={stats?.top5_gainers}
          top5Losers={stats?.top5_losers}
          etfTopGainers={etfTopGainers}
          etfTopLosers={etfTopLosers}
          turkishGainers={turkishGainers}
          mostInvested={stats?.most_invested}
          mostHeldStocks={stats?.most_held_stocks}
          categoryStats={stats?.category_stats}
          categoryChange={stats?.category_change}
          funds={funds}
          benchmarks={data?.benchmarks}
        />

        {/* ── TÜM FONLAR & ETF — TEK GRID + TAB BAR ── */}
        <div>
          {/* Section divider */}
          <div className="flex items-center gap-3 py-1 mb-3">
            <div className="flex-1 h-px bg-neutral-200" />
            <span className="text-xs font-semibold text-neutral-500 uppercase tracking-wide">Tüm Varlıklar</span>
            <div className="flex-1 h-px bg-neutral-200" />
          </div>

          {/* Tab bar card */}
          <div className="bg-white border border-neutral-200 rounded-xl overflow-hidden">
            {/* Tab bar */}
            <div className="flex items-center gap-2 px-4 py-2.5 border-b border-neutral-100">
              <span className="font-bold text-sm text-neutral-900">Tüm Varlıklar</span>
              <div className="ml-auto flex gap-1 bg-neutral-100 rounded-lg p-0.5">
                {([
                  { key: "all" as const, label: `Tümü (${(data?.funds?.length || 0) + (initialEtfs?.length || 0)})` },
                  { key: "turkish" as const, label: `Türk Fonları (${(data?.funds?.length || 0)})` },
                  { key: "etf" as const, label: `Yabancı ETF (${initialEtfs?.length || 0})` },
                ]).map(t => (
                  <button
                    key={t.key}
                    onClick={() => setAssetTab(t.key)}
                    className={`px-2.5 py-1 rounded-md text-[11px] font-medium transition ${
                      assetTab === t.key
                        ? "bg-white text-blue-700 shadow-sm"
                        : "text-neutral-500 hover:text-neutral-700"
                    }`}
                  >
                    {t.label}
                  </button>
                ))}
              </div>
            </div>

            {/* ── TÜMÜ TAB ── */}
            {assetTab === "all" && (
              <>
                {/* Sort bar for mixed */}
                <div className="flex items-center gap-2 px-4 py-2 border-b border-neutral-100 overflow-x-auto no-scrollbar">
                  <span className="text-[10px] text-neutral-400 shrink-0">Sırala:</span>
                  <div className="flex gap-1 shrink-0">
                    <button onClick={() => {}} className="px-2 py-0.5 rounded text-[10px] font-medium bg-blue-600 text-white">Günlük</button>
                    <button onClick={() => {}} className="px-2 py-0.5 rounded text-[10px] font-medium bg-neutral-100 text-neutral-500 hover:bg-neutral-200">Aylık</button>
                  </div>
                  <span className="text-[10px] text-neutral-400 shrink-0 ml-2">— FON ve ETF birlikte, günlük değişime göre sıralı</span>
                </div>
                {/* Mixed grid */}
                <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 xl:grid-cols-4 gap-2 p-3">
                  {mixedItems.map((item) => {
                    const isEtf = item.kind === "etf";
                    const isPos = item.daily_change >= 0;
                    const typeColor = !isEtf && item.fund_type ? (TYPE_COLORS[item.fund_type] || "bg-neutral-100 text-neutral-600") : "bg-neutral-100 text-neutral-600";
                    const gradId = `sg${Math.abs((item.code?.split("").reduce((a, c) => (a * 31 + c.charCodeAt(0)) | 0, 0) ?? 0) % 99999)}`;
                    const sparkPoints = !isEtf && "sparkline" in item ? (item.sparkline as { points: [number, number][]; positive: boolean } | null)?.points || null : null;
                    const sparkColor = !isEtf && "sparkline" in item ? ((item.sparkline as { points: [number, number][]; positive: boolean } | null)?.positive ?? isPos) ? "#10B981" : "#EF4444" : isPos ? "#10B981" : "#EF4444";
                    return (
                      <Link key={`${item.kind}-${item.code}`} href={item.href} className="group block">
                        <Card className="h-full transition-all duration-150 hover:shadow-md hover:-translate-y-0.5 cursor-pointer">
                          <CardContent className="p-2.5 flex flex-col h-full gap-1">
                            <div className="flex items-start gap-1.5">
                              {isEtf ? (
                                <div className="w-7 h-7 rounded-md bg-amber-50 border border-amber-200 flex items-center justify-center shrink-0 mt-0.5">
                                  <span className="text-[9px] font-bold text-amber-700">ETF</span>
                                </div>
                              ) : (
                                <CompanyLogo
                                  logoFile={item.company_logo ?? undefined}
                                  company={item.company ?? undefined}
                                  name={item.name}
                                  code={item.code}
                                  size={28}
                                  className="mt-0.5 shrink-0"
                                />
                              )}
                              <div className="min-w-0 flex-1">
                                <div className="flex items-center gap-1 flex-wrap">
                                  <span className={`font-mono font-bold text-[10px] truncate group-hover:underline ${isEtf ? "text-amber-700" : "text-blue-700"}`}>
                                    {item.code}
                                  </span>
                                  {!isEtf && item.fund_type && (
                                    <span className={`text-[9px] px-1 py-0.5 rounded-full font-medium ${typeColor}`}>
                                      {TYPE_LABELS[item.fund_type] || item.fund_type}
                                    </span>
                                  )}
                                  {isEtf && item.asset_type && (
                                    <span className={`text-[9px] px-1 py-0.5 rounded-full font-medium bg-neutral-100 text-neutral-600`}>
                                      {item.asset_type}
                                    </span>
                                  )}
                                  <span className={`shrink-0 px-1 py-0.5 rounded text-[10px] font-semibold ${isPos ? "bg-green-100 text-green-700" : "bg-red-100 text-red-700"}`}>
                                    {isPos ? "+" : ""}{item.daily_change.toFixed(2)}%
                                  </span>
                                </div>
                                <div className="text-[10px] text-neutral-600 font-medium line-clamp-2 leading-tight mt-0.5">{item.name}</div>
                              </div>
                            </div>
                            {/* Sparkline */}
                            {sparkPoints && sparkPoints.length >= 2 ? (
                              <svg width="100%" height={28} viewBox="0 0 280 28" className="w-full h-7 overflow-visible">
                                <defs>
                                  <linearGradient id={gradId} x1="0" y1="0" x2="0" y2="1">
                                    <stop offset="0%" stopColor={sparkColor} stopOpacity="0.12" />
                                    <stop offset="100%" stopColor={sparkColor} stopOpacity="0" />
                                  </linearGradient>
                                </defs>
                                {((): React.ReactNode => {
                                  const pathD = sparkPoints.map((p, idx) => {
                                    const [px, py] = p;
                                    return `${idx === 0 ? "M" : "L"}${px.toFixed(1)},${py.toFixed(1)}`;
                                  }).join(" ");
                                  const areaD = pathD + ` L280,28 L0,28 Z`;
                                  const [lastX, lastY] = sparkPoints[sparkPoints.length - 1];
                                  return <><path d={areaD} fill={`url(#${gradId})`} /><path d={pathD} fill="none" stroke={sparkColor} strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" /><circle cx={lastX} cy={lastY} r="2" fill={sparkColor} /></>;
                                })()}
                              </svg>
                            ) : <div className="h-7" />}
                            {/* Footer */}
                            <div className="flex items-end justify-between pt-1 border-t border-neutral-100">
                              <div>
                                <div className="text-sm font-black text-neutral-900 font-mono tracking-tight">
                                  {isEtf
                                    ? (item.currency === "GBp" ? `£${((item.price ?? 0) / 100).toFixed(2)}` : `$${(item.price ?? 0).toFixed(2)}`)
                                    : (item.price != null ? `₺${item.price.toFixed(4)}` : "—")}
                                </div>
                                <div className="text-[9px] text-neutral-400">
                                  {isEtf ? (item.currency !== "USD" ? item.currency : "USD") : "₺"}
                                </div>
                              </div>
                              {!isEtf && item.market_cap != null && (
                                <div className="text-right">
                                  <div className="text-xs font-semibold text-neutral-700">{fmtMoney(item.market_cap)}</div>
                                  <div className="text-[9px] text-neutral-400">AUM</div>
                                </div>
                              )}
                              {isEtf && item.aum != null && (
                                <div className="text-right">
                                  <div className="text-xs font-semibold text-neutral-700">
                                    {item.aum >= 1e12 ? `$${(item.aum / 1e12).toFixed(1)}T` : item.aum >= 1e9 ? `$${(item.aum / 1e9).toFixed(1)}B` : `$${(item.aum / 1e6).toFixed(0)}M`}
                                  </div>
                                  <div className="text-[9px] text-neutral-400">AUM</div>
                                </div>
                              )}
                              {!isEtf && item.monthly != null && (
                                <div className={`text-xs font-semibold font-mono ${item.monthly >= 0 ? "text-green-600" : "text-red-600"}`}>
                                  {item.monthly >= 0 ? "+" : ""}{item.monthly.toFixed(1)}%
                                </div>
                              )}
                              {isEtf && (
                                <div className={`text-xs font-semibold font-mono ${item.daily_change >= 0 ? "text-green-600" : "text-red-600"}`}>
                                  {item.daily_change >= 0 ? "+" : ""}{item.daily_change.toFixed(2)}%
                                </div>
                              )}
                            </div>
                          </CardContent>
                        </Card>
                      </Link>
                    );
                  })}
                </div>
                {/* Footer */}
                <div className="text-center text-[10px] text-neutral-400 py-2 border-t border-neutral-100">
                  {mixedItems.length} varlık — karışık sıralı
                  <span className="ml-2"><Link href="/performers" className="text-blue-600 hover:underline">Tümünü gör →</Link></span>
                </div>
              </>
            )}

            {/* ── TÜRK FONLARI TAB ── */}
            {assetTab === "turkish" && (
              <>
                {/* Filter bar */}
                <div className="flex items-center gap-1.5 px-4 py-2 overflow-x-auto no-scrollbar border-b border-neutral-100">
                  {ALL_TYPES.map(t => (
                    <button
                      key={t}
                      onClick={() => setTypeFilter(t)}
                      className={`px-2 py-0.5 rounded-full text-xs font-medium whitespace-nowrap shrink-0 transition ${
                        typeFilter === t
                          ? "bg-blue-600 text-white"
                          : "bg-neutral-100 text-neutral-600 hover:bg-blue-100 hover:text-blue-700"
                      }`}
                    >
                      {t === "Tümü" ? t : TYPE_LABELS[t] || t}
                    </button>
                  ))}
                  <div className="w-px h-4 bg-neutral-200 shrink-0 mx-0.5" />
                  <div className="flex items-center gap-0.5 shrink-0">
                    <span className="text-[10px] text-neutral-400 hidden sm:inline">Sırala:</span>
                    {([
                      { k: "market_cap" as SortKey, label: "Büyüklük" },
                      { k: "daily_change" as SortKey, label: "Günlük" },
                      { k: "monthly" as SortKey, label: "Aylık" },
                    ]).map(({ k, label }) => (
                      <button
                        key={k}
                        onClick={() => toggleSort(k)}
                        className={`flex items-center gap-0.5 px-1.5 py-0.5 rounded text-[10px] transition whitespace-nowrap ${
                          sortKey === k
                            ? "bg-blue-600 text-white"
                            : "bg-neutral-100 text-neutral-500 hover:bg-blue-100"
                        }`}
                      >
                        {label}
                        {sortKey === k && (sortDir === "asc" ? <ArrowUp className="w-2 h-2" /> : <ArrowDown className="w-2 h-2" />)}
                      </button>
                    ))}
                  </div>
                </div>
                {/* Fund grid */}
                <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 xl:grid-cols-4 gap-2 p-3">
                  {paginated.length === 0 ? (
                    <div className="col-span-full text-center py-12 text-neutral-400 text-sm">Sonuç bulunamadı</div>
                  ) : paginated.map((f) => {
                    const typeColor = TYPE_COLORS[f.fund_type || ""] || "bg-neutral-100 text-neutral-600";
                    const sparkPoints = f.sparkline?.points || null;
                    const sparkPositive = f.sparkline?.positive ?? ((f.monthly ?? f.daily_change ?? 0) >= 0);
                    const sparkColor = sparkPositive ? "#10B981" : "#EF4444";
                    const gradId = `sg${Math.abs((f.code?.split("").reduce((a, c) => (a * 31 + c.charCodeAt(0)) | 0, 0) ?? 0) % 99999)}`;
                    return (
                      <Link key={f.code} href={`/fon/${f.code}`} className="group block">
                        <Card className="h-full transition-all duration-150 hover:shadow-md hover:-translate-y-0.5 cursor-pointer">
                          <CardContent className="p-2.5 flex flex-col h-full gap-1">
                            <div className="flex items-start gap-1.5">
                              <CompanyLogo logoFile={f.company_logo} company={f.company || undefined} name={f.name} code={f.code} size={28} className="mt-0.5 shrink-0" />
                              <div className="min-w-0 flex-1">
                                <div className="flex items-center gap-1 flex-wrap">
                                  <span className="font-mono font-bold text-blue-600 text-[10px] truncate group-hover:underline">{f.code}</span>
                                  {f.fund_type && <span className={`text-[9px] px-1 py-0.5 rounded-full font-medium ${typeColor}`}>{TYPE_LABELS[f.fund_type] || f.fund_type}</span>}
                                  <ChangeBadge value={f.daily_change} />
                                </div>
                                <div className="text-[10px] text-neutral-600 font-medium line-clamp-2 leading-tight mt-0.5">{f.name}</div>
                              </div>
                            </div>
                            {sparkPoints && sparkPoints.length >= 2 ? (
                              <svg width="100%" height={28} viewBox="0 0 280 28" className="w-full h-7 overflow-visible">
                                <defs>
                                  <linearGradient id={gradId} x1="0" y1="0" x2="0" y2="1">
                                    <stop offset="0%" stopColor={sparkColor} stopOpacity="0.12" />
                                    <stop offset="100%" stopColor={sparkColor} stopOpacity="0" />
                                  </linearGradient>
                                </defs>
                                {((): React.ReactNode => {
                                  const pathD = sparkPoints.map((p, idx) => {
                                    const [px, py] = p;
                                    return `${idx === 0 ? "M" : "L"}${px.toFixed(1)},${py.toFixed(1)}`;
                                  }).join(" ");
                                  const areaD = pathD + ` L280,28 L0,28 Z`;
                                  const [lastX, lastY] = sparkPoints[sparkPoints.length - 1];
                                  return <><path d={areaD} fill={`url(#${gradId})`} /><path d={pathD} fill="none" stroke={sparkColor} strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" /><circle cx={lastX} cy={lastY} r="2" fill={sparkColor} /></>;
                                })()}
                              </svg>
                            ) : <div className="h-7" />}
                            <div className="flex items-end justify-between pt-1 border-t border-neutral-100">
                              <div>
                                <div className="text-sm font-black text-neutral-900 font-mono tracking-tight">{f.price != null ? f.price.toFixed(4) : "—"}</div>
                                <div className="text-[9px] text-neutral-400">₺</div>
                              </div>
                              <div className="text-right">
                                <div className="text-xs font-semibold text-neutral-700">{f.market_cap ? fmtMoney(f.market_cap) : "—"}</div>
                                <div className="text-[9px] text-neutral-400">AUM</div>
                              </div>
                              {f.monthly != null && (
                                <div className={`text-xs font-semibold font-mono ${f.monthly >= 0 ? "text-green-600" : "text-red-600"}`}>{f.monthly >= 0 ? "+" : ""}{f.monthly.toFixed(1)}%</div>
                              )}
                            </div>
                          </CardContent>
                        </Card>
                      </Link>
                    );
                  })}
                </div>
                {totalPages > 1 && (
                  <div className="flex items-center justify-center gap-1 py-2 border-t border-neutral-100">
                    <Button variant="ghost" size="sm" className="h-7 text-xs" onClick={() => setPage(p => Math.max(1, p - 1))} disabled={page === 1}>←</Button>
                    <span className="text-xs text-neutral-500 px-2">{page} / {totalPages}</span>
                    <Button variant="ghost" size="sm" className="h-7 text-xs" onClick={() => setPage(p => Math.min(totalPages, p + 1))} disabled={page === totalPages}>→</Button>
                  </div>
                )}
                <div className="text-center text-[10px] text-neutral-400 py-1.5 border-t border-neutral-100">
                  {filtered.length > PAGE_SIZE ? `${(page - 1) * PAGE_SIZE + 1}–${Math.min(page * PAGE_SIZE, filtered.length)} / ${filtered.length}` : `${filtered.length} fon`}
                </div>
              </>
            )}

            {/* ── YABANCI ETF TAB ── */}
            {assetTab === "etf" && (
              <>
                {/* ETF filter bar */}
                <div className="flex items-center gap-1.5 px-4 py-2 overflow-x-auto no-scrollbar border-b border-neutral-100">
                  <div className="relative shrink-0">
                    <Search className="absolute left-1.5 top-1/2 -translate-y-1/2 w-2.5 h-2.5 text-neutral-400 pointer-events-none" />
                    <input
                      value={etfSearch}
                      onChange={e => { setEtfSearch(e.target.value); }}
                      onKeyDown={e => { if (e.key === "Enter") setEtfQ(etfSearch); }}
                      placeholder="ETF ara..."
                      className="pl-5 pr-2 h-6 text-xs bg-neutral-100 border-0 rounded-full focus:ring-1 focus:ring-amber-400 focus:bg-white w-28"
                    />
                  </div>
                  <div className="w-px h-4 bg-neutral-200 shrink-0 mx-0.5" />
                  <div className="flex items-center gap-0.5 shrink-0">
                    <span className="text-[10px] text-neutral-400 hidden sm:inline">Sırala:</span>
                    {([
                      { k: "aum" as EtfSortKey, label: "AUM" },
                      { k: "daily_change" as EtfSortKey, label: "Günlük" },
                      { k: "ytd" as EtfSortKey, label: "YTD (₺)" },
                      { k: "expense_ratio" as EtfSortKey, label: "Gider" },
                    ]).map(({ k, label }) => (
                      <button
                        key={k}
                        onClick={() => toggleEtfSort(k)}
                        className={`flex items-center gap-0.5 px-1.5 py-0.5 rounded text-[10px] transition whitespace-nowrap ${
                          etfSortKey === k ? "bg-amber-500 text-white" : "bg-neutral-100 text-neutral-500 hover:bg-amber-100"
                        }`}
                      >
                        {label}
                        {etfSortKey === k && (etfSortDir === "asc" ? <ArrowUp className="w-2 h-2" /> : <ArrowDown className="w-2 h-2" />)}
                      </button>
                    ))}
                  </div>
                </div>
                {/* ETF grid */}
                <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 xl:grid-cols-4 gap-2 p-3">
                  {etfPaginated.length === 0 ? (
                    <div className="col-span-full text-center py-12 text-neutral-400 text-sm">Sonuç bulunamadı</div>
                  ) : etfPaginated.map((etf) => {
                    const assetColor = etf.asset_type
                      ? ({ EQUITY: "bg-blue-100 text-blue-700", BOND: "bg-green-100 text-green-700", COMMODITY: "bg-amber-100 text-amber-700", REAL_ESTATE: "bg-purple-100 text-purple-700", MONEY_MARKET: "bg-gray-100 text-gray-700" }[etf.asset_type] || "bg-neutral-100 text-neutral-600")
                      : "bg-neutral-100 text-neutral-600";
                    return (
                      <Link key={etf.symbol} href={`/etf/${etf.symbol}`} className="group block">
                        <Card className="h-full transition-all duration-150 hover:shadow-md hover:-translate-y-0.5 cursor-pointer">
                          <CardContent className="p-2.5 flex flex-col h-full gap-1">
                            <div className="flex items-start justify-between gap-1">
                              <div className="min-w-0 flex-1">
                                <div className="flex items-center gap-1 flex-wrap">
                                  <span className="font-mono font-bold text-amber-600 text-[10px] group-hover:underline">{etf.symbol}</span>
                                  {etf.asset_type && <span className={`text-[9px] px-1 py-0.5 rounded-full font-medium ${assetColor}`}>{etf.asset_type}</span>}
                                </div>
                                <div className="text-[10px] text-neutral-600 font-medium line-clamp-2 leading-tight mt-0.5">{etf.name}</div>
                              </div>
                              <div className={`shrink-0 px-1.5 py-0.5 rounded text-[10px] font-semibold ${(etf.change_pct ?? 0) >= 0 ? "bg-emerald-100 text-emerald-700" : "bg-red-100 text-red-700"}`}>
                                {(etf.change_pct ?? 0) >= 0 ? "+" : ""}{((etf.change_pct ?? 0) * 100).toFixed(2)}%
                              </div>
                            </div>
                            <div className="flex items-end justify-between pt-1 border-t border-neutral-100">
                              <div>
                                <div className="text-sm font-black text-neutral-900 font-mono tracking-tight">
                                  {etf.currency === "GBp" ? `£${((etf.price ?? 0)/100).toFixed(2)}` : `$${(etf.price ?? 0).toFixed(2)}`}
                                </div>
                                {etf.currency && etf.currency !== "USD" && <div className="text-[9px] text-neutral-400">{etf.currency}</div>}
                              </div>
                              <div className="text-right">
                                <div className="text-xs font-semibold text-neutral-700">
                                  {etf.aum ? (etf.aum >= 1e12 ? `$${(etf.aum/1e12).toFixed(1)}T` : etf.aum >= 1e9 ? `$${(etf.aum/1e9).toFixed(1)}B` : `$${(etf.aum/1e6).toFixed(0)}M`) : "—"}
                                </div>
                                <div className="text-[9px] text-neutral-400">AUM</div>
                              </div>
                              {etf.ytd_return_try != null ? (
                                <div className={`text-xs font-semibold font-mono ${etf.ytd_return_try >= 0 ? "text-green-600" : "text-red-600"}`}
                                     title={etf.ytd_return != null ? `USD: ${(etf.ytd_return >= 0 ? "+" : "") + (etf.ytd_return * 100).toFixed(1)}%` : ""}>
                                  {(etf.ytd_return_try >= 0 ? "+" : "")}{(etf.ytd_return_try * 100).toFixed(1)}%
                                  <span className="text-[9px] font-normal ml-0.5 text-neutral-400">₺</span>
                                </div>
                              ) : etf.ytd_return != null ? (
                                <div className={`text-xs font-semibold font-mono ${etf.ytd_return >= 0 ? "text-green-600" : "text-red-600"}`}>
                                  {(etf.ytd_return >= 0 ? "+" : "")}{(etf.ytd_return * 100).toFixed(1)}%
                                </div>
                              ) : null}
                            </div>
                            <div className="flex items-center gap-2 flex-wrap">
                              {etf.expense_ratio != null && <span className="text-[9px] text-neutral-400">Gider: <span className="font-medium text-neutral-600">{(etf.expense_ratio * 100).toFixed(2)}%</span></span>}
                              {etf.dividend_yield != null && <span className="text-[9px] text-neutral-400">Div: <span className="font-medium text-neutral-600">{(etf.dividend_yield * 100).toFixed(2)}%</span></span>}
                            </div>
                          </CardContent>
                        </Card>
                      </Link>
                    );
                  })}
                </div>
                {etfTotalPages > 1 && (
                  <div className="flex items-center justify-center gap-1 py-2 border-t border-neutral-100">
                    <Button variant="ghost" size="sm" className="h-7 text-xs" onClick={() => setEtfPage(p => Math.max(1, p - 1))} disabled={etfPage === 1}>←</Button>
                    <span className="text-xs text-neutral-500 px-2">{etfPage} / {etfTotalPages}</span>
                    <Button variant="ghost" size="sm" className="h-7 text-xs" onClick={() => setEtfPage(p => Math.min(etfTotalPages, p + 1))} disabled={etfPage === etfTotalPages}>→</Button>
                  </div>
                )}
                <div className="text-center text-[10px] text-neutral-400 py-1.5 border-t border-neutral-100">
                  {etfFiltered.length > ETF_PAGE_SIZE ? `${(etfPage - 1) * ETF_PAGE_SIZE + 1}–${Math.min(etfPage * ETF_PAGE_SIZE, etfFiltered.length)} / ${etfFiltered.length}` : `${etfFiltered.length} ETF`}
                </div>
              </>
            )}
          </div>
        </div>
      </main>

      <footer className="border-t border-neutral-200 mt-12 py-4 bg-white">
        <div className="max-w-7xl mx-auto px-4 flex flex-wrap items-center justify-center gap-x-6 gap-y-1 text-xs text-neutral-400">
          <span>FonRapor — Tefas + KAP verileri</span>
          <span>{data?.stats?.total || 0} fon</span>
          <span>{fmtMoney(data?.stats?.total_market_cap || 0)} ₺ AUM</span>
          <span>ort. {((data?.stats?.avg_daily_change ?? 0) >= 0 ? "+" : "")}{data?.stats?.avg_daily_change?.toFixed(2) || "—"}%</span>
          <span>Veri: {data?.stats?.latest_date ? new Date(data?.stats.latest_date + "T00:00:00").toLocaleDateString("tr-TR", { day: "2-digit", month: "2-digit", year: "2-digit" }) : "—"}</span>
          <span>{data?.stats?.trading_days || 0} işlem günü</span>
        </div>
      </footer>
    </div>
  );
}
