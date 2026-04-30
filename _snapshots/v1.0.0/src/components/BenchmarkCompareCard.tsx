"use client";

import { useMemo } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { TrendingUp, TrendingDown } from "lucide-react";

interface PricePoint {
  date: string;
  price: number;
  change?: number;
}

interface BenchmarkResult {
  label: string;
  shortLabel: string;
  color: string;
  fundAnnual: number;
  benchAnnual: number;
  diff: number;
  better: boolean;
  hasData: boolean;
}

const BENCHMARK_META: Record<string, { label: string; shortLabel: string; color: string }> = {
  BIST100:  { label: "BIST 100",  shortLabel: "BIST",   color: "#6366f1" },
  SP500:    { label: "S&P 500",   shortLabel: "S&P",    color: "#16a34a" },
  NASDAQ:   { label: "Nasdaq",    shortLabel: "Nasdaq",  color: "#0891b2" },
  USDTRY:   { label: "USD/TRY",   shortLabel: "$/₺",    color: "#9333ea" },
  GOLD:     { label: "Altın",     shortLabel: "Au",      color: "#eab308" },
  BTCUSD:   { label: "Bitcoin",   shortLabel: "BTC",     color: "#f97316" },
  ETHUSD:   { label: "Ethereum",  shortLabel: "ETH",    color: "#8b5cf6" },
};

function computeReturn(
  benchData: Array<{ date: string; price: number }> | undefined,
  fundHistory: PricePoint[],
): { annual: number; fundAnnual: number } | null {
  if (!fundHistory?.length) return null;
  const fundStart = fundHistory[0]?.price;
  const fundEnd = fundHistory[fundHistory.length - 1]?.price;
  if (!fundStart || !fundEnd || fundStart === 0) return null;

  const fundTotalReturn = (fundEnd - fundStart) / fundStart;
  const fundAnnual = Math.pow(1 + fundTotalReturn, 252 / Math.max(fundHistory.length, 1)) - 1;

  if (!benchData?.length) return { annual: 0, fundAnnual };

  const benchStart = benchData[0].price;
  const benchEnd = benchData[benchData.length - 1].price;
  if (!benchStart || !benchEnd || benchStart === 0) return { annual: 0, fundAnnual };

  const benchTotalReturn = (benchEnd - benchStart) / benchStart;
  const benchAnnual = Math.pow(1 + benchTotalReturn, 252 / Math.max(benchData.length, 1)) - 1;

  return { annual: benchAnnual, fundAnnual };
}

interface BenchmarkCompareCardProps {
  fundCode: string;
  priceHistory: PricePoint[];
  benchmarks?: Record<string, Array<{ date: string; price: number }>> | null;
}

