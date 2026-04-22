"use client";

import { useState, useMemo } from "react";
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, ReferenceLine
} from "recharts";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { TrendingUp } from "lucide-react";

interface PricePoint {
  date: string;
  price: number;
  change?: number;
}

interface BenchmarkPoint {
  date: string;
  price: number;
}

interface BenchmarkData {
  [key: string]: BenchmarkPoint[];
}

type Period = "1H" | "1A" | "3A" | "6A" | "YBB" | "1Y";
type Benchmark = "none" | "BIST100" | "SP500" | "NASDAQ" | "USDTRY" | "GOLD" | "BTCUSD" | "ETHUSD";

const BENCHMARK_CONFIG: Record<Exclude<Benchmark, "none">, { label: string; shortLabel: string; color: string }> = {
  BIST100:  { label: "BIST 100",  shortLabel: "BIST",  color: "#6366f1" },
  SP500:    { label: "S&P 500",   shortLabel: "S&P",   color: "#16a34a" },
  NASDAQ:   { label: "Nasdaq",    shortLabel: "Nasdaq", color: "#0891b2" },
  USDTRY:   { label: "USD/TRY",   shortLabel: "$/₺",   color: "#9333ea" },
  GOLD:     { label: "Altın",     shortLabel: "Au",     color: "#eab308" },
  BTCUSD:   { label: "Bitcoin",   shortLabel: "BTC",    color: "#f97316" },
  ETHUSD:   { label: "Ethereum", shortLabel: "ETH",    color: "#8b5cf6" },
};

const BENCHMARK_TOGGLES: Array<{ key: Exclude<Benchmark, "none">; color: string }> = [
  { key: "GOLD",    color: "#eab308" },
  { key: "BTCUSD",  color: "#f97316" },
  { key: "ETHUSD",  color: "#8b5cf6" },
  { key: "SP500",   color: "#16a34a" },
  { key: "NASDAQ",  color: "#0891b2" },
  { key: "BIST100", color: "#6366f1" },
  { key: "USDTRY",  color: "#9333ea" },
];

const PERIODS: { key: Period; label: string; days: number }[] = [
  { key: "1H",  label: "1H",  days: 7   },
  { key: "1A",  label: "1A",  days: 21  },
  { key: "3A",  label: "3A",  days: 63  },
  { key: "6A",  label: "6A",  days: 126 },
  { key: "YBB", label: "YBB", days: 9999 },
  { key: "1Y",  label: "1Y",  days: 252 },
];

function fmtDate(s: string): string {
  const d = new Date(s);
  return d.toLocaleDateString("tr-TR", { day: "2-digit", month: "short" });
}

function fmtDateFull(s: string): string {
  const d = new Date(s);
  return d.toLocaleDateString("tr-TR", { day: "2-digit", month: "2-digit", year: "numeric" });
}

interface FundChartProps {
  priceHistory: PricePoint[];
  name: string;
  code: string;
  benchmarks?: BenchmarkData;
}

interface CustomTooltipProps {
  active?: boolean;
  payload?: Array<{ value: number; payload: PricePoint & { _benchmark?: number; _benchLabel?: string; _benchColor?: string } }>;
  label?: string;
  benchmark?: Exclude<Benchmark, "none">;
}

function CustomTooltip({ active, payload, benchmark }: CustomTooltipProps) {
  if (!active || !payload?.length) return null;
  const point = payload[0].payload;
  const change = payload[0].value;
  const benchChange = point._benchmark;
  const benchLabel = point._benchLabel;
  const benchColor = point._benchColor;
  return (
    <div className="bg-white border border-neutral-200 rounded-lg shadow-lg px-3 py-2 text-xs min-w-[160px]">
      <div className="font-medium text-neutral-700 mb-1.5">{fmtDateFull(point.date)}</div>
      <div className="font-mono font-bold text-neutral-900 text-sm mb-1">
        {change >= 0 ? "+" : ""}{change.toFixed(2)}%
      </div>
      {benchChange != null && benchmark && (
        <div className="flex items-center justify-between mt-1 pt-1.5 border-t border-neutral-100">
          <span className="text-neutral-500">{benchLabel}</span>
          <span className={`font-mono font-semibold ${benchChange >= 0 ? "text-green-600" : "text-red-600"}`}>
            {benchChange >= 0 ? "+" : ""}{benchChange.toFixed(2)}%
          </span>
        </div>
      )}
    </div>
  );
}

