"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { ArrowLeft, Search, BarChart2, ExternalLink } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { ChangeBadge } from "@/components/ChangeBadge";
import { Logo } from "@/components/Logo";
import { TYPE_LABELS, TYPE_COLORS } from "@/lib/shared-config";

interface FundHolding {
  id: number;
  fund_code: string;
  ticker: string | null;
  isin: string | null;
  total_value: number | null;
  updated_at: string;
  fund_name: string | null;
  fund_type: string | null;
  fund_price: number | null;
  fund_daily_change: number | null;
}

interface HoldingsPageClientProps {
  holdings: FundHolding[];
  page: number;
  totalPages: number;
  total: number;
}

function fmtMoney(n: number | null): string {
  if (n == null) return "—";
  if (n >= 1e12) return `${(n / 1e12).toFixed(2)}T`;
  if (n >= 1e9) return `${(n / 1e9).toFixed(1)}B`;
  if (n >= 1e6) return `${(n / 1e6).toFixed(1)}M`;
  return n.toLocaleString("tr-TR");
}

function fmtNum(n: number): string {
  return n.toLocaleString("tr-TR");
}

export default function HoldingsPageClient({
  holdings: initialHoldings,
  page: initialPage,
  totalPages: initialTotalPages,
  total: initialTotal,
}: HoldingsPageClientProps) {
  const [holdings] = useState<FundHolding[]>(initialHoldings);
  const [page] = useState(initialPage);
  const [totalPages] = useState(initialTotalPages);
  const [total] = useState(initialTotal);
  const [search, setSearch] = useState("");
  const [q, setQ] = useState("");

  useEffect(() => {
    document.title = "Portföydeki Varlıklar | FonRapor";
  }, []);

  const filteredHoldings = search
    ? holdings.filter(
        (h) =>
          h.fund_code.toLowerCase().includes(search.toLowerCase()) ||
          (h.ticker || "").toLowerCase().includes(search.toLowerCase()) ||
          (h.isin || "").toLowerCase().includes(search.toLowerCase()) ||
          (h.fund_name || "").toLowerCase().includes(search.toLowerCase())
      )
    : holdings;

  return (
    <div className="min-h-screen bg-neutral-50">
      {/* Header */}
      <header className="bg-white border-b border-neutral-200 sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-3 sm:px-4 h-16 flex items-center gap-3">
          <Link href="/" className="hover:opacity-70 transition shrink-0">
            <Logo variant="full" className="h-8 w-auto" />
          </Link>
          <div className="h-6 w-px bg-neutral-200 hidden sm:block" />
          {/* Nav Links */}
          <nav className="hidden md:flex items-center gap-1 ml-1">
            <Link href="/companies" className="px-3 py-1.5 text-sm font-medium text-neutral-600 hover:text-blue-600 hover:bg-blue-50 rounded-lg transition">Şirketler</Link>
            <Link href="/holdings" className="px-3 py-1.5 text-sm font-medium text-blue-600 bg-blue-50 rounded-lg">Hisse Tercihleri</Link>
            <Link href="/performers" className="px-3 py-1.5 text-sm font-medium text-neutral-600 hover:text-blue-600 hover:bg-blue-50 rounded-lg transition">En Çok Kazandıranlar</Link>
            <Link href="/etf" className="px-3 py-1.5 text-sm font-medium text-neutral-600 hover:text-blue-600 hover:bg-blue-50 rounded-lg transition">Yabancı ETF</Link>
          </nav>
          <div className="h-6 w-px bg-neutral-200 hidden sm:block" />
          <span className="text-sm font-bold text-neutral-900 hidden sm:block">
            Portföydeki Varlıklar
          </span>
          <Badge variant="secondary" className="text-xs hidden sm:inline-flex">
            {total} varlık
          </Badge>
          <div className="relative flex-1 min-w-0 max-w-xs sm:max-w-sm ml-auto">
            <Search className="absolute left-2 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-neutral-400 pointer-events-none" />
            <Input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              onKeyDown={(e) => { if (e.key === "Enter") setQ(search); }}
              placeholder="Fon kodu, hisse veya ISIN ara..."
              className="pl-7 pr-3 h-8 text-sm bg-neutral-100 border-transparent focus:bg-white focus:border-blue-300"
            />
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-3 sm:px-4 py-6 space-y-4">
        {/* Back link */}
        <Link
          href="/"
          className="inline-flex items-center gap-1.5 text-sm text-neutral-500 hover:text-blue-600 transition"
        >
          <ArrowLeft className="w-4 h-4" />
          Tüm Fonlara Dön
        </Link>

        {/* Summary Card */}
        <Card>
          <CardContent className="p-5">
            <div className="flex flex-col lg:flex-row lg:items-center gap-5">
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-3">
                  <h1 className="text-xl font-black text-neutral-900">
                    Portföydeki Varlıklar
                  </h1>
                  <Badge variant="outline" className="text-[10px] font-mono">
                    FON_HOLDINGS
                  </Badge>
                </div>
                <div className="flex items-center gap-1 text-neutral-400">
                  <span className="text-xs">{fmtNum(total)} varlık</span>
                  <span>·</span>
                  <span className="text-xs">
                    Sayfa {page} / {totalPages}
                  </span>
                </div>
              </div>

              {/* Stats */}
              <div className="flex items-center gap-6 shrink-0">
                <div className="text-right">
                  <div className="text-xs text-neutral-400">Toplam Değer</div>
                  <div className="text-sm font-bold text-neutral-900">
                    {fmtMoney(holdings.reduce((s, h) => s + (h.total_value || 0), 0))}
                  </div>
                </div>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Divider */}
        <div className="flex items-center gap-3 py-1">
          <div className="flex-1 h-px bg-neutral-200" />
        </div>

        {/* Holdings Table */}
        {filteredHoldings.length === 0 ? (
          <Card>
            <CardContent className="p-12 text-center">
              <BarChart2 className="w-12 h-12 mx-auto mb-3 text-neutral-300" />
              <div className="text-neutral-500 font-medium">
                Sonuç bulunamadı
              </div>
              <div className="text-sm text-neutral-400 mt-1">
                Arama kriterlerinize uygun varlık bulunamadı
              </div>
            </CardContent>
          </Card>
        ) : (
          <>
            <Card>
              <CardContent className="p-0">
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-neutral-200 bg-neutral-50">
                        <th className="text-left py-3 px-4 font-medium text-neutral-500">
                          Fon Kodu
                        </th>
                        <th className="text-left py-3 px-4 font-medium text-neutral-500">
                          Hisse / Varlık
                        </th>
                        <th className="text-left py-3 px-4 font-medium text-neutral-500">
                          ISIN
                        </th>
                        <th className="text-right py-3 px-4 font-medium text-neutral-500">
                          Toplam Değer
                        </th>
                        <th className="text-right py-3 px-4 font-medium text-neutral-500">
                          Güncelleme
                        </th>
                      </tr>
                    </thead>
                    <tbody>
                      {filteredHoldings.map((holding, i) => {
                        const typeColor =
                          TYPE_COLORS[holding.fund_type || ""] ||
                          "bg-neutral-100 text-neutral-600";

                        return (
                          <tr
                            key={`${holding.fund_code}-${holding.id}`}
                            className={`border-b border-neutral-100 last:border-0 hover:bg-neutral-50 transition ${
                              i % 2 === 0 ? "bg-white" : "bg-neutral-50/30"
                            }`}
                          >
                            <td className="py-3 px-4">
                              <Link
                                href={`/fon/${holding.fund_code}`}
                                className="flex flex-col gap-1 hover:underline"
                              >
                                <span className="font-mono font-bold text-blue-600">
                                  {holding.fund_code}
                                </span>
                                <span className="text-xs text-neutral-500 line-clamp-1 max-w-[150px]">
                                  {holding.fund_name || "—"}
                                </span>
                                {holding.fund_type && (
                                  <span
                                    className={`text-[10px] px-1.5 py-0.5 rounded-full font-medium w-fit ${typeColor}`}
                                  >
                                    {TYPE_LABELS[holding.fund_type] ||
                                      holding.fund_type}
                                  </span>
                                )}
                              </Link>
                            </td>
                            <td className="py-3 px-4">
                              <div className="flex items-center gap-2">
                                {holding.ticker ? (
                                  <>
                                    <span className="font-mono font-bold text-neutral-900">
                                      {holding.ticker}
                                    </span>
                                    {holding.fund_daily_change != null && (
                                      <ChangeBadge
                                        value={holding.fund_daily_change}
                                      />
                                    )}
                                  </>
                                ) : (
                                  <span className="text-neutral-400">—</span>
                                )}
                              </div>
                            </td>
                            <td className="py-3 px-4">
                              {holding.isin ? (
                                <span className="font-mono text-xs text-neutral-600">
                                  {holding.isin}
                                </span>
                              ) : (
                                <span className="text-neutral-400">—</span>
                              )}
                            </td>
                            <td className="py-3 px-4 text-right">
                              {holding.total_value != null ? (
                                <div>
                                  <span className="font-mono font-semibold text-neutral-900">
                                    {fmtMoney(holding.total_value)}
                                  </span>
                                  <span className="text-xs text-neutral-400 ml-1">
                                    ₺
                                  </span>
                                </div>
                              ) : (
                                <span className="text-neutral-400">—</span>
                              )}
                            </td>
                            <td className="py-3 px-4 text-right text-neutral-500 text-xs">
                              {holding.updated_at
                                ? new Date(holding.updated_at).toLocaleDateString(
                                    "tr-TR",
                                    {
                                      day: "2-digit",
                                      month: "short",
                                      year: "numeric",
                                    }
                                  )
                                : "—"}
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </CardContent>
            </Card>

            {/* Pagination info */}
            <div className="flex items-center justify-between">
              <div className="text-xs text-neutral-400">
                <span className="font-semibold text-neutral-900">
                  {fmtNum(filteredHoldings.length)}
                </span>{" "}
                sonuç (sayfa {page}/{totalPages})
              </div>
              <div className="flex items-center gap-1">
                <Button
                  variant="outline"
                  size="sm"
                  disabled={page <= 1}
                  className="h-7 w-7 p-0 opacity-50"
                >
                  ←
                </Button>
                <span className="text-xs text-neutral-500 px-2">
                  Sayfa {page}
                </span>
                <Button
                  variant="outline"
                  size="sm"
                  disabled={page >= totalPages}
                  className="h-7 w-7 p-0 opacity-50"
                >
                  →
                </Button>
              </div>
            </div>
          </>
        )}
      </main>

      <footer className="border-t border-neutral-200 mt-12 py-4 bg-white">
        <div className="max-w-7xl mx-auto px-4 flex items-center justify-center text-xs text-neutral-400 gap-3">
          <Link href="/" className="hover:text-blue-600 transition">
            FonRapor
          </Link>
          <span>·</span>
          <span>{fmtNum(total)} varlık</span>
        </div>
      </footer>
    </div>
  );
}
