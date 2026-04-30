"use client";

import Link from "next/link";
import { ArrowLeft, ExternalLink } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Logo } from "@/components/Logo";
import { ChangeBadge } from "@/components/ChangeBadge";
import { TYPE_LABELS, TYPE_COLORS } from "@/lib/shared-config";
import { displayName, type HoldingDetail } from "@/lib/holdings-data";

function fmtWeight(n: number | null): string {
  if (n == null) return "—";
  return `${n.toFixed(2)}%`;
}

export default function HoldingsDetailClient({
  detail,
}: {
  detail: HoldingDetail;
}) {
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
            Fon Listesi
          </span>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-3 sm:px-4 py-6 space-y-4">
        {/* Back */}
        <Link
          href="/holdings"
          className="inline-flex items-center gap-1.5 text-sm text-neutral-500 hover:text-blue-600 transition"
        >
          <ArrowLeft className="w-4 h-4" />
          Tüm Varlıklara Dön
        </Link>

        {/* Asset Info Card */}
        <Card>
          <CardContent className="p-5">
            <div className="flex flex-col sm:flex-row sm:items-start gap-4">
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-1 flex-wrap">
                  <h1 className="text-xl font-black text-neutral-900 font-mono">
                    {displayName(detail.isin, detail.company)}
                  </h1>
                  {detail.ticker && (
                    <Badge className="bg-blue-100 text-blue-700 font-mono">
                      {detail.isin}
                    </Badge>
                  )}
                  {!detail.ticker && (
                    <span className="text-xs font-mono text-neutral-400">
                      {detail.isin}
                    </span>
                  )}
                </div>
                <div className="flex items-center gap-4 flex-wrap">
                  <div>
                    <span className="text-xs text-neutral-400">Fon Sayısı</span>
                    <p className="text-lg font-bold text-neutral-900">
                      {detail.funds.length}
                    </p>
                  </div>
                </div>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Funds Table */}
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
                          i % 2 === 0 ? "bg-white" : "bg-neutral-50/30"
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
                                {TYPE_LABELS[f.fund_type] || f.fund_type}
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
      </main>
    </div>
  );
}
