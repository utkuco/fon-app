# TASKS.md — FonApp

## Pending

- [x] **Sparkline rendering fix (VERIFIED)** — `SparklineMini` viewBox="0 0 280 28" → "0 0 280 40" + ETF points (x<280, y<1) auto-scale to SVG space. Fund sparklines 0-40 space, ETF sparklines 0-1 space. `isScaled` flag maxY>28 ile ayrılıyor. Commit 3f72727. Vercel build ✓, DOM ✓ (55 SVG paths, viewBox 280×40, full y-range 0-40 used). (27 Apr 2026)
- [ ] **Full batch run** — 507 PDF'in tamamını parse et, Supabase'e yaz. Corrupt PDF'leri (OYL, OHK, SUA, UPH) skip et. İşlem ~2 saat sürecek — arka planda çalıştır. (26 Apr 2026)
- [ ] **KARMA corrupt PDF recovery** — OYL, SUA, UPH corrupt. KAP'tan tekrar download denenebilir mi? (26 Apr 2026)
- [ ] **Homepage stats cron manual trigger** — `homepage_stats` tablosu Apr 22'den beri güncel değil. Manual trigger veya Vercel'de test et. (26 Apr 2026)
- [ ] **CAIE/MUD delisted check** — CAIE yf=210 rows (Jun 2025'te kurulmuş). MUD yfinance'da var ama belki delisted? Verify on NYSE. (27 Apr 2026)

## Done

- [x] **Admin panel log fix** — `readLog()` artık `~/Desktop/.../kap_parse.log` yerine Supabase `parse_job_runs` tablosunu okuyor. Committed + pushed to Vercel. (26 Apr 2026)
- [x] **ETF sparkline backfill — PRECOMPUTED** — `foreign_etfs.sparkline` column eklendi. 1002 ETF'in ~389K fiyat satırı paginate fetch + ThreadPoolExecutor ile concurrent çekildi. Her ETF için `{points, positive}` precomputed. `varliklar/page.tsx` artık DB'den okuyor, on-the-fly fallback kaldırıldı. Production'da sparkline SVG'ler görünüyor (MPG, CRDU, MPL, MSOX vb.). PLUL hariç (0 price rows). Script: `scripts/backfill_etf_sparkline_precomputed.py`. (27 Apr 2026)
- [x] **ETF sparkline backfill** — `foreign_etf_prices` tablosunda 247 ETF'e 3486 yeni satır eklendi. Key fix: `merge-duplicates` tek satırda 409 veriyor (2+ satır gerekli), çözüm: DB'deki mevcut tarihleri önce kontrol et → sadece yeni tarihleri batch upsert et. Fake 999.99 VOO verisi temizlendi. MUD fake $2000+ verileri temizlendi. Kalan 247 partial ETF'in çoğu tamamlandı (VOO=251, SPY=251, QQQ=251, VTI=253, TLT=251, IWM=251, MUD=251). CAIE=210 (Jun 2025'te kurulmuş, full year değil). Script: `scripts/backfill_etf_sparkline.py`. NOVM delisted. (27 Apr 2026)
- [x] **parse_job_runs cleanup** — Orphaned entries (id=12, 15) silindi. (26 Apr 2026)
- [x] **KAP daily pipeline** — `kap_daily_pipeline.py` (Chrome-free REST API + ZhipuAI + pdfminer). launchd her gün 09:00 TR'de çalışıyor. (26 Apr 2026)
- [x] **TEFAS launchd verified** — com.fonapp.tefas-daily-cron.plist doğru çalışıyor. Republic Day bypass ✓. Next: Monday Apr 27 10:00 TR. (26 Apr 2026)
- [x] **ETF launchd verified** — com.fonapp.etf-daily-cron.plist permission hatası düzeltildi (chmod +x). Weekend skip ✓. (26 Apr 2026)
- [x] **ETF detail page** — 52-Week High/Low + Tracking Error eklendi. (26 Apr 2026)
- [x] **Admin panel layout** — SiteNavbar/Footer/CookieBanner admin routes için gizleniyor. (26 Apr 2026)
