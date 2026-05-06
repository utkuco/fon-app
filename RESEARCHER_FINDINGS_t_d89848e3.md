# RESEARCHER FINDINGS
Task: t_d89848e3 — ETF 1A getiri tutarsızlığı — ×100 format ve 3 sparkline sistemi

## Root Cause

**Kodda tutarsızlık BULUNAMADI.** Tüm ETF `one_month_return_try` kullanım yerlerinde ×100 uygulanıyor. Tüm Türk fon `change_1m` kullanım yerlerinde ×100 uygulanmıyor (zaten %).

## 3 Bağımsız Sparkline/Veri Sistemi

### Pipeline 1 — Türk fon kartları (CategoryTypeCards "Türk Fonları" tabı)
- Kaynak: `funds.price_history` → `homepage-stats-lib.ts` → `homepage_stats` tablosu
- 1A/3A/6A: AUM-weighted period return, `change_1m` zaten % cinsinden
- **×100 YOK** (zaten %) ✓

### Pipeline 2 — ETF kartları (CategoryTypeCards "Yabancı ETF" tabı)
- Kaynak: `foreign_etfs.one_month_return_try` (RATIO,örn 1.27678=127.678%)
- Aggregation: AUM-weighted `weighted_1m = Σ(one_month_return_try × aum) / Σ(aum)` → RATIO formatında
- Display: `(w.m1 * 100).toFixed(1)%` → **×100 uygulanıyor** ✓
- `change_pct` için de aynı: `(w.change * 100).toFixed(2)%` ✓

### Pipeline 3 — Homepage karışık grid (HomePageClient)
- Kaynak: `foreign_etfs.one_month_return_try` → PureFundItem → FundCard
- ETF `monthly: one_month_return_try * 100` → **×100 uygulanıyor** ✓

### Pipeline 4 — ETF detay sayfası (EtfDetailClient)
- `oneMonthReturn={one_month_return_try * 100}` → **×100 uygulanıyor** ✓

### Pipeline 5 — GainersSection (En Çok Kazandıranlar)
- `getReturn()` ETF kolu: `entry.ret_1m * 100` → **×100 uygulanıyor** ✓

## ×100 Uygulanan Yerler (Tümü DOĞRU)
- `varliklar/page.tsx` line 113: `monthly: one_month_return_try * 100` ✓
- `HomePageClient.tsx` line 232: `monthly: one_month_return_try * 100` ✓
- `etf/[[...category]]/page.tsx` line 73: `quarterly: one_month_return_try * 100` ✓
- `EtfDetailClient.tsx` line 563: `oneMonthReturn: one_month_return_try * 100` ✓
- `gainers-section.tsx` line 57: `entry.ret_1m * 100` ✓

## ×100 UYGULANMAYAN Yerler (Tümü DOĞRU — zaten %)
- `homepage-stats-lib.ts` line 292: `change_1m: aum_weighted_1m / total_aum` (zaten %)
- `CategoryTypeCards.tsx` line 297: `stat.change_1m` → `toFixed(1)%` (Türk fonları)
- `etf-cascade-lib.ts` line 191: `ret = (latest.p / refPrice - 1) * 100` (zaten %, cascade'a yazılırken)

## Olası Gerçek Neden

**İki farklı hesaplama metodolojisi karşılaştırılıyor olabilir:**
- Detay sayfası = Yahoo Finance `one_month_return_try × 100` (dış veri kaynağı)
- Kategori kartları = `homepage-stats-lib.ts`'nin `funds.price_history`'dan kendi hesapladığı değer (farklı veri kaynağı ve metod)

Bu iki değer FARKLI olabilir ve bu bir UYGULAMA BUG'I DEĞİLDİR — farklı veri kaynakları ve hesaplama metodlarıdır.

## Potential Improvement

`homepage-stats-lib.ts` ETF category sparklines'ı `precomputed_etf_categories`'daki `avg_change_1m`'i (zaten % cinsinden, `etf-cascade-lib.ts` line 191'de hesaplanıyor) KULLANMIYOR. Şu an `homepage-stats-lib.ts` line 158'de `computeEtfCategorySparklines()` çağırıyor ama bu sadece sparkline points üretiyor, avg_change_* değerlerini kullanmıyor. ETF kartlarındaki 1A/3A/6A değerleri için `precomputed_etf_categories.avg_change_1m` kullanılabilir.

## Files Checked
1. `CategoryTypeCards.tsx` — ETF ×100 doğru, Türk fon ×100 yok (zaten %)
2. `etf/[[...category]]/page.tsx` — ×100 doğru
3. `EtfDetailClient.tsx` — ×100 doğru
4. `HomePageClient.tsx` — ×100 doğru
5. `varliklar/page.tsx` — ×100 doğru
6. `gainers-section.tsx` — ×100 doğru
7. `homepage-stats-lib.ts` — Türk fon (×100 yok), ETF sparklines precomputed'dan
8. `etf-cascade-lib.ts` — avg_change_1m zaten % cinsinden hesaplanıyor
9. `category-section.tsx` — prop geçişi doğru
10. `homepage-data.ts` — type tanımları doğru

## Recommendation
Kod değişikliği GEREKMİYOR. Eğer kullanıcı tutarsızlığı gerçekten görüyorsa, detay sayfası ve kategori kartları aynı veri kaynağını (`precomputed_etf_categories.avg_change_1m`) kullanmalı — şu an kategori kartları kendi hesaplama yapıyor.
