/**
 * ETF Sparkline Backfill Script
 * Fetches 2-year daily price history from Yahoo Finance for all ETFs in foreign_etfs table,
 * then computes sparkline data and stores it per ETF.
 * 
 * Usage: node scripts/etf_sparkline_backfill.js
 * Env: NEXT_PUBLIC_SUPABASE_URL, SUPABASE_SERVICE_KEY (or anon key)
 */

const yfinance = require('yfinance');
const { createClient } = require('@supabase/supabase-js');
const path = require('path');

// Load env
require('dotenv').config({ path: path.join(__dirname, '../web/.env.local') });

const SUPABASE_URL = process.env.NEXT_PUBLIC_SUPABASE_URL || 'https://oqkobptbvcazifpvjwfz.supabase.co';
const SUPABASE_KEY = process.env.SUPABASE_SERVICE_KEY || process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;

const BATCH_SIZE = 20;        // ETFs per batch
const RETRY_DELAY_MS = 500;   // delay between batches
const MAX_RETRIES = 2;

const supabase = createClient(SUPABASE_URL, SUPABASE_KEY);

async function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

async function fetchWithRetry(symbol, retries = MAX_RETRIES) {
  for (let attempt = 1; attempt <= retries; attempt++) {
    try {
      const ticker = yfinance.Ticker(symbol);
      const hist = await ticker.history({ period: '2y', interval: '1d' });
      return hist;
    } catch (err) {
      if (attempt === retries) throw err;
      await sleep(1000 * attempt);
    }
  }
}

async function processBatch(symbols) {
  const priceRows = [];
  
  for (const symbol of symbols) {
    try {
      const hist = await fetchWithRetry(symbol);
      if (!hist || !hist.length) continue;
      
      const rows = hist.map(d => ({
        symbol,
        date: new Date(d.date).toISOString().split('T')[0],
        open: d.open,
        high: d.high,
        low: d.low,
        close: d.close,
        volume: d.volume,
      }));
      priceRows.push(...rows);
      console.log(`  ✓ ${symbol}: ${rows.length} price rows`);
    } catch (err) {
      console.warn(`  ✗ ${symbol}: ${err.message}`);
    }
  }
  
  if (!priceRows.length) return;
  
  // Insert prices in sub-batches of 500
  for (let i = 0; i < priceRows.length; i += 500) {
    const chunk = priceRows.slice(i, i + 500);
    const { error } = await supabase
      .from('foreign_etf_prices')
      .upsert(chunk, { onConflict: 'symbol,date', ignoreDuplicates: true });
    if (error) console.error(`  upsert error: ${error.message}`);
  }
}

async function main() {
  console.log(`\nETF Sparkline Backfill starting...`);
  console.log(`  Supabase: ${SUPABASE_URL}`);
  console.log(`  Batch size: ${BATCH_SIZE}\n`);
  
  // Fetch all ETF symbols
  const { data: etfs, error } = await supabase
    .from('foreign_etfs')
    .select('symbol');
  
  if (error) { console.error('Failed to fetch ETFs:', error.message); return; }
  
  const symbols = etfs.map(r => r.symbol);
  console.log(`Found ${symbols.length} ETFs\n`);
  
  let processed = 0;
  let batches = Math.ceil(symbols.length / BATCH_SIZE);
  
  for (let i = 0; i < symbols.length; i += BATCH_SIZE) {
    const batch = symbols.slice(i, i + BATCH_SIZE);
    const batchNum = Math.floor(i / BATCH_SIZE) + 1;
    process.stdout.write(`[${batchNum}/${batches}] Fetching ${batch.join(', ')} ... `);
    
    await processBatch(batch);
    processed += batch.length;
    
    if (i + BATCH_SIZE < symbols.length) {
      await sleep(RETRY_DELAY_MS);
    }
  }
  
  console.log(`\n\n✅ Done! Processed ${processed}/${symbols.length} ETFs`);
  console.log(`\nSparkline data is now in foreign_etf_prices.`);
  console.log(`page.tsx will automatically compute sparklines on next request.`);
}

main().catch(console.error);
