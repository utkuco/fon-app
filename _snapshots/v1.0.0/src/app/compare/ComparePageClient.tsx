"use client";

import { useSearchParams, useRouter } from "next/navigation";
import { Suspense, useMemo, useState, useEffect } from "react";
import Link from "next/link";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
} from "recharts";
import { ArrowLeft, X, TrendingUp, TrendingDown, BarChart2 } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";

interface Fund {
  code: string;
  name: string;
  fund_type: string;
  daily_change: number | null;
  market_cap: number | null;
  price: number | null;
  nav: number | null;
  price_history: Array<{ date: string; price: number }>;
}

interface CompareFund extends Fund {
  normalized: Array<{ date: string; value: number }>;
  returns: {
    "1H": number | null;
    "1A": number | null;
    "3A": number | null;
    "6A": number | null;
    YBB: number | null;
    "1Y": number | null;
  };
  rank: Record<string, { rank: number; total: number }> | null;
}

const TYPE_COLORS: Record<string, string> = {
  ALTIN: "bg-amber-100 text-amber-800 border-amber-200",
  DEĞİŞKEN: "bg-blue-100 text-blue-800 border-blue-200",
  ÖZEL_SEKTÖR: "bg-violet-100 text-violet-800 border-violet-200",
  SERBEST: "bg-emerald-100 text-emerald-800 border-emerald-200",
  DÖVİZ: "bg-cyan-100 text-cyan-800 border-cyan-200",
  "BORÇLANMA ARACI": "bg-orange-100 text-orange-800 border-orange-200",
  HİSSE: "bg-red-100 text-red-800 border-red-200",
  BYF: "bg-slate-100 text-slate-800 border-slate-200",
};

function getColor(i: number) {
  const colors = ["#3b82f6", "#10b981", "#f59e0b", "#ef4444", "#8b5cf6", "#ec4899"];
  return colors[i % colors.length];
}

function fmtMoney(n: number): string {
  if (n >= 1e12) return `${(n / 1e12).toFixed(2)}T`;
  if (n >= 1e9) return `${(n / 1e9).toFixed(1)}B`;
  if (n >= 1e6) return `${(n / 1e6).toFixed(1)}M`;
  return n.toLocaleString("tr-TR");
}

function fmtDate(s: string): string {
  return new Date(s).toLocaleDateString("tr-TR", {
    day: "2-digit",
    month: "short",
  });
}

export default function ComparePage() {
  return (
    <Suspense fallback={<div className="min-h-screen flex items-center justify-center text-neutral-400">Yükleniyor...</div>}>
      <ComparePageInner />
    </Suspense>
  );
}

