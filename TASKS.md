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

## In Progress

- Info notice: `/varliklar` sayfasına da aynı notice'i ekle (VarliklarListClient.tsx)

## Backlog

### Yüksek Öncelik

- **KAP portfolio parser**: Zhipu GLM ile KAP PDF'lerinden portföy dağılımı çıkar
  - 507 PDF var, 102'si parse edildi, 405 bekliyor
  - Supabase management token 401 veriyor → yeni token gerekli

- **Supabase DDL**: Schema değişikliklerini management API ile uygula
  - Mevcut tablolar: funds, foreign_etfs, homepage_stats, vb.
  - SQL migrations yazılıp uygulanacak

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
