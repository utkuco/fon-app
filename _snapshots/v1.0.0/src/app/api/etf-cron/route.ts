import { NextResponse } from "next/server";

// Vercel Cron: runs daily at 23:00 (11PM Turkey = 4PM EST US market close)
// Uses yahoo-finance2 (Node.js)
// Holdings are fetched separately by the Python scraper (scripts/etf_scraper.py)
// CRON_SECRET configured in Vercel project settings

const SUPABASE_URL = process.env.NEXT_PUBLIC_SUPABASE_URL || "https://oqkobptbvcazifpvjwfz.supabase.co";
const SUPABASE_KEY = process.env.SUPABASE_SERVICE_KEY || "***";

const ETF_LIST = [
  "SPY", "IVV", "VOO", "QQQ", "QQQM", "VTI", "ITOT",
  "XLK", "XLV", "XLF", "XLE", "XLY", "XLP", "XLI", "XLRE", "XLB", "XLC", "XLU",
  "BND", "AGG", "TLT", "VGLT", "SHY", "TIP", "LQD", "HYG",
  "GLD", "SLV", "USO", "DJP",
  "VEA", "VWO", "EFA", "IEFA",
];

const ETF_ASSET_TYPES: Record<string, string> = {
  SPY: "EQUITY", IVV: "EQUITY", VOO: "EQUITY", QQQ: "EQUITY", QQQM: "EQUITY", VTI: "EQUITY", ITOT: "EQUITY",
  XLK: "EQUITY", XLV: "EQUITY", XLF: "EQUITY", XLE: "EQUITY", XLY: "EQUITY", XLP: "EQUITY", XLI: "EQUITY",
  XLRE: "REAL_ESTATE", XLB: "EQUITY", XLC: "EQUITY", XLU: "EQUITY",
  BND: "BOND", AGG: "BOND", TLT: "BOND", VGLT: "BOND", SHY: "BOND", TIP: "BOND", LQD: "BOND", HYG: "BOND",
  GLD: "COMMODITY", SLV: "COMMODITY", USO: "COMMODITY", DJP: "COMMODITY",
  VEA: "EQUITY", VWO: "EQUITY", EFA: "EQUITY", IEFA: "EQUITY",
};

async function supabaseUpsert(table: string, rows: Record<string, unknown>[], conflictCol: string) {
  if (!rows.length) return;
  const url = `${SUPABASE_URL}/rest/v1/${table}`;
  const payload = JSON.stringify(rows);
  const req = new Request(url, {
    method: "POST",
    headers: {
      apikey: SUPABASE_KEY,
      Authorization: `Bearer ${SUPABASE_KEY}`,
      "Content-Type": "application/json",
      Prefer: "resolution=merge-duplicates",
      "On-Conflict": conflictCol,
    },
    body: payload,
  });
  const res = await fetch(req);
  if (!res.ok) {
    console.error(`UPSERT ERROR ${table}:`, await res.text());
  }
}

async function fetchQuote(symbol: string, yf: any): Promise<Record<string, unknown> | null> {
  try {
    const info = await yf.quote(symbol);
    if (!info || info.quoteType !== "ETF") return null;
    return info;
  } catch (e) {
    console.error(`${symbol} error:`, e);
    return null;
  }
}

async function fetchHistory(symbol: string, yf: any): Promise<Record<string, unknown>[]> {
  try {
    const bars = await yf.historical(symbol, { interval: "1d", period: "5d" });
    if (!bars || bars.length === 0) return [];
    return bars.map((bar: any) => ({
      symbol,
      date: String(bar.date).split("T")[0],
      open: bar.open,
      high: bar.high,
      low: bar.low,
      close: bar.close,
      volume: bar.volume || null,
    }));
  } catch (e) {
    console.error(`${symbol} history error:`, e);
    return [];
  }
}

