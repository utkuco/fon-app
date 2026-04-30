#!/usr/bin/env node
/**
 * tefas-webhook-cascade.js
 * 
 * Called by run_tefas_cron.sh AFTER tefas_scraper_v2.py completes successfully.
 * Triggers fund-cron and homepage-stats-cron on Vercel.
 * 
 * Usage: node tefas-webhook-cascade.js
 * 
 * The script:
 *  1. Waits 60s for TEFAS data to settle in DB
 *  2. Calls fund-cron (sparkline + daily_change recompute)
 *  3. Calls homepage-stats-cron (category rankings + homepage aggregates)
 * 
 * Both cron routes on Vercel require x-vercel-cron: true header.
 * We call them via the internal Vercel URL so the header is trusted.
 */

const WEB_APP_URL = process.env.WEB_APP_URL || 'https://web-brmfvldc6.vercel.app';
const CRON_SECRET = process.env.CRON_SECRET || 'cron_secret_utku';

async function triggerCron(path, label) {
  const url = `${WEB_APP_URL}${path}`;
  console.log(`[cascade] Triggering ${label}: ${url}`);
  
  try {
    const res = await fetch(url, {
      method: 'GET',
      headers: {
        'x-vercel-cron': 'true',
        'Authorization': `Bearer ${CRON_SECRET}`,
        'User-Agent': 'FonApp-TEFAS-Cascade/1.0',
      },
    });
    
    const text = await res.text();
    console.log(`[cascade] ${label} → ${res.status} in ${url}`);
    if (res.status !== 200) {
      console.error(`[cascade] ${label} FAILED: ${text.slice(0, 200)}`);
      return false;
    }
    return true;
  } catch (e) {
    console.error(`[cascade] ${label} ERROR: ${e.message}`);
    return false;
  }
}

async function main() {
  console.log(`[cascade] TEFAS cascade starting at ${new Date().toISOString()}`);
  
  // Step 1: Wait for TEFAS data to settle (scraper writes to DB, then we compute)
  console.log('[cascade] Waiting 60s for TEFAS data to settle in DB...');
  await new Promise(r => setTimeout(r, 60_000));
  
  // Step 2: Trigger fund-cron (computes sparkline + daily_change for all funds)
  const fundOk = await triggerCron('/api/fund-cron', 'fund-cron');
  
  // Step 3: Trigger homepage-stats-cron (computes homepage aggregates + category rankings)
  const homeOk = await triggerCron('/api/homepage-stats-cron', 'homepage-stats-cron');
  
  // Summary
  console.log('\n[cascade] === Cascade Complete ===');
  console.log(`[cascade] fund-cron:          ${fundOk ? '✓ OK' : '✗ FAILED'}`);
  console.log(`[cascade] homepage-stats-cron: ${homeOk ? '✓ OK' : '✗ FAILED'}`);
  
  if (!fundOk || !homeOk) {
    console.error('[cascade] WARNING: Some cron jobs failed. Check Vercel logs.');
    process.exit(1);
  }
  
  console.log('[cascade] All done. Homepage will reflect today\'s TEFAS data.');
  process.exit(0);
}

main().catch(e => {
  console.error('[cascade] Fatal:', e.message);
  process.exit(1);
});
