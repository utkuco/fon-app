"use client";

import { useState } from "react";
import { Card, CardContent } from "@/components/ui/card";
import Link from "next/link";
import { ETF_CATEGORIES } from "@/lib/etf-categories";

interface Fund {
  code: string;
  name: string;
  fund_type: string | null;
  market_cap: number | null;
  daily_change: number | null;
  sparkline?: { points: Array<[number, number]>; positive: boolean } | null;
}

interface CategoryStats {
  [key: string]: { count: number; avg_change: number; total_market_cap: number };
}

interface CategoryChange {
  [key: string]: { change_pct: number; prev_aum: number; curr_aum: number; count: number };
}

interface CategorySparklines {
  [key: string]: { points: Array<[number, number]>; positive: boolean };
}

interface EtfRaw {
  symbol: string;
  name: string;
  asset_type: string | null;
  aum: number | null;
  ytd_return: number | null;
  ytd_return_try: number | null;
  change_pct: number | null;
  one_month_return_try: number | null;
  three_month_return_try: number | null;
  six_month_return_try: number | null;
}

interface CategoryTypeCardsProps {
  funds?: Fund[];
  categoryStats?: CategoryStats;
  categoryChange?: CategoryChange;
  categorySparklines?: CategorySparklines;
  etfData?: EtfRaw[];
}

// TEFAS fund type codes → display labels
const TYPE_META: Record<string, { label: string; color: string }> = {
  "SRF":       { label: "Serbest",           color: "bg-blue-50 text-blue-700" },
  "VFF":       { label: "Değişken",          color: "bg-emerald-50 text-emerald-700" },
  "OKS":       { label: "Karma",             color: "bg-purple-50 text-purple-700" },
  "ALTIN":     { label: "Altın",             color: "bg-yellow-50 text-yellow-700" },
  "KFF":       { label: "Tahvil & Bono",     color: "bg-orange-50 text-orange-700" },
  "DÖVİZ":     { label: "Döviz",            color: "bg-cyan-50 text-cyan-700" },
  "BYF":       { label: "Borsa Yönetilen",   color: "bg-indigo-50 text-indigo-700" },
  "OTHER":     { label: "Diğer",             color: "bg-neutral-50 text-neutral-700" },
};

// Aggregate ETF data by mega-category
type EtfCatAgg = {
  count: number;
  total_aum: number;
  avg_ytd_try: number;
  avg_change: number;
  avg_1m: number;   // one_month_return_try (already in decimal form, e.g. 0.0743 = 7.43%)
  avg_3m: number;   // three_month_return_try
  avg_6m: number;   // six_month_return_try
};

function buildPath(points: Array<[number, number]>, W = 280, H = 40): string {
  if (!points || points.length === 0) return "";
  const [startX, startY] = points[0];
  let d = `M${startX.toFixed(1)},${startY.toFixed(1)}`;
  for (let i = 1; i < points.length; i++) {
    const [x, y] = points[i];
    d += ` L${x.toFixed(1)},${y.toFixed(1)}`;
  }
  return d;
}

function buildArea(points: Array<[number, number]>, W = 280, H = 40): string {
  if (!points || points.length === 0) return "";
  const line = buildPath(points, W, H);
  const last = points[points.length - 1];
  const first = points[0];
  return `${line} L${last[0].toFixed(1)},${H} L${first[0].toFixed(1)},${H} Z`;
}

function formatAUM(value: number): string {
  if (value >= 1e12) return `${(value / 1e12).toFixed(1)}T`;
  if (value >= 1e9) return `${(value / 1e9).toFixed(1)}B`;
  if (value >= 1e6) return `${(value / 1e6).toFixed(1)}M`;
  return value.toString();
}

function fmtEtfAUM(v: number): string {
  if (v >= 1e12) return `$${(v / 1e12).toFixed(1)}T`;
  if (v >= 1e9) return `$${(v / 1e9).toFixed(1)}B`;
  if (v >= 1e6) return `$${(v / 1e6).toFixed(0)}M`;
  return `$${v.toFixed(0)}`;
}

