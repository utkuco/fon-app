# Product Marketing Context — FonRapor (fonrapor.com)

> **Otomatik taslak** — codebase incelemesinden derlenmiştir.
> Düzeltme ve eksik bilgi için: "What needs correcting? What's missing?"

*Son güncellendi: 2026-04-24*

---

## Product Overview

**One-liner:** Türkiye'nin tek platformu — 2.400+ yerli yatırım fonu VE 1.000+ yabancı ETF'i tek bir yerde analiz et.

**What it does:** FonRapor, Türk yatırımcıların yerli fonları (TEFAS/KAP verileri) ve küresel ETF'leri (yfinance) tek ekranda karşılaştırmasına, portföy dağılımını analiz etmesine ve performans takibi yapmasına olanak tanıyan ücretsiz bir portföy analiz platformudur.

**Product category:** Yatırım fonu ve ETF analiz platformu / finansal veri aracı

**Product type:** SaaS (ücretsiz freemium — tüm veri erişimi ücretsiz)

**Business model:** Şu an tamamen ücretsiz. Uzun vadede: premium özellikler (ileri analiz, uyarılar, portföy takibi) için freemium model planlanıyor.

---

## Target Audience

**Target companies:** Bireysel Türk yatırımcılar — özellikle:
- Mevcut TEFAS kullanıcıları (devlet fon platformu sınırlı analiz sunuyor)
- Hisse senedi yatırımcıları portföy çeşitlendirmesi arayanlar
- Döviz/altın fonlarına geçiş düşünenler
- Yabancı piyasalara erişimi olan (ikinci nesil/yurt dışı) yatırımcılar

**Decision-makers:** Bireysel yatırımcı (tek karar verici)

**Primary use case:** "En iyi fonu/ETF'i nasıl bulurum?" — karşılaştırma, sıralama, seçim

**Jobs to be done:**
1. Türk fonlarını getiriye göre sıralayıp en iyilerini görmek
2. İki fonu veya fondan ETF'e performans karşılaştırması yapmak
3. Bir fonun portföy dağılımını (hisse/tahvil/altın) görmek
4. Yabancı ETF'leri kategori bazlı (S&P 500, Nasdaq, Tahvil, Altın) taramak
5. Gider oranı (expense ratio) karşılaştırması yapmak

**Use cases:**
- Yatırımcı TEFAS'ta bir fon görür → fon kodunu FonRapor'da arar → detaylı analiz ve karşılaştırma yapar
- Yatırımcı "altın fonu mu yoksa fiziki altın mı" düşünür → FonRapor'da GLD vs TLN altın ETF'lerini karşılaştırır
- Portföy danışmanı müşterisine "son 6 ayın en iyi karma fonu"nu göstermek ister

---

## Personas

| Persona | Cares about | Challenge | Value we promise |
|---------|-------------|-----------|------------------|
| **TEFAS kullanıcısı** (bireysel yatırımcı, 30-55 yaş) | Getiri sıralaması, günlük değişim | TEFAS'ta sınırlı filtreleme, karşılaştırma yok, portföy dağılımı yok | Kapsamlı sıralama, 1-3-6-12 ay filtreleme, sektör dağılımı |
| **ETF meraklısı** (bireysel yatırımcı, 25-40 yaş, İngilizce okuyabilir) | Global piyasalara erişim, USD/TRY etkisi | Yabancı platformlar (investing.com, Morningstar) Türk yatırımcıya uygun değil, TRY'ye çevrimi yok | Türkçe arayüzde 1.000+ ETF, TRY getirisi hesaplanmış, kategori bazlı tarama |
| **Portföy çeşitlendirici** (40-60 yaş, TL fon kullanıyor) | Risk dağılımı, altın/döviz fonu geçişi | Hangi fondan hangi fonda geçiş yapacağını bilmiyor | Kategori bazlı karşılaştırma, gider oranı, performans trendi |
| **Finansal danışman** (profesyonel, 30-50 yaş) | Çok sayıda fonu hızlı tarama, müşteri sunumu | Excel ile manuel analiz, veri güncelliği sorunu | Tek tıkla PDF/çıktı, güncel veri, profesyonel karşılaştırma tablosu |

