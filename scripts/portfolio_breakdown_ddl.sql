-- Portfolio Breakdown DDL for Supabase
-- Run this in: Supabase Dashboard > SQL Editor > New Query

CREATE TABLE IF NOT EXISTS portfolio_breakdown (
    id              UUID        DEFAULT gen_random_uuid() PRIMARY KEY,
    fund_code       TEXT        NOT NULL,
    report_date     DATE        NOT NULL,
    published_at    TIMESTAMPTZ,
    
    -- Asset allocation percentages
    stock_pct           NUMERIC(6,2) DEFAULT 0,
    government_bond_pct NUMERIC(6,2) DEFAULT 0,
    private_bond_pct    NUMERIC(6,2) DEFAULT 0,
    eurobond_pct        NUMERIC(6,2) DEFAULT 0,
    treasury_bill_pct   NUMERIC(6,2) DEFAULT 0,
    commercial_paper_pct NUMERIC(6,2) DEFAULT 0,
    bank_bill_pct       NUMERIC(6,2) DEFAULT 0,
    gold_pct            NUMERIC(6,2) DEFAULT 0,
    repo_pct            NUMERIC(6,2) DEFAULT 0,
    reverse_repo_pct    NUMERIC(6,2) DEFAULT 0,
    byf_pct             NUMERIC(6,2) DEFAULT 0,
    etf_pct             NUMERIC(6,2) DEFAULT 0,
    term_deposit_pct    NUMERIC(6,2) DEFAULT 0,
    precious_metals_pct  NUMERIC(6,2) DEFAULT 0,
    foreign_equity_pct  NUMERIC(6,2) DEFAULT 0,
    foreign_bond_pct    NUMERIC(6,2) DEFAULT 0,
    derivatives_pct     NUMERIC(6,2) DEFAULT 0,
    participation_account_pct NUMERIC(6,2) DEFAULT 0,
    kiracert_pct        NUMERIC(6,2) DEFAULT 0,
    other_pct           NUMERIC(6,2) DEFAULT 0,
    total_pct           NUMERIC(7,2) DEFAULT 0,
    
    -- AI metadata
    ai_model            TEXT,
    ai_token_count      INTEGER,
    raw_text            TEXT,
    
    -- Timestamps
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    updated_at          TIMESTAMPTZ DEFAULT NOW(),
    
    -- Unique constraint: one record per fund per report date
    UNIQUE(fund_code, report_date)
);

-- Performance indexes
CREATE INDEX IF NOT EXISTS idx_pb_fund_code ON portfolio_breakdown(fund_code);
CREATE INDEX IF NOT EXISTS idx_pb_report_date ON portfolio_breakdown(report_date DESC);
CREATE INDEX IF NOT EXISTS idx_pb_fund_date ON portfolio_breakdown(fund_code, report_date DESC);

-- Row Level Security
ALTER TABLE portfolio_breakdown ENABLE ROW LEVEL SECURITY;

-- Policies: anyone can read, service role can insert/update
CREATE POLICY "Anyone can read" ON portfolio_breakdown FOR SELECT USING (true);
CREATE POLICY "Service can insert" ON portfolio_breakdown FOR INSERT WITH CHECK (true);
CREATE POLICY "Service can update" ON portfolio_breakdown FOR UPDATE USING (true);
