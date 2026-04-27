# Programmatic SEO Stratejisi — FonRapor

> **Hazırlık:** `programmatic-seo` skill'i referans alınmıştır.
> **Tarih:** 2026-04-24
> **Durum:** Strateji taslağı — uygulama ayrıca planlanacak

---

## Mevcut Durum Analizi

### Mevcut Sayfalar

| Sayfa | URL | Tip |
|-------|-----|-----|
| Ana sayfa | `/` | Statik dinamik |
| Fon detay | `/fon/[code]` | Dinamik — 2,400 sayfa |
| ETF detay | `/etf/[symbol]` | Dinamik — 1,176 sayfa |
| ETF kategori | `/etf/[[...category]]` | Dinamik — 6 kategori |
| Fon kategori | `/type/[type]` | Static params — 7 sayfa |
| Karşılaştırma | `/compare` | Manuel (kullanıcı seçer) |
| Fon şirketleri | `/companies` | Mevcut |
| Performers | `/performers` | Mevcut |

### Eksik Olan Programmatic Sayfalar

1. **Fon ↔ Fon karşılaştırma sayfaları** (`/compare/[code1]-vs-[code2]`)
2. **Fon ↔ ETF karşılaştırma sayfaları** (`/compare/[code]-vs-[symbol]`)
3. **Fon şirketi profilleri** (`/company/[id]`)
4. **Fon türü açıklama sayfaları** (`/guides/altin-fonu-nedir`)
5. **ETF kategori açıklama sayfaları** (`/guides/sp500-etf-nedir`)
6. **Persona bazlı sayfalar** (`/for/yeni-baslayan-yatirimci`)
7. **Fon türü + dönem sayfaları** (`/type/BYF?period=1y`)

---

## Uygulanabilir Playbook'lar — FonApp'e Özel

### Playbook 1: Comparisons (En Yüksek Öncelik) ⭐⭐⭐

**Kaç sayfa:** Potansiyel ~C(2400, 2) = 2.9M kombinasyon — ama gerçekçi subset:
- Her fon için en alakalı 3-5 rakip fondan oluşan sayfalar = ~10,000 sayfa
- En çok aranan karşılaştırmalar: aynı kategorideki fonlar arası
- DB'de `fund_type` ve `company_id` var → aynı tür + farklı şirket = ideal karşılaştırma

**URL pattern:** `/compare/[code1]-vs-[code2]`

**Veri kaynağı:** DB'deki mevcut veri:
- `funds.code`, `funds.name`, `funds.fund_type`, `funds.company_id`
- `funds.daily_change`, `funds.weekly`, `funds.monthly`, `funds.quarterly`
- `funds.price_history`, `funds.breakdown`
- `companies.name`, `companies.logo`

**Page template:**
```
/compare/[code1]-vs-[code2]
├── Header: "{Fon1} vs {Fon2} — Karşılaştırma"
├── Özet tablo (1 ay, 3 ay, 6 ay, 1 yıl, günlük değişim, AUM, gider oranı)
├── Performans grafiği (sparkline karşılaştırması)
├── Portföy dağılımı karşılaştırması (hisse vs tahvil vs altın)
├── Şirket karşılaştırması (logo, yönetim şirketi)
├── Artı/Eksi tablosu
├── İlgili karşılaştırmalar (aynı kategorideki diğer fonlar)
└── CTA: "Detaylı analiz için → /fon/[code]"
```

**SEO değeri:**
- Anahtar kelimeler: "{Fon1} vs {Fon2}", "{Fon1} mi {Fon2} mi", "en iyi {category} fonu"
- Intent: yüksek — karar aşamasındaki yatırımcı
- Rival siteler: investing.com, tefas — onlarda bu karşılaştırma yok

**Öncelik:** ÇOK YÜKSEK — ilk uygulama hedefi

**Uygulama notu:** `generateStaticParams` ile tüm kombinasyonlar üretilemez (çok fazla). Strateji:
1. Her fon için "en çok karşılaştırılan" 5 rakip belirle (AUM büyüklüğü + aynı kategori)
2. Critical mass: ~500-1000 sayfa ile başla
3. Sonra genişlet

---

