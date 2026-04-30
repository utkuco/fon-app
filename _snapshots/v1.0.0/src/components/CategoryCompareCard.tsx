"use client";

import { useMemo } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { TrendingUp, TrendingDown, BarChart2 } from "lucide-react";

interface PricePoint {
  date: string;
  price: number;
  change?: number;
  market_cap?: number | null;
}

interface CategoryCompareCardProps {
  fundCode: string;
  fundType: string | null;
  fundDailyChange: number | null;
  priceHistory: PricePoint[];
  categoryStats?: Record<string, { avg_change: number; count: number }>;
}

interface PeriodRow {
  label: string;
  fund: number;
  category: number;
  diff: number;
}

export default function CategoryCompareCard({
  fundCode,
  fundType,
  fundDailyChange,
  priceHistory,
  categoryStats,
}: CategoryCompareCardProps) {
  const analysis = useMemo(() => {
    if (!priceHistory || priceHistory.length < 5 || !categoryStats || !fundType) return null;

    const cat = categoryStats[fundType];
    if (!cat) return null;

    const sorted = [...priceHistory].sort((a, b) => a.date.localeCompare(b.date));
    const latest = sorted[sorted.length - 1];

    // Calculate fund returns for different periods
    const getReturn = (days: number): number => {
      if (sorted.length < 2) return 0;
      const todayDate = sorted[sorted.length - 1].date;
      const cutoff = new Date(todayDate);
      cutoff.setDate(cutoff.getDate() - days);
      const cutoffStr = cutoff.toISOString().split("T")[0];
      const idx = sorted.findIndex(p => p.date >= cutoffStr);
      if (idx < 0 || idx === 0) return 0;
      const start = sorted[idx - 1]?.price || 0;
      const end = sorted[sorted.length - 1]?.price || 0;
      if (!start) return 0;
      return ((end - start) / start) * 100;
    };

    const catDailyAvg = cat.avg_change ?? 0;

    // Project category returns for same periods
    // Using compound daily avg as proxy for category performance
    const projectCatReturn = (days: number) => {
      return catDailyAvg * days * 0.7; // approximate — reduces overshoot vs pure compounding
    };

    const periods: PeriodRow[] = [
      {
        label: "1 Gün",
        fund: fundDailyChange ?? 0,
        category: catDailyAvg,
        diff: (fundDailyChange ?? 0) - catDailyAvg,
      },
      {
        label: "1 Hafta",
        fund: getReturn(7),
        category: projectCatReturn(7),
        diff: getReturn(7) - projectCatReturn(7),
      },
      {
        label: "1 Ay",
        fund: getReturn(21),
        category: projectCatReturn(21),
        diff: getReturn(21) - projectCatReturn(21),
      },
      {
        label: "3 Ay",
        fund: getReturn(63),
        category: projectCatReturn(63),
        diff: getReturn(63) - projectCatReturn(63),
      },
    ].filter(p => Math.abs(p.fund) > 0.01 || Math.abs(p.category) > 0.01);

    const dailyDiff = (fundDailyChange ?? 0) - catDailyAvg;
    const betterThanAvg = dailyDiff > 0;

    return {
      periods,
      dailyDiff,
      betterThanAvg,
      categoryCount: cat.count,
      catDailyAvg,
      fundDailyChange: fundDailyChange ?? 0,
    };
  }, [priceHistory, categoryStats, fundType, fundDailyChange]);

  if (!analysis) {
    return (
      <Card>
        <CardContent className="p-4">
          <h3 className="text-sm font-semibold text-neutral-700 mb-3 flex items-center gap-2">
            <BarChart2 className="w-4 h-4" />
            Kategori Karşılaştırması
          </h3>
          <div className="flex flex-col items-center justify-center py-4 text-center">
            <div className="text-sm text-neutral-500">Karşılaştırma verisi yok</div>
          </div>
        </CardContent>
      </Card>
    );
  }

  const { periods, dailyDiff, betterThanAvg, categoryCount, catDailyAvg, fundDailyChange: fd } = analysis;

  return (
    <Card>
      <CardContent className="p-4">
        <div className="flex items-center gap-2 mb-3">
          <h3 className="text-sm font-semibold text-neutral-700 flex items-center gap-2">
            <BarChart2 className="w-4 h-4" />
            vs Kategori Ortalaması
          </h3>
          <span className={`ml-auto inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-semibold ${betterThanAvg ? "bg-green-100 text-green-700" : "bg-red-100 text-red-700"}`}>
            {betterThanAvg ? <TrendingUp className="w-3 h-3" /> : <TrendingDown className="w-3 h-3" />}
            {betterThanAvg ? "+" : ""}{dailyDiff.toFixed(2)}%
          </span>
        </div>

        {/* Period comparison table */}
        <div className="space-y-2">
          {periods.map((p) => {
            const pBetter = p.diff > 0;
            const maxAbs = Math.max(Math.abs(p.fund), Math.abs(p.category));
            const fundWidth = maxAbs > 0 ? Math.abs(p.fund) / maxAbs * 100 : 0;
            const catWidth = maxAbs > 0 ? Math.abs(p.category) / maxAbs * 100 : 0;

            return (
              <div key={p.label} className="flex items-center gap-2">
                <span className="text-xs text-neutral-400 w-12 shrink-0">{p.label}</span>

                <div className="flex-1 min-w-0">
                  {/* Fund bar */}
                  <div className="flex items-center gap-1 mb-0.5">
                    <span className="text-[10px] font-mono font-semibold w-10 text-right shrink-0 text-neutral-700">
                      {p.fund >= 0 ? "+" : ""}{p.fund.toFixed(1)}%
                    </span>
                    <div className="flex-1 h-1.5 bg-neutral-100 rounded-full overflow-hidden">
                      <div
                        className={`h-full rounded-full ${p.fund >= 0 ? "bg-green-400" : "bg-red-400"}`}
                        style={{ width: `${fundWidth}%` }}
                      />
                    </div>
                  </div>
                  {/* Category bar */}
                  <div className="flex items-center gap-1">
                    <span className="text-[10px] font-mono w-10 text-right shrink-0 text-neutral-400">
                      {p.category >= 0 ? "+" : ""}{p.category.toFixed(1)}%
                    </span>
                    <div className="flex-1 h-1 bg-neutral-100 rounded-full overflow-hidden">
                      <div
                        className={`h-full rounded-full ${p.category >= 0 ? "bg-blue-300" : "bg-orange-300"}`}
                        style={{ width: `${catWidth}%` }}
                      />
                    </div>
                  </div>
                </div>

                <span className={`text-[10px] font-bold w-12 text-right shrink-0 ${pBetter ? "text-green-600" : "text-red-600"}`}>
                  {pBetter ? "+" : ""}{p.diff.toFixed(1)}%
                </span>
              </div>
            );
          })}
        </div>

        {/* Legend */}
        <div className="flex items-center gap-3 mt-3 pt-2 border-t border-neutral-100">
          <span className="flex items-center gap-1 text-[10px] text-neutral-500">
            <span className="w-2 h-1.5 rounded-full bg-green-400 inline-block" />
            {fundCode}
          </span>
          <span className="flex items-center gap-1 text-[10px] text-neutral-500">
            <span className="w-2 h-1 bg-blue-300 rounded-full inline-block" />
            {fundType} ort. ({categoryCount} fon)
          </span>
        </div>

        <div className="mt-2 text-[10px] text-neutral-400 italic">
          Kategori ortalaması tahmini — gerçek tarihsel kategori verisi Supabase&apos;da olmadığında yaklaşık hesap
        </div>
      </CardContent>
    </Card>
  );
}
