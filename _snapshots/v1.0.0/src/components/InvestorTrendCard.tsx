"use client";

import { useMemo } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Users, TrendingUp, TrendingDown, Minus, ArrowUpRight, ArrowDownRight, DollarSign } from "lucide-react";

interface PricePoint {
  date: string;
  price: number;
  change?: number;
  investors?: number | null;
  shares?: number | null;
  market_cap?: number | null;
}

interface InvestorTrendCardProps {
  priceHistory: PricePoint[];
  currentInvestors: number | null;
}

function fmtNum(n: number | null | undefined, decimals = 0): string {
  if (n == null) return "—";
  return n.toLocaleString("tr-TR", { maximumFractionDigits: decimals });
}

function fmtMoney(n: number | null | undefined): string {
  if (n == null) return "—";
  if (Math.abs(n) >= 1e9) return `${(n / 1e9).toFixed(2)}B ₺`;
  if (Math.abs(n) >= 1e6) return `${(n / 1e6).toFixed(1)}M ₺`;
  if (Math.abs(n) >= 1e3) return `${(n / 1e3).toFixed(0)}K ₺`;
  return `${n.toLocaleString("tr-TR")} ₺`;
}

function fmtMoneySimple(n: number): string {
  if (Math.abs(n) >= 1e9) return `${(n / 1e9).toFixed(2)}B`;
  if (Math.abs(n) >= 1e6) return `${(n / 1e6).toFixed(1)}M`;
  if (Math.abs(n) >= 1e3) return `${(n / 1e3).toFixed(0)}K`;
  return n.toFixed(0);
}

function Sparkline({ data, positive }: { data: number[]; positive: boolean }) {
  if (data.length < 2) return null;
  const min = Math.min(...data);
  const max = Math.max(...data);
  const range = max - min || 1;
  const width = 280;
  const height = 56;
  const points = data.map((v, i) => {
    const x = (i / (data.length - 1)) * width;
    const y = height - ((v - min) / range) * height;
    return `${x},${y}`;
  }).join(" ");

  return (
    <svg width="100%" height={height} viewBox={`0 0 ${width} ${height}`} className="w-full h-14 overflow-visible">
      <defs>
        <linearGradient id="invGrad" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={positive ? "#16a34a" : "#dc2626"} stopOpacity="0.15" />
          <stop offset="100%" stopColor={positive ? "#16a34a" : "#dc2626"} stopOpacity="0" />
        </linearGradient>
      </defs>
      <polyline
        points={points}
        fill="none"
        stroke={positive ? "#16a34a" : "#dc2626"}
        strokeWidth="2"
        strokeLinejoin="round"
        strokeLinecap="round"
      />
      <circle cx={points.split(" ")[points.split(" ").length - 1].split(",")[0]} cy={points.split(" ")[points.split(" ").length - 1].split(",")[1]} r="3" fill={positive ? "#16a34a" : "#dc2626"} />
    </svg>
  );
}

