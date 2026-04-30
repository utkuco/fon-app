"use client";

import { useState, useEffect, Suspense } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ArrowLeft, TrendingUp, TrendingDown, Search, ArrowUpDown, ChevronLeft, ChevronRight } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Logo } from "@/components/Logo";
import { CompanyLogo } from "@/components/CompanyLogo";
import { ChangeBadge } from "@/components/ChangeBadge";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { TYPE_LABELS, TYPE_COLORS, ASSET_LABELS, ASSET_COLORS } from "@/lib/shared-config";

interface PricePoint { date: string; price: number; change: number }
interface Fund {
  code: string;
  name: string;
  fund_type: string | null;
  company?: string | null;
  company_logo?: string;
  daily_change: number | null;
  market_cap: number | null;
  price: number | null;
  weekly?: number | null;
  monthly?: number | null;
  quarterly?: number | null;
  returns?: Record<string, number> | null;
  breakdown?: Record<string, number> | null;
  price_history?: PricePoint[] | null;
}

interface CompanyPageClientProps {
  initialData: { funds: Fund[] } | null;
  companyName: string;
  slug: string;
  sortKey: SortKey;
  sortDir: "asc" | "desc";
  page: number;
  totalPages: number;
  total: number;
  stats: { total: number; totalAUM: number; avgChange: number };
}

function fmtMoney(n: number | null): string {
  if (n == null) return "—";
  if (n >= 1e9) return `${(n / 1e9).toFixed(1)}B`;
  if (n >= 1e6) return `${(n / 1e6).toFixed(1)}M`;
  return `${n.toLocaleString("tr-TR")}`;
}

function fmtNum(n: number): string {
  return n.toLocaleString("tr-TR");
}

function getReturn(f: Fund, days: number): number {
  const ph = f.price_history;
  if (!ph || ph.length < 2) return 0;
  const sorted = [...ph].sort((x, y) => x.date.localeCompare(y.date));
  const today = sorted[sorted.length - 1];
  const cutoff = new Date(today.date);
  cutoff.setDate(cutoff.getDate() - days);
  const cutoffStr = cutoff.toISOString().split("T")[0];
  const idx = sorted.findIndex(p => p.date >= cutoffStr);
  if (idx < 0 || idx === 0) return 0;
  const start = sorted[idx - 1]?.price || 0;
  const end = sorted[sorted.length - 1]?.price || 0;
  if (!start) return 0;
  return ((end - start) / start) * 100;
}

type SortKey = "market_cap" | "daily_change" | "weekly" | "monthly" | "quarterly";
type SortDir = "asc" | "desc";

