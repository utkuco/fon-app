"use client";

import { useState, useMemo } from "react";
import Link from "next/link";
import { Card, CardContent } from "@/components/ui/card";
import { TrendingUp, TrendingDown, Star, PieChart } from "lucide-react";
import { StockLogo } from "@/components/StockLogo";

interface TopFund {
  code: string;
  name: string;
  change: number;
  market_cap?: number | null;
}

interface TopEtf {
  symbol: string;
  name: string;
  change_pct: number;
  aum?: number | null;
}

interface MostInvested {
  code: string;
  name: string;
  market_cap?: number | null;
  daily_change?: number | null;
}

interface MostHeldStock {
  ticker: string;
  company: string;
  total_weight: number;
  fund_count: number;
}

interface CategoryStats {
  [key: string]: { count: number; total_market_cap: number };
}

interface CategoryChange {
  [key: string]: { change_pct: number; count: number };
}

interface FundData {
  code: string;
  name: string;
  daily_change: number | null;
  weekly: number | null;
  monthly: number | null;
  quarterly: number | null;
  fund_type?: string | null;
  market_cap?: number;
  price?: number;
}

interface FunListsProps {
  top5Gainers?: TopFund[];
  top5Losers?: TopFund[];
  etfTopGainers?: Array<{ symbol: string; name: string; change_pct: number; aum: number | null; ret_1m: number; ret_3m: number; ret_6m: number }>;
  etfTopLosers?: TopEtf[];
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
  mostInvested?: MostInvested[];
  mostHeldStocks?: MostHeldStock[];
  categoryStats?: CategoryStats;
  categoryChange?: CategoryChange;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  funds?: any[];
  benchmarks?: Record<string, Array<{ date: string; price: number }>>;
}

const TYPE_LABELS: Record<string, string> = {
  "TYPE-A": "Hisse",
  "TYPE-B": "Borçlanma",
  "TYPE-C": "Para Piyasası",
  "TYPE-D": "Katılım",
  "TYPE-E": "Gümüş",
  "TYPE-F": "Altın",
  "TYPE-G": "Gayrimenkul",
  "TYPE-H": "Özel",
};

// Accent: [badge-bg, badge-text, change-text]
const ACCENT: Record<string, [string, string, string]> = {
  green:  ["bg-green-50",   "text-green-700", "text-green-600"],
  red:    ["bg-red-50",     "text-red-700",   "text-red-600"],
  blue:   ["bg-blue-50",    "text-blue-700",  "text-blue-600"],
  purple: ["bg-purple-50",  "text-purple-700","text-purple-600"],
  amber:  ["bg-amber-50",   "text-amber-700", "text-amber-600"],
};

// ─── Section wrapper ───
function SectionWrap({
  icon, title, subtitle, children,
}: {
  icon: React.ReactNode;
  title: string;
  subtitle?: string;
  children: React.ReactNode;
}) {
  return (
    <div className="bg-white rounded-xl shadow-sm px-4 py-3.5">
      <div className="flex items-center gap-2 mb-3">
        <span className="text-neutral-400">{icon}</span>
        <div>
          <div className="text-sm font-bold text-neutral-900">{title}</div>
          {subtitle && <div className="text-xs text-neutral-400">{subtitle}</div>}
        </div>
      </div>
      <div className="flex gap-2.5 overflow-x-auto no-scrollbar pb-1">
        {children}
      </div>
    </div>
  );
}

// ─── MiniCard ───
function MiniCard({
  code, name, change, metric, metricLabel, href, accent = "blue",
}: {
  code: string; name: string; change?: number | null; metric?: string;
  metricLabel?: string; href?: string; accent?: "green" | "red" | "blue" | "purple" | "amber";
}) {
  const [badgeBg, badgeText, changeColor] = ACCENT[accent];

  const inner = (
    <div className="w-52 min-w-[208px] rounded-xl border border-neutral-200 bg-white p-3 flex flex-col gap-1.5 hover:shadow-md hover:-translate-y-0.5 transition-all duration-200 cursor-pointer">
      <div className="flex items-center gap-1.5">
        <span className={`${badgeBg} ${badgeText} text-[10px] font-bold px-1.5 py-0.5 rounded-md font-mono`}>
          {code}
        </span>
        {change != null && (
          <span className={`text-xs font-bold font-mono ml-auto ${changeColor}`}>
            {change >= 0 ? "+" : ""}{change.toFixed(2)}%
          </span>
        )}
      </div>
      <div className="text-[11px] font-medium text-neutral-600 leading-snug line-clamp-2 break-words">
        {name}
      </div>
      {metric && (
        <div className="flex items-baseline gap-1 mt-auto pt-1">
          <span className="text-sm font-semibold text-neutral-900">{metric}</span>
          {metricLabel && <span className="text-[10px] text-neutral-400">{metricLabel}</span>}
        </div>
      )}
    </div>
  );

  if (href) return <Link href={href} className="shrink-0">{inner}</Link>;
  return <div className="shrink-0">{inner}</div>;
}

