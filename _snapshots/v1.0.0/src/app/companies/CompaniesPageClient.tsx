"use client";

import { useState, useMemo } from "react";
import Link from "next/link";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Building2, TrendingUp, Search, ArrowUpDown } from "lucide-react";
import { Logo } from "@/components/Logo";

type Company = {
  id: string;
  name: string;
  slug: string;
  display_name: string | null;
  logo: string | null;
  fund_count: number;
  total_aum: number;
};

function fmtMoney(n: number | undefined | null): string {
  if (n == null) return "—";
  if (n >= 1e12) return `${(n / 1e12).toFixed(1)}T`;
  if (n >= 1e9) return `${(n / 1e9).toFixed(1)}B`;
  if (n >= 1e6) return `${(n / 1e6).toFixed(0)}M`;
  return n.toLocaleString("tr-TR");
}

function CompanyAvatar({ companyName, size = 40 }: { companyName: string; size?: number }) {
  // Use a colored badge with initials as logo
  const colors = [
    "bg-blue-100 text-blue-700",
    "bg-green-100 text-green-700",
    "bg-purple-100 text-purple-700",
    "bg-orange-100 text-orange-700",
    "bg-pink-100 text-pink-700",
    "bg-cyan-100 text-cyan-700",
    "bg-amber-100 text-amber-700",
    "bg-indigo-100 text-indigo-700",
  ];
  const idx = companyName.charCodeAt(0) % colors.length;
  const initials = companyName.substring(0, 2).toUpperCase();
  return (
    <div
      className={`${colors[idx]} rounded-lg flex items-center justify-center font-bold text-sm shrink-0`}
      style={{ width: size, height: size }}
    >
      {initials}
    </div>
  );
}

export default function CompaniesPageClient({ companies }: { companies: Company[] }) {
  const [search, setSearch] = useState("");
  const [sortBy, setSortBy] = useState<"funds" | "aum">("funds");

  const filtered = useMemo(() => {
    const q = search.toLowerCase().trim();
    let list = companies.filter(
      (c) =>
        !q ||
        c.name.toLowerCase().includes(q) ||
        (c.display_name || "").toLowerCase().includes(q)
    );
    if (sortBy === "aum") {
      list = [...list].sort((a, b) => (b.total_aum || 0) - (a.total_aum || 0));
    } else {
      list = [...list].sort((a, b) => (b.fund_count || 0) - (a.fund_count || 0));
    }
    return list;
  }, [companies, search, sortBy]);

  const totalFunds = companies.reduce((s, c) => s + (c.fund_count || 0), 0);
  const totalAUM = companies.reduce((s, c) => s + (c.total_aum || 0), 0);

  return (
    <div className="min-h-screen bg-neutral-50">
      {/* Header */}
      <header className="bg-white border-b border-neutral-200 sticky top-0 z-50">
        <div className="max-w-6xl mx-auto px-4 h-16 flex items-center gap-3">
          <Link href="/" className="shrink-0">
            <Logo variant="full" className="h-8 w-auto" />
          </Link>
          <div className="h-6 w-px bg-neutral-200 hidden sm:block" />
          <nav className="hidden md:flex items-center gap-1">
            <Link href="/companies" className="px-3 py-1.5 text-sm font-medium text-neutral-600 hover:text-blue-600 hover:bg-blue-50 rounded-lg transition">Şirketler</Link>
            <Link href="/holdings" className="px-3 py-1.5 text-sm font-medium text-neutral-600 hover:text-blue-600 hover:bg-blue-50 rounded-lg transition">Hisse Tercihleri</Link>
            <Link href="/performers" className="px-3 py-1.5 text-sm font-medium text-neutral-600 hover:text-blue-600 hover:bg-blue-50 rounded-lg transition">En Çok Kazandıranlar</Link>
            <Link href="/etf" className="px-3 py-1.5 text-sm font-medium text-neutral-600 hover:text-blue-600 hover:bg-blue-50 rounded-lg transition">Yabancı ETF</Link>
          </nav>
        </div>
      </header>

      <main className="max-w-6xl mx-auto px-4 py-8 space-y-6">
        {/* Header */}
        <div>
          <h1 className="text-2xl font-bold text-neutral-900 flex items-center gap-2">
            <Building2 className="w-6 h-6 text-blue-600" />
            Yatırım Şirketleri
          </h1>
          <p className="text-neutral-500 mt-1">
            {companies.length} şirket · {totalFunds.toLocaleString("tr-TR")} fon ·{" "}
            {fmtMoney(totalAUM)} TL toplam AUM
          </p>
        </div>

        {/* Search + Sort */}
        <div className="flex items-center gap-3">
          <div className="relative flex-1 max-w-sm">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-neutral-400" />
            <Input
              placeholder="Şirket ara..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="pl-9"
            />
          </div>
          <div className="flex gap-1 bg-neutral-100 rounded-lg p-1">
            <button
              onClick={() => setSortBy("funds")}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm font-medium transition ${
                sortBy === "funds"
                  ? "bg-white shadow text-blue-600"
                  : "text-neutral-500 hover:text-neutral-700"
              }`}
            >
              <ArrowUpDown className="w-3.5 h-3.5" />
              Fon Sayısı
            </button>
            <button
              onClick={() => setSortBy("aum")}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm font-medium transition ${
                sortBy === "aum"
                  ? "bg-white shadow text-blue-600"
                  : "text-neutral-500 hover:text-neutral-700"
              }`}
            >
              <TrendingUp className="w-3.5 h-3.5" />
              AUM
            </button>
          </div>
        </div>

        {/* Company Grid */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {filtered.map((company) => (
            <Link key={company.id} href={`/company/${company.slug}`}>
              <Card className="hover:shadow-md hover:border-blue-200 transition cursor-pointer h-full">
                <CardContent className="p-4 flex flex-col gap-3">
                  <div className="flex items-start gap-3">
                    <CompanyAvatar companyName={company.name} size={44} />
                    <div className="min-w-0 flex-1">
                      <h3 className="font-semibold text-neutral-900 truncate">
                        {company.display_name || company.name}
                      </h3>
                      <p className="text-xs text-neutral-400 font-mono mt-0.5">
                        {company.name}
                      </p>
                    </div>
                  </div>

                  <div className="flex items-center justify-between">
                    <Badge variant="secondary" className="text-xs">
                      {company.fund_count ?? 0} fon
                    </Badge>
                    <span className="text-sm font-medium text-neutral-700">
                      {fmtMoney(company.total_aum)} TL
                    </span>
                  </div>
                </CardContent>
              </Card>
            </Link>
          ))}
        </div>

        {filtered.length === 0 && (
          <div className="text-center py-12 text-neutral-400">
            <Building2 className="w-12 h-12 mx-auto mb-3 opacity-30" />
            <p>Sonuç bulunamadı</p>
          </div>
        )}
      </main>
    </div>
  );
}
