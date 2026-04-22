"use client";

import { useState, useMemo } from "react";
import Link from "next/link";
import { ArrowLeft, TrendingUp, TrendingDown } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Logo } from "@/components/Logo";

const ASSET_TYPE_LABELS: Record<string, string> = {
  EQUITY: "Hisse",
  BOND: "Tahvil",
  COMMODITY: "Emtia",
  REAL_ESTATE: "Gayrimenkul",
};

const SECTOR_COLORS = [
  "bg-blue-500", "bg-green-500", "bg-amber-500", "bg-red-500",
  "bg-purple-500", "bg-pink-500", "bg-cyan-500", "bg-indigo-500",
  "bg-teal-500", "bg-orange-500",
];

function fmtNum(n: number | null, decimals = 2): string {
  if (n == null) return "—";
  return n.toLocaleString("tr-TR", { maximumFractionDigits: decimals });
}

function fmtMoney(n: number | null): string {
  if (n == null) return "—";
  if (n >= 1e12) return `$${(n / 1e12).toFixed(1)}T`;
  if (n >= 1e9) return `$${(n / 1e9).toFixed(1)}B`;
  if (n >= 1e6) return `$${(n / 1e6).toFixed(1)}M`;
  return `$${n.toLocaleString()}`;
}

function fmtPrice(n: number | null, currency: string | null): string {
  if (n == null) return "—";
  if (currency === "GBp") return `£${(n / 100).toFixed(2)}`;
  return `$${n.toFixed(2)}`;
}

function fmtPct(n: number | null, showSign = false): string {
  if (n == null) return "—";
  const sign = showSign && n > 0 ? "+" : "";
  return `${sign}${n.toFixed(2)}%`;
}

function ChangePill({ value, size = "md" }: { value: number | null; size?: "sm" | "md" }) {
  if (value == null) return <span className="text-neutral-400">—</span>;
  const isPos = value >= 0;
  const cls = size === "sm"
    ? `px-1.5 py-0.5 text-xs`
    : `px-2 py-1 text-sm`;
  return (
    <span className={`inline-flex items-center gap-0.5 rounded font-bold ${cls} ${
      isPos ? "bg-emerald-100 text-emerald-700" : "bg-red-100 text-red-700"
    }`}>
      {isPos ? <TrendingUp className="w-3 h-3" /> : <TrendingDown className="w-3 h-3" />}
      {isPos ? "+" : ""}{fmtNum(value, 2)}%
    </span>
  );
}

interface PriceRow { date: string; close: number | string }
interface Holding { holding_symbol: string; holding_name: string; weight: number }
interface Sector { sector: string; weight: number }

function MiniSparkline({ data }: { data: PriceRow[] }) {
  const prices = data.map((p) => typeof p.close === "number" ? p.close : parseFloat(String(p.close)));
  if (prices.length < 2) return null;
  const min = Math.min(...prices);
  const max = Math.max(...prices);
  const range = max - min || 1;
  const W = 80, H = 28;
  const pts = prices.map((p, i) => {
    const x = (i / (prices.length - 1)) * W;
    const y = H - ((p - min) / range) * H;
    return `${x},${y}`;
  }).join(" ");
  const isUp = prices[prices.length - 1] >= prices[0];
  const color = isUp ? "#10b981" : "#ef4444";
  return (
    <svg width={W} height={H} className="overflow-visible">
      <polyline points={pts} fill="none" stroke={color} strokeWidth="1.5" />
    </svg>
  );
}

function SectorBar({ sectors }: { sectors: Sector[] }) {
  return (
    <div className="space-y-2">
      {sectors.map((s, i) => (
        <div key={s.sector} className="flex items-center gap-2">
          <span className="text-xs text-neutral-600 w-28 truncate shrink-0">{s.sector}</span>
          <div className="flex-1 bg-neutral-100 rounded-full h-2 overflow-hidden">
            <div
              className={`h-full rounded-full ${SECTOR_COLORS[i % SECTOR_COLORS.length]}`}
              style={{ width: `${Math.min(s.weight, 100)}%` }}
            />
          </div>
          <span className="text-xs font-semibold text-neutral-700 w-10 text-right">
            {s.weight.toFixed(1)}%
          </span>
        </div>
      ))}
    </div>
  );
}

