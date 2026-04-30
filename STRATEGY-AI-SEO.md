# AI SEO Stratejisi — FonRapor

> **Hazırlık:** `ai-seo` skill'i referans alınmıştır.
> **Tarih:** 2026-04-24
> **Durum:** Strateji taslağı — uygulama ayrıca planlanacak

---

## Mevcut Durum Analizi

### AI Search'de FonApp Nerede?

**Bilinen:** fonrapor.com — Google AI Overviews, ChatGPT, Perplexity'de şu an bilinmiyor. Hiç kontrol yapılmamış.

### FonApp İçin AI SEO Fırsatı

**Neden FonApp AI SEO için ideal:**
1. **Finansal veri = AI altını** — İstatistikler, rakamlar, getiri oranları AI tarafından en çok alıntılanan içerik tipi (+37% görünürlük)
2. **Karşılaştırma içeriği = en çok alıntılanan** — AI cevaplarının %33'ü karşılaştırma sayfalarından geliyor
3. **Türkçe içerik = az rekabet** — AI sistemleri Türkçe finansal içeriğe aç, çok az kaliteli kaynak var
4. **TRY'ye çevrilmiş veri = benzersiz** — Yabancı ETF getirilerini TL'ye çevrilmiş gösteren başka platform yok
5. **Günlük güncellenen veri = tazelik sinyali** — AI sistemleri güncel veriye öncelik veriyor

### Rakip Analizi — AI'da Kim Var?

| Platform | AI Görünürlük | AI Citable İçerik | Türkçe |
|----------|:-------------:|:-----------------:|:------:|
| tefas.gov.tr | Bilinmiyor | Hayır (devlet platformu) | ✅ |
| investing.com | Var | Var (genel) | ❌ |
| morningstar.com | Var | Var | ❌ |
| financelab.com | Sınırlı | Sınırlı | ✅ |
| fonrapor.com | **0** | **Yok** | ✅ |

**Sonuç:** Türkçe AI search'de BÜYÜK BOŞLUK var. FonApp buraya ilk giren olabilir.

---

## Üç Sütun Stratejisi

### Sütun 1: Yapı — İçeriği AI İçin Çıkarılabilir Kıl

#### Her Sayfaya Eklenmesi Gereken Yapısal Öğeler

**1. Definition Block (İlk paragrafta)**
Her fon detay sayfası için ilk paragraf:
```
{fonAdi}, {şirket} tarafından yönetilen {fonTürü} kategorisinde bir yatırım fonudur.
 Fonun güncel fiyatı {fiyat} TL, günlük değişim {+%/-%} {değisım}%.
```

**2. Karşılaştırma Tabloları**
AI en çok tablolardan alıntı yapıyor. Her sayfada:
- Dönemsel getiri tablosu (1G, 1A, 3A, 6A, 1Y)
- Kategori karşılaştırma (Aynı kategorideki en iyi 3 fon)
- Özellik karşılaştırma (Gider oranı, AUM, minimum yatırım)

**3. FAQ Section**
Her sayfaya eklenebilir sorular:
- "{FonAdi} nedir?"
- "{FonAdi} günlük değişimi nedir?"
- "{FonTürü} fonları en iyi hangileri?"
- "Altın fonu mı yoksa altın ETF mi daha karlı?"

**4. Self-Contained Answer Blocks**
Her önemli bilgi cümlesi tek başına anlamlı olmalı:
- ❌ "Fon, piyasa koşullarına göre değişkenlik göstermektedir."
- ✅ "Bu fon son 1 yılda +47.3% getiri sağlamıştır. Aynı dönemde BIST100 +38.1% getiri sağlamıştır."

---

### Sütun 2: Otorite — İçeriği AI'ın Alıntı Yapmak İsteyeceği Hale Getir

#### AI Citation İçin Kritik Unsurlar

**1. İstatistik ve Rakamlar (+37% görünürlük)**
- Her fonda: "+{X}% yıllık getiri, {Y} milyar TL AUM, {Z}% gider oranı"
- Her kategori için: "Son 30 günde en iyi performans gösteren kategori: {kategori} (+{X}%)"
- Tarihlerle birlikte: "2026-04-24 itibarıyla fon verileri"

