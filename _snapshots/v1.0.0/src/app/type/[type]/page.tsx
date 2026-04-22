import { Metadata } from "next";
import { notFound } from "next/navigation";
import { TYPE_LABELS } from "@/lib/shared-config";
import { supabaseAdmin } from "@/lib/supabase-admin";
import TypePageClient from "./TypePageClient";

const BASE_URL = "https://fonrapor.com";
const FUND_TYPES = ["SRF", "VFF", "BYF", "DÖVİZ", "ALTIN", "KFF", "OKS"] as const;
const PAGE_SIZE = 50;

export const revalidate = 3600;

export async function generateStaticParams() {
  return FUND_TYPES.map((type) => ({ type }));
}

type SortKey = "market_cap" | "daily_change" | "weekly" | "monthly" | "quarterly";

async function getTypeFunds(fundType: string, sortKey: SortKey, sortDir: "asc" | "desc", page: number) {
  const orderCol = sortKey === "daily_change" ? "daily_change"
    : sortKey === "weekly" ? "weekly"
    : sortKey === "monthly" ? "monthly"
    : sortKey === "quarterly" ? "quarterly"
    : "market_cap";

  const { data, error, count } = await supabaseAdmin
    .from("funds")
    .select(`
      code, name, fund_type, market_cap, daily_change, price,
      weekly, monthly, quarterly, returns, breakdown, price_history,
      company_id, companies:company_id ( name, logo, display_name )
    `, { count: "exact" })
    .eq("fund_type", fundType)
    .order(orderCol, { ascending: sortDir === "asc" })
    .range((page - 1) * PAGE_SIZE, page * PAGE_SIZE - 1);

  if (error) throw error;

  const total = count ?? 0;

  return {
    funds: data.map((f: any) => ({
      code: f.code, name: f.name, fund_type: f.fund_type,
      company: f.companies?.display_name || f.companies?.name || null,
      company_logo: f.companies?.logo || null,
      daily_change: f.daily_change, market_cap: f.market_cap,
      price: f.price, weekly: f.weekly, monthly: f.monthly, quarterly: f.quarterly,
      returns: f.returns, breakdown: f.breakdown, price_history: f.price_history,
    })),
    total,
    totalPages: Math.ceil(total / PAGE_SIZE),
  };
}

async function getTypeStats(fundType: string) {
  const { data, error } = await supabaseAdmin
    .from("funds")
    .select("market_cap, daily_change")
    .eq("fund_type", fundType);

  if (error) throw error;

  const total = data.length;
  const totalAUM = data.reduce((s: number, f: any) => s + (f.market_cap || 0), 0);
  const avgChange = total > 0
    ? data.reduce((s: number, f: any) => s + (f.daily_change || 0), 0) / total
    : 0;

  return { total, totalAUM, avgChange };
}

async function getCategoryHistory(fundType: string) {
  const { data } = await supabaseAdmin
    .from("category_history")
    .select("fund_type, date, avg_price_index, avg_return, fund_count")
    .eq("fund_type", fundType)
    .order("date", { ascending: true });
  return data || [];
}

async function getBenchmarks() {
  const { data } = await supabaseAdmin
    .from("benchmarks")
    .select("symbol, date, price")
    .eq("symbol", "BIST100")
    .order("date", { ascending: true });
  return data || [];
}

export async function generateMetadata ({
  params,
  searchParams,
}: {
  params: Promise<{ type: string }>;
  searchParams: Promise<{ page?: string; sort?: string }>;
}): Promise<Metadata> {
  const { type } = await params;
  const sp = await searchParams;
  const upperType = decodeURIComponent(type).toUpperCase();
  const page = Math.max(1, parseInt(sp.page || "1"));

  if (!FUND_TYPES.includes(upperType as typeof FUND_TYPES[number])) return {};

  const stats = await getTypeStats(upperType);
  const label = TYPE_LABELS[upperType] || upperType;

  const aumStr = stats.totalAUM >= 1e9
    ? `${(stats.totalAUM / 1e9).toFixed(1)} Milyar TL`
    : stats.totalAUM >= 1e6
    ? `${(stats.totalAUM / 1e6).toFixed(0)} Milyon TL`
    : "—";

  const title = page > 1
    ? `${label} Fonları — Sayfa ${page} (${stats.total} fon)`
    : `${label} Fonları (${stats.total} fon)`;
  const description = `${label} türündeki ${stats.total} yatırım fonu. Toplam AUM: ${aumStr}. Ortalama günlük değişim: ${stats.avgChange >= 0 ? "+" : ""}${stats.avgChange.toFixed(2)}%.`;
  const canonicalUrl = `${BASE_URL}/type/${upperType}`;

  return {
    title,
    description,
    openGraph: { type: "website", locale: "tr_TR", url: canonicalUrl, siteName: "FonRapor", title, description },
    twitter: { card: "summary_large_image", title, description },
    alternates: { canonical: canonicalUrl },
  };
}

export default async function TypePage({
  params,
  searchParams,
}: {
  params: Promise<{ type: string }>;
  searchParams: Promise<{ page?: string; sort?: string }>;
}) {
  const { type } = await params;
  const sp = await searchParams;
  const upperType = decodeURIComponent(type).toUpperCase();

  if (!FUND_TYPES.includes(upperType as typeof FUND_TYPES[number])) notFound();

  const page = Math.max(1, parseInt(sp.page || "1"));
  const sortKey = (sp.sort as SortKey) || "market_cap";
  const sortDir: "asc" | "desc" = "desc";

  const [{ funds, total, totalPages }, stats, categoryHistory, benchmarks] = await Promise.all([
    getTypeFunds(upperType, sortKey, sortDir, page),
    getTypeStats(upperType),
    getCategoryHistory(upperType),
    getBenchmarks(),
  ]);

  return (
    <TypePageClient
      initialData={{ funds }}
      type={upperType}
      sortKey={sortKey}
      sortDir={sortDir}
      page={page}
      totalPages={totalPages}
      total={total}
      stats={stats}
      categoryHistory={categoryHistory}
      benchmarks={benchmarks}
    />
  );
}