export async function GET(request: Request) {
  const authHeader = request.headers.get("authorization");
  if (authHeader !== `Bearer ${process.env.CRON_SECRET}`) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  console.log("[ETF Cron] Starting...");
  const start = Date.now();

  try {
    // Dynamic import yahoo-finance2 (avoid bundling issues)
    const YahooFinance = (await import("yahoo-finance2")).default;
    const yf = new YahooFinance({ suppressNotices: ["yahooSurvey"] });

    // 1. Exchange rates
    console.log("[ETF Cron] Rates...");
    const rates: Record<string, number> = {};
    const ratePairs = [["USD", "TRY=X"], ["EUR", "EURTRY=X"], ["GBP", "GBPTRY=X"]];
    for (const [base, ticker] of ratePairs) {
      try {
        const info = await yf.quote(ticker);
        if (info?.regularMarketPrice) {
          rates[base] = info.regularMarketPrice;
          console.log(`  ${base}/TRY = ${info.regularMarketPrice}`);
        }
      } catch (e) {
        console.error(`  ${base} rate error:`, e);
      }
    }
    const today = new Date().toISOString().split("T")[0];
    if (Object.keys(rates).length > 0) {
      const rateRows = Object.entries(rates).map(([base, rate]) => ({
        base, quote: "TRY", rate, date: today,
      }));
      await supabaseUpsert("exchange_rates", rateRows, "base");
    }

    // 2. ETF info
    console.log("[ETF Cron] ETF info...");
    const etfRows: Record<string, unknown>[] = [];
    for (const symbol of ETF_LIST) {
      const info = await fetchQuote(symbol, yf);
      if (!info) continue;

      const priceRaw = info.regularMarketPrice ?? info.navPrice;
      const price = priceRaw != null ? Number(priceRaw) : null;
      const currency = String(info.currency || "USD");
      const rate = rates[currency] ?? 1;
      const priceTry = price != null ? Math.round(price * rate * 100) / 100 : null;

      const changeRaw = info.regularMarketChangePercent;
      const expenseRaw = info.netExpenseRatio;
      const yieldRaw = info.dividendYield;
      const aumRaw = info.totalAssets;
      const ytdRaw = info.ytdReturn;
      const threeYrRaw = info.threeYearAverageReturn;
      const fiveYrRaw = info.fiveYearAverageReturn;
      const betaRaw = info.beta3Year;

      etfRows.push({
        symbol,
        name: String(info.longName || info.shortName || symbol),
        category: info.category ? String(info.category) : null,
        fund_family: info.fundFamily ? String(info.fundFamily) : null,
        region: "US",
        asset_type: ETF_ASSET_TYPES[symbol] || "EQUITY",
        currency,
        nav_price: info.navPrice != null ? Number(info.navPrice) : null,
        price,
        price_try: priceTry,
        change_pct: changeRaw != null ? Number(changeRaw) / 100 : null,
        expense_ratio: expenseRaw != null ? Number(expenseRaw) : null,
        dividend_yield: yieldRaw != null ? Number(yieldRaw) : null,
        aum: aumRaw != null ? Number(aumRaw) : null,
        ytd_return: ytdRaw != null ? Number(ytdRaw) : null,
        three_yr_return: threeYrRaw != null ? Number(threeYrRaw) : null,
        five_yr_return: fiveYrRaw != null ? Number(fiveYrRaw) : null,
        beta: betaRaw != null ? Number(betaRaw) : null,
        currency_rate: rate !== 1 ? rate : null,
        updated_at: new Date().toISOString(),
        is_active: true,
      });

      // Rate limit: 3 req/sec max
      await new Promise((r) => setTimeout(r, 350));
    }
    await supabaseUpsert("foreign_etfs", etfRows, "symbol");
    console.log(`[ETF Cron] Upserted ${etfRows.length} ETFs`);

    // 3. Recent prices (last 5 days)
    console.log("[ETF Cron] Prices...");
    for (const symbol of ETF_LIST) {
      const prices = await fetchHistory(symbol, yf);
      if (prices.length > 0) {
        await supabaseUpsert("foreign_etf_prices", prices.slice(-5), "symbol");
      }
      await new Promise((r) => setTimeout(r, 200));
    }

    const elapsed = Math.round((Date.now() - start) / 1000);
    console.log(`[ETF Cron] Done in ${elapsed}s`);

    return NextResponse.json({
      success: true,
      etfs_updated: etfRows.length,
      rates_updated: Object.keys(rates).length,
      elapsed_seconds: elapsed,
      timestamp: new Date().toISOString(),
    });
  } catch (error) {
    console.error("[ETF Cron] Error:", error);
    return NextResponse.json({ error: String(error) }, { status: 500 });
  }
}
