import { createClient } from "@supabase/supabase-js";

const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL || "https://oqkobptbvcazifpvjwfz.supabase.co";
const supabaseServiceKey = process.env.SUPABASE_SERVICE_KEY || "***";

export async function POST() {
  const supabase = createClient(supabaseUrl, supabaseServiceKey);

  const results = [];

  // foreign_etfs
  const { error: e1 } = await supabase.rpc("exec_sql", {
    sql: `
      CREATE TABLE IF NOT EXISTS foreign_etfs (
        id              SERIAL PRIMARY KEY,
        symbol          TEXT UNIQUE NOT NULL,
        name            TEXT NOT NULL,
        category        TEXT,
        fund_family     TEXT,
        region          TEXT DEFAULT 'US',
        asset_type      TEXT DEFAULT 'EQUITY',
        currency        TEXT NOT NULL DEFAULT 'USD',
        nav_price       NUMERIC(12,4),
        price           NUMERIC(12,4),
        price_try       NUMERIC(12,2),
        change_pct      NUMERIC(8,4),
        expense_ratio   NUMERIC(8,4),
        dividend_yield NUMERIC(8,4),
        aum             BIGINT,
        ytd_return      NUMERIC(8,4),
        three_yr_return NUMERIC(8,4),
        five_yr_return  NUMERIC(8,4),
        beta            NUMERIC(6,4),
        currency_rate   NUMERIC(10,4),
        updated_at      TIMESTAMPTZ DEFAULT NOW(),
        is_active       BOOLEAN DEFAULT TRUE
      );
    `
  });
  results.push({ table: "foreign_etfs", error: e1?.message || null });

  const { error: e2 } = await supabase.rpc("exec_sql", {
    sql: `CREATE INDEX IF NOT EXISTS idx_etf_symbol ON foreign_etfs(symbol);`
  });
  const { error: e3 } = await supabase.rpc("exec_sql", {
    sql: `CREATE INDEX IF NOT EXISTS idx_etf_region ON foreign_etfs(region);`
  });
  const { error: e4 } = await supabase.rpc("exec_sql", {
    sql: `CREATE INDEX IF NOT EXISTS idx_etf_asset_type ON foreign_etfs(asset_type);`
  });

  // foreign_etf_holdings
  const { error: e5 } = await supabase.rpc("exec_sql", {
    sql: `
      CREATE TABLE IF NOT EXISTS foreign_etf_holdings (
        id              SERIAL PRIMARY KEY,
        etf_symbol      TEXT NOT NULL REFERENCES foreign_etfs(symbol) ON DELETE CASCADE,
        holding_symbol  TEXT NOT NULL,
        holding_name    TEXT NOT NULL,
        weight          NUMERIC(6,4) NOT NULL,
        updated_at      TIMESTAMPTZ DEFAULT NOW(),
        UNIQUE(etf_symbol, holding_symbol)
      );
    `
  });
  results.push({ table: "foreign_etf_holdings", error: e5?.message || null });

  // foreign_etf_sectors
  const { error: e6 } = await supabase.rpc("exec_sql", {
    sql: `
      CREATE TABLE IF NOT EXISTS foreign_etf_sectors (
        id              SERIAL PRIMARY KEY,
        etf_symbol      TEXT NOT NULL REFERENCES foreign_etfs(symbol) ON DELETE CASCADE,
        sector          TEXT NOT NULL,
        weight          NUMERIC(6,4) NOT NULL,
        updated_at      TIMESTAMPTZ DEFAULT NOW(),
        UNIQUE(etf_symbol, sector)
      );
    `
  });
  results.push({ table: "foreign_etf_sectors", error: e6?.message || null });

  // foreign_etf_prices
  const { error: e7 } = await supabase.rpc("exec_sql", {
    sql: `
      CREATE TABLE IF NOT EXISTS foreign_etf_prices (
        id          SERIAL PRIMARY KEY,
        symbol      TEXT NOT NULL,
        date        DATE NOT NULL,
        open        NUMERIC(12,4),
        high        NUMERIC(12,4),
        low         NUMERIC(12,4),
        close       NUMERIC(12,4),
        volume      BIGINT,
        UNIQUE(symbol, date)
      );
    `
  });
  results.push({ table: "foreign_etf_prices", error: e7?.message || null });

  const { error: e8 } = await supabase.rpc("exec_sql", {
    sql: `CREATE INDEX IF NOT EXISTS idx_etf_price_symbol_date ON foreign_etf_prices(symbol, date);`
  });

  // exchange_rates
  const { error: e9 } = await supabase.rpc("exec_sql", {
    sql: `
      CREATE TABLE IF NOT EXISTS exchange_rates (
        id          SERIAL PRIMARY KEY,
        base        TEXT NOT NULL,
        quote       TEXT NOT NULL DEFAULT 'TRY',
        rate        NUMERIC(12,4) NOT NULL,
        date        DATE NOT NULL,
        updated_at  TIMESTAMPTZ DEFAULT NOW(),
        UNIQUE(base, quote, date)
      );
    `
  });
  results.push({ table: "exchange_rates", error: e9?.message || null });

  return Response.json({ success: true, results });
}
