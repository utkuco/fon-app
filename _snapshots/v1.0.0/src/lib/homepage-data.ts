// Shared data-fetching logic for homepage
// Used by both the API route (api/homepage-data/route.ts) and the page component (page.tsx)
import { supabaseAdmin } from "@/lib/supabase-admin";

export interface HomePageData {
  funds: any[];
  stats: {
    total: number;
    total_market_cap: number;
    avg_daily_change: number;
    latest_date: string | null;
    trading_days: number;
    top5_gainers: Array<{ code: string; name: string; change: number; market_cap: number }>;
    top5_losers: Array<{ code: string; name: string; change: number; market_cap: number }>;
    most_invested: Array<{ code: string; name: string; market_cap: number }>;
    most_held_stocks: Array<Record<string, unknown>>;
    category_stats: Record<string, { count: number; avg_change: number; total_market_cap: number }>;
    category_change: Record<string, { change_pct: number; prev_aum: number; curr_aum: number; count: number }>;
    category_sparklines: Record<string, { points: Array<[number, number]>; positive: boolean }>;
    // benchmarks_data: pre-computed by fetch-benchmarks.py, written to homepage_stats.benchmarks_data
    // Format: { SYMBOL: { data: [{date, price}], change: number } }
    benchmarks_data: Record<string, { data: Array<{ date: string; price: number }>; change: number }>;
  } | null;
  benchmarks: Record<string, Array<{ date: string; price: number }>>; // legacy, kept for compatibility
}

export async function fetchHomePageData(): Promise<HomePageData> {
  // ── 1. Funds (pre-computed sparkline, ordered by AUM) ──────────────────
  // Note: Supabase REST default limit is 1000 — set explicit limit above that
  const { data: funds, error } = await supabaseAdmin
    .from("funds")
    .select(`code, name, fund_type, company_id, market_cap, daily_change, price, weekly, monthly, quarterly, breakdown, sparkline`)
    .order("market_cap", { ascending: false })
    .limit(5000);

  if (error) {
    console.error("[homepage] funds error:", error);
    return { funds: [], stats: null, benchmarks: {} };
  }

  // ── 2. Pre-computed stats from homepage_stats (includes benchmarks_data) ────
  // benchmarks_data is pre-computed by fetch-benchmarks.py → written to homepage_stats
  const { data: statsRow } = await supabaseAdmin
    .from("homepage_stats")
    .select("*")
    .eq("id", 1)
    .single();

  const benchmarks_data: Record<string, { data: Array<{ date: string; price: number }>; change: number }> =
    (statsRow?.benchmarks_data as Record<string, { data: Array<{ date: string; price: number }>; change: number }>) || {};

  // Legacy grouped format for existing components
  const grouped: Record<string, Array<{ date: string; price: number }>> = {};
  for (const [sym, v] of Object.entries(benchmarks_data)) {
    if (v?.data) grouped[sym] = v.data;
  }

  const stats = statsRow ? {
    total: statsRow.total || 0,
    total_market_cap: Number(statsRow.total_market_cap) || 0,
    avg_daily_change: Number(statsRow.avg_daily_change) || 0,
    latest_date: statsRow.latest_date || null,
    trading_days: statsRow.trading_days || 0,
    top5_gainers: statsRow.top5_gainers || [],
    top5_losers: statsRow.top5_losers || [],
    most_invested: statsRow.most_invested || [],
    most_held_stocks: statsRow.most_held_stocks || [],
    category_stats: statsRow.category_stats || {},
    category_change: statsRow.category_change || {},
    category_sparklines: statsRow.category_sparklines || {},
    benchmarks_data,
  } : null;

  return { funds: funds || [], stats, benchmarks: grouped };
}
