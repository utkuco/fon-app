#!/usr/bin/env python3
"""funds.price kolonu 0/null olan fonları price_history son geçerli (>0) fiyatıyla
doldur. Kök neden: TEFAS güncel-fiyat çağrısı, fon o gün fiyat yayınlamadan önce
0 dönüyor (para piyasası/katılım fonları 10:00'dan geç yayınlıyor). price_history
zaten doğru; sadece kolon stale kalıyordu (başlık ₺0.0000 gösteriyordu)."""
import re, sys, psycopg2

# DB config'i etf_daily_cron.py'den parse et (parola burada hardcode olmasın).
src = open("scripts/etf_daily_cron.py").read()
m = re.search(r"SUPABASE_DB\s*=\s*dict\((.*?)\)", src, re.S)
cfg = {}
for line in m.group(1).split("\n"):
    kv = re.match(r"\s*(\w+)\s*=\s*'([^']*)'|\s*(\w+)\s*=\s*(\d+)", line)
    if kv:
        if kv.group(1): cfg[kv.group(1)] = kv.group(2)
        else: cfg[kv.group(3)] = int(kv.group(4))

conn = psycopg2.connect(**cfg, connect_timeout=30)
conn.autocommit = False
cur = conn.cursor()

cur.execute("""
  SELECT code, price_history
  FROM funds
  WHERE (price IS NULL OR price = 0)
    AND last_tefas_fetch >= now() - interval '14 days'
    AND price_history IS NOT NULL
""")
rows = cur.fetchall()
print(f"aday (price=0/null, aktif): {len(rows)}")

fixed, skipped = 0, 0
for code, ph in rows:
    if not isinstance(ph, list) or not ph:
        skipped += 1; continue
    last_valid = None
    for entry in reversed(ph):
        try:
            p = float(entry.get("price"))
        except (TypeError, ValueError):
            continue
        if p > 0:
            last_valid = p; break
    if last_valid is None:
        skipped += 1; continue
    cur.execute("UPDATE funds SET price = %s WHERE code = %s", (last_valid, code))
    fixed += 1

conn.commit()
print(f"düzeltildi: {fixed}, atlandı (geçerli geçmiş yok): {skipped}")
cur.close(); conn.close()
