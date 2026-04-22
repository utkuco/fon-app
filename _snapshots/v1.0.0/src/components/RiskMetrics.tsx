"use client";

import { useMemo } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { TrendingUp, TrendingDown, Shield, Activity, Info } from "lucide-react";

interface PricePoint {
  date: string;
  price: number;
  change?: number;
}

interface RiskMetricsProps {
  priceHistory: PricePoint[];
  currentPrice: number | null;
}

function calcStdDev(changes: number[]): number {
  if (changes.length < 2) return 0;
  const mean = changes.reduce((a, b) => a + b, 0) / changes.length;
  const sqDiffs = changes.map(c => Math.pow(c - mean, 2));
  const variance = sqDiffs.reduce((a, b) => a + b, 0) / sqDiffs.length;
  return Math.sqrt(variance);
}

function annualizeStdDev(dailyStd: number, days: number = 252): number {
  return dailyStd * Math.sqrt(days);
}

function getRiskLevel(annualized: number): { label: string; color: string; bg: string; desc: string } {
  if (annualized <= 3) return { label: "Çok Düşük", color: "text-emerald-600", bg: "bg-emerald-50", desc: "Fiyat hareketleri çok düşük, portföy oldukça stabil" };
  if (annualized <= 7) return { label: "Düşük", color: "text-green-600", bg: "bg-green-50", desc: "Günlük dalgalanmalar sınırlı, uzun vadeli yatırım için uygun" };
  if (annualized <= 15) return { label: "Orta", color: "text-amber-600", bg: "bg-amber-50", desc: "Makul dalgalanma — piyasa koşullarına bağlı değişimler beklenir" };
  if (annualized <= 25) return { label: "Yüksek", color: "text-orange-600", bg: "bg-orange-50", desc: "Yüksek fiyat hareketleri — kısa vadeli volatilite güçlü" };
  return { label: "Çok Yüksek", color: "text-red-600", bg: "bg-red-50", desc: "Aşırı dalgalanma — yüksek getiri potansiyeli ama büyük kayıp riski" };
}

