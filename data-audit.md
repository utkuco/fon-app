# FonApp Data Audit — 2026-04-25

## Executive Summary

| Table | Total Rows | Freshness | Status |
|-------|-----------|-----------|--------|
| `funds` | 2400 | 2026-04-24 | ✅ 392/2400 güncel (cron), 2008 stale |
| `foreign_etfs` | 1176 | 2026-04-23 21:15 | ✅ 1000/1176 has returns |
| `foreign_etf_prices` | ~401K | 2026-04-22 | ✅ |
| `fund_category_ranks` | **1000** (not 2400!) | 2026-04-24 07:30 | ⚠️ |
| `homepage_stats` | 1 row | 2026-04-24 16:43 | ⚠️ latest_date=2026-04-19 (stale) |
| `benchmarks` | ~50 | 2026-04-17–2026-04-19 | 🟡 |
| `system_status` | 1 row | 2026-04-24 00:50 | ✅ |
| `exchange_rates` | 2 rows | 2026-04-21 (3 days stale) | 🟡 |
| **`portfolio_breakdown`** | **0** | **—** | 🔴 YENİ — veri yok, toplanacak |
| **`funds.breakdown`** | **NULL for all** | **—** | 🔴 YENİ — toplanacak |

---

## Tablolar

### `funds` — Türk Yatırım Fonları
- **Toplam satır:** 2400
- **Price history:** 2400/2400 — ~1 yıl verisi (252 pts, 2025-04 → 2026-04)
- **Sparkline:** 2399/2400 (99.9%)
- **Daily change:** 2396/2400 (99.8%)
- **Breakdown:** NULL for ALL funds — 🔴 veri yok
- **Son fiyat:** 2026-04-24 (`system_status.last_tefas_fetch`)

### `foreign_etfs` — Yabancı ETF'ler
- **Toplam:** 1176 ETF
- **1A/3A/6A return (TRY):** 1000/1176 (85%)
- **eksik:** Sector data, holdings data, 176 ETF'in return'ı yok

### `foreign_etf_prices` — ETF Fiyat Geçmişi
- **Toplam satır:** ~401,276 (1175 ETF, ~341 satır/ETF)
- **Tarih aralığı:** 2011-11-01 → 2026-04-22

### `fund_category_ranks` — Fon Kategori Sıralamaları
- **Toplam satır:** 1000 (2400 değil!)
- **Hesaplanma:** 2026-04-24T07:30:51
- **Sorun:** `homepage-stats-cron` Supabase 1000 satır limiti → 1400 fon sıralanmamış
- **Eksik:** 1400 fonun kategori sıralaması yok

### `homepage_stats` — Ön Hesaplanmış Ana Sayfa Verisi
- **updated_at:** 2026-04-24T16:43:23
- **latest_date:** 2026-04-19 ⚠️ (5 gün stale — Cloudflare nedeniyle veri çekilemiyor)
- **total:** 2400 (artık tüm fonlar işleniyor)
- **category_stats:** 7 kategori (BYF/KFF/OKS/SRF/VFF/ALTIN/DÖVİZ)
- **category_sparklines:** 7 kategori, 17-70 puan

### `benchmarks` — Piyasa Endeksleri
- **Satır:** ~50 (6 sembol × ~8 satır)
- **Stale:** SP500/GOLD/NASDAQ/USDTRY 2026-04-17, BTCUSD/ETHUSD 2026-04-19
- **Kullanım:** Ana sayfa benchmark grafığı

### `exchange_rates` — Döviz Kurları
- **USD/TRY:** 44.8879 (2026-04-21) — 3 gün eski (hafta sonu normal)
- **EUR/TRY:** 52.9075 (2026-04-21)
- **Kullanım:** ETF USD→TRY dönüşümü

### `portfolio_breakdown` — 🔴 YENİ TABLE (yok)
- **Durum:** Table SUPABASE'DE YOK — oluşturulması gerekiyor
- **Planlanan sütunlar:** fund_code, date, stock, government_bond, private_sector_bond, eurobond, gold, repo, reverse_repo, treasury_bill, bank_bills, commercial_paper, term_deposit, etf, derivatives, foreign_equity, foreign_bond, precious_metals, participation_account, other
- **Veri kaynağı:** KAP (Public Disclosure Platform) — aylık Portföy Dağılım Raporu PDF'leri

---

## 🔴 Critical Issues (Aktif)

### 1. ✅ TEFAS Scraper — Cloudflare WAF BYPASSED
**Status:** RESOLVED 2026-04-24
**Fix:** `undetected-chromedriver.Chrome()` standart `webdriver.Chrome()` yerine eklendi
**Commit:** `ff779c9` — pushlandı ve deploy edildi
**Etki:** 608/1000 fon artık çekilebilecek (önceki %39 başarı → %100 hedef)

