"use client";

import { useMemo } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Trophy, TrendingUp, TrendingDown, Minus } from "lucide-react";

interface CategoryRankCardProps {
  rank: number | null;
  fundType: string | null;
  dailyChange: number | null;
  categoryStats?: Record<string, { avg_change: number; count: number }>;
  fundDailyChange?: number | null;
}

function getRiskLabel(vol: number): { label: string; color: string } {
  if (vol < 0.05) return { label: "Çok Düşük", color: "text-blue-600" };
  if (vol < 0.10) return { label: "Düşük", color: "text-green-600" };
  if (vol < 0.20) return { label: "Orta", color: "text-yellow-600" };
  if (vol < 0.35) return { label: "Yüksek", color: "text-orange-600" };
  return { label: "Çok Yüksek", color: "text-red-600" };
}

export default function CategoryRankCard({
  rank,
  fundType,
  dailyChange,
  categoryStats,
  fundDailyChange,
}: CategoryRankCardProps) {
  const { percentile, categoryCount } = useMemo(() => {
    if (!categoryStats || !fundType || dailyChange == null) return { percentile: null, categoryCount: null };

    const cat = categoryStats[fundType];
    if (!cat || cat.count < 2) return { percentile: null, categoryCount: null };

    // Estimate percentile: if fund change > category avg, likely above 50th
    const diff = (fundDailyChange ?? dailyChange) - cat.avg_change;
    // Simple model: ±2 std dev range
    const stdDev = Math.abs(cat.avg_change) * 2 || 0.1;
    const zScore = stdDev > 0 ? diff / stdDev : 0;
    const percentile = Math.min(99, Math.max(1, 50 + zScore * 20));

    return { percentile: Math.round(percentile), categoryCount: cat.count };
  }, [categoryStats, fundType, dailyChange, fundDailyChange]);

  if (rank != null) {
    const pct = rank > 0 ? Math.round((1 - rank / categoryCount!) * 100) : 0;
    return (
      <Card>
        <CardContent className="p-4">
          <h3 className="text-sm font-semibold text-neutral-700 mb-3 flex items-center gap-2">
            <Trophy className="w-4 h-4 text-amber-500" />
            Kategori Sıralaması
          </h3>
          <div className="flex items-center gap-3">
            <div className="text-3xl font-bold font-mono text-amber-600">#{rank}</div>
            <div>
              <div className="text-xs text-neutral-500">{fundType}</div>
              <div className="text-sm text-neutral-600">
                {categoryCount ? `top ${pct}%` : ""}
              </div>
            </div>
          </div>
        </CardContent>
      </Card>
    );
  }

  if (percentile != null) {
    const topPct = 100 - percentile;
    const icon = topPct > 20 ? <TrendingUp className="w-4 h-4 text-green-600" />
      : topPct < -20 ? <TrendingDown className="w-4 h-4 text-red-600" />
      : <Minus className="w-4 h-4 text-neutral-400" />;
    const bg = topPct > 20 ? "bg-green-50" : topPct < -20 ? "bg-red-50" : "bg-neutral-50";
    const text = topPct > 20 ? "text-green-700" : topPct < -20 ? "text-red-700" : "text-neutral-700";

    return (
      <Card>
        <CardContent className="p-4">
          <h3 className="text-sm font-semibold text-neutral-700 mb-3 flex items-center gap-2">
            <Trophy className="w-4 h-4 text-amber-500" />
            Kategori Sıralaması
          </h3>
          <div className="flex items-center justify-between">
            <div>
              <div className="text-3xl font-bold font-mono text-neutral-800">
                %{percentile}
              </div>
              <div className="text-xs text-neutral-500">{fundType} — {categoryCount} fon</div>
            </div>
            <div className={`flex items-center gap-1 px-2 py-1 rounded-lg ${bg}`}>
              {icon}
              <span className={`text-sm font-semibold ${text}`}>top {topPct > 0 ? `+${topPct}` : topPct}%</span>
            </div>
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardContent className="p-4">
        <h3 className="text-sm font-semibold text-neutral-700 mb-3 flex items-center gap-2">
          <Trophy className="w-4 h-4 text-amber-500" />
          Kategori Sıralaması
        </h3>
        <div className="flex flex-col items-center justify-center py-3 text-center">
          <div className="text-3xl mb-1">📊</div>
          <div className="text-sm text-neutral-500">Sıralama verisi yok</div>
          {fundType && (
            <div className="text-xs text-neutral-400 mt-1">{fundType} kategorisinde yeterli veri</div>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
