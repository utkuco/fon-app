"use client";

import { useState, useMemo } from "react";
import Link from "next/link";
import { Search } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Logo } from "@/components/Logo";
import { Badge } from "@/components/ui/badge";
import { ETF_CATEGORIES, filterEtfsByCategory } from "@/lib/etf-categories";

type Sparkline = { points: [number, number][]; positive: boolean };

interface Etf {
  symbol: string;
  name: string;
  category: string | null;
  fund_family: string | null;
  region: string | null;
  asset_type: string | null;
  currency: string | null;
  nav_price: number | null;
  price: number | null;
  price_try: number | null;
  change_pct: number | null;
  expense_ratio: number | null;
  dividend_yield: number | null;
  aum: number | null;
  ytd_return: number | null;
  ytd_return_try: number | null;
  one_month_return_try: number | null;
  three_month_return_try: number | null;
  six_month_return_try: number | null;
  three_yr_return: number | null;
  five_yr_return: number | null;
  beta: number | null;
  updated_at: string | null;
}

function fmtAum(n: number | null): string {
  if (n == null) return "—";
  if (n >= 1e12) return `$${(n / 1e12).toFixed(1)}T`;
  if (n >= 1e9) return `$${(n / 1e9).toFixed(1)}B`;
  if (n >= 1e6) return `$${(n / 1e6).toFixed(0)}M`;
  return `$${n.toLocaleString()}`;
}

function fmtPrice(n: number | null, currency: string | null): string {
  if (n == null) return "—";
  if (currency === "GBp") return `£${(n / 100).toFixed(2)}`;
  return `$${n.toFixed(2)}`;
}

function fmtPct(n: number | null, showSign = false): string {
  if (n == null) return "—";
  const sign = showSign && n > 0 ? "+" : "";
  return `${sign}${n.toFixed(2)}%`;
}