---

## Problems & Pain Points

**Core problem:** Türk yatırımcıların yerli fonları (TEFAS) ve yabancı ETF'leri (yurt dışı platformlar) AYRI AYRI takip etmesi gerekiyor — tek bir karşılaştırma yok.

**Why alternatives fall short:**
- **TEFAS:** Karşılaştırma yok, portföy dağılımı yok, yabancı ETF yok, mobil deneyim zayıf
- **investing.com/finviz:** Yabancı piyasalar odaklı, Türk fon verisi yok veya sınırlı, TRY cinsinden analiz yok
- **Morningstar:** Uluslararası odaklı, Türk fon desteği sınırlı
- **Excel/DIY:** Veri güncelliği sorunu, manuel iş yükü, hata riski

**What it costs them:**
- Yanlış fon seçimi → kaybedilen getiri fırsatı (yıllık %2-5 arası)
- Karşılaştırma yapamamak → yüksek gider oranlı fonlarda kalma
- Ayrı platformlarda takip → zaman kaybı (haftada 1-2 saat)
- Portföy dağılımını bilmememek → aşırı risk veya aşırı muhafazakâr dağılım

**Emotional tension:**
- "En iyi fonu buldum sandım ama belki yanlış seçim yaptım"
- "Yabancı ETF alsam mı, TL fon mu kalsam" kararsızlığı
- "Gider oranı yüksek fonların farkında değilim"
- "Portföyüm gerçekten dengeli mi?"

---

## Competitive Landscape

**Direct competitors:**
- **TEFAS (tefas.gov.tr)** — Devlet fon platformu, sınırlı analiz, karşılaştırma yok, yabancı ETF yok → Eksik: karşılaştırma, portföy detayı, ETF entegrasyonu
- **Qnbfi (qnbfi.com)** — Sadece kendi fonları, sınırlı sayıda, karşılaştırma zayıf
- **İş Yatırım (isnet.isyatirim.com.tr)** — Sadece kendi fonları

**Secondary competitors:**
- **investing.com** — Global piyasalar, Türk fon verisi var ama sınırlı, TRY hesaplaması yok
- **finviz.com** — ABD hisseleri/ETF odaklı, Türk fonu yok
- **Morningstar** — Uluslararası fon analizi, Türk fonu sınırlı, Türkçe değil

**Indirect competitors:**
- **Banka döviz/altın hesapları** — Fiziki yatırım alternatifleri
- **Kripto** — Genç yatırımcılar için alternatif varlık sınıfı
- **Bireysel hisse yatırımı** — Aktif yatırım tercihi

---

## Differentiation

**Key differentiators:**

1. **Türkiye'de rakipsiz veri kapsamı:** 2.400+ yerli fon + 1.000+ yabancı ETF = rakip hiçbir platformda yok
2. **TRY'ye çevrilmiş getiri hesabı:** Yabancı ETF getirileri hem USD hem TRY olarak gösteriliyor
3. **Portföy dağılımı (KAP verisi):** Sadece TEFAS'ın sunmadığı sektör/varlık dağılımı
4. **Günlük otomatik güncelleme:** TEFAS scraper + yfinance cron = her işlem günü güncel
5. **Karşılaştırma tablosu:** Aynı anda 2-3 fon/ETF performans karşılaştırması

**How we do it differently:**
- Tek platformda hem TEFAS (yerli) hem yfinance (yabancı) verisi
- Otomatik güncelleme (kullanıcı manuel veri giriyor)
- Türk yatırımcı için optimize Türkçe arayüz

