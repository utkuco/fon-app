#!/usr/bin/env node
/**
 * Sync holdings from SQLite (with company names) to Supabase fund_holdings.
 * Replaces all existing holdings (with company column now added).
 */
const Database = require("better-sqlite3");
const { createClient } = require("@supabase/supabase-js");

const DB = "./db/fonapp.db";
const supabase = createClient(
  "https://oqkobptbvcazifpvjwfz.supabase.co",
  "sb_publishable__GPrsdfKRZCMZE8to916iQ_Izv9naG-"
);

async function main() {
  console.log("📂 Loading from SQLite...");
  const db = new Database(DB);

  const rows = db
    .prepare(
      `
    SELECT
      f.code as fund_code,
      h.ticker,
      h.isin,
      h.company,
      h.total_value
    FROM holdings h
    JOIN reports r ON r.id = h.report_id
    JOIN funds f ON f.id = r.fund_id
    WHERE f.code IS NOT NULL
      AND f.code NOT LIKE 'TEST%'
      AND h.isin IS NOT NULL
      AND h.isin != ''
      AND h.isin NOT LIKE 'TEST%'
      AND h.company IS NOT NULL
      AND h.company != ''
    ORDER BY f.code
  `
    )
    .all();

  console.log(`   Raw rows: ${rows.length}`);

  // Dedupe: keep one entry per fund_code+isin
  const seen = new Map();
  for (const h of rows) {
    const key = h.fund_code + "|" + (h.isin || "");
    if (!seen.has(key)) seen.set(key, h);
  }
  const unique = Array.from(seen.values());
  console.log(`   Unique: ${unique.length}`);

  const records = unique.map((h) => ({
    fund_code: h.fund_code,
    ticker: h.ticker || "",
    isin: h.isin || "",
    company: h.company || "",
    total_value: h.total_value || 0,
  }));

  console.log(`   Sample: ${JSON.stringify(records[0])}`);
  db.close();

  // Clear existing holdings
  console.log("\n🗑️  Clearing existing holdings...");
  const { error: deleteError } = await supabase
    .from("fund_holdings")
    .delete()
    .neq("fund_code", "___never_matches___");
  // Actually use a different approach - truncate via management API
  const mgmtRes = await fetch(
    "https://api.supabase.com/v1/projects/oqkobptbvcazifpvjwfz/database/query",
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: "Bearer sbp_9843b092bef7b9f182a07b59516c50f6dc421190",
      },
      body: JSON.stringify({ query: "DELETE FROM fund_holdings;" }),
    }
  );
  const mgmtData = await mgmtRes.json();
  console.log("   Delete result:", JSON.stringify(mgmtData));

  // Insert in batches of 100
  console.log(`\n🚀 Inserting ${records.length} records (batches of 100)...`);
  const batchSize = 100;
  let totalInserted = 0;
  let totalErrors = 0;

  for (let i = 0; i < records.length; i += batchSize) {
    const batch = records.slice(i, i + batchSize);
    const { data, error } = await supabase
      .from("fund_holdings")
      .insert(batch)
      .select();

    const batchNum = Math.floor(i / batchSize) + 1;
    const totalBatches = Math.ceil(records.length / batchSize);

    if (error) {
      totalErrors += batch.length;
      console.log(
        `   Batch ${batchNum}/${totalBatches}: ERROR — ${error.message.slice(0, 80)}`
      );
    } else {
      totalInserted += data?.length || 0;
      if (batchNum % 10 === 0 || batchNum === totalBatches) {
        console.log(
          `   Batch ${batchNum}/${totalBatches}: OK (${data?.length} inserted)`
        );
      }
    }
  }

  console.log("\n" + "=".repeat(60));
  console.log(
    `✅ Done! Inserted: ${totalInserted}, Errors: ${totalErrors}`
  );
  console.log("=".repeat(60));

  // Verify
  const { count } = await supabase
    .from("fund_holdings")
    .select("*", { count: "exact", head: true });
  console.log(`📊 Supabase fund_holdings count: ${count}`);
}

main().catch((e) => {
  console.error("Fatal:", e);
  process.exit(1);
});