function HoldingsTable({ holdings }: { holdings: Holding[] }) {
  return (
    <div className="space-y-1.5">
      {holdings.map((h) => (
        <div key={h.holding_symbol} className="flex items-center gap-3 py-1.5 border-b border-neutral-50 last:border-0">
          <div className="w-16 shrink-0">
            <span className="text-xs font-bold text-neutral-800">{h.holding_symbol}</span>
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-xs text-neutral-600 truncate">{h.holding_name}</p>
          </div>
          <div className="w-16 text-right">
            <span className="text-xs font-semibold text-blue-600">
              {h.weight.toFixed(2)}%
            </span>
          </div>
          <div className="w-20 bg-neutral-100 rounded-full h-1.5 overflow-hidden">
            <div
              className="h-full bg-blue-500 rounded-full"
              style={{ width: `${Math.min(h.weight * 2, 100)}%` }}
            />
          </div>
        </div>
      ))}
    </div>
  );
}

function EtfPriceChart({ data }: { data: PriceRow[] }) {
  const prices = data.map((p) => typeof p.close === "number" ? p.close : parseFloat(String(p.close)));
  if (prices.length < 2) return <div className="text-xs text-neutral-400 py-8 text-center">Fiyat verisi yok</div>;
  const min = Math.min(...prices);
  const max = Math.max(...prices);
  const range = max - min || 1;
  const W = 800, H = 200;
  const dates = data.map((p) => p.date);
  const svgW = W;
  const svgH = H;
  const pts = prices.map((p, i) => {
    const x = (i / (prices.length - 1)) * svgW;
    const y = svgH - ((p - min) / range) * svgH;
    return `${x},${y}`;
  }).join(" ");
  const areaPts = `0,${svgH} ${pts} ${svgW},${svgH}`;
  const isUp = prices[prices.length - 1] >= prices[0];
  const lineColor = isUp ? "#10b981" : "#ef4444";
  const gradId = `grad-${isUp ? "up" : "down"}`;

  // X-axis labels: first, middle, last
  const labelPositions = [0, Math.floor(dates.length / 2), dates.length - 1];
  const labels = labelPositions.map((i) => ({
    x: (i / (dates.length - 1)) * svgW,
    label: dates[i]?.slice(0, 10) || "",
  }));

  return (
    <div className="w-full overflow-hidden">
      <svg viewBox={`0 0 ${svgW} ${svgH + 20}`} className="w-full h-auto" preserveAspectRatio="none">
        <defs>
          <linearGradient id={gradId} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={lineColor} stopOpacity="0.15" />
            <stop offset="100%" stopColor={lineColor} stopOpacity="0.02" />
          </linearGradient>
        </defs>
        <polygon points={areaPts} fill={`url(#${gradId})`} />
        <polyline points={pts} fill="none" stroke={lineColor} strokeWidth="2" />
        {labels.map((l) => (
          <text key={l.label} x={l.x} y={svgH + 14} textAnchor="middle" fontSize="10" fill="#9ca3af">
            {l.label}
          </text>
        ))}
      </svg>
    </div>
  );
}

