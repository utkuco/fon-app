"use client";

import { useMemo } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Activity, TrendingUp, TrendingDown, Info } from "lucide-react";

interface PricePoint {
  date: string;
  price: number;
  change?: number;
}

interface SharpeRatioCardProps {
  priceHistory: PricePoint[];
  currentPrice: number | null;
  riskFreeRate?: number;
}

export default function SharpeRatioCard({ priceHistory, currentPrice, riskFreeRate = 0.20 }: SharpeRatioCardProps) {
  const analysis = useMemo(() => {
    if (!priceHistory || priceHistory.length < 30) return null;

    const dailyRiskFree = riskFreeRate / 365;

    const dailyReturns = priceHistory.slice(1).map((p, i) => {
      const prev = priceHistory[i].price;
      return prev > 0 ? (p.price - prev) / prev : 0;
    });

    if (dailyReturns.length < 20) return null;

    const avgDailyReturn = dailyReturns.reduce((s, r) => s + r, 0) / dailyReturns.length;
    const variance = dailyReturns.reduce((s, r) => s + (r - avgDailyReturn) ** 2, 0) / dailyReturns.length;
    const dailyStd = Math.sqrt(variance);
    const annualizedStd = dailyStd * Math.sqrt(252);

    const annualizedReturn = avgDailyReturn * 252;

    const sharpe = annualizedStd > 0 ? (annualizedReturn - riskFreeRate) / annualizedStd : 0;

    const negativeReturns = dailyReturns.filter(r => r < 0);
    const downsideVariance = negativeReturns.length > 0
      ? negativeReturns.reduce((s, r) => s + r ** 2, 0) / negativeReturns.length
      : 0;
    const downsideStd = Math.sqrt(downsideVariance) * Math.sqrt(252);
    const sortino = downsideStd > 0 ? (annualizedReturn - riskFreeRate) / downsideStd : 0;

    let maxDrawdown = 0;
    let peak = priceHistory[0].price;
    for (const p of priceHistory) {
      if (p.price > peak) peak = p.price;
      const dd = (p.price - peak) / peak;
      if (dd < maxDrawdown) maxDrawdown = dd;
    }

    const calmar = Math.abs(maxDrawdown) > 0 ? annualizedReturn / Math.abs(maxDrawdown) : 0;

    return {
      sharpe,
      sortino,
      calmar,
      annualizedReturn,
      annualizedStd,
      maxDrawdown,
      riskFreeRate,
    };
  }, [priceHistory, riskFreeRate]);

  if (!analysis) {
    return (
      <Card>
        <CardContent className="p-4">
          <h3 className="text-sm font-semibold text-neutral-700 mb-3 flex items-center gap-2">
            <Activity className="w-4 h-4" />
            Risk-Ayarı Getiri
          </h3>
          <div className="flex flex-col items-center justify-center py-4 text-center">
            <div className="text-3xl mb-1">📊</div>
            <div className="text-sm text-neutral-500">Yeterli veri yok</div>
          </div>
        </CardContent>
      </Card>
    );
  }

  const { sharpe, sortino, calmar, annualizedReturn, annualizedStd, maxDrawdown, riskFreeRate: rf } = analysis;

  const sharpeColor = sharpe > 1 ? "text-green-600" : sharpe > 0.5 ? "text-yellow-600" : "text-red-600";
  const sharpeBarColor = sharpe > 1 ? "bg-green-500" : sharpe > 0.5 ? "bg-yellow-400" : "bg-red-400";
  const sharpeDesc = sharpe > 2 ? "Çok yüksek — üstün performans" : sharpe > 1 ? "İyi — risk başına güçlü getiri" : sharpe > 0.5 ? "Orta — risksiz getiri üstü" : sharpe > 0 ? "Zayıf — risksiz faiz altında" : "Negatif — risksiz faiz bile kaybettiriyor";

  const sortinoColor = sortino > 1.5 ? "text-green-600" : sortino > 0.5 ? "text-yellow-600" : "text-red-600";
  const sortinoDesc = sortino > 1.5 ? "İyi — düşüş riski düşük" : sortino > 0.5 ? "Orta" : "Zayıf";

  const calmarColor = calmar > 1 ? "text-green-600" : calmar > 0 ? "text-yellow-600" : "text-red-600";
  const calmarDesc = calmar > 1 ? "Güçlü — max kayıba göre iyi getiri" : calmar > 0 ? "Orta" : "Dikkat — kayıp riski yüksek";

  return (
    <Card>
      <CardContent className="p-4">
        <h3 className="text-sm font-semibold text-neutral-700 mb-4 flex items-center gap-2">
          <Activity className="w-4 h-4" />
          Risk-Ayarı Getiri
        </h3>

        <div className="space-y-4">

          {/* ─── Sharpe Ratio (Hero) ─── */}
          <div className="p-3 rounded-xl bg-neutral-50 border border-neutral-200">
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center gap-1">
                <span className="text-sm font-semibold text-neutral-700">Sharpe Oranı</span>
                <span className="text-neutral-300" title="Risksiz getiri (mevduat faizi) üstü alınan getiri / alınan risk. 1+ iyi, 2+ çok iyi.">
                  <Info className="w-3.5 h-3.5" />
                </span>
              </div>
              <span className={`text-xl font-black font-mono ${sharpeColor}`}>
                {sharpe > 0 ? "+" : ""}{sharpe.toFixed(2)}
              </span>
            </div>
            <div className="h-2.5 bg-neutral-100 rounded-full overflow-hidden">
              <div
                className={`h-full rounded-full ${sharpeBarColor}`}
                style={{ width: `${Math.min(100, Math.max(0, (sharpe + 1) / 3 * 100))}%` }}
              />
            </div>
            <div className={`text-xs mt-1.5 font-semibold ${sharpeColor}`}>{sharpeDesc}</div>
            <div className="text-xs text-neutral-400 mt-1 leading-relaxed">
              Risksiz getiri oranı: <span className="font-mono">%{(rf * 100).toFixed(0)}</span> (TL mevduat). Formül: <span className="font-mono">(Yıllık Getiri − Risksiz Oran) ÷ Yıllık Volatilite</span>
            </div>
          </div>

          {/* ─── Sortino Ratio ─── */}
          <div className="flex items-start justify-between p-3 rounded-lg bg-neutral-50">
            <div>
              <div className="flex items-center gap-1 mb-1">
                <span className="text-xs font-semibold text-neutral-600">Sortino Oranı</span>
                <span className="text-neutral-300" title="Sadece düşüş günlerinin riskini hesaba katar — yatırımcının gerçek kayıp korkusunu yansıtır">
                  <Info className="w-3.5 h-3.5" />
                </span>
              </div>
              <div className="text-lg font-bold font-mono text-neutral-400">
                {sortino > 0 ? "+" : ""}{sortino.toFixed(2)}
              </div>
            </div>
            <div className={`text-xs font-semibold px-2 py-1 rounded-full ${sortino > 1.5 ? "bg-green-100 text-green-700" : sortino > 0.5 ? "bg-yellow-100 text-yellow-700" : "bg-red-100 text-red-700"}`}>
              {sortinoColor.includes("green") ? "İyi" : sortinoColor.includes("yellow") ? "Orta" : "Zayıf"}
            </div>
          </div>
          <div className="text-xs text-neutral-400 -mt-2 leading-relaxed px-1">
            Sadece <span className="text-orange-500 font-medium">kayıp günlerin</span> standart sapmasını kullanır. Sharpe'tan daha hassas — yüksek = düşüşler öngörülebilir. {sortinoDesc.toLowerCase()}
          </div>

          {/* ─── Calmar Ratio ─── */}
          <div className="flex items-start justify-between p-3 rounded-lg bg-neutral-50">
            <div>
              <div className="flex items-center gap-1 mb-1">
                <span className="text-xs font-semibold text-neutral-600">Calmar Oranı</span>
                <span className="text-neutral-300" title="Yıllık getiri / Max drawdown. En kötü kaybın ne kadar getiri sağladığını gösterir">
                  <Info className="w-3.5 h-3.5" />
                </span>
              </div>
              <div className="text-lg font-bold font-mono text-neutral-400">
                {calmar > 0 ? "+" : ""}{calmar.toFixed(2)}
              </div>
            </div>
            <div className={`text-xs font-semibold px-2 py-1 rounded-full ${calmar > 1 ? "bg-green-100 text-green-700" : calmar > 0 ? "bg-yellow-100 text-yellow-700" : "bg-red-100 text-red-700"}`}>
              {calmar > 1 ? "Güçlü" : calmar > 0 ? "Orta" : "Dikkat"}
            </div>
          </div>
          <div className="text-xs text-neutral-400 -mt-2 leading-relaxed px-1">
            Yıllık getiri / <span className="text-red-500 font-medium">Max Drawdown</span>. En kötü kayıp başına ne kadar getiri alındığını gösterir. {calmarDesc.toLowerCase()}
          </div>

          {/* ─── Supporting Metrics ─── */}
          <div className="pt-3 border-t border-neutral-100 grid grid-cols-2 gap-3">
            <div>
              <div className="text-xs text-neutral-400 mb-1">Yıllık Getiri</div>
              <div className={`text-sm font-bold font-mono ${annualizedReturn >= 0 ? "text-green-600" : "text-red-600"}`}>
                {annualizedReturn >= 0 ? "+" : ""}{(annualizedReturn * 100).toFixed(1)}%
              </div>
            </div>
            <div>
              <div className="text-xs text-neutral-400 mb-1">Yıllık Volatilite</div>
              <div className="text-sm font-bold font-mono text-neutral-600">
                {(annualizedStd * 100).toFixed(1)}%
              </div>
            </div>
          </div>

          {/* ─── Quick Guide ─── */}
          <div className="pt-2 border-t border-neutral-100">
            <div className="text-xs font-medium text-neutral-500 mb-2">Nasıl okunur?</div>
            <div className="space-y-1.5">
              <div className="flex items-start gap-2">
                <TrendingUp className="w-3.5 h-3.5 text-green-500 mt-0.5 shrink-0" />
                <div className="text-xs text-neutral-400 leading-relaxed">
                  <span className="font-semibold text-neutral-600">Sharpe &gt; 1</span> — risk başına iyi getiri, risksiz faizin üstünde
                </div>
              </div>
              <div className="flex items-start gap-2">
                <TrendingUp className="w-3.5 h-3.5 text-green-500 mt-0.5 shrink-0" />
                <div className="text-xs text-neutral-400 leading-relaxed">
                  <span className="font-semibold text-neutral-600">Sortino &gt; 1.5</span> — düşüş riski düşük, kayıplar kontrol altında
                </div>
              </div>
              <div className="flex items-start gap-2">
                <TrendingUp className="w-3.5 h-3.5 text-green-500 mt-0.5 shrink-0" />
                <div className="text-xs text-neutral-400 leading-relaxed">
                  <span className="font-semibold text-neutral-600">Calmar &gt; 1</span> — en kötü günde bile güçlü getiri
                </div>
              </div>
            </div>
          </div>

        </div>
      </CardContent>
    </Card>
  );
}