function normalizeToIndex(data: PricePoint[], daysBack: number): (PricePoint & { index: number })[] {
  if (!data || data.length < 2) return [];
  const sorted = [...data].sort((a, b) => a.date.localeCompare(b.date));
  const today = sorted[sorted.length - 1].date;
  const cutoff = new Date(today);
  cutoff.setDate(cutoff.getDate() - daysBack);
  const cutoffStr = cutoff.toISOString().split("T")[0];
  const slice = sorted.filter(p => p.date >= cutoffStr);
  if (slice.length < 2) return [];
  const base = slice[0].price;
  if (base === 0) return [];
  return slice.map(p => ({ ...p, index: ((p.price - base) / base) * 100 }));
}

export default function FundChart({ priceHistory, name, code, benchmarks }: FundChartProps) {
  const [period, setPeriod] = useState<Period>("1Y");
  const [benchmark, setBenchmark] = useState<Benchmark>("none");

  const periodDays = useMemo(() => {
    return PERIODS.find(p => p.key === period)?.days ?? 252;
  }, [period]);

  const filtered = useMemo(() => {
    if (!priceHistory?.length) return [];
    const sorted = [...priceHistory].sort((a, b) => a.date.localeCompare(b.date));
    if (period === "YBB") {
      const year = new Date().getFullYear();
      const ytdStart = `${year}-01-01`;
      return sorted.filter(p => p.date >= ytdStart);
    }
    const today = sorted[sorted.length - 1]?.date || "";
    const cutoff = new Date(today);
    cutoff.setDate(cutoff.getDate() - periodDays);
    const cutoffStr = cutoff.toISOString().split("T")[0];
    return sorted.filter(p => p.date >= cutoffStr);
  }, [priceHistory, period, periodDays]);

  const indexedFund = useMemo(() => {
    if (filtered.length < 2) return [];
    const base = filtered[0].price;
    if (base === 0) return [];
    return filtered.map(p => ({ ...p, index: ((p.price - base) / base) * 100 }));
  }, [filtered]);

  const indexedBench = useMemo(() => {
    if (!benchmarks || benchmark === "none") return null;
    const benchData = benchmarks[benchmark];
    if (!benchData?.length) return null;
    return normalizeToIndex(benchData as PricePoint[], periodDays);
  }, [benchmarks, benchmark, periodDays]);

  const chartData = useMemo(() => {
    if (!indexedFund.length) return [];
    const benchMap = new Map<string, number>();
    if (indexedBench) {
      for (const p of indexedBench) benchMap.set(p.date, p.index);
    }
    return indexedFund.map(p => {
      const benchVal = benchMap.get(p.date);
      const config = benchmark !== "none" ? BENCHMARK_CONFIG[benchmark] : null;
      return {
        ...p,
        _benchmark: benchVal != null ? benchVal : undefined,
        _benchLabel: benchVal != null ? config?.label : undefined,
        _benchColor: benchVal != null ? config?.color : undefined,
      };
    });
  }, [indexedFund, indexedBench, benchmark]);

  const stats = useMemo(() => {
    if (filtered.length < 2) return null;
    const first = filtered[0].price;
    const last = filtered[filtered.length - 1].price;
    const high = Math.max(...filtered.map(p => p.price));
    const low = Math.min(...filtered.map(p => p.price));
    const change = first > 0 ? ((last - first) / first) * 100 : 0;
    return { first, last, high, low, change, positive: change >= 0 };
  }, [filtered]);

  const benchStats = useMemo(() => {
    if (!indexedBench || indexedBench.length < 2) return null;
    const first = indexedBench[0].price;
    const last = indexedBench[indexedBench.length - 1].price;
    return first > 0 ? ((last - first) / first) * 100 : 0;
  }, [indexedBench]);

  const hasBench = benchmark !== "none" && benchStats !== null;

  if (!priceHistory?.length) {
    return (
      <Card>
        <CardContent className="p-6 text-center text-neutral-400">
          <TrendingUp className="w-8 h-8 mx-auto mb-2 opacity-30" />
          <div className="text-sm">Fiyat geçmişi yok</div>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardContent className="p-3 sm:p-4">
        {/* Header */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 mb-3">
          <div>
            <div className="flex items-center gap-2">
              <TrendingUp className="w-3.5 h-3.5 text-neutral-400" />
              <span className="text-xs sm:text-sm font-semibold text-neutral-700">
                {stats && (
                  <span className={`font-bold ${stats.positive ? "text-green-600" : "text-red-600"}`}>
                    {stats.positive ? "+" : ""}{stats.change.toFixed(2)}%
                  </span>
                )}
                {" "}
                <span className="font-normal text-neutral-400 text-xs hidden sm:inline">
                  {filtered.length} gün
                </span>
              </span>
              {hasBench && benchStats !== null && (
                <Badge variant="outline" className={`text-xs font-semibold hidden sm:inline-flex ${benchStats >= 0 ? "border-green-200 text-green-700" : "border-red-200 text-red-700"}`}>
                  {BENCHMARK_CONFIG[benchmark]?.label}: {benchStats >= 0 ? "+" : ""}{benchStats.toFixed(1)}%
                </Badge>
              )}
            </div>
          </div>

          {/* Controls */}
          <div className="flex flex-col gap-1.5">
            {/* Period selector */}
            <div className="flex gap-0.5">
              {PERIODS.map(p => (
                <button
                  key={p.key}
                  onClick={() => setPeriod(p.key)}
                  className={`px-1.5 py-0.5 rounded text-[10px] sm:text-xs font-medium transition whitespace-nowrap ${
                    period === p.key
                      ? "bg-blue-600 text-white"
                      : "bg-neutral-100 text-neutral-600 hover:bg-neutral-200"
                  }`}
                >
                  {p.key}
                </button>
              ))}
            </div>
            {/* Benchmark selector */}
            <div className="flex gap-0.5">
              <button
                onClick={() => setBenchmark("none")}
                className={`px-1.5 py-0.5 rounded text-[10px] sm:text-xs font-medium transition whitespace-nowrap ${
                  benchmark === "none" ? "bg-neutral-800 text-white" : "bg-neutral-100 text-neutral-600 hover:bg-neutral-200"
                }`}
              >
                Sadece Fon
              </button>
              {BENCHMARK_TOGGLES.map(({ key, color }) => (
                <button
                  key={key}
                  onClick={() => setBenchmark(key)}
                  className={`px-1.5 py-0.5 rounded text-[10px] sm:text-xs font-medium transition whitespace-nowrap ${
                    benchmark === key ? "text-white" : "bg-neutral-100 text-neutral-600 hover:bg-neutral-200"
                  }`}
                  style={benchmark === key ? { backgroundColor: color } : {}}
                >
                  {BENCHMARK_CONFIG[key].shortLabel}
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* Chart */}
        {indexedFund.length > 1 ? (
          <>
            <div className="h-48 sm:h-72">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={chartData} margin={{ top: 5, right: 5, bottom: 0, left: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" vertical={false} />
                  <XAxis
                    dataKey="date"
                    tickFormatter={fmtDate}
                    tick={{ fontSize: 10, fill: "#9ca3af" }}
                    tickLine={false}
                    axisLine={false}
                    interval="preserveStartEnd"
                  />
                  <YAxis
                    tick={{ fontSize: 10, fill: "#9ca3af" }}
                    tickLine={false}
                    axisLine={false}
                    tickFormatter={(v) => `${v >= 0 ? "+" : ""}${v.toFixed(1)}%`}
                    domain={["auto", "auto"]}
                    width={52}
                  />
                  <Tooltip
                    content={<CustomTooltip benchmark={benchmark !== "none" ? benchmark as Exclude<Benchmark, "none"> : undefined} />}
                  />
                  <ReferenceLine y={0} stroke="#d1d5db" strokeDasharray="4 4" />
                  {/* Fund line */}
                  <Line
                    type="monotone"
                    dataKey="index"
                    stroke={stats?.positive ? "#16a34a" : "#dc2626"}
                    strokeWidth={2}
                    dot={false}
                    activeDot={{ r: 4, fill: stats?.positive ? "#16a34a" : "#dc2626" }}
                    name="Fon"
                  />
                  {/* Benchmark line */}
                  {benchmark !== "none" && indexedBench && indexedBench.length > 0 && (
                    <Line
                      type="monotone"
                      dataKey="_benchmark"
                      stroke={BENCHMARK_CONFIG[benchmark].color}
                      strokeWidth={1.5}
                      strokeDasharray="5 3"
                      dot={false}
                      activeDot={{ r: 3, fill: BENCHMARK_CONFIG[benchmark].color }}
                      name={BENCHMARK_CONFIG[benchmark].label}
                    />
                  )}
                </LineChart>
              </ResponsiveContainer>
            </div>

            {/* Legend */}
            <div className="flex items-center justify-center gap-4 mt-2 text-xs">
              <span className="flex items-center gap-1.5">
                <span className={`w-3 h-0.5 rounded-full ${stats?.positive ? "bg-green-500" : "bg-red-500"}`} />
                <span className="text-neutral-600">Fon</span>
              </span>
              {benchmark !== "none" && (
                <span className="flex items-center gap-1.5">
                  <span className="w-3 h-0.5 rounded-full border-dashed" style={{ borderTop: `2px dashed ${BENCHMARK_CONFIG[benchmark].color}` }} />
                  <span className="text-neutral-600">{BENCHMARK_CONFIG[benchmark].label}</span>
                  {benchStats !== null && (
                    <span className={`font-semibold ${benchStats >= 0 ? "text-green-600" : "text-red-600"}`}>
                      {benchStats >= 0 ? "+" : ""}{benchStats.toFixed(1)}%
                    </span>
                  )}
                </span>
              )}
            </div>

            {/* Stats row */}
            {stats && (
              <div className="grid grid-cols-4 gap-1 sm:gap-2 mt-3 pt-3 border-t border-neutral-100">
                <div className="text-center">
                  <div className="text-[10px] sm:text-xs text-neutral-400">Açılış</div>
                  <div className="font-mono text-[11px] sm:text-sm font-semibold text-neutral-700 truncate">{stats.first.toFixed(4)}</div>
                </div>
                <div className="text-center">
                  <div className="text-[10px] sm:text-xs text-neutral-400">En Yüksek</div>
                  <div className="font-mono text-[11px] sm:text-sm font-semibold text-green-600 truncate">{stats.high.toFixed(4)}</div>
                </div>
                <div className="text-center">
                  <div className="text-[10px] sm:text-xs text-neutral-400">En Düşük</div>
                  <div className="font-mono text-[11px] sm:text-sm font-semibold text-red-600 truncate">{stats.low.toFixed(4)}</div>
                </div>
                <div className="text-center">
                  <div className="text-[10px] sm:text-xs text-neutral-400">Kapanış</div>
                  <div className="font-mono text-[11px] sm:text-sm font-semibold text-neutral-900 truncate">{stats.last.toFixed(4)}</div>
                </div>
              </div>
            )}
          </>
        ) : (
          <div className="h-40 flex items-center justify-center text-neutral-400 text-sm">
            Bu periyot için yeterli veri yok
          </div>
        )}
      </CardContent>
    </Card>
  );
}
