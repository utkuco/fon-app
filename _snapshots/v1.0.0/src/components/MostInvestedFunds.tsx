"use client";

import { Users, ChevronRight } from "lucide-react";
import Link from "next/link";
import { Card, CardContent } from "@/components/ui/card";

interface MostInvested {
  code: string;
  name: string;
  investors: number;
  market_cap: number;
}

function fmtMoney(n: number): string {
  if (n >= 1e9) return `${(n / 1e9).toFixed(1)}B`;
  if (n >= 1e6) return `${(n / 1e6).toFixed(1)}M`;
  return n.toLocaleString("tr-TR");
}

function fmtInvestors(n: number): string {
  if (n >= 1e6) return `${(n / 1e6).toFixed(2)}M`;
  if (n >= 1e3) return `${(n / 1e3).toFixed(0)}K`;
  return n.toLocaleString("tr-TR");
}

interface MostInvestedFundsProps {
  funds: MostInvested[];
}

export default function MostInvestedFunds({ funds }: MostInvestedFundsProps) {
  return (
    <Card>
      <CardContent className="p-0">
        <div className="px-4 py-3 border-b border-neutral-100 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Users className="w-4 h-4 text-blue-600" />
            <h3 className="text-sm font-semibold text-neutral-700">En Çok Yatırımcılı Fonlar</h3>
          </div>
          <span className="text-xs text-neutral-400">toplam yatırımcı sayısı</span>
        </div>
        <div className="divide-y divide-neutral-50">
          {funds.map((f, i) => (
            <Link
              key={f.code}
              href={`/fon/${f.code}`}
              className="flex items-center gap-3 px-4 py-2.5 hover:bg-neutral-50/50 transition"
            >
              <span className="w-5 text-xs text-neutral-400 font-mono">{i + 1}</span>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <span className="font-mono font-bold text-blue-700 text-sm">{f.code}</span>
                  <span className="text-xs text-blue-600 font-medium">
                    {fmtInvestors(f.investors)} yatırımcı
                  </span>
                </div>
                <div className="text-xs text-neutral-500 truncate mt-0.5">{f.name}</div>
              </div>
              <div className="text-right shrink-0">
                <div className="text-xs font-mono text-neutral-700">{fmtMoney(f.market_cap)}</div>
                <div className="text-xs text-neutral-400">₺</div>
              </div>
            </Link>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}
