# FonRapor.com — Görev Listesi
**Son Güncelleme:** 30 Nisan 2026

---

## Mevcut Pipeline Durumu

```
[YEREL MAC — her gün 10:00 TR (08:00 UTC, 1-7)]
com.fonapp.tefas-daily-cron.plist (launchd)
    caffeinate -s -m -i
    └── run_tefas_cron.sh
            ├── Chrome CDP → tefas_scraper_v2.py (TEFAS → funds.price_history + name)
            ├── curl /api/tefas-cascade (Vercel cascade)
            └── health_check.py (→ logs/health_check.log)

[YEREL MAC — isteğe bağlı, her 2 gün (00:00 UTC)]
com.fonapp.fund-metadata.plist (launchd)
    └── fetch_fund_metadata.py (TEFAS FonBilgiGetir API → funds tablosuna metadata)

[YEREL MAC — her gün 11:00 TR (08:00 UTC, 1-7)]
com.fonapp.health-check.plist (launchd)
    └── health_check.py → fonrapor.com DB sağlık kontrolü

[VERCEL — her iş günü 10:00 TR = 07:00 UTC]
risk-free-rates-cron
    └── Gecelik risk-free faiz oranları (TR faiz eğrisi) — Yahoo Finance

[VERCEL — her iş günü 10:30 TR = 07:30 UTC]
benchmark-prices-cron
    └── ^GSPC, ^IXIC, GC=F, TRY=X, ^IRX — 30 gün Yahoo Finance → benchmark_prices tablosu

[VERCEL — her iş günü 10:45 TR = 07:45 UTC]
homepage-stats-cron (1. run — sabah)
    └── computeHomepageStats() — kategori sparkline + returns → homepage_stats

[VERCEL — her iş günü 11:00 TR = 08:00 UTC]
fund-metrics-cron
    └── Sharpe, Sortino, Beta, Alpha, MaxDrawdown, Volatility — benchmark_prices'tan okur

[VERCEL — her iş günü 11:15 TR = 08:15 UTC]
fund-cron
    └── funds.price_history okur, daily_change + sparkline hesaplar

[VERCEL — her iş günü 11:30 TR = 08:30 UTC]
tefas-cascade
    ├── Step 1: computeFundCronMetrics() → fund_metrics
    ├── Step 2: syncCompanies() → companies
    └── Step 3: computeHomepageStats() → homepage_stats

[VERCEL — her iş günü 22:00 TR = 19:00 UTC]
homepage-stats-cron (2. run — akşam)
    └── computeHomepageStats() — kategori sparkline + returns

[YEREL MAC — her gün 22:00 TR (19:00 UTC, 1-7)]
com.fonapp.etf-daily-cron.plist (launchd)
    └── etf_daily_cron.py (yfinance → foreign_etf_prices)

[VERCEL — her iş günü 23:00 TR = 20:00 UTC]
etf-cron
    └── Yabancı ETF fiyat serileri + category_history — Yahoo Finance HTTP

[VERCEL — her iş günü 23:30 TR = 20:30 UTC]
etf-returns-cron
    └── ETF 1Y/3Y/5Y return hesaplamaları + FX kuru

[VERCEL — her iş günü 23:45 TR = 20:45 UTC]
etf-cascade
    └── ETF category hisseleri ve detay hesaplamaları → precomputed_etf_categories
```

---

## Health Check Sistemi

**Script:** `~/Desktop/projects/fon-app/scripts/health_check.py`
**Log:** `~/Desktop/projects/fon-app/logs/health_check.log`
**Launchd:** `com.fonapp.health-check` — her gün 11:00 TR

**Kontroller:**
| Check | OK | WARNING | ERROR |
|---|---|---|---|
| Fund prices | Tüm fonlar son 2 gün | — | >3 gün eski |
| TEFAS fetch count | Bugün ≥2000 fon fetch | — | <2000 fon |
| Fund metrics | ≥2300 güncel | — | Boş veya 3+ gün eski |
| Homepage stats | Tablo dolu | — | Boş |
| ETF prices | ≥30% tickers 2d | 10-30% tickers | <10% tickers |
| ETF categories | Tüm kategoriler taze | — | Hepsi eski |

**Exit:** 0=OK, 1=WARNING, 2=ERROR

---

## TEFAS API'leri

### 1. `fonFiyatBilgiGetir` — Fiyat geçmişi (her gün, fiyat scraper)
```
POST https://www.tefas.gov.tr/api/funds/fonFiyatBilgiGetir
Payload: {"fonKodu": "OGD", "dil": "TR", "periyod": 60}
Returns: fonKodu, fonUnvan, kategoriDerece, kategoriFonSay, tarih, fiyat
Kullanım: price_history, latest_price, daily_change, name, category_rank, category_fund_count
```

