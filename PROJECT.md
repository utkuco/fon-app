# FonRapor.com — Proje Dökümanı
**Son Güncelleme:** 30 Nisan 2026

---

## Platform Hakkında

FonRapor.com, Türkiye'nin TEFAS ve KAP verilerini kullanan bağımsız bir yatırım fonu ve ETF analiz platformudur. Next.js (React) tabanlı SSR/SSG mimarisi, Supabase PostgreSQL veritabanı, Vercel serverless cron jobs.

**Site:** fonrapor.com
**Veritabanı:** Supabase PostgreSQL — `postgresql://postgres:rzvfO6ub5F1W6hpR@db.oqkobptbvcazifpvjwfz.supabase.co:5432/postgres`

---

## Cron Job Takvimi

### Yerel Mac (launchd) — Otomatik

| Job | Zaman | Interval | Komut | Log |
|---|---|---|---|---|
| `com.fonapp.tefas-daily-cron` | Her gün 10:00 TR | launchd (daily) | `tefas_scraper_v2.py` → TEFAS fiyatları | `logs/tefas.log` |
| `com.fonapp.tefas-health` | Her gün 11:00 TR | launchd (daily) | `health_check.py` → DB sağlık | `logs/health_check.log` |
| `com.fonapp.fund-metadata` | Her gün 11:30 TR | **48 saat (2 gün)** | `fetch_fund_metadata.py` → FonBilgiGetir | `logs/metadata.log` |
| `com.fonapp.etf-daily-cron` | 22:00, 01:00, 04:00, 07:00, 10:00 TR | 5× launchd | `etf_daily_cron.py` → yfinance | `logs/etf.log` |

**launchd plist konumu:** `~/Desktop/projects/fon-app/com.fonapp.*.plist`
**Çalıştırmak için:** `sudo launchctl load /Users/admin/Desktop/projects/fon-app/com.fonapp.fund-metadata.plist`

### Vercel (Serverless Cron)

| Cron | Zaman (UTC) | Zaman (TR) | İş |
|---|---|---|---|
| `risk-free-rates-cron` | 00:05 | 03:05 | USD T-bill → system_rates |
| `benchmark-prices-cron` | 00:10 | 03:10 | Yahoo → benchmark_prices |
| `homepage-stats-cron` | 14:00, 23:30 | 17:00, 02:30 | homepage_stats + category_ranks |
| `fund-metrics-cron` | 05:13 | 08:13 | Tüm metrikler (16 adet) |
| `etf-cron` | 13:00 | 16:00 | yfinance → foreign_etf_prices |
| `etf-cascade` | 21:30 | 00:30 (+1) | precomputed_etf_categories |
| `fund-cron` | 13:00 | 16:00 | TEFAS → funds tablosu |
| `tefas-cascade` | 15:00 | 18:00 | fund_metrics → companies → homepage_stats |

---

## TEFAS API'leri

### 1. `fonFiyatBilgiGetir` — Fiyat Geçmişi
**Kullanım:** Her gün 10:00 TR (tefas_scraper_v2.py)
**Endpoint:** `POST https://www.tefas.gov.tr/api/funds/fonFiyatBilgiGetir`
**Payload:** `{"fonKodu": "OGD", "dil": "TR", "periyod": 60}`
**periyod değerleri:** `60`=5yıl, `90`=3yıl, `180`=18ay, `365`=1yıl
**Rate limit:** ~200ms/isteğin, 2400 fon ≈ 8 dk

**Döndürdükleri:**
| API Alanı | DB Kolonu | Açıklama |
|---|---|---|
| `tarih` + `fiyat` | `price_history` (JSONB) | Fiyat geçmişi |
| `fiyat` (son satır) | `price` | Son güncellenmiş fiyat |
| `fiyat` (son-1 satır) | `daily_change` | Günlük değişim % |
| `fonUnvan` | `name` | Fon adı |
| `kategoriDerece` | `category_rank` | Kategori sırası |
| `kategoriFonSay` | `category_fund_count` | Kategori fon sayısı |

### 2. `FonBilgiGetir` — Fon Metadata
**Kullanım:** Her 2 günde bir 11:30 TR (fetch_fund_metadata.py)
**Endpoint:** `POST https://www.tefas.gov.tr/api/funds/FonBilgiGetir`
**Payload:** `{"fonKodu": "OGD", "dil": "TR"}`
**Rate limit:** ~250ms/isteğin, 2400 fon ≈ 10 dk

**Döndürdükleri:**
| API Alanı | DB Kolonu | Açıklama |
|---|---|---|
| `portBuyukluk` | `market_cap` | Portföy büyüklüğü (TL) |
| `payAdet` | `pay_adet` | Pay adedi |
| `yatirimciSayi` | `num_investors` | Yatırımcı sayısı |
| `pazarPayi` | `market_share` | Pazar payı (%) |
| `gunlukGetiri` | `daily_return` | Günlük getiri (%) |
| `fonKategori` | `fund_category` | TEFAS kategori adı |
| `kategoriDerece` | `category_rank` | Kategorisindeki sıra |
| `kategoriFonSay` | `category_fund_count` | Kategori fon sayısı |
| `fonUnvan` | `name` | Fon adı |

---

## Veritabanı Tabloları

### `funds` — Ana Fon Tablosu