### Playbook 2: ETF ↔ ETF ve Fon ↔ ETF Comparisons ⭐⭐⭐

**Kaç sayfa:**
- Aynı kategorideki ETF'ler: C(1000, 2) ≈ 500K kombinasyon — subset ile başla
- Fon ↔ ETF karşılaştırması: en mantıklısı aynı varlık sınıfı (altın fon vs altın ETF, S&P 500 fon vs S&P 500 ETF)

**URL pattern:** `/compare/[symbol1]-vs-[symbol2]` (karışık Fon/ETF)

**Örnek sayfalar:**
- `/compare/SPY-vs-VOO` — en klasik ETF karşılaştırması
- `/compare/GLD-vs-TLN` — altın ETF vs altın fonu
- `/compare/VOO-vs-hsbc-portfoy` — S&P 500 ETF vs Türk fonu

**Değer önerisi:**
- investing.com'da bu karşılaştırmalar var AMA Türkçe değil ve TRY hesaplaması yok
- FonRapor'un farkı: TRY'ye çevrilmiş getiri = Türk yatırımcı için en gerçekçi karşılaştırma

**Veri:** `foreign_etfs` (USD/TL fiyat, getiriler) + `funds` (TL fiyat, getiriler)

---

### Playbook 3: Fon Şirketi Profilleri ⭐⭐