export default function BenchmarkCompareCard({ fundCode, priceHistory, benchmarks }: BenchmarkCompareCardProps) {
  const comparisons: BenchmarkResult[] = useMemo(() => {
    const results: BenchmarkResult[] = [];
    for (const [sym, meta] of Object.entries(BENCHMARK_META)) {
      const benchData = benchmarks?.[sym];
      const result = computeReturn(benchData, priceHistory);
      if (result) {
        const diff = result.fundAnnual - result.annual;
        results.push({
          ...meta,
          fundAnnual: result.fundAnnual,
          benchAnnual: result.annual,
          diff,
          better: result.fundAnnual > result.annual,
          hasData: !!benchData?.length,
        });
      }
    }
    return results;
  }, [benchmarks, priceHistory]);

  const available = comparisons.filter(c => c.hasData);
  const sorted = [...available].sort((a, b) => b.diff - a.diff);

  if (sorted.length === 0) {
    return (
      <Card>
        <CardContent className="p-3">
          <h3 className="text-xs font-semibold text-neutral-700 mb-2 flex items-center gap-1.5">
            <TrendingUp className="w-3.5 h-3.5 text-neutral-400" />
            Benchmark Karşılaştırması
          </h3>
          <div className="flex flex-wrap gap-1.5">
            {Object.entries(BENCHMARK_META).map(([sym, meta]) => (
              <div
                key={sym}
                className="flex items-center gap-1 px-2 py-1 rounded-full text-[10px] font-medium"
                style={{ backgroundColor: `${meta.color}15`, color: meta.color }}
              >
                {meta.shortLabel}
                <span className="text-neutral-400">—</span>
              </div>
            ))}
          </div>
          <p className="text-[10px] text-neutral-400 mt-2">Benchmark verisi yükleniyor...</p>
        </CardContent>
      </Card>
    );
  }

  const bestBench = sorted[0];
  const worstBench = sorted[sorted.length - 1];

  return (
    <Card>
      <CardContent className="p-3">
        <h3 className="text-xs font-semibold text-neutral-700 mb-2 flex items-center gap-1.5">
          <TrendingUp className="w-3.5 h-3.5 text-neutral-400" />
          Benchmark Karşılaştırması
          <span className="ml-auto text-[10px] text-neutral-400 font-normal">
            yıllık
          </span>
        </h3>

        {/* Benchmark rows */}
        <div className="space-y-1">
          {sorted.map((comp) => (
            <div key={comp.label} className="flex items-center gap-2 py-1">
              {/* Color dot + label */}
              <div className="flex items-center gap-1.5 min-w-0 flex-shrink-0 w-20">
                <span className="w-2 h-2 rounded-full shrink-0" style={{ backgroundColor: comp.color }} />
                <span className="text-[11px] text-neutral-600 truncate">{comp.shortLabel}</span>
              </div>

              {/* Fund return bar */}
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-1.5">
                  <span className="text-[10px] text-neutral-400 font-mono w-10 text-right shrink-0">
                    {comp.benchAnnual >= 0 ? "+" : ""}{(comp.benchAnnual * 100).toFixed(1)}%
                  </span>
                  {/* Bar */}
                  <div className="flex-1 h-1.5 bg-neutral-100 rounded-full overflow-hidden relative">
                    <div
                      className="absolute h-full rounded-full transition-all"
                      style={{
                        backgroundColor: comp.color,
                        left: "50%",
                        width: `${Math.min(Math.abs(comp.diff) / 0.5 * 50, 50)}%`,
                        transform: comp.diff >= 0 ? "translateX(-100%)" : "translateX(0)",
                      }}
                    />
                  </div>
                  {/* Fund diff */}
                  <span className={`text-[10px] font-bold font-mono w-10 shrink-0 ${comp.diff >= 0 ? "text-green-600" : "text-red-600"}`}>
                    {comp.diff >= 0 ? "+" : ""}{(comp.diff * 100).toFixed(1)}%
                  </span>
                </div>
              </div>

              {/* Winner badge */}
              <div className="w-4 flex justify-center shrink-0">
                {comp.better && (
                  <span className="text-[10px] font-bold text-green-600">★</span>
                )}
              </div>
            </div>
          ))}
        </div>

        {/* Summary badges */}
        <div className="mt-2 pt-2 border-t border-neutral-100 space-y-1">
          {bestBench && bestBench.diff > 0.001 && (
            <div className="flex items-center gap-1.5 text-[10px] text-green-700 bg-green-50 px-2 py-1 rounded">
              <TrendingUp className="w-3 h-3 text-green-600 shrink-0" />
              <span>Fon, {bestBench.shortLabel}'den <strong>+{(bestBench.diff * 100).toFixed(1)}%</strong> iyi</span>
            </div>
          )}
          {worstBench && worstBench.diff < -0.001 && (
            <div className="flex items-center gap-1.5 text-[10px] text-red-700 bg-red-50 px-2 py-1 rounded">
              <TrendingDown className="w-3 h-3 text-red-600 shrink-0" />
              <span>{worstBench.shortLabel} karşısında <strong>{(worstBench.diff * 100).toFixed(1)}%</strong> geri</span>
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
