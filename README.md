# FonRapor (fon-app)

> Türkiye yatırım fonu ve ETF analiz platformu. [fonrapor.com](https://fonrapor.com)

## Proje Yapısı

```
fon-app/
├── web/                    # Next.js 15 frontend (Vercel deploy)
│   ├── src/app/            # App Router pages
│   ├── src/components/     # React components
│   └── src/lib/            # Supabase clients, API helpers
├── scripts/                # Python scraper/parser scripts
│   ├── tefas_scraper_v2.py # TEFAS CDP API scraper
│   ├── etf_daily_cron.py   # ETF prices via yfinance
│   ├── kap_portfolio_parser.py  # KAP PDF → Zhipu GLM
│   └── kap_discover_download.py  # KAP PDF discovery & download
├── db/                     # SQLite (local only, not on Git)
└── PROJECT.md              # Architecture reference (single source of truth)
```

## Teknoloji Stack

| Katman | Teknoloji |
|--------|-----------|
| Frontend | Next.js 15, React 19, TypeScript, Tailwind CSS, shadcn/ui |
| Backend | Vercel Cron Routes (Edge), Local Python scripts |
| Database | Supabase (PostgreSQL) |
| Storage | KAP PDF files (`~/Desktop/projects/fon-app/pdfs/`) |
| AI | Zhipu GLM-4 (KAP portfolio PDF parsing) |

## Veri Kaynakları

- **TEFAS** → fon fiyatları, AUM, yatırımcı sayısı (`tefas_scraper_v2.py`)
- **KAP** → fon portföy dağılımı PDF'leri (`kap_portfolio_parser.py`)
- **yfinance** → uluslararası ETF fiyatları (`etf_daily_cron.py`)
- **Yahoo Finance** → benchmark endeksleri (`benchmarks-cron`)

### ETF Fiyat Gösterimi
- ETF fiyatları **USD** olarak gösterilir (`$` prefix)
- ETF getiri metrikleri **TL** cinsinden hesaplanır (yabancı piyasalar TL'den)
- Tüm dönem badge'leri: "1A TL", "1G TL" (sıralama butonları: "Günlük (TL)", "Aylık (TL)")

## Cron Job Bölümü

### Vercel (15:00–02:30 TR, Pazartesi–Cuma)
| Cron | Zaman | İş |
|------|-------|-----|
| `fund-cron` | 15:00 | `funds.daily_change`, `funds.sparkline` hesapla |
| `homepage-stats-cron` | 16:00 & 02:30 | `homepage_stats`, `fund_category_ranks` hesapla |
| `benchmarks-cron` | 09:30 | Benchmark endekslerini çek |
| `etf-cron` | 23:00 | ETF fiyatlarını güncelle |
| `etf-returns-cron` | 00:00 | ETF getiri metriklerini hesapla |

### Local Mac (launchd, ~/Library/LaunchAgents)
| Job | Zaman | İş |
|-----|-------|-----|
| `com.fonapp.tefas-daily-cron` | 10:00 | TEFAS'tan fon verisi çek |
| `com.fonapp.etf-daily-cron` | 22:00 | ETF sparkline + fiyat |
| `com.fonapp.kap-portfolio-cron` | 09:00 Pazartesi | KAP PDF parse |
| `com.fonapp.tefas-monitor` | 11:00 | TEFAS taze mi kontrol et |

## Kurulum

### Web (Next.js)
```bash
cd web
npm install
npm run dev
```

### Yerel Cron Scripts
```bash
# .env gereken değişkenler:
# SUPABASE_URL, SUPABASE_SERVICE_KEY, ZHIPU_API_KEY
# TEFAS_EMAIL, TEFAS_PASSWORD, SLACK_WEBHOOK_URL

# TEFAS scraper
python3 scripts/tefas_scraper_v2.py

# ETF cron
python3 scripts/etf_daily_cron.py

# KAP parser
python3 scripts/kap_portfolio_parser.py
```

### Launchd (macOS)
```bash
# Install
cp ~/Desktop/projects/fon-app/scripts/com.fonapp.*.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.fonapp.tefas-daily-cron.plist
```

## Deployment

```bash
cd web
npx vercel --prod --token <VERCEL_TOKEN>
```

**Admin panel:** `/admin` (password: `Yigit-co1`)

## Commit Convention

```
feat: new feature
fix: bug fix
docs: documentation
refactor: code refactor
cron: cron job change
```

## Takım

- **Utku Özer Coşkun** — [@utkuozerc](https://x.com/utkuozerc)