### 2. `FonBilgiGetir` — Fon metadata (haftada 1 veya gerektiğinde)
```
POST https://www.tefas.gov.tr/api/funds/FonBilgiGetir
Payload: {"fonKodu": "OGD", "dil": "TR"}
Returns: portBuyukluk(TL), payAdet, yatirimciSayi, pazarPayi(%), gunlukGetiri(%),
         fonKategori, kategoriDerece, kategoriFonSay, fonUnvan
Kullanım: market_cap, num_investors, pay_adet, market_share, daily_return,
          fund_category, category_rank, category_fund_count, name
```

---

## DB Kolonları — funds tablosu (Tam Liste)

| Kolon | Kaynak | Açıklama |
|---|---|---|
| `price_history` | fonFiyatBilgiGetir | Fiyat geçmişi (JSONB) |
| `price` | fonFiyatBilgiGetir | Son fiyat |
| `daily_change` | fonFiyatBilgiGetir | Günlük değişim % |
| `name` | fonFiyatBilgiGetir.fonUnvan | Fon adı |
| `market_cap` | FonBilgiGetir.portBuyukluk | Portföy büyüklüğü (TL) |
| `num_investors` | FonBilgiGetir.yatirimciSayi | Yatırımcı sayısı |
| `pay_adet` | FonBilgiGetir.payAdet | Pay adedi |
| `market_share` | FonBilgiGetir.pazarPayi | Pazar payı (%) |
| `daily_return` | FonBilgiGetir.gunlukGetiri | Günlük getiri (%) |
| `fund_category` | FonBilgiGetir.fonKategori | TEFAS kategori adı |
| `category_rank` | fonFiyatBilgiGetir + FonBilgiGetir | Kategorisindeki sıra |
| `category_fund_count` | fonFiyatBilgiGetir + FonBilgiGetir | Kategorideki fon sayısı |
| `management_fee` | Eski Selenium scrape (stale) | Yönetim ücreti |
| `fund_type` | isimden inferred (guess_type) | Fon tipi (SRF/VFF/OKS/ALTIN...) |

---

## Done ✅

### P0 — Kritik Altyapı

- [x] **TEFAS cron çalışıyor** — 2400 fon, launchd + caffeinate, her gün 10:00 TR
- [x] **homepage_stats.latest_date bug** — new Date() yerine gerçek price_history tarihi
- [x] **Cascade 200 OK** — 2,389 fon 3dk'da işleniyor
- [x] **ORDER BY timeout** — Supabase PostgREST + Vercel serverless'ta ORDER BY timeout → UI'da sort et
- [x] **foreign_etfs index'leri** — is_active + aum index'leri eklendi
- [x] **Tüm 2400 Türk fonu güncel** (30 Nisan 2026) — psycopg2 direct writes
- [x] **Health check sistemi** — scripts/health_check.py, her gün 11:00 TR
- [x] **TEFAS scraper sadeleştirildi** — 3 API çağrısı → 1 API çağrısı (periyod=60)
- [x] **fetch_price_history returns metadata** — returns (price_rows, meta) tuple
- [x] **scrape_fund extracts name** — meta["name"] → upsert_funds'e veriliyor
- [x] **TEFAS FonBilgiGetir API keşfedildi** — market_cap, num_investors, pay_adet, market_share, daily_return, fund_category, category_rank, category_fund_count
- [x] **fetch_fund_metadata.py yazıldı** — 2400 fonu FonBilgiGetir'den çeker (tek seferlik)
- [x] **DB kolonları eklendi** — pay_adet, num_investors, market_share, daily_return, fund_category, category_rank, category_fund_count
- [x] **Fon detay sayfası güncellendi** — StatCard'lara 3 yeni kart: Pazar Payı, Kategori Sırası, TEFAS Kategorisi
- [x] **Deploy** — fonrapor.com (web-brmfvldc6)
- [x] **Kategori period returns düzeltildi** (30 Nisan 2026) — AUM-ağırlıklı 1H/1A/3A/6A hesaplaması eklendi. latestDate gerçek price_history'den alınıyor. MAX_ABS_RETURN=50 outlier threshold. Deploy: 3bae9c0.
- [x] **VFF sparkline düzeltildi** (30 Nisan 2026) — Log10 scale normalization, points ters çevrildi (en yeni sol). GTL spike artık sağda. Commit: 3bae9c0.
- [x] **Mobil 6A okunabilirliği** (30 Nisan 2026) — flex→grid-cols-4, font 9px→10px / 11px→12px, min-w-0 overflow fix. Commit: 3bae9c0.
- [x] **FrameShot footer geliştirildi** (7 Mayıs 2026) — Newsletter signup, "Made in Istanbul" location, trust badges (Secure·Private·100% Free), changelog link. Commit: e78253a.

