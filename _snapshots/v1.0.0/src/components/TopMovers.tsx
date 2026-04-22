"use client";

import { TrendingUp, TrendingDown, ChevronRight } from "lucide-react";
import Link from "next/link";
import { Card, CardContent } from "@/components/ui/card";

interface Mover {
  code: string;
  name: string;
  change: number;
  market_cap: number | null;
}

function fmtMoney(n: number): string {
  if (n >= 1e9) return `${(n / 1e9).toFixed(1)}B`;
  if (n >= 1e6) return `${(n / 1e6).toFixed(1)}M`;
  return n.toLocaleString("tr-TR");
}

interface TopMoversProps {
  gainers: Mover[];
  losers: Mover[];
}

export default function TopMovers({ gainers, losers }: TopMoversProps) {
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
      {/* En Çok Yükselen */}
      <Card className="overflow-hidden">
        <CardContent className="p-0">
          <div className="bg-gradient-to-r from-green-50 to-emerald-50 px-4 py-3 border-b border-green-100 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <TrendingUp className="w-4 h-4 text-green-600" />
              <h3 className="text-sm font-semibold text-green-800">En Çok Yükselen Fonlar</h3>
            </div>
            <Link href="/ movers" className="text-xs text-green-600 hover:text-green-800 flex items-center gap-0.5 transition">
              Tümünü gör <ChevronRight className="w-3 h-3" />
            </Link>
          </div>
          <div className="divide-y divide-green-50">
            {gainers.map((g) => (
              <Link
                key={g.code}
                href={`/fon/${g.code}`}
                className="flex items-center gap-3 px-4 py-2.5 hover:bg-green-50/50 transition"
              >
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="font-mono font-bold text-green-700 text-sm">{g.code}</span>
                    <span className="text-xs text-green-600 font-mono">
                      {g.change >= 0 ? "+" : ""}{g.change.toFixed(2)}%
                    </span>
                  </div>
                  <div className="text-xs text-neutral-500 truncate mt-0.5">{g.name}</div>
                </div>
                {g.market_cap && (
                  <div className="text-xs text-neutral-400 shrink-0">
                    {fmtMoney(g.market_cap)}
                  </div>
                )}
              </Link>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* En Çok Düşen */}
      <Card className="overflow-hidden">
        <CardContent className="p-0">
          <div className="bg-gradient-to-r from-red-50 to-orange-50 px-4 py-3 border-b border-red-100 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <TrendingDown className="w-4 h-4 text-red-600" />
              <h3 className="text-sm font-semibold text-red-800">En Çok Düşen Fonlar</h3>
            </div>
            <Link href="/losers" className="text-xs text-red-600 hover:text-red-800 flex items-center gap-0.5 transition">
              Tümünü gör <ChevronRight className="w-3 h-3" />
            </Link>
          </div>
          <div className="divide-y divide-red-50">
            {losers.map((l) => (
              <Link
                key={l.code}
                href={`/fon/${l.code}`}
                className="flex items-center gap-3 px-4 py-2.5 hover:bg-red-50/50 transition"
              >
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="font-mono font-bold text-red-700 text-sm">{l.code}</span>
                    <span className="text-xs text-red-600 font-mono">
                      {l.change.toFixed(2)}%
                    </span>
                  </div>
                  <div className="text-xs text-neutral-500 truncate mt-0.5">{l.name}</div>
                </div>
                {l.market_cap && (
                  <div className="text-xs text-neutral-400 shrink-0">
                    {fmtMoney(l.market_cap)}
                  </div>
                )}
              </Link>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
