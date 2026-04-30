"use client";

import { PieChart, ChevronRight } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";

interface MostHeldStock {
  ticker: string;
  company: string;
  total_weight: number;
  fund_count: number;
}

interface MostHeldStocksProps {
  stocks: MostHeldStock[];
}

export default function MostHeldStocks({ stocks }: MostHeldStocksProps) {
  return (
    <Card>
      <CardContent className="p-0">
        <div className="px-4 py-3 border-b border-neutral-100 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <PieChart className="w-4 h-4 text-violet-600" />
            <h3 className="text-sm font-semibold text-neutral-700">En Çok Tutulan Hisseler</h3>
          </div>
          <span className="text-xs text-neutral-400">tüm fonlarda</span>
        </div>
        <div className="divide-y divide-neutral-50">
          {stocks.slice(0, 10).map((s) => (
            <div
              key={s.ticker}
              className="flex items-center gap-3 px-4 py-2.5"
            >
              <span className="w-6 h-6 rounded bg-violet-100 text-violet-700 text-xs font-bold flex items-center justify-center shrink-0">
                {s.ticker.slice(0, 2)}
              </span>
              <div className="flex-1 min-w-0">
                <div className="text-sm font-medium text-neutral-800 truncate">{s.company || s.ticker}</div>
                <div className="text-xs text-neutral-400">{s.fund_count} fonun portföyünde</div>
              </div>
              <div className="text-right shrink-0">
                <div className="text-sm font-mono font-bold text-violet-700">
                  {s.total_weight.toFixed(1)}%
                </div>
                <div className="text-xs text-neutral-400">ağırlık</div>
              </div>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}
