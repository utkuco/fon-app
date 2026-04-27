# FonRapor — Project Architecture

## Overview
FonRapor (fonrapor.com) is a Turkish fund analytics platform. It aggregates fund/ETF prices from TEFAS and KAP, stores them in Supabase, and serves them via a Next.js frontend. The system has three execution environments: **Vercel** (cron jobs + web server), **Local Mac** (launchd cron jobs), and **GitHub Actions** (backup/fallback pipelines).

---

## Data Architecture

### Database
- **Supabase**: `oqkobptbvcazifpvjwfz.supabase.co`
- **Anon key** (frontend): `sb_publishable__GPrsdfKRZCMZE8to916iQ_Izv9naG-`
- **Service key** (scripts, Vercel server): in Vercel env vars as `SUPABASE_SERVICE_KEY`
- **Management token** (`sbp_...`): DDL operations via `supabase` CLI or direct PG connection

### Core Tables
| Table | Purpose | Updated by |
|-------|---------|------------|
| `funds` | TEFAS funds: price, daily_change, price_history, sparkline, last_tefas_fetch | `tefas_scraper_v2.py` (local launchd), `tefas_scraper.py` (GitHub Actions) |
| `foreign_etfs` | International ETFs: price, sparkline, category_history | `etf_daily_cron.py` (local launchd) |
| `category_history` | Benchmark index daily values (ALTIN, BORSA, DOVIZ, all) | `benchmarks-cron` (Vercel) |
| `homepage_stats` | Pre-computed homepage aggregates: top_gainers, category_stats | `homepage-stats-cron` (Vercel) |
| `system_status` | Cron job last-run timestamps + stats JSON | Local scripts + Vercel cron routes (see below) |
| `content_posts` | Blog/content management | Admin panel |
| `kap_portfolio_holdings` | KAP PDF portfolio holdings (GLM parsed) | `kap_portfolio_parser.py` (local launchd) |
| `parse_job_runs` | KAP parse job run logs | `kap_portfolio_parser.py` (local launchd) |

### Sparkline Format
- **Storage**: JSON object `{"points": [[x, y], ...], "positive": bool}`
- **x range**: [0, 280] (280 data points)
- **y range**: [0, 40] (pre-scaled to SVG viewBox height)
- **Fund sparklines**: Computed by `fund-cron` (Vercel) for funds where `sparkline IS NULL` — chunked in batches of 100
- **ETF sparklines**: Computed by `etf_daily_cron.py` (local) or `etf-cron` (Vercel)
- **Rendering**: `SparklineMini` component (src/app/admin/../ui/fund-card.tsx) uses pre-scaled data directly — no JS scaling needed for new data. Backwards compatibility: if `maxY <= 28`, scales legacy y=[0-1] ETF data up to y=[0,40].

---

## Cron Jobs

### Vercel Cron Routes (vercel.json)

| Route | Schedule (UTC) | Schedule (TR) | Writes to | Reads from |
|-------|---------------|---------------|-----------|------------|
| `fund-cron` | 0 13 **1-5** | 15:00 Pazartesi–Cuma | `funds` (via TEFAS REST API fallback) | TEFAS REST API |
| `homepage-stats-cron` | 0 14 **1-5**, 30 23 **1-5** | 16:00 & 02:30 Pazartesi–Cuma | `homepage_stats`, `fund_category_ranks`, `system_status` (last_homepage_stats_cron) | `funds` (lightweight: code, name, fund_type, market_cap, daily_change, price) |
| `benchmarks-cron` | 30 7 **1-5** | 09:30 Pazartesi–Cuma | `category_history` | Yahoo Finance (yfinance) |
| `etf-cron` | 0 21 **1-5** | 23:00 Pazartesi–Cuma | `foreign_etfs` | Yahoo Finance |
| `etf-sparkline-cron` | 30 21 **1-5** | 23:30 Pazartesi–Cuma | `foreign_etfs.sparkline` | `foreign_etfs.price_history` |
| `etf-returns-cron` | 0 22 **1-5** | 00:00 Pazartesi–Cuma | `foreign_etfs.returns` | `foreign_etfs.price_history` |

