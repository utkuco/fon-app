-- ================================================================
-- FonApp: portfolio_breakdown table
-- Portföy dağılımı: her fon için aylık varlık sınıfı yüzdeleri
-- KAP Portföy Dağılım Raporları'ndan AI ile çıkarılacak
-- ================================================================

CREATE TABLE IF NOT EXISTS portfolio_breakdown (
    id              UUID        DEFAULT gen_random_uuid() PRIMARY KEY,
    fund_code       TEXT        NOT NULL,
    report_date     DATE        NOT NULL,          -- Portföy dönemi (ayın sonu)
    published_at    TIMESTAMPTZ,                   -- KAP'ta yayınlanma tarihi
    
    -- Varlık sınıfları (yüzde olarak, 0-100 arası)
    stock_pct           NUMERIC(6,2),   -- Hisse senedi
    government_bond_pct NUMERIC(6,2),   -- Devlet tahvili (DİBS)
    private_bond_pct    NUMERIC(6,2),   -- Özel sektör tahvili
    eurobond_pct        NUMERIC(6,2),   -- Eurobond
    treasury_bill_pct   NUMERIC(6,2),   -- Hazine bonnosu
    commercial_paper_pct NUMERIC(6,2),  -- Finansman bonnosu
    bank_bill_pct       NUMERIC(6,2),   -- Banka bonnosu
    gold_pct            NUMERIC(6,2),   -- Altın ve diğer kıymetli madenler
    repo_pct            NUMERIC(6,2),   -- Repo
    reverse_repo_pct    NUMERIC(6,2),   -- Ters repo
    byf_pct             NUMERIC(6,2),   -- Borsa yatırım fonları
    etf_pct             NUMERIC(6,2),   -- Exchange traded funds
    term_deposit_pct   NUMERIC(6,2),   -- Vadeli mevduat
    precious_metals_pct NUMERIC(6,2),   -- Kıymetli madenler (altın dışında)
    foreign_equity_pct  NUMERIC(6,2),   -- Yabancı hisse senedi
    foreign_bond_pct    NUMERIC(6,2),   -- Yabancı borçlanma araçları
    derivatives_pct     NUMERIC(6,2),   -- Türev araçları
    participation_account_pct NUMERIC(6,2), -- Katılım hesabı
    kiracert_pct        NUMERIC(6,2),   -- Kira sertifikası
    other_pct           NUMERIC(6,2),   -- Diğer
    
    -- Toplam kontrol (tüm yüzdeler toplamı ~100 olmalı)
    total_pct           NUMERIC(7,2),
    
    -- AI metadata
    ai_model        TEXT,
    ai_token_count  INTEGER,
    raw_text        TEXT,    -- Ham AI çıktısı (debugging)
    
    -- Unique constraint
    UNIQUE(fund_code, report_date),
    
    -- Otomatik zamanlar
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

-- Indexler
CREATE INDEX IF NOT EXISTS idx_pb_fund_code     ON portfolio_breakdown(fund_code);
CREATE INDEX IF NOT EXISTS idx_pb_report_date  ON portfolio_breakdown(report_date DESC);
CREATE INDEX IF NOT EXISTS idx_pb_fund_date    ON portfolio_breakdown(fund_code, report_date DESC);

-- RLS
ALTER TABLE portfolio_breakdown ENABLE ROW LEVEL SECURITY;

-- Herkes okuyabilir, sadece service role yazabilir
CREATE POLICY "Anyone can read" ON portfolio_breakdown
    FOR SELECT USING (true);

CREATE POLICY "Service role can insert/update" ON portfolio_breakdown
    FOR INSERT WITH CHECK (true);

CREATE POLICY "Service role can update" ON portfolio_breakdown
    FOR UPDATE USING (true);

COMMENT ON TABLE portfolio_breakdown IS 
'E-Tower KAP portföy dağılım verileri. AI (GLM) ile KAP PDFlerinden çıkarılmıştır.';