function ComparePageInner() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const codesParam = searchParams.get("codes") || "";

  const [funds, setFunds] = useState<Fund[]>([]);
  const [loading, setLoading] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState<Fund[]>([]);
  const [benchmarks, setBenchmarks] = useState<Record<string, Array<{ date: string; price: number }>>>({});
  const [selectedBenchmarks, setSelectedBenchmarks] = useState<string[]>([]);

  // Load funds by codes from API
  useEffect(() => {
    if (!codesParam) return;
    setLoading(true);
    fetch(`/api/search?codes=${codesParam}`)
      .then((r) => r.json())
      .then((d) => {
        setFunds(d.funds || []);
        setBenchmarks(d.benchmarks || {});
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, [codesParam]);

  // Update page title
  useEffect(() => {
    if (funds.length > 0) {
      document.title = `${funds.map(f => f.code).join(" vs ")} — Karşılaştır | FonRapor`;
    } else {
      document.title = "Karşılaştır | FonRapor";
    }
  }, [funds]);

  // Search handler — use API
  function handleSearch(q: string) {
    setSearchQuery(q);
    if (!q.trim()) {
      setSearchResults([]);
      return;
    }
    fetch(`/api/search?q=${encodeURIComponent(q)}&limit=6`)
      .then((r) => r.json())
      .then((d) => {
        const results = (d.funds || []).filter(
          (f: Fund) => !funds.find((cf) => cf.code === f.code)
        );
        setSearchResults(results);
      });
  }

  function addFund(fund: Fund) {
    if (funds.length >= 6) return;
    const newFunds = [...funds, fund];
    setFunds(newFunds);
    setSearchQuery("");
    setSearchResults([]);
    router.replace(`/compare?codes=${newFunds.map((f) => f.code).join(",")}`);
  }

  function removeFund(code: string) {
    const newFunds = funds.filter((f) => f.code !== code);
    setFunds(newFunds);
    router.replace(
      newFunds.length ? `/compare?codes=${newFunds.map((f) => f.code).join(",")}` : "/compare"
    );
  }

  // Compute normalized prices & returns
  const compareFunds = useMemo((): CompareFund[] => {
    return funds.map((f) => {
      const history = [...(f.price_history || [])].sort((a, b) =>
        a.date.localeCompare(b.date)
      );

      function calc(days: number): number | null {
        if (history.length < 2) return null;
        const idx = history.length - 1 - days;
        if (idx < 0) return null;
        const start = history[idx]?.price;
        if (!start) return null;
        const end = history[history.length - 1]?.price;
        if (!end) return null;
        return ((end - start) / start) * 100;
      }

      const year = new Date().getFullYear();
      const ybbIdx = history.findIndex((p) => p.date >= `${year}-01-01`);
      const ybbReturn =
        ybbIdx >= 0
          ? (() => {
              const start = history[ybbIdx].price;
              const end = history[history.length - 1].price;
              return start > 0 ? ((end - start) / start) * 100 : null;
            })()
          : null;

      // Normalize to 100
      const base = history[0]?.price || 1;
      const normalized = history.map((p) => ({
        date: p.date,
        value: (p.price / base) * 100,
      }));

      // Get dates shared across all funds
      return {
        ...f,
        normalized,
        returns: {
          "1H": calc(5),
          "1A": calc(21),
          "3A": calc(63),
          "6A": calc(126),
          YBB: ybbReturn,
          "1Y": calc(252),
        },
        rank: null,
      };
    });
  }, [funds]);

  // Combined chart data (funds + selected benchmarks)
  const chartData = useMemo(() => {
    if (!compareFunds.length) return [];
    const allDates = new Set<string>();
    compareFunds.forEach((cf) =>
      cf.normalized.forEach((n) => allDates.add(n.date))
    );
    const sorted = Array.from(allDates).sort();
    return sorted.map((date) => {
      const point: Record<string, string | number> = { date: fmtDate(date) };
      compareFunds.forEach((cf) => {
        const entry = cf.normalized.find((n) => n.date === date);
        point[cf.code] = entry ? entry.value : NaN;
      });
      // Normalize selected benchmarks to match the fund date range
      selectedBenchmarks.forEach((sym) => {
        const bmData = benchmarks[sym];
        if (!bmData) return;
        const base = bmData[0]?.price || 1;
        const entry = bmData.find((p) => p.date === date);
        point[`bm_${sym}`] = entry ? (entry.price / base) * 100 : NaN;
      });
      return point;
    });
  }, [compareFunds, benchmarks, selectedBenchmarks]);

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-neutral-400">Yükleniyor...</div>
      </div>
    );
  }

  const allFunds = funds; // used in handleSearch results

  return (
    <div className="min-h-screen bg-neutral-50">
      {/* Header */}
      <div className="bg-white border-b border-neutral-200 sticky top-0 z-10">
        <div className="max-w-7xl mx-auto px-4 h-14 flex items-center gap-4">
          <Link
            href="/"
            className="flex items-center gap-1.5 text-sm text-neutral-500 hover:text-neutral-900 transition shrink-0"
          >
            <ArrowLeft className="w-4 h-4" />
            <span className="hidden sm:inline">Fonlar</span>
          </Link>
          <div className="flex items-center gap-2 shrink-0">
            <BarChart2 className="w-5 h-5 text-blue-600" />
            <h1 className="text-base font-bold text-neutral-900">Karşılaştırma</h1>
            {funds.length > 0 && (
              <span className="text-xs bg-blue-100 text-blue-700 px-2 py-0.5 rounded-full">
                {funds.length}/3
              </span>
            )}
          </div>
          {funds.length > 0 && (
            <button
              onClick={() => { setFunds([]); router.replace("/compare"); }}
              className="ml-auto flex items-center gap-1 text-xs text-neutral-400 hover:text-red-600 transition shrink-0"
            >
              <X className="w-3.5 h-3.5" />
              <span className="hidden sm:inline">Temizle</span>
            </button>
          )}
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-4 py-6 space-y-6">
        {/* Search */}
        <Card>
          <CardContent className="p-4">
            <div className="flex gap-2">
              <div className="relative flex-1">
                <Input
                  type="text"
                  value={searchQuery}
                  onChange={(e) => handleSearch(e.target.value)}
                  placeholder="Karşılaştırmak için fon ara..."
                  className="w-full px-3 py-2 text-sm border border-neutral-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                  disabled={funds.length >= 3}
                />
                {searchResults.length > 0 && (
                  <div className="absolute top-full left-0 right-0 mt-1 bg-white border border-neutral-200 rounded-lg shadow-lg z-20 overflow-hidden">
                    {searchResults.map((r) => (
                      <button
                        key={r.code}
                        onClick={() => addFund(r)}
                        className="w-full text-left px-3 py-2 text-sm hover:bg-neutral-50 border-b border-neutral-100 last:border-0"
                      >
                        <span className="font-mono font-bold text-blue-600 mr-2">
                          {r.code}
                        </span>
                        <span className="text-neutral-700 truncate">{r.name}</span>
                      </button>
                    ))}
                  </div>
                )}
              </div>
            </div>
            {funds.length >= 3 && (
              <p className="text-xs text-amber-600 mt-2">
                Maksimum 3 fon karşılaştırılabilir. Karşılaştırmak için bir fonu kaldırın.
              </p>
            )}
          </CardContent>
        </Card>

        {compareFunds.length === 0 ? (
          <Card>
            <CardContent className="p-12 text-center">
              <BarChart2 className="w-12 h-12 mx-auto mb-3 text-neutral-300" />
              <div className="text-neutral-500 font-medium">
                Karşılaştırmak için fon seçin
              </div>
              <div className="text-sm text-neutral-400 mt-1">
                Yukarıdaki arama kutusundan fon ara ve ekleyin
              </div>
            </CardContent>
          </Card>
        ) : (
          <>
            {/* Fund pills */}
            <div className="flex flex-wrap gap-2">
              {compareFunds.map((cf, i) => (
                <div
                  key={cf.code}
                  className="flex items-center gap-2 px-3 py-1.5 rounded-full text-sm font-medium"
                  style={{
                    backgroundColor: getColor(i) + "20",
                    color: getColor(i),
                    border: `1px solid ${getColor(i)}40`,
                  }}
                >
                  <span className="font-mono font-bold">{cf.code}</span>
                  <button
                    onClick={() => removeFund(cf.code)}
                    className="hover:opacity-70 transition"
                  >
                    <X className="w-3.5 h-3.5" />
                  </button>
                </div>
              ))}
            </div>

            {/* Price Chart */}
            <Card>
              <CardContent className="p-4">
                <div className="flex items-center justify-between mb-4">
                  <h3 className="text-sm font-semibold text-neutral-700">
                    Fiyat Performansı (Normalleştirilmiş, Başlangıç = 100)
                  </h3>
                  {/* Benchmark toggles */}
                  {Object.keys(benchmarks).length > 0 && (
                    <div className="flex items-center gap-1.5">
                      <span className="text-xs text-neutral-400">Benchmark:</span>
                      {Object.keys(benchmarks).map((sym) => {
                        const BM_COLORS: Record<string, string> = { USDTRY: "#3b82f6", SP500: "#10b981", NASDAQ: "#8b5cf6", EURUSD: "#f59e0b" };
                        const BM_LABELS: Record<string, string> = { USDTRY: "USD/TRY", SP500: "S&P 500", NASDAQ: "NASDAQ", EURUSD: "EUR/USD" };
                        const isActive = selectedBenchmarks.includes(sym);
                        return (
                          <button
                            key={sym}
                            onClick={() => setSelectedBenchmarks((prev) => isActive ? prev.filter((s) => s !== sym) : [...prev, sym])}
                            className={`text-xs px-2 py-1 rounded-full border transition font-medium ${
                              isActive
                                ? "border-current text-white"
                                : "border-neutral-200 text-neutral-400 hover:border-neutral-400"
                            }`}
                            style={isActive ? { backgroundColor: BM_COLORS[sym] || "#888", borderColor: BM_COLORS[sym] || "#888" } : {}}
                          >
                            {BM_LABELS[sym] || sym}
                          </button>
                        );
                      })}
                    </div>
                  )}
                </div>
                <div className="h-64">
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={chartData}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                      <XAxis
                        dataKey="date"
                        tick={{ fontSize: 11, fill: "#9ca3af" }}
                        interval="preserveStartEnd"
                      />
                      <YAxis
                        tick={{ fontSize: 11, fill: "#9ca3af" }}
                        tickFormatter={(v) => v.toFixed(0)}
                        domain={["auto", "auto"]}
                      />
                      <Tooltip
                        contentStyle={{
                          borderRadius: 8,
                          border: "1px solid #e5e7eb",
                          fontSize: 12,
                        }}
                        formatter={(value: unknown, name: unknown) => [
                          typeof value === "number" && !isNaN(value as number) ? `${(value as number).toFixed(2)}` : "—",
                          String(name),
                        ]}
                      />
                      {compareFunds.map((cf, i) => (
                        <Line
                          key={cf.code}
                          type="monotone"
                          dataKey={cf.code}
                          stroke={getColor(i)}
                          strokeWidth={2}
                          dot={false}
                          connectNulls
                        />
                      ))}
                      {selectedBenchmarks.map((sym) => {
                        const BM_COLORS: Record<string, string> = { USDTRY: "#3b82f6", SP500: "#10b981", NASDAQ: "#8b5cf6", EURUSD: "#f59e0b" };
                        return (
                          <Line
                            key={`bm_${sym}`}
                            type="monotone"
                            dataKey={`bm_${sym}`}
                            stroke={BM_COLORS[sym] || "#888"}
                            strokeWidth={1.5}
                            strokeDasharray="5 3"
                            dot={false}
                            connectNulls
                          />
                        );
                      })}
                    </LineChart>
                  </ResponsiveContainer>
                </div>
                {/* Legend */}
                <div className="flex flex-wrap gap-4 mt-3">
                  {compareFunds.map((cf, i) => (
                    <div key={cf.code} className="flex items-center gap-1.5">
                      <div
                        className="w-3 h-3 rounded-full"
                        style={{ backgroundColor: getColor(i) }}
                      />
                      <span className="text-xs font-mono font-bold" style={{ color: getColor(i) }}>
                        {cf.code}
                      </span>
                      <span className="text-xs text-neutral-500 truncate max-w-[150px]">
                        {cf.name}
                      </span>
                    </div>
                  ))}
                  {selectedBenchmarks.map((sym) => {
                    const BM_COLORS: Record<string, string> = { USDTRY: "#3b82f6", SP500: "#10b981", NASDAQ: "#8b5cf6", EURUSD: "#f59e0b" };
                    const BM_LABELS: Record<string, string> = { USDTRY: "USD/TRY", SP500: "S&P 500", NASDAQ: "NASDAQ", EURUSD: "EUR/USD" };
                    return (
                      <div key={`leg_${sym}`} className="flex items-center gap-1.5">
                        <div className="w-3 h-0.5 rounded-full" style={{ backgroundColor: BM_COLORS[sym] || "#888", borderTop: `2px dashed ${BM_COLORS[sym] || "#888"}` }} />
                        <span className="text-xs font-medium" style={{ color: BM_COLORS[sym] || "#888" }}>
                          {BM_LABELS[sym] || sym}
                        </span>
                      </div>
                    );
                  })}
                </div>
              </CardContent>
            </Card>

            {/* Returns Table */}
            <Card>
              <CardContent className="p-4">
                <h3 className="text-sm font-semibold text-neutral-700 mb-4">
                  Dönemsel Getiri Karşılaştırması
                </h3>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm min-w-[600px]">
                    <thead>
                      <tr className="border-b border-neutral-200">
                        <th className="text-left py-2 pr-4 font-medium text-neutral-500">Fon</th>
                        <th className="text-right py-2 px-2 font-medium text-neutral-500">Tür</th>
                        <th className="text-right py-2 px-2 font-medium text-neutral-500">Fiyat</th>
                        <th className="text-right py-2 px-2 font-medium text-neutral-500">Günlük</th>
                        <th className="text-right py-2 px-2 font-medium text-neutral-500">1H</th>
                        <th className="text-right py-2 px-2 font-medium text-neutral-500">1A</th>
                        <th className="text-right py-2 px-2 font-medium text-neutral-500">3A</th>
                        <th className="text-right py-2 px-2 font-medium text-neutral-500">6A</th>
                        <th className="text-right py-2 px-2 font-medium text-neutral-500">YBB</th>
                        <th className="text-right py-2 px-2 font-medium text-neutral-500">1Y</th>
                        <th className="text-right py-2 pl-3 font-medium text-neutral-500">AUM</th>
                      </tr>
                    </thead>
                    <tbody>
                      {compareFunds.map((cf, i) => (
                        <tr
                          key={cf.code}
                          className="border-b border-neutral-100 last:border-0 hover:bg-neutral-50"
                        >
                          <td className="py-3 pr-4">
                            <div className="flex items-center gap-2">
                              <div
                                className="w-2.5 h-2.5 rounded-full shrink-0"
                                style={{ backgroundColor: getColor(i) }}
                              />
                              <div>
                                <Link
                                  href={`/fon/${cf.code}`}
                                  className="font-mono font-bold text-blue-600 hover:underline"
                                >
                                  {cf.code}
                                </Link>
                                <div className="text-xs text-neutral-500 truncate max-w-[200px]">
                                  {cf.name}
                                </div>
                              </div>
                            </div>
                          </td>
                          <td className="text-right py-3 px-2">
                            <span
                              className={`inline-block px-2 py-0.5 rounded text-xs font-medium border ${
                                TYPE_COLORS[cf.fund_type] ||
                                "bg-neutral-100 text-neutral-700 border-neutral-200"
                              }`}
                            >
                              {cf.fund_type}
                            </span>
                          </td>
                          <td className="text-right py-3 px-2 font-mono">
                            {cf.price ? cf.price.toFixed(4) : "—"}
                          </td>
                          <td
                            className={`text-right py-3 px-2 font-mono font-bold ${
                              (cf.daily_change || 0) >= 0 ? "text-green-600" : "text-red-600"
                            }`}
                          >
                            {cf.daily_change != null
                              ? `${cf.daily_change >= 0 ? "+" : ""}${cf.daily_change.toFixed(2)}%`
                              : "—"}
                          </td>
                          {(["1H", "1A", "3A", "6A", "YBB", "1Y"] as const).map((key) => (
                            <td
                              key={key}
                              className={`text-right py-3 px-2 font-mono font-medium ${
                                (cf.returns[key] || 0) >= 0 ? "text-green-600" : "text-red-600"
                              }`}
                            >
                              {cf.returns[key] != null
                                ? `${cf.returns[key]! >= 0 ? "+" : ""}${cf.returns[key]!.toFixed(2)}%`
                                : "—"}
                            </td>
                          ))}
                          <td className="text-right py-3 pl-3 font-mono text-neutral-700">
                            {cf.market_cap ? fmtMoney(cf.market_cap) : "—"}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </CardContent>
            </Card>

            {/* Quick stats cards */}
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
              {compareFunds.map((cf, i) => (
                <div key={cf.code} className={`card-animate card-delay-${i + 1}`}>
                <Card>
                  <CardContent className="p-4">
                    <div className="flex items-center gap-2 mb-3">
                      <div
                        className="w-3 h-3 rounded-full"
                        style={{ backgroundColor: getColor(i) }}
                      />
                      <span className="font-mono font-bold text-neutral-900">{cf.code}</span>
                      <Link
                        href={`/fon/${cf.code}`}
                        className="ml-auto text-xs text-blue-600 hover:underline"
                      >
                        Detay →
                      </Link>
                    </div>
                    <div className="grid grid-cols-2 gap-3">
                      <div>
                        <div className="text-xs text-neutral-500">Fiyat</div>
                        <div className="font-mono font-bold text-neutral-900">
                          {cf.price ? cf.price.toFixed(4) : "—"}
                        </div>
                      </div>
                      <div>
                        <div className="text-xs text-neutral-500">Fon Büyüklüğü</div>
                        <div className="font-mono font-bold text-neutral-900">
                          {cf.market_cap ? fmtMoney(cf.market_cap) : "—"}
                        </div>
                      </div>
                      <div>
                        <div className="text-xs text-neutral-500">Günlük Değişim</div>
                        <div
                          className={`font-mono font-bold flex items-center gap-0.5 ${
                            (cf.daily_change || 0) >= 0 ? "text-green-600" : "text-red-600"
                          }`}
                        >
                          {(cf.daily_change || 0) >= 0 ? (
                            <TrendingUp className="w-3 h-3" />
                          ) : (
                            <TrendingDown className="w-3 h-3" />
                          )}
                          {cf.daily_change != null
                            ? `${cf.daily_change >= 0 ? "+" : ""}${cf.daily_change.toFixed(2)}%`
                            : "—"}
                        </div>
                      </div>
                      <div>
                        <div className="text-xs text-neutral-500">Tür</div>
                        <span
                          className={`inline-block px-2 py-0.5 rounded text-xs font-medium border ${
                            TYPE_COLORS[cf.fund_type] ||
                            "bg-neutral-100 text-neutral-700 border-neutral-200"
                          }`}
                        >
                          {cf.fund_type}
                        </span>
                      </div>
                    </div>
                  </CardContent>
                </Card>
                </div>
              ))}
            </div>
          </>
        )}
      </div>
    </div>
  );
}