export default function InvestorTrendCard({ priceHistory, currentInvestors }: InvestorTrendCardProps) {
  const analysis = useMemo(() => {
    if (!priceHistory || priceHistory.length < 10) return null;

    // Get investor data points
    const investorPoints = priceHistory
      .map((p) => ({ date: p.date, investors: p.investors }))
      .filter((p) => p.investors != null && p.investors > 0)
      .sort((a, b) => a.date.localeCompare(b.date));

    if (investorPoints.length < 5) return null;

    const latest = investorPoints[investorPoints.length - 1].investors!;
    const oldest = investorPoints[0].investors!;
    const firstMonth = investorPoints[Math.min(21, investorPoints.length - 1)].investors!;
    const threeMonth = investorPoints[Math.min(63, investorPoints.length - 1)].investors!;

    const totalChange = latest - oldest;
    const totalChangePct = oldest > 0 ? (totalChange / oldest) * 100 : 0;
    const monthlyChange = latest - firstMonth;
    const monthlyChangePct = firstMonth > 0 ? (monthlyChange / firstMonth) * 100 : 0;
    const threeMonthChange = latest - threeMonth;
    const threeMonthChangePct = threeMonth > 0 ? (threeMonthChange / threeMonth) * 100 : 0;

    // Share data
    const sharePoints = priceHistory
      .map((p) => ({ date: p.date, shares: p.shares }))
      .filter((p) => p.shares != null && p.shares > 0)
      .sort((a, b) => a.date.localeCompare(b.date));

    const latestShares = sharePoints.length > 0 ? sharePoints[sharePoints.length - 1].shares : null;
    const oldestShares = sharePoints.length > 0 ? sharePoints[0].shares : null;
    const sharesChangePct = oldestShares && oldestShares > 0 && latestShares
      ? ((latestShares - oldestShares) / oldestShares) * 100 : 0;

    // Fund flow calculation using AUM
    const aumPoints = priceHistory
      .map((p) => ({ date: p.date, market_cap: p.market_cap }))
      .filter((p) => p.market_cap != null && p.market_cap > 0)
      .sort((a, b) => a.date.localeCompare(b.date));

    let fundFlow = null;
    let monthlyFundFlow = null;
    let totalFlowTL = null;
    let monthlyFlowTL = null;

    if (aumPoints.length >= 2 && sharePoints.length >= 2) {
      const latestAum = aumPoints[aumPoints.length - 1].market_cap!;
      const oldestAum = aumPoints[0].market_cap!;
      const firstMonthAum = aumPoints.length > 21 ? aumPoints[Math.min(21, aumPoints.length - 1)].market_cap! : oldestAum;

      const latestNav = investorPoints[investorPoints.length - 1].investors!;
      const oldestNav = investorPoints[0].investors!;
      const firstMonthNav = investorPoints[Math.min(21, investorPoints.length - 1)].investors!;

      const priceReturnPct = oldestNav > 0 ? ((latestNav - oldestNav) / oldestNav * 100) : 0;
      const monthlyPriceReturnPct = firstMonthNav > 0 ? ((latestNav - firstMonthNav) / firstMonthNav * 100) : 0;

      const aumChangePct = oldestAum > 0 ? ((latestAum - oldestAum) / oldestAum) * 100 : 0;
      const monthlyAumChangePct = firstMonthAum > 0 ? ((latestAum - firstMonthAum) / firstMonthAum) * 100 : 0;

      fundFlow = aumChangePct - priceReturnPct;
      monthlyFundFlow = monthlyAumChangePct - monthlyPriceReturnPct;

      // Approximate TL flow: AUM change not explained by price
      const totalAumChange = latestAum - oldestAum;
      const priceContribution = oldestAum * (priceReturnPct / 100);
      totalFlowTL = totalAumChange - priceContribution;

      const monthlyAumChange = latestAum - firstMonthAum;
      const monthlyPriceContribution = firstMonthAum * (monthlyPriceReturnPct / 100);
      monthlyFlowTL = monthlyAumChange - monthlyPriceContribution;
    }

    // Sparkline
    const sparkData = investorPoints.map((p) => p.investors as number);
    const sparkPositive = totalChange >= 0;

    // Investor momentum
    const momentum = monthlyChangePct > 2 ? "strong_inflow" : monthlyChangePct < -2 ? "strong_outflow" : "stable";

    return {
      current: latest,
      totalChange,
      totalChangePct,
      monthlyChange,
      monthlyChangePct,
      threeMonthChange,
      threeMonthChangePct,
      latestShares,
      sharesChangePct,
      sparkData,
      sparkPositive,
      fundFlow,
      monthlyFundFlow,
      totalFlowTL,
      monthlyFlowTL,
      momentum,
      investorPoints,
    };
  }, [priceHistory]);

  if (!analysis) {
    return (
      <Card>
        <CardContent className="p-4">
          <h3 className="text-sm font-semibold text-neutral-700 mb-3 flex items-center gap-2">
            <Users className="w-4 h-4" />
            Yatırımcı Eğilimi
          </h3>
          <div className="flex flex-col items-center justify-center py-4 text-center">
            <div className="text-3xl mb-2">👥</div>
            <div className="text-sm text-neutral-500">Yeterli veri yok</div>
          </div>
        </CardContent>
      </Card>
    );
  }

  const {
    current, totalChange, totalChangePct,
    monthlyChange, monthlyChangePct,
    threeMonthChange, threeMonthChangePct,
    latestShares, sharesChangePct,
    sparkData, sparkPositive, fundFlow, monthlyFundFlow,
    totalFlowTL, monthlyFlowTL, momentum, investorPoints
  } = analysis;

  const isPositive = totalChange >= 0;
  const trendColor = isPositive ? "text-green-600" : "text-red-600";
  const trendBg = isPositive ? "bg-green-50 border-green-200" : "bg-red-50 border-red-200";
  const trendIcon = isPositive ? <TrendingUp className="w-5 h-5" /> : <TrendingDown className="w-5 h-5" />;

  const momentumBadge = momentum === "strong_inflow"
    ? { label: "Güçlü Giriş", bg: "bg-green-100 text-green-700", icon: <ArrowUpRight className="w-4 h-4" /> }
    : momentum === "strong_outflow"
    ? { label: "Güçlü Çıkış", bg: "bg-red-100 text-red-700", icon: <ArrowDownRight className="w-4 h-4" /> }
    : { label: "Stabil", bg: "bg-neutral-100 text-neutral-600", icon: <Minus className="w-4 h-4" /> };

  const flowPositive = (totalFlowTL ?? 0) >= 0;
  const flowColor = (totalFlowTL ?? 0) === 0 ? "text-neutral-600" : flowPositive ? "text-green-600" : "text-red-600";
  const flowBg = (totalFlowTL ?? 0) === 0 ? "bg-neutral-50" : flowPositive ? "bg-green-50" : "bg-red-50";

  return (
    <Card>
      <CardContent className="p-4">
        <div className="flex items-center gap-2 mb-3">
          <h3 className="text-sm font-semibold text-neutral-700 flex items-center gap-2">
            <Users className="w-4 h-4" />
            Yatırımcı Eğilimi
          </h3>
          <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-semibold ${momentumBadge.bg}`}>
            {momentumBadge.icon}
            {momentumBadge.label}
          </span>
        </div>

        <div className="flex items-start gap-4">
          {/* Left: main stats */}
          <div className="flex-1 min-w-0">
            <div className="flex items-end gap-3 flex-wrap">
              <div>
                <div className="text-3xl font-black font-mono text-neutral-900 leading-none">
                  {fmtNum(current, 0)}
                </div>
                <div className="text-xs text-neutral-400 mt-0.5">yatırımcı</div>
              </div>

              <div className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded-xl border ${trendBg}`}>
                {trendIcon}
                <div className="flex flex-col">
                  <span className={`text-sm font-bold ${trendColor}`}>
                    {totalChange > 0 ? "+" : ""}{fmtNum(totalChange, 0)}
                  </span>
                  <span className={`text-xs ${trendColor}`}>
                    {totalChangePct >= 0 ? "+" : ""}{totalChangePct.toFixed(1)}%
                  </span>
                </div>
              </div>

              {/* Fund flow TL */}
              {totalFlowTL != null && (
                <div className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded-xl border ${flowBg} ${flowPositive ? "border-green-200" : "border-red-200"}`}>
                  <DollarSign className={`w-4 h-4 ${flowColor}`} />
                  <div className="flex flex-col">
                    <span className={`text-sm font-bold ${flowColor}`}>
                      {flowPositive ? "+" : ""}{fmtMoneySimple(totalFlowTL)}
                    </span>
                    <span className="text-xs text-neutral-400">
                      {monthlyFlowTL != null ? `${flowPositive ? "+" : ""}${fmtMoneySimple(monthlyFlowTL)}/ay` : "toplam"}
                    </span>
                  </div>
                </div>
              )}
            </div>

            {/* Period breakdown */}
            <div className="grid grid-cols-3 gap-3 mt-3 pt-3 border-t border-neutral-100">
              <div>
                <div className="text-xs text-neutral-400">1H Değişim</div>
                <div className={`text-sm font-bold font-mono ${monthlyChangePct >= 0 ? "text-green-600" : "text-red-600"}`}>
                  {monthlyChangePct >= 0 ? "+" : ""}{fmtNum(monthlyChange, 0)} ({(monthlyChangePct >= 0 ? "+" : "") + monthlyChangePct.toFixed(1)}%)
                </div>
              </div>
              <div>
                <div className="text-xs text-neutral-400">1A Değişim</div>
                <div className={`text-sm font-bold font-mono ${threeMonthChangePct >= 0 ? "text-green-600" : "text-red-600"}`}>
                  {threeMonthChangePct >= 0 ? "+" : ""}{fmtNum(threeMonthChange, 0)} ({(threeMonthChangePct >= 0 ? "+" : "") + threeMonthChangePct.toFixed(1)}%)
                </div>
              </div>
              <div>
                <div className="text-xs text-neutral-400">Toplam Değişim</div>
                <div className={`text-sm font-bold font-mono ${isPositive ? "text-green-600" : "text-red-600"}`}>
                  {isPositive ? "+" : ""}{fmtNum(totalChange, 0)} ({(totalChangePct >= 0 ? "+" : "") + totalChangePct.toFixed(1)}%)
                </div>
              </div>
            </div>

            {/* Fund flow percentage */}
            {fundFlow != null && (
              <div className="flex items-center gap-3 mt-2 pt-2 border-t border-neutral-100">
                <span className="text-xs text-neutral-400">Fon Akışı</span>
                <div className="flex items-center gap-2">
                  <div className={`text-xs font-bold font-mono px-1.5 py-0.5 rounded ${fundFlow >= 0 ? "bg-green-100 text-green-700" : "bg-red-100 text-red-700"}`}>
                    {fundFlow >= 0 ? "+" : ""}{fundFlow.toFixed(1)}%
                  </div>
                  {monthlyFundFlow != null && (
                    <span className="text-xs text-neutral-400">
                      (ay: {monthlyFundFlow >= 0 ? "+" : ""}{monthlyFundFlow.toFixed(1)}%)
                    </span>
                  )}
                </div>
              </div>
            )}

            {/* Shares */}
            {latestShares && (
              <div className="flex items-center gap-3 mt-1">
                <span className="text-xs text-neutral-400">Toplam Pay</span>
                <span className="text-xs font-mono font-semibold text-neutral-700">
                  {latestShares >= 1e9 ? `${(latestShares / 1e9).toFixed(2)}B` : `${(latestShares / 1e6).toFixed(1)}M`}
                  <span className={`ml-1 ${sharesChangePct >= 0 ? "text-green-500" : "text-red-500"}`}>
                    ({sharesChangePct >= 0 ? "+" : ""}{sharesChangePct.toFixed(1)}%)
                  </span>
                </span>
              </div>
            )}
          </div>

          {/* Right: sparkline */}
          {sparkData.length >= 2 && (
            <div className="shrink-0 w-48 hidden sm:block">
              <Sparkline data={sparkData} positive={sparkPositive} />
              <div className="text-xs text-neutral-400 text-center mt-1">
                {investorPoints[0]?.date?.split("T")[0]} → {investorPoints[investorPoints.length - 1]?.date?.split("T")[0]}
              </div>
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