**Why that's better:**
- Karar verme süresi kısalır (saatler → dakikalar)
- Daha bilinçli fon seçimi = daha yüksek net getiri
- Risk dağılımı görünür → daha dengeli portföy

**Why customers choose us:**
- Ücretsiz ve kayıtsız kullanım
- TEFAS'ın sunmadığı karşılaştırma özelliği
- "Yabancı ETF'leri Türkçe görmek" için tek adres

---

## Objections

| Objection | Response |
|-----------|----------|
| "TEFAS ücretsiz, bu da ücretsiz — ne farkı var?" | TEFAS karşılaştırma yapmaz, portföy dağılımı göstermez, yabancı ETF yok. FonRapor hepsini tek yerde sunar. |
| "Veriler doğru mu?" | TEFAS ve KAP'tan doğrudan çekilen veri + yfinance (dünyanın en yaygın finans verisi kaynağı). Her gün otomatik güncellenir. |
| "Bir şey satıyor musunuz? Komisyon mu alıyorsunuz?" | Hayır. FonRapor tamamen ücretsiz. Hiçbir fon alım/satımına aracılık etmiyor. Platformdan gelir beklemiyoruz — şimdilik. |
| "Telefondan kullanabilir miyim?" | Evet, responsive tasarım. Ana sayfa, fon listesi ve ETF sayfaları mobil uyumlu. |

**Anti-persona:**
- Kurumsal yatırımcılar (büyük hacim, profesyonel araçlar zaten kullanıyorlar)
- Uluslararası yatırımcılar (Türkçe bilmeyen, sadece global piyasalar ilgilendiren)
- Aktif günlük trader'lar (gerçek zamanlı veri gerekiyor, biz günlük güncelliyoruz)

---

## Switching Dynamics

**Push (mevcut çözümden kurtulma):**
- TEFAS'ta "hangi fon en iyi" araması tatmin edici sonuç vermiyor
- Karşılaştırma için 3 farklı site açmak zor geliyor
- Yabancı ETF'lere geçiş düşünüyor ama USD/TL hesabı karıştırıyor

