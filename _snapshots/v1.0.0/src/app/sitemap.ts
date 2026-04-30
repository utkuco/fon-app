import { MetadataRoute } from "next";
import { supabaseAdmin } from "@/lib/supabase-admin";

const BASE_URL = "https://fonrapor.com";
const FUND_TYPES = ["SRF", "VFF", "BYF", "DÖVİZ", "ALTIN", "KFF", "OKS"] as const;

async function getTopFunds(limit = 500) {
  const { data, error } = await supabaseAdmin
    .from("funds")
    .select("code, market_cap")
    .order("market_cap", { ascending: false })
    .limit(limit);

  if (error) return [];
  return data as unknown as Array<{ code: string; market_cap: number | null }>;
}

async function getAllCompanySlugs() {
  const { data, error } = await supabaseAdmin
    .from("companies")
    .select("slug, fund_count")
    .order("fund_count", { ascending: false });

  if (error) return [];
  return data as unknown as Array<{ slug: string; fund_count: number | null }>;
}

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const [topFunds, companies] = await Promise.all([
    getTopFunds(500),
    getAllCompanySlugs(),
  ]);
  const now = new Date();

  const staticPages: MetadataRoute.Sitemap = [
    { url: BASE_URL, lastModified: now, changeFrequency: "daily", priority: 1 },
    { url: `${BASE_URL}/favorites`, lastModified: now, changeFrequency: "weekly", priority: 0.5 },
    { url: `${BASE_URL}/compare`, lastModified: now, changeFrequency: "weekly", priority: 0.5 },
  ];

  const typePages: MetadataRoute.Sitemap = FUND_TYPES.map((type) => ({
    url: `${BASE_URL}/type/${type}`,
    lastModified: now,
    changeFrequency: "daily" as const,
    priority: 0.8,
  }));

  const companyPages: MetadataRoute.Sitemap = companies
    .filter((c) => (c.fund_count ?? 0) > 0)
    .map((company) => ({
      url: `${BASE_URL}/company/${company.slug}`,
      lastModified: now,
      changeFrequency: "daily" as const,
      priority: company.fund_count && company.fund_count > 80 ? 0.9 : 0.7,
    }));

  const fundPages: MetadataRoute.Sitemap = topFunds.map((fund) => ({
    url: `${BASE_URL}/fon/${fund.code}`,
    lastModified: now,
    changeFrequency: "daily" as const,
    priority: fund.market_cap && fund.market_cap > 1e9 ? 0.9 : 0.7,
  }));

  return [...staticPages, ...typePages, ...companyPages, ...fundPages];
}
