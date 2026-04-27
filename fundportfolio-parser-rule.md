# Fund Portfolio Parser — Parsing Kuralları

## GLM Gönderilecek Fonlar (AI Parsing)

| Kategori | Neden GLM Gerekli | Açıklama |
|---|---|---|
| **HİSSE** | Şirket detayı (A.Grup) — hisse isimleri + adet + oran | En yaygın hisse fonları |
| **KARMA** | Hem hisse hem diğer varlıklar — hisse kısmı AI ile | Karma fonlar |
| **SERBEST** | Özel portföy — şirket/hisse içeriği olabilir | Serbest fonlar da standart tablo yayınlamaz ama özel GLM ile çıkarılabilir |
| **YABAN** | Yabancı hisseler — şirket isimleri AI ile | Yabancı piyasa fonları |

## Rule-Based / Skip Edilecek Fonlar

| Kategori | Nasıl Çözülür | Açıklama |
|---|---|---|
| **PARA** | Regex — kategori toplamı yeterli | T.REPO, Bono, Mevduat — şirket detayı yok |
| **KIRA** | Skip | Kira Sertifikası / Katılım Hesabı — standart tablo yok |
| **ALTIN** | Skip veya basit regex | Tek emtia — kategori yeterli |
| **DÖVİZ** | Skip veya basit regex | Döviz ağırlıklı — şirket detayı yok |

## Parsing Akışı

```
┌──────────────────────────────────────────────────────┐
│  PDF extract (pdfminer)                              │
│  ↓                                                   │
│  detect_fund_category()                              │
│  ↓                                                   │
│  HISSE / KARMA / SERBEST / YABAN                     │
│  → extract_with_glm()  ← GLM gider                  │
│  ↓                                                   │
│  PARA                                                 │
│  → _parse_para_piyasasi_section4()  ← Regex         │
│  ↓                                                   │
│  KIRA / ALTIN / DÖVİZ                                │
│  → skip()                                            │
└──────────────────────────────────────────────────────┘
```

## GLM Rate Limit Stratejisi

- **Sıralı gönderim** — bir fondan sonra diğeri, limit aşımı yok
- **Model:** `glm-4.5-air` (non-reasoning) — `content` field JSON output
- **Fallback:** pdfplumber önce, başarısız olursa GLM

## Onay

- **Tarih:** 25 Nisan 2026
- **Karar:** Utku Özer Coşkun
