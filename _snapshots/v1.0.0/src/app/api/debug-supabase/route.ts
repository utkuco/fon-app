import { supabaseAdmin } from "@/lib/supabase-admin";
import { NextResponse } from "next/server";

export async function GET() {
  const start = Date.now();
  const tests: Record<string, any> = {};

  try {
    // Test 1: Simple query (already known to work)
    const { data: d1, error: e1 } = await supabaseAdmin
      .from("funds").select("code, name").limit(1);
    tests.simple = { success: !e1, error: e1?.message, count: d1?.length };

    // Test 2: With company_id column
    const { data: d2, error: e2 } = await supabaseAdmin
      .from("funds").select("code, company_id").limit(1);
    tests.with_company_id = { success: !e2, error: e2?.message, count: d2?.length, sample: d2?.[0] };

    // Test 3: Full join query (like homepage)
    const { data: d3, error: e3 } = await supabaseAdmin
      .from("funds")
      .select(`code, name, fund_type, market_cap, daily_change, price,
        weekly, monthly, quarterly, breakdown,
        company_id, companies:company_id ( name, logo, display_name )`)
      .order("market_cap", { ascending: false }).limit(1);
    tests.full_join = { success: !e3, error: e3?.message, count: d3?.length, sample: d3?.[0] ? {code: d3[0].code, name: d3[0].name, company: d3[0].companies} : null };

    return NextResponse.json({
      tests,
      total_duration_ms: Date.now() - start,
    });
  } catch (err: any) {
    return NextResponse.json({ tests, error: err?.message, stack: err?.stack, total_duration_ms: Date.now() - start });
  }
}
