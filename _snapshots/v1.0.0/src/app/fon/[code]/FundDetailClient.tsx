"use client";

import { useState, useMemo } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import {
  TrendingUp, TrendingDown, ArrowLeft, PieChart,
  Users, Share2, Banknote, BarChart2, Heart,
  Percent, Clock, Receipt
} from "lucide-react";
import FundChart from "@/components/FundChart";
import ReturnsTable from "@/components/ReturnsTable";
import CategoryRankCard from "@/components/CategoryRankCard";
import RiskMetrics from "@/components/RiskMetrics";
import InvestorTrendCard from "@/components/InvestorTrendCard";
import CategoryCompareCard from "@/components/CategoryCompareCard";
import SharpeRatioCard from "@/components/SharpeRatioCard";
import BenchmarkCompareCard from "@/components/BenchmarkCompareCard";
import BetaAlphaCard from "@/components/BetaAlphaCard";
import { Logo } from "@/components/Logo";
import { StockLogo } from "@/components/StockLogo";
import { CompanyLogo } from "@/components/CompanyLogo";
import { useFavorites } from "@/hooks/useFavorites";
import { TYPE_LABELS, ASSET_LABELS, ASSET_COLORS } from "@/lib/shared-config";

function fmtNum(n: number | null | undefined, decimals = 0): string {
  if (n == null) return "—";
  return n.toLocaleString("tr-TR", { maximumFractionDigits: decimals });
}

function fmtMoney(n: number | null | undefined): string {
  if (n == null) return "—";
  if (n >= 1e9) return `${(n / 1e9).toFixed(2)}B TL`;
  if (n >= 1e6) return `${(n / 1e6).toFixed(1)}M TL`;
  if (n >= 1e3) return `${(n / 1e3).toFixed(0)}K TL`;
  return `${n.toLocaleString("tr-TR")} TL`;
}

function fmtDate(s: string | null | undefined): string {
  if (!s) return "—";
  return s.split(" ")[0];
}

function ChangeDisplay({ value }: { value: number | null }) {
  if (value == null) return null;
  const positive = value >= 0;
  return (
    <span className={`inline-flex items-center gap-1 text-sm font-bold ${positive ? "text-green-600" : "text-red-600"}`}>
      {positive ? <TrendingUp className="w-4 h-4" /> : <TrendingDown className="w-4 h-4" />}
      {positive ? "+" : ""}{fmtNum(value, 3)}%
    </span>
  );
}

function StatCard({ label, value, icon: Icon }: { label: string; value: string; icon: any }) {
  return (
    <div className="flex items-center gap-2 px-2.5 py-2 rounded-lg bg-neutral-50 hover:bg-blue-50 border border-transparent transition-all cursor-default">
      <div className="w-7 h-7 rounded-md bg-white border border-neutral-200 flex items-center justify-center shrink-0">
        <Icon className="w-3.5 h-3.5 text-blue-600" />
      </div>
      <div>
        <div className="text-[10px] text-neutral-400 leading-tight">{label}</div>
        <div className="font-bold text-neutral-900 text-xs leading-tight">{value}</div>
      </div>
    </div>
  );
}

