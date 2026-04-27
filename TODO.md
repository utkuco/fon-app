# KAP Parser — Yapılacaklar

## 🔴 Acil / Devam Eden

- [ ] **PARA fon Section4 header eksikliği** — Bazı PARA fonlarında "FON TOPLAM DEĞERİ" / "T.REPO" header'ı yok. `_parse_para_piyasasi_section4` başarısız oluyor. Alternatif: doğrudan "GRUP TOPLAMI" parse et veya PDF tables'ı kullan.

## 🟡 İyileştirme / Bekleyen

- [ ] **Batch sonrası Supabase kayıt doğrulaması** — Yeni batch (KIRA fix'li) tamamlandığında toplam kayıt sayısını kontrol et.
- [ ] **ZPX30 tarih hatası** — Önceki batch'de "invalid date" vermişti, `_validate_date` fix'inden sonra tekrar denenmeli.
- [ ] **GLM çağrısı sadece HISSE/KARMA** — mimari karar onaylandı. Kod zaten böyle çalışıyor.

## ✅ Tamamlandı (25 Nisan 2026)

- [x] **`_validate_date` — eksik tarih fix** — "2026-02" gibi eksik tarihleri `2025-12-31`'e düzeltir. Gelecek tarihleri de reddeder (year > 2100).
- [x] **`detect_fund_category` — KIRA tespiti** — KİRA SERTİFİKASI / KATILIM HESABI / KATILIM FONU → "KIRA" → skip. (ZPF, ZPG, ZSF, ZSG, ZTG, ZPBDL, ZELOT, ZMY, ZGOLD, ZTLRK, ZP6, ZP8, ZP9, ZPA, ZPC, ZPX30 artık doğru kategoride)
- [x] **`detect_fund_category` — PARA/HISSE/KARMA/SERBEST/UNKNOWN** — doğru tespit
- [x] **`resolution=update`** — Supabase upsert 409 duplicate hatası yönetimi
- [x] **`fund_code` parametresi** — `_parse_para_piyasasi` tüm çağrı sitelerinde mevcut
- [x] **GLM non-reasoning model** (`glm-4.5`) — `content` field'da JSON output
- [x] **DATA_AUDIT.md** — mimari karar + batch sonuçları + teknik kurallar dokümante edildi
- [x] **TASKS.md** — data ile ilgili yapılacaklar listesi güncellendi
