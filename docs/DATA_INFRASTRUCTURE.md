# FonRapor — Veri Altyapısı & Cron Sistemi

> fonrapor.com'u canlı tutan veri pipeline'ı: hangi job neyi günceller, nasıl
> çalışır, bozulduğunda nasıl teşhis/düzeltilir. **Son güncelleme: 2026-06-02.**

---

## 1. Genel mimari

- **Scriptler:** `/Users/admin/Documents/Projects/fon-app/scripts/` (Python 3.11)
- **Python:** `/opt/homebrew/bin/python3.11` (FDA'lı — aşağıya bak)
- **DB:** Supabase (Postgres). Bağlantı `web/.env` → `NEXT_PUBLIC_SUPABASE_URL`,
  `SUPABASE_SERVICE_KEY`, `SUPABASE_DB_URL`. Scriptler `cron_shared.load_env()`
  ile bunları + `~/.hermes/.env`'i (MiniMax key) yükler.
- **AI:** **MiniMax** (`MiniMax-M2.7`, Anthropic-uyumlu endpoint
  `https://api.minimax.io/anthropic/v1/messages`, key `~/.hermes/.env`).
  ⚠️ Zhipu/GLM **KULLANILMIYOR** (hesapta bakiye yok). Tüm AI çağrıları MiniMax.
- **Zamanlayıcı:** macOS `launchd` — `~/Library/LaunchAgents/com.fonapp.*` ve
  `com.fonrapor.*`. Her boot'ta yüklenir, `StartCalendarInterval` ile tetiklenir.
- **Loglar:** `~/Library/Logs/fonrapor/<job>.log` / `.err`
  (⚠️ Documents'ta DEĞİL — bkz. §4 TCC).

---

## 2. Cron job'ları (LaunchAgent)

| Label | Script | Zaman (UTC) | Günceller |
|-------|--------|-------------|-----------|
| `com.fonapp.tefas-daily-cron` | `run_tefas_cron.py` | Hafta içi 08:00 (TR 11:00) | Fon NAV/fiyat (TEFAS, Chrome CDP) |
| `com.fonapp.fund-cascade` | `fund_cascade.py` | TEFAS sonrası | Fon getirileri, sparkline, **benchmark_prices**, homepage_stats |
| `com.fonapp.fund-metrics` | `fund_metrics.py` | günlük | Sharpe/Beta/volatilite/maxDD (`fund_metrics`) |
| `com.fonapp.etf-daily-cron` | `etf_daily_cron.py` | UTC 19/22/01/04/07 | ETF fiyat/günlük |
| `com.fonapp.etf-returns` | `etf_returns.py` | günlük | ETF TL getirileri |
| `com.fonapp.etf-metadata-refresh` | `etf_metadata_refresh.py` | periyodik | `foreign_etfs` metadata (1176 ETF) |
| `com.fonapp.risk-free-rates` | `risk_free_rates.py` | günlük | `system_rates` (USD ^IRX, TRY TCMB) |
| `com.fonapp.holdings-refresh` | `refresh_holdings.sh` | haftalık (Pazar) | fon holdings |
| `com.fonrapor.kap-daily` | `kap_daily_pipeline.py` | günlük | `portfolio_breakdown` (KAP PDF → MiniMax) |
| `com.fonrapor.kap-news` | `run_kap_news.py` | saatlik | Haber + **AI özet** (KAP + ETF + market_digest) |
| `com.fonapp.health-check` / `health-alarm` | — | periyodik | Veri sağlık denetimi |

### kap-news pipeline (saatlik, `run_kap_news.py`)
5 adım, her biri bağımsız (biri patlasa diğeri devam):
1. `kap_announcements_fetcher.py 2` → `fund_announcements` (son 2 gün)
2. `kap_summarize.py` (MiniMax) → AI özet/etiket
3. `etf_news_fetcher.py` → `etf_news` (Yahoo Finance, ~51 anchor ETF)
4. `etf_news_translate.py` (MiniMax) → TR çeviri/özet
5. `market_digest.py` (MiniMax) → günün piyasa özeti (`market_digest`)

---

## 3. Önemli DB tabloları & tazelik

| Tablo | Kaynak job | Beklenen tazelik |
|-------|-----------|------------------|
| `funds` (price/daily_change) | tefas-daily-cron | hafta içi günlük |
| `fund_metrics` | fund-metrics | günlük |
| `benchmark_prices` + `homepage_stats.benchmarks_data` | fund-cascade | günlük |
| `foreign_etfs`, ETF getirileri | etf-* | günlük |
| `system_rates` | risk-free-rates | günlük |
| `fund_announcements` / `etf_news` (+ `ai_summary`) | kap-news | saatlik |
| `market_digest` | kap-news | saatlik |
| `portfolio_breakdown` | kap-daily | KAP portföy raporu yayımladıkça (genelde aylık) |

> ⚠️ Anasayfa parite değerlerini **`homepage_stats.benchmarks_data`**'dan okur,
> legacy `benchmarks` tablosundan DEĞİL. O tablo eski kalabilir, önemsiz.

---

## 4. ⚠️ macOS TCC tuzağı (2026-05-27'de tüm pipeline'ı kırdı)

**Belirti:** Tüm cron job'ları exit 78 (EX_CONFIG) / 126 ile patlıyor, veri donuyor.

**Kök neden:** Scriptler `~/Documents/` altında. macOS TCC, `launchd`'in
korumalı Documents klasörüne erişmesini engelliyor → job ya scripti okuyamıyor
ya da log dosyasını açamıyor (`Operation not permitted`).

**Kalıcı çözüm (iki parça, ikisi de şart):**
1. **Full Disk Access** ver: System Settings → Privacy → Full Disk Access →
   `+` ile `/opt/homebrew/bin/python3.11` **ve** `/bin/bash` ekle, toggle aç.
   (Interpreter Documents'taki scriptleri *okuyabilsin* diye.)
2. **Log yolları Documents DIŞINDA** olmalı: tüm plist'lerde
   `StandardOutPath`/`StandardErrorPath` → `~/Library/Logs/fonrapor/`.
   (`launchd` log dosyasını *programdan önce kendi* açar; launchd'e FDA verilemez.)

**Ek not — bash bağımlılığı:** `/bin/bash`'in FDA'sı kırılgan. Shell wrapper
gerektiren joblar python orchestrator'a çevrildi:
- `run_kap_news.sh` → `run_kap_news.py`
- `run_tefas_cron.sh` → `run_tefas_cron.py`
Böylece launchd sadece FDA'lı `python3.11`'i çağırır, bash'e ihtiyaç kalmaz.

---

## 5. Manuel çalıştırma & teşhis (runbook)

```bash
cd /Users/admin/Documents/Projects/fon-app
set -a; source web/.env; set +a            # DB + env yükle

# Tek job'u elle çalıştır (bu shell Documents'a erişebilir):
/opt/homebrew/bin/python3.11 scripts/risk_free_rates.py

# launchd üzerinden tetikle (FDA + log fix'i test eder):
launchctl kickstart -k "gui/$(id -u)/com.fonapp.risk-free-rates"

# Job durumu (2. sütun = son exit kodu; 0 = OK, 78/126 = TCC/path):
launchctl list | grep -E "fonapp|fonrapor"

# Loglar:
tail -f ~/Library/Logs/fonrapor/<job>.log

# Plist yeniden yükle (düzenledikten sonra):
launchctl bootout "gui/$(id -u)/<label>"
launchctl bootstrap "gui/$(id -u)" ~/Library/LaunchAgents/<label>.plist

# Plist geçerlilik kontrolü:
plutil -lint ~/Library/LaunchAgents/<label>.plist
```

**DB tazelik sorgusu:** `web/.env` source'la, Supabase REST'e
`?select=updated_at&order=updated_at.desc&limit=1` at (örnekler bu repodaki
geçmiş session loglarında).

**TEFAS özel:** Chrome remote-debugging (port 9222) gerekir. `run_tefas_cron.py`
yoksa açar (`open -a "Google Chrome" --args --remote-debugging-port=9222
--user-data-dir=/tmp/chrome-debug`). `curl -s http://localhost:9222/json/version`
ile kontrol et.

---

## 6. Bilinen sınırlar / açık işler

- **portfolio_breakdown coverage (#62):** KAP yalnız portföy raporu yayımladıkça
  güncellenir; "sürekli bilgilendirme formu" PDF'leri portföy verisi içermez →
  "No categories" normal olabilir. Kapsam ~566/2400.
- **fund_holdings PDF parser (#61):** ticker, company string'inin ilk kelimesi
  olarak parse ediliyor — tabular/ISIN tabanlı parse'a geçilmeli.
- **benchmarks_data BTCUSD:** yfinance BTC-USD çekimi ara sıra bayat kalıyor
  (BIST/Altın/USD sağlam).
- **Plist arşivi:** Bu repodaki `launchagents/` dizininde 12 plist'in kopyası
  versiyon kontrollü tutulur (canlı kopya `~/Library/LaunchAgents/`).
