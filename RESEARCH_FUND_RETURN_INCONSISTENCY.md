# RESEARCHER FINDINGS
Task: Fund return inconsistency root cause — homepage "En Çok Kazandıranlar" shows PMP +24.0%
Date: 2026-05-03

---

## Root Cause

**BUĞDAY FONLARI DEĞİL — veri tutarsızlığı yok. Gösterilen metrik yanlış anlaşılmış.**

### Analiz Özeti

| Konum | PMP Günlük Değişim | PMP 1 Aylık Getiri |
|---|---|---|
| fonrapor.com/fon/PMP detay sayfası | **-1.9%** (Günlük) | **+24.0%** (1A) |
| Homepage "En Çok Kazandıranlar" (default 1A) | — | **+24.0%** ✓ |

**Sonuç: Homepage +24.0% doğru gösteriyor — bu 1 aylık getiri.**

---

## Kod Akışı Analizi

### 1. Veri Kaynağı (Supabase `funds` tablosu)
- `getTurkishGainers()` → `page.tsx` satır 102-181
- Sorgu: `monthly` sütununa göre azalan sıralı, ilk 500 kayıt
- `monthly` = TEFAS scraper'ından gelen 1 aylık getiri (% cinsinden, e.g. 8.38 = 8.38%)
- `daily_change` = günlük değişim (% cinsinden)

### 2. TurkishGainerEntry Dönüşümü (page.tsx satır 167-177)
```typescript
ret_1d: f.daily_change ?? 0,   // Günlük % (e.g. -1.9)
ret_1w: f.weekly ?? 0,          // Haftalık % (e.g. -2.5)
ret_1m: f.monthly ?? 0,         // Aylık % (e.g. +24.0)
ret_3m: get3M(f),               // 3 aylık % (e.g. -2.3)
ret_6m: get6M(f),               // 6 aylık % (e.g. -23.0)
```

### 3. GainersSection Sıralama ve Gösterim (gainers-section.tsx)
- **Default period**: `"1A"` (satır 93: `useState<Period>("1A")`)
- `getReturn(f, "1A")` → `entry.ret_1m` (satır 47)
- Sıralama: `return rb - ra` (büyükten küçüğe, satır 139)
- PMP'nin `ret_1m = 24.0` → En Çok Kazandıranlar'da 1. sırada

### 4. Period Picker Kullanıcı Etkileşimi
Kullanıcı 1G (günlük) seçerse, PMP `-1.9%` gösterir. Bu doğru.

---

## Gösterge Etiketi Karışıklığı (GERÇEK BUG)

**Bulundu: `gainers-section.tsx` satır 203-205**

```typescript
<span className="w-16 text-right">
  {period === "1G" ? "1G" : period === "1H" ? "1H" : period === "1A" ? "1A" : period === "3A" ? "3A" : "6A"}
</span>
```

**Sorun**: Column header'da sadece periyot kısaltması gösteriliyor (1A, 1G, 1H...). Kullanıcı "1A"nın ne anlama geldiğini açıkça göremez. Ancak hover tooltip yok.

**Daha Büyük Potansiyel Sorun**: `period === "1A" ? "1A" : ...` — 3A seçildiğinde label "3A" ama veri `ret_3m`'den geliyor. Kullanıcıya "3A" gösteriliyor ama veri aslında 3 aylık getiri (`ret_3m`), 3 yıllık değil. **Etiket yanlış olabilir.**

---

## Veri Tutarsızlığı Değil — Beklenen Davranış

| Periyot Butonu | Gösterilen Değer (PMP) | Kaynak Alan |
|---|---|---|
| 1G | -1.9% | `daily_change` |
| 1H | -2.5% | `weekly` |
| **1A (default)** | **+24.0%** | `monthly` |
| 3A | -2.3% | `ret_3m` (3M TEFAS) |
| 6A | -23.0% | `ret_6m` |

** fonrapor.com detay sayfası "1 Aylık" değeri +24.0% — homepage "1A" değeri +24.0% ✓ EŞLEŞİYOR**

---

## 3A Etiket Bug Açıklaması

`gainers-section.tsx` satır 203-205'te:
- `period === "3A"` → header "3A" gösteriyor
- Ama veri `getReturn(f, "3A")` → `entry.ret_3m` oluyor
- `ret_3m` = 3 aylık getiri (M的话就3个月，不是3年)
- Kullanıcı "3A"yı "3 Yıl" sanabilir, ama veri 3 aylık

Benzer şekilde 6A: "6A" gösteriyor ama `ret_6m` = 6 aylık.

---

## Root Cause Summary

**Primary finding**: homepage +24.0% for PMP is **correct** — it shows 1-month return matching fonrapor.com.

**Secondary finding (UX bug)**: "3A" and "6A" period buttons show misleading labels. "3A" should clarify it means 3-month return (not 3-year), and similarly "6A" means 6-month (not 6-year). The actual 3-year and 6-year returns come from different database columns (`return_3a`, `return_6a`) which are NOT used in GainersSection.

---

## Files to Change

- `/Users/admin/Desktop/projects/fon-app/web/src/components/ui/gainers-section.tsx`: line 203-205 — column header label for 3A/6A periods is misleading (shows "3A" but data is 3-month return). Consider clarifying label or using "3A" → "3A (3ay)" format.

---

## No Real Bug Found — False Alarm

The homepage correctly displays PMP's 1-month return of +24.0% in the "En Çok Kazandıranlar" section. The fund's daily change of -1.9% is a separate metric shown when the user selects "1G" period. These are different time horizons, not inconsistent data.