**Pull (FonRapor'a çekilme):**
- Tek arayüzde hem Türk fonları hem ETF'ler
- Ücretsiz ve kayıtsız — denemek için bile yeterli
- TRY'ye çevrilmiş getiri = net karşılaştırma

**Habit (mevcuta bağlılık):**
- "TEFAS'ı zaten biliyorum, oradan hallediyorum"
- "Excel'im var, kendim takip ediyorum"
- Değişiklik için mental çaba gerekiyor

**Anxiety (geçiş kaygısı):**
- "Veriler güvenilir mi?"
- "Bir şey satmaya çalışıyorlar mı?"
- "Kullanmak için kayıt olmam gerekiyor mu?"

---

## Customer Language

**How they describe the problem:**
- "En iyi fonu bulmak için saatlerce uğraşıyorum"
- "Hangi fonun gider oranı düşük bakmak istiyorum"
- "Altın fonu mu alsam, fiziki altın mı bilemedim"
- "Yabancı ETF almak istiyorum ama USD bazında ne getirdiğini hesaplayamıyorum"
- "İki fonu yan yana görmek istiyorum"
- "Portföyümdeki fonların dağılımı ne"

**How they describe us (hedeflediğimiz):**
- "Fonları karşılaştırabildiğim site"
- "TEFAS'ın açıklamadığı şeyleri gösteren"
- "Yabancı ETF'leri Türkçe listeleyen"

**Words to use:** fon, getiri, performans, karşılaştırma, portföy, dağılım, günlük değişim, aylık getiri, gider oranı, sıralama, en iyi, ETF, TRY, USD

**Words to avoid:** portfolio (Türkçe kullan — "portföy"), yield (yerine "getiri"), asset allocation (yerine "varlık dağılımı"), return (yerine "getiri" veya "performans")

**Glossary:**
| Term | Meaning |
|------|---------|
| TEFAS | Türkiye Elektronik Fon Alım Satım Sistemi — devlet fon platformu |
| KAP | Kamuyu Aydınlatma Platformu — şirket/fon açıklamaları |
| Gider oranı | Fundın yönetim ücreti (expense ratio) |
| Sparkline | Son 30 günlük fiyat grafiği |
| BYF | Birikimli Yönetim Fonu |
| KFF | Karma ve Değişken Fon |
| OKS | Özel Sermaye Fonu |
| SRF | Serbest Fon |
| VFF | Varlık Fonu |

---

## Brand Voice

**Tone:** Profesyonel ama samimi — bir finans danışmanı gibi değil, bilgili bir arkadaş gibi konuşuyoruz.

**Style:** 
- Türkçe, günlük, anlaşılır
- Jargon kullanmaktan kaçın — kullanınca açıkla
- Rakamlar ve veriler ön planda
- Dürüst: "Bu fon iyi performans gösterdi AMA gider oranı yüksek" diyebiliriz

**Personality:** 3-5 adjective:
- Bilgili (veri odaklı)
- Dürüst (tarafsız karşılaştırma)
- Erişileşir (karmaşık değil)
- Güncel (veri her zaman taze)
- Türk yatırımcısının yanında (yerel odaklı)

---

## Proof Points

**Metrics:**
- 2.400+ Türk fonu verisi
- 1.000+ yabancı ETF verisi
- Günlük otomatik güncelleme
- TEFAS + KAP + yfinance veri kaynakları

**Customers:** (henüz yok — doğrulama gerekiyor)
- Açık kaynak değil, kullanıcı verisi paylaşılmıyor
- Google Analytics var: G-E3TWFYB7F4

**Testimonials:**
> [Henüz yok — eklenmeli]

**Value themes:**
| Theme | Proof |
|-------|-------|
| Kapsamlı veri | Tek platformda 3.400+ yatırım aracı |
| Ücretsiz | Kayıtsız, limitsiz kullanım |
| Türk yatırımcısına özel | TRY bazlı getiri, Türkçe arayüz, KAP verisi |
| Güncel veri | Her işlem günü güncellenen veri |

---

## Goals

**Business goal:** Türkiye'nin önde gelen bağımsız fon analiz platformu olmak. İlk aşamada: bilinirlik ve kullanıcı tabanı büyütmek.

**Conversion action:** Kullanıcıları sitede daha fazla zaman geçirmeye ve karşılaştırma yapmaya teşvik. Uzun vadede: e-posta bülteni / portföy takibi için kayıt.

**Current metrics:**
- fonrapor.com — canlı site
- Google Analytics: G-E3TWFYB7F4 (henüz detaylı metrik bilinmiyor)
- Kaç kullanıcı, bounce rate, session süresi — bilinmiyor
- Domain Authority: bilinmiyor

---

## Notes — Düzeltilmesi Gereken Alanlar

Aşağıdaki bölümler eksik veya doğrulama gerektiriyor — kullanıcıdan bilgi alınmalı:

- [ ] **Müşteri yorumları / testimonial** — gerçek kullanıcı yoksa eklenemez
- [ ] **Mevcut kullanıcı metrikleri** — GA4'e erişim veya rapor paylaşımı gerek
- [ ] **Gerçek müşteri dili** — yukarıdaki "müşteri dili" bölümü varsayıma dayalı; gerçek kullanıcı araştırması gerek
- [ ] **Rakip alternatifler hakkında derinlemesine bilgi** — her rakibin tam olarak ne yaptığı ve nerede eksik kaldığı doğrulanmadı
- [ ] **Pricing / monetization plan** — ücretsiz kalma kararı mı, yoksa gelecekte premium plan var mı?
- [ ] **Target audience priorite sırası** — 4 persona var, hangisi en büyük ve öncelikli?
- [ ] **Social proof / ortaklıklar** — herhangi bir finans kuruluşu veya influencer ile işbirliği var mı?
