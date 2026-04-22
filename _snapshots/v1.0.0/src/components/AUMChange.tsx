"use client";

import { TrendingUp, TrendingDown } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";

interface AUMChangeProps {
  totalAum: number;
  aumChangeWeek: number | null;
  aumChangeMonth: number | null;
  aumChangeQuarter: number | null;
}

function fmtMoney(n: number): string {
  if (n >= 1e12) return `${(n / 1e12).toFixed(2)}T`;
  if (n >= 1e9) return `${(n / 1e9).toFixed(1)}B`;
  if (n >= 1e6) return `${(n / 1e6).toFixed(1)}M`;
  return n.toLocaleString("tr-TR");
}

export default function AUMChange({ totalAum, aumChangeWeek, aumChangeMonth, aumChangeQuarter }: AUMChangeProps) {
  return (
    <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
      {[
        { label: "1 Hafta", value: aumChangeWeek, icon: TrendingUp },
        { label: "1 Ay", value: aumChangeMonth, icon: TrendingUp },
        { label: "3 Ay", value: aumChangeQuarter, icon: TrendingUp },
      ].map(({ label, value, icon: Icon }) => {
        const positive = (value || 0) >= 0;
        const color = positive ? "text-green-600" : "text-red-600";
        const bg = positive ? "bg-green-50 border-green-100" : "bg-red-50 border-red-100";
        return (
          <div
            key={label}
            className={`rounded-xl border px-4 py-3 ${bg}`}
          >
            <div className="flex items-center gap-1.5 mb-1">
              <Icon className={`w-3.5 h-3.5 ${color}`} />
              <span className="text-xs font-medium text-neutral-500">Fon Büyüklüğü ({label})</span>
            </div>
            <div className={`text-xl font-bold font-mono ${color}`}>
              {value != null
                ? `${positive ? "+" : ""}${value.toFixed(2)}%`
                : "—"}
            </div>
          </div>
        );
      })}
    </div>
  );
}
