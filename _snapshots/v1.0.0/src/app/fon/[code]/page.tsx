import { Metadata } from "next";
import { notFound } from "next/navigation";
import { supabaseAdmin } from "@/lib/supabase-admin";
import { TYPE_LABELS } from "@/lib/shared-config";
import FundDetailClient from "./FundDetailClient";

const BASE_URL = "https://web-vert-delta-62.vercel.app";

// Dynamic — her istekte server-side render
// Kullanıcı fondetay'a tıklayınca: skeleton/header anında gelir, veri sonra yüklenir
export const dynamic = "force-dynamic";

async function getFundByCode(code: string) {
  const { data } = await supabaseAdmin
    .from("funds")
    .select(`
      code, name, fund_type, market_cap, daily_change, price,
      weekly, monthly, quarterly, returns, breakdown, price_history,
      management_fee, max_total_expense_ratio, purchase_valor, sale_valor,
      company_id, companies:company_id ( name, logo, display_name )
    `)
    .eq("code", code)
    .single();

  if (!data) return null;
  const d = data as any;

  const latestPriceEntry = d.price_history?.length > 0
    ? d.price_history[d.price_history.length - 1]
    : null;

  return {
    code: d.code,
    name: d.name,
    fund_type: d.fund_type,
    company: Array.isArray(d.companies)
      ? d.companies[0]?.display_name || d.companies[0]?.name || null
      : d.companies?.display_name || d.companies?.name || null,
    company_logo: Array.isArray(d.companies)
      ? d.companies[0]?.logo || null
      : d.companies?.logo || null,
    daily_change: d.daily_change,
    market_cap: d.market_cap,
    price: d.price,
    weekly: d.weekly,
    monthly: d.monthly,
    quarterly: d.quarterly,
    returns: d.returns,
    breakdown: d.breakdown,
    price_history: d.price_history,
    number_of_investors: latestPriceEntry?.investors ?? null,
    number_of_shares: latestPriceEntry?.shares ?? null,
    management_fee: d.management_fee ?? null,
    max_total_expense_ratio: d.max_total_expense_ratio ?? null,
    purchase_valor: d.purchase_valor ?? null,
    sale_valor: d.sale_valor ?? null,
  };
}

async function getFundRank(code: string) {
  const { data } = await supabaseAdmin
    .from("fund_category_ranks")
    .select("rank, category_count, percentile")
    .eq("fund_code", code)
    .single();
  return data ?? null;
}

async function getData() {
  // Kategori istatistikleri için — sadece son 60 gün, hızlı olsun
  const [catHistResult, benchResult] = await Promise.all([
    supabaseAdmin
      .from("category_history")
      .select("fund_type, date, avg_price_index, avg_return, fund_count")
      .order("date", { ascending: true })
      .limit(500), // sadece son birkaç ay
    supabaseAdmin
      .from("benchmarks")
      .select("symbol, date, price")
      .in("symbol", ["BIST100", "GOLD", "USDTRY", "SP500", "NASDAQ", "BTCUSD", "ETHUSD"])
      .order("date", { ascending: true }),
  ]);

  const categoryHistoryMap: Record<string, Record<string, { avg_price_index: number; avg_return: number; fund_count: number }>> = {};
  for (const row of (catHistResult.data || [])) {
    if (!categoryHistoryMap[row.fund_type]) categoryHistoryMap[row.fund_type] = {};
    categoryHistoryMap[row.fund_type][row.date] = {
      avg_price_index: parseFloat(row.avg_price_index),
      avg_return: parseFloat(row.avg_return),
      fund_count: row.fund_count,
    };
  }

  return { benchmarks: benchResult.data || [], categoryHistoryMap };
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ code: string }>;
}): Promise<Metadata> {
  const { code } = await params;
  const upperCode = code.toUpperCase();
  const fund = await getFundByCode(upperCode) as any;

  if (!fund) {
    return {
      title: "Fon Bulunamadı | FonRapor",
      description: "İstediğiniz yatırım fonu bulunamadı.",
    };
  }

  const typeLabel = TYPE_LABELS[fund.fund_type || ""] || fund.fund_type || "Yatırım Fonu";
  const title = `${fund.code} — ${fund.name} | FonRapor`;
  const aumStr = fund.market_cap
    ? `${(fund.market_cap / 1e6).toLocaleString("tr-TR", { maximumFractionDigits: 0 })}M TL`
    : "—";
  const description = `${fund.name} (${fund.code}) fon analizi. Tür: ${typeLabel}. Fiyat: ${fund.price?.toFixed(4) ?? "—" } TL. AUM: ${aumStr}. Günlük değişim: ${fund.daily_change != null ? (fund.daily_change >= 0 ? "+" : "") + fund.daily_change.toFixed(2) + "%" : "—"}. Portföy dağılımı ve getiri performansı.`;

  const canonicalUrl = `${BASE_URL}/fon/${fund.code}`;

  return {
    title,
    description,
    keywords: [fund.code, fund.name, typeLabel, "yatırım fonu", "tefas", "fon analizi", "portföy", fund.company || ""].filter(Boolean).join(", "),
    authors: [{ name: "FonRapor" }],
    openGraph: {
      type: "article", locale: "tr_TR", url: canonicalUrl, siteName: "FonRapor", title, description,
      images: [{ url: "/og-image.png", width: 1200, height: 630, alt: `${fund.code} — ${fund.name}` }],
    },
    twitter: { card: "summary_large_image", title, description, images: ["/og-image.png"] },
    alternates: { canonical: canonicalUrl },
  };
}

function FundJsonLd({ fund, canonicalUrl, typeLabel }: { fund: any; canonicalUrl: string; typeLabel: string }) {
  const jsonLd = {
    "@context": "https://schema.org",
    "@graph": [
      {
        "@type": "BreadcrumbList",
        itemListElement: [
          { "@type": "ListItem", position: 1, name: "Anasayfa", item: BASE_URL },
          { "@type": "ListItem", position: 2, name: typeLabel, item: `${BASE_URL}/type/${fund.fund_type}` },
          { "@type": "ListItem", position: 3, name: fund.code, item: canonicalUrl },
        ],
      },
      {
        "@type": "Product",
        name: fund.name,
        description: `${fund.name} (${fund.code}) fon analizi. Tür: ${typeLabel}.`,
        identifier: fund.code,
        offers: { "@type": "Offer", price: fund.price?.toString() ?? "0", priceCurrency: "TRY" },
      },
    ],
  };
  return (
    <script
      type="application/ld+json"
      dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }}
    />
  );
}

export default async function FundPage({
  params,
}: {
  params: Promise<{ code: string }>;
}) {
  const { code } = await params;
  const upperCode = code.toUpperCase();

  const [fund, data, fundRank] = await Promise.all([
    getFundByCode(upperCode),
    getData(),
    getFundRank(upperCode),
  ]);

  if (!fund) notFound();

  const typeLabel = TYPE_LABELS[fund.fund_type || ""] || fund.fund_type || "Yatırım Fonu";
  const canonicalUrl = `${BASE_URL}/fon/${fund.code}`;

  return (
    <>
      <FundJsonLd fund={fund} canonicalUrl={canonicalUrl} typeLabel={typeLabel} />
      <FundDetailClient
        initialFund={fund}
        initialBenchmarks={data.benchmarks}
        categoryHistoryMap={data.categoryHistoryMap}
        fundRank={fundRank}
      />
    </>
  );
}
