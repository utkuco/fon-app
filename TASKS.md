# TASKS.md — FonApp

## Pending

- [ ] **Full batch run** — 507 PDF'in tamamını parse et, Supabase'e yaz. Corrupt PDF'leri (OYL, OHK, SUA, UPH) skip et. İşlem ~2 saat sürecek — arka planda çalıştır. (26 Apr 2026)
- [ ] **KARMA corrupt PDF recovery** — OYL, SUA, UPH corrupt. KAP'tan tekrar download denenebilir mi? (26 Apr 2026)
- [ ] **CAIE/MUD delisted check** — CAIE yf=210 rows (Jun 2025'te kurulmuş). MUD yfinance'da var ama belki delisted? Verify on NYSE. (27 Apr 2026)
- [ ] **Vercel homepage-stats-cron system_status bug** — upsertSystemStatus REST API'ye geçildi (fetch-based, supabaseAdmin bypass). Deploy sonrası izle: last_homepage_stats_cron hâlâ DB'de yoksa, Vercel logs kontrol et. (27 Apr 2026)
- [ ] **GitHub Actions TEFAS redundancy** — tefas-cron.yml hâlâ aktif (10:00 TR weekdays, PyPI tefas package). Local tefas_scraper_v2.py (undetected-chromedriver) daha güvenilir. GitHub Actions'ı schedule'dan kaldır (sadece workflow_dispatch bırak). (27 Apr 2026)
- [ ] **TEFAS / Vercel fund-cron etkileşimi** — fund-cron route TEFAS REST API'ye fallback yapıyor ama Vercel IP'leri TEFAS tarafından engelleniyor. fund-cron'un gerçekten çalışıp çalışmadığını doğrula. (27 Apr 2026)

## In Progress

## Done

- [x] **Full system audit (local/Vercel/GitHub)** — 3 ortam haritası çıkarıldı. vercel.json + admin/system/page.tsx + launchd plists + GitHub Actions workflows incelendi. (27 Apr 2026)
- [x] **GitHub Actions KAP cron disabled** — kap-cron.yml schedule-comment-out, sadece workflow_dispatch. Local launchd (com.fonapp.kap-portfolio-cron.plist, 09:00 TR Monday) primary. Duplicate çalışma önlendi. (27 Apr 2026)
- [x] **upsertSystemStatus REST API fix** — supabaseAdmin.supabase.from("system_status").upsert() yerine direct fetch POST (Prefer: resolution=merge-duplicates). Vercel edge runtime uyumluluğu + "***" key fallback bug'ı çözüldü. (27 Apr 2026)
- [x] **Admin system page schedule fixes** — TEFAS vercel source: "Weekdays 07:00 UTC" → "Weekdays 13:00 UTC (15:00 TR)" + systemStatusKey "last_tefas_cron" → "last_fund_cron". GLM pipeline key: "last_glm_pipeline" → "last_kap_portfolio_cron". ETF returns schedule: "Weekdays 21:30 UTC" → "Weekdays 22:00 UTC (00:00 TR)". (27 Apr 2026)
- [x] **PROJECT.md full rewrite** — Tüm veri mimarisi dokümante edildi: DB tables, sparkline format, 3 ortam (Vercel/local/GitHub), tüm cron job'lar, key scripts, known issues. (27 Apr 2026)
- [x] **ETF sparkline format alignment** — etf_daily_cron.py + backfill script: y=[0-1] → y=[0-40], x=[0-280]. 1011 ETF backfilled in 18s. DB verified: max_x=280.0, max_y=40.00 for all. Front-end SparklineMini: pre-scaled data directly used (legacy y=[0-1] still auto-detected via maxY>28). Commit 67d75f0. (27 Apr 2026)
- [x] **Admin panel log fix** — `readLog()` artık `~/Desktop/.../kap_parse.log` yerine Supabase `parse_job_runs` tablosunu okuyor. Committed + pushed to Vercel. (26 Apr 2026)
- [x] **ETF sparkline backfill — PRECOMPUTED** — `foreign_etfs.sparkline` column eklendi. 1002 ETF'in ~389K fiyat satırı paginate fetch + ThreadPoolExecutor ile concurrent çekildi. Her ETF için `{points, positive}` precomputed. `varliklar/page.tsx` artık DB'den okuyor, on-the-fly fallback kaldırıldı. Production'da sparkline SVG'ler görünüyor (MPG, CRDU, MPL, MSOX vb.). PLUL hariç (0 price rows). Script: `scripts/backfill_etf_sparkline_precomputed.py`. (27 Apr 2026)
- [x] **ETF sparkline backfill** — `foreign_etf_prices` tablosunda 247 ETF'e 3486 yeni satır eklendi. Key fix: `merge-duplicates` tek satırda 409 veriyor (2+ satır gerekli), çözüm: DB'deki mevcut tarihleri önce kontrol et → sadece yeni tarihleri batch upsert et. Fake 999.99 VOO verisi temizlendi. MUD fake $2000+ verileri temizlendi. Kalan 247 partial ETF'in çoğu tamamlandı (VOO=251, SPY=251, QQQ=251, VTI=253, TLT=251, IWM=251, MUD=251). CAIE=210 (Jun 2025'te kurulmuş, full year değil). Script: `scripts/backfill_etf_sparkline.py`. NOVM delisted. (27 Apr 2026)
- [x] **parse_job_runs cleanup** — Orphaned entries (id=12, 15) silindi. (26 Apr 2026)
- [x] **KAP daily pipeline** — `kap_daily_pipeline.py` (Chrome-free REST API + ZhipuAI + pdfminer). launchd her gün 09:00 TR'de çalışıyor. (26 Apr 2026)
- [x] **TEFAS launchd verified** — com.fonapp.tefas-daily-cron.plist doğru çalışıyor. Republic Day bypass ✓. Next: Monday Apr 27 10:00 TR. (26 Apr 2026)
- [x] **ETF launchd verified** — com.fonapp.etf-daily-cron.plist permission hatası düzeltildi (chmod +x). Weekend skip ✓. (26 Apr 2026)
- [x] **ETF detail page** — 52-Week High/Low + Tracking Error eklendi. (26 Apr 2026)
- [x] **Admin panel layout** — SiteNavbar/Footer/CookieBanner admin routes için gizleniyor. (26 Apr 2026)