// ─── StockCard ───
function StockCard({
  ticker, company, totalWeight, fundCount,
}: {
  ticker: string; company: string; totalWeight: number; fundCount: number;
}) {
  const [badgeBg, badgeText] = ACCENT.purple;

  return (
    <div className="w-52 min-w-[208px] rounded-xl border border-neutral-200 bg-white p-3 flex flex-col gap-1.5 hover:shadow-md hover:-translate-y-0.5 transition-all duration-200 cursor-pointer">
      <div className="flex items-center gap-1.5">
        <StockLogo ticker={ticker} company={company} size={20} />
        <span className={`${badgeBg} ${badgeText} text-[10px] font-mono font-bold px-1.5 py-0.5 rounded-md`}>
          {ticker.replace(".E", "")}
        </span>
        <span className={`ml-auto ${badgeBg} ${badgeText} text-[10px] font-semibold px-1.5 py-0.5 rounded-md`}>
          {fundCount} fon
        </span>
      </div>
      <div className="text-[11px] font-medium text-neutral-600 leading-snug line-clamp-2 break-words">
        {company}
      </div>
      <div className="flex items-baseline gap-1 mt-auto pt-1">
        <span className="text-sm font-bold text-neutral-800">{totalWeight.toFixed(1)}%</span>
        <span className="text-[10px] text-neutral-400">ağırlık</span>
      </div>
    </div>
  );
}

// ─── ChampionCard ───
function ChampionCard({
  code, fundName, category, change, fundCount, href, accent = "amber",
}: {
  code: string; fundName: string; category: string;
  change?: number | null; fundCount?: number; href?: string;
  accent?: "green" | "red" | "blue" | "purple" | "amber";
}) {
  const [badgeBg, badgeText, changeColor] = ACCENT[accent];

  const inner = (
    <div className="w-52 min-w-[208px] rounded-xl border border-neutral-200 bg-white p-3 flex flex-col gap-1.5 hover:shadow-md hover:-translate-y-0.5 transition-all duration-200 cursor-pointer">
      <div className={`self-start ${badgeBg} ${badgeText} text-[10px] font-semibold px-2 py-0.5 rounded-full flex items-center gap-1`}>
        <Star className="w-3 h-3" />
        {category}
      </div>
      <div className="flex items-center gap-1.5">
        <span className="text-[11px] font-mono font-bold text-blue-600">{code}</span>
        {change != null && (
          <span className={`text-sm font-bold font-mono ml-auto ${changeColor}`}>
            {change >= 0 ? "+" : ""}{change.toFixed(2)}%
          </span>
        )}
      </div>
      <div className="text-[12px] font-medium text-neutral-700 leading-snug line-clamp-2 min-h-[2rem]">
        {fundName}
      </div>
      {fundCount != null && (
        <span className="text-xs text-neutral-400 mt-auto pt-1.5">{fundCount} fon</span>
      )}
    </div>
  );

  if (href) return <Link href={href} className="shrink-0">{inner}</Link>;
  return <div className="shrink-0">{inner}</div>;
}

