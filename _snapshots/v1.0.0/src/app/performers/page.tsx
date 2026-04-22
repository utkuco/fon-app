import { Metadata } from "next";
import { supabaseAdmin } from "@/lib/supabase-admin";
import PerformersClient from "./PerformersClient";

const BASE_URL = "https://fonrapor.com";

export const revalidate = 3600;

async function getTurkishFundsTopPerformers() {
  // Get funds with best YTD returns, including company info and price_try for USD conversion
  const { data, error } = await supabaseAdmin
    .from("funds")
    .select(`
      code, name, fund_type, market_cap, price, daily_change,
      weekly, monthly, quarterly,
      companies:company_id ( name, logo, display_name )
    `)
    .not("returns", "is", null)
    .order("monthly", { ascending: false })
    .limit(10);

  if (error) throw error;

  // Get latest exchange rate
  const { data: rateData } = await supabaseAdmin
    .from("exchange_rates")
    .select("rate")
    .eq("base", "USD")
    .order("date", { ascending: false })
    .limit(1)
    .single();

  const usdRate = rateData?.rate || 44.5;

  // Compute USD returns from price history
  // For now, use stored quarterly/monthly/weekly returns as proxy
  // and convert price to USD
  return (data || []).map((f: any) => {
    const priceTL = f.price || 0;
    const priceUSD = priceTL / usdRate;
    const returns = f.returns as Record<string, number> | null;
    return {
      code: f.code,
      name: f.name,
      fund_type: f.fund_type,
      company: f.companies?.display_name || f.companies?.name || null,
      company_logo: f.companies?.logo || null,
      market_cap: f.market_cap,
      price: priceTL,
      price_usd: Math.round(priceUSD * 100) / 100,
      daily_change: f.daily_change,
      weekly: f.weekly,
      monthly: f.monthly,
      quarterly: f.quarterly,
      returns,
      // For USD estimate: approximate using TL return + USD/TRY change
      // We'll show returns in TL and note the USD equivalent
      usd_rate: usdRate,
    };
  });
}

async function getEtfTopPerformers() {
  const { data, error } = await supabaseAdmin
    .from("foreign_etfs")
    .select("symbol, name, price, price_try, currency, change_pct, ytd_return, three_yr_return, five_yr_return, aum, asset_type")
    .eq("is_active", true)
    .not("ytd_return", "is", null)
    .order("ytd_return", { ascending: false })
    .limit(10);

  if (error) throw error;
  return data || [];
}

export async function generateMetadata(): Promise<Metadata> {
  return {
    title: "Performanslar — Türk Fon ve Yabancı ETF Karşılaştırma | FonRapor",
    description: "Türk yatırım fonları ve ABD ETF'leri birlikte sıralandı. Aylık ve çeyreklik getiriye göre karışık performans karşılaştırması.",
    alternates: { canonical: `${BASE_URL}/performers` },
  };
}

export default async function PerformersPage() {
  const [turkishFunds, etfs] = await Promise.all([
    getTurkishFundsTopPerformers(),
    getEtfTopPerformers(),
  ]);

  return <PerformersClient turkishFunds={turkishFunds} etfs={etfs} />;
}
