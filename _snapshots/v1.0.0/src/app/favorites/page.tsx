"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { Heart, ArrowLeft, X, BarChart2, Search } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { ChangeBadge } from "@/components/ChangeBadge";
import { CompanyLogo } from "@/components/CompanyLogo";
import { useFavorites } from "@/hooks/useFavorites";
import { TYPE_LABELS, TYPE_COLORS } from "@/lib/shared-config";

interface Fund {
  code: string;
  name: string;
  company: string | null;
  company_logo?: string;
  fund_type: string | null;
  price: number | null;
  daily_change: number | null;
  market_cap: number | null;
}

function fmtMoney(n: number | null | undefined): string {
  if (n == null) return "—";
  if (n >= 1e12) return `${(n / 1e12).toFixed(2)}T`;
  if (n >= 1e9) return `${(n / 1e9).toFixed(1)}B`;
  if (n >= 1e6) return `${(n / 1e6).toFixed(1)}M`;
  return n.toLocaleString("tr-TR");
}

export default function FavoritesPage() {
  const { favorites, removeFavorite, loaded } = useFavorites();
  const [funds, setFunds] = useState<Fund[]>([]);
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);

  // Fetch favorite funds from Supabase by code
  useEffect(() => {
    if (!loaded || favorites.length === 0) {
      setLoading(false);
      return;
    }

    const codes = favorites.map((f) => f.code);
    fetch(`/api/funds?codes=${codes.join(",")}`)
      .then((r) => r.json())
      .then((d) => {
        setFunds(d.funds || []);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, [loaded, favorites]);

  const enriched = favorites.map((fav) => {
    const full = funds.find((f) => f.code === fav.code);
    return { ...fav, ...full };
  });

  const filtered = search
    ? enriched.filter(
        (f) =>
          f.code.toLowerCase().includes(search.toLowerCase()) ||
          f.name?.toLowerCase().includes(search.toLowerCase())
      )
    : enriched;

  useEffect(() => {
    document.title =
      favorites.length > 0
        ? `Favorilerim (${favorites.length}) | FonRapor`
        : "Favorilerim | FonRapor";
  }, [favorites]);

  if (!loaded || loading) {
    return (
      <div className="min-h-screen bg-neutral-50 flex items-center justify-center">
        <div className="text-neutral-400">Yükleniyor...</div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-neutral-50">
      {/* Header */}
      <div className="bg-white border-b border-neutral-200 sticky top-0 z-10">
        <div className="max-w-7xl mx-auto px-4 h-14 flex items-center gap-4">
          <Link
            href="/"
            className="flex items-center gap-1.5 text-sm text-neutral-500 hover:text-neutral-900 transition shrink-0"
          >
            <ArrowLeft className="w-4 h-4" />
            <span className="hidden sm:inline">Fonlar</span>
          </Link>
          <div className="flex items-center gap-2 shrink-0">
            <Heart className="w-5 h-5 text-red-500 fill-red-500" />
            <h1 className="text-base font-bold text-neutral-900">Favorilerim</h1>
            {favorites.length > 0 && (
              <span className="text-xs bg-red-100 text-red-700 px-2 py-0.5 rounded-full">
                {favorites.length}
              </span>
            )}
          </div>
          {favorites.length > 1 && (
            <Link
              href={`/compare?codes=${enriched.map((f) => f.code).join(",")}`}
              className="ml-auto flex items-center gap-1.5 text-xs font-medium text-blue-600 hover:text-blue-800 transition shrink-0"
            >
              <BarChart2 className="w-3.5 h-3.5" />
              <span className="hidden sm:inline">Tümünü Karşılaştır</span>
            </Link>
          )}
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-4 py-6 space-y-4">
        {favorites.length > 3 && (
          <div className="relative max-w-xs">
            <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-neutral-400 pointer-events-none" />
            <Input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Favorilerde ara..."
              className="pl-8 h-8 text-sm bg-white"
            />
          </div>
        )}

        {favorites.length === 0 ? (
          <Card>
            <CardContent className="p-16 text-center">
              <Heart className="w-12 h-12 mx-auto mb-3 text-neutral-300" />
              <div className="text-neutral-500 font-medium">Henüz favori fon eklemediniz</div>
              <div className="text-sm text-neutral-400 mt-1">Fon detay sayfasındaki kalp simgesine tıklayarak ekleyin</div>
              <Link
                href="/"
                className="inline-block mt-4 px-4 py-2 text-sm font-medium bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition"
              >
                Fonlara Göz At
              </Link>
            </CardContent>
          </Card>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-3">
            {filtered.map((f, i) => (
              <div key={f.code} className={`card-animate card-delay-${Math.min(i + 1, 8)}`}>
                <Card className="h-full transition-all duration-200 hover:shadow-lg hover:shadow-blue-500/5 hover:-translate-y-0.5 cursor-pointer border-neutral-200">
                  <CardContent className="p-4 flex flex-col h-full">
                    <div className="flex items-start gap-3 mb-2">
                      <CompanyLogo
                        logoFile={f.company_logo}
                        company={f.company || undefined}
                        code={f.code}
                        size={44}
                        className="mt-0.5 shrink-0"
                      />
                      <div className="min-w-0 flex-1">
                        <div className="flex items-center gap-1.5 flex-wrap">
                          <Link href={`/fon/${f.code}`} className="font-mono font-bold text-blue-600 text-sm hover:underline">
                            {f.code}
                          </Link>
                          {f.fund_type && (
                            <span className={`text-xs px-1.5 py-0.5 rounded-full font-medium ${TYPE_COLORS[f.fund_type] || "bg-neutral-100 text-neutral-600"}`}>
                              {TYPE_LABELS[f.fund_type] || f.fund_type}
                            </span>
                          )}
                          {f.daily_change != null && <ChangeBadge value={f.daily_change} />}
                        </div>
                        <div className="text-sm text-neutral-700 font-medium line-clamp-2 mt-1 leading-snug">
                          {f.name || "—"}
                        </div>
                      </div>
                    </div>

                    <div className="flex items-end justify-between pt-3 border-t border-neutral-100 mt-auto">
                      <div>
                        <div className="text-lg font-black text-neutral-900 font-mono tracking-tight">
                          {f.price != null ? f.price.toFixed(4) : "—"}
                        </div>
                        <div className="text-xs text-neutral-400">₺</div>
                      </div>
                      <div className="text-right">
                        <div className="text-sm font-semibold text-neutral-700">
                          {f.market_cap ? fmtMoney(f.market_cap) : "—"}
                        </div>
                        <div className="text-xs text-neutral-400">AUM</div>
                      </div>
                    </div>

                    <div className="flex items-center gap-1 mt-3 pt-2 border-t border-neutral-100">
                      <Link
                        href={`/compare?codes=${f.code}`}
                        className="flex-1 flex items-center justify-center gap-1 py-1 text-xs text-blue-600 hover:bg-blue-50 rounded transition"
                      >
                        <BarChart2 className="w-3 h-3" />
                        Karşılaştır
                      </Link>
                      <button
                        onClick={() => removeFavorite(f.code)}
                        className="flex-1 flex items-center justify-center gap-1 py-1 text-xs text-red-500 hover:bg-red-50 rounded transition"
                      >
                        <X className="w-3 h-3" />
                        Kaldır
                      </button>
                    </div>
                  </CardContent>
                </Card>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
