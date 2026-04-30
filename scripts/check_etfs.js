const { createClient } = require('@supabase/supabase-js');

const sb = createClient(
  'https://oqkobptbvcazifpvjwfz.supabase.co',
  'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im9xa29icHRidmNhemlmcHZqd2Z6Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3MzUwNjQ0MTYsImV4cCI6MjA1MDY0MDQxNn0.Z6E9RXYmiRiFeVwbLCqGxNqL3rK0Qv8d9x9'
);

async function main() {
  // Check foreign_etfs count
  const { count } = await sb.from('foreign_etfs').select('*', { count: 'exact', head: true });
  console.log('foreign_etfs count:', count);
  
  // Check foreign_etf_prices count
  const { count: priceCount } = await sb.from('foreign_etf_prices').select('*', { count: 'exact', head: true });
  console.log('foreign_etf_prices count:', priceCount);
  
  // Sample 5 ETFs with prices
  const { data } = await sb
    .from('foreign_etfs')
    .select('symbol, name, aum, one_month_return_try')
    .eq('is_active', true)
    .order('aum', { ascending: false, nullsFirst: false })
    .limit(5);
  console.log('Sample ETFs:', JSON.stringify(data, null, 2));
  
  // Check how many ETFs have price data
  const { data: priceSamples } = await sb
    .from('foreign_etf_prices')
    .select('symbol')
    .limit(5);
  console.log('Price samples:', JSON.stringify(priceSamples));
}
main().catch(console.error);