> ⚠️ **BUG**: `homepage-stats-cron` calls `upsertSystemStatus("last_homepage_stats_cron", ...)` but this key does NOT appear in `system_status` table. The cron runs and updates `homepage_stats` but the status row is missing. Investigate the `upsertSystemStatus` function.

### Local Launchd Jobs (~/Library/LaunchAgents)

| Job | Script | Schedule (TR) | Writes to | Notes |
|-----|--------|---------------|-----------|-------|
| `com.fonapp.tefas-daily-cron.plist` | `run_tefas_cron.sh` → `tefas_scraper_v2.py` | 10:00 Pazartesi–Cuma | `funds`, `system_status` (last_tefas_fetch) | Primary TEFAS source. Uses undetected-chromedriver + Chrome Remote Debugging. |
| `com.fonapp.etf-daily-cron.plist` | `run_etf_cron.sh` → `etf_daily_cron.py` | 22:00 Her gün | `foreign_etfs`, `system_status` (last_etf_fetch, etf_cron_stats) | Fetches ETF prices via Yahoo Finance, computes sparklines |
| `com.fonapp.tefas-monitor.plist` | `run_tefas_monitor.sh` → `tefas_monitor.py` | 11:00 Pazartesi–Cuma | None (read-only) | Monitors last_tefas_fetch age, sends Slack alert if > 4h |
| `com.fonapp.kap-portfolio-cron.plist` | `kap_discover_download.py --batch --limit 0` then `kap_portfolio_parser.py --batch --limit 0` | 09:00 Pazartesi | `kap_portfolio_holdings`, `parse_job_runs`, `system_status` (last_kap_portfolio_cron) | Downloads + parses KAP portfolio PDFs |

### GitHub Actions Workflows

| Workflow | Schedule (UTC) | Schedule (TR) | Trigger | Notes |
|----------|---------------|---------------|---------|-------|
| `tefas-cron.yml` | 0 8 **1-5** | 10:00 Pazartesi–Cuma | schedule + workflow_dispatch | Backup TEFAS source. Uses PyPI `tefas` package (different from local v2). Writes `system_status` (last_tefas_fetch via insert_system_status). |
| `kap-cron.yml` | **DISABLED** | — | workflow_dispatch only | Was running same KAP pipeline as local launchd → duplicate work. Disabled 2026-04-27. Local launchd is primary. Re-enable only if Mac is offline. |

---

## Data Flow Summary

### Fund Data (TEFAS funds)
1. `tefas_scraper_v2.py` (local Mac, 10:00 TR weekdays) scrapes TEFAS → writes `funds.price_history`, `funds.last_tefas_fetch`, `system_status.last_tefas_fetch`
2. `tefas_scraper.py` (GitHub Actions, 10:00 TR weekdays) — PyPI tefas package fallback → same writes
3. `fund-cron` (Vercel, 15:00 TR weekdays) — TEFAS REST API fallback → `funds` (unreliable, TEFAS blocks cloud IPs). ALSO computes sparklines for funds where `sparkline IS NULL` (chunked, 100 at a time).
4. `homepage-stats-cron` (Vercel, 16:00 & 02:30 TR weekdays) reads lightweight `funds` columns → computes `homepage_stats` + `fund_category_ranks` + `system_status`

### ETF Data
1. `etf_daily_cron.py` (local Mac, 22:00 TR daily) fetches Yahoo Finance → writes `foreign_etfs.price_history`, `foreign_etfs.sparkline`
2. `etf-cron` (Vercel, 23:00 TR weekdays) → `foreign_etfs` (same data, redundancy)
3. `etf-sparkline-cron` (Vercel, 23:30 TR weekdays) → `foreign_etfs.sparkline` (same data, redundancy)

### Benchmark Data
1. `benchmarks-cron` (Vercel, 09:30 TR weekdays) fetches Yahoo Finance → writes `category_history`

### KAP Portfolio
1. `kap_discover_download.py` (local Mac, 09:00 TR Pazartesi) discovers + downloads new KAP PDFs → saves to `pdfs/portfoy_dagilim/`
2. `kap_portfolio_parser.py` (local Mac, 09:00 TR Pazartesi) parses PDFs via Zhipu GLM → writes `kap_portfolio_holdings`, logs to `parse_job_runs`

---

## Key Scripts

### Active Scripts (scripts/)