| Kolon | Tip | Kaynak | Açıklama |
|---|---|---|---|
| `code` | text PK | TEFAS | Fon kodu (OGD, RDH...) |
| `name` | text | fonFiyatBilgiGetir | Fon adı |
| `fund_type` | text | isimden inferred | SRF/VFF/OKS/ALTIN... |
| `price` | numeric | fonFiyatBilgiGetir | Son fiyat (TL) |
| `daily_change` | numeric | fonFiyatBilgiGetir | Günlük değişim % |
| `price_history` | jsonb | fonFiyatBilgiGetir | `[{"date":"2026-04-30","price":11.57,"change":null}]` |
| `market_cap` | numeric | FonBilgiGetir | Portföy büyüklüğü (TL) |
| `num_investors` | numeric | FonBilgiGetir | Yatırımcı sayısı |
| `pay_adet` | numeric | FonBilgiGetir | Pay adedi |
| `market_share` | numeric | FonBilgiGetir | Pazar payı % |
| `daily_return` | numeric | FonBilgiGetir | Günlük getiri % |
| `fund_category` | text | FonBilgiGetir | TEFAS kategori adı |
| `category_rank` | integer | fonFiyatBilgiGetir | Kategorisindeki sıra |
| `category_fund_count` | integer | fonFiyatBilgiGetir | Kategori fon sayısı |
| `management_fee` | numeric | Eski (Ocak 2026, stale) | Yönetim ücreti % |
| `weekly` | jsonb | Cascade | Haftalık getiri % |
| `monthly` | jsonb | Cascade | Aylık getiri % |
| `quarterly` | jsonb | Cascade | 3 aylık getiri % |
| `returns` | jsonb | Cascade | Tüm periyotlar |
| `breakdown` | jsonb | Cascade | Varlık dağılımı |
| `purchase_valor` | integer | Eski | Satın alma valörü (gün) |
| `sale_valor` | integer | Eski | Satış valörü (gün) |
| `company_id` | integer FK | Cascade | Yönetim şirketi |

---

## Data Flow (Güncel)

```
[HER GÜN 10:00 TR — com.fonapp.tefas-daily-cron]
tefas_scraper_v2.py (Chrome CDP yok, sadece requests + fonFiyatBilgiGetir)
    └── Direct psycopg2 writes → funds.price_history, name, daily_change
    └── curl https://fonrapor.com/api/tefas-cascade
    └── health_check.py

[HER GÜN 11:30 TR (2 günde 1) — com.fonapp.fund-metadata]
fetch_fund_metadata.py
    └── Direct psycopg2 writes → funds.market_cap, num_investors, pay_adet,
                                  market_share, daily_return, fund_category,
                                  category_rank, category_fund_count, name

[HER GÜN 11:00 TR — com.fonapp.tefas-health]
health_check.py → DB sağlık kontrolü
    ├── Fiyat son 5 gün mü?
    ├── TEFAS fetch count ≥2000?
    ├── fund_metrics güncel mi?
    └── Homepage stats tablosu dolu mu?

[HER GÜN 15:00 UTC (18:00 TR) — Vercel /api/tefas-cascade]
Step 1: computeFundCronMetrics() → fund_metrics
Step 2: syncCompanies() → companies
Step 3: computeHomepageStats() → homepage_stats

[HER GÜN 14:00 + 23:30 UTC — Vercel /homepage-stats-cron]
computeHomepageStats() → homepage_stats

[HER GÜN 21:30 UTC — Vercel /etf-cascade]
precomputed_etf_categories → ETF sparkline'ları
```

---

## Önemli Notlar

- **Supabase direct connection:** `psycopg2` ile direkt yazıyoruz (Supabase PostgREST API timeout issue — Nisan 2026'da düzeltildi)
- **TEFAS API rate limit:** ~200-250ms/isteğin — 2400 fon ≈ 8-10 dk
- **price_history format:** Python list → JSONB. `{"date": "2026-04-30", "price": 11.57, "change": null}` — ISO YYYY-MM-DD
- **FonBilgiGetir** = tam fon bilgisi (AUM, investor count, pazar payı). **Sadece 2 günde 1 güncellenir** (değişmez çabuk)
- **Vercel serverless:** TCP 5432 bağlantısı yok → Supabase PostgREST (HTTPS/443) şart
- **PG numeric tipi:** JavaScript'te string olarak gelir → `Number(r.rate_annualized)` gerekli

---

## Bilinen Sorunlar

### Düzeltilenler ✅
- **TEFAS pipeline** — psycopg2 direct writes, artık timeout yok
- **homepage_stats.latest_date** — price_history'den gelen tarih
- **Tüm 2400 fon güncel** — 30 Nisan 2026
- **ORDER BY timeout** — Supabase PostgREST'te sort UI'da yapılıyor
- **FonBilgiGetir API** — market_cap, num_investors, fund_category, category_rank eklendi

### Bekleyen
- **SP500 sparkline 0** — precomputed_etf_categories SP500 0 puan
- **Footer boş** — Site footer'ı doldurulacak
- **Skeleton loading yok** — Fon listesi/detay sayfası
- **Blog schema eksik** — SEO için Schema.org ekle
- **Mobil hamburger menu** — SiteNavbar

---

## Dosya Yolları

| Dosya | Konum |
|---|---|
| TEFAS scraper | `~/Desktop/projects/fon-app/tefas_scraper_v2.py` |
| Metadata fetch | `~/Desktop/projects/fon-app/scripts/fetch_fund_metadata.py` |
| Health check | `~/Desktop/projects/fon-app/scripts/health_check.py` |
| Cascade (Vercel) | `~/Desktop/projects/fon-app/web/src/app/api/tefas-cascade/route.ts` |
| Homepage stats | `~/Desktop/projects/fon-app/web/src/app/api/homepage-stats-cron/route.ts` |
| ETF cascade | `~/Desktop/projects/fon-app/web/src/app/api/etf-cascade/route.ts` |
| Launchd plists | `~/Desktop/projects/fon-app/com.fonapp.*.plist` |
| Cron logları | `~/Desktop/projects/fon-app/logs/` |
| Vercel token | `<VERCEL_TOKEN>` |
