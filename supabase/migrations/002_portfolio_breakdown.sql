-- Portfolio breakdown: asset allocation percentages per fund per report date
-- Upserted by kap_portfolio_parser.py (scripts/)
CREATE TABLE IF NOT EXISTS portfolio_breakdown (
  id SERIAL PRIMARY KEY,
  fund_code TEXT NOT NULL,
  report_date DATE NOT NULL,
  -- Asset allocation percentages (0-100 scale, e.g. 35.5 = 35.5%)
  stock_pct               NUMERIC,
  government_bond_pct     NUMERIC,
  private_bond_pct         NUMERIC,
  eurobond_pct            NUMERIC,
  treasury_bill_pct       NUMERIC,
  commercial_paper_pct    NUMERIC,
  bank_bill_pct           NUMERIC,
  gold_pct                NUMERIC,
  repo_pct                NUMERIC,
  reverse_repo_pct        NUMERIC,
  byf_pct                 NUMERIC,
  etf_pct                 NUMERIC,
  term_deposit_pct        NUMERIC,
  precious_metals_pct     NUMERIC,
  foreign_equity_pct      NUMERIC,
  foreign_bond_pct        NUMERIC,
  derivatives_pct         NUMERIC,
  participation_account_pct NUMERIC,
  kiracert_pct            NUMERIC,
  other_pct               NUMERIC,
  -- Totals
  total_pct               NUMERIC,
  fund_summary            TEXT,
  extraction_method       TEXT,
  ai_model                TEXT,
  ai_token_count          INTEGER,
  created_at              TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(fund_code, report_date)
);

CREATE INDEX IF NOT EXISTS idx_portfolio_breakdown_fund_code ON portfolio_breakdown(fund_code);
CREATE INDEX IF NOT EXISTS idx_portfolio_breakdown_report_date ON portfolio_breakdown(report_date);