| Script | Purpose | Trigger |
|--------|---------|---------|
| `tefas_scraper_v2.py` | Scrape TEFAS fund prices via undetected-chromedriver | Local launchd (tefas-daily-cron) |
| `tefas_scraper.py` | Scrape TEFAS via PyPI `tefas` package | GitHub Actions tefas-cron.yml |
| `etf_daily_cron.py` | Fetch ETF prices via yfinance, compute sparklines | Local launchd (etf-daily-cron) |
| `kap_discover_download.py` | Discover + download KAP portfolio PDFs | Local launchd (kap-portfolio-cron) |
| `kap_portfolio_parser.py` | Parse KAP PDFs via Zhipu GLM, write holdings | Local launchd (kap-portfolio-cron) |
| `run_tefas_monitor.sh` | Monitor TEFAS freshness, alert via Slack if stale | Local launchd (tefas-monitor) |

### One-time / Backfill Scripts (scripts/)

| Script | Purpose |
|--------|---------|
| `tefas_5y_backfill.py` | Historical TEFAS data backfill (5 years) |
| `backfill_etf_sparkline_precomputed.py` | Backfill ETF sparklines in new y=[0-40] format |
| `compute_etf_returns.py` | Compute ETF return metrics |
| `kap_discover_download.py` | Also used for one-time KAP PDF discovery |
| `etf_scraper_all.py`, `etf_scraper_v3.py` | Obsolete ETF scraper variants |
| `sync-tefas-fees.py`, `sync-valour-only.py` | Obsolete sync scripts |

> Obsolete scripts (`*_refactor*`, `*_old*`, `*_backup*`, `*_bak*`, `check_etfs.js`, `etf_sparkline_backfill.*`) should be deleted after verification.

---

## Known Issues

1. **Duplicate KAP pipeline**: GitHub Actions `kap-cron.yml` was disabled (2026-04-27). Local launchd is primary. If Mac goes offline for extended period, re-enable GitHub Actions schedule.

2. **Vercel fund-cron unreliable**: TEFAS blocks cloud/Vercel IPs. `fetchTefasFunds()` in `fund-cron/route.ts` likely fails. Primary fund data source is local `tefas_scraper_v2.py`.

3. **Duplicate ETF pipelines**: `etf_daily_cron.py` (local, 22:00) and `etf-cron` (Vercel, 23:00) both write to `foreign_etfs`. Could consolidate to one source.

4. **`system_status` table keys**:
   - `last_tefas_fetch` → written by `tefas_scraper_v2.py` ✓
   - `last_5y_backfill` → written by `tefas_5y_backfill.py` (one-time)
   - `last_kap_portfolio_cron` → written by `kap_portfolio_parser.py` ✓
   - `last_etf_fetch` → written by `etf_daily_cron.py` ✓
   - `etf_cron_stats` → written by `etf_daily_cron.py` ✓
   - `last_homepage_stats_cron` → written by `homepage-stats-cron` ✓ (FIXED 2026-04-28: removed `|| "***"` fallback in supabase-admin.ts)
   - `tefas_scraper_log` → written by `tefas_scraper_v2.py` ✓

---

## Environment Variables

### Vercel (Production)
```
ADMIN_PASSWORD=***
CRON_SECRET=***
SUPABASE_SERVICE_KEY=***
NEXT_PUBLIC_SUPABASE_ANON_KEY=sb_publishable__GPrsdfKRZCMZE8to916iQ_Izv9naG-
NEXT_PUBLIC_SUPABASE_URL=https://oqkobptbvcazifpvjwfz.supabase.co
```

### Local Mac (.env.local in scripts/)
```
SUPABASE_URL=https://oqkobptbvcazifpvjwfz.supabase.co
SUPABASE_SERVICE_KEY=***
ZHIPU_API_KEY=***
TEFAS_EMAIL=***
TEFAS_PASSWORD=***
SLACK_WEBHOOK_URL=***
```

---

## Deployment

- **Vercel token**: `vcp_***` (stored in 1Password)
- **Deploy**: `vercel --prod --token $VERCEL_TOKEN` (token in 1Password)
- **Admin panel**: /admin (password: `Yigit-co1`)
- **Git author**: `utkuozercoskun@gmail.com` / `Utku Özer Coşkun`
