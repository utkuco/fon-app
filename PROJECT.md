# FonRapor.com — Proje Dökümanı
**Son Güncelleme:** 29 Nisan 2026

---

## Platform Hakkında

FonRapor.com, Türkiye'nin TEFAS ve KAP verilerini kullanan bağımsız bir yatırım fonu ve ETF analiz platformudur. Next.js (React) tabanlı SSR/SSG mimarisi, Supabase PostgreSQL veritabanı, Vercel serverless cron jobs.

**Site:** fonrapor.com (Türkçe arayüz, Türkçe içerik)

---

## Teknik Mimari

### Stack
- **Frontend:** Next.js 15 (App Router), React 19, TypeScript, Tailwind CSS v4
- **Backend:** Vercel Serverless Functions (cron jobs + API routes)
- **Database:** Supabase PostgreSQL
- **Styling:** CSS Variables (dark/light mode), shadcn/ui pattern
- **Deployment:** Vercel (web-brmfvldc6)

### Veritabanı Tabloları

| Tablo | Amaç | Anahtar Kolonlar |
|---|---|---|
| `funds` | Ana fon verisi (TEFAS'tan) | fund_id, name, fund_code, fund_type, currency, price, daily_change, benchmark_symbol, price_history (JSONB), weekly/monthly/quarterly_returns |
| `fund_metrics` | **Precomputed** risk metrikleri | fund_id, sharpe, sortino, calmar, beta, alpha, max_drawdown, annualized_return, annualized_volatility, downside_deviation, tracking_error, info_ratio, r_squared, updated_at |
| `homepage_stats` | **Precomputed** ana sayfa agregasyonları | fund_id, top funds by period, top gainers/losers, category rankings, sparkline (array) |
| `fund_category_ranks` | Kategori performans sıralamaları | category, period, fund_id, rank, metric_value |
| `foreign_etfs` | Yabancı ETF'ler (Yahoo Finance) | ticker, name, currency, category |
| `foreign_etf_prices` | ETF fiyat geçmişi | ticker, date, price, daily_change, weekly/monthly/quarterly_return, sparkline (array) |
| `benchmark_prices` | Endeks fiyatları (S&P500, NASDAQ, BIST100, Altın, USD/TRY) | symbol, date, close_price, daily_return |
| `system_rates` | Risksiz faiz oranları (USD T-bill, TRY, EUR) | currency, rate_annualized |
| `companies` | Fon yönetim şirketleri | code, name, logo_url, fund_count |
| `system_status` | Cron sağlık izleme | job_name, status, last_run, next_run |

### Cron Job Takvimi (Vercel)

| Cron | Zaman (UTC) | Zaman (TR) | İş |
|---|---|---|---|
| `risk-free-rates-cron` | 00:05 | 03:05 | USD T-bill → system_rates |
| `benchmark-prices-cron` | 00:10 | 03:10 | Yahoo → benchmark_prices |
| `homepage-stats-cron` | 00:30, 17:30 | 03:30, 20:30 | homepage_stats + category_ranks |
| `fund-metrics-cron` | 16:05 | 19:05 | Tüm metrikler (16 adet) |
| `etf-cron` | 17:00 | 20:00 | Yahoo → foreign_etf_prices |
| `etf-returns-cron` | 21:05 | 00:05 (+1) | ETF relative returns |

### Data Flow (Mevcut)

```
TEFAS (fundturkey.com.tr API)
  → LOCAL: tefas_crawler.py → SQLite db/fonapp.db (KAP portfolio holdings)
  → SUPABASE: funds tablosu (one-time backfill? — güncel değil!)
    → fund-cron (Vercel, /api/fund-cron, 13:00 UTC)
      → funds.price_history + daily_change + sparkline
      → fund_metrics (16 metrik: Sharpe/Sortino/Calmar/Beta/Alpha/MaxDD/etc.)
    → homepage-stats-cron (Vercel, /api/homepage-stats-cron, 00:30+17:30 UTC)
      → homepage_stats + fund_category_ranks

Yahoo Finance (Vercel)
  → benchmark-prices-cron (/api/benchmark-prices-cron, 00:10 UTC)
    → benchmark_prices
  → etf-cron (/api/etf-cron, 17:00 UTC)
    → foreign_etf_prices
  → etf-returns-cron (/api/etf-returns-cron, 21:05 UTC)
    → fund_metrics (ETF relative returns)
```

### KRİTİK AÇIK: TEFAS → Supabase Pipeline Eksik

`tefas_crawler.py` → LOCAL SQLite (`db/fonapp.db`) yazıyor.
Supabase `funds` tablosuna günlük veri yazan bir pipeline YOK.
`funds.price_history` Supabase'de güncellenmiyor → `fund-cron` çalışamaz.

**ÇÖZÜM GEREKLİ:** `scripts/tefas-to-supabase.js` + `/api/tefas-webhook` webhook sistemi.

---

## Bilinen Sorunlar (Site Analizi Raporu — 29 Nisan 2026)

### P0 — Kritik
1. **Dark mode başlangıç hatası:** Sistem dark mode'tayken tüm sayfalar siyah/okunamaz
2. **`/funds` 404:** Bu URL kırık, `/fon`'a yönlendirme gerekli
3. **TEFAS → Supabase pipeline eksik:** Günlük veri akışı yok

### P1 — SEO
4. **H1–H6 hiyerarşisi zayıf:** Ana sayfada sadece 1 H1, önemli bölümlerde başlık yok
5. **Blog schema eksik:** `BlogPosting`, `Article`, `Person` şeması yok
6. **`sameAs` boş:** Sosyal medya bağlantısı yok
7. **Başlıkta tarih:** `FonRapor — 2400 fon, 28.04.2026` — canonical sorunu
8. **Blog başlık tekrarı:** `Blog | FonRapor | FonRapor`
9. **Blog URL uyumsuzluğu:** İç link kırık

### P2 — UI/UX
10. **Footer boş:** Büyük siyah alan, içerik yok
11. **Navbar ikon erişilebilirlik:** Favoriler/karşılaştır sadece ikon, label yok
12. **Skeleton loading yok:** Soluk içerik görünüyor
13. **Performers sayfası:** H1/H2 yok
14. **Varlıklar pagination:** Yetersiz
15. **Mobil nav:** Hamburger menü yok
16. **İletişim sayfası:** Neredeyse boş
17. **PWA eksik:** Apple Touch Icon, Web Manifest yok

### P3 — İçerik
18. **Hakkımızda sayfası yok** (mevcut sayfa kontrol edilecek)
19. **Portföy dağılımı "veri yok" mesajı:** Kullanıcıya açıklama gerekli
20. **Blog içerik yetersiz:** Sadece 3–10 makale
21. **Sosyal medya tamamen yok**

---

## Kaynaklar

- **TEFAS Crawler:** `~/Desktop/projects/fon-app/tefas_crawler.py` (LOCAL SQLite için)
- **Supabase Admin:** `postgresql://postgres:rzvfO6ub5F1W6hpR@db.oqkobptbvcazifpvjwfz.supabase.co:5432/postgres`
- **API Scripts:** `~/Desktop/projects/fon-app/web/scripts/`
- **API Routes:** `~/Desktop/projects/fon-app/web/src/app/api/`
- **Frontend:** `~/Desktop/projects/fon-app/web/src/app/`
- **DB Schema Script:** `scripts/check_schema.js`
- **Metrics Backfill:** `scripts/backfill-fund-metrics-recompute.js`
- **Homepage Stats:** `scripts/compute-homepage-stats.ts`
- **Vercel Token:** `vcp_***` (Güvenlik nedeniyle gizli — ortam değişkeni olarak kullanılıyor)

---

## Environment Variables (Vercel)

```
NEXT_PUBLIC_SUPABASE_URL=https://xxx.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=eyJ...
SUPABASE_SERVICE_ROLE_KEY=eyJ...
CRON_API_KEY=cron_secret_utku
SB_SECRET_PkAEAOU2YO4YS-ELYpwS5w_SsVg2kqi
```
