import { NextRequest, NextResponse } from "next/server";
import { supabaseAdmin } from "@/lib/supabase-admin";

export const revalidate = 300;

export async function GET(request: NextRequest) {
  const { searchParams } = new URL(request.url);
  const codes = searchParams.get("codes");

  if (!codes) {
    return NextResponse.json({ funds: [] });
  }

  const codeList = codes.split(",").filter(Boolean);

  const { data, error } = await supabaseAdmin
    .from("funds")
    .select(`
      code, name, fund_type, market_cap, daily_change, price,
      weekly, monthly, quarterly,
      company_id, companies:company_id ( name, logo, display_name )
    `)
    .in("code", codeList);

  if (error) {
    return NextResponse.json({ error: error.message }, { status: 500 });
  }

  const funds = data.map((f: any) => ({
    code: f.code,
    name: f.name,
    fund_type: f.fund_type,
    company: f.companies?.display_name || f.companies?.name || null,
    company_logo: f.companies?.logo || null,
    daily_change: f.daily_change,
    market_cap: f.market_cap,
    price: f.price,
    weekly: f.weekly,
    monthly: f.monthly,
    quarterly: f.quarterly,
  }));

  return NextResponse.json({ funds });
}