**Kaç sayfa:** ~70 fon yönetim şirketi (DB'de `companies` tablosu var)

**URL pattern:** `/company/[id]` veya `/sirket/[slug]`

**Mevcut durum:** `/companies` listesi var, bireysel şirket sayfası yok

**Page template:**
```
/company/[slug]
├── Sirket adi + logo
├── Toplam AUM (tüm fonları)
├── Fon sayısı
├── En iyi performans gösteren fonları
├── Kategori dagilimi (kac BYF, kac KFF, vs)
├── Son 30 günlük ortalama getiri
└── Sirket fonlari → /type/[type]?company=[slug] (filtreli)
```

**SEO değeri:**
- "{Fon Sirketi Adi} fonları" — orta hacim, düsük rekabet
- "Yapi Kredi fonlari", "Ak Portfoy fonlari" gibi aramalarda

---

### Playbook 4: Glossary / Bilgi Sayfaları ⭐⭐

**Kaç sayfa:** 15-20 temel terim

**URL pattern:** `/guides/[terim]`

**Sayfalar:**
- `/guides/altin-fonu-nedir` — altın fonu açıklaması + en iyi altın fonları
- `/guides/byf-nedir` — birikimli yönetim fonu açıklaması
- `/guides/sp500-etf-nedir` — S&P 500 ETF açıklaması
- `/guides/tahvil-fonu-nedir` — tahvil fonu açıklaması
- `/guides/yatirim-fonu-nasil-calisir`
- `/guides/etf-ve-fon-farki`
- `/guides/gider-orani-nedir`
- `/guides/tefas-nedir`

**Değer:** Top-of-funnel trafiği yakalar. "Altın fonu nedir" araması → FonRapor'a gelir → orada kalır.

---

### Playbook 5: Persona Bazlı (Funnel) Sayfalar ⭐

**Kaç sayfa:** 5-8 persona

**URL pattern:** `/for/[persona]`

**Sayfalar:**
- `/for/yeni-baslayan` — "Yeni yatırımcılar için fon rehberi"
- `/for/tefas-kullanicilari` — "TEFAS'in sunmadıkları"
- `/for/portfoy-corayan` — "Riskini dağıtmak isteyenler"
- `/for/emeklilik-planlayan` — "Emeklilik için birikim fonları"

**Değer:** Düşük hacim AMA yüksek intent ve marka bilinci.

---

## Öncelik Sıralaması — Hızlı Kazanç İçin

| # | Playbook | Sayfa Sayısı | SEO Değeri | Uygulama Zorluğu | Öncelik |
|---|----------|-------------|-----------|-----------------|---------|
| 1 | **Karşılaştırma (Fon↔Fon)** | ~1,000 | Çok yüksek | Orta | ⭐⭐⭐ |
| 2 | **Glossary sayfaları** | ~15 | Orta-yüksek | Düşük | ⭐⭐⭐ |
| 3 | **Fon↔ETF karşılaştırma** | ~500 | Çok yüksek | Orta | ⭐⭐ |
| 4 | **Fon şirketi profilleri** | ~70 | Orta | Düşük | ⭐⭐ |
| 5 | **ETF↔ETF karşılaştırma** | ~500 | Yüksek | Orta | ⭐⭐ |
| 6 | **Persona sayfaları** | ~5-8 | Düşük | Düşük | ⭐ |

---

## Teknik Mimari Önerisi

### Mevcut `/compare` Sayfasını Genişletme

Mevcut `/compare` manuel sayfası → programatik sayfalara temel oluşturabilir.

**Önerilen route:** `/compare/[slug1]-vs-[slug2]`

- `slug1` = `{code}-{short-name}` veya ETF için `{symbol}`
- Aynı `ComparePageClient` component'ini kullanır
- Sadece URL'den fon kodlarını alır, veriyi DB'den çeker

**Önemi:** Programmatic sayfa oluşturmak için yeni component yazmaya gerek yok — mevcut karşılaştırma altyapısını genişlet yeter.

### Yeni Route Ekleme

```
web/src/app/compare/[slug]/page.tsx
```

- `generateStaticParams`: En önemli 500-1000 karşılaştırma için
- `generateMetadata`: Her sayfa için unique title/description
- DB sorgusu: iki fon/ETF verisini al → karşılaştırma component'ine ver

### Internal Linking Stratejisi

Her fon detay sayfasına ekle:
- "Benzer fonlarla karşılaştır" → aynı kategorideki 3 rakip fondan sayfalara link
- "En çok karşılaştırılan fonlar" → top 5 comparison pages

**Hub & Spoke:**
```
Hub: /type/BYF (BYF fonları listesi)
├── Spokes: /compare/hsbc-vs-ak (BYF karşılaştırma sayfaları)
├── Spokes: /company/hsbc ( HSBC fonları)
└── Cross-links: "Altın fonları için" → /type/ALTIN
```

---

## Uygulama Öncelikli Çıktı: İlk 10 Sayfa

Glossary sayfaları düşük zorluk + yüksek değer → ilk başarısızlık için ideal.

**Hemen yapılabilecek 10 sayfa (sıfır yeni route gerekmez):**

1. `/type/ALTIN` — Altın fonları için bilgi banner + "En iyi altın fonu nedir?" açıklaması
2. `/type/BYF` — Birikimli fonlar için aynı
3. `/type/KFF` — Karma fonlar için aynı
4. `/etf/sp500` — S&P 500 ETF kategori sayfası için açıklama banner
5. `/etf/nasdaq` — Nasdaq ETF kategori sayfası için
6. `/etf/altin` — Altın ETF kategori sayfası için

**Bu sayfalar için:** Mevcut kategori sayfalarına metadata + bilgi section'ı ekle yeter. Yeni route gerekmez.

---

## 경쟁 (Rakip) Analizi — Boşluklar

| Rakip | Fon Karşılaştırma | ETF Karşılaştırma | Türkçe | TRY Getiri |
|-------|:-----------------:|:-----------------:|:------:|:----------:|
| fonrapor.com (biz) | ❌ (sadece manuel) | ❌ | ✅ | ✅ |
| tefas.gov.tr | ❌ | ❌ | ✅ | ✅ |
| investing.com | ✅ | ✅ | ❌ | ❌ |
| finviz.com | ❌ | ✅ | ❌ | ❌ |
| morningstar.com | ✅ (sınırlı) | ✅ | ❌ | ❌ |

**Sonuç:** Fon↔Fon ve Fon↔ETF karşılaştırmasında PİYASADA BOŞLUK var. Bu alanı doldurmak = yüksek SEO değeri.

---

## Sonraki Adımlar

1. **Hemen:** Glossary sayfaları için content brief hazırla
2. **1. sprint:** `/compare/[slug1]-vs-[slug2]` route + ilk 100 sayfa
3. **2. sprint:** Fon şirketi profilleri (70 sayfa)
4. **3. sprint:** Fon↔ETF karşılaştırmaları (500 sayfa)
5. **Devam:** Internal linking + sitemap güncellemeleri
