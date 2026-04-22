"use client";

import { useMemo } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { TrendingUp, TrendingDown, BarChart2 } from "lucide-react";

interface PricePoint {
  date: string;
  price: number;
  change?: number;
}

interface ReturnsTableProps {
  priceHistory: PricePoint[];
  currentPrice: number | null;
}

interface ReturnRow {
  label: string;
  value: number | null;
}

export default function ReturnsTable({ priceHistory, currentPrice }: ReturnsTableProps) {
  const returns = useMemo((): ReturnRow[] => {
    if (!priceHistory?.length || priceHistory.length < 2) {
      return [];
    }

    const sorted = [...priceHistory].sort((a, b) => a.date.localeCompare(b.date));
    const prices = sorted.map(p => ({ date: p.date, price: p.price }));

    function getReturn(daysBack: number): number | null {
      if (prices.length < 2) return null;
      const targetIdx = prices.length - 1 - daysBack;
      if (targetIdx < 0) return null;
      const startPrice = prices[targetIdx]?.price;
      if (!startPrice || startPrice === 0) return null;
      const lastPrice = prices[prices.length - 1]?.price;
      if (!lastPrice) return null;
      return ((lastPrice - startPrice) / startPrice) * 100;
    }

    const year = new Date().getFullYear();
    const ybbIdx = prices.findIndex(p => p.date >= `${year}-01-01`);
    const ybbReturn = ybbIdx >= 0
      ? (() => {
          const start = prices[ybbIdx].price;
          const last = prices[prices.length - 1].price;
          return start > 0 ? ((last - start) / start) * 100 : null;
        })()
      : null;

    return [
      { label: "Günlük", value: getReturn(1) },
      { label: "Haftalık", value: getReturn(5) },
      { label: "1 Aylık", value: getReturn(21) },
      { label: "3 Aylık", value: getReturn(63) },
      { label: "6 Aylık", value: getReturn(126) },
      { label: "Yılbaşından", value: ybbReturn },
      { label: "1 Yıllık", value: getReturn(252) },
    ];
  }, [priceHistory]);

  if (returns.length === 0) {
    return (
      <Card>
        <CardContent className="p-4 text-center text-neutral-400">
          <BarChart2 className="w-6 h-6 mx-auto mb-1 opacity-30" />
          <div className="text-sm">Getiri verisi yok</div>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardContent className="p-4">
        <h3 className="text-sm font-semibold text-neutral-700 mb-3 flex items-center gap-2">
          <BarChart2 className="w-4 h-4" />
          Dönemsel Getiriler
        </h3>
        <div className="grid grid-cols-4 sm:grid-cols-4 gap-1.5">
          {returns.map(r => (
            <div key={r.label} className="text-center py-1.5 px-1 rounded-lg bg-neutral-50 hover:bg-neutral-100 transition">
              <div className="text-xs text-neutral-400 mb-0.5">{r.label}</div>
              {r.value !== null ? (
                <div className={`flex items-center justify-center gap-0.5 font-mono font-bold text-xs ${
                  r.value >= 0 ? "text-green-600" : "text-red-600"
                }`}>
                  {r.value >= 0
                    ? <TrendingUp className="w-2.5 h-2.5 shrink-0" />
                    : <TrendingDown className="w-2.5 h-2.5 shrink-0" />
                  }
                  <span>{r.value >= 0 ? "+" : ""}{r.value.toFixed(1)}%</span>
                </div>
              ) : (
                <div className="text-xs text-neutral-300">—</div>
              )}
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}
