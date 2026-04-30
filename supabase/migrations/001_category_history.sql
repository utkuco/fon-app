-- Category historical average price index
-- Calculated daily from all funds in each fund_type
CREATE TABLE IF NOT EXISTS category_history (
  id SERIAL PRIMARY KEY,
  date DATE NOT NULL,
  fund_type TEXT NOT NULL,
  avg_price_index NUMERIC,  -- normalized price index at period start = 100
  avg_return NUMERIC,       -- daily return %
  fund_count INTEGER,
  UNIQUE(date, fund_type)
);
