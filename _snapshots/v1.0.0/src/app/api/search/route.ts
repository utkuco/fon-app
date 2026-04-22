import { NextRequest, NextResponse } from "next/server";
import { supabaseAdmin } from "@/lib/supabase-admin";

export const revalidate = 300;

async function getBenchmarks() {
  const { data } = await supabaseAdmin
    .from("benchmarks")
    .select("symbol, date, price")
    .order("date", { ascending: true });
  if (!data) return {};
  const map: Record<string, Array<{ date: string; price: number }>> = {};
  for (const row of data) {
    if (!map[row.symbol]) map[row.symbol] = [];
    map[row.symbol].push({ date: row.date, price: parseFloat(row.price) });
  }
  return map;
}

export async function GET(request: NextRequest) {
  const { searchParams } = new URL(request.url);
  const q = searchParams.get("q");
  const codes = searchParams.get("codes");
  const limit = Math.min(parseInt(searchParams.get("limit") || "10"), 20);

  // Search mode
  if (q && q.length >= 2) {
    const { data, error } = await supabaseAdmin
      .from("funds")
      .select(`
        code, name, fund_type, market_cap, daily_change, price,
        weekly, monthly, quarterly,
        company_id, companies:company_id ( name, logo, display_name )
      `)
      .or(`code.ilike.%${q}%,name.ilike.%${q}%`)
      .order("market_cap", { ascending: false })
      .limit(limit);

    if (error) return NextResponse.json({ error: error.message }, { status: 500 });

    const funds = data.map((f: any) => ({
      code: f.code, name: f.name, fund_type: f.fund_type,
      company: f.companies?.display_name || f.companies?.name || null, company_logo: f.companies?.logo || null,
      daily_change: f.daily_change, market_cap: f.market_cap, price: f.price,
      weekly: f.weekly, monthly: f.monthly, quarterly: f.quarterly,
    }));

    return NextResponse.json({ funds });
  }

  // By codes mode
  if (codes) {
    const codeList = codes.split(",").filter(Boolean);
    const { data, error } = await supabaseAdmin
      .from("funds")
      .select(`
        code, name, fund_type, market_cap, daily_change, price,
        weekly, monthly, quarterly, returns, breakdown, price_history,
        company_id, companies:company_id ( name, logo, display_name )
      `)
      .in("code", codeList);

    if (error) return NextResponse.json({ error: error.message }, { status: 500 });

    const funds = data.map((f: any) => ({
      code: f.code, name: f.name, fund_type: f.fund_type,
      company: Array.isArray(f.companies) ? f.companies[0]?.name || null : f.companies?.display_name || f.companies?.name || null,
      company_logo: Array.isArray(f.companies) ? f.companies[0]?.logo || null : f.companies?.logo || null,
      daily_change: f.daily_change, market_cap: f.market_cap, price: f.price,
      weekly: f.weekly, monthly: f.monthly, quarterly: f.quarterly,
      returns: f.returns, breakdown: f.breakdown, price_history: f.price_history,
    }));

    return NextResponse.json({ funds, benchmarks: await getBenchmarks() });
  }

  return NextResponse.json({ funds: [], error: "Provide q or codes param" }, { status: 400 });
}