**2. Kaynak Göstergesi**
Her sayfanın altında:
```
Veri kaynakları: TEFAS (Türkiye Elektronik Fon Alım Satım Sistemi), KAP (Kamuyu Aydınlatma Platformu), yfinance
Son güncelleme: 2026-04-24
```

**3. Güncellik Sinyali**
- Her sayfada "Son güncelleme: {tarih}" göster
- DB'deki `updated_at` değerini sayfada göster
- Eski verili fon varsa "Veri güncel değil" uyarısı

**4. Karşılaştırmalarda Dengeli Yaklaşım**
- AI yanlı karşılaştırmaları cezalandırıyor
- Her karşılaştırmada "Zayıf yönleri" bölümü olsun
- Örnek: "VOO avantajlı: düşük gider oranı (0.03%). Dezavantajı: sadece S&P 500."

---

### Sütun 3: Varlık — AI'ın Baktığı Yerde Bulun

#### Üçüncü Taraf Kaynak Stratejisi

**1. Wikipedia Sayfası**
- FonApp için Wikipedia sayfası yok
- Wikipedia AI cevaplarının %7.8'inde kaynak olarak geçiyor
- Aksiyon: Wikipedia'ya "FonRapor" sayfası ekle veya mevcut Türk fon piyasası sayfalarına katkıda bulun

**2. Reddit Varlığı**
- r/TurkishFinance, r/Borsa, r/Yatirim gibi subreddit'lerde aktif ol
- AI, Reddit'ten %1.8 oranında alıntı yapıyor
- Gerçek katkı sağla, spam değil

**3. Review Platformları**
- G2, Product Hunt Türkiye alternatifleri
- Finans/teknoloji blog'larına misafir yazıları

---

## Uygulama Planı

### Faz 1: Mevcut Sayfaları AI İçin Optimize Et (Hemen — 1-2 saat)

**Fon detay sayfası (`/fon/[code]`):**

Mevcut yapıya eklenecek:

1. **Definition block** — İlk paragrafta fon tanımı
2. **"Son güncelleme" timestamp** — DB `updated_at`'den
3. **Kaynak notu** — TEFAS/KAP/yfinance
4. **FAQ section** — 3-5 soru cevap (mevcut sayfaya ekle)

**ETF detay sayfası (`/etf/[symbol]`):**

1. **Definition block** — ETF tanımı (USD fiyat + TRY karşılığı)
2. **TRY çevrilmiş getiri** — Türkçe + net
3. **"Neden bu ETF?"** — Kısa açıklama
4. **Karşılaştırma önerisi** — Aynı kategorideki 2-3 rakip ETF

**Type/kategori sayfaları (`/type/[type]`):**

1. **Definition block** — Fon türü açıklaması (BYF nedir, KFF nedir)
2. **Kategori istatistikleri** — Toplam fon sayısı, toplam AUM, ortalama getiri
3. **"En iyi {type} fonu"** — İstatistik ile destekli

### Faz 2: AI İçin Machine-Readable Dosyalar (1 saat)

**`/pricing.md`** — FonApp ücretsiz olduğu için:
```markdown
# FonRapor — Fiyatlandırma

## Ücretsiz Plan
- Fiyat: Ücretsiz ( sonsuz )
- Erişim: Tüm fon verileri, tüm ETF verileri, tüm karşılaştırma araçları
- Özellikler: Günlük güncelleme, portföy takibi, PDF export, API erişimi
- Sınır: Yok
```

**`/llms.txt`** — AI sistemleri için site özeti:
```
FonRapor — Türkiye'nin Bağımsız Fon ve ETF Analiz Platformu

Hakkında: FonRapor, Türk yatırımcıların yerli fonları (TEFAS/KAP) ve yabancı ETF'leri 
(yfinance) tek platformda analiz etmesini sağlar.

Ana sayfalar:
- / — Ana sayfa
- /type/[type] — Fon türüne göre liste (BYF, KFF, SRF, VFF, ALTIN, DÖVİZ, OKS)
- /etf — Yabancı ETF listesi
- /compare — Manuel karşılaştırma

Veri kaynakları: TEFAS, KAP, yfinance
Son güncelleme: Her işlem günü saat 10:00 TR
```

### Faz 3: Schema Markup (2-3 saat)

Mevcut sayfalara eklenecek schema türleri:

