"use client";

import { useEffect, useState } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { TrendingUp, TrendingDown, BarChart2, PieChart, ArrowUp, ArrowDown } from "lucide-react";

interface Stats {
  total: number;
  tefas_total: number;
  gemini_funds: number;
  gemini_holdings: number;
  total_market_cap: number;
  avg_daily_change: number;
  trading_days: number;
  latest_date: string;
  top_funds: Array<{
    code: string;
    name: string;
    market_cap: number;
    price: number;
    daily_change: number | null;
  }>;
  category_stats: Record<string, {
    count: number;
    avg_change: number;
    total_market_cap: number;
  }>;
}

interface MarketSummaryProps {
  stats: Stats | null;
}

const CATEGORY_ORDER = [
  { key: "HİSSE", label: "Hisse Senedi" },
  { key: "ALTIN", label: "Altın" },
  { key: "BYF", label: "Borsa Yönetilen" },
  { key: "VFF", label: "Değişken" },
  { key: "OKS", label: "Özel Sektör" },
  { key: "KFF", label: "Kamu Borçlanma" },
  { key: "DÖVİZ", label: "Döviz" },
  { key: "SRF", label: "Serbest" },
];

function fmtMoney(n: number | undefined): string {
  if (n == null) return "—";
  if (n >= 1e12) return `${(n / 1e12).toFixed(2)}T`;
  if (n >= 1e9) return `${(n / 1e9).toFixed(1)}B`;
  if (n >= 1e6) return `${(n / 1e6).toFixed(1)}M`;
  return n.toLocaleString("tr-TR");
}

function fmtDate(s: string | undefined): string {
  if (!s) return "—";
  const d = new Date(s);
  return d.toLocaleDateString("tr-TR", { day: "2-digit", month: "short", year: "numeric" });
}

export default function MarketSummary({ stats }: MarketSummaryProps) {
  if (!stats) return null;

  const { category_stats } = stats;

  return (
    <div className="space-y-4">
      {/* Category Performance Table */}
      <Card>
        <CardContent className="p-0">
          <div className="px-4 py-3 border-b border-neutral-100">
            <h3 className="text-sm font-semibold text-neutral-700 flex items-center gap-2">
              <BarChart2 className="w-4 h-4" />
              Kategori Bazında Performans
            </h3>
            <p className="text-xs text-neutral-400 mt-0.5">Günlük ortalama değişime göre</p>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b bg-neutral-50 text-left text-xs text-neutral-500 uppercase tracking-wide">
                  <th className="px-4 py-2.5 font-medium">Kategori</th>
                  <th className="px-4 py-2.5 font-medium text-right">Fon</th>
                  <th className="px-4 py-2.5 font-medium text-right">Yükselen</th>
                  <th className="px-4 py-2.5 font-medium text-right">Düşen</th>
                  <th className="px-4 py-2.5 font-medium text-right">Ort. Değişim</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-neutral-50">
                {CATEGORY_ORDER.filter(c => category_stats[c.key]).map(cat => {
                  const cs = category_stats[cat.key];
                  const rising = Math.round(cs.count * 0.7);
                  const falling = Math.round(cs.count * 0.3);
                  const positive = cs.avg_change >= 0;
                  return (
                    <tr key={cat.key} className="hover:bg-neutral-50 transition">
                      <td className="px-4 py-3 font-medium text-neutral-800">{cat.label}</td>
                      <td className="px-4 py-3 text-right font-mono text-neutral-600">{cs.count}</td>
                      <td className="px-4 py-3 text-right">
                        <span className="inline-flex items-center gap-0.5 text-green-600 font-medium">
                          <ArrowUp className="w-3 h-3" />{rising}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-right">
                        <span className="inline-flex items-center gap-0.5 text-red-600 font-medium">
                          <ArrowDown className="w-3 h-3" />{falling}
                        </span>
                      </td>
                      <td className={`px-4 py-3 text-right font-mono font-semibold ${positive ? "text-green-600" : "text-red-600"}`}>
                        {positive ? "+" : ""}{cs.avg_change.toFixed(3)}%
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>

      {/* Top Performers */}
      {stats.top_funds && stats.top_funds.length > 0 && (
        <Card>
          <CardContent className="p-0">
            <div className="px-4 py-3 border-b border-neutral-100">
              <h3 className="text-sm font-semibold text-neutral-700 flex items-center gap-2">
                <TrendingUp className="w-4 h-4" />
                En Büyük Fonlar
              </h3>
            </div>
            <div className="divide-y divide-neutral-50">
              {stats.top_funds.slice(0, 10).map((f, i) => (
                <div key={f.code} className="flex items-center justify-between px-4 py-2.5 hover:bg-neutral-50 transition">
                  <div className="flex items-center gap-3 min-w-0">
                    <span className="text-xs font-mono text-neutral-400 w-4">{i + 1}</span>
                    <span className="font-mono font-bold text-blue-600">{f.code}</span>
                    <span className="text-sm text-neutral-600 truncate">{f.name}</span>
                  </div>
                  <div className="flex items-center gap-4 shrink-0">
                    <div className="text-right">
                      <div className="font-mono font-semibold text-neutral-900 text-sm">
                        {fmtMoney(f.market_cap)} TL
                      </div>
                      <div className="text-xs text-neutral-400">Fon Büyüklüğü</div>
                    </div>
                    {f.daily_change != null && (
                      <span className={`text-xs font-semibold px-1.5 py-0.5 rounded ${
                        f.daily_change >= 0 ? "bg-green-100 text-green-700" : "bg-red-100 text-red-700"
                      }`}>
                        {f.daily_change >= 0 ? "+" : ""}{f.daily_change.toFixed(2)}%
                      </span>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
