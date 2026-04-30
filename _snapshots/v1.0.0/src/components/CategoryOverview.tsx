"use client";

import { BarChart2 } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";

interface CategoryStat {
  count: number;
  avg_change: number;
  total_market_cap: number;
}

interface CategoryChange {
  change_pct: number;
  prev_aum: number;
  curr_aum: number;
  count: number;
}

const TYPE_COLORS: Record<string, string> = {
  ALTIN: "bg-amber-50 border-amber-200",
  DEĞİŞKEN: "bg-blue-50 border-blue-200",
  ÖZEL_SEKTÖR: "bg-violet-50 border-violet-200",
  SERBEST: "bg-emerald-50 border-emerald-200",
  DÖVİZ: "bg-cyan-50 border-cyan-200",
  BORÇLANMA_ARACI: "bg-orange-50 border-orange-200",
  HİSSE: "bg-red-50 border-red-200",
  BYF: "bg-slate-50 border-slate-200",
  VFF: "bg-pink-50 border-pink-200",
  OKS: "bg-teal-50 border-teal-200",
  KFF: "bg-lime-50 border-lime-200",
};

const TYPE_LABELS: Record<string, string> = {
  ALTIN: "Altın",
  DEĞİŞKEN: "Değişken",
  ÖZEL_SEKTÖR: "Özel Sektör",
  SERBEST: "Serbest",
  DÖVİZ: "Döviz",
  BORÇLANMA_ARACI: "Borçlanma",
  HİSSE: "Hisse",
  BYF: "BYF",
  VFF: "Varlık Fon",
  OKS: "OKS",
  KFF: "Katılım KF",
};

function fmtMoney(n: number): string {
  if (n >= 1e12) return `${(n / 1e12).toFixed(2)}T`;
  if (n >= 1e9) return `${(n / 1e9).toFixed(1)}B`;
  if (n >= 1e6) return `${(n / 1e6).toFixed(1)}M`;
  return n.toLocaleString("tr-TR");
}

interface CategoryOverviewProps {
  categoryStats: Record<string, CategoryStat>;
  categoryChange: Record<string, CategoryChange>;
}

export default function CategoryOverview({ categoryStats, categoryChange }: CategoryOverviewProps) {
  const sorted = Object.entries(categoryStats)
    .sort((a, b) => b[1].total_market_cap - a[1].total_market_cap);

  return (
    <Card>
      <CardContent className="p-0">
        <div className="px-4 py-3 border-b border-neutral-100 flex items-center gap-2">
          <BarChart2 className="w-4 h-4 text-neutral-500" />
          <h3 className="text-sm font-semibold text-neutral-700">Kategori Performansı</h3>
          <span className="ml-auto text-xs text-neutral-400">günlük değişim</span>
        </div>
        <div className="divide-y divide-neutral-50">
          {sorted.map(([cat, stat]) => {
            const change = categoryChange[cat];
            const catLabel = TYPE_LABELS[cat] || cat;
            const colorClass = TYPE_COLORS[cat] || "bg-neutral-50 border-neutral-200";
            const changeVal = change?.change_pct ?? stat.avg_change;
            const positive = changeVal >= 0;
            return (
              <div
                key={cat}
                className={`flex items-center gap-3 px-4 py-2.5 border-l-2 ${colorClass.split(" ")[0].replace("bg-", "border-")} border-l-0`}
              >
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-medium text-neutral-800">{catLabel}</span>
                    <span className="text-xs text-neutral-400">{stat.count} fon</span>
                  </div>
                  <div className="text-xs text-neutral-500 mt-0.5">
                    {fmtMoney(stat.total_market_cap)} TL
                  </div>
                </div>
                {change && (
                  <div className="text-right shrink-0">
                    <div className={`text-sm font-mono font-bold ${positive ? "text-green-600" : "text-red-600"}`}>
                      {positive ? "+" : ""}{change.change_pct.toFixed(2)}%
                    </div>
                    <div className={`text-xs ${positive ? "text-green-500" : "text-red-500"}`}>
                      günlük
                    </div>
                  </div>
                )}
                {!change && (
                  <div className="text-right shrink-0">
                    <div className={`text-sm font-mono font-bold ${positive ? "text-green-600" : "text-red-600"}`}>
                      {positive ? "+" : ""}{stat.avg_change.toFixed(2)}%
                    </div>
                    <div className="text-xs text-neutral-400">ort.</div>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </CardContent>
    </Card>
  );
}
