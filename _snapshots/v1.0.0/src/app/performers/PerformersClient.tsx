"use client";

import { useState, useMemo } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { TrendingUp, TrendingDown } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Logo } from "@/components/Logo";
import { CompanyLogo } from "@/components/CompanyLogo";

interface TurkishFund {
  code: string;
  name: string;
  fund_type: string | null;
  company: string | null;
  company_logo: string | null;
  market_cap: number | null;
  price: number;
  price_usd: number;
  daily_change: number | null;
  weekly: number | null;
  monthly: number | null;
  quarterly: number | null;
  returns: Record<string, number> | null;
  usd_rate: number;
}

interface Etf {
  symbol: string;
  name: string;
  price: number | null;
  price_try: number | null;
  currency: string | null;
  change_pct: number | null;
  ytd_return: number | null;
  three_yr_return: number | null;
  five_yr_return: number | null;
  aum: number | null;
  asset_type: string | null;
}

function fmtMoney(n: number | null): string {
  if (n == null) return "—";
  if (n >= 1e9) return `$${(n / 1e9).toFixed(1)}B`;
  if (n >= 1e6) return `$${(n / 1e6).toFixed(1)}M`;
  return `$${n.toLocaleString()}`;
}

function fmtPct(n: number | null, showSign = false): string {
  if (n == null) return "—";
  const sign = showSign && n > 0 ? "+" : "";
  return `${sign}${n.toFixed(2)}%`;
}

function PctCell({ value }: { value: number | null }) {
  if (value == null) return <span className="text-xs text-neutral-400">—</span>;
  const isPos = value >= 0;
  return (
    <span className={`inline-flex items-center gap-0.5 text-xs font-semibold ${isPos ? "text-emerald-600" : "text-red-600"}`}>
      {isPos ? <TrendingUp className="w-3 h-3" /> : <TrendingDown className="w-3 h-3" />}
      {fmtPct(value, true)}
    </span>
  );
}

function TurkishFundRow({ fund, rank }: { fund: TurkishFund; rank: number }) {
  return (
    <Link href={`/fon/${fund.code}`} className="group">
      <div className="flex items-center gap-3 px-3 py-3 hover:bg-blue-50 transition border-b border-neutral-100 last:border-0">
        <span className="text-sm font-bold text-neutral-400 w-5 shrink-0">{rank}</span>
        {fund.company_logo && (
          <CompanyLogo logoFile={fund.company_logo} name={fund.company || ""} size={28} className="shrink-0" />
        )}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-1.5">
            <span className="text-sm font-semibold text-neutral-900 group-hover:text-blue-600 transition-colors">
              {fund.code}
            </span>
            <span className="text-xs text-neutral-400 truncate">{fund.name}</span>
          </div>
          <div className="text-xs text-neutral-400 mt-0.5">
            {fund.company || ""} · ₺{fund.price.toFixed(2)} ≈ ${fund.price_usd}
          </div>
        </div>
        <div className="flex items-center gap-4 text-xs">
          <div className="text-center w-14">
            <p className="text-neutral-400 mb-0.5">Haftalık</p>
            <PctCell value={fund.weekly} />
          </div>
          <div className="text-center w-14">
            <p className="text-neutral-400 mb-0.5">Aylık</p>
            <PctCell value={fund.monthly} />
          </div>
          <div className="text-center w-14">
            <p className="text-neutral-400 mb-0.5">Çeyreklik</p>
            <PctCell value={fund.quarterly} />
          </div>
        </div>
      </div>
    </Link>
  );
}

function EtfRow({ etf, rank }: { etf: Etf; rank: number }) {
  return (
    <Link href={`/etf/${etf.symbol}`} className="group">
      <div className="flex items-center gap-3 px-3 py-3 hover:bg-blue-50 transition border-b border-neutral-100 last:border-0">
        <span className="text-sm font-bold text-neutral-400 w-5 shrink-0">{rank}</span>
        <div className="w-8 h-8 rounded-full bg-blue-100 flex items-center justify-center shrink-0">
          <span className="text-xs font-bold text-blue-700">{etf.symbol.slice(0, 2)}</span>
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-1.5">
            <span className="text-sm font-semibold text-neutral-900 group-hover:text-blue-600 transition-colors">
              {etf.symbol}
            </span>
            <span className="text-xs text-neutral-400 truncate">{etf.name}</span>
          </div>
          <div className="text-xs text-neutral-400 mt-0.5">
            ${etf.price?.toFixed(2)} · {etf.currency} · {etf.asset_type}
          </div>
        </div>
        <div className="flex items-center gap-4 text-xs">
          <div className="text-center w-14">
            <p className="text-neutral-400 mb-0.5">YTD</p>
            <PctCell value={etf.ytd_return} />
          </div>
          <div className="text-center w-14">
            <p className="text-neutral-400 mb-0.5">3 Yıl</p>
            <PctCell value={etf.three_yr_return} />
          </div>
          <div className="text-center w-14">
            <p className="text-neutral-400 mb-0.5">5 Yıl</p>
            <PctCell value={etf.five_yr_return} />
          </div>
        </div>
      </div>
    </Link>
  );
}