export function CategoryTypeCards({
  categoryStats = {},
  categoryChange = {},
  categorySparklines = {},
  etfData = [],
}: CategoryTypeCardsProps) {
  const topTypes = Object.entries(categoryStats)
    .sort(([, a], [, b]) => b.total_market_cap - a.total_market_cap)
    .slice(0, 8);

  const totalAUM = Object.values(categoryStats).reduce((s, c) => s + c.total_market_cap, 0);

  // ── Asset-type → category mapping for uncategorized ETFs ──
  const ASSET_TYPE_FALLBACK: Record<string, string> = {
    EQUITY: "dunya",
    COMMODITY: "altin",
    BOND: "tahvil",
    "Large Blend": "dunya",
    "Large Value": "dunya",
    "Large Growth": "dunya",
    "Mid-Cap Blend": "dunya",
    "Mid-Cap Value": "dunya",
    "Mid-Cap Growth": "dunya",
    "Small Blend": "dunya",
    "Small Value": "dunya",
    "Small Growth": "dunya",
    "Diversified Emerging Mkts": "dunya",
    "Foreign Large Blend": "dunya",
    "Foreign Large Value": "dunya",
    "Foreign Large Growth": "dunya",
    "Europe Stock": "dunya",
    "Japan Stock": "dunya",
    "China Region": "dunya",
    "India Equity": "dunya",
    "Pacific/Asia ex-Japan Stk": "dunya",
    "Latin America Stock": "dunya",
    "REAL_ESTATE": "dunya",
    "Global Real Estate": "dunya",
    "Real Estate": "dunya",
    "Preferred Stock": "tahvil",
    "High Yield Bond": "tahvil",
    "Emerging Markets Bond": "tahvil",
    "Global Bond": "tahvil",
    "Intermediate Core Bond": "tahvil",
    "Short-Term Bond": "tahvil",
    "Long Government": "tahvil",
    "Ultrashort Bond": "tahvil",
    "Multisector Bond": "tahvil",
    "Corporate Bond": "tahvil",
    "Bank Loan": "tahvil",
    "Commodities Broad Basket": "altin",
    "Commodities Focused": "altin",
    "Natural Resources": "altin",
    "Inflation-Protected Bond": "tahvil",
    "Equity Energy": "dunya",
    "Financial": "dunya",
    "Health": "dunya",
    "Technology": "dunya",
    "Consumer Cyclical": "dunya",
    "Consumer Defensive": "dunya",
    "Communications": "dunya",
    "Infrastructure": "dunya",
    "Global Large-Stock Blend": "dunya",
    "Global Large-Stock Growth": "dunya",
    "Global Large-Stock Value": "dunya",
    "Global Small/Mid Stock": "dunya",
    "Moderate Allocation": "dunya",
    "Global Moderate Allocation": "dunya",
    "Aggressive Allocation": "dunya",
    "Global Aggressive Allocation": "dunya",
    "Conservative Allocation": "dunya",
    "Global Conservative Allocation": "dunya",
  };

  // ── Aggregate ETF data: symbol match first, then asset_type fallback, then "diger" ──
  const etfAgg: Record<string, EtfCatAgg> = {};
  for (const etf of etfData) {
    let catKey: string | null = null;
    // 1. Try symbol match against ETF_CATEGORIES
    for (const cat of ETF_CATEGORIES) {
      if (cat.key !== "diger" && cat.symbols.has(etf.symbol)) {
        catKey = cat.key;
        break;
      }
    }
    // 2. Fallback: asset_type mapping
    if (!catKey && etf.asset_type) {
      catKey = ASSET_TYPE_FALLBACK[etf.asset_type] || null;
    }
    // 3. Default: diger
    if (!catKey) catKey = "diger";

    const prev = etfAgg[catKey] || { count: 0, total_aum: 0, avg_ytd_try: 0, avg_change: 0, avg_1m: 0, avg_3m: 0, avg_6m: 0 };
    const ytdVal = (etf as EtfRaw).ytd_return_try ?? etf.ytd_return ?? 0;
    const chgVal = etf.change_pct ?? 0;
    const ret1m = (etf as EtfRaw).one_month_return_try ?? 0;
    const ret3m = (etf as EtfRaw).three_month_return_try ?? 0;
    const ret6m = (etf as EtfRaw).six_month_return_try ?? 0;
    etfAgg[catKey] = {
      count: prev.count + 1,
      total_aum: prev.total_aum + (etf.aum || 0),
      avg_ytd_try: (prev.avg_ytd_try * prev.count + ytdVal) / (prev.count + 1),
      avg_change: (prev.avg_change * prev.count + chgVal) / (prev.count + 1),
      avg_1m: (prev.avg_1m * prev.count + ret1m) / (prev.count + 1),
      avg_3m: (prev.avg_3m * prev.count + ret3m) / (prev.count + 1),
      avg_6m: (prev.avg_6m * prev.count + ret6m) / (prev.count + 1),
    };
  }

  const totalEtfAUM = Object.values(etfAgg).reduce((s, v) => s + v.total_aum, 0);

  // Hide "diger" if it has too many ETFs (threshold: 100)
  const DIGER_THRESHOLD = 100;
  // Always include "diger" as last card if it has ETFs — rendered inside the same grid
  const etfCatsToShow = ETF_CATEGORIES.filter(cat => {
    if (cat.key === "diger") return false; // handled below
    return (etfAgg[cat.key]?.count ?? 0) > 0;
  });
  const showDiger = (etfAgg["diger"]?.count ?? 0) > 0;

  const [catTab, setCatTab] = useState<"turkish" | "etf">("turkish");

  return (
    <div className="bg-white rounded-xl border border-neutral-200 overflow-hidden">
      {/* Tab bar */}
      <div className="flex items-center gap-2 px-4 py-2.5 border-b border-neutral-100 bg-neutral-50">
        <span className="text-xs font-semibold text-neutral-500 uppercase tracking-wide">Kategoriler</span>
        <div className="ml-auto flex gap-1 bg-white border border-neutral-200 rounded-lg p-0.5">
          <button
            onClick={() => setCatTab("turkish")}
            className={`px-3 py-1 rounded-md text-[11px] font-medium transition ${
              catTab === "turkish"
                ? "bg-blue-600 text-white shadow-sm"
                : "text-neutral-500 hover:text-blue-700"
            }`}
          >
            Türk Fonları
          </button>
          <button
            onClick={() => setCatTab("etf")}
            className={`px-3 py-1 rounded-md text-[11px] font-medium transition ${
              catTab === "etf"
                ? "bg-amber-500 text-white shadow-sm"
                : "text-neutral-500 hover:text-amber-700"
            }`}
          >
            Yabancı ETF
          </button>
        </div>
      </div>

      {/* ── TÜRK FON KATEGORİLERİ ── */}
      {catTab === "turkish" && topTypes.length > 0 && (
        <div className="p-3">
          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-2">
            {topTypes.map(([type, stat]) => {
              const meta = TYPE_META[type] || TYPE_META["OTHER"];
              const spark = categorySparklines[type];
              const share = totalAUM > 0 ? (stat.total_market_cap / totalAUM) * 100 : 0;
              const avgChange = stat.avg_change ?? 0;
              const points = spark?.points || [];
              const sparkPositive = spark?.positive ?? (avgChange >= 0);
              const sparkColor = sparkPositive ? "#10B981" : "#EF4444";

              const W = 280, H = 40;
              const linePath = buildPath(points, W, H);
              const areaPath = buildArea(points, W, H);

              const periods = [
                { label: "1H", mult: 0.25 },
                { label: "1A", mult: 4.5 },
                { label: "3A", mult: 13.5 },
                { label: "6A", mult: 27 },
              ];

              return (
                <Link key={type} href={`/type/${type}`}>
                  <Card className="h-full transition-all duration-200 hover:shadow-md hover:-translate-y-0.5 cursor-pointer overflow-hidden">
                    <CardContent className="p-3 flex flex-col gap-2 h-full">
                      <div className="flex items-center gap-2">
                        <div className={`w-7 h-7 rounded-lg flex items-center justify-center text-xs font-bold ${meta.color}`}>
                          {stat.count}
                        </div>
                        <div className="min-w-0 flex-1">
                          <div className="text-xs font-bold text-neutral-900 truncate">{meta.label}</div>
                          <div className="text-[10px] text-neutral-400">{formatAUM(stat.total_market_cap)} TL · %{share.toFixed(1)}</div>
                        </div>
                        <div className="shrink-0 text-right">
                          <div className={`text-[11px] font-bold ${avgChange >= 0 ? "text-emerald-600" : "text-red-500"}`}>
                            {avgChange >= 0 ? "+" : ""}{avgChange.toFixed(2)}%
                          </div>
                          <div className="text-[9px] text-neutral-400">günlük</div>
                        </div>
                      </div>

                      {/* Sparkline — Son 6 Ay */}
                      {points.length >= 2 ? (
                        <div className="flex flex-col gap-0.5">
                          <span className="text-[8px] text-neutral-300 font-medium">SON 6 AY</span>
                          <svg width="100%" height={48} viewBox={`0 0 ${W} ${H}`} className="w-full overflow-visible">
                            <defs>
                              <linearGradient id={`sg-type-${type}`} x1="0" y1="0" x2="0" y2="1">
                                <stop offset="0%" stopColor={sparkColor} stopOpacity="0.2" />
                                <stop offset="100%" stopColor={sparkColor} stopOpacity="0" />
                              </linearGradient>
                            </defs>
                            <path d={areaPath} fill={`url(#sg-type-${type})`} />
                            <path d={linePath} fill="none" stroke={sparkColor} strokeWidth="1.5" strokeLinecap="round" />
                          </svg>
                        </div>
                      ) : (
                        <div className="h-12 flex items-center justify-center gap-1.5 bg-neutral-50 rounded-lg">
                          <div className={`w-2.5 h-2.5 rounded-full ${sparkPositive ? "bg-emerald-400" : "bg-red-400"}`} />
                          <span className="text-[10px] text-neutral-400">{sparkPositive ? "Pozitif trend" : "Negatif trend"}</span>
                        </div>
                      )}

                      <div className="flex items-center gap-1.5">
                        {periods.map(({ label, mult }) => (
                          <div key={label} className="flex-1 flex flex-col items-center py-1.5 rounded-lg bg-neutral-50 gap-0.5">
                            <span className="text-[9px] text-neutral-400 font-medium">{label}</span>
                            <span className={`text-[11px] font-bold ${avgChange >= 0 ? "text-emerald-600" : "text-red-500"}`}>
                              {avgChange >= 0 ? "+" : ""}{(avgChange * mult).toFixed(1)}%
                            </span>
                          </div>
                        ))}
                      </div>
                    </CardContent>
                  </Card>
                </Link>
              );
            })}
          </div>
        </div>
      )}

      {/* ── YABANCI ETF KATEGORİLERİ ── */}
      {catTab === "etf" && etfData.length > 0 && (
        <div className="p-3">
          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-2">
            {etfCatsToShow.map(cat => {
              const stat = etfAgg[cat.key];
              if (!stat) return null;
              const share = totalEtfAUM > 0 ? (stat.total_aum / totalEtfAUM) * 100 : 0;
              const avgChange = stat.avg_change ?? 0;
              const sparkPositive = avgChange >= 0;
              const sparkColor = sparkPositive ? "#10B981" : "#EF4444";

              // Sparkline from DB
              const etfCatKey = cat.key.toUpperCase();
              const catSpark = categorySparklines?.[etfCatKey];
              const sparkPoints = catSpark?.points || [];
              const W = 280, H = 40;
              const linePath = buildPath(sparkPoints, W, H);
              const areaPath = buildArea(sparkPoints, W, H);

              return (
                <Link key={cat.key} href={`/etf/${cat.key}`}>
                  <Card className={`h-full transition-all duration-200 hover:shadow-md hover:-translate-y-0.5 cursor-pointer overflow-hidden ${cat.bgHover}`}>
                    <CardContent className="p-3 flex flex-col gap-2 h-full">
                      {/* Header row — IDENTICAL to Turkish fund card */}
                      <div className="flex items-center gap-2">
                        <div className={`w-7 h-7 rounded-lg flex items-center justify-center text-xs font-bold ${cat.color}`}>
                          {stat.count}
                        </div>
                        <div className="min-w-0 flex-1">
                          <div className="text-xs font-bold text-neutral-900 truncate">{cat.label}</div>
                          <div className="text-[10px] text-neutral-400">{fmtEtfAUM(stat.total_aum)} · %{share.toFixed(1)}</div>
                        </div>
                        <div className="shrink-0 text-right">
                          <div className={`text-[11px] font-bold ${avgChange >= 0 ? "text-emerald-600" : "text-red-500"}`}>
                            {avgChange >= 0 ? "+" : ""}{(avgChange * 100).toFixed(2)}%
                          </div>
                          <div className="text-[9px] text-neutral-400">günlük</div>
                        </div>
                      </div>

                      {/* Sparkline — IDENTICAL to Turkish fund card */}
                      {sparkPoints.length >= 2 ? (
                        <div className="flex flex-col gap-0.5">
                          <span className="text-[8px] text-neutral-300 font-medium">SON 6 AY</span>
                          <svg width="100%" height={48} viewBox={`0 0 ${W} ${H}`} className="w-full overflow-visible">
                            <defs>
                              <linearGradient id={`sg-etf-${cat.key}`} x1="0" y1="0" x2="0" y2="1">
                                <stop offset="0%" stopColor={sparkColor} stopOpacity="0.2" />
                                <stop offset="100%" stopColor={sparkColor} stopOpacity="0" />
                              </linearGradient>
                            </defs>
                            <path d={areaPath} fill={`url(#sg-etf-${cat.key})`} />
                            <path d={linePath} fill="none" stroke={sparkColor} strokeWidth="1.5" strokeLinecap="round" />
                          </svg>
                        </div>
                      ) : (
                        <div className="h-12 flex items-center justify-center gap-1.5 bg-neutral-50 rounded-lg">
                          <div className={`w-2.5 h-2.5 rounded-full ${sparkPositive ? "bg-emerald-400" : "bg-red-400"}`} />
                          <span className="text-[10px] text-neutral-400">Fiyat verisi yok</span>
                        </div>
                      )}

                      {/* Returns — IDENTICAL to Turkish fund card (1H/1A/3A/6A) */}
                      {/* For ETF: 1H = daily change * 1, 1A = avg_1m, 3A = avg_3m, 6A = avg_6m */}
                      <div className="flex items-center gap-1.5">
                        <div className="flex-1 flex flex-col items-center py-1.5 rounded-lg bg-neutral-50 gap-0.5">
                          <span className="text-[9px] text-neutral-400 font-medium">1H</span>
                          <span className={`text-[11px] font-bold ${avgChange >= 0 ? "text-emerald-600" : "text-red-500"}`}>
                            {avgChange >= 0 ? "+" : ""}{(avgChange * 100).toFixed(2)}%
                          </span>
                        </div>
                        <div className="flex-1 flex flex-col items-center py-1.5 rounded-lg bg-neutral-50 gap-0.5">
                          <span className="text-[9px] text-neutral-400 font-medium">1A</span>
                          <span className={`text-[11px] font-bold ${(stat.avg_1m ?? 0) >= 0 ? "text-emerald-600" : "text-red-500"}`}>
                            {(stat.avg_1m ?? 0) >= 0 ? "+" : ""}{((stat.avg_1m ?? 0) * 100).toFixed(1)}%
                          </span>
                        </div>
                        <div className="flex-1 flex flex-col items-center py-1.5 rounded-lg bg-neutral-50 gap-0.5">
                          <span className="text-[9px] text-neutral-400 font-medium">3A</span>
                          <span className={`text-[11px] font-bold ${(stat.avg_3m ?? 0) >= 0 ? "text-emerald-600" : "text-red-500"}`}>
                            {(stat.avg_3m ?? 0) >= 0 ? "+" : ""}{((stat.avg_3m ?? 0) * 100).toFixed(1)}%
                          </span>
                        </div>
                        <div className="flex-1 flex flex-col items-center py-1.5 rounded-lg bg-neutral-50 gap-0.5">
                          <span className="text-[9px] text-neutral-400 font-medium">6A</span>
                          <span className={`text-[11px] font-bold ${(stat.avg_6m ?? 0) >= 0 ? "text-emerald-600" : "text-red-500"}`}>
                            {(stat.avg_6m ?? 0) >= 0 ? "+" : ""}{((stat.avg_6m ?? 0) * 100).toFixed(1)}%
                          </span>
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                </Link>
              );
            })}
            {/* Diğer — 6th card inside the grid, same style as others */}
            {showDiger && (() => {
              const stat = etfAgg["diger"];
              const digerShare = totalEtfAUM > 0 ? ((stat?.total_aum ?? 0) / totalEtfAUM) * 100 : 0;
              const avgChange = stat?.avg_change ?? 0;
              return (
                <Link href="/etf/diger">
                  <Card className="h-full transition-all duration-200 hover:shadow-md hover:-translate-y-0.5 cursor-pointer overflow-hidden hover:bg-neutral-50">
                    <CardContent className="p-3 flex flex-col gap-2 h-full">
                      <div className="flex items-center gap-2">
                        <div className="w-7 h-7 rounded-lg flex items-center justify-center text-xs font-bold bg-neutral-100 text-neutral-600">
                          {stat?.count ?? 0}
                        </div>
                        <div className="min-w-0 flex-1">
                          <div className="text-xs font-bold text-neutral-700 truncate">Diğer</div>
                          <div className="text-[10px] text-neutral-400">${((stat?.total_aum ?? 0) / 1e9).toFixed(0)}B · %{digerShare.toFixed(1)}</div>
                        </div>
                        <div className="shrink-0 text-right">
                          <div className={`text-[11px] font-bold ${avgChange >= 0 ? "text-emerald-600" : "text-red-500"}`}>
                            {avgChange >= 0 ? "+" : ""}{(avgChange * 100).toFixed(2)}%
                          </div>
                          <div className="text-[9px] text-neutral-400">günlük</div>
                        </div>
                      </div>
                      {/* Sparkline placeholder — same visual style as other cards */}
                      <div className="h-[52px] flex flex-col items-center justify-center bg-neutral-50 rounded-lg gap-0.5">
                        <span className="text-[8px] text-neutral-300 font-medium">SON 6 AY</span>
                        <div className="flex items-center justify-center w-full h-[40px]">
                          <span className="text-xs text-neutral-400">Tümünü gör →</span>
                        </div>
                      </div>
                      <div className="flex items-center gap-1.5">
                        <div className="flex-1 flex flex-col items-center py-1.5 rounded-lg bg-neutral-50 gap-0.5">
                          <span className="text-[9px] text-neutral-400 font-medium">1H</span>
                          <span className={`text-[11px] font-bold ${avgChange >= 0 ? "text-emerald-600" : "text-red-500"}`}>
                            {avgChange >= 0 ? "+" : ""}{(avgChange * 100).toFixed(2)}%
                          </span>
                        </div>
                        <div className="flex-1 flex flex-col items-center py-1.5 rounded-lg bg-neutral-50 gap-0.5">
                          <span className="text-[9px] text-neutral-400 font-medium">1A</span>
                          <span className="text-[11px] font-bold text-neutral-400">—</span>
                        </div>
                        <div className="flex-1 flex flex-col items-center py-1.5 rounded-lg bg-neutral-50 gap-0.5">
                          <span className="text-[9px] text-neutral-400 font-medium">3A</span>
                          <span className="text-[11px] font-bold text-neutral-400">—</span>
                        </div>
                        <div className="flex-1 flex flex-col items-center py-1.5 rounded-lg bg-neutral-50 gap-0.5">
                          <span className="text-[9px] text-neutral-400 font-medium">6A</span>
                          <span className="text-[11px] font-bold text-neutral-400">—</span>
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                </Link>
              );
            })()}
          </div>
        </div>
      )}

      {/* Empty state */}
      {catTab === "turkish" && topTypes.length === 0 && (
        <div className="p-6 text-center text-sm text-neutral-400">Kategori verisi yok</div>
      )}
      {catTab === "etf" && etfData.length === 0 && (
        <div className="p-6 text-center text-sm text-neutral-400">ETF verisi yok</div>
      )}
    </div>
  );
}
