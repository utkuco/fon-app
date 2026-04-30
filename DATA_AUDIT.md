# Data Audit — KAP Portfolio Parser

## Mimarisi Karar (Onaylandı — 25 Nisan 2026)

```
┌──────────────────────────────────────────────────────────────┐
│  detect_fund_category()                                     │
│                                                              │
│  KIRA      → skip (Kira Sertifikası, standart tablo yok)    │
│  SERBEST  → skip (standart tablo yok, karşılaştırılamaz)    │
│  PARA     → _parse_para_piyasasi_section4 → GRUP TOPLAMI    │
│            → return result (GLM YOK)                         │
│  HISSE    → _parse_hisse_tables → result                    │
│            → extract_with_glm() (stock detail)             │
│  KARMA    → _parse_hisse_tables → result                    │
│            → extract_with_glm() (stock detail)             │
│  UNKNOWN  → _parse_hisse_tables → GLM fallback              │
└──────────────────────────────────────────────────────────────┘
```

**GLM sadece HISSE + KARMA için çağrılıyor.**
**PARA, SERBEST, KIRA → GLM yok.**

### Maliyet Tahmini
- ~150 Hisse + Karma × ~$0.07 = ~$10-15/batch
- ~350 Para + Serbest + Kira × $0 = ~$0
- **Toplam: ~$10-15/batch** (önceki ~$60-80 yerine)

---

## Batch Sonuçlari (25 Nisan 2026)

| Sonuç | Adet | Açıklama |
|---|---|---|
| ✅ Upserted | 42 | Başarılı Supabase yazıldı |
| ❌ KIRA pdfplumber failed | 49 | Standart tablo yok (Kira/Katılım) |
| ❌ SERBEST pdfplumber failed | 37 | Beklenen hata — standart tablo yok |
| ❌ OHK | 1 | Corrupt PDF |

### KIRA/KATILIM Fonları (49 adet) — KIRA Olarak yeniden kategorize edildi

Artık `detect_fund_category` bu fonları doğru tespit ediyor:

```
ZPF  ZPG  ZSF  ZSG  ZTG  ZPBDL  ZELOT  ZMY  ZGOLD  ZTLRK
ZP6  ZP8  ZP9  ZPA  ZPC  ZPX30
```

**Root Cause (DÜZELTİLDI):** `detect_fund_category` → "KIRA" diyor (Kira Sertifikası/Katılım tespiti) → skip ediliyor → GLM yok.

### Beklenen Hatalar (SERBEST — 37 adet)

```
OBP  ODD  ODS  OFI  OFS  OGD  (ve diğer serbest fonlar)
```

Bunlar standart portföy tablosu yayınlamıyor. **Beklenen davranış — bunlar için GLM de çalışmaz.**

---

## Supabase Tablo Durumu

- Tablo: `portfolio_breakdown`
- Endpoint: `oqkobtabvcazifpvjwfz.supabase.co`
- Mimari: `(fund_code, report_date)` unique composite key

---

## Veri Kalitesi Notları

### Hisse/Karma fonları → En zengin veri
- Şirket isimleri + hisse adedi + oran (GLM çıkarıyor)
- A tipi grup toplamları

### Para piyasası fonları → Standart veri
- Kategori bazlı toplam: T.REPO, Bono, Mevduat, vb.
- Toplam portföy yüzdesi

### Kira Sertifikası / Katılım fonları → Düşük veri
- Standart tablo yok
- İçerik: Kira Sertifikası, Katılım Hesabı, Döviz Katılım Hesabı
- GLM de çıkaramaz çünkü standart training data değil

### Serbest fonlar → Veri yok
- Standart tablo yok
- Özel portföy, karşılaştırılamaz

---

## Teknik Kural

> **GLM sadece HISSE + KARMA fonları için kullanılır.** PARA PIYASASI, SERBEST, ve KIRA/KATILIM fonları için GLM çağrılmaz — standart pdfplumber + regex yeterli veya skip edilir.

> **KIRA/KATILIM fonları standart PARA PIYASASI değildir.** `detect_fund_category` bu fonları "KIRA" olarak tespit eder ve skip eder. Standart "FON TOPLAM DEĞERİ" tablosu bu fonlarda bulunmaz.

---

## Log Metodları

| Log Çıktısı | Anlamı |
|---|---|
| `[para_piyasasi_text+section4]` | PARA — Section4 + GRUP TOPLAMI başarılı |
| `[section4_total_only]` | PARA — sadece Section4 |
| `[glm_fallback]` | HISSE/KARMA — pdfplumber başarısız, GLM çalıştı |
| `[pdfplumber+glm]` | HISSE — pdfplumber + GLM merged |
| `KIRA/KATILIM fon — non-standard portfolio` | Beklenen — standart tablo yok, skip edildi |
| `SERBEST fund — no standard portfolio` | Beklenen — standart tablo yok, skip edildi |
| `PARA fund: pdfplumber failed` | PARA tespit edildi ama tablo yok (eskiden KIRA hatası) |

---

## Gerçekleştirilen Düzeltmeler

1. ✅ `_validate_date` — "2026-02" gibi eksik tarihleri `2025-12-31`'e düzeltir
2. ✅ `detect_fund_category` — KIRA tespiti eklendi (Kira Sertifikası/Katılım → "KIRA" → skip)
3. ✅ `detect_fund_category` — SERBEST/HISSE/KARMA/PARA/UNKNOWN doğru tespit
4. ✅ `resolution=update` — Supabase upsert 409 duplicate yönetimi
5. ✅ `fund_code` parametresi — tüm `_parse_para_piyasasi` çağrılarında
6. ✅ GLM `glm-4.5` non-reasoning — `content` field JSON
7. ✅ `_validate_date` — gelecek tarihleri reddeder (year > 2100)

## Bekleyen Düzeltmeler

1. 🔴 **PARA fon Section4 header yok** — Bazı PARA fonlarında "FON TOPLAM DEĞERİ" / "T.REPO" header'ı yok. Alternatif: doğrudan GRUP TOPLAMI parse et. (49 KIRA hatası düzeltildi, şimdi 0 PARA hatası bekleniyor)
2. 🔴 **Batch sonrası Supabase kontrolü** — Yeni batch'te gerçek başarı oranını doğrula
