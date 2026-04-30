-- DZE fund_holdings corruption fix
-- Deletes rows where total_value > 1 quadrillion (likely parsing error from PDF)
-- Run in Supabase SQL Editor: https://supabase.com/dashboard/project/oqkobptbvcazifpvjwfz/sql

-- Step 1: See what will be deleted
SELECT fund_code, isin, total_value, company
FROM fund_holdings
WHERE fund_code = 'DZE'
  AND total_value > 1000000000000000;

-- Step 2: Delete corrupted rows
DELETE FROM fund_holdings
WHERE fund_code = 'DZE'
  AND total_value > 1000000000000000;

-- Step 3: Verify - should show 0 rows
SELECT COUNT(*) as corrupted_remaining
FROM fund_holdings
WHERE fund_code = 'DZE'
  AND total_value > 1000000000000000;