function SparklineSvg({ sparkline, height = 52 }: { sparkline: Sparkline; height?: number }) {
  const W = 280;
  const { points, positive } = sparkline;
  const minX = points[0][0];
  const maxX = points[points.length - 1][0];
  const minY = Math.min(...points.map(p => p[1]));
  const maxY = Math.max(...points.map(p => p[1]));
  const rangeX = maxX - minX || 1;
  const rangeY = maxY - minY || 1;
  const toX = (x: number) => ((x - minX) / rangeX) * W;
  const toY = (y: number) => height - ((y - minY) / rangeY) * height;

  const linePath = points.map((pt, i) =>
    `${i === 0 ? "M" : "L"}${toX(pt[0]).toFixed(1)},${toY(pt[1]).toFixed(1)}`
  ).join(" ");
  const areaPath = `${linePath} L${W},${height} L0,${height} Z`;
  const color = positive ? "#34d399" : "#f87171";

  return (
    <svg width="100%" height={height} viewBox={`0 0 ${W} ${height}`} className="overflow-visible">
      <defs>
        <linearGradient id={`sg-etf-${positive}`} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={color} stopOpacity="0.15" />
          <stop offset="100%" stopColor={color} stopOpacity="0" />
        </linearGradient>
      </defs>
      <path d={areaPath} fill={`url(#sg-etf-${positive})`} />
      <path d={linePath} fill="none" stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function ChangeBadge({ value }: { value: number | null }) {
  if (value == null) return null;
  const isPos = value >= 0;
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-bold shrink-0 ${
      isPos ? "bg-emerald-50 text-emerald-700 border border-emerald-200" : "bg-red-50 text-red-700 border border-red-200"
    }`}>
      {isPos ? "+" : ""}{value.toFixed(2)}%
    </span>
  );
}

function EtfCard({ etf, sparkline }: { etf: Etf; sparkline?: Sparkline }) {
  const change = etf.change_pct;
  const isPos = (change ?? 0) >= 0;

  return (
    <Link href={`/etf/${etf.symbol}`} className="group block">
      <div className="bg-white rounded-xl border border-neutral-200 hover:border-blue-300 hover:shadow-md transition-all duration-200 overflow-hidden">

        {/* Top row: symbol + badge + change */}
        <div className="px-3 pt-3 pb-1.5 flex items-start justify-between gap-2">
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-1.5 mb-0.5">
              <span className="text-sm font-bold text-neutral-900 group-hover:text-blue-600 transition-colors leading-tight">
                {etf.symbol}
              </span>
              {etf.fund_family && (
                <span className="text-[10px] text-neutral-400 truncate hidden sm:inline">
                  {etf.fund_family}
                </span>
              )}
            </div>
            <p className="text-[10px] text-neutral-400 leading-tight line-clamp-1" title={etf.name}>
              {etf.name}
            </p>
          </div>
          <div className="flex flex-col items-end gap-1 shrink-0">
            <ChangeBadge value={change} />
            {etf.price != null && (
              <span className="text-xs font-bold text-neutral-900">
                {fmtPrice(etf.price, etf.currency)}
              </span>
            )}
          </div>
        </div>

        {/* Sparkline */}
        <div className="px-1">
          {sparkline ? (
            <SparklineSvg sparkline={sparkline} height={52} />
          ) : (
            <div className={`h-[52px] flex items-center justify-center ${isPos ? "bg-emerald-50" : "bg-red-50"}`}>
              <div className={`w-3 h-3 rounded-full ${isPos ? "bg-emerald-400" : "bg-red-400"}`} />
            </div>
          )}
        </div>

        {/* Bottom row: returns + AUM bar */}
        <div className="px-3 pb-2 pt-1">
          {/* Returns */}
          <div className="flex items-center gap-2 text-[10px] mb-1.5">
            <span className="text-neutral-400 shrink-0">1A</span>
            <span className={`font-semibold ${(etf.one_month_return_try ?? 0) >= 0 ? "text-emerald-600" : "text-red-600"}`}>
              {fmtPct(etf.one_month_return_try, true)}
            </span>
            <span className="text-neutral-300">|</span>
            <span className="text-neutral-400 shrink-0">3A</span>
            <span className={`font-semibold ${(etf.three_yr_return ?? 0) >= 0 ? "text-emerald-600" : "text-red-600"}`}>
              {fmtPct(etf.three_yr_return, true)}
            </span>
            <span className="text-neutral-300">|</span>
            <span className="text-neutral-400 shrink-0">6A</span>
            <span className={`font-semibold ${(etf.six_month_return_try ?? 0) >= 0 ? "text-emerald-600" : "text-red-600"}`}>
              {fmtPct(etf.six_month_return_try, true)}
            </span>
          </div>

          {/* AUM + expense */}
          <div className="flex items-center justify-between text-[10px]">
            <span className="text-neutral-400">
              {fmtAum(etf.aum)}
            </span>
            {etf.expense_ratio != null && (
              <span className="text-neutral-400">
                Gider <span className="font-semibold text-neutral-600">{etf.expense_ratio.toFixed(2)}%</span>
              </span>
            )}
          </div>
        </div>
      </div>
    </Link>
  );
}

export default function EtfPageClient({
  initialEtfs,
  sparklineMap,
  activeCategory,
  activeCategoryLabel,
  totalCount,
}: {
  initialEtfs: Etf[];
  sparklineMap: Record<string, Sparkline>;
  activeCategory?: string;
  activeCategoryLabel?: string;
  totalCount?: number;
}) {
  const [etfs] = useState<Etf[]>(initialEtfs);
  const [search, setSearch] = useState("");
  const [activeTab, setActiveTab] = useState<string>(activeCategory ?? "all");
  const [sortKey, setSortKey] = useState<string>("aum");

  const filtered = useMemo(() => {
    let result = etfs;

    if (activeTab !== "all") {
      result = filterEtfsByCategory(result, activeTab);
    }

    if (search.trim()) {
      const q = search.trim().toLowerCase();
      result = result.filter(
        (e) =>
          e.symbol.toLowerCase().includes(q) ||
          e.name.toLowerCase().includes(q) ||
          (e.category || "").toLowerCase().includes(q) ||
          (e.fund_family || "").toLowerCase().includes(q)
      );
    }

    const sorted = [...result];
    switch (sortKey) {
      case "aum": sorted.sort((a, b) => (b.aum || 0) - (a.aum || 0)); break;
      case "change": sorted.sort((a, b) => (b.change_pct || 0) - (a.change_pct || 0)); break;
      case "ytd": sorted.sort((a, b) => (b.ytd_return || 0) - (a.ytd_return || 0)); break;
      case "name": sorted.sort((a, b) => a.name.localeCompare(b.name)); break;
    }
    return sorted;
  }, [etfs, activeTab, search, sortKey]);

  return (
    <div className="min-h-screen bg-neutral-50">
      {/* Header */}
      <header className="bg-white border-b border-neutral-200 sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-3 sm:px-4 h-16 flex items-center gap-3">
          <Link href="/" className="hover:opacity-70 transition shrink-0">
            <Logo variant="full" className="h-8 w-auto" />
          </Link>
          <div className="h-6 w-px bg-neutral-200 hidden sm:block" />
          <nav className="hidden md:flex items-center gap-1 ml-1">
            <Link href="/" className="px-3 py-1.5 text-sm font-medium text-neutral-600 hover:text-blue-600 hover:bg-blue-50 rounded-lg transition">Fonlar</Link>
            <Link href="/etf" className="px-3 py-1.5 text-sm font-medium text-blue-600 bg-blue-50 rounded-lg">ETF'ler</Link>
            <Link href="/performers" className="px-3 py-1.5 text-sm font-medium text-neutral-600 hover:text-blue-600 hover:bg-blue-50 rounded-lg transition">Performanslar</Link>
            <Link href="/companies" className="px-3 py-1.5 text-sm font-medium text-neutral-600 hover:text-blue-600 hover:bg-blue-50 rounded-lg transition">Şirketler</Link>
          </nav>
          <div className="h-6 w-px bg-neutral-200 hidden sm:block" />
          <Badge variant="secondary" className="text-xs hidden sm:inline-flex">
            {filtered.length} ETF{activeCategoryLabel ? ` · ${activeCategoryLabel}` : ""}
          </Badge>
          <div className="relative flex-1 min-w-0 max-w-xs sm:max-w-sm ml-auto">
            <Search className="absolute left-2 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-neutral-400 pointer-events-none" />
            <Input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="ETF ara..."
              className="pl-7 pr-3 h-8 text-sm bg-neutral-100 border-transparent focus:bg-white focus:border-blue-300"
            />
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-3 sm:px-4 py-4">
        {/* Category tabs */}
        <div className="flex flex-wrap items-center gap-2 mb-4">
          <Link
            href="/etf"
            onClick={() => setActiveTab("all")}
            className={`px-3 py-1.5 rounded-full text-xs font-semibold transition ${
              activeTab === "all"
                ? "bg-blue-600 text-white"
                : "bg-white border border-neutral-200 text-neutral-600 hover:border-blue-300 hover:text-blue-600"
            }`}
          >
            Tümü
          </Link>
          {ETF_CATEGORIES.map((cat) => (
            <Link
              key={cat.key}
              href={`/etf/${cat.key}`}
              onClick={() => setActiveTab(cat.key)}
              className={`px-3 py-1.5 rounded-full text-xs font-semibold transition ${
                activeTab === cat.key
                  ? "bg-blue-600 text-white"
                  : "bg-white border border-neutral-200 text-neutral-600 hover:border-blue-300 hover:text-blue-600"
              }`}
            >
              {cat.label}
            </Link>
          ))}
          <div className="h-4 w-px bg-neutral-200 mx-1 hidden sm:block" />
          <select
            value={sortKey}
            onChange={(e) => setSortKey(e.target.value)}
            className="appearance-none pl-3 pr-7 py-1.5 text-xs font-medium bg-white border border-neutral-200 rounded-lg text-neutral-700 hover:border-blue-300 focus:outline-none focus:border-blue-400 cursor-pointer"
          >
            <option value="aum">AUM</option>
            <option value="change">Günlük</option>
            <option value="ytd">YTD</option>
            <option value="name">İsim</option>
          </select>
        </div>

        {/* Grid */}
        {filtered.length === 0 ? (
          <div className="text-center py-16 text-neutral-400">
            <p className="text-lg">Sonuç bulunamadı</p>
          </div>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-3">
            {filtered.map((etf) => (
              <EtfCard
                key={etf.symbol}
                etf={etf}
                sparkline={sparklineMap[etf.symbol]}
              />
            ))}
          </div>
        )}
      </main>
    </div>
  );
}
