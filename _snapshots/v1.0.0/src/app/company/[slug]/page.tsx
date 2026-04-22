import { Metadata } from "next";
import { notFound } from "next/navigation";
import CompanyPageClient from "./CompanyPageClient";

const SB_URL = "https://oqkobptbvcazifpvjwfz.supabase.co";
const SB_KEY = "sb_publishable__GPrsdfKRZCMZE8to916iQ_Izv9naG-";
const BASE_URL = "https://fonrapor.com";
const PAGE_SIZE = 50;

export const revalidate = 3600;

// generateStaticParams intentionally omitted — all company pages are server-rendered dynamically

type SortKey = "market_cap" | "daily_change" | "weekly" | "monthly" | "quarterly";

async function getCompanyBySlug(slug: string) {
  try {
    const url = `${SB_URL}/rest/v1/companies?select=id,name,display_name,slug,logo,fund_count,total_aum&slug=eq.${encodeURIComponent(slug)}&limit=1`;
    const res = await fetch(url, {
      headers: {
        "apikey": SB_KEY,
        "Authorization": `Bearer ${SB_KEY}`,
        "Content-Type": "application/json",
      },
      next: { revalidate: 3600 },
    });
    if (!res.ok) return null;
    const data = await res.json();
    return data?.[0] || null;
  } catch {
    return null;
  }
}

async function getCompanyFunds(companyId: string, sortKey: SortKey, sortDir: "asc" | "desc", page: number) {
  const orderCol = sortKey === "daily_change" ? "daily_change"
    : sortKey === "weekly" ? "weekly"
    : sortKey === "monthly" ? "monthly"
    : sortKey === "quarterly" ? "quarterly"
    : "market_cap";

  const offset = (page - 1) * PAGE_SIZE;
  const dir = sortDir === "asc" ? "asc" : "desc";

  const selectCols = [
    "code", "name", "fund_type", "market_cap", "daily_change", "price",
    "weekly", "monthly", "quarterly", "returns", "breakdown", "price_history",
    "company_id",
  ].join(",");

  try {
    const fundsUrl = `${SB_URL}/rest/v1/funds?select=${selectCols},companies:company_id(name,logo,display_name)&company_id=eq.${companyId}&order=${orderCol}.${dir}&offset=${offset}&limit=${PAGE_SIZE}`;
    const fundsRes = await fetch(fundsUrl, {
      headers: { "apikey": SB_KEY, "Authorization": `Bearer ${SB_KEY}`, "Content-Type": "application/json" },
      next: { revalidate: 3600 },
    });
    const funds = fundsRes.ok ? await fundsRes.json() : [];

    const countUrl = `${SB_URL}/rest/v1/funds?company_id=eq.${companyId}&select=code&limit=1000`;
    const countRes = await fetch(countUrl, {
      headers: { "apikey": SB_KEY, "Authorization": `Bearer ${SB_KEY}`, "Content-Type": "application/json" },
      next: { revalidate: 3600 },
    });
    const countData = countRes.ok ? await countRes.json() : [];
    const total = Array.isArray(countData) ? countData.length : 0;

    return {
      funds: (Array.isArray(funds) ? funds : []).map((f: any) => ({
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
  } catch {
    return { funds: [], total: 0, totalPages: 0 };
  }
}

async function getCompanyStats(companyId: string) {
  try {
    const url = `${SB_URL}/rest/v1/funds?company_id=eq.${companyId}&select=market_cap,daily_change&limit=1000`;
    const res = await fetch(url, {
      headers: { "apikey": SB_KEY, "Authorization": `Bearer ${SB_KEY}`, "Content-Type": "application/json" },
      next: { revalidate: 3600 },
    });
    const data = res.ok ? await res.json() : [];
    const arr = Array.isArray(data) ? data : [];
    const total = arr.length;
    const totalAUM = arr.reduce((s: number, f: any) => s + (f.market_cap || 0), 0);
    const avgChange = total > 0
      ? arr.reduce((s: number, f: any) => s + (f.daily_change || 0), 0) / total
      : 0;
    return { total, totalAUM, avgChange };
  } catch {
    return { total: 0, totalAUM: 0, avgChange: 0 };
  }
}

export async function generateMetadata({
  params,
  searchParams,
}: {
  params: Promise<{ slug: string }>;
  searchParams: Promise<{ page?: string; sort?: string }>;
}): Promise<Metadata> {
  const { slug } = await params;
  const sp = await searchParams;
  const page = Math.max(1, parseInt(sp.page || "1"));

  // Wrap everything in try/catch to prevent 500 from metadata
  let title = "Şirket | FonRapor";
  let description = "Yatırım fonu yönetim şirketi";

  try {
    const company = await getCompanyBySlug(slug);
    if (company) {
      const stats = await getCompanyStats(company.id);
      const aumStr = stats.totalAUM >= 1e9
        ? `${(stats.totalAUM / 1e9).toFixed(1)} Milyar TL`
        : stats.totalAUM >= 1e6
        ? `${(stats.totalAUM / 1e6).toFixed(0)} Milyon TL`
        : "—";

      title = page > 1
        ? `${company.display_name || company.name} Fonları — Sayfa ${page} (${stats.total} fon) | FonRapor`
        : `${company.display_name || company.name} (${stats.total} fon) | FonRapor`;
      description = `${company.display_name || company.name} yönetim şirketine ait ${stats.total} yatırım fonu. Toplam AUM: ${aumStr}.`;
    }
  } catch {
    // Keep defaults
  }

  const canonicalUrl = `${BASE_URL}/company/${slug}`;
  return {
    title,
    description,
    openGraph: { type: "website", locale: "tr_TR", url: canonicalUrl, siteName: "FonRapor", title, description },
    twitter: { card: "summary_large_image", title, description },
    alternates: { canonical: canonicalUrl },
  };
}

export default async function CompanyPage({
  params,
  searchParams,
}: {
  params: Promise<{ slug: string }>;
  searchParams: Promise<{ page?: string; sort?: string }>;
}) {
  const { slug } = await params;
  const sp = await searchParams;

  let company: Awaited<ReturnType<typeof getCompanyBySlug>> = null;
  try {
    company = await getCompanyBySlug(slug);
  } catch {
    company = null;
  }

  if (!company) notFound();

  const page = Math.max(1, parseInt(sp.page || "1"));
  const sortKey = (sp.sort as SortKey) || "market_cap";
  const sortDir: "asc" | "desc" = "desc";

  const { funds, total, totalPages } = await getCompanyFunds(company.id, sortKey, sortDir, page);
  const stats = await getCompanyStats(company.id);

  if (total === 0) notFound();

  return (
    <CompanyPageClient
      initialData={{ funds }}
      companyName={company.display_name || company.name}
      slug={slug}
      sortKey={sortKey}
      sortDir={sortDir}
      page={page}
      totalPages={totalPages}
      total={total}
      stats={stats}
    />
  );
}
