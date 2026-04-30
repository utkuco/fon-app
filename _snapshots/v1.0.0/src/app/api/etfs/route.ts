import { createClient } from "@supabase/supabase-js";
import { NextResponse } from "next/server";

const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL || "https://oqkobptbvcazifpvjwfz.supabase.co";
const supabaseServiceKey = process.env.SUPABASE_SERVICE_KEY || "***";

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  const region = searchParams.get("region");
  const assetType = searchParams.get("asset_type");
  const sort = searchParams.get("sort") || "aum";
  const symbol = searchParams.get("symbol");

  const supabase = createClient(supabaseUrl, supabaseServiceKey);

  // Single ETF by symbol
  if (symbol) {
    const { data, error } = await supabase
      .from("foreign_etfs")
      .select("*")
      .eq("symbol", symbol)
      .single();

    if (error || !data) {
      return NextResponse.json({ error: "ETF not found" }, { status: 404 });
    }

    // Fetch holdings + sectors + prices in parallel
    const [{ data: holdings }, { data: sectors }, { data: prices }] = await Promise.all([
      supabase.from("foreign_etf_holdings").select("*").eq("etf_symbol", symbol).order("weight", { ascending: false }),
      supabase.from("foreign_etf_sectors").select("*").eq("etf_symbol", symbol).order("weight", { ascending: false }),
      supabase.from("foreign_etf_prices").select("*").eq("symbol", symbol).order("date", { ascending: false }).limit(365),
    ]);

    return NextResponse.json({ ...data, holdings: holdings || [], sectors: sectors || [], prices: prices || [] });
  }

  // All ETFs with filters
  let query = supabase
    .from("foreign_etfs")
    .select("symbol, name, category, fund_family, region, asset_type, currency, nav_price, price, price_try, change_pct, expense_ratio, dividend_yield, aum, ytd_return, three_yr_return, five_yr_return, beta, currency_rate, updated_at, is_active")
    .eq("is_active", true);

  if (region) query = query.eq("region", region);
  if (assetType) query = query.eq("asset_type", assetType);

  // Sort
  const sortMap: Record<string, string> = {
    aum: "aum",
    price: "price",
    change: "change_pct",
    yield: "dividend_yield",
    expense: "expense_ratio",
    ytd: "ytd_return",
    three_yr: "three_yr_return",
  };
  const sortCol = sortMap[sort] || "aum";
  query = query.order(sortCol, { ascending: false, nullsFirst: false });

  const { data, error } = await query;

  if (error) {
    return NextResponse.json({ error: error.message }, { status: 500 });
  }

  return NextResponse.json(data || []);
}