| Sayfa | Schema | Açıklama |
|-------|--------|---------|
| Fon detay | `FinancialProduct` | Fon adı, fiyat, getiri, gider oranı |
| ETF detay | `FinancialProduct` | ETF adı, fiyat (USD+TRY), getiri |
| Fon kategori | `ItemList` | Kategorideki fonların listesi |
| Ana sayfa | `Organization` | Site bilgileri |
| FAQ sayfaları | `FAQPage` | SSS için |

### Faz 4: Glossary Sayfaları (Programmatic SEO ile paralel)

Her terim için ayrı sayfa:
- `/guides/tefas-nedir`
- `/guides/yatirim-fonu-nasil-calisir`
- `/guides/etf-ve-fon-farki`
- `/guides/gider-orani-nedir`
- `/guides/altin-fonu-vs-fiziki-altin`

### Faz 5: Wikipedia + Reddit Stratejisi (2-4 hafta)

1. **Wikipedia:** FonApp veya Türk fon piyasası hakkında bilgi ekle
2. **Reddit:** r/BorsaTurkey, r/TurkFinance'de aktif ol
3. **Misafir yazı:** Türk finans blog'larına

---

## AI Platform Bazlı Önceliklendirme

| Platform | Öncelik | Neden | İlk Aksiyon |
|----------|---------|-------|-------------|
| **Google AI Overviews** | Çok yüksek | En büyük arama motoru | Schema markup + FAQ pages |
| **Perplexity** | Yüksek | Her cevaba kaynak ekliyor | Kaliteli karşılaştırma sayfaları |
| **ChatGPT (Search)** | Orta-yüksek | Büyüyen pay | Wikipedia + üçüncü taraf varlık |
| **Bing Copilot** | Orta | Türkiye'de düşük Bing kullanımı | llms.txt + schema |

---

## Hızlı Kazanç Kontrol Listesi

### Bugün Yapılabilecekler (2 saat)

- [ ] Her fon sayfasına "Son güncelleme: {tarih}" timestamp ekle
- [ ] Her fon sayfasına kaynak notu ekle (TEFAS, KAP, yfinance)
- [ ] `/pricing.md` dosyası oluştur
- [ ] `/llms.txt` dosyası oluştur
- [ ] `robots.txt`'de AI bot'larının engellenmediğini doğrula

### Bu Hafta (4-8 saat)

- [ ] Fon detay sayfalarına FAQ section ekle (3-5 soru)
- [ ] ETF detay sayfalarına TRY çevrilmiş veri açıklaması ekle
- [ ] Type/kategori sayfalarına definition block ekle
- [ ] `FinancialProduct` schema markup'ı ekle
- [ ] Fon detay sayfalarına "Benzer fonlar" comparison section ekle

### Bu Ay (8-16 saat)

- [ ] Glossary sayfaları oluştur (10 sayfa)
- [ ] Wikipedia sayfası ekle veya güncelle
- [ ] Karşılaştırma sayfalarını AI için optimize et (sonuç/özet tabloları)
- [ ] AI citation monitoring başlat (m她的手动 takip)

---

## Ölçüm

### AI Görünürlük Takibi

**Manuel kontrol (her ay):**
1. ChatGPT'de test sorguları çalıştır
2. Perplexity'de kontrol et
3. Google AI Overview'da var mı kontrol et

**Test sorguları:**
- "En iyi Türk yatırım fonları"
- "Altın fonu mı altın ETF mi daha iyi"
- "TEFAS fon karşılaştırma nasıl yapılır"
- "{FonAdi} nedir"
- "{ETFAdi} vs {ETFB}"
- "S&P 500 ETF Türkiye'den nasıl alınır"

**Hedef:**
- 3 ay içinde: En az 1 AI platformda citation
- 6 ay içinde: Google AI Overview'da görünürlük
- 12 ay içinde: marka sorgularında (brand queries) citation

---

## Notlar

- AI SEO, geleneksel SEO'nun yerine değil, üstüne geliyor. Temel SEO sağlam olmalı.
- AI'ın cezalandırdığı şeyler: keyword stuffing, güncel olmayan veri, yanlı karşılaştırmalar, thin content
- FonApp'in en büyük avantajı: **veri** — bu her AI sistemi için en çekici içerik tipi
