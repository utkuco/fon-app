# Portföy Dağılımı (portfolio_breakdown) — Araştırma & Plan

> Fon portföy dağılımını KAP'tan sağlıklı, kalıcı, MiniMax ile çekmek için
> araştırma + tasarım. **Tarih: 2026-06-02.** Durum: ARAŞTIRMA — uygulama onay bekliyor.

---

## 1. Mevcut durum & kök neden

**Belirti:** `portfolio_breakdown` 2026-04-21'de takılı; günlük cron "0 ✓ / 67 ✗,
No categories" veriyor. Anasayfa "Sektör Favorileri" widget'ı bozuk (ASELS ASELS,
CIMSA CIMSA CIMENTO, ağırlıklar %0.0).

**Bulgular (bugün doğrulandı):**
1. **AI motoru yanlıştı (çözüldü):** Eski kod Zhipu GLM kullanıyordu — hesapta
   bakiye yok + SDK `model_api` kaldırılmış. → **MiniMax-M2.7'ye taşındı**
   (`parse_with_glm`, haber pipeline'ıyla aynı motor). Temiz metinde test edildi,
   kategorileri doğru çıkarıyor. ✅
2. **ASIL KÖK NEDEN — yanlış dosya indiriliyor:** KAP "Portföy Dağılım Raporu"
   duyurusunun indirilen PDF'i yalnızca **kapak sayfası** (~560 karakter: başlık,
   "Güncelleme mi? Hayır", "Bildirim İçeriği"). **Gerçek dağılım tablosu bu PDF'de
   YOK** — duyuruya **ekli ayrı dosyada** (attachment; genelde Excel/ayrı PDF).
   `kap_download_pdf` kapak PDF'ini (`/api/BildirimPdf/{index}`) indiriyor, eki değil.
   → MiniMax'a boş metin gidiyor → "No categories". **MiniMax suçsuz.**
3. **Queue yok:** `kap_daily_state.json` sadece `{last_run}` tutuyor. Başarısız/
   işlenmemiş duyuru takibi, retry, rate-limit kuyruğu yok.
4. **Sektör Favorileri (#61):** `most_held_stocks`, `fund_holdings`'ten ticker'a
   göre agregeleniyor. fund_holdings parser ticker'ı company string'inin ilk
   kelimesi sanıyor → "ASELS ASELS", ağırlık %0.0 (kolon boş/yanlış).

---

## 2. Kullanıcı sorularının yanıtları

| Soru | Yanıt |
|------|-------|
| Güncel PDF'ler nasıl gelecek? | KAP `disclosure/list/main` API'si (Chrome'suz, çalışıyor) "dağılım/portföy" başlıklı duyuruları keşfediyor. Sorun keşifte değil, **ekin indirilmesinde**. |
| Geldiği gibi MiniMax işleyebilecek mi? | **Evet** — ama önce **gerçek tabloyu** (ek dosya) ona vermeliyiz. Kapak metniyle değil. Ek Excel ise pdfminer yerine `openpyxl`/`pandas`; ek PDF ise pdfminer tablo metni. |
| Hata alırsa ne olur, sonraki gün? | **Queue modeli:** her duyuru `pending/done/failed(attempts)` olarak state'te. Başarısızlar ertesi gün tekrar denenir (max N deneme). |
| MiniMax limiti bitince? | Her run **rate-limit'li batch** işler (örn. günde max K duyuru, istekler arası bekleme). İşlenmeyenler queue'da kalır, ertesi gün devam — kuyruk drain edilene kadar. |

---

## 3. Tasarım

### 3a. Doğru veri kaynağı (en kritik)
- Duyuru ekini bul: `kap_download_pdf`'teki fallback zaten
  `/tr/api/file/download/...` linklerini regex'liyor — bunu **birincil yol** yap.
  Disclosure sayfasından (`/Bildirim/{index}`) ek dosya URL'sini çıkar, indir.
- Ek tipi:
  - **Excel (.xlsx/.xls):** `openpyxl`/`pandas` ile tablo oku → kategoriler + %.
    (Çoğu portföy dağılım raporu ekı tablo Excel'dir.)
  - **PDF (tablolu):** `pdfminer` + tablo-farkında ayrıştırma ya da metni MiniMax'a ver.
  - **HTML:** doğrudan parse.
- Doğrulama: ek metninde "HİSSE SENEDİ", "TERS REPO", yüzde işareti var mı?
  Yoksa MiniMax'a gönderme (kota koruması).

### 3b. Queue + rate-limit + retry (state genişlet)
`kap_daily_state.json` →
```json
{
  "last_run": "...",
  "queue": {
    "<disclosure_index>": {
      "fund_code": "KLI", "publish_date": "...",
      "status": "pending|done|failed", "attempts": 0, "last_error": null
    }
  }
}
```
- **Discover:** yeni duyuruları queue'ya `pending` ekle (mevcutları bozma).
- **Drain:** her run `pending` + `failed(attempts<3)` olanları işle, ama
  `MAX_PER_RUN` (örn. 30) ve istekler arası `SLEEP` ile (MiniMax + KAP 429 dostu).
- **Sonuç:** başarılı → `done` + `portfolio_breakdown` upsert; hata → `failed`,
  `attempts++`, `last_error`. 3 denemede vazgeç (log'la).
- **Idempotent:** `done` olanlar tekrar indirilmez/işlenmez.

### 3c. system_status 409 düzeltmesi
`last_kap_portfolio_cron` upsert'i INSERT yapıyor → duplicate key (23505).
`on_conflict=key` ile gerçek upsert'e çevir (kozmetik ama log kirletiyor).

### 3d. Sektör Favorileri / fund_holdings (#61) — portföy düzelince
- fund_holdings parser: ticker'ı company string ilk kelimesinden değil,
  **ISIN'den** veya tablonun ticker kolonundan türet (TR<...>91X deseni
  fund_cascade'de zaten var — oraya hizala).
- Düzelince `most_held_stocks` ağırlıkları gerçek %, isimler tekilleşir
  ("ASELS ASELS" → "ASELS"). Widget anlamlı hale gelir.
- Alternatif: bu widget'ı portföy verisi sağlıklı olana kadar **gizle** ya da
  "fon sayısı" yerine gerçek katkıyı göster.

---

## 4. Uygulama fazları (önerilen sıra)

1. **Faz 1 — Ek indirme:** `kap_download_pdf`'i ek-dosya-öncelikli yap; Excel
   okuyucu ekle. 5-10 duyuruda doğrula (gerçek kategoriler geliyor mu).
2. **Faz 2 — Queue:** state'i genişlet, drain + rate-limit + retry. Bir-iki gün
   çalıştır, kuyruğun dolup boşaldığını gözle.
3. **Faz 3 — Backfill:** geçmiş aylar için discover penceresini genişlet (queue
   zaten rate-limit'li, güvenli). Coverage 566 → hedef ~2000.
4. **Faz 4 — fund_holdings ticker fix + Sektör Favorileri** (#61).

## 5. Açık sorular / riskler
- Ek dosya formatı fon/portföy şirketine göre değişebilir (Excel vs PDF vs HTML)
  — birkaç örnek incelenmeli (Faz 1'de).
- MiniMax günlük/dakikalık kota limiti net değil — `MAX_PER_RUN` + sleep ile
  konservatif başla, log'dan ayarla.
- KAP rate-limit (429) agresif — `_http_request` retry'ı var ama drain hızını
  düşük tut.
- Bazı fonlar portföy raporunu aylık/üç aylık yayımlar → günlük "yeni yok"
  normaldir; freshness beklentisi buna göre.
