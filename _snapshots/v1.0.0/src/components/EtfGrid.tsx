"use client";

import Link from "next/link";
import { Card, CardContent } from "@/components/ui/card";

type HomeEtf = {
  symbol: string;
  name: string;
  price: number | null;
  price_try: number | null;
  currency: string | null;
  change_pct: number | null;
  expense_ratio: number | null;
  dividend_yield: number | null;
  aum: number | null;
  ytd_return: number | null;
  three_yr_return: number | null;
  five_yr_return: number | null;
  beta: number | null;
  asset_type: string | null;
  fund_family: string | null;
  updated_at: string | null;
};

function fmtAum(n: number | null): string {
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

function fmtPct(n: number | null, showSign = true): string {
  if (n == null) return "—";
  const sign = showSign && n > 0 ? "+" : "";
  return `${sign}${(n * 100).toFixed(2)}%`;
}

function ChangePill({ value }: { value: number | null }) {
  if (value == null) return <span className="text-xs text-neutral-400">—</span>;
  const isPos = value >= 0;
  return (
    <span className={`inline-flex items-center px-1.5 py-0.5 rounded text-xs font-medium ${
      isPos ? "bg-emerald-100 text-emerald-700" : "bg-red-100 text-red-700"
    }`}>
      {isPos ? "+" : ""}{(value * 100).toFixed(2)}%
    </span>
  );
}

const ASSET_TYPE_LABELS: Record<string, string> = {
  EQUITY: "Hisse",
  BOND: "Tahvil",
  COMMODITY: "Emtia",
  REAL_ESTATE: "Gayrimenkul",
  MONEY_MARKET: "Para Piyasası",
};

const ASSET_TYPE_COLORS: Record<string, string> = {
  EQUITY: "bg-blue-100 text-blue-700",
  BOND: "bg-green-100 text-green-700",
  COMMODITY: "bg-amber-100 text-amber-700",
  REAL_ESTATE: "bg-purple-100 text-purple-700",
  MONEY_MARKET: "bg-gray-100 text-gray-700",
};

export function EtfGrid({ etfs }: { etfs?: HomeEtf[] }) {
  if (!etfs || etfs.length === 0) {
    return (
      <div className="text-center py-24 text-neutral-400">
        <div className="text-base">ETF verisi bulunamadı</div>
      </div>
    );
  }

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-3">
      {etfs.map((etf) => {
        const assetColor = etf.asset_type ? (ASSET_TYPE_COLORS[etf.asset_type] || "bg-neutral-100 text-neutral-600") : "bg-neutral-100 text-neutral-600";

        return (
          <Link key={etf.symbol} href={`/etf/${etf.symbol}`} className="group block">
            <Card className="h-full transition-all duration-200 hover:shadow-lg hover:-translate-y-0.5 cursor-pointer">
              <CardContent className="p-3.5 flex flex-col h-full gap-1.5">
                {/* Row 1: symbol + type + change */}
                <div className="flex items-start justify-between">
                  <div>
                    <div className="flex items-center gap-1.5">
                      <span className="font-mono font-bold text-blue-600 text-sm group-hover:underline">
                        {etf.symbol}
                      </span>
                      {etf.asset_type && (
                        <span className={`text-[10px] px-1.5 py-0.5 rounded-full font-medium ${assetColor}`}>
                          {ASSET_TYPE_LABELS[etf.asset_type] || etf.asset_type}
                        </span>
                      )}
                    </div>
                    <div className="text-xs text-neutral-500 font-medium line-clamp-2 leading-snug mt-0.5 max-w-[180px]">
                      {etf.name}
                    </div>
                  </div>
                  <ChangePill value={etf.change_pct} />
                </div>

                {/* Price + Currency */}
                <div className="flex items-end justify-between pt-2 border-t border-neutral-100">
                  <div>
                    <div className="text-base font-black text-neutral-900 font-mono tracking-tight">
                      {fmtPrice(etf.price, etf.currency)}
                    </div>
                    {etf.currency && etf.currency !== "USD" && (
                      <div className="text-[10px] text-neutral-400">{etf.currency}</div>
                    )}
                  </div>
                  <div className="text-right">
                    <div className="text-sm font-semibold text-neutral-700">
                      {fmtAum(etf.aum)}
                    </div>
                    <div className="text-[10px] text-neutral-400">AUM</div>
                  </div>
                </div>

                {/* Returns */}
                {(etf.ytd_return != null || etf.expense_ratio != null || etf.dividend_yield != null) && (
                  <div className="flex items-center gap-2 flex-wrap">
                    {etf.ytd_return != null && (
                      <div className="flex items-center gap-0.5 text-xs">
                        <span className="text-neutral-400">YTD</span>
                        <span className={`font-semibold font-mono ${etf.ytd_return >= 0 ? "text-green-600" : "text-red-600"}`}>
                          {fmtPct(etf.ytd_return)}
                        </span>
                      </div>
                    )}
                    {etf.expense_ratio != null && (
                      <div className="flex items-center gap-0.5 text-xs">
                        <span className="text-neutral-400">Gider</span>
                        <span className="font-semibold font-mono text-neutral-600">
                          {fmtPct(etf.expense_ratio, false)}
                        </span>
                      </div>
                    )}
                    {etf.dividend_yield != null && (
                      <div className="flex items-center gap-0.5 text-xs">
                        <span className="text-neutral-400">Div.</span>
                        <span className="font-semibold font-mono text-neutral-600">
                          {fmtPct(etf.dividend_yield, false)}
                        </span>
                      </div>
                    )}
                  </div>
                )}

                {/* 3Y / 5Y returns */}
                {(etf.three_yr_return != null || etf.five_yr_return != null) && (
                  <div className="flex items-center gap-1.5">
                    {etf.three_yr_return != null && (
                      <div className="flex items-center gap-0.5 text-xs">
                        <span className="text-neutral-400">3Y</span>
                        <span className={`font-semibold font-mono ${etf.three_yr_return >= 0 ? "text-green-600" : "text-red-600"}`}>
                          {fmtPct(etf.three_yr_return)}
                        </span>
                      </div>
                    )}
                    {etf.five_yr_return != null && (
                      <div className="flex items-center gap-0.5 text-xs">
                        <span className="text-neutral-400">5Y</span>
                        <span className={`font-semibold font-mono ${etf.five_yr_return >= 0 ? "text-green-600" : "text-red-600"}`}>
                          {fmtPct(etf.five_yr_return)}
                        </span>
                      </div>
                    )}
                  </div>
                )}
              </CardContent>
            </Card>
          </Link>
        );
      })}
    </div>
  );
}
