# FonRapor.com — Görev Listesi
**Odak:** Sadece P4 — Veri Altyapısı

---

## Proje Özeti
FonRapor.com — Türkiye'nin TEFAS ve KAP verilerini kullanan bağımsız yatırım fonu ve ETF analiz platformu.
Next.js SSR/SSG, Supabase PostgreSQL, Vercel cron jobs.

---

## Pipeline Mimarisi (Son Durum)

```
[YEREL MAC — her iş günü ~18:00 TR]
run_tefas_cron.sh
    ├── Chrome CDP → tefas_scraper_v2.py  (TEFAS'tan veri çeker)
    │       └── PostgREST → Supabase /funds (price_history günceller)
    │
    └── Scraper başarılıysa → curl /api/tefas-cascade
            (Vercel otomatik de çalışır: her gün 15:00 UTC = 18:00 TR)

[VERCEL]
/api/tefas-cascade (cron: 0 15 * * 1-5 = her iş günü 15:00 UTC = 18:00 TR)
    │
    ├── Step 1: computeFundCronMetrics()
    │       └── funds.tablosu → precomputed_funds (sparkline + daily_change + risk metrics)
    │
    ├── Step 2: syncCompanies()
    │       └── precomputed_funds.top_holdings → companies tablosu
    │
    └── Step 3: computeHomepageStats()
            └── precomputed_homepage (category rankings + homepage_stats)
```

**Eski crons (hâlâ çalışır, 15 dkda bir kontrol eder):**
- `fund-cron` (13:00 UTC) — risk metrics için yedek
- `homepage-stats-cron` (14:00 + 23:30 UTC) — ek güncellemeler

---

## Done ✅

### P4-1 ✅ — TEFAS veri boşluğu araştırması
- **Bulgu:** 10 gün = 4 iş günü (Ramazan Bayramı 21-24 Nisan) + hafta sonu (26 Pazar) + scraper çalışmadı (27-28) + bugün henüz çalışmadı (29)
- 29 Nisan verisi: 0 fon — bugün 18:00'de scraper çalışınca dolacak

### P4-2 ✅ — P4-2 aslında zaten mevcuttu
- `run_tefas_cron.sh` → `tefas_scraper_v2.py` → Supabase pipeline'ı baştan beri çalışıyordu
- Sadece cascade otomasyonu eksikti

### P4-3 ✅ — Cascade sistemi
- [x] `src/lib/fund-cron-lib.ts` — shared lib (computeSparkline, computeFundCronMetrics, syncCompanies)
- [x] `src/lib/homepage-stats-lib.ts` — shared lib (computeCategoryStats, computeEtfCategorySparklines, computeHomepageStats)
- [x] `src/app/api/fund-cron/route.ts` — lib kullanacak şekilde yeniden yazıldı (4xx → 58 satır)
- [x] `src/app/api/homepage-stats-cron/route.ts` — lib kullanacak şekilde yeniden yazıldı (577 → 60 satır)
- [x] `src/app/api/internal/fund-cron/route.ts` — header check yok, cascade'den doğrudan çağrılır
- [x] `src/app/api/internal/homepage-stats-cron/route.ts` — header check yok
- [x] `src/app/api/tefas-cascade/route.ts` — Vercel cron (15:00 UTC), sırayla 3 adımı çalıştırır
- [x] `scripts/run_tefas_cron.sh` — scraper başarılıysa cascade'i tetikler
- [x] `vercel.json` — homepage-stats-cron timeout 120s → 300s, tefas-cascade cron eklendi (0 15 * * 1-5)
- [x] TypeScript build kontrolü — 0 yeni hata

### P4-4 ✅ — homepage-stats-cron TEFAS sonrası otomatik tetikleme
- `tefas-cascade` route'u sırayla `computeHomepageStats()` çağırır

### P4-5 ✅ — daily pipeline.sh scripti
- `run_tefas_cron.sh` güncellendi — scraper + cascade webhook

---

## Bekleyen — Deploy

**Deploy edilmesi gereken değişiklikler (fonrapor.com):**

1. `src/lib/fund-cron-lib.ts` — 14,701 bytes, yeni dosya
2. `src/lib/homepage-stats-lib.ts` — 15,128 bytes, yeni dosya
3. `src/app/api/fund-cron/route.ts` — yeniden yazıldı (4xx → 58 satır)
4. `src/app/api/homepage-stats-cron/route.ts` — yeniden yazıldı (577 → 60 satır)
5. `src/app/api/internal/fund-cron/route.ts` — yeni dosya
6. `src/app/api/internal/homepage-stats-cron/route.ts` — yeni dosya
7. `src/app/api/tefas-cascade/route.ts` — yeni dosya
8. `vercel.json` — timeout güncelleme + yeni cron
9. `scripts/run_tefas_cron.sh` — cascade ekleme

---

## Doğrulama Planı

Bugün 18:00'de (veya TEFAS verisi gelince) `run_tefas_cron.sh` çalıştırılacak.
Sonra Supabase'de kontrol edilecek:

```sql
-- precomputed_funds güncellenmiş mi?
SELECT updated_at, COUNT(*) FROM precomputed_funds GROUP BY updated_at ORDER BY updated_at DESC LIMIT 5;

-- precomputed_homepage güncellenmiş mi?
SELECT updated_at FROM precomputed_homepage WHERE id=1;

-- system_status
SELECT * FROM system_status ORDER BY updated_at DESC LIMIT 10;
```
