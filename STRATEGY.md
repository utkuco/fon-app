# FonRapor — Ürün & UX Stratejisi

## Mevcut Durum

### Türk Fonları ✓
- Temiz kategori yapısı: Serbest, Değişken, Altın, Karma, Tahvil & Bono, Döviz, Borsa
- Her kategoride AUM, günlük değişim, 1A/3A/6A getiri
- Fund detail sayfası: fiyat, getiri, portföy dağılımı, sektör/bileşenler
- Sorun: Hisse Tercihleri / Şirketler nav'ı fena değil ama izolasyon

### Yabancı ETF'ler ✗
- 1176 ETF var, kategori micro-segmentation ile "Diğer" yığını (40+ micro kategori)
- Türk yatırımcı için hiçbir anlam ifade etmeyen Morningstar kategorileri
- "YTD (₺)" hesaplaması yanlış veya yanıltıcı
- Ana sayfada tüm ETF kategorilerinin listelenmesi ekranı dolduruyor, değerli değil

---

## Vizyon

**Türk yatırımcısına hem TL bazlı fonları hem de USD bazlı yabancı ETF'leri tek bir platformda izleme, karşılaştırma ve keşfetme imkanı.**

Temel value proposition:
1. **TL cinsinden portföy çeşitlendirmesi** — Türk yatırımcı neden %50 TL fon + %50 USD ETF bölmek istesin?
2. **Kıyaslama** — "Bu Türk serbest fonu SPY'den (S&P 500 ETF) iyi mi?"
3. **Keşif** — Türk yatırımcı yabancı ETF'leri nasıl keşfeder?

---

## Sayfa Yapısı Önerisi

### ANASAYFA — "Yatırım Paneli" Olmalı

İki modül: **Türk Fonları** ve **Yabancı ETF'ler** — BİR ARADA ama AYRI.

```
┌─────────────────────────────────────────────────────────────┐
│  FONRAPOR                    [Arama]    [Favoriler] [Karşılaştır] │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─── TÜRK FONLARI ─────────┐  ┌─── YABANCI ETF ─────────┐  │
│  │  [7 kategori kartı]       │  │  [6 basitleştirilmiş  │  │
│  │  Serbest · Değişken       │  │   kategori kartı]     │  │
│  │  Altın · Karma            │  │  S&P 500 · Nasdaq     │  │
│  │  Tahvil · Döviz · Borsa   │  │  Dünya · Tahvil · Altın│  │
│  └───────────────────────────┘  │  Sektör ETF            │  │
│                                  └─────────────────────────┘  │
│                                                             │
│  ┌─── EN ÇOK KAZANDIRANLAR ──────────────────────────────┐  │
│  │  [Aktif tab] Bugün · Bu Hafta · Bu Ay · YTD          │  │
│  │  [Tab] Tümü · Türk Fon · Yabancı ETF                 │  │
│  │  ┌─────────────┬─────────────┬─────────────┐          │  │
│  │  │ FONKOD      │ TÜRK FON    │ +2.4%      │ ₺5,234   │  │
│  │  │ SPY         │ Yabancı ETF │ +1.8%      │ $702     │  │
│  │  │ FONKOD      │ TÜRK FON    │ +1.6%      │ ₺3,120   │  │
│  │  └─────────────┴─────────────┴─────────────┘          │  │
│  └────────────────────────────────────────────────────────┘  │
│                                                             │
│  ┌─── ÖNE ÇIKANLAR ───────────────────────────────────────┐  │
│  │  [Türk fon + Yabancı ETF birlikte, seçilmiş 10-15 ürün]│  │
│  └────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

### Detay Sayfaları

**Türk Fon Detay** (`/fon/[code]`)
- TL bazlı fiyat, günlük değişim
- 1A/3A/6A getiri
- Portföy dağılımı (sektör, varlık türü)
- Hangi şirketlerin hisselerine yatırım yapıyor (top holding'ler)
- Karşılaştırma: "Benzer Yabancı ETF'ler" önerisi

**Yabancı ETF Detay** (`/etf/[symbol]`)
- USD fiyat + TL karşılığı
- Günlük değişim, YTD, 3A, 5A getiri
- Expense ratio, dividend yield, AUM
- TL'de yatırım maliyeti (USD/TRY kuru etkisi)
- Karşılaştırma: "Benzer Türk Fonlar" önerisi

---

## Kategori Basitleştirme — Yabancı ETF

Mevcut: 40+ micro kategori ("Ultrashort Bond", "Trading--Inverse Equity" vb.)
Önerilen: 6 basit kategori

| Basit Kategori | Kapsadığı ETF Sayısı | Örnekler |
|---|---|---|
| **S&P 500 / ABD** | ~10 | SPY, VOO, IVV, SPXL (3x) |
| **Nasdaq / Teknoloji** | ~15 | QQQ, QQQM, QLD, TQQQ, SOXX |
| **Dünya / Gelişmiş** | ~15 | VTI, VXUS, VEA, VWO, EFA |
| **Tahvil & Bono** | ~15 | BND, AGG, TLT, LQD, HYG |
| **Altın & Emtia** | ~8 | GLD, SLV, IAU, DBA, PDBC |
| **Sektör & Diğer** | ~1100+ | Yukarıdakilerin dışındaki tümü |

Alternatif: Sadece **4 mega-kategori** göster, geri kalanı arama/filter ile.

---

## Navigasyon Yapısı

Mevcut nav: Şirketler | Hisse Tercihleri | Yabancı ETF

Önerilen:
```
FonRapor
├── Fonlar           (Türk fonları anasayfa)
│   ├── Kategoriler  (/type/[type])
│   └── [Fon Detay]  (/fon/[code])
├── Yabancı ETF      (/etf)
│   ├── S&P 500
│   ├── Nasdaq
│   ├── Tahvil
│   ├── Altın
│   └── Tüm ETF'ler  (/etf — full list)
│   └── [ETF Detay]  (/etf/[symbol])
├── Karşılaştır       (/compare)  ← TÜRK FON + YABANCI ETF birlikte
├── Performans        (/performers)
└── Şirketler        (/companies)
```

---

## Kritik Farkındalık: Karşılaştırma Motoru

Türk yatırımcının en büyük sorusu:

> "SPY (S&P 500 ETF) aldığımda TL bazında ne kadar kazanırım?
>  Bu Türk Altın Fonu ile GLD arasında ne fark var?
>  Döviz Fonu mı yoksa yabancı Tahvil ETF mi daha iyi?"

Bunu yanıtlayan bir **Karşılaştır** sayfası ana killer feature olur.

---

## Yapılacaklar Öncelik Sırası

1. **[HEMEN]** Ana sayfayı yeniden tasarla — iki panel (Türk Fon + Yabancı ETF) + En Çok Kazandıranlar (karışık)
2. **[HEMEN]** Yabancı ETF anasayfayı basitleştir — 6 basit kategori
3. **[SONRA]** Karşılaştır sayfası — fon + ETF yan yana
4. **[SONRA]** ETF detail sayfasında "Benzer Türk Fon" önerisi
5. **[SONRA]** Türk fon detail sayfasında "Benzer Yabancı ETF" önerisi
6. **[SONRA]** Watchlist / portföy takip (kullanıcı bazlı)
