-- exchange_rates Historical Rates DDL
-- Run this ONCE via Supabase Dashboard SQL Editor or psql
-- Adds UNIQUE(base, date) constraint to preserve historical FX rates

BEGIN;

-- Step 1: Drop existing indexes on exchange_rates (including old unique constraint on 'base')
DO $$
DECLARE
  idx RECORD;
BEGIN
  FOR idx IN
    SELECT indexname FROM pg_indexes
    WHERE tablename = 'exchange_rates'
      AND schemaname = 'public'
  LOOP
    EXECUTE format('DROP INDEX IF EXISTS %I;', idx.indexname);
  END LOOP;
END
$$;

-- Step 2: Add composite unique constraint on (base, date)
ALTER TABLE exchange_rates
ADD CONSTRAINT exchange_rates_base_date_key UNIQUE (base, date);

COMMIT;

-- Verify:
-- SELECT * FROM exchange_rates ORDER BY base, date DESC LIMIT 20;
-- \d exchange_rates  (should show exchange_rates_base_date_key)
