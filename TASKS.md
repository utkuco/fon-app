# TASKS — FonApp

## Done

- ETF sparkline backfill: x=0-280, y=0-40 formatına align et
- TEFAS scraper v2: undetected-chromedriver ile Cloudflare bypass
- Fund detail BetaAlphaCard: category_history guard (Apr 2026)
- homepage-stats-cron: price_history JSONB fetch removed (timeout fix)
- Admin layout: SiteNavbar/Footer gizleme for /admin routes
- Sparkline rendering: DB pre-scaled points (y=0-40) directly use et
- KAP portfolio parser: Zhipu GLM ile PDF parse pipeline
- ETF fiyat gösterimi: USD ($ prefix), getiri badge'leri TL etiketli (1A TL, 1G TL, Günlük (TL), Aylık (TL))
- Homepage: Tüm Varlıklar grid 20'ye çıkarıldı, blog posts 6'ya çıkarıldı
- Info notice: "Yabancı ETF getirileri TL cinsinden hesaplanır. Fiyatları USD'dir." — homepage'e eklendi
- Info notice: `/varliklar` sayfasına da eklendi (VarliklarListClient.tsx)
- Sort bar (TL): `/varliklar` sayfası "Günlük (TL)", "Aylık (TL)"
- **ETF TL return fix**: `exchange_rates` tablosu `(base, date)` PK ile historical FX korumaya başladı
  - DDL: `exchange_rates_pkey` → `(base, date)` primary key olarak değiştirildi
  - `etf-cron`: upsert key `"base"` → `"base,date"` (historical FX korunuyor)
  - `etf-returns-cron`: historical FX rate + doğru TL return formülü `((endPx*endFX)/(startPx*startFX))-1`
  - Build + Vercel deploy başarılı
- **FX historical backfill**: 198 gün USD/TRY + 197 gün EUR/TRY verisi `exchange_rates` tablosuna yazıldı
  - `scripts/fx_historical_backfill.py` ile Yahoo Finance'ten çekildi (yfinance)
  - Tarih aralığı: 2025-07-23 → 2026-04-28
  - PostgREST filter nota: `base` ve `quote` kolonları operatör olarak parse ediliyor — `select=date&base=eq.USD&quote=eq.TRY` kullan
- **Supabase DDL workflow**: README'ye eklendi, migration dosyası `web/supabase/migrations/` dizininde
- **README cron table**: vercel.json ile eşleşecek şekilde güncellendi (Mayıs 2026)

- **Kategori kartı historical returns FIX** (Mayıs 2026):
  - `homepage-stats-cron`: `computeCategoryStats()` — tek geçişte hem sparklines hem period returns
  - AUM-ağırlıklı ortalama: Son 30 gün fiyat serisi + 1H/1A/3A/6A gerçek historical getiriler
  - `category_stats` → `change_1d/change_1w/change_1m/change_3m/change_6m` (eskisi `avg_change` equal-weighted idi)
  - `CategoryTypeCards.tsx`: SAHTE `avgChange×mult` → gerçek `change_1m/change_3m/change_6m`
  - Her periyodun rengi kendi değerinin işaretine göre (yeşil/kırmızı)
  - Commit `10ddcb4`, Vercel deploy `proc_c6f78c14e03b`

## Backlog

### Yüksek Öncelik

- **KAP portfolio parser**: Zhipu GLM ile KAP PDF'lerinden portföy dağılımı çıkar
  - 507 PDF var, 102'si parse edildi, 405 bekliyor
  - Supabase management token 401 veriyor → yeni token gerekli
- **Supabase DDL**: Schema değişikliklerini management API ile uygula
  - Mevcut tablolar: funds, foreign_etfs, homepage_stats, vb.
  - SQL migrations yazılıp uygulanacak
- ~~**Kategori sparkline fix**: `category_sparklines` computation ekle~~
  - ~~Her kategori için Son 6Ay AUM-ağırlıklı ortalama getiri hesapla~~
  - ~~`homepage_stats` tablosuna yaz — cron çalıştığında update et~~

### Orta Öncelik

- **ETF category pages**: /varliklar/hisseler, /varliklar/tahvil, /varliklar/altin, /varliklar/gelismekte
  - Mevcut /varliklar sayfası çalışıyor, category routing eklenecek
- **Blog post content**: Türkçe finans içeriği üret
  - 71 içerik var (content_posts tablosu)
  - Aktif içerik üretimi + SEO optimize içerik planı

### Düşük Öncelik

- **SEO**: Fund/ETF sayfalarına JSON-LD structured data ekle
- **Fund detail BetaAlphaCard guard**: category_history olmayan ETF'ler için koruma
  - VOO (EQUITY/SRF) gibi ETF'ler ALTIN benchmark yerine doğru benchmark kullanmalı