export default function EtfDetailClient({
  etf,
  holdings,
  sectors,
  prices,
}: {
  etf: any;
  holdings: Holding[];
  sectors: Sector[];
  prices: PriceRow[];
}) {
  const [chartPeriod, setChartPeriod] = useState<"1M" | "3M" | "6M" | "1Y">("1Y");

  const filteredPrices = useMemo(() => {
    if (!prices.length) return [];
    const now = new Date(prices[prices.length - 1]?.date);
    const cutoff = new Date(now);
    switch (chartPeriod) {
      case "1M": cutoff.setMonth(now.getMonth() - 1); break;
      case "3M": cutoff.setMonth(now.getMonth() - 3); break;
      case "6M": cutoff.setMonth(now.getMonth() - 6); break;
      case "1Y": cutoff.setFullYear(now.getFullYear() - 1); break;
    }
    return prices.filter((p) => new Date(p.date) >= cutoff);
  }, [prices, chartPeriod]);

  const priceChange = useMemo(() => {
    if (filteredPrices.length < 2) return null;
    const first = typeof filteredPrices[0].close === "number"
      ? filteredPrices[0].close as number
      : parseFloat(String(filteredPrices[0].close));
    const last = typeof filteredPrices[filteredPrices.length - 1].close === "number"
      ? filteredPrices[filteredPrices.length - 1].close as number
      : parseFloat(String(filteredPrices[filteredPrices.length - 1].close));
    return ((last - first) / first) * 100;
  }, [filteredPrices]);

  const isEquity = etf.asset_type === "EQUITY";
  const isBond = etf.asset_type === "BOND";

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
            <Link href="/companies" className="px-3 py-1.5 text-sm font-medium text-neutral-600 hover:text-blue-600 hover:bg-blue-50 rounded-lg transition">Şirketler</Link>
            <Link href="/holdings" className="px-3 py-1.5 text-sm font-medium text-neutral-600 hover:text-blue-600 hover:bg-blue-50 rounded-lg transition">Hisse Tercihleri</Link>
            <Link href="/performers" className="px-3 py-1.5 text-sm font-medium text-neutral-600 hover:text-blue-600 hover:bg-blue-50 rounded-lg transition">En Çok Kazandıranlar</Link>
            <Link href="/etf" className="px-3 py-1.5 text-sm font-medium text-blue-600 bg-blue-50 rounded-lg">Yabancı ETF</Link>
          </nav>
          <div className="h-6 w-px bg-neutral-200 hidden sm:block" />
          <Link
            href="/etf"
            className="flex items-center gap-1 text-sm text-neutral-500 hover:text-blue-600 transition ml-auto"
          >
            <ArrowLeft className="w-4 h-4" />
            <span className="hidden sm:inline">ETF'lere Dön</span>
          </Link>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-3 sm:px-4 py-6">
        {/* ETF title + badges */}
        <div className="flex flex-wrap items-start gap-3 mb-6">
          <div className="flex-1 min-w-0">
            <div className="flex flex-wrap items-center gap-2 mb-1">
              <h1 className="text-3xl font-bold text-neutral-900">{etf.symbol}</h1>
              {etf.asset_type && (
                <span className="px-2 py-0.5 rounded-full text-xs font-semibold bg-blue-100 text-blue-700">
                  {ASSET_TYPE_LABELS[etf.asset_type] || etf.asset_type}
                </span>
              )}
              <Badge variant="secondary" className="text-xs">{etf.currency}</Badge>
            </div>
            <p className="text-sm text-neutral-500 mb-3">{etf.name}</p>
            {/* Stats row */}
            <div className="flex flex-wrap items-center gap-4">
              <div>
                <p className="text-xs text-neutral-400">Fiyat</p>
                <p className="text-2xl font-bold text-neutral-900">
                  {fmtPrice(etf.price, etf.currency)}
                  {etf.price_try && etf.currency !== "TRY" && (
                    <span className="text-sm font-normal text-neutral-400 ml-1">
                      ≈ ₺{etf.price_try.toLocaleString("tr-TR", { maximumFractionDigits: 2 })}
                    </span>
                  )}
                </p>
              </div>
              <div>
                <p className="text-xs text-neutral-400">NAV</p>
                <p className="text-lg font-semibold text-neutral-700">
                  {etf.nav_price ? fmtPrice(etf.nav_price, etf.currency) : "—"}
                </p>
              </div>
              <div>
                <p className="text-xs text-neutral-400">Günlük</p>
                <ChangePill value={etf.change_pct} />
              </div>
              <div>
                <p className="text-xs text-neutral-400">AUM</p>
                <p className="text-sm font-semibold text-neutral-700">{fmtMoney(etf.aum)}</p>
              </div>
            </div>
          </div>
        </div>

        {/* Price chart */}
        <div className="bg-white rounded-xl border border-neutral-200 p-4 mb-6">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h2 className="text-base font-semibold text-neutral-800">Fiyat Grafiği</h2>
              {priceChange != null && (
                <ChangePill value={priceChange} size="sm" />
              )}
            </div>
            <div className="flex gap-1">
              {(["1M", "3M", "6M", "1Y"] as const).map((p) => (
                <button
                  key={p}
                  onClick={() => setChartPeriod(p)}
                  className={`px-3 py-1 rounded text-xs font-medium transition ${
                    chartPeriod === p
                      ? "bg-blue-600 text-white"
                      : "bg-neutral-100 text-neutral-600 hover:bg-neutral-200"
                  }`}
                >
                  {p}
                </button>
              ))}
            </div>
          </div>
          <EtfPriceChart data={filteredPrices.length ? filteredPrices : prices} />
        </div>

        {/* Key metrics grid */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-6">
          {[
            { label: "Gider Oranı", value: etf.expense_ratio != null ? `${etf.expense_ratio.toFixed(3)}%` : "—" },
            { label: "Temettü Verimi", value: fmtPct(etf.dividend_yield) },
            { label: "Beta", value: etf.beta?.toFixed(2) ?? "—" },
            { label: "YTD Getiri", value: fmtPct(etf.ytd_return, true), color: (etf.ytd_return ?? 0) >= 0 ? "emerald" : "red" },
            ...(isEquity ? [
              { label: "3 Yıl Ort.", value: fmtPct(etf.three_yr_return, true), color: (etf.three_yr_return ?? 0) >= 0 ? "emerald" : "red" },
              { label: "5 Yıl Ort.", value: fmtPct(etf.five_yr_return, true), color: (etf.five_yr_return ?? 0) >= 0 ? "emerald" : "red" },
            ] : [
              { label: "Fon Ailesi", value: etf.fund_family || "—", color: "neutral" as const },
              { label: "Kategori", value: etf.category || "—", color: "neutral" as const },
            ]),
          ].map((item) => (
            <div key={item.label} className="bg-white rounded-xl border border-neutral-200 p-3">
              <p className="text-xs text-neutral-400 mb-0.5">{item.label}</p>
              <p className={`text-base font-bold ${
                item.color === "emerald" ? "text-emerald-600" :
                item.color === "red" ? "text-red-600" : "text-neutral-900"
              }`}>
                {item.value}
              </p>
            </div>
          ))}
        </div>

        {/* Two-column: holdings + sectors */}
        {(holdings.length > 0 || sectors.length > 0) && (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-6">
            {/* Top Holdings */}
            {holdings.length > 0 && (
              <div className="bg-white rounded-xl border border-neutral-200 p-4">
                <h2 className="text-base font-semibold text-neutral-800 mb-3">
                  Portföy Dağılımı
                  <span className="text-xs font-normal text-neutral-400 ml-2">
                    ({holdings.length} holding)
                  </span>
                </h2>
                <HoldingsTable holdings={holdings} />
              </div>
            )}

            {/* Sectors */}
            {sectors.length > 0 && (
              <div className="bg-white rounded-xl border border-neutral-200 p-4">
                <h2 className="text-base font-semibold text-neutral-800 mb-3">
                  Sektör Dağılımı
                </h2>
                <SectorBar sectors={sectors} />
              </div>
            )}
          </div>
        )}

        {/* Meta info */}
        <div className="bg-white rounded-xl border border-neutral-200 p-4">
          <div className="grid grid-cols-2 gap-3 text-xs text-neutral-500">
            <div>
              <span className="font-medium text-neutral-700">Fon Ailesi: </span>
              {etf.fund_family || "—"}
            </div>
            <div>
              <span className="font-medium text-neutral-700">Kategori: </span>
              {etf.category || "—"}
            </div>
            <div>
              <span className="font-medium text-neutral-700">Bölge: </span>
              {etf.region || "—"}
            </div>
            <div>
              <span className="font-medium text-neutral-700">Son Güncelleme: </span>
              {etf.updated_at ? new Date(etf.updated_at).toLocaleString("tr-TR") : "—"}
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}
