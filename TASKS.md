# TASKS.md — FonApp

## Pending

- [ ] **Full batch run** — 507 PDF'in tamamını parse et, Supabase'e yaz. Corrupt PDF'leri (OYL, OHK, SUA, UPH) skip et. İşlem ~2 saat sürecek — arka planda çalıştır. (26 Apr 2026)
- [ ] **KARMA corrupt PDF recovery** — OYL, SUA, UPH corrupt. KAP'tan tekrar download denenebilir mi? (26 Apr 2026)
- [ ] **Homepage stats cron manual trigger** — `homepage_stats` tablosu Apr 22'den beri güncel değil. Manual trigger veya Vercel'de test et. (26 Apr 2026)
- [ ] **CAIE/MUD delisted check** — CAIE yf=210 rows (Jun 2025'te kurulmuş). MUD yfinance'da var ama belki delisted? Verify on NYSE. (27 Apr 2026)

## Done

- [x] **Admin panel log fix** — `readLog()` artık `~/Desktop/.../kap_parse.log` yerine Supabase `parse_job_runs` tablosunu okuyor. Committed + pushed to Vercel. (26 Apr 2026)
- [x] **ETF sparkline backfill** — `foreign_etf_prices` tablosunda 247 ETF'e 3486 yeni satır eklendi. Key fix: `merge-duplicates` tek satırda 409 veriyor (2+ satır gerekli), çözüm: DB'deki mevcut tarihleri önce kontrol et → sadece yeni tarihleri batch upsert et. Fake 999.99 VOO verisi temizlendi. MUD fake $2000+ verileri temizlendi. Kalan 247 partial ETF'in çoğu tamamlandı (VOO=251, SPY=251, QQQ=251, VTI=253, TLT=251, IWM=251, MUD=251). CAIE=210 (Jun 2025'te kurulmuş, full year değil). Script: `scripts/backfill_etf_sparkline.py`. NOVM delisted. (27 Apr 2026)
- [x] **parse_job_runs cleanup** — Orphaned entries (id=12, 15) silindi. (26 Apr 2026)
- [x] **KAP daily pipeline** — `kap_daily_pipeline.py` (Chrome-free REST API + ZhipuAI + pdfminer). launchd her gün 09:00 TR'de çalışıyor. (26 Apr 2026)
- [x] **TEFAS launchd verified** — com.fonapp.tefas-daily-cron.plist doğru çalışıyor. Republic Day bypass ✓. Next: Monday Apr 27 10:00 TR. (26 Apr 2026)
- [x] **ETF launchd verified** — com.fonapp.etf-daily-cron.plist permission hatası düzeltildi (chmod +x). Weekend skip ✓. (26 Apr 2026)
- [x] **ETF detail page** — 52-Week High/Low + Tracking Error eklendi. (26 Apr 2026)
- [x] **Admin panel layout** — SiteNavbar/Footer/CookieBanner admin routes için gizleniyor. (26 Apr 2026)
