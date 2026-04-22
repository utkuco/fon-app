"use client";

import { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import { Search, BarChart2, ArrowLeft, TrendingUp, ExternalLink } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Logo } from "@/components/Logo";
import { TYPE_LABELS, TYPE_COLORS } from "@/lib/shared-config";
import { ChangeBadge } from "@/components/ChangeBadge";
import { displayName } from "@/lib/holdings-data";

interface AggregatedHolding {
  isin: string;
  company: string;
  ticker: string;
  fund_count: number;
  updated_at: string | null;
}

interface HoldingFund {
  fund_code: string;
  fund_name: string | null;
  fund_type: string | null;
  weight_pct: number | null;
  daily_change: number | null;
}

interface HoldingDetail {
  isin: string;
  ticker: string;
  company: string | null;
  funds: HoldingFund[];
}

function fmtWeight(n: number | null): string {
  if (n == null) return "—";
  return `${n.toFixed(2)}%`;
}

function SkeletonRow() {
  return (
    <div className="flex items-center gap-4 py-4 px-4 border-b border-neutral-100 animate-pulse">
      <div className="flex-1 space-y-2">
        <div className="h-4 bg-neutral-200 rounded w-48" />
        <div className="h-3 bg-neutral-100 rounded w-32" />
      </div>
      <div className="h-4 bg-neutral-200 rounded w-16" />
    </div>
  );
}