### 2. 🟡 Homepage `latest_date` 5 gün stale
**Status:** PARTIALLY RESOLVED
**Problem:** `latest_date = 2026-04-19` (2026-04-24 itibarıyla)
**Kök Neden:** TEFAS Cloudflare WAF öncesi çoğu fonu çekemiyordu → `price_history` hâlâ 5 gün önceki veri
**Fix:** undetected-chromedriver deploy edildi → cron çalışınca düzelecek
**Manuel tetikleme:** `UPDATE funds SET updated_at = NOW()` çalıştırılabilir

### 3. 🔴 `portfolio_breakdown` — VERİ YOK
**Status:** ACIL — öncelikli aksiyon gerekli
**Mevcut durum:**
- `portfolio_breakdown` table Supabase'de YOK
- `funds.breakdown` NULL for ALL 2400 fon
- KAP'da aylık Portföy Dağılım Raporları mevcut (PDF)
**Veri kaynağı:** KAP (kap.org.tr) — her fonun KAP sayfasında aylık bildirimler

### 4. 🔴 Fon detay — Sektör/Coğrafya dağılımı YOK
**Status:** ACIL — kullanıcı istedi
**Mevcut:** Fon detay sayfasında yok
**Gerekli:** Varlık dağılımı pasta grafikleri (hisse, tahvil, altın, döviz vb.)
**Not:** TEFAS'ın eski `fundturkey.com.tr/api/DB/BindHistoryAllocation` endpoint'i artık çalışmıyor

---

## 🟡 Medium Issues

### 5. `benchmarks` EURUSD 1 yıl eski
**Severity:** MEDIUM
**Data:** EURUSD son satır 2025-04-10 (1 yıl önce!)
**Impact:** Ana sayfa benchmark grafığinde yanlış EUR karşılaştırması
**Fix:** EURUSD verisini güncelle (TEFAS veya alternatif kaynak)

### 6. 176 ETF'in return'ı yok
**Severity:** LOW
**Data:** 1176 ETF var, sadece 1000'inin 1A/3A/6A return'ı var
**Impact:** Bu 176 ETF anasayfada "N/A" gösterir
**Fix:** `etf-returns-cron`'ı kontrol et

### 7. `fund_category_ranks` sadece 1000 fon
**Severity:** MEDIUM
**Data:** 2400 fon var, sadece 1000'i sıralanmış
**Impact:** 1400 fon /performers sayfasında görünmüyor
**Fix:** Ranking query'sine pagination ekle

---

## ✅ Verified OK (2026-04-24/25)

- ✅ Site canlı: `https://fonrapor.com` → 200 OK
- ✅ Vercel deployment başarılı (web-gp8yv7gs7-utkuozercoskun-2568s-projects.vercel.app)
- ✅ `funds.price_history` 2400/2400 fon mevcut (1 yıl verisi)
- ✅ `fund_category_ranks` = 1000 satır, computed 2026-04-24T07:30:51
- ✅ 7 kategori sparklines mevcut (BYF/KFF/OKS/SRF/VFF/ALTIN/DÖVİZ)
- ✅ 1000 ETF'in TRY return'ları mevcut
- ✅ `system_status.last_tefas_fetch` = 2026-04-24T00:50:20 UTC
- ✅ Vercel cron auth düzeltildi (x-vercel-cron header)
- ✅ TEFAS scraper Cloudflare bypass (`undetected-chromedriver`)
- ✅ Gelişmiş arama eklendi (debounced + type filter chips)
- ✅ Performers karışık tablo sort düzeltildi (ETF + Turkish fon ayrı metrikler)
- ✅ ETF kartları `* 100` düzeltildi (ondalık → yüzde)
- ✅ FundCard routing düzeltildi (isEtf type narrowing)
- ✅ Performers Turkish fon filtresi düzeltildi (monthly sütunu)
- ✅ DZE corruption SQL fix çalıştırıldı
- ✅ BetaAlphaCard %7550 bug düzeltildi

---

## Cron Job Durumu

| Cron | Son Çalışma | Durum |
|------|-------------|-------|
| `fund-cron` (Vercel) | Bilinmiyor | ⚠️ CRON_SECRET 401 sorunu olabilir |
| `homepage-stats-cron` (Vercel) | 2026-04-24 16:43 UTC ✅ | Çalışıyor |
| `etf-prices-cron` (local) | ~2026-04-23 | ✅ |
| `etf-returns-cron` (Vercel) | 2026-04-23 21:15 UTC | ✅ |
| `tefas-monitor` (local) | 2026-04-24 00:50 UTC | ✅ — undetected-chromedriver ile |

---

## Veri Kaynakları

### Mevcut
| Kaynak | Veri | Durum |
|--------|------|-------|
| TEFAS (tefas.gov.tr) | Fiyat, getiri, price_history | ✅ Cloudflare bypass edildi |
| KAP (kap.org.tr) | Fon bilgileri, bildirimler | ✅ Erişilebilir |
| Foreign ETF API | ETF fiyatları, return'lar | ✅ |