export default function CompanyPageClient({ initialData, companyName, slug, sortKey, sortDir, page, totalPages, total, stats }: CompanyPageClientProps) {
  const router = useRouter();
  const [data] = useState<{ funds: Fund[] } | null>(initialData);
  const [loading] = useState(false);
  const [search, setSearch] = useState("");
  const [q, setQ] = useState("");
  const [localSort, setLocalSort] = useState(sortKey);
  const [localDir, setLocalDir] = useState(sortDir);

  useEffect(() => { setLocalSort(sortKey); setLocalDir(sortDir); }, [sortKey, sortDir]);

  if (loading) return (
    <div className="min-h-screen flex items-center justify-center bg-neutral-50">
      <div className="animate-pulse text-neutral-400">Yükleniyor...</div>
    </div>
  );

  if (!data) return (
    <div className="min-h-screen flex flex-col items-center justify-center gap-4 bg-neutral-50">
      <div className="text-neutral-400">Veri yüklenemedi</div>
      <button onClick={() => window.location.reload()} className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm">Yeniden Dene</button>
      <Link href="/" className="text-blue-600 hover:underline text-sm">← Anasayfaya Dön</Link>
    </div>
  );

  const allFunds: Fund[] = data.funds || [];
  let companyFunds = allFunds;

  if (q) {
    const lower = q.toLowerCase();
    companyFunds = companyFunds.filter(f =>
      f.code.toLowerCase().includes(lower) ||
      (f.name || "").toLowerCase().includes(lower)
    );
  }

  const sorted = [...companyFunds].sort((a, b) => {
    let cmp = 0;
    if (localSort === "market_cap") cmp = ((a.market_cap ?? 0) - (b.market_cap ?? 0));
    else if (localSort === "daily_change") cmp = ((a.daily_change ?? 0) - (b.daily_change ?? 0));
    else if (localSort === "weekly") cmp = getReturn(a, 5) - getReturn(b, 5);
    else if (localSort === "monthly") cmp = getReturn(a, 21) - getReturn(b, 21);
    else if (localSort === "quarterly") cmp = getReturn(a, 63) - getReturn(b, 63);
    return localDir === "asc" ? cmp : -cmp;
  });

  const positive = stats.avgChange >= 0;

  const topGainers = [...companyFunds].sort((a, b) => ((b.daily_change ?? 0) - (a.daily_change ?? 0))).slice(0, 3);
  const topLosers = [...companyFunds].sort((a, b) => ((a.daily_change ?? 0) - (b.daily_change ?? 0))).slice(0, 3);

  // Unique types in this company
  const typeSet = new Set(companyFunds.map(f => f.fund_type).filter(Boolean));

  function toggleSort(k: SortKey) {
    if (localSort === k) {
      const newDir = localDir === "asc" ? "desc" : "asc";
      setLocalDir(newDir);
      router.push(`/company/${slug}?page=${page}&sort=${k}`);
    } else {
      setLocalSort(k);
      setLocalDir("desc");
      router.push(`/company/${slug}?page=1&sort=${k}`);
    }
  }

  function goToPage(p: number) {
    if (p < 1 || p > totalPages) return;
    router.push(`/company/${slug}?page=${p}&sort=${localSort}`);
  }

  return (
    <div className="min-h-screen bg-neutral-50">
      {/* Header */}
      <header className="bg-white border-b border-neutral-200 sm:sticky sm:top-0 sm:z-10">
        <div className="max-w-7xl mx-auto px-3 sm:px-4 h-16 flex items-center gap-3">
          <Link href="/" className="hover:opacity-70 transition shrink-0">
            <Logo variant="full" className="h-8 w-auto" />
          </Link>
          <div className="h-6 w-px bg-neutral-200 hidden sm:block" />
          {/* Nav Links */}
          <nav className="hidden md:flex items-center gap-1 ml-1">
            <Link href="/companies" className="px-3 py-1.5 text-sm font-medium text-neutral-600 hover:text-blue-600 hover:bg-blue-50 rounded-lg transition">Şirketler</Link>
            <Link href="/holdings" className="px-3 py-1.5 text-sm font-medium text-neutral-600 hover:text-blue-600 hover:bg-blue-50 rounded-lg transition">Hisse Tercihleri</Link>
            <Link href="/performers" className="px-3 py-1.5 text-sm font-medium text-neutral-600 hover:text-blue-600 hover:bg-blue-50 rounded-lg transition">En Çok Kazandıranlar</Link>
            <Link href="/etf" className="px-3 py-1.5 text-sm font-medium text-neutral-600 hover:text-blue-600 hover:bg-blue-50 rounded-lg transition">Yabancı ETF</Link>
          </nav>
          <div className="h-6 w-px bg-neutral-200 hidden sm:block" />
          <span className="text-sm font-bold text-neutral-900 hidden sm:block">{companyName}</span>
          <Badge variant="secondary" className="text-xs hidden sm:inline-flex">{stats.total} fon</Badge>
          <div className="relative flex-1 min-w-0 max-w-xs sm:max-w-sm ml-auto">
            <Search className="absolute left-2 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-neutral-400 pointer-events-none" />
            <Input
              value={search}
              onChange={e => setSearch(e.target.value)}
              onKeyDown={e => { if (e.key === "Enter") setQ(search); }}
              placeholder="Fon ara..."
              className="pl-7 pr-3 h-8 text-sm bg-neutral-100 border-transparent focus:bg-white focus:border-blue-300"
            />
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-3 sm:px-4 py-6 space-y-4">

        {/* Back link */}
        <Link href="/" className="inline-flex items-center gap-1.5 text-sm text-neutral-500 hover:text-blue-600 transition">
          <ArrowLeft className="w-4 h-4" />
          Tüm Şirketler
        </Link>

        {/* Summary Card */}
        <Card>
          <CardContent className="p-5">
            <div className="flex flex-col lg:flex-row lg:items-end gap-5">
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-3">
                  <h1 className="text-xl font-black text-neutral-900">{companyName}</h1>
                  <Badge variant="outline" className="text-[10px] font-mono">Yönetim Şirketi</Badge>
                </div>
                <div className="flex items-center gap-1 text-neutral-400 mb-1">
                  <span className="text-xs">{stats.total} fon</span>
                  <span>·</span>
                  <span className="text-xs">{fmtMoney(stats.totalAUM)} ₺ AUM</span>
                  {typeSet.size > 0 && (
                    <>
                      <span>·</span>
                      <span className="text-xs">{typeSet.size} tür</span>
                    </>
                  )}
                </div>
                <div className="flex items-center gap-1">
                  {positive
                    ? <TrendingUp className="w-4 h-4 text-emerald-600" />
                    : <TrendingDown className="w-4 h-4 text-red-600" />
                  }
                  <span className={`text-base font-bold ${positive ? "text-emerald-600" : "text-red-600"}`}>
                    {positive ? "+" : ""}{stats.avgChange.toFixed(2)}% ort. günlük
                  </span>
                </div>
              </div>

              {/* Company logo large */}
              <div className="lg:w-[300px] w-full flex justify-center lg:justify-end">
                <div className="bg-neutral-50 rounded-xl p-6 flex items-center justify-center">
                  <CompanyLogo
                    logoFile={companyFunds[0]?.company_logo}
                    company={companyName}
                    code={companyFunds[0]?.code}
                    size={80}
                    className="opacity-90"
                  />
                </div>
              </div>
            </div>

            {/* Top gainers / losers */}
            {(topGainers.length > 0 || topLosers.length > 0) && (
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mt-4 pt-4 border-t border-neutral-100">
                {topGainers.length > 0 && (
                  <div>
                    <div className="text-[10px] text-neutral-400 font-medium mb-1.5">En Çok Yükselen</div>
                    {topGainers.map(f => (
                      <Link key={f.code} href={`/fon/${f.code}`} className="flex items-center gap-2 py-1 hover:bg-neutral-50 rounded px-1 -mx-1 transition">
                        <span className="text-[11px] font-mono font-bold text-blue-600">{f.code}</span>
                        <span className="text-[11px] text-neutral-500 truncate flex-1">{f.name}</span>
                        <span className={`text-[11px] font-bold font-mono shrink-0 ${(f.daily_change ?? 0) >= 0 ? "text-emerald-600" : "text-red-600"}`}>
                          {(f.daily_change ?? 0) >= 0 ? "+" : ""}{(f.daily_change ?? 0).toFixed(2)}%
                        </span>
                      </Link>
                    ))}
                  </div>
                )}
                {topLosers.length > 0 && (
                  <div>
                    <div className="text-[10px] text-neutral-400 font-medium mb-1.5">En Çok Düşen</div>
                    {topLosers.map(f => (
                      <Link key={f.code} href={`/fon/${f.code}`} className="flex items-center gap-2 py-1 hover:bg-neutral-50 rounded px-1 -mx-1 transition">
                        <span className="text-[11px] font-mono font-bold text-blue-600">{f.code}</span>
                        <span className="text-[11px] text-neutral-500 truncate flex-1">{f.name}</span>
                        <span className={`text-[11px] font-bold font-mono shrink-0 ${(f.daily_change ?? 0) >= 0 ? "text-emerald-600" : "text-red-600"}`}>
                          {(f.daily_change ?? 0) >= 0 ? "+" : ""}{(f.daily_change ?? 0).toFixed(2)}%
                        </span>
                      </Link>
                    ))}
                  </div>
                )}
              </div>
            )}
          </CardContent>
        </Card>

        {/* Divider */}
        <div className="flex items-center gap-3 py-1">
          <div className="flex-1 h-px bg-neutral-200" />
        </div>

        {/* Filter bar */}
        <div className="flex items-center gap-2 overflow-x-auto no-scrollbar">
          <span className="text-xs text-neutral-400 shrink-0">Sırala:</span>
          {([
            { k: "market_cap" as SortKey, label: "Büyüklük" },
            { k: "daily_change" as SortKey, label: "Günlük" },
            { k: "weekly" as SortKey, label: "Haftalık" },
            { k: "monthly" as SortKey, label: "Aylık" },
            { k: "quarterly" as SortKey, label: "3A" },
          ]).map(({ k, label: sortLabel }) => (
            <button
              key={k}
              onClick={() => toggleSort(k)}
              className={`flex items-center gap-0.5 px-2 py-1 rounded-md text-xs transition whitespace-nowrap shrink-0 ${
                localSort === k ? "bg-neutral-900 text-white" : "text-neutral-500 hover:bg-neutral-100"
              }`}
            >
              {sortLabel}
              {localSort === k && <ArrowUpDown className="w-2.5 h-2.5" />}
            </button>
          ))}
        </div>

        {/* Pagination info */}
        <div className="flex items-center justify-between">
          <div className="text-xs text-neutral-400">
            <span className="font-semibold text-neutral-900">{fmtNum(sorted.length)}</span> sonuç (sayfa {page}/{totalPages})
          </div>
          <div className="flex items-center gap-1">
            <Button variant="outline" size="sm" onClick={() => goToPage(page - 1)} disabled={page <= 1} className="h-7 w-7 p-0">
              <ChevronLeft className="w-4 h-4" />
            </Button>
            {page > 1 && <Button variant="ghost" size="sm" onClick={() => goToPage(page - 1)} className="h-7 text-xs">{page - 1}</Button>}
            <Button variant="default" size="sm" className="h-7 w-7 p-0 text-xs font-bold" disabled>{page}</Button>
            {page < totalPages && <Button variant="ghost" size="sm" onClick={() => goToPage(page + 1)} className="h-7 text-xs">{page + 1}</Button>}
            <Button variant="outline" size="sm" onClick={() => goToPage(page + 1)} disabled={page >= totalPages} className="h-7 w-7 p-0">
              <ChevronRight className="w-4 h-4" />
            </Button>
          </div>
        </div>

        {/* Fund Grid */}
        {sorted.length === 0 ? (
          <div className="text-center py-24 text-neutral-400">Sonuç bulunamadı</div>
        ) : (
          <>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-3">
              {sorted.map((f) => {
                const typeColor = TYPE_COLORS[f.fund_type || ""] || "bg-neutral-100 text-neutral-600";

                const sparkPoints = (() => {
                  if (!f.price_history || f.price_history.length < 2) return null;
                  const last30 = f.price_history.slice(-30);
                  const min = Math.min(...last30.map(p => p.price));
                  const max = Math.max(...last30.map(p => p.price));
                  const range = max - min || 1;
                  const W = 280, H = 40;
                  return last30.map((p, idx) => ({
                    x: (idx / (last30.length - 1)) * W,
                    y: H - ((p.price - min) / range) * H,
                  }));
                })();
                const sparkPositive = (getReturn(f, 21) || f.daily_change || 0) >= 0;
                const sparkColor = sparkPositive ? "#10B981" : "#EF4444";
                const gradId = `sg${Math.abs((f.code?.split("").reduce((a, c) => (a * 31 + c.charCodeAt(0)) | 0, 0) ?? 0) % 99999)}`;

                return (
                  <Link key={f.code} href={`/fon/${f.code}`} className="group block">
                    <Card className="h-full transition-all duration-200 hover:shadow-lg hover:shadow-blue-500/5 hover:-translate-y-0.5 cursor-pointer">
                      <CardContent className="p-3.5 flex flex-col h-full gap-1.5">
                        {/* Row 1: logo + code + type + change */}
                        <div className="flex items-start gap-2">
                          <CompanyLogo
                            logoFile={f.company_logo}
                            company={f.company || undefined}
                            code={f.code}
                            size={36}
                            className="mt-0.5 shrink-0"
                          />
                          <div className="min-w-0 flex-1">
                            <div className="flex items-center gap-1 flex-wrap">
                              <span className="font-mono font-bold text-blue-600 text-xs truncate group-hover:underline">
                                {f.code}
                              </span>
                              {f.fund_type && (
                                <span className={`text-[10px] px-1 py-0.5 rounded-full font-medium ${typeColor}`}>
                                  {TYPE_LABELS[f.fund_type] || f.fund_type}
                                </span>
                              )}
                              <ChangeBadge value={f.daily_change} />
                            </div>
                            <div className="text-xs text-neutral-700 font-medium line-clamp-2 leading-snug mt-0.5">
                              {f.name}
                            </div>
                          </div>
                        </div>

                        {/* Sparkline */}
                        {sparkPoints && sparkPoints.length >= 2 ? (
                          <svg width="100%" height={40} viewBox="0 0 280 40" className="w-full h-10 overflow-visible">
                            <defs>
                              <linearGradient id={gradId} x1="0" y1="0" x2="0" y2="1">
                                <stop offset="0%" stopColor={sparkColor} stopOpacity="0.12" />
                                <stop offset="100%" stopColor={sparkColor} stopOpacity="0" />
                              </linearGradient>
                            </defs>
                            {(() => {
                              const pathD = sparkPoints.map((p, i) => `${i === 0 ? "M" : "L"}${p.x.toFixed(1)},${p.y.toFixed(1)}`).join(" ");
                              const areaD = pathD + ` L280,40 L0,40 Z`;
                              return <>
                                <path d={areaD} fill={`url(#${gradId})`} />
                                <path d={pathD} fill="none" stroke={sparkColor} strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
                                <circle cx={sparkPoints[sparkPoints.length - 1].x} cy={sparkPoints[sparkPoints.length - 1].y} r="2.5" fill={sparkColor} />
                              </>;
                            })()}
                          </svg>
                        ) : (
                          <div className="h-10" />
                        )}

                        {/* Price + AUM */}
                        <div className="flex items-end justify-between pt-2 border-t border-neutral-100">
                          <div>
                            <div className="text-base font-black text-neutral-900 font-mono tracking-tight">
                              {f.price != null ? f.price.toFixed(4) : "—"}
                            </div>
                            <div className="text-[10px] text-neutral-400">₺</div>
                          </div>
                          <div className="text-right">
                            <div className="text-sm font-semibold text-neutral-700">
                              {f.market_cap ? fmtMoney(f.market_cap) : "—"}
                            </div>
                            <div className="text-[10px] text-neutral-400">AUM</div>
                          </div>
                        </div>

                        {/* Returns */}
                        {(getReturn(f, 5) !== 0 || getReturn(f, 21) !== 0 || getReturn(f, 63) !== 0) && (
                          <div className="flex items-center gap-1.5">
                            {getReturn(f, 5) !== 0 && (
                              <div className="flex items-center gap-0.5 text-xs">
                                <span className="text-neutral-400">1H</span>
                                <span className={`font-semibold font-mono ${getReturn(f, 5) >= 0 ? "text-green-600" : "text-red-600"}`}>
                                  {getReturn(f, 5) >= 0 ? "+" : ""}{getReturn(f, 5).toFixed(1)}%
                                </span>
                              </div>
                            )}
                            {getReturn(f, 21) !== 0 && (
                              <div className="flex items-center gap-0.5 text-xs">
                                <span className="text-neutral-400">1A</span>
                                <span className={`font-semibold font-mono ${getReturn(f, 21) >= 0 ? "text-green-600" : "text-red-600"}`}>
                                  {getReturn(f, 21) >= 0 ? "+" : ""}{getReturn(f, 21).toFixed(1)}%
                                </span>
                              </div>
                            )}
                            {getReturn(f, 63) !== 0 && (
                              <div className="flex items-center gap-0.5 text-xs">
                                <span className="text-neutral-400">3A</span>
                                <span className={`font-semibold font-mono ${getReturn(f, 63) >= 0 ? "text-green-600" : "text-red-600"}`}>
                                  {getReturn(f, 63) >= 0 ? "+" : ""}{getReturn(f, 63).toFixed(1)}%
                                </span>
                              </div>
                            )}
                          </div>
                        )}

                        {/* Breakdown */}
                        {f.breakdown && Object.keys(f.breakdown).length > 0 && (
                          <div className="mt-1 pt-1.5 border-t border-neutral-100">
                            <div className="flex gap-0.5 h-4 rounded-sm overflow-hidden bg-neutral-100">
                              {Object.entries(f.breakdown)
                                .filter(([, v]) => v > 0)
                                .sort(([, a], [, b]) => b - a)
                                .slice(0, 4)
                                .map(([key, value]) => (
                                  <div
                                    key={key}
                                    className={`h-full rounded-sm transition-all ${ASSET_COLORS[key] || "bg-gray-400"}`}
                                    style={{ width: `${Math.min(value, 100)}%` }}
                                    title={`${ASSET_LABELS[key] || key}: ${value}%`}
                                  />
                                ))}
                            </div>
                            <div className="flex gap-1.5 mt-1 flex-wrap">
                              {Object.entries(f.breakdown)
                                .filter(([, v]) => v > 0)
                                .sort(([, a], [, b]) => b - a)
                                .slice(0, 3)
                                .map(([key, value]) => (
                                  <div key={key} className="flex items-center gap-0.5">
                                    <div className={`w-1.5 h-1.5 rounded-full ${ASSET_COLORS[key] || "bg-gray-400"} shrink-0`} />
                                    <span className="text-[10px] text-neutral-400">{ASSET_LABELS[key] || key}</span>
                                    <span className="text-[10px] font-mono font-medium text-neutral-600">{value}%</span>
                                  </div>
                                ))}
                              {Object.keys(f.breakdown).filter(k => f.breakdown![k] > 0).length > 3 && (
                                <span className="text-[10px] text-neutral-400">+{Object.keys(f.breakdown).filter(k => f.breakdown![k] > 0).length - 3}</span>
                              )}
                            </div>
                          </div>
                        )}
                      </CardContent>
                    </Card>
                  </Link>
                );
              })}
            </div>

            {/* Bottom pagination */}
            <div className="flex items-center justify-center gap-2 py-4">
              <Button variant="outline" size="sm" onClick={() => goToPage(page - 1)} disabled={page <= 1}>
                <ChevronLeft className="w-4 h-4 mr-1" /> Önceki
              </Button>
              <span className="text-xs text-neutral-400">Sayfa {page} / {totalPages}</span>
              <Button variant="outline" size="sm" onClick={() => goToPage(page + 1)} disabled={page >= totalPages}>
                Sonraki <ChevronRight className="w-4 h-4 ml-1" />
              </Button>
            </div>
          </>
        )}
      </main>

      {/* Footer */}
      <footer className="border-t border-neutral-200 mt-12 py-4 bg-white">
        <div className="max-w-7xl mx-auto px-4 flex items-center justify-center text-xs text-neutral-400 gap-3">
          <Link href="/" className="hover:text-blue-600 transition">FonRapor</Link>
          <span>·</span>
          <span>{companyName} — {stats.total} fon</span>
        </div>
      </footer>
    </div>
  );
}
