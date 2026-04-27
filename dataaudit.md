# KAP Parser — Data Audit & Architecture Rules

## GLM Usage Policy (2026-04-25)

**GLM (Zhipu AI) sadece 2 kategori için kullanılır:**

| Kategori | GLM Kullanır mı? | Açıklama |
|---|---|---|
| `HISSE` | ✅ Evet | Hisse detayı için pdfplumber sonrası ek GLM çağrısı |
| `KARMA` | ✅ Evet | Karma fonlarda hisse % tespiti için |
| `PARA` | ❌ Hayır | Sadece `_parse_para_piyasasi_section4` + GRUP TOPLAMI regex |
| `SERBEST` | ❌ Hayır | Standart portföy tablosu yok — skip |
| `UNKNOWN` | ⚠️GLM cağrılabilir | Bilinmeyen kategoriler için son çare |

**Maliyet etkisi:** ~200 PARA fonu = sıfır GLM çağrısı. Tahmini batch maliyeti: $8-10 → $0.50

---

## Extraction Priority Per Category

```
┌──────────────────────────────────────────────────────────────┐
│  parse_portfolio_tables()                                     │
│                                                              │
│  SERBEST  → return None (skip)                               │
│  PARA     → _parse_para_piyasasi_section4 (Section IV)       │
│            → _parse_para_piyasasi (GRUP TOPLAMI regex)       │
│            → return result or None (NO GLM)                   │
│  HISSE    → _parse_hisse_tables (pdfplumber)                 │
│  KARMA    → _parse_hisse_tables (pdfplumber)                 │
│  UNKNOWN  → _parse_hisse_tables (pdfplumber)                 │
└──────────────────────────────────────────────────────────────┘
                │
                ▼
┌──────────────────────────────────────────────────────────────┐
│  parse_single_pdf() [FALLBACK — only if result is None]      │
│                                                              │
│  HISSE/KARMA/UNKNOWN → extract_with_glm() → merge           │
│  PARA/SERBEST        → NO GLM, skip immediately              │
└──────────────────────────────────────────────────────────────┘
```

---

## Known Fund Categories (KAP PDF Format)

| Kategori | KAP Format | Örnek Fonlar | Tablo Var mı? |
|---|---|---|---|
| Hisse Fonları | GRUP TOPLAMI (A. GRUP/PYŞ/PHAR) + hisse listesi | AN1, GTY | ✅ Standart |
| Karma Fonlar | Hisse + Tahvil GRUP TOPLAMI | GAE, GVA | ✅ Standart |
| Tahvil/Para Piyasası | Section IV (FON TOPLAM DEĞERİ) + GRUP TOPLAMI | GVI, GZG, KUD | ✅ Standart |
| Altın Fonları | Altın + Diğer | — | ✅ Standart |
| Yabancı Fonlar | Döviz + Yabancı varlıklar | — | ✅ Standart |
| Serbest Fonlar | Özel portföy, GEREKİŞ yok | OBP, ODS, OFS | ❌ Yok |
| Katılım/Kira Sertifikası | Farklı format (Kira Sertifikası, Katılım) | ZPG, ZPF, ZSF | ❌ Farklı format |

---

## Validation Rules

### `report_date`
- GLM'den gelen eksik/invalid tarihler yakalanır: `"2026-02"` → `"2025-12-31"` fallback
- Impossibly high day numbers (e.g., Feb 30) → max valid day of month
- Future dates or absurd years → `"2025-12-31"` fallback

### `total_pct`
- Beklenen aralık: 95-105% (bazı fonlarda küçük yuvarlama farkları normal)
- `total_pct < 90%` veya `> 110%` → WARNING log
- `total_pct > 115%` veya `< 85%` → ERROR log

### `stock_pct`
- String format gelebilir (`"74.66%"`) → normalize edilir
- PARA fonları için her zaman 0 veya çok düşük

---

## Bug History

### 2026-04-25 — Bug: PARA fonları gereksiz GLM çağrısı yapıyordu
**Dosya:** `scripts/kap_portfolio_parser.py`
**Satır:** ~1085-1115 (parse_single_pdf fallback bloğu)
**Sorun:** `parse_portfolio_tables` `None` döndüğünde (PARA için bile) GLM fallback tetikleniyordu
**Tetikleyici:** `_parse_para_piyasasi_section4` başarısız olduğunda → `_parse_para_piyasasi` çağrılıyor → o da `None` dönerse → GLM devreye giriyordu
**Örnek:** OGD (PARA) → `glm_fallback` method → gereksiz ~30sn GLM çağrısı
**Düzeltme:** Fallback bloğunda kategori kontrolü eklendi:
```python
if category in ("HISSE", "KARMA", "UNKNOWN"):
    # GLM fallback allowed
elif category in ("PARA", "SERBEST"):
    # NO GLM, skip immediately
```

### 2026-04-25 — Bug: `MHF` tarih hatası `"2026-02"` 
**Sorun:** GLM `"2026-02"` çıkardı (eksik ay) → Supabase date constraint violation
**Düzeltme:** `_validate_date` → `len(parts) != 3` kontrolü → `"2025-12-31"` fallback

### 2026-04-25 — Bug: `_parse_para_piyasasi` signature mismatch
**Sorun:** `TypeError: _parse_para_piyasasi() missing 1 required positional argument: 'fund_code'`
**Neden:** Fonksiyon hem 1-arg stub (satır 145) hem 2-arg gerçek (satır 705) olarak tanımlı — Python sonuncusunu kullanıyordu
**Düzeltme:** Stub → `_parse_para_piyasasi_section4` olarak yeniden adlandırıldı

### 2026-04-25 — Bug: OHK corrupt PDF
**Sorun:** `Unexpected EOF` — PDF dosyası bozuk
**Durum:** Beklenen hata, düzeltme yok

---

## Supabase Schema

**Table:** `portfolio_breakdown`
**Unique constraint:** `(fund_code, report_date)`

| Column | Type | Constraint |
|---|---|---|
| fund_code | text | NOT NULL |
| report_date | date | NOT NULL |
| category | text | — |
| amount | numeric | — |
| rate | numeric | — |
| stock_pct | numeric | — |
| total_pct | numeric | — |
| extraction_method | text | — |

---

## Status Tracking

**SQLite DB:** `scripts/kap_parse_status.db`
- `succeeded`: Parse + upsert başarılı
- `failed`: Tüm yöntemler başarısız
- `pending`: Henüz denenmedi