---

## Sırada (Öncelik Sırasına Göre)

### P0 — Kritik Bug'lar

| # | Görev | Açıklama |
|---|---|---|
| P0-1 | **SP500 0 sparkline** | precomputed_etf_categories'da SP500/DUNYA 0 puan — is_active fix test edilecek |
| ~~P0-2~~ ✅ | ~~site veri boş~~ | **ÇÖZÜLDÜ** — homepage_stats tablosu artık dolu, cron 2×/gün çalışıyor |

---

## ETF Return/Sparkline Mimari Düzeltmesi (6 Faz)

**Kullanıcı onayı:** Utku — 6 ayrı pipeline, gerekirse sil baştan yaz.

### Mimari Hedef
| | ETF'ler | Türk Fonları |
|---|---|---|
| Fiyat | USD (foreign_etf_prices.close) | TRY (funds.price_history) |
| Sparkline | USD fiyat bazlı | TRY fiyat bazlı ✓ |
| Homepage 1H | USD daily + TRY daily (küçük) | TRY daily ✓ |
| Getiri kolonları | TRY (`*_return_try`) ✓ | TRY ✓ |
| Detay grafik | USD fiyat | TRY fiyat ✓ |

### Faz 1 — ✅ DOĞRULANDI
ETF sparkline'ları zaten USD fiyatlarından hesaplanıyor (SPY=$723). **Mevcut durum istenen şekil — kapatıldı.**

### Faz 2 — DB: `close_try` kolonu
`foreign_etf_prices` tablosuna `close_try` (Decimal) kolonu ekle. Her fiyat yazılırken USD×FX ile TRY fiyatı da yazılsın. `system_status`'a `fx_usd_try` kaydedilsin.

### Faz 3 — Cron: TRY Sparkline Hesabı
`etf_daily_cron.py`'de sparkline'ları TRY olarak hesapla: `foreign_etf_prices.close_try` kullan. SVG point'ler TRY fiyatları üzerinden çizilsin.

### Faz 4 — TRY Sparkline Backfill
Mevcut 1176 ETF'in TRY sparkline'larını yeniden hesapla. Backfill script'i yaz, çalıştır, doğrula.

### Faz 5 — Homepage: ETF Kartları TRY Göstersin
CategoryTypeCards.tsx ETF kartları: TRY sparkline kullan, 1H TRY daily göster (USD daily küçük text).

### Faz 6 — Detay Sayfası: ReturnsTable + Grafik
ETF detayında: ReturnsTable TRY getiri büyük / USD getiri küçük. Grafik çizgisi USD fiyat göstersin.

### P1 — UI/UX

| # | Görev | Açıklama |
|---|---|---|
| P1-1 | **Skeleton loading** | Fon listesi ve detay sayfasına skeleton ekle |
| P1-2 | **Footer** | Platform bilgisi, hızlı linkler, sosyal medya |
| P1-3 | **Navbar ikon erişilebilirlik** | sr-only label ekle |
| P1-4 | **Mobil nav** | Hamburger menü |

### P2 — SEO

| # | Görev | Açıklama |
|---|---|---|
| P2-1 | **H1–H6 hiyerarşisi** | Ana sayfada tek H1, bölümler H2/H3 |
| P2-2 | **Blog schema** | BlogPosting + Article + Person şeması |
| P2-3 | **sameAs dizisi** | Sosyal medya hesapları ekle |
| P2-4 | **Başlıkta tarih** | "FonRapor — 2400 fon, 28.04.2026" → tarih kaldır |

---

## Notlar

- **Supabase DB:** `postgresql://postgres:***@db.oqkobptbvcazifpvjwfz.supabase.co:5432/postgres`
- **Vercel Token:** `<VERCEL_TOKEN>`
- **Launchd:** `com.fonapp.tefas-daily-cron`, `com.fonapp.etf-daily-cron`, `com.fonapp.health-check`
- **Supabase PostgREST:** TCP 5432 Vercel'de çalışmaz — tüm DB işlemleri HTTPS/443
- **Vercel maxDuration:** 300sn, default 10sn
- **PG driver:** Vercel serverless TCP 5432'ye bağlanamaz — supabase JS client şart
- **Pipeline:** TEFAS scrape (10:00 TR) → cascade (15:00 TR) → homepage_stats (14:00+23:30 TR)
- **14 stuck fon:** GKE, GMV, GKO (Garanti Portföy), PAP ve diğerleri — TEFAS'ta delist edilmiş
- **FonBilgiGetir hız:** ~200ms/çağrı, 2400 fon ≈ 8-10 dk (tek seferlik, gerektiğinde çalıştır)
