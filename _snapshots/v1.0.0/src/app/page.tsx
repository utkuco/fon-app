import HomePageClient from "./HomePageClient";
import { fetchHomePageData } from "@/lib/homepage-data";
import { supabaseAdmin } from "@/lib/supabase-admin";

export const revalidate = 3600; // cache 1 hour

async function getEtfData() {
  const { data, error } = await supabaseAdmin
    .from("foreign_etfs")
    .select("symbol, name, price, price_try, currency, change_pct, expense_ratio, dividend_yield, aum, ytd_return, ytd_return_try, one_month_return_try, three_month_return_try, six_month_return_try, three_yr_return, five_yr_return, beta, asset_type, fund_family, updated_at")
    .eq("is_active", true)
    .order("aum", { ascending: false, nullsFirst: false });

  if (error) return { etfs: [], topGainers: [], topLosers: [] };

  const etfs = data || [];
  // Sort by 1-month return (TRY) for top gainers — same metric Turkish funds use (monthly)
  const sortedByMonthly = [...etfs].sort((a, b) => (b.one_month_return_try ?? 0) - (a.one_month_return_try ?? 0));
  const topGainers = sortedByMonthly.slice(0, 24).map(e => ({
    symbol: e.symbol,
    name: e.name,
    change_pct: e.one_month_return_try ?? 0,
    aum: e.aum,
    ret_1m: (e.one_month_return_try ?? 0) * 100,
    ret_3m: (e.three_month_return_try ?? 0) * 100,
    ret_6m: (e.six_month_return_try ?? 0) * 100,
  }));
  // Sort by 1-month return ascending for losers — take worst 24
  const topLosers = sortedByMonthly.slice(-24).reverse().map(e => ({
    symbol: e.symbol,
    name: e.name,
    change_pct: (e.one_month_return_try ?? 0) * 100,
    aum: e.aum,
    ret_1m: (e.one_month_return_try ?? 0) * 100,
    ret_3m: (e.three_month_return_try ?? 0) * 100,
    ret_6m: (e.six_month_return_try ?? 0) * 100,
  }));

  return { etfs, topGainers, topLosers };
}

// Fetch top Turkish funds with period returns for GainersSection
// Note: funds table has weekly/monthly but NOT quarterly or 6m — use returns JSON as fallback
async function getTurkishGainers() {
  const { data, error } = await supabaseAdmin
    .from("funds")
    .select("code, name, market_cap, daily_change, weekly, monthly, returns")
    .order("monthly", { ascending: false, nullsFirst: false })
    .limit(100);

  if (error || !data) return { topGainers: [], topLosers: [] };

  const sorted = [...data].sort((a, b) => (b.monthly ?? 0) - (a.monthly ?? 0));
  const topGainers = sorted.slice(0, 20).map(f => ({
    code: f.code,
    name: f.name,
    market_cap: f.market_cap ?? 0,
    ret_1d: f.daily_change ?? 0,
    ret_1w: f.weekly ?? 0,
    ret_1m: f.monthly ?? 0,
    ret_3m: (f.returns as Record<string, number> | null)?.["3M"] ?? null,
    ret_6m: null,
  }));
  const topLosers = sorted.slice(-20).reverse().map(f => ({
    code: f.code,
    name: f.name,
    market_cap: f.market_cap ?? 0,
    ret_1d: f.daily_change ?? 0,
    ret_1w: f.weekly ?? 0,
    ret_1m: f.monthly ?? 0,
    ret_3m: (f.returns as Record<string, number> | null)?.["3M"] ?? null,
    ret_6m: null,
  }));

  return { topGainers, topLosers };
}

export default async function HomePage() {
  const [initialData, { etfs, topGainers, topLosers }, { topGainers: turkishGainers, topLosers: turkishLosers }] = await Promise.all([
    fetchHomePageData(),
    getEtfData(),
    getTurkishGainers(),
  ]);

  return <HomePageClient initialData={initialData} initialEtfs={etfs} etfTopGainers={topGainers} etfTopLosers={topLosers} turkishGainers={turkishGainers} />;
}