// ─── BenchmarksSection ───
function BenchmarksSection({
  benchmarks,
}: {
  benchmarks?: Record<string, Array<{ date: string; price: number }>>;
}) {
  if (!benchmarks || Object.keys(benchmarks).length === 0) return null;

  const BENCHMARK_META: Record<string, { label: string; color: string }> = {
    BIST100: { label: "BIST 100",  color: "text-red-600" },
    SP500:   { label: "S&P 500",  color: "text-blue-600" },
    NASDAQ:  { label: "Nasdaq",   color: "text-indigo-600" },
    USDTRY:  { label: "USD/TRY",  color: "text-slate-600" },
    GOLD:    { label: "Altın",     color: "text-amber-500" },
    BTCUSD:  { label: "Bitcoin",   color: "text-orange-500" },
    ETHUSD:  { label: "Ethereum",  color: "text-purple-500" },
  };

  // Dynamic base date: always "today - 1 year"
  const oneYearAgo = new Date();
  oneYearAgo.setFullYear(oneYearAgo.getFullYear() - 1);
  const months = ["Oca","Şub","Mar","Nis","May","Haz","Tem","Ağu","Eyl","Eki","Kas","Ara"];
  const baseDateStr = `${oneYearAgo.getDate()} ${months[oneYearAgo.getMonth()]} ${oneYearAgo.getFullYear()}`;

  const items = Object.entries(benchmarks)
    .filter(([sym]) => BENCHMARK_META[sym])
    .map(([sym, data]) => {
      const sorted = [...data].sort((a, b) => a.date.localeCompare(b.date));
      if (sorted.length < 2) return null;
      const base = sorted[0].price;
      const current = sorted[sorted.length - 1].price;
      const pct = ((current - base) / base) * 100;
      const isPositive = pct >= 0;
      return { symbol: sym, meta: BENCHMARK_META[sym], base, current, pct, isPositive, sorted };
    })
    .filter(Boolean) as Array<{ symbol: string; meta: typeof BENCHMARK_META[string]; base: number; current: number; pct: number; isPositive: boolean; sorted: Array<{ date: string; price: number }> }>;

  if (items.length === 0) return null;

  return (
    <div className="bg-white rounded-xl shadow-sm px-4 py-3.5">
      <div className="flex items-center gap-2 mb-3">
        <span className="text-neutral-400">
          <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3.055 11H5a2 2 0 012 2v1a2 2 0 002 2 2 2 0 012 2v2.945M8 3.935V5.5A2.5 2.5 0 0010.5 8h.5a2 2 0 012 2 2 2 0 104 0 2 2 0 012-2h1.064M15 20.488V18a2 2 0 012-2h3.064" />
          </svg>
        </span>
        <div>
          <div className="text-sm font-bold text-neutral-900">Piyasa Göstergeleri</div>
          <div className="text-xs text-neutral-400">BIST 100, S&P 500, Nasdaq, Altın, Bitcoin, Ethereum — son 1 yılda base=100</div>
        </div>
      </div>
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        {items.map(({ symbol, meta, pct, isPositive }) => {
          const barColor = isPositive ? "bg-green-400" : "bg-red-400";
          const textColor = isPositive ? "text-green-600" : "text-red-600";
          const barBgColor = isPositive ? "bg-green-50" : "bg-red-50";
          const absPct = Math.abs(pct);
          const barWidth = Math.min(100, (absPct / 20) * 100); // 20% = full bar

          return (
            <div key={symbol} className={`rounded-xl border border-neutral-100 ${barBgColor} p-3 flex flex-col gap-1.5`}>
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold text-neutral-600">{meta.label}</span>
                <span className={`text-sm font-black font-mono ${textColor}`}>
                  {isPositive ? "+" : ""}{pct.toFixed(1)}%
                </span>
              </div>
              <div className={`h-1.5 rounded-full bg-white overflow-hidden`}>
                <div className={`h-full rounded-full ${barColor}`} style={{ width: `${barWidth}%` }} />
              </div>
              <div className="text-[10px] text-neutral-400 leading-tight">
                {symbol === "BIST100" ? "BIST 100 endeksi" :
                 symbol === "BTCUSD" ? "Bitcoin/USD" :
                 symbol === "ETHUSD" ? "Ethereum/USD" :
                 symbol === "USDTRY" ? "Dolar/TL kuru" :
                 symbol === "SP500" ? "S&P 500 endeksi" :
                 symbol === "NASDAQ" ? "Nasdaq bileşik" :
                 "Altın fiyatı"}
              </div>
            </div>
          );
        })}
      </div>
      <div className="mt-2 text-[10px] text-neutral-300">
        Base = 100 ({baseDateStr}). Referans: son 1 yıllık değişim.
      </div>
    </div>
  );
}