export default function HoldingsClient({
  initialHoldings,
}: {
  initialHoldings: AggregatedHolding[];
}) {
  const [holdings, setHoldings] = useState<AggregatedHolding[]>(initialHoldings);
  const [detail, setDetail] = useState<HoldingDetail | null>(null);
  const [loading, setLoading] = useState(false);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [search, setSearch] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [selectedIsin, setSelectedIsin] = useState<string | null>(null);

  const loadDetail = useCallback(async (isin: string) => {
    setLoadingDetail(true);
    setDetail(null);
    try {
      const res = await fetch(`/api/holdings/${isin}`);
      if (!res.ok) throw new Error("Detay yüklenemedi");
      const data = await res.json();
      setDetail(data);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoadingDetail(false);
    }
  }, []);

  useEffect(() => {
    document.title = selectedIsin
      ? `${displayName(selectedIsin, detail?.company)} — Hangi Fonlarda | FonRapor`
      : "Hisse Tercihleri | FonRapor";
  }, [selectedIsin, detail]);

  useEffect(() => {
    if (selectedIsin) {
      loadDetail(selectedIsin);
    }
  }, [selectedIsin, loadDetail]);

  const filteredHoldings = search
    ? holdings.filter(
        (h) =>
          displayName(h.isin, h.company).toLowerCase().includes(search.toLowerCase()) ||
          h.isin.toLowerCase().includes(search.toLowerCase())
      )
    : holdings;

  const topGainers = filteredHoldings.slice(0, 5);
  const rest = filteredHoldings.slice(5);

  return (
    <div className="min-h-screen bg-neutral-50">
      {/* Header */}
      <header className="bg-white border-b border-neutral-200 sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-3 sm:px-4 h-16 flex items-center gap-3">
          <Link href="/" className="hover:opacity-70 transition shrink-0">
            <Logo variant="full" className="h-8 w-auto" />
          </Link>
          <div className="h-6 w-px bg-neutral-200 hidden sm:block" />
          <nav className="hidden md:flex items-center gap-1 ml-1">
            <Link
              href="/companies"
              className="px-3 py-1.5 text-sm font-medium text-neutral-600 hover:text-blue-600 hover:bg-blue-50 rounded-lg transition"
            >
              Şirketler
            </Link>
            <Link
              href="/holdings"
              className="px-3 py-1.5 text-sm font-medium text-blue-600 bg-blue-50 rounded-lg"
            >
              Hisse Tercihleri
            </Link>
          </nav>
          <div className="h-6 w-px bg-neutral-200 hidden sm:block" />
          <span className="text-sm font-bold text-neutral-900 hidden sm:block">
            {selectedIsin ? "Fon Listesi" : "Hisse Tercihleri"}
          </span>

          <div className="relative flex-1 min-w-0 max-w-xs sm:max-w-sm ml-auto">
            <Search className="absolute left-2 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-neutral-400 pointer-events-none" />
            <Input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder={
                selectedIsin
                  ? displayName(selectedIsin, detail?.company)
                  : "Sembol veya ISIN ara..."
              }
              className="pl-7 pr-3 h-8 text-sm bg-neutral-100 border-transparent focus:bg-white focus:border-blue-300"
            />
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-3 sm:px-4 py-6 space-y-4">
        {/* Back */}
        {selectedIsin && (
          <button
            onClick={() => {
              setSelectedIsin(null);
              setDetail(null);
              setSearch("");
            }}
            className="inline-flex items-center gap-1.5 text-sm text-neutral-500 hover:text-blue-600 transition"
          >
            <ArrowLeft className="w-4 h-4" />
            Tüm Varlıklara Dön
          </button>
        )}

        {!selectedIsin ? (
          <>
            {/* Ana Sayfa: En Çok Tutulan Varlıklar */}
            <Card>
              <CardContent className="p-5">
                <div className="flex flex-col lg:flex-row lg:items-center gap-4">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-2">
                      <h1 className="text-xl font-black text-neutral-900">
                        Hisse Tercihleri
                      </h1>
                      <Badge
                        variant="outline"
                        className="text-[10px] font-mono bg-blue-50 text-blue-600 border-blue-200"
                      >
                        {holdings.length} varlık
                      </Badge>
                    </div>
                    <p className="text-sm text-neutral-500">
                      Fonların en çok tercih ettiği varlıklar. Her varlığın
                      kaç fon tarafından tutulduğunu görün.
                    </p>
                  </div>
                  <div className="flex items-center gap-6 shrink-0">
                    <div className="text-right">
                      <div className="text-xs text-neutral-400">En Çok Fon</div>
                      <div className="text-lg font-bold text-neutral-900">
                        {holdings.length > 0
                          ? Math.max(...holdings.map((h) => h.fund_count))
                          : "—"}
                      </div>
                    </div>
                  </div>
                </div>
              </CardContent>
            </Card>

            {/* Error state */}
            {error && (
              <Card className="border-red-200 bg-red-50">
                <CardContent className="p-4 text-sm text-red-700">
                  {error} —{" "}
                  <button
                    onClick={() => {
                      setError(null);
                      setHoldings(initialHoldings);
                    }}
                    className="underline font-medium"
                  >
                    Sıfırla
                  </button>
                </CardContent>
              </Card>
            )}

            {/* Loading */}
            {loading && (
              <Card>
                <CardContent className="p-0">
                  {Array.from({ length: 10 }).map((_, i) => (
                    <SkeletonRow key={i} />
                  ))}
                </CardContent>
              </Card>
            )}

            {/* Top 5 cards */}
            {!loading && !error && topGainers.length > 0 && (
              <>
                <div className="flex items-center gap-2">
                  <TrendingUp className="w-4 h-4 text-emerald-600" />
                  <h2 className="text-sm font-semibold text-neutral-700">
                    En Çok Tutulan Varlıklar
                  </h2>
                </div>
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5 gap-3">
                  {topGainers.map((h, i) => (
                    <button
                      key={h.isin}
                      onClick={() => setSelectedIsin(h.isin)}
                      className="text-left card p-4 hover:shadow-md hover:-translate-y-0.5 transition-all bg-white border border-neutral-200 rounded-xl"
                    >
                      <div className="flex items-start justify-between gap-2 mb-2">
                        <div className="min-w-0 flex-1">
                          <p className="font-bold text-neutral-900 text-sm truncate">
                            {displayName(h.isin, h.company)}
                          </p>
                          <p className="text-[10px] font-mono text-neutral-400 mt-0.5">
                            {h.isin}
                          </p>
                        </div>
                        <Badge
                          variant="outline"
                          className="bg-blue-100 text-blue-700 text-[10px] shrink-0"
                        >
                          #{i + 1}
                        </Badge>
                      </div>
                      <div className="flex items-center gap-1">
                        <BarChart2 className="w-3 h-3 text-neutral-400" />
                        <span className="text-xs font-semibold text-neutral-700">
                          {h.fund_count} fon
                        </span>
                      </div>
                    </button>
                  ))}
                </div>
              </>
            )}

            {/* Full Table */}
            {!loading && !error && rest.length > 0 && (
              <Card>
                <CardContent className="p-0">
                  <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="border-b border-neutral-200 bg-neutral-50">
                          <th className="text-left py-3 px-4 font-medium text-neutral-500">
                            Sembol
                          </th>
                          <th className="text-left py-3 px-4 font-medium text-neutral-500 hidden md:table-cell">
                            ISIN
                          </th>
                          <th className="text-right py-3 px-4 font-medium text-neutral-500">
                            Fon Sayısı
                          </th>
                        </tr>
                      </thead>
                      <tbody>
                        {rest.map((h, i) => (
                          <tr
                            key={h.isin}
                            onClick={() => setSelectedIsin(h.isin)}
                            className={`border-b border-neutral-100 cursor-pointer last:border-0 hover:bg-blue-50 transition ${
                              i % 2 === 0 ? "bg-white" : "bg-neutral-50/30"
                            }`}
                          >
                            <td className="py-3 px-4">
                              <div className="flex items-center gap-2">
                                <span className="font-mono font-semibold text-neutral-900">
                                  {displayName(h.isin, h.company)}
                                </span>
                              </div>
                            </td>
                            <td className="py-3 px-4 hidden md:table-cell">
                              <span className="font-mono text-xs text-neutral-500">
                                {h.isin}
                              </span>
                            </td>
                            <td className="py-3 px-4 text-right">
                              <Badge
                                variant="outline"
                                className="text-xs font-semibold"
                              >
                                {h.fund_count} fon
                              </Badge>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </CardContent>
              </Card>
            )}

            {/* Empty state */}
            {!loading && !error && filteredHoldings.length === 0 && (
              <Card>
                <CardContent className="p-12 text-center">
                  <BarChart2 className="w-12 h-12 mx-auto mb-3 text-neutral-300" />
                  <div className="text-neutral-500 font-medium">
                    Sonuç bulunamadı
                  </div>
                </CardContent>
              </Card>
            )}
          </>
        ) : (
          <>
            {/* Detay Sayfası: Bir Varlığı Tutan Fonlar */}
            <Card>
              <CardContent className="p-5">
                <div className="flex flex-col sm:flex-row sm:items-start gap-4">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1 flex-wrap">
                      <h1 className="text-xl font-black text-neutral-900">
                        {displayName(selectedIsin, detail?.ticker)}
                      </h1>
                      <Badge className="bg-blue-100 text-blue-700 font-mono">
                        {selectedIsin}
                      </Badge>
                    </div>
                    <div className="flex items-center gap-4 flex-wrap">
                      <div>
                        <span className="text-xs text-neutral-400">
                          Fon Sayısı
                        </span>
                        <p className="text-lg font-bold text-neutral-900">
                          {detail?.funds.length || "—"}
                        </p>
                      </div>
                    </div>
                  </div>
                </div>
              </CardContent>
            </Card>

            {/* Detail loading */}
            {loadingDetail && (
              <Card>
                <CardContent className="p-0">
                  {Array.from({ length: 8 }).map((_, i) => (
                    <SkeletonRow key={i} />
                  ))}
                </CardContent>
              </Card>
            )}

            {/* Detail error */}
            {error && (
              <Card className="border-red-200 bg-red-50">
                <CardContent className="p-4 text-sm text-red-700">
                  {error} —{" "}
                  <button
                    onClick={() => loadDetail(selectedIsin)}
                    className="underline font-medium"
                  >
                    Tekrar dene
                  </button>
                </CardContent>
              </Card>
            )}

            {/* Funds table */}
            {!loadingDetail && !error && detail && (
              <Card>
                <CardContent className="p-0">
                  <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="border-b border-neutral-200 bg-neutral-50">
                          <th className="text-left py-3 px-4 font-medium text-neutral-500">
                            Fon
                          </th>
                          <th className="text-right py-3 px-4 font-medium text-neutral-500 hidden sm:table-cell">
                            Günlük Değişim
                          </th>
                          <th className="text-right py-3 px-4 font-medium text-neutral-500">
                            Ağırlık
                          </th>
                          <th className="w-8" />
                        </tr>
                      </thead>
                      <tbody>
                        {detail.funds.map((f, i) => {
                          const typeColor =
                            TYPE_COLORS[f.fund_type || ""] ||
                            "bg-neutral-100 text-neutral-600";
                          return (
                            <tr
                              key={f.fund_code}
                              className={`border-b border-neutral-100 last:border-0 hover:bg-neutral-50 transition ${
                                i % 2 === 0
                                  ? "bg-white"
                                  : "bg-neutral-50/30"
                              }`}
                            >
                              <td className="py-3 px-4">
                                <Link
                                  href={`/fon/${f.fund_code}`}
                                  className="flex flex-col gap-1 hover:underline"
                                >
                                  <span className="font-mono font-bold text-blue-600">
                                    {f.fund_code}
                                  </span>
                                  <span className="text-xs text-neutral-500 line-clamp-1 max-w-[180px]">
                                    {f.fund_name || "—"}
                                  </span>
                                  {f.fund_type && (
                                    <span
                                      className={`text-[10px] px-1.5 py-0.5 rounded-full font-medium w-fit ${typeColor}`}
                                    >
                                      {TYPE_LABELS[f.fund_type] ||
                                        f.fund_type}
                                    </span>
                                  )}
                                </Link>
                              </td>
                              <td className="py-3 px-4 text-right hidden sm:table-cell">
                                {f.daily_change != null ? (
                                  <ChangeBadge value={f.daily_change} />
                                ) : (
                                  <span className="text-neutral-400">—</span>
                                )}
                              </td>
                              <td className="py-3 px-4 text-right">
                                {f.weight_pct != null ? (
                                  <span className="font-mono font-semibold text-neutral-900">
                                    {fmtWeight(f.weight_pct)}
                                  </span>
                                ) : (
                                  <span className="text-neutral-400">—</span>
                                )}
                              </td>
                              <td className="py-3 px-4 text-right">
                                <Link
                                  href={`/fon/${f.fund_code}`}
                                  className="text-neutral-400 hover:text-blue-600 transition"
                                >
                                  <ExternalLink className="w-3.5 h-3.5" />
                                </Link>
                              </td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                </CardContent>
              </Card>
            )}
          </>
        )}
      </main>
    </div>
  );
}