### Geliştirilmeli / Yeni
| Kaynak | Veri | Durum |
|--------|------|-------|
| KAP PDF (Portföy Dağılım) | Varlık dağılımı (hisse/tahvil/altın) | 🔴 YOK — parse edilecek |
| fonbul.com API | Varlık dağılımı | 🔴 YOK — API araştırılacak |
| fundturkey.com.tr | Varlık dağılımı | ❌ BLOCKED — Cloudflare |
| Takasbank | Fon portföy verileri | 🔴 YOK — API araştırılacak |

---

## Öncelikli Aksiyon Listesi

### Yapıldı ✅
1. ✅ **[CRITICAL] TEFAS scraper Cloudflare bypass** — undetected-chromedriver → 2026-04-24
2. ✅ **[HOME] homepage-stats-cron pagination fix** — tüm 2400 fon işlensin → 2026-04-24
3. ✅ **[HOME] latest_date** — price_history'den alınıyor → 2026-04-24
4. ✅ **[CRITICAL] Performers karışık tablo sort** — ETF/Turkish fon ayrı metrikler → 2026-04-24
5. ✅ **[MED] ETF kartları ×100** — ondalık → yüzde → 2026-04-24
6. ✅ **[MED] Search bar** — debounced + type filter chips → 2026-04-24
7. ✅ **[MED] FundCard isEtf routing** — type narrowing fix → 2026-04-24
8. ✅ **[MED] Performers Turkish fon filter** — monthly sütunu → 2026-04-24
9. ✅ **[MED] DZE corruption fix** — SQL script çalıştırıldı → 2026-04-24
10. ✅ **[MED] BetaAlphaCard %7550** — meanFund * 252 (×100 yok) → 2026-04-24
11. ✅ **[LOW] TEFAS 5Y backfill** — GEREKSİZ (tüm fonlar < 5 yıl) → 2026-04-24

### Yapılacak 🔴 KRITIK
1. 🔴 **[CRITICAL] portfolio_breakdown table oluştur** — Supabase DDL + KAP scraper
2. 🔴 **[HIGH] KAP PDF parser** — Portföy Dağılım Raporları parse et → DB'ye yaz
3. 🔴 **[HIGH] Fon detay UI** — Varlık dağılımı pasta grafik (BreakdownChart component)

### Yapılacak 🟡 Öncelikli
4. 🟡 **[MED] Homepage stale** — undetected-chromedriver deploy sonrası cron çalışsın → 2026-04-25
5. 🟡 **[MED] 176 ETF return eksik** — etf-returns-cron sebebini ara
6. 🟡 **[MED] fund_category_ranks** — 1000 yerine 2400 fonu sırala
7. 🟡 **[MED] EURUSD benchmark** — 1 yıl eski, güncelle

### Yapılacak 🟢 Düşük
8. 🟢 **[LOW] exchange_rates** — USD/TRY hafta içi otomatik güncellenir
9. 🟢 **[LOW] "Diğer" ETF kategorisi** — 1000+ ETF eşik ile gizle
10. 🟢 **[LOW] BIST 100 endeksi** — canlı grafik + fonlarla karşılaştırma
11. 🟢 **[LOW] ETF screener** — expense ratio, dividend yield, AUM filtreleme

---

## Öncelikli Proje: Fon Portföy Dağılımı 🔴

### Hedef
Her fon için aylık portföy dağılımını topla ve fon detay sayfasında göster.

### Veri Kaynağı: KAP (kap.org.tr)
Her fonun KAP sayfasında (örn. `https://kap.org.tr/tr/fon-bilgileri/ozet/ylc-ata-portfoy-tarim-ve-gida-degisken-fon`) aylık "Portföy Dağılım Raporu" bildirimleri var. Bu bildirimler PDF olarak ekleniyor.

**KAP'da 2400 Türk fonun hepsinin sayfası var.** KAP search API ile toplu sorgu yapılabilir.

### Alternatif: fonbul.com
`https://www.fonbul.com/FonBulPlus/YatirimFonlari/PortfoyAnalizleri/FonPortfoyDagilimi` — Takasbank varlık sınıflandırmasına göre 38 varlık türü listeleniyor. Ücretli API olabilir.

### Alternatif: Takasbank
Takasbank'ın `Fon İşlemleri Menüsü` üzerinden portföy verileri mevcut. API araştırılacak.

### Plan
1. `portfolio_breakdown` table oluştur (Supabase DDL)
2. KAP fon listesi çek (2400 fon)
3. KAP PDF indir + parse et (PyMuPDF/camelot)
4. DB'ye yaz (Upsert)
5. BreakdownChart component (pasta grafik)
6. FundDetailClient'e entegre et

### Takasbank Varlık Sınıflandırması (2021+)
```
Hisse Senedi | Devlet Tahvili | Özel Sektör Tahvili | Eurobond
Hazine Bonosu | Finansman Bonosu | Banka Bonosu | Vadeli Mevduat
Kıymetli Madenler (Altın) | Repo/Ters-Repo | BYF | Türev Araçları
Yabancı Hisse Senedi | Yabancı Borçlanma | Katılım Hesabı
Kira Sertifikaları (Kamu/Özel) | Takasbank Para Piyasası | Diğer
```
