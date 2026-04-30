"use client";

import { useMemo } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { BarChart2, TrendingUp, Target, Info } from "lucide-react";

interface PricePoint {
  date: string;
  price: number;
  change?: number;
}

interface BenchmarkPoint {
  date: string;
  avg_return: number;
}

interface BetaAlphaCardProps {
  priceHistory: PricePoint[];
  fundType: string;
  benchmarkData: BenchmarkPoint[];
}

function pearsonCorr(x: number[], y: number[]): number {
  const n = Math.min(x.length, y.length);
  if (n < 4) return 0;
  const sumX = x.reduce((a, b) => a + b, 0);
  const sumY = y.reduce((a, b) => a + b, 0);
  const sumXY = x.reduce((acc, xi, i) => acc + xi * y[i], 0);
  const sumX2 = x.reduce((a, b) => a + b * b, 0);
  const sumY2 = y.reduce((a, b) => a + b * b, 0);
  const num = n * sumXY - sumX * sumY;
  const den = Math.sqrt((n * sumX2 - sumX * sumX) * (n * sumY2 - sumY * sumY));
  return den === 0 ? 0 : num / den;
}

export default function BetaAlphaCard({ priceHistory, fundType, benchmarkData }: BetaAlphaCardProps) {
  const metrics = useMemo(() => {
    if (!priceHistory || priceHistory.length < 30 || !benchmarkData || benchmarkData.length < 10) {
      return null;
    }

    // Sort and align dates
    const sortedPH = [...priceHistory].sort((a, b) => a.date.localeCompare(b.date));
    const sortedBM = [...benchmarkData].sort((a, b) => a.date.localeCompare(b.date));

    // Build date → return map for benchmark
    const bmMap = new Map<string, number>();
    for (const p of sortedBM) {
      bmMap.set(p.date.slice(0, 10), p.avg_return);
    }

    // Match fund returns to benchmark dates
    const fundReturns: number[] = [];
    const bmReturns: number[] = [];

    for (let i = 1; i < sortedPH.length; i++) {
      const date = sortedPH[i].date.slice(0, 10);
      const prevPrice = sortedPH[i - 1].price;
      const currPrice = sortedPH[i].price;
      if (prevPrice <= 0) continue;
      const fundRet = (currPrice - prevPrice) / prevPrice;
      const bmRet = bmMap.get(date);
      if (bmRet !== undefined) {
        fundReturns.push(fundRet);
        bmReturns.push(bmRet);
      }
    }

    if (fundReturns.length < 20) return null;

    // Beta
    const meanFund = fundReturns.reduce((a, b) => a + b, 0) / fundReturns.length;
    const meanBM = bmReturns.reduce((a, b) => a + b, 0) / bmReturns.length;
    const cov = fundReturns.reduce((acc, r, i) => acc + (r - meanFund) * (bmReturns[i] - meanBM), 0) / fundReturns.length;
    const varBM = bmReturns.reduce((acc, r) => acc + (r - meanBM) ** 2, 0) / bmReturns.length;
    const beta = varBM > 0 ? cov / varBM : 0;

    // Alpha (annualized)
    const excessReturn = meanFund - meanBM;
    const alpha = excessReturn * 252;

    // R-squared
    const corr = pearsonCorr(fundReturns, bmReturns);
    const rSquared = corr * corr;

    // Tracking error
    const trackingErrors = fundReturns.map((r, i) => r - bmReturns[i]);
    const meanTE = trackingErrors.reduce((a, b) => a + b, 0) / trackingErrors.length;
    const trackingError = Math.sqrt(trackingErrors.reduce((a, b) => a + (b - meanTE) ** 2, 0) / trackingErrors.length) * Math.sqrt(252);

    // Information ratio
    const infoRatio = trackingError > 0 ? (excessReturn * 252) / trackingError : 0;

    // Interpretation
    const betaLabel = beta < 0.5 ? "Çok Düşük" : beta < 0.8 ? "Düşük" : beta < 1.2 ? "Piyasa ile Paralel" : beta < 1.5 ? "Yüksek" : "Çok Yüksek";
    const betaColor = beta < 0.5 ? "text-blue-600" : beta < 0.8 ? "text-cyan-600" : beta < 1.2 ? "text-neutral-600" : beta < 1.5 ? "text-orange-600" : "text-red-600";
    const betaBg = beta < 0.5 ? "bg-blue-50" : beta < 0.8 ? "bg-cyan-50" : beta < 1.2 ? "bg-neutral-50" : beta < 1.5 ? "bg-orange-50" : "bg-red-50";

    const alphaLabel = alpha > 0.05 ? "Üstün" : alpha > 0 ? "Hafif Üstün" : alpha > -0.02 ? "Piyasa Paralel" : alpha > -0.1 ? "Hafif Zayıf" : "Zayıf";
    const alphaColor = alpha > 0.05 ? "text-green-600" : alpha > 0 ? "text-emerald-600" : alpha > -0.02 ? "text-neutral-600" : alpha > -0.1 ? "text-orange-600" : "text-red-600";
    const alphaBg = alpha > 0.05 ? "bg-green-50" : alpha > 0 ? "bg-emerald-50" : alpha > -0.02 ? "bg-neutral-50" : alpha > -0.1 ? "bg-orange-50" : "bg-red-50";

    const r2Label = rSquared > 0.8 ? "Çok Güçlü" : rSquared > 0.5 ? "Güçlü" : rSquared > 0.2 ? "Orta" : rSquared > 0.05 ? "Zayıf" : "Çok Zayıf";
    const r2Color = rSquared > 0.8 ? "text-green-600" : rSquared > 0.5 ? "text-emerald-600" : rSquared > 0.2 ? "text-yellow-600" : rSquared > 0.05 ? "text-orange-600" : "text-red-600";
    const r2Bg = rSquared > 0.8 ? "bg-green-50" : rSquared > 0.5 ? "bg-emerald-50" : rSquared > 0.2 ? "bg-yellow-50" : rSquared > 0.05 ? "bg-orange-50" : "bg-red-50";

    return {
      beta: parseFloat(beta.toFixed(3)),
      alpha: parseFloat(alpha.toFixed(4)),
      rSquared: parseFloat(rSquared.toFixed(3)),
      trackingError: parseFloat(trackingError.toFixed(3)),
      infoRatio: parseFloat(infoRatio.toFixed(3)),
      corr: parseFloat(corr.toFixed(3)),
      fundReturn: parseFloat((meanFund * 252 * 100).toFixed(2)),
      bmReturn: parseFloat((meanBM * 252 * 100).toFixed(2)),
      days: fundReturns.length,
      betaLabel,
      betaColor,
      betaBg,
      alphaLabel,
      alphaColor,
      alphaBg,
      r2Label,
      r2Color,
      r2Bg,
    };
  }, [priceHistory, benchmarkData]);

  if (!metrics) {
    return (
      <Card>
        <CardContent className="p-4 text-center text-neutral-400">
          <BarChart2 className="w-6 h-6 mx-auto mb-1 opacity-30" />
          <div className="text-sm">Beta/Alpha hesaplamak için yeterli veri yok</div>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardContent className="p-4">
        <h3 className="text-sm font-semibold text-neutral-700 mb-4 flex items-center gap-2">
          <BarChart2 className="w-4 h-4" />
          Beta / Alpha — Kategori Karşılaştırması
          <span className="ml-auto text-xs font-normal text-neutral-400">{metrics.days} gün</span>
        </h3>

        <div className="space-y-3">

          {/* Beta */}
          <div className="p-3 rounded-xl border border-neutral-200">
            <div className="flex items-center justify-between mb-1.5">
              <div className="flex items-center gap-1.5">
                <span className="text-sm font-semibold text-neutral-700">Beta</span>
                <span className="text-neutral-300" title="Fonun piyasaya (kategori ortalamasına) duyarlılığı. 1 = piyasa ile aynı hareket eder.">
                  <Info className="w-3.5 h-3.5" />
                </span>
                <span className={`text-xs font-medium px-1.5 py-0.5 rounded-full ${metrics.betaBg} ${metrics.betaColor}`}>
                  {metrics.betaLabel}
                </span>
              </div>
              <span className={`text-2xl font-black font-mono ${metrics.betaColor}`}>
                {metrics.beta.toFixed(2)}
              </span>
            </div>
            <div className="h-1.5 bg-neutral-100 rounded-full overflow-hidden">
              <div
                className={`h-full rounded-full ${metrics.betaColor.replace("text-", "bg-")}`}
                style={{ width: `${Math.min(100, Math.max(0, metrics.beta * 70))}%` }}
              />
            </div>
            <div className="text-xs text-neutral-400 mt-1.5 leading-relaxed">
              {metrics.beta < 1
                ? `Piyasadan ${((1 - metrics.beta) * 100).toFixed(0)}% daha az hareketli — daha stabil.`
                : `Piyasadan ${((metrics.beta - 1) * 100).toFixed(0)}% daha fazla hareketli — daha volatil.`
              }{" "}
              Beta &lt; 0.8 = düşük risk, Beta &gt; 1.2 = yüksek risk.
            </div>
          </div>

          {/* Alpha */}
          <div className="p-3 rounded-xl border border-neutral-200">
            <div className="flex items-center justify-between mb-1.5">
              <div className="flex items-center gap-1.5">
                <span className="text-sm font-semibold text-neutral-700">Alpha</span>
                <span className="text-neutral-300" title="Fonun benchmark (kategori ortalaması) üstünde elde ettiği ek getiri. Pozitif = kategorisindeki fonları geçmiş.">
                  <Info className="w-3.5 h-3.5" />
                </span>
                <span className={`text-xs font-medium px-1.5 py-0.5 rounded-full ${metrics.alphaBg} ${metrics.alphaColor}`}>
                  {metrics.alphaLabel}
                </span>
              </div>
              <span className={`text-2xl font-black font-mono ${metrics.alphaColor}`}>
                {metrics.alpha >= 0 ? "+" : ""}{metrics.alpha.toFixed(1)}%
              </span>
            </div>
            <div className="text-xs text-neutral-400 mt-1 leading-relaxed">
              {metrics.alpha > 0
                ? `Bu fon, kategorisindeki ortalama fondan yıllık %${(metrics.alpha).toFixed(1)} daha fazla kazandırıyor.`
                : `Bu fon, kategorisindeki ortalama fondan yıllık %${Math.abs(metrics.alpha).toFixed(1)} daha az kazandırıyor.`
              }{" "}
              Formül: <span className="font-mono">(Fon Yıllık Getiri − Kategori Yıllık Getiri)</span>
            </div>
            <div className="mt-1.5 flex items-center gap-3 text-xs text-neutral-400">
              <span>Fon getirisi: <span className={`font-mono font-semibold ${metrics.fundReturn >= 0 ? "text-green-600" : "text-red-600"}`}>{metrics.fundReturn >= 0 ? "+" : ""}%{metrics.fundReturn}</span></span>
              <span>Kategori: <span className="font-mono font-semibold text-neutral-500">%{metrics.bmReturn}</span></span>
            </div>
          </div>

          {/* R-Squared */}
          <div className="p-3 rounded-xl border border-neutral-200">
            <div className="flex items-center justify-between mb-1.5">
              <div className="flex items-center gap-1.5">
                <span className="text-sm font-semibold text-neutral-700">R-Kare (R²)</span>
                <span className="text-neutral-300" title="Fon hareketinin yüzde kaçının kategori hareketiyle açıklandığı. 1 = tamamen kategoriye bağlı.">
                  <Info className="w-3.5 h-3.5" />
                </span>
                <span className={`text-xs font-medium px-1.5 py-0.5 rounded-full ${metrics.r2Bg} ${metrics.r2Color}`}>
                  {metrics.r2Label}
                </span>
              </div>
              <span className={`text-2xl font-black font-mono ${metrics.r2Color}`}>
                {metrics.rSquared.toFixed(2)}
              </span>
            </div>
            <div className="h-1.5 bg-neutral-100 rounded-full overflow-hidden">
              <div
                className={`h-full rounded-full ${metrics.r2Color.replace("text-", "bg-")}`}
                style={{ width: `${Math.min(100, metrics.rSquared * 100)}%` }}
              />
            </div>
            <div className="text-xs text-neutral-400 mt-1.5 leading-relaxed">
              R² = {((metrics.rSquared) * 100).toFixed(0)}% — fon hareketinin {((metrics.rSquared) * 100).toFixed(0)}%'i kategori performansıyla açıklanabilir.{" "}
              {metrics.rSquared < 0.5
                ? "Düşük R² = fon kategorisinden bağımsız hareket ediyor (özellik yönetiliyor)."
                : "Yüksek R² = fon kategori ile paralel hareket ediyor (pasif yönetim)."}
            </div>
            <div className="mt-1 text-xs text-neutral-400">
              Korelasyon: <span className="font-mono font-semibold text-neutral-600">{metrics.corr.toFixed(2)}</span>
            </div>
          </div>

          {/* Tracking Error + Info Ratio */}
          <div className="grid grid-cols-2 gap-2 pt-1">
            <div className="p-3 rounded-lg bg-neutral-50">
              <div className="flex items-center gap-1 mb-1">
                <span className="text-xs font-semibold text-neutral-600">Tracking Error</span>
                <span className="text-neutral-300" title="Fonun benchmark'tan ortalama sapması. Düşük = benchmark'a sadık.">
                  <Info className="w-3 h-3 text-neutral-300" />
                </span>
              </div>
              <div className="text-lg font-black font-mono text-neutral-700">%{metrics.trackingError.toFixed(2)}</div>
              <div className="text-xs text-neutral-400 mt-0.5">Yıllık standart sapma</div>
            </div>
            <div className="p-3 rounded-lg bg-neutral-50">
              <div className="flex items-center gap-1 mb-1">
                <span className="text-xs font-semibold text-neutral-600">Info. Oranı</span>
                <span className="text-neutral-300" title="Alfa / Tracking Error. Pozitif = aktif yönetim değeri yaratıyor.">
                  <Info className="w-3 h-3 text-neutral-300" />
                </span>
              </div>
              <div className={`text-lg font-black font-mono ${metrics.infoRatio >= 0 ? "text-green-600" : "text-red-600"}`}>
                {metrics.infoRatio >= 0 ? "+" : ""}{metrics.infoRatio.toFixed(2)}
              </div>
              <div className="text-xs text-neutral-400 mt-0.5">
                {metrics.infoRatio > 0.5 ? "İyi" : metrics.infoRatio > 0 ? "Orta" : "Zayıf"} — {metrics.infoRatio > 0 ? "pozitif" : "negatif"} alfa
              </div>
            </div>
          </div>

          {/* Legend */}
          <div className="pt-2 border-t border-neutral-100">
            <div className="text-xs font-medium text-neutral-500 mb-2">Nasıl okunur?</div>
            <div className="space-y-1.5">
              <div className="flex items-start gap-2">
                <Target className="w-3.5 h-3.5 text-green-500 mt-0.5 shrink-0" />
                <div className="text-xs text-neutral-400 leading-relaxed">
                  <span className="font-semibold text-neutral-600">Beta = 1</span> — fon tam piyasa ile hareket eder
                </div>
              </div>
              <div className="flex items-start gap-2">
                <TrendingUp className="w-3.5 h-3.5 text-green-500 mt-0.5 shrink-0" />
                <div className="text-xs text-neutral-400 leading-relaxed">
                  <span className="font-semibold text-neutral-600">Alpha &gt; 0</span> — fon kategorisini consistently geçiyor
                </div>
              </div>
              <div className="flex items-start gap-2">
                <BarChart2 className="w-3.5 h-3.5 text-blue-500 mt-0.5 shrink-0" />
                <div className="text-xs text-neutral-400 leading-relaxed">
                  <span className="font-semibold text-neutral-600">R² &gt; 0.7</span> — yüksek korelasyon, beta anlamlı
                </div>
              </div>
            </div>
          </div>

        </div>
      </CardContent>
    </Card>
  );
}
