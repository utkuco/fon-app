// Debug script: check actual DB values for Turkish gainers
const { createClient } = require('@supabase/supabase-js');

const supabase = createClient(
  process.env.SUPABASE_URL || 'https://oqkobptbvcazifpvjwfz.supabase.co',
  process.env.SUPABASE_SERVICE_ROLE_KEY || 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im9xa29iYXRidmNhemlmcHZqd2Z6Iiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTYzOTI1NjQyMCwiZXhwIjoxOTU0ODMyNDIsImp0aSI6ImQxOGUzMzQ0In0.ZG8j0sJtLxJ1JU7kYR4C7gKjLJdBbBV2e2L6SaLgLBY'
);

async function main() {
  // Check 5 random funds with their weekly/monthly values
  const { data: sample } = await supabase
    .from('funds')
    .select('code, name, weekly, monthly, return_1g, return_1h, return_1a, return_3a, return_6a, price, price_history')
    .limit(10);

  console.log('=== SAMPLE FUNDS (weekly/monthly columns) ===');
  for (const f of sample || []) {
    console.log(`\n${f.code} - ${f.name}`);
    console.log(`  weekly: ${JSON.stringify(f.weekly)}`);
    console.log(`  monthly: ${JSON.stringify(f.monthly)}`);
    console.log(`  return_1g: ${f.return_1g}`);
    console.log(`  return_1h: ${f.return_1h}`);
    console.log(`  return_1a: ${f.return_1a}`);
    console.log(`  return_3a: ${f.return_3a}`);
    console.log(`  return_6a: ${f.return_6a}`);
    console.log(`  price_history length: ${f.price_history?.length || 0}`);
  }

  // Count how many funds have null weekly/monthly
  const { count: nullWeekly } = await supabase
    .from('funds')
    .select('code', { count: 'exact', head: true })
    .is('monthly', null);
  const { count: notNullWeekly } = await supabase
    .from('funds')
    .select('code', { count: 'exact', head: true })
    .not('monthly', 'is', null);

  console.log(`\n=== monthly column stats ===`);
  console.log(`null monthly: ${nullWeekly}`);
  console.log(`non-null monthly: ${notNullWeekly}`);

  // Check a specific fund that has the bug (1H and 1A showing same value)
  // Let's look at funds with high monthly values
  const { data: highMonthly } = await supabase
    .from('funds')
    .select('code, name, weekly, monthly, return_1h, return_1a')
    .not('monthly', 'is', null)
    .gt('monthly', 0.5)
    .limit(10);
  
  console.log(`\n=== FUNDS WITH HIGH monthly (>50%) ===`);
  for (const f of highMonthly || []) {
    console.log(`${f.code}: monthly=${f.monthly}, weekly=${f.weekly}, return_1h=${f.return_1h}, return_1a=${f.return_1a}`);
  }

  // Check return_1h vs monthly for same funds
  const { data: compare } = await supabase
    .from('funds')
    .select('code, name, monthly, weekly, return_1h, return_1a')
    .not('monthly', 'is', null)
    .not('weekly', 'is', null)
    .limit(10);

  console.log(`\n=== COMPARISON: monthly vs weekly vs return_1h vs return_1a ===`);
  for (const f of compare || []) {
    console.log(`${f.code}: monthly=${f.monthly?.toFixed(4)}, weekly=${f.weekly?.toFixed(4)}, return_1h=${f.return_1h?.toFixed(4)}, return_1a=${f.return_1a?.toFixed(4)}`);
  }
}

main().catch(console.error);
