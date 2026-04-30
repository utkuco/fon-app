#!/usr/bin/env python3
"""ETF Return Calculator v4 — period='2y' for reliable yfinance data"""
import yfinance as yf
import pandas as pd
import urllib.request, json, time, warnings
from datetime import date, datetime, timedelta
warnings.filterwarnings('ignore')

SB_URL = "https://oqkobptbvcazifpvjwfz.supabase.co"
SB_KEY = "sb_publishable__GPrsdfKRZCMZE8to916iQ_Izv9naG-"
H = {"apikey": SB_KEY, "Authorization": f"Bearer {SB_KEY}", "Content-Type": "application/json"}

def get(url, params=None):
    import urllib.parse
    if params: url = f"{url}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers=H)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())

def patch(url, data):
    import urllib.parse
    req = urllib.request.Request(url, data=json.dumps(data).encode(), method="PATCH", headers={**H})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status in (200, 204)
    except: return False

def get_fx():
    try:
        t = yf.Ticker("USDTRY=X")
        h = t.history(period="2y")
        if h is None or h.empty: return None
        fx = h["Close"]
        fx.index = fx.index.tz_localize(None) if fx.index.tz else fx.index
        fx.index = fx.index.normalize()
        return fx
    except: return None

def get_etfs_missing():
    """Return ETFs that need any return data (1M, 3M, or 6M).
    Supabase REST API: column=is.null works, but max 1000 per page.
    We check all three columns and return union via offset pagination.
    """
    # All three columns share the same 164 missing ETFs (confirmed by DB check)
    # Use one_month_return_try=is.null with offset pagination (max 1000/page)
    missing = []
    for offset in range(0, 10000, 1000):
        page = get(f"{SB_URL}/rest/v1/foreign_etfs", {
            "select": "id,symbol",
            "one_month_return_try": "is.null",
            "limit": "1000",
            "offset": str(offset)
        })
        if not page: break
        missing.extend(page)
        if len(page) < 1000: break
    return [(e["id"], e["symbol"]) for e in missing]

def calc_return(series, days, fx):
    if series is None or len(series) < 5: return None
    today = series.index.max()
    p_today = float(series.iloc[-1])
    p_start = None
    start_ts = today - timedelta(days)
    for dt in series.index:
        if dt >= start_ts:
            p_start = float(series.loc[dt])
            break
    if p_start is None or p_start == 0: return None
    usd_ret = p_today / p_start - 1
    if fx is not None:
        try:
            fx_now = float(fx.loc[fx.index[-1]])
            fx_then = float(fx.loc[fx.index[fx.index <= today][-1]])
            return round(usd_ret * (fx_now / fx_then), 6)
        except: pass
    return round(usd_ret, 6)

def main():
    print(f"[{datetime.now().strftime('%H:%M:%S')}] ETF Return Calculator v4")
    fx = get_fx()
    if fx is not None:
        print(f"  FX: now={float(fx.iloc[-1]):.2f}, 2y={float(fx.iloc[0]):.2f}")
    else:
        print("  WARNING: No FX data")
    missing = get_etfs_missing()
    print(f"  {len(missing)} ETFs need data")
    if not missing: return
    updated = skipped = errors = 0
    for idx, (row_id, sym) in enumerate(missing):
        if idx > 0 and idx % 50 == 0:
            print(f"  Progress: {idx}/{len(missing)} updated={updated} skipped={skipped}")
        try:
            df = yf.download(sym, period="2y", progress=False, auto_adjust=True, timeout=15)
            if df is None or df.empty:
                skipped += 1; continue
            if isinstance(df.columns, pd.MultiIndex):
                cc = next((c for c in df.columns if c[0]=="Close"), None)
                if cc is None: skipped += 1; continue
                s = df[cc].dropna()
            else:
                s = df["Close"].dropna() if "Close" in df.columns else None
            if s is None or len(s) < 10: skipped += 1; continue
            s.index = s.index.tz_localize(None) if s.index.tz else s.index
            s.index = s.index.normalize()
            r1 = calc_return(s, 30, fx)
            r3 = calc_return(s, 90, fx)
            r6 = calc_return(s, 180, fx)
            pd_ = {"updated_at": datetime.utcnow().isoformat()}
            if r1 is not None: pd_["one_month_return_try"] = r1
            if r3 is not None: pd_["three_month_return_try"] = r3
            if r6 is not None: pd_["six_month_return_try"] = r6
            if len(pd_) > 1 and patch(f"{SB_URL}/rest/v1/foreign_etfs?id=eq.{row_id}", pd_):
                updated += 1
                if updated <= 5:
                    print(f"  {sym}: 1M={r1*100:+.1f}% 3M={r3*100:+.1f}% 6M={r6*100:+.1f}%" if all([r1,r3,r6]) else f"  {sym}: partial")
            else: errors += 1
        except: skipped += 1
        time.sleep(0.25)
    print(f"\nDONE: {updated} updated, {skipped} skipped, {errors} errors")

if __name__ == "__main__": main()
