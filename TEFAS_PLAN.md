# Tefas Crawler + DB Migration Plan

## Tefas API Overview
- **Source:** fundturkey.com.tr (public API, no auth)
- **Endpoints:**
  - `POST /api/DB/BindHistoryInfo` → daily fund price/NAV, market cap, investor count
  - `POST /api/DB/BindHistoryAllocation` → portfolio breakdown by asset type (50+ categories)
- **Fund types:** YAT (securities), EMK (pension), BYF (ETF)
- **Daily crawl:** Tek tarih veya tarih aralığı çekilebilir

## New DB Schema

### funds (add columns)
```sql
ALTER TABLE funds ADD COLUMN price REAL;           -- Günlük fiyat/NAV
ALTER TABLE funds ADD COLUMN price_date TEXT;       -- Fiyat tarihi
ALTER TABLE funds ADD COLUMN market_cap REAL;       -- Portföy büyüklüğü (TL)
ALTER TABLE funds ADD COLUMN number_of_shares REAL; -- Tedavüldeki pay sayısı
ALTER TABLE funds ADD COLUMN number_of_investors REAL; -- Yatırımcı sayısı
ALTER TABLE funds ADD COLUMN daily_change REAL;     -- Günlük değişim %
ALTER TABLE funds ADD COLUMN tefas_title TEXT;      -- Tefas'taki tam ad
```

### NEW: price_history
```sql
CREATE TABLE price_history (
  id INTEGER PRIMARY KEY,
  fund_id INTEGER REFERENCES funds(id),
  date TEXT,
  price REAL,
  daily_change REAL,    -- %, positive or negative
  market_cap REAL,
  number_of_shares REAL,
  number_of_investors REAL,
  UNIQUE(fund_id, date)
);
```

### NEW: portfolio_breakdown (Tefas asset allocation)
```sql
CREATE TABLE portfolio_breakdown (
  id INTEGER PRIMARY KEY,
  fund_id INTEGER REFERENCES funds(id),
  date TEXT,
  -- Asset type percentages
  stock REAL,            -- HS: Hisse Senedi
  government_bond REAL,  -- DT: Devlet Tahvili
  private_sector_bond REAL, -- OST: Özel Sektör Tahvili
  eurobond REAL,         -- EUT: Eurobond
  gold REAL,              -- KM: Kıymetli Madenler
  repo REAL,              -- R: Repo
  reverse_repo REAL,      -- TR: Ters Repo
  treasury_bill REAL,     -- HB: Hazine Bonosu
  bank_bills REAL,        -- BB: Banka Bonosu
  commercial_paper REAL,  -- FB: Finansman Bonosu
  term_deposit REAL,      -- VM: Vadeli Mevduat
  foreign_equity REAL,    -- YHS: Yabancı Hisse
  foreign_bond REAL,      -- YBA: Yabancı Borçlanma
  etf REAL,               -- BYF: Borsa Yönetilen Fon
  derivatives REAL,       -- T: Türev Araçları
  precious_metals REAL,  -- KM: Kıymetli Madenler
  participation_account REAL, -- KH: Katılma Hesabı
  other REAL,             -- D: Diğer
  ...
  UNIQUE(fund_id, date)
);
```

## Crawler Script: tefas_crawler.py
- Install: `pip install tefas-crawler` veya direct requests
- Daily run: dünün tarihi ile crawl et
- Store in DB: upsert funds, price_history, portfolio_breakdown
- Error handling: rate limit → retry with backoff
- Cron: her gün gece 02:00'de çalışsın

## Homepage Redesign (Priority)

### Hero Section
- **Buy/Sell price** (büyük, bold) — en önemli veri
- Günlük değişim % (green/red badge)
- Toplam fon sayısı, toplam AUM (market cap sum), ortalama günlük değişim
- Son güncelleme zamanı

### Filter Bar
- Fund type (OKS, VFF, KFF, BYF, tümü)
- Yönetici
- Günlük değişim sıralaması (en çok artan, en çok düşen)
- AUM büyüklüğü

### Fund Card (Grid)
- Fon kodu + tam ad
- **Fiyat/NAV** (büyük, bold) — #1 veri
- Günlük değişim % (renkli badge)
- Fon tipi badge
- Portföy dağılımı mini bar (hisse%, tahvil%, diğer)
- Yönetici

### Sort Options
- Günlük değişim (en iyi / en kötü)
- AUM (büyüklük)
- Fiyat
- Hisse ağırlığı

## Fund Detail Page Redesign (Priority)

### Header
- Fon kodu + tam ad + fon tipi badge
- **NAV / Fiyat** (büyük) — #1 veri
- **Günlük değişim %** (green/red, büyük)
- Tarih
- Yönetici, ISIN, fon büyüklüğü, yatırımcı sayısı

### Price Chart
- Son 30/90/365 gün NAV grafiği
- Mini area chart

### Portfolio Breakdown (Tefas data!)
- **Asset type bars** (horizontal): Hisse, Tahvil, Altın, Repo, Diğer
- Her bar % olarak
- Tum asset kategorileri listesi

### Holdings (KAP/Gemini data — secondary)
- Sadece hisse senetleri tablosu
- Ticker, şirket, %, değer

### Comparison
- "Bu fonu hangi fonlar da tutuyor?" — en çok ortak holding

## Technical Notes
- Tefas data: günlük (her iş günü)
- KAP/Gemini data: haftalık (bildirimler)
- Fiyat = Tefas, Portföy dağılımı = Tefas (daha güncel), Holdings = KAP/Gemini
- Site static JSON: her gece rebuild + deploy (cron)
- data.json: fiyat + breakdown + holdings hepsi birleşik