function BreakdownChart({ breakdown }: { breakdown: Record<string, number> | null }) {
  if (!breakdown || Object.keys(breakdown).length === 0) {
    return (
      <Card>
        <CardContent className="p-6 text-center text-neutral-400">
          <PieChart className="w-8 h-8 mx-auto mb-2 opacity-30" />
          <div className="text-sm">Portföy dağılımı verisi yok</div>
        </CardContent>
      </Card>
    );
  }

  const entries = Object.entries(breakdown)
    .filter(([, v]) => v > 0)
    .sort(([, a], [, b]) => b - a);

  const total = entries.reduce((sum, [, v]) => sum + v, 0);

  return (
    <Card>
      <CardContent className="p-4">
        <h3 className="text-sm font-semibold text-neutral-700 mb-3 flex items-center gap-2">
          <PieChart className="w-4 h-4" />
          Portföy Dağılımı
        </h3>
        <div className="flex flex-col gap-2">
          {entries.map(([key, value]) => (
            <div key={key} className="flex items-center gap-2">
              <div className="w-36 text-xs text-neutral-600 truncate flex-shrink-0">
                {ASSET_LABELS[key] || key}
              </div>
              <div className="flex-1 bg-neutral-100 rounded-full h-5 overflow-hidden">
                <div
                  className={`h-full rounded-full ${ASSET_COLORS[key] || "bg-gray-400"}`}
                  style={{ width: `${Math.min(value, 100)}%`, minWidth: value > 1 ? "4px" : "2px" }}
                />
              </div>
              <div className="w-12 text-xs font-mono text-right text-neutral-600">
                {fmtNum(value, 1)}%
              </div>
            </div>
          ))}
        </div>
        <div className="mt-3 pt-3 border-t border-neutral-100 flex items-center justify-between">
          <span className="text-xs text-neutral-400">
            Toplam: <span className="font-mono font-medium text-neutral-600">{fmtNum(total, 1)}%</span>
          </span>
          {Math.abs(total - 100) > 0.5 && (
            <span className="text-xs px-2 py-1 rounded-full bg-amber-50 border border-amber-200 text-amber-700 font-medium">
              ⚠ {fmtNum(100 - total, 1)}% bilinmiyor (tüm portföy verileri yok)
            </span>
          )}
        </div>
      </CardContent>
    </Card>
  );
}

interface Holding {
  ticker: string;
  isin: string;
  company: string;
  total_value: string;
  weight_pct: string;
  type: string;
}

interface FundData {
  code: string;
  name: string;
  company: string | null;
  company_logo: string;
  fund_type: string | null;
  manager: string | null;
  tefas_code: string;
  report_date: string;
  nav: number | null;
  price: number | null;
  price_date: string;
  market_cap: number | null;
  number_of_investors: number | null;
  number_of_shares: number | null;
  daily_change: number | null;
  holdings: Holding[];
  holding_count: number;
  breakdown: Record<string, number> | null;
  has_gemini: boolean;
  price_history: Array<{ date: string; price: number; change: number; investors?: number | null; shares?: number | null; market_cap?: number | null }>;
  returns: Record<string, number>;
  rank: number | null;
  // Fee & valour fields
  management_fee: number | null;
  max_total_expense_ratio: number | null;
  purchase_valor: number | null;
  sale_valor: number | null;
}

interface BenchmarkData {
  [key: string]: Array<{ date: string; price: number }>;
}

interface FundDetailProps {
  initialFund: any;
  initialBenchmarks: any[];
  categoryHistoryMap?: any;
  categoryStats?: Record<string, { avg_change: number; count: number }>;
  fundRank?: { rank: number; category_count: number; percentile: number } | null;
}

