"use client";

import { TrendingUp, TrendingDown, PieChart, BarChart2, Users, Activity, CalendarDays, Coins } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";

interface DashboardStats {
  total: number;
  total_market_cap: number;
  avg_daily_change: number;
  latest_date: string;
  trading_days: number;
  gemini_funds: number;
  gemini_holdings: number;
  top_gainer: { code: string; name: string; change: number } | null;
  top_loser: { code: string; name: string; change: number } | null;
}

interface DashboardStatsProps {
  stats: DashboardStats | null;
}

function fmtMoney(n: number): string {
  if (n >= 1e12) return `${(n / 1e12).toFixed(2)}T`;
  if (n >= 1e9) return `${(n / 1e9).toFixed(1)}B`;
  if (n >= 1e6) return `${(n / 1e6).toFixed(1)}M`;
  return n.toLocaleString("tr-TR");
}

function fmtDate(s: string): string {
  if (!s) return "—";
  return new Date(s).toLocaleDateString("tr-TR", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  });
}

export default function DashboardStats({ stats }: DashboardStatsProps) {
  if (!stats) return null;

  const changePositive = stats.avg_daily_change >= 0;

  return (
    <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
      {/* Toplam Fon */}
      <div className="rounded-xl bg-white border border-neutral-200 p-4 hover:shadow-sm transition">
        <div className="flex items-center gap-2 mb-2">
          <div className="w-8 h-8 rounded-lg bg-blue-50 flex items-center justify-center">
            <BarChart2 className="w-4 h-4 text-blue-600" />
          </div>
          <span className="text-xs font-medium text-neutral-500">Toplam Fon</span>
        </div>
        <div className="text-2xl font-bold font-mono text-neutral-900">{stats.total.toLocaleString("tr-TR")}</div>
        <div className="text-xs text-neutral-400 mt-0.5">adet fon</div>
      </div>

      {/* Toplam Fon Büyüklüğü */}
      <div className="rounded-xl bg-white border border-neutral-200 p-4 hover:shadow-sm transition">
        <div className="flex items-center gap-2 mb-2">
          <div className="w-8 h-8 rounded-lg bg-violet-50 flex items-center justify-center">
            <Coins className="w-4 h-4 text-violet-600" />
          </div>
          <span className="text-xs font-medium text-neutral-500">Fon Büyüklüğü</span>
        </div>
        <div className="text-2xl font-bold font-mono text-neutral-900">{fmtMoney(stats.total_market_cap)}</div>
        <div className="text-xs text-neutral-400 mt-0.5">₺</div>
      </div>

      {/* Ortalama Günlük Değişim */}
      <div className="rounded-xl bg-white border border-neutral-200 p-4 hover:shadow-sm transition">
        <div className="flex items-center gap-2 mb-2">
          <div className={`w-8 h-8 rounded-lg flex items-center justify-center ${changePositive ? "bg-green-50" : "bg-red-50"}`}>
            {changePositive ? (
              <TrendingUp className="w-4 h-4 text-green-600" />
            ) : (
              <TrendingDown className="w-4 h-4 text-red-600" />
            )}
          </div>
          <span className="text-xs font-medium text-neutral-500">Ort. Günlük Değişim</span>
        </div>
        <div className={`text-2xl font-bold font-mono ${changePositive ? "text-green-600" : "text-red-600"}`}>
          {changePositive ? "+" : ""}{stats.avg_daily_change.toFixed(3)}%
        </div>
        <div className="text-xs text-neutral-400 mt-0.5">tüm fonlar</div>
      </div>

      {/* Veri Tarihi */}
      <div className="rounded-xl bg-white border border-neutral-200 p-4 hover:shadow-sm transition">
        <div className="flex items-center gap-2 mb-2">
          <div className="w-8 h-8 rounded-lg bg-amber-50 flex items-center justify-center">
            <CalendarDays className="w-4 h-4 text-amber-600" />
          </div>
          <span className="text-xs font-medium text-neutral-500">Son Veri</span>
        </div>
        <div className="text-xl font-bold text-neutral-900">{fmtDate(stats.latest_date)}</div>
        <div className="text-xs text-neutral-400 mt-0.5">{stats.trading_days} işlem günü</div>
      </div>

      {/* Parsed Fon */}
      <div className="rounded-xl bg-white border border-neutral-200 p-4 hover:shadow-sm transition">
        <div className="flex items-center gap-2 mb-2">
          <div className="w-8 h-8 rounded-lg bg-emerald-50 flex items-center justify-center">
            <Activity className="w-4 h-4 text-emerald-600" />
          </div>
          <span className="text-xs font-medium text-neutral-500">KAP Parsed</span>
        </div>
        <div className="text-2xl font-bold font-mono text-neutral-900">{stats.gemini_funds.toLocaleString("tr-TR")}</div>
        <div className="text-xs text-neutral-400 mt-0.5">fon ({stats.gemini_holdings.toLocaleString("tr-TR")} holding)</div>
      </div>

      {/* En Çok Yükselen */}
      {stats.top_gainer && (
        <div className="rounded-xl bg-gradient-to-br from-green-50 to-emerald-50 border border-green-200 p-4 hover:shadow-sm transition">
          <div className="flex items-center gap-2 mb-2">
            <div className="w-8 h-8 rounded-lg bg-green-100 flex items-center justify-center">
              <TrendingUp className="w-4 h-4 text-green-700" />
            </div>
            <span className="text-xs font-medium text-green-700">En Çok Yükselen</span>
          </div>
          <div className="text-lg font-bold font-mono text-green-800">{stats.top_gainer.code}</div>
          <div className="text-xs text-green-600 mt-0.5 truncate" title={stats.top_gainer.name}>
            {stats.top_gainer.name}
          </div>
          <div className="text-sm font-bold text-green-700 mt-1">
            +{stats.top_gainer.change.toFixed(2)}%
          </div>
        </div>
      )}

      {/* En Çok Düşen */}
      {stats.top_loser && (
        <div className="rounded-xl bg-gradient-to-br from-red-50 to-orange-50 border border-red-200 p-4 hover:shadow-sm transition">
          <div className="flex items-center gap-2 mb-2">
            <div className="w-8 h-8 rounded-lg bg-red-100 flex items-center justify-center">
              <TrendingDown className="w-4 h-4 text-red-700" />
            </div>
            <span className="text-xs font-medium text-red-700">En Çok Düşen</span>
          </div>
          <div className="text-lg font-bold font-mono text-red-800">{stats.top_loser.code}</div>
          <div className="text-xs text-red-600 mt-0.5 truncate" title={stats.top_loser.name}>
            {stats.top_loser.name}
          </div>
          <div className="text-sm font-bold text-red-700 mt-1">
            {stats.top_loser.change.toFixed(2)}%
          </div>
        </div>
      )}
    </div>
  );
}
