# TASKS — FonApp / FonRapor — Anasayfa Sadeleştirme

## Active Goal
Anasayfayı sadeleştir + ETF category sparkline ekle

## ✅ Bugün yapılan

### Kategori birleştirme
- `CategoryTypeCards.tsx` → iki ayrı grid tek kart + tab bar ("Türk Fonları | Yabancı ETF")
- FunLists → "En Büyük Fonlar" section kaldırıldı

### ETF "Diğer" sorunu
- `ASSET_TYPE_FALLBACK` mapping (65+ asset_type → 5 kategori)
- DIGER_THRESHOLD = 100

### ETF category sparkline (YENİ)
- `scripts/compute-etf-sparklines.mjs` oluşturuldu
- DB'ye 5 ETF category sparkline kaydedildi: SP500, NASDAQ, DUNYA, ALTIN, TAHVIL
- Kaynak: `foreign_etf_prices` tablosu (SPY, IVV, VOO, QQQ, VTI, VEA, VWO, EFA, GLD, SLV, BND, AGG, TLT, LQD)
- `CategoryTypeCards.tsx` → ETF kartlarında sparkline gösterimi ("SON 6 AY" etiketi + 48px SVG)

### Route düzeltmesi
- `[symbol]` + `[[...category]]` route çakışması çözüldü
- `[[...category]]/page.tsx` artık hem category hem individual ETF handle ediyor
- `/etf/sp500`, `/etf/nasdaq`, `/etf/dunya`, `/etf/SPY` hepsi çalışıyor

## 📊 DB Durumu
- `homepage_stats.category_sparklines`: 11 sparkline (önceden 7 Türk fon + 5 ETF = 12... aslında overlap olabilir)
  - Türk: BYF, KFF, OKS, SRF, VFF, ALTIN, DÖVİZ
  - ETF: SP500, NASDAQ, DUNYA, ALTIN, TAHVIL
- `foreign_etf_prices`: 4 ETF (SPY, IVV, VOO, QQQ) — 251 günlük veri

## ✅ Return Hesaplaması (BUGÜN - 22 Nisan 2026)
- `compute_returns_yf.py` scripti düzeltildi: `and=(...)` syntax → `column=is.null` + offset pagination
- 164 eksik ETF için return hesaplandı → **159 başarılı, 5 skipped**
- Son durum: **1171/1176 ETF** dönüş verisi mevcut (99.6%)
- 5 eksik: CWY, DGAP, CBOX, MUYY, ORBX (yfinance'de veri yok)
- DB: `foreign_etfs.one_month_return_try`, `three_month_return_try`, `six_month_return_try`