export default function FundDetailClient({ initialFund, initialBenchmarks, categoryHistoryMap, categoryStats, fundRank }: FundDetailProps) {
  const params = useParams();
  const code = (params.code as string)?.toUpperCase() || "";
  const [fund] = useState<FundData | null>(initialFund);
  const [benchmarks] = useState<Array<{ symbol: string; date: string; price: number }> | undefined>(initialBenchmarks);

  // Convert Supabase array format to component object format
  const benchMap: BenchmarkData | undefined = useMemo(() => {
    if (!benchmarks || !Array.isArray(benchmarks)) return undefined;
    const map: BenchmarkData = {};
    for (const row of benchmarks) {
      const sym = (row.symbol as string).toUpperCase();
      if (!map[sym]) map[sym] = [];
      map[sym].push({ date: row.date, price: parseFloat(String(row.price)) });
    }
    // Sort each by date
    for (const key of Object.keys(map)) {
      map[key]!.sort((a, b) => a.date.localeCompare(b.date));
    }
    return map;
  }, [benchmarks]);

  // Derive categoryStats from categoryHistoryMap for CategoryCompareCard
  const derivedCategoryStats = useMemo(() => {
    if (!categoryHistoryMap) return undefined;
    const stats: Record<string, { avg_change: number; count: number }> = {};
    const historyMap = categoryHistoryMap as Record<string, Record<string, { avg_return: number; fund_count: number }>>;
    for (const [fundType, dateMap] of Object.entries(historyMap)) {
      const entries = Object.values(dateMap);
      if (entries.length === 0) continue;
      const avgChange = entries.reduce((s, e) => s + (e.avg_return || 0), 0) / entries.length;
      const count = entries.reduce((s, e) => s + (e.fund_count || 0), 0) / entries.length;
      stats[fundType] = { avg_change: avgChange, count: Math.round(count) };
    }
    return stats;
  }, [categoryHistoryMap]);

  const [loading] = useState(false);
  const { toggleFavorite, isFavorite } = useFavorites();

  if (loading) return (
    <div className="min-h-screen bg-neutral-50 flex items-center justify-center">
      <div className="text-neutral-400 animate-pulse">Yükleniyor...</div>
    </div>
  );

  if (!fund) return (
    <div className="min-h-screen bg-neutral-50 flex flex-col items-center justify-center gap-4">
      <div className="text-neutral-400">Fon bulunamadı: {code}</div>
      <Link href="/" className="text-blue-600 hover:underline flex items-center gap-1">
        <ArrowLeft className="w-4 h-4" /> Fonlar
      </Link>
    </div>
  );

  const holdings = fund.holdings || [];

  return (
    <div className="min-h-screen bg-neutral-50">
      {/* Header — sticky on desktop, static on mobile to save screen space */}
      <header className="bg-white border-b border-neutral-200 sm:sticky sm:top-0 sm:z-10">
        <div className="max-w-5xl mx-auto px-3 pt-1.5 pb-1 sm:px-4 sm:pt-3 sm:pb-2">
          {/* Top row: back + code + badge + actions */}
          <div className="flex items-center justify-between gap-2">
            <div className="flex items-center gap-2 min-w-0">
              <Link href="/" className="flex items-center gap-1.5 text-neutral-500 hover:text-neutral-900 transition p-1 -ml-1">
                <Logo variant="icon" iconSize={24} className="shrink-0" />
                <ArrowLeft className="w-4 h-4 shrink-0" />
              </Link>
              <div className="h-5 w-px bg-neutral-200 hidden sm:block" />
              <Link href="/companies" className="hidden md:flex items-center px-2 py-1 text-xs font-medium text-neutral-500 hover:text-blue-600 hover:bg-blue-50 rounded-lg transition">Şirketler</Link>
              <Link href="/performers" className="hidden md:flex items-center px-2 py-1 text-xs font-medium text-neutral-500 hover:text-blue-600 hover:bg-blue-50 rounded-lg transition">En Çok Kazandıranlar</Link>
              <Link href="/etf" className="hidden md:flex items-center px-2 py-1 text-xs font-medium text-neutral-500 hover:text-blue-600 hover:bg-blue-50 rounded-lg transition">Yabancı ETF</Link>
              <Link href="/holdings" className="hidden md:flex items-center px-2 py-1 text-xs font-medium text-neutral-500 hover:text-blue-600 hover:bg-blue-50 rounded-lg transition">Hisseler</Link>
              <span className="font-mono font-bold text-neutral-900 text-sm">{fund.code}</span>
              {fund.fund_type && (
                <Badge className="bg-blue-100 text-blue-700 text-xs py-0 px-1.5">
                  {TYPE_LABELS[fund.fund_type] || fund.fund_type}
                </Badge>
              )}
            </div>
            <div className="flex items-center gap-1.5 shrink-0">
              <Link
                href={`/compare?codes=${fund.code}`}
                className="flex items-center gap-1 px-2 py-1 text-xs font-medium bg-neutral-100 text-neutral-700 rounded-lg hover:bg-blue-600 hover:text-white transition"
              >
                <BarChart2 className="w-3.5 h-3.5" />
                <span className="hidden sm:inline">Karşılaştır</span>
              </Link>
              <button
                onClick={() => toggleFavorite(fund.code, fund.name)}
                className={`p-1 rounded-lg transition ${
                  isFavorite(fund.code)
                    ? "bg-red-50 text-red-600"
                    : "bg-neutral-100 text-neutral-700 hover:text-red-600"
                }`}
                title={isFavorite(fund.code) ? "Favorilerden kaldır" : "Favorilere ekle"}
              >
                <Heart className="w-4 h-4" fill={isFavorite(fund.code) ? "currentColor" : "none"} />
              </button>
            </div>
          </div>

          {/* Fund name + price + logo */}
          <div className="flex items-center justify-between gap-2 mt-1">
            <div className="flex items-center gap-2 min-w-0">
              <CompanyLogo logoFile={fund.company_logo || undefined} company={fund.company || undefined} code={fund.code} size={48} className="shrink-0 sm:hidden" />
              <CompanyLogo logoFile={fund.company_logo || undefined} company={fund.company || undefined} code={fund.code} size={64} className="shrink-0 hidden sm:flex" />
              <div className="min-w-0">
                <h1 className="text-sm font-bold text-neutral-900 leading-tight truncate">
                  {fund.name}
                </h1>
              </div>
            </div>
            <div className="flex items-baseline gap-1 shrink-0">
              <span className="text-lg sm:text-4xl font-bold font-mono text-neutral-900 leading-none">
                {fund.price != null ? fmtNum(fund.price, 4) : "—"}
              </span>
              <span className="text-xs text-neutral-500">₺</span>
              <ChangeDisplay value={fund.daily_change} />
            </div>
          </div>
        </div>

        {/* Stats row — compact single row, centered */}
        <div className="max-w-5xl mx-auto px-4 pb-3 hidden sm:block">
          <div className="flex flex-wrap justify-center gap-2">
            <StatCard
              label="Fon Büyüklüğü"
              value={fund.market_cap ? fmtMoney(fund.market_cap) : "—"}
              icon={Banknote}
            />
            <StatCard
              label="Yatırımcı Sayısı"
              value={fund.number_of_investors != null ? fmtNum(fund.number_of_investors, 0) : "—"}
              icon={Users}
            />
            <StatCard
              label="Toplam Pay"
              value={fund.number_of_shares != null ? fmtNum(fund.number_of_shares, 0) : "—"}
              icon={Share2}
            />
            {fund.management_fee != null && (
              <StatCard
                label="Yönetim Ücreti"
                value={`${fmtNum(fund.management_fee, 2)}%`}
                icon={Percent}
              />
            )}
            {fund.max_total_expense_ratio != null && (
              <StatCard
                label="Gider Kesintisi"
                value={`${fmtNum(fund.max_total_expense_ratio, 2)}%`}
                icon={Receipt}
              />
            )}
            {fund.purchase_valor != null && (
              <StatCard
                label="Alış Valörü"
                value={`${fund.purchase_valor} gün`}
                icon={Clock}
              />
            )}
            {fund.sale_valor != null && (
              <StatCard
                label="Satış Valörü"
                value={`${fund.sale_valor} gün`}
                icon={Clock}
              />
            )}
          </div>
        </div>
      </header>

      {/* Content — grid with equal-height columns */}
      <main className="max-w-5xl mx-auto px-4 py-6 space-y-6">
        {/* Yatırımcı Eğilimi — full width, prominent */}
        <InvestorTrendCard
          priceHistory={fund.price_history || []}
          currentInvestors={fund.number_of_investors}
        />

        {/* Price Chart + Sidebar */}
        <div className="grid grid-cols-1 lg:grid-cols-3 items-start">
          <div className="lg:col-span-2 min-h-0">
            <FundChart
              priceHistory={fund.price_history || []}
              name={fund.name}
              code={fund.code}
              benchmarks={benchMap}
            />
            {/* Risk Metrics + Risk-Ayarı Getiri + Beta/Alpha — full width below chart */}
            <RiskMetrics
              priceHistory={fund.price_history || []}
              currentPrice={fund.price}
            />
            <SharpeRatioCard
              priceHistory={fund.price_history || []}
              currentPrice={fund.price}
            />
            <BetaAlphaCard
              priceHistory={fund.price_history || []}
              fundType={fund.fund_type || ""}
              benchmarkData={
                (categoryHistoryMap && fund.fund_type && categoryHistoryMap[fund.fund_type])
                  ? Object.entries(categoryHistoryMap[fund.fund_type]).map(([date, v]) => ({
                      date,
                      avg_return: (v as { avg_return: number }).avg_return,
                    }))
                  : []
              }
            />
          </div>
          <div className="lg:col-span-1 lg:pl-4 space-y-4 lg:sticky lg:top-24">
            <CategoryRankCard
              rank={fundRank?.rank ?? null}
              fundType={fund.fund_type}
              dailyChange={fund.daily_change}
              fundDailyChange={fund.daily_change}
            />
            <BreakdownChart breakdown={fund.breakdown || null} />
            <CategoryCompareCard
              fundCode={fund.code}
              fundType={fund.fund_type}
              fundDailyChange={fund.daily_change}
              priceHistory={fund.price_history || []}
              categoryStats={derivedCategoryStats}
            />
            <BenchmarkCompareCard
              fundCode={fund.code}
              priceHistory={fund.price_history || []}
              benchmarks={benchMap}
            />
            <ReturnsTable
              priceHistory={fund.price_history || []}
              currentPrice={fund.price}
            />
          </div>
        </div>

        {/* Holdings */}
        {holdings.length === 0 ? (
          <Card>
            <CardContent className="p-8 text-center text-neutral-400">
              <PieChart className="w-10 h-10 mx-auto mb-3 opacity-30" />
              <div>Bireysel holding verisi yok</div>
              <div className="text-sm mt-1">Bu fon KAP/Gemini verisi ile henüz parse edilmedi</div>
            </CardContent>
          </Card>
        ) : (
          <Card>
            <CardContent className="p-0">
              <div className="px-4 py-3 border-b border-neutral-100 flex items-center justify-between">
                <h3 className="text-sm font-semibold text-neutral-700 flex items-center gap-2">
                  <PieChart className="w-4 h-4" />
                  Portföydeki Varlıklar ({holdings.length})
                </h3>
                {fund.has_gemini && (
                  <Badge variant="outline" className="text-xs text-green-600 border-green-200 bg-green-50">
                    ✓ KAP verisi
                  </Badge>
                )}
              </div>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b bg-neutral-50 text-left text-xs text-neutral-500 uppercase tracking-wide">
                      <th className="px-4 py-3 font-medium w-10">Logo</th>
                      <th className="px-4 py-3 font-medium">Sembol</th>
                      <th className="px-4 py-3 font-medium text-right hidden sm:table-cell">Ağırlık</th>
                      <th className="px-4 py-3 font-medium text-right">Değer</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-neutral-100">
                    {holdings.map((h, i) => (
                      <tr key={i} className="hover:bg-neutral-50 transition">
                        <td className="px-4 py-3">
                          <StockLogo ticker={h.ticker || ""} company={h.company} size={36} />
                        </td>
                        <td className="px-4 py-3">
                          <div className="flex items-center gap-1.5">
                            <span className={`font-mono font-semibold text-sm ${h.ticker?.endsWith(".E") ? "text-blue-600" : "text-neutral-600"}`}>
                              {h.ticker?.replace(".E", "") || "—"}
                            </span>
                            {h.type && h.type !== "stock" && (
                              <Badge variant="outline" className="text-xs text-neutral-400">{h.type}</Badge>
                            )}
                          </div>
                        </td>
                        <td className="px-4 py-3 text-right hidden sm:table-cell">
                          {h.weight_pct ? (
                            <span className="font-mono text-neutral-700">{h.weight_pct}%</span>
                          ) : "—"}
                        </td>
                        <td className="px-4 py-3 text-right">
                          {h.total_value ? (
                            <span className="font-mono text-neutral-600 text-xs">{h.total_value}</span>
                          ) : "—"}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </CardContent>
          </Card>
        )}
      </main>
    </div>
  );
}
