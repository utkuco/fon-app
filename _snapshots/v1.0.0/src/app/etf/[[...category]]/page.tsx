import { Metadata } from "next";
import { notFound } from "next/navigation";
import { supabaseAdmin } from "@/lib/supabase-admin";
import EtfPageClient from "../EtfPageClient";
import EtfDetailClient from "../EtfDetailClient";
import { filterEtfsByCategory, getCategoryByKey } from "@/lib/etf-categories";

// Known ETFs with price history in foreign_etf_prices
const KNOWN_PRICE_SYMBOLS = ["SPY", "IVV", "VOO", "QQQ", "VTI", "VEA", "VWO", "EFA", "IEMG", "GLD", "IAU", "SLV", "SGOL", "BND", "AGG", "TLT", "IEF", "LQD"];

const BASE_URL = "https://fonrapor.com";

export const revalidate = 3600;

async function getEtfs() {
  const { data: page1, error: err1 } = await supabaseAdmin
    .from("foreign_etfs")
    .select("symbol, name, category, fund_family, region, asset_type, currency, nav_price, price, price_try, change_pct, expense_ratio, dividend_yield, aum, ytd_return, ytd_return_try, one_month_return_try, three_month_return_try, six_month_return_try, three_yr_return, five_yr_return, beta, updated_at")
    .eq("is_active", true)
    .order("aum", { ascending: false, nullsFirst: false })
    .range(0, 999);

  if (err1) throw err1;

  const { data: page2, error: err2 } = await supabaseAdmin
    .from("foreign_etfs")
    .select("symbol, name, category, fund_family, region, asset_type, currency, nav_price, price, price_try, change_pct, expense_ratio, dividend_yield, aum, ytd_return, ytd_return_try, one_month_return_try, three_month_return_try, six_month_return_try, three_yr_return, five_yr_return, beta, updated_at")
    .eq("is_active", true)
    .order("aum", { ascending: false, nullsFirst: false })
    .range(1000, 2000);

  if (err2) {
    console.warn("Second ETF page failed:", err2.message);
    return page1 || [];
  }

  return [...(page1 || []), ...(page2 || [])];
}

async function getEtf(symbol: string) {
  const { data, error } = await supabaseAdmin
    .from("foreign_etfs")
    .select("*")
    .eq("symbol", symbol)
    .single();

  if (error || !data) return null;
  return data;
}

async function getEtfHoldings(symbol: string) {
  const { data } = await supabaseAdmin
    .from("foreign_etf_holdings")
    .select("*")
    .eq("etf_symbol", symbol)
    .order("weight", { ascending: false })
    .limit(10);
  return data || [];
}

async function getEtfSectors(symbol: string) {
  const { data } = await supabaseAdmin
    .from("foreign_etf_sectors")
    .select("*")
    .eq("etf_symbol", symbol)
    .order("weight", { ascending: false });
  return data || [];
}

async function getEtfPrices(symbol: string) {
  const { data } = await supabaseAdmin
    .from("foreign_etf_prices")
    .select("date, close")
    .eq("symbol", symbol)
    .order("date", { ascending: true })
    .limit(365);
  return data || [];
}

async function getEtfPricesForSymbols(symbols: string[]) {
  const { data } = await supabaseAdmin
    .from("foreign_etf_prices")
    .select("symbol, date, close")
    .in("symbol", symbols)
    .order("date", { ascending: true });
  return data || [];
}

// Pre-compute sparkline for a set of price points
function computeSparkline(prices: { date: string; close: number }[]): { points: [number, number][]; positive: boolean } | null {
  if (!prices || prices.length < 2) return null;
  const W = 100, H = 40;
  const closes = prices.map(p => p.close);
  const min = Math.min(...closes);
  const max = Math.max(...closes);
  const range = max - min || 1;
  const rangeX = (prices.length - 1) || 1;
  const pts: [number, number][] = prices.map((p, i) => [
    (i / rangeX) * W,
    H - ((p.close - min) / range) * H,
  ]);
  return { points: pts, positive: prices[prices.length - 1].close >= prices[0].close };
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ category?: string[] }>;
}): Promise<Metadata> {
  const { category } = await params;
  const key = category?.[0];

  if (key) {
    const etf = await getEtf(key);
    if (etf) {
      return {
        title: `${etf.name} (${key}) — ETF Detay | FonRapor`,
        description: `${etf.name} ETF fiyatı, gider oranı, portföy dağılımı, sektör ağırlıkları ve getiri performansı.`,
        alternates: { canonical: `${BASE_URL}/etf/${key}` },
      };
    }

    const cat = getCategoryByKey(key);
    if (cat) {
      const allEtfs = await getEtfs();
      const filtered = filterEtfsByCategory(allEtfs, key);
      return {
        title: `${cat.label} ETF (${filtered.length}) | FonRapor`,
        description: `${cat.label} kategorisindeki yabancı ETF'ler — ABD borsalarında işlem gören fonlar. Fiyat, gider oranı ve portföy dağılımı.`,
        alternates: { canonical: `${BASE_URL}/etf/${key}` },
      };
    }
  }

  return {
    title: `Yabancı ETF'ler | FonRapor`,
    description: "ABD borsalarında işlem gören yabancı ETF'ler — S&P 500, Nasdaq, altın, tahvil fonları. Fiyat, gider oranı, temettü verimi.",
    alternates: { canonical: `${BASE_URL}/etf` },
  };
}

export default async function EtfPage({
  params,
}: {
  params: Promise<{ category?: string[] }>;
}) {
  const { category } = await params;
  const key = category?.[0];

  // Always fetch all ETFs + all prices
  const [allEtfs, allPrices] = await Promise.all([
    getEtfs(),
    getEtfPricesForSymbols(KNOWN_PRICE_SYMBOLS),
  ]);

  // Build sparkline map: symbol → { points, positive }
  const sparklineMap: Record<string, { points: [number, number][]; positive: boolean }> = {};
  for (const symbol of KNOWN_PRICE_SYMBOLS) {
    const symbolPrices = allPrices.filter(p => p.symbol === symbol);
    if (symbolPrices.length >= 2) {
      const sp = computeSparkline(symbolPrices);
      if (sp) sparklineMap[symbol] = sp;
    }
  }

  // Case 1: No key → all ETFs
  if (!key) {
    return (
      <EtfPageClient
        initialEtfs={allEtfs}
        sparklineMap={sparklineMap}
        activeCategory={undefined}
        activeCategoryLabel={undefined}
        totalCount={allEtfs.length}
      />
    );
  }

  // Case 2: Check if key is a real ETF symbol
  const etf = await getEtf(key);
  if (etf) {
    const [holdings, sectors, prices] = await Promise.all([
      getEtfHoldings(key),
      getEtfSectors(key),
      getEtfPrices(key),
    ]);
    return <EtfDetailClient etf={etf} holdings={holdings} sectors={sectors} prices={prices} />;
  }

  // Case 3: Check if key is a category
  const cat = getCategoryByKey(key);
  if (cat) {
    const filtered = filterEtfsByCategory(allEtfs, key);
    return (
      <EtfPageClient
        initialEtfs={filtered}
        sparklineMap={sparklineMap}
        activeCategory={cat.key}
        activeCategoryLabel={cat.label}
        totalCount={allEtfs.length}
      />
    );
  }

  // Case 4: Not found
  notFound();
}