// ─── EtfMiniCard ───
function EtfMiniCard({
  symbol, name, change_pct, aum, href,
}: {
  symbol: string; name: string; change_pct?: number | null; aum?: number | null; href?: string;
}) {
  const isPos = (change_pct ?? 0) >= 0;
  const [badgeBg, badgeText, changeColor] = isPos ? ACCENT.green : ACCENT.red;

  const fmtAum = (n: number) => {
    if (n >= 1e12) return `$${(n/1e12).toFixed(1)}T`;
    if (n >= 1e9) return `$${(n/1e9).toFixed(1)}B`;
    return `$${(n/1e6).toFixed(0)}M`;
  };

  const inner = (
    <div className="w-52 min-w-[208px] rounded-xl border border-amber-200 bg-white p-3 flex flex-col gap-1.5 hover:shadow-md hover:-translate-y-0.5 transition-all duration-200 cursor-pointer">
      <div className="flex items-center gap-1.5">
        <span className={`${badgeBg} ${badgeText} text-[10px] font-bold px-1.5 py-0.5 rounded-md font-mono`}>
          {symbol}
        </span>
        {change_pct != null && (
          <span className={`text-xs font-bold font-mono ml-auto ${changeColor}`}>
            {isPos ? "+" : ""}{(change_pct * 100).toFixed(2)}%
          </span>
        )}
      </div>
      <div className="text-[11px] font-medium text-neutral-600 leading-snug line-clamp-2 break-words">
        {name}
      </div>
      {aum != null && (
        <div className="flex items-baseline gap-1 mt-auto pt-1">
          <span className="text-sm font-semibold text-neutral-900">{fmtAum(aum)}</span>
          <span className="text-[10px] text-neutral-400">AUM</span>
        </div>
      )}
    </div>
  );

  if (href) return <Link href={href} className="shrink-0">{inner}</Link>;
  return <div className="shrink-0">{inner}</div>;
}

// ─── GainersSection: Karışık FON+ETF sıralı tablo ───
type Period = "1G" | "1H" | "1A" | "3A" | "6A";

const PERIOD_LABELS: Record<Period, string> = {
  "1G": "1G",
  "1H": "1H",
  "1A": "1A",
  "3A": "3A",
  "6A": "6A",
};

type TurkishGainerEntry = {
  code: string;
  name: string;
  market_cap: number;
  ret_1d: number;
  ret_1w: number;
  ret_1m: number;
  ret_3m: number | null;
  ret_6m: number | null;
};

type EtfGainerEntry = {
  symbol: string;
  name: string;
  change_pct: number;
  aum: number | null;
  ret_1m: number;
  ret_3m: number;
  ret_6m: number;
};

function getReturn(entry: TurkishGainerEntry | EtfGainerEntry, period: Period): number | null {
  if ("code" in entry) {
    // Turkish fund
    switch (period) {
      case "1G": return entry.ret_1d;
      case "1H": return entry.ret_1w;
      case "1A": return entry.ret_1m;
      case "3A": return entry.ret_3m;
      case "6A": return entry.ret_6m;
    }
  } else {
    // ETF (returns in TRY)
    switch (period) {
      case "1G": return entry.change_pct;
      case "1H": return entry.change_pct; // 1H ≈ daily
      case "1A": return entry.ret_1m;
      case "3A": return entry.ret_3m;
      case "6A": return entry.ret_6m;
    }
  }
  return null;
}