export default function PerformersClient({
  turkishFunds,
  etfs,
}: {
  turkishFunds: TurkishFund[];
  etfs: Etf[];
}) {
  const pathname = usePathname();
  const [tab, setTab] = useState<"mixed" | "turkish" | "etf">("mixed");
  const [mixedSort, setMixedSort] = useState<"1m" | "3m">("1m");

  // Turkish funds sorted by selected period
  const topTurkish = useMemo(() => {
    const sorted = [...turkishFunds].filter((f) => f.monthly != null);
    return sorted.sort((a, b) => {
      const key = mixedSort === "1m" ? "monthly" : "quarterly";
      return (b[mixedSort === "1m" ? "monthly" : "quarterly"] || 0) - (a[mixedSort === "1m" ? "monthly" : "quarterly"] || 0);
    }).slice(0, 10);
  }, [turkishFunds, mixedSort]);

  // ETFs sorted by YTD
  const topEtf = useMemo(() => {
    return [...etfs]
      .filter((e) => e.ytd_return != null)
      .sort((a, b) => (b.ytd_return || 0) - (a.ytd_return || 0))
      .slice(0, 10);
  }, [etfs]);

  // Mixed list: combine top Turkish funds and ETFs, sort by selected period
  // For Turkish funds: convert to USD return (monthly or quarterly)
  // For ETFs: use ytd_return as common metric
  const mixedList = useMemo(() => {
    const turkishEntries = topTurkish.map((f) => {
      const returnVal = mixedSort === "1m" ? f.monthly : f.quarterly;
      return {
        type: "fund" as const,
        code: f.code,
        name: f.name,
        return_pct: returnVal,
        detail: f.company ? `${f.company} · ₺${f.price.toFixed(2)}` : `₺${f.price.toFixed(2)}`,
        href: `/fon/${f.code}`,
        monthly: f.monthly,
        quarterly: f.quarterly,
      };
    });

    const etfEntries = topEtf.map((e) => ({
      type: "etf" as const,
      code: e.symbol,
      name: e.name,
      return_pct: e.ytd_return,
      detail: e.price != null ? `$${e.price.toFixed(2)} · ${e.currency || ""}` : "",
      href: `/etf/${e.symbol}`,
      monthly: null,
      quarterly: null,
    }));

    return [...turkishEntries, ...etfEntries].sort((a, b) => (b.return_pct || 0) - (a.return_pct || 0));
  }, [topTurkish, topEtf, mixedSort]);

  const tabs: { key: typeof tab; label: string }[] = [
    { key: "mixed", label: `Karışık (${mixedList.length})` },
    { key: "turkish", label: `Türk Fon (${topTurkish.length})` },
    { key: "etf", label: `Yabancı ETF (${topEtf.length})` },
  ];

  return (
    <div className="min-h-screen bg-neutral-50">
      {/* Header */}
      <header className="bg-white border-b border-neutral-200 sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-3 sm:px-4 h-16 flex items-center gap-3">
          <Link href="/" className="hover:opacity-70 transition shrink-0">
            <Logo variant="full" className="h-8 w-auto" />
          </Link>

          {/* Nav Links */}
          <nav className="hidden md:flex items-center gap-0.5 ml-2">
            <Link
              href="/"
              className={`px-3 py-1.5 text-sm font-medium rounded-lg transition ${
                pathname === "/" ? "text-blue-600 bg-blue-50" : "text-neutral-600 hover:text-blue-600 hover:bg-blue-50"
              }`}
            >
              Fonlar
            </Link>
            <Link
              href="/etf"
              className={`px-3 py-1.5 text-sm font-medium rounded-lg transition ${
                pathname?.startsWith("/etf") ? "text-blue-600 bg-blue-50" : "text-neutral-600 hover:text-blue-600 hover:bg-blue-50"
              }`}
            >
              ETF'ler
            </Link>
            <Link
              href="/performers"
              className={`px-3 py-1.5 text-sm font-medium rounded-lg transition ${
                pathname === "/performers" ? "text-blue-600 bg-blue-50" : "text-neutral-600 hover:text-blue-600 hover:bg-blue-50"
              }`}
            >
              Performanslar
            </Link>
            <Link
              href="/companies"
              className={`px-3 py-1.5 text-sm font-medium rounded-lg transition ${
                pathname === "/companies" ? "text-blue-600 bg-blue-50" : "text-neutral-600 hover:text-blue-600 hover:bg-blue-50"
              }`}
            >
              Şirketler
            </Link>
          </nav>

          <Badge variant="secondary" className="text-xs ml-auto hidden sm:inline-flex">
            Performanslar
          </Badge>
        </div>
      </header>

      <main className="max-w-5xl mx-auto px-3 sm:px-4 py-6">
        {/* Tab bar */}
        <div className="flex gap-1 mb-6 bg-white rounded-xl border border-neutral-200 p-1">
          {tabs.map((t) => (
            <button
              key={t.key}
              onClick={() => setTab(t.key)}
              className={`flex-1 py-2 px-4 rounded-lg text-sm font-medium transition ${
                tab === t.key
                  ? "bg-blue-600 text-white shadow-sm"
                  : "text-neutral-600 hover:bg-neutral-100"
              }`}
            >
              {t.label}
            </button>
          ))}
        </div>

        {/* ── KARISIK SIRALAMA (Tümü) ── */}
        {tab === "mixed" && (
          <div className="space-y-4">
            {/* Sort toggle */}
            <div className="flex items-center gap-3">
              <span className="text-xs text-neutral-500 font-medium">Sıralama:</span>
              <div className="flex gap-1 bg-neutral-100 rounded-lg p-0.5">
                {[{ k: "1m", l: "Aylık" }, { k: "3m", l: "Çeyreklik" }].map((s) => (
                  <button
                    key={s.k}
                    onClick={() => setMixedSort(s.k as "1m" | "3m")}
                    className={`px-2.5 py-1 rounded-md text-xs font-medium transition ${
                      mixedSort === s.k ? "bg-white text-blue-700 shadow-sm" : "text-neutral-500 hover:text-neutral-700"
                    }`}
                  >
                    {s.l}
                  </button>
                ))}
              </div>
              <span className="text-xs text-neutral-400">— Türk fon + ETF birlikte</span>
            </div>

            <div className="bg-white rounded-xl border border-neutral-200 overflow-hidden">
              <div className="flex items-center gap-3 px-3 py-2 bg-neutral-50 border-b border-neutral-200 text-xs font-medium text-neutral-500">
                <span className="w-5">#</span>
                <span className="w-16">Tür</span>
                <span className="flex-1">Varlık</span>
                <span className="w-14 text-center">Aylık</span>
                <span className="w-14 text-center">Çeyreklik</span>
              </div>
              {mixedList.map((item, i) => (
                <Link key={`${item.type}-${item.code}`} href={item.href} className="group">
                  <div className="flex items-center gap-3 px-3 py-3 hover:bg-blue-50 transition border-b border-neutral-100 last:border-0">
                    <span className="text-sm font-bold text-neutral-400 w-5">{i + 1}</span>
                    <span className={`w-16 text-[10px] font-bold px-1.5 py-0.5 rounded-md text-center ${
                      item.type === "fund"
                        ? "bg-blue-50 text-blue-700"
                        : "bg-amber-50 text-amber-700"
                    }`}>
                      {item.type === "fund" ? "FON" : "ETF"}
                    </span>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-1.5">
                        <span className="text-sm font-semibold text-neutral-900 group-hover:text-blue-600 transition-colors">
                          {item.code}
                        </span>
                        <span className="text-xs text-neutral-400 truncate">{item.name}</span>
                      </div>
                      <div className="text-xs text-neutral-400 mt-0.5">{item.detail}</div>
                    </div>
                    <div className="w-14 text-center">
                      <PctCell value={item.monthly} />
                    </div>
                    <div className="w-14 text-center">
                      <PctCell value={item.quarterly} />
                    </div>
                  </div>
                </Link>
              ))}
            </div>
          </div>
        )}

        {/* Turkish only */}
        {tab === "turkish" && (
          <div>
            <div className="bg-white rounded-xl border border-neutral-200 overflow-hidden">
              <div className="flex items-center gap-3 px-3 py-2 bg-neutral-50 border-b border-neutral-200 text-xs font-medium text-neutral-500">
                <span className="w-5">#</span>
                <span className="flex-1">Fon</span>
                <span className="w-14 text-center">Haftalık</span>
                <span className="w-14 text-center">Aylık</span>
                <span className="w-14 text-center">Çeyreklik</span>
              </div>
              {topTurkish.map((f, i) => (
                <TurkishFundRow key={f.code} fund={f} rank={i + 1} />
              ))}
            </div>
          </div>
        )}

        {/* ETF only */}
        {tab === "etf" && (
          <div>
            <div className="bg-white rounded-xl border border-neutral-200 overflow-hidden">
              <div className="flex items-center gap-3 px-3 py-2 bg-neutral-50 border-b border-neutral-200 text-xs font-medium text-neutral-500">
                <span className="w-5">#</span>
                <span className="flex-1">ETF</span>
                <span className="w-14 text-center">YTD</span>
                <span className="w-14 text-center">3 Yıl</span>
                <span className="w-14 text-center">5 Yıl</span>
              </div>
              {topEtf.map((e, i) => (
                <EtfRow key={e.symbol} etf={e} rank={i + 1} />
              ))}
            </div>
          </div>
        )}

        {tab !== "mixed" && topTurkish.length === 0 && topEtf.length === 0 && (
          <div className="text-center py-16 text-neutral-400">
            <p className="text-lg">Veri henüz yüklenmedi</p>
          </div>
        )}
      </main>
    </div>
  );
}