export default function RiskMetrics({ priceHistory }: RiskMetricsProps) {
  const metrics = useMemo(() => {
    if (!priceHistory || priceHistory.length < 10) return null;

    const sorted = [...priceHistory].sort((a, b) => a.date.localeCompare(b.date));
    const changes = sorted.map(p => p.change ?? 0).filter(c => c !== 0);

    if (changes.length < 5) return null;

    const dailyStd = calcStdDev(changes);
    const annualStd = annualizeStdDev(dailyStd);
    const risk = getRiskLevel(annualStd);

    // Max drawdown with dates
    let peak = sorted[0].price;
    let peakDate: string = sorted[0].date;
    let maxDrawdown = 0;
    let maxDrawdownDate: string = sorted[0].date;
    let troughDate: string = sorted[0].date;

    for (const p of sorted) {
      if (p.price > peak) {
        peak = p.price;
        peakDate = p.date;
      }
      const dd = ((peak - p.price) / peak) * 100;
      if (dd > maxDrawdown) {
        maxDrawdown = dd;
        maxDrawdownDate = p.date;
        troughDate = p.date;
      }
    }

    // Downside deviation (only negative returns)
    const negChanges = changes.filter(c => c < 0);
    const downsideStd = negChanges.length > 1 ? calcStdDev(negChanges) : dailyStd;

    // Best/worst day
    const bestDay = Math.max(...changes);
    const worstDay = Math.min(...changes);
    const bestDayIdx = changes.indexOf(bestDay);
    const worstDayIdx = changes.indexOf(worstDay);
    const bestDayDate = sorted[bestDayIdx + 1]?.date || sorted[0].date;
    const worstDayDate = sorted[worstDayIdx + 1]?.date || sorted[0].date;

    // Recent 21-day and 63-day volatility for comparison
    const recent21 = changes.slice(-21);
    const recent63 = changes.slice(-63);
    const std21 = recent21.length > 1 ? annualizeStdDev(calcStdDev(recent21)) : null;
    const std63 = recent63.length > 1 ? annualizeStdDev(calcStdDev(recent63)) : null;

    return {
      dailyStd: dailyStd.toFixed(3),
      annualStd: annualStd.toFixed(2),
      maxDrawdown: maxDrawdown.toFixed(2),
      maxDrawdownDate,
      peakDate,
      downsideStd: downsideStd.toFixed(3),
      bestDay: bestDay.toFixed(2),
      bestDayDate,
      worstDay: worstDay.toFixed(2),
      worstDayDate,
      risk,
      days: sorted.length,
      std21:    std21 !== null ? std21.toFixed(2)   : null,
      std63:    std63 !== null ? std63.toFixed(2)   : null,
    };
  }, [priceHistory]);

  if (!metrics) {
    return (
      <Card>
        <CardContent className="p-4 text-center text-neutral-400">
          <Activity className="w-6 h-6 mx-auto mb-1 opacity-30" />
          <div className="text-sm">Yeterli veri yok</div>
        </CardContent>
      </Card>
    );
  }

  const volPct = parseFloat(metrics.annualStd);

  return (
    <Card>
      <CardContent className="p-4">
        <h3 className="text-sm font-semibold text-neutral-700 mb-4 flex items-center gap-2">
          <Shield className="w-4 h-4" />
          Risk Metrikleri
        </h3>

        {/* ─── 1. Annualized Volatility (Hero) ─── */}
        <div className="p-4 rounded-xl bg-neutral-50 border border-neutral-200 mb-3">
          <div className="flex items-center justify-between mb-2">
            <div className="flex items-center gap-1.5">
              <span className="text-sm font-semibold text-neutral-700">Yıllık Volatilite</span>
              <span className="text-neutral-300" title="Fiyatların yıllık ortalama dalgalanma yüzdesi — ne kadar yüksekse o kadar riskli">
                <Info className="w-3.5 h-3.5" />
              </span>
            </div>
            <span className={`text-xs font-bold px-2 py-0.5 rounded-full ${metrics.risk.bg} ${metrics.risk.color}`}>
              {metrics.risk.label}
            </span>
          </div>

          <div className="text-3xl font-black font-mono text-neutral-900 mb-1">
            %{metrics.annualStd}
          </div>

          {/* Risk bar */}
          <div className="mt-2 bg-neutral-200 rounded-full h-2 overflow-hidden">
            <div
              className={`h-full rounded-full transition-all ${metrics.risk.color.replace("text-", "bg-")}`}
              style={{ width: `${Math.min((volPct / 35) * 100, 100)}%` }}
            />
          </div>

          {/* Explanatory */}
          <div className="mt-2 text-xs text-neutral-500 leading-relaxed">
            <span className="font-medium text-neutral-600">{metrics.risk.desc}</span>
            {" "}Günlük standart sapma: <span className="font-mono">%{metrics.dailyStd}</span> σ
          </div>

          {/* Short-term volatility comparison */}
          {metrics.std21 !== null && metrics.std63 !== null && (
            <div className="mt-2 pt-2 border-t border-neutral-200 flex items-center gap-4 text-xs text-neutral-400">
              <span>21G: <span className={`font-mono font-semibold ${parseFloat(String(metrics.std21)) > volPct ? "text-orange-500" : "text-green-500"}`}>%{String(metrics.std21)}</span></span>
              <span>63G: <span className={`font-mono font-semibold ${parseFloat(String(metrics.std63)) > volPct ? "text-orange-500" : "text-green-500"}`}>%{String(metrics.std63)}</span></span>
              <span className="text-neutral-300">|</span>
              <span className="text-neutral-400">252G: <span className="font-mono font-semibold text-neutral-600">%{String(metrics.annualStd)}</span></span>
            </div>
          )}
        </div>

        {/* ─── 2. Max Drawdown ─── */}
        <div className="p-3 rounded-lg bg-neutral-50 mb-2">
          <div className="flex items-start justify-between">
            <div>
              <div className="flex items-center gap-1 mb-1">
                <span className="text-xs font-semibold text-neutral-600">Max Drawdown</span>
                <span className="text-neutral-300" title="En yüksek tepeden en düşük seviyeye yaşanan en büyük kayıp">
                  <Info className="w-3.5 h-3.5" />
                </span>
              </div>
              <div className="text-2xl font-black font-mono text-red-500">
                -{metrics.maxDrawdown}%
              </div>
              <div className="text-xs text-neutral-400 mt-0.5 leading-relaxed">
                En düşük: <span className="font-mono">{metrics.maxDrawdownDate?.split("T")[0]}</span>
                {" "}(zirve: <span className="font-mono">{metrics.peakDate?.split("T")[0]}</span>)
              </div>
              <div className="text-xs text-neutral-400 mt-1">
                En yüksek tepeden sonra yaşanan en büyük kayıp. Bu süre zarfında fon %{metrics.maxDrawdown} değer kaybetmiş.
              </div>
            </div>
          </div>
        </div>

        {/* ─── 3. Downside Deviation ─── */}
        <div className="p-3 rounded-lg bg-neutral-50 mb-2">
          <div className="flex items-start justify-between">
            <div>
              <div className="flex items-center gap-1 mb-1">
                <span className="text-xs font-semibold text-neutral-600">Downside Sapma</span>
                <span className="text-neutral-300" title="Sadece negatif getirilerin standart sapması — düşüş riskini daha hassas ölçer">
                  <Info className="w-3.5 h-3.5" />
                </span>
              </div>
              <div className="text-2xl font-black font-mono text-orange-500">
                %{metrics.downsideStd}
              </div>
              <div className="text-xs text-neutral-400 mt-1 leading-relaxed">
                Sadece <span className="font-medium text-orange-600">kayıp günlerin</span> standart sapması. Negatif getirilerin ne kadar dalgalı olduğunu gösterir — yüksek = düşüşler öngörülemez.
              </div>
            </div>
          </div>
        </div>

        {/* ─── 4. Best / Worst Day ─── */}
        <div className="grid grid-cols-2 gap-2 mb-2">
          <div className="p-3 rounded-lg bg-neutral-50">
            <div className="flex items-center gap-1 mb-1">
              <TrendingUp className="w-3 h-3 text-green-500" />
              <span className="text-xs font-semibold text-neutral-600">En İyi Gün</span>
            </div>
            <div className="text-xl font-black font-mono text-green-600">
              +{metrics.bestDay}%
            </div>
            <div className="text-xs text-neutral-400 mt-0.5">
              {metrics.bestDayDate?.split("T")[0]}
            </div>
          </div>
          <div className="p-3 rounded-lg bg-neutral-50">
            <div className="flex items-center gap-1 mb-1">
              <TrendingDown className="w-3 h-3 text-red-500" />
              <span className="text-xs font-semibold text-neutral-600">En Kötü Gün</span>
            </div>
            <div className="text-xl font-black font-mono text-red-500">
              {metrics.worstDay}%
            </div>
            <div className="text-xs text-neutral-400 mt-0.5">
              {metrics.worstDayDate?.split("T")[0]}
            </div>
          </div>
        </div>

        {/* ─── Legend ─── */}
        <div className="pt-2 border-t border-neutral-100 text-xs text-neutral-400 leading-relaxed">
          <div className="font-medium text-neutral-500 mb-1">Nasıl okunur?</div>
          <div className="space-y-0.5">
            <div>• <span className="font-mono">Volatilite</span> — günlük fiyat dalgalanmasının yıllık tahmini. %15+ yüksek risk.</div>
            <div>• <span className="font-mono">Max Drawdown</span> — zirveden dibe en büyük kayıp. Ne zaman olduğu önemli.</div>
            <div>• <span className="font-mono">Downside Sapma</span> — sadece kayıp günlerin hassasiyeti. Yüksek = düşüşler beklenmedik.</div>
            <div>• <span className="font-mono">21G / 63G</span> — son 21 ve 63 günlük volatilite. Kısa vadeli riski gösterir.</div>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