function GainersSection({
  topTurkish,   // old daily-based top gainers from homepage_stats (for LosersSection compat)
  etfTopGainers, // period-aware ETF gainers (ret_1m/ret_3m/ret_6m)
  turkishGainers, // new period-aware Turkish fund gainers
}: {
  topTurkish: TopFund[];
  etfTopGainers: Array<{ symbol: string; name: string; change_pct: number; aum: number | null; ret_1m: number; ret_3m: number; ret_6m: number }>;
  turkishGainers?: TurkishGainerEntry[];
}) {
  const [tab, setTab] = useState<"all" | "turkish" | "etf">("all");
  const [period, setPeriod] = useState<Period>("1A"); // 1A = best available data for both funds & ETFs

  const allEtfGainers = turkishGainers ? etfTopGainers : [];

  // Build mixed list: FON + ETF together, sorted by selected period return
  const mixedItems = useMemo(() => {
    if (!turkishGainers) {
      // Fallback to old behavior if no period data
      const fundEntries = topTurkish.map((f) => ({
        type: "fund" as const,
        id: f.code,
        code: f.code,
        name: f.name,
        change: f.change,
        href: `/fon/${f.code}`,
      }));
      const etfEntries = etfTopGainers.map((e) => ({
        type: "etf" as const,
        id: e.symbol,
        code: e.symbol,
        name: e.name,
        change: (e.change_pct ?? 0) * 100, // ×100: DB stores decimal (1.77981 = 177.98%), display expects ×100
        href: `/etf/${e.symbol}`,
      }));
      return [...fundEntries, ...etfEntries].sort((a, b) => b.change - a.change);
    }

    const fundEntries = turkishGainers.map((f) => ({
      type: "fund" as const,
      id: f.code,
      code: f.code,
      name: f.name,
      change: getReturn(f, period),
      href: `/fon/${f.code}`,
    }));
    const etfEntries = allEtfGainers.map((e) => ({
      type: "etf" as const,
      id: e.symbol,
      code: e.symbol,
      name: e.name,
      change: getReturn(e, period),
      href: `/etf/${e.symbol}`,
    }));
    return [...fundEntries, ...etfEntries].sort((a, b) => {
      const ra = a.change;
      const rb = b.change;
      if (ra === null && rb === null) return 0;
      if (ra === null) return 1;
      if (rb === null) return -1;
      return rb - ra;
    });
  }, [topTurkish, etfTopGainers, turkishGainers, period, allEtfGainers]);

  const items =
    tab === "turkish"
      ? mixedItems.filter((i) => i.type === "fund")
      : tab === "etf"
      ? mixedItems.filter((i) => i.type === "etf")
      : mixedItems;

  const typeTabs: { key: typeof tab; label: string }[] = [
    { key: "all", label: `Karışık (${mixedItems.length})` },
    { key: "turkish", label: `Türk Fon` },
    { key: "etf", label: `Yabancı ETF` },
  ];

  return (
    <div className="bg-white rounded-xl shadow-sm px-4 py-3.5">
      {/* Header */}
      <div className="flex items-center gap-2 mb-3 flex-wrap">
        <span className="text-neutral-400"><TrendingUp className="w-3.5 h-3.5" /></span>
        <span className="text-sm font-bold text-neutral-900">En Çok Kazandıranlar</span>

        {/* Period picker */}
        <div className="ml-auto flex gap-0.5 bg-neutral-100 rounded-lg p-0.5">
          {(Object.keys(PERIOD_LABELS) as Period[]).map((p) => (
            <button
              key={p}
              onClick={() => setPeriod(p)}
              className={`px-2 py-0.5 rounded-md text-[11px] font-medium transition ${
                period === p
                  ? "bg-white text-blue-700 shadow-sm"
                  : "text-neutral-500 hover:text-neutral-700"
              }`}
            >
              {PERIOD_LABELS[p]}
            </button>
          ))}
        </div>

        {/* Type filter */}
        <div className="flex gap-1 bg-neutral-100 rounded-lg p-0.5">
          {typeTabs.map((t) => (
            <button
              key={t.key}
              onClick={() => setTab(t.key)}
              className={`px-2 py-0.5 rounded-md text-[11px] font-medium transition ${
                tab === t.key
                  ? "bg-white text-blue-700 shadow-sm"
                  : "text-neutral-500 hover:text-neutral-700"
              }`}
            >
              {t.label}
            </button>
          ))}
        </div>
      </div>

      {/* Column headers */}
      <div className="flex items-center gap-2 px-1 py-1 border-b border-neutral-100 text-[10px] font-semibold text-neutral-400 uppercase tracking-wide">
        <span className="w-6 text-center">#</span>
        <span className="w-10">Tür</span>
        <span className="flex-1">Varlık</span>
        <span className="w-16 text-right">{PERIOD_LABELS[period]}</span>
      </div>

      {/* Rows */}
      <div className="divide-y divide-neutral-50">
        {items.length === 0 ? (
          <div className="text-sm text-neutral-400 py-6 text-center">Veri yok</div>
        ) : (
          items.slice(0, 12).map((item, i) => {
            const isEtf = item.type === "etf";
            const isPos = item.change !== null ? item.change >= 0 : null;
            const changeColor = isPos === null ? "text-neutral-300" : isPos ? "text-green-600" : "text-red-600";
            const badgeClass = isEtf
              ? "bg-amber-50 text-amber-700"
              : "bg-blue-50 text-blue-700";

            return (
              <Link
                key={item.id}
                href={item.href}
                className="flex items-center gap-2 px-1 py-2 hover:bg-neutral-50 transition rounded"
              >
                {/* Rank */}
                <span className="w-6 text-center text-xs font-bold text-neutral-400">{i + 1}</span>

                {/* Type badge */}
                <span className={`w-10 text-[10px] font-bold px-1 py-0.5 rounded text-center ${badgeClass}`}>
                  {isEtf ? "ETF" : "FON"}
                </span>

                {/* Name + code */}
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-1.5">
                    <span className={`text-xs font-bold font-mono ${isEtf ? "text-amber-700" : "text-blue-700"}`}>
                      {item.code}
                    </span>
                    <span className="text-xs text-neutral-500 truncate">{item.name}</span>
                    {isEtf && <span className="text-[9px] text-neutral-400">(<span className="text-amber-500">TL</span>)</span>}
                  </div>
                </div>

                {/* Selected period return */}
                <span className={`w-16 text-right text-xs font-bold font-mono ${item.change === null ? "text-neutral-300" : changeColor}`}>
                  {item.change === null ? "—" : `${item.change >= 0 ? "+" : ""}${item.change.toFixed(2)}%`}
                </span>
              </Link>
            );
          })
        )}
      </div>

      {/* Footer */}
      {items.length > 12 && (
        <div className="mt-2 pt-2 border-t border-neutral-100 text-center">
          <Link
            href="/performers"
            className="text-xs text-blue-600 hover:text-blue-700 font-medium"
          >
            Tümünü gör →
          </Link>
        </div>
      )}
    </div>
  );
}
export function FunLists({
  top5Gainers, top5Losers, etfTopGainers, etfTopLosers, turkishGainers,
  mostHeldStocks,
  categoryStats, categoryChange, funds = [], benchmarks,
}: FunListsProps) {
  return (
    <div className="max-w-7xl mx-auto px-3 sm:px-4 space-y-2">

      {/* Benchmarks */}
      <BenchmarksSection benchmarks={benchmarks} />

      {/* ── Birleşik Kazandıranlar Section — Tümü/Türk/Yabancı ETF alt-tab'ı ── */}
      {(top5Gainers && top5Gainers.length > 0) && (etfTopGainers && etfTopGainers.length > 0) && (
        <GainersSection
          topTurkish={top5Gainers}
          etfTopGainers={etfTopGainers}
          turkishGainers={turkishGainers}
        />
      )}

      {/* Fallback: sadece Türk fon varsa eski gösterim */}
      {(top5Gainers && top5Gainers.length > 0) && !(etfTopGainers && etfTopGainers.length > 0) && (
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
          <SectionWrap icon={<TrendingUp className="w-3.5 h-3.5" />} title="En Çok Yükselenler" subtitle="Bugünün şampiyonları">
            {top5Gainers.map((f) => (
              <MiniCard key={f.code} code={f.code} name={f.name} change={f.change} href={`/fon/${f.code}`} accent="green" />
            ))}
          </SectionWrap>
          {top5Losers && top5Losers.length > 0 && (
            <SectionWrap icon={<TrendingDown className="w-3.5 h-3.5" />} title="En Çok Düşenler" subtitle="Bugünün kaybedenleri">
              {top5Losers.map((f) => (
                <MiniCard key={f.code} code={f.code} name={f.name} change={f.change} href={`/fon/${f.code}`} accent="red" />
              ))}
            </SectionWrap>
          )}
        </div>
      )}

      {/* Sektör Favorileri — kompakt horizontal scroll row */}
      {mostHeldStocks && mostHeldStocks.length > 0 && (
        <SectionWrap icon={<PieChart className="w-3.5 h-3.5" />} title="Sektör Favorileri" subtitle="En çok tutulan hisseler">
          {mostHeldStocks.slice(0, 8).map((s) => (
            <StockCard key={s.ticker} ticker={s.ticker} company={s.company} totalWeight={s.total_weight} fundCount={s.fund_count} />
          ))}
        </SectionWrap>
      )}
    </div>
  );
}
