#!/usr/bin/env python3
"""
compute_smart_picks.py

Generates the homepage_stats.smart_picks JSONB blob — 4 ana sekme:
  - strategies (6): TR fonu için stratejik seçimler
  - themes (12): ETF tema kovaları (kahve, AI, savunma, …)
  - personas (4): yatırımcı tipine göre seçim
  - hedges (3): enflasyon / kur / kriz korumaları

Anasayfada SmartPicksCard tek query'de bu blobu okuyor. Cron'da
fund_cascade.py'den önce ya da sonra çalıştırılır.
"""
import json
import os
import sys
from datetime import datetime, timezone
from collections import defaultdict
from typing import Any, Optional

import psycopg2
import psycopg2.extras

DB_URL = os.environ.get(
    "SUPABASE_DB_URL",
    "postgresql://postgres:rzvfO6ub5F1W6hpR@db.oqkobptbvcazifpvjwfz.supabase.co:5432/postgres",
)


def log(msg: str) -> None:
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")


# ─────────────────────────────────────────────────────────────────────
# THEME → TICKER MAPPING
# ─────────────────────────────────────────────────────────────────────
THEMES: dict[str, dict[str, Any]] = {
    "coffee": {
        "label": "Kahve & Soft Emtia",
        "emoji": "☕",
        "blurb": "Kahve, kakao, şeker — softlar üzerine yatırım",
        "tickers": ["DBA", "CANE", "PDBA", "JO", "NIB", "JJG"],
    },
    "ai_robotics": {
        "label": "Yapay Zeka & Robotik",
        "emoji": "🤖",
        "blurb": "Generative AI, robotik, makine öğrenmesi",
        "tickers": ["CHAT", "CHPX", "DRGN", "DRAI", "BOTZ", "AIQ", "IRBO", "ROBO"],
    },
    "defense": {
        "label": "Savunma & Havacılık",
        "emoji": "🛡",
        "blurb": "Savunma sanayi, havacılık, NATO ülkeleri",
        "tickers": ["PPA", "DFEN", "NATO", "DUTY", "ITA", "XAR"],
    },
    "water": {
        "label": "Su & Altyapı",
        "emoji": "💧",
        "blurb": "Su kaynakları, arıtma, altyapı yatırımı",
        "tickers": ["PHO", "CGW", "PIO", "FIW"],
    },
    "ev_battery": {
        "label": "Elektrikli Araç & Lityum",
        "emoji": "🚗",
        "blurb": "EV üreticileri, otonom araç, lityum",
        "tickers": ["DRIV", "KARS", "IDRV", "LIT", "KBAT"],
    },
    "clean_energy": {
        "label": "Temiz Enerji",
        "emoji": "🌳",
        "blurb": "Güneş, rüzgar, hidrojen — yenilenebilir",
        "tickers": ["PBW", "PBD", "ICLN", "TAN", "QCLN", "FAN"],
    },
    "nuclear": {
        "label": "Nükleer & Uranyum",
        "emoji": "☢",
        "blurb": "Uranyum madenciliği, nükleer enerji",
        "tickers": ["NLR", "NUKZ", "URA", "URNM"],
    },
    "biotech": {
        "label": "Biyoteknoloji & İlaç",
        "emoji": "🧬",
        "blurb": "İlaç, biyoteknoloji, genom",
        "tickers": ["PBPH", "PBE", "XBI", "IBB", "IHE", "ARKG", "XLV", "PPH", "PJP"],
    },
    "cybersec": {
        "label": "Siber Güvenlik",
        "emoji": "🔐",
        "blurb": "Cybersecurity, firewall, zero-trust",
        "tickers": ["CIBR", "PSWD", "HACK", "BUG"],
    },
    "mining": {
        "label": "Madencilik",
        "emoji": "💎",
        "blurb": "Altın madenciliği, kıymetli metal üreticileri",
        "tickers": ["NUGT", "NUGY", "PICK", "GDX", "GDXJ", "SIL"],
    },
    "cannabis": {
        "label": "Cannabis & Marijuana",
        "emoji": "🌿",
        "blurb": "Kannabis sektörü, ABD ve Kanada bazlı",
        "tickers": ["MSOS", "CNBS", "MJ", "THCX"],
    },
    "high_dividend": {
        "label": "Yüksek Temettü",
        "emoji": "💰",
        "blurb": "Sürekli temettü ödeyen şirketler",
        "tickers": ["SDY", "NOBL", "DVY", "VYM", "HDV", "VIG", "SCHD"],
    },
}


# ─────────────────────────────────────────────────────────────────────
# PERSONA criteria & weights
# ─────────────────────────────────────────────────────────────────────
PERSONAS: dict[str, dict[str, Any]] = {
    "beginner": {
        "label": "Yeni Mezun / Yeni Başlayan",
        "emoji": "👶",
        "blurb": "Düşük gider, basit, kayıp riski sınırlı",
    },
    "saver": {
        "label": "Birikim Yapan (3-5 yıl)",
        "emoji": "🏠",
        "blurb": "Düzenli birikim için dengeli portföy",
    },
    "retirement": {
        "label": "Emekliliğe Hazırlanan",
        "emoji": "🛀",
        "blurb": "BES, devlet katkısı, uzun vade",
    },
    "trader": {
        "label": "Aktif Yatırımcı / Trader",
        "emoji": "💼",
        "blurb": "Yüksek dalgalanma, momentum, agresif",
    },
}


# ─────────────────────────────────────────────────────────────────────
# DB load helpers
# ─────────────────────────────────────────────────────────────────────
def load_funds(cur) -> list[dict]:
    cur.execute(
        """
        SELECT f.code, f.name, f.fund_type, f.market_cap, f.daily_change,
               f.monthly, f.weekly, f.quarterly,
               f.return_1g, f.return_1h, f.return_1a, f.return_3a, f.return_6a,
               f.management_fee, f.price_history,
               c.display_name AS company,
               m.sharpe_ratio, m.sortino_ratio, m.annualized_return,
               m.annualized_volatility, m.max_drawdown, m.beta
        FROM funds f
        LEFT JOIN companies c ON f.company_id = c.id
        LEFT JOIN fund_metrics m ON m.fund_code = f.code
        WHERE f.market_cap >= 10000000
          AND abs(coalesce(f.daily_change, 0)) <= 200
          AND abs(coalesce(f.monthly, 0)) <= 300
        """
    )
    return [dict(r) for r in cur.fetchall()]


def load_etfs(cur) -> list[dict]:
    cur.execute(
        """
        SELECT symbol, name, asset_type, category, fund_family,
               aum, expense_ratio, dividend_yield, beta,
               ytd_return, one_month_return_try, three_month_return_try,
               six_month_return_try, three_yr_return, five_yr_return,
               sparkline
        FROM foreign_etfs
        WHERE is_active = true
        """
    )
    return [dict(r) for r in cur.fetchall()]


def fund_to_pick(f: dict, criterion: str, criterion_value: str | None = None) -> dict:
    """Compact dict for JSON payload."""
    return {
        "code": f["code"],
        "name": f.get("name") or "",
        "company": f.get("company") or "",
        "fund_type": f.get("fund_type"),
        "monthly": float(f["monthly"]) if f.get("monthly") is not None else None,
        "return_1a": float(f["return_1a"]) * 100 if f.get("return_1a") is not None else None,
        "sharpe": float(f["sharpe_ratio"]) if f.get("sharpe_ratio") is not None else None,
        "market_cap": float(f["market_cap"]) if f.get("market_cap") is not None else None,
        "criterion": criterion,
        "criterion_value": criterion_value,
    }


def etf_to_pick(e: dict, criterion: str, criterion_value: str | None = None) -> dict:
    return {
        "code": e["symbol"],
        "name": e.get("name") or "",
        "family": e.get("fund_family") or "",
        "asset_type": e.get("asset_type"),
        "aum": float(e["aum"]) if e.get("aum") is not None else None,
        "expense_ratio": float(e["expense_ratio"]) if e.get("expense_ratio") is not None else None,
        "monthly_try": float(e["one_month_return_try"]) * 100 if e.get("one_month_return_try") is not None else None,
        "ytd": float(e["ytd_return"]) if e.get("ytd_return") is not None else None,
        "criterion": criterion,
        "criterion_value": criterion_value,
    }


# ─────────────────────────────────────────────────────────────────────
# STRATEGY computers
# ─────────────────────────────────────────────────────────────────────
def monthly_returns_from_history(ph: list, n_months: int) -> list[float]:
    """Last n_months calendar-month returns from price_history."""
    if not ph or not isinstance(ph, list):
        return []
    cleaned = sorted(
        [(p["date"], float(p["price"])) for p in ph
         if isinstance(p, dict) and p.get("date") and p.get("price") and float(p["price"]) > 0],
        key=lambda x: x[0],
    )
    if len(cleaned) < 30:
        return []
    by_month: dict[str, tuple[float, float]] = {}
    for d, p in cleaned:
        ym = d[:7]
        if ym not in by_month:
            by_month[ym] = (p, p)
        else:
            by_month[ym] = (by_month[ym][0], p)
    months = sorted(by_month.keys())[-n_months:]
    rets = []
    for m in months:
        first, last = by_month[m]
        if first > 0:
            rets.append((last - first) / first * 100)
    return rets


def ytd_return(ph: list) -> Optional[float]:
    if not ph or not isinstance(ph, list):
        return None
    cleaned = sorted(
        [(p["date"], float(p["price"])) for p in ph
         if isinstance(p, dict) and p.get("date") and p.get("price") and float(p["price"]) > 0],
        key=lambda x: x[0],
    )
    if len(cleaned) < 2:
        return None
    year = cleaned[-1][0][:4]
    first = None
    for d, p in cleaned:
        if d >= f"{year}-01-01":
            first = p
            break
    if first is None or first <= 0:
        return None
    last = cleaned[-1][1]
    return (last - first) / first * 100


def investor_growth_90d(ph: list) -> Optional[float]:
    """% change in number of investors over last ~90 days."""
    if not ph or not isinstance(ph, list):
        return None
    rows = []
    for p in ph:
        if isinstance(p, dict) and p.get("date") and p.get("investors"):
            try:
                inv = int(p["investors"])
                if inv > 0:
                    rows.append((p["date"], inv))
            except (TypeError, ValueError):
                continue
    if len(rows) < 10:
        return None
    rows.sort(key=lambda x: x[0])
    latest = rows[-1][1]
    # Find row ~90 days earlier
    from datetime import date as date_cls, timedelta
    latest_date = date_cls.fromisoformat(rows[-1][0][:10])
    cutoff = (latest_date - timedelta(days=90)).isoformat()
    older = None
    for d, n in rows:
        if d >= cutoff:
            older = n
            break
    if not older or older <= 0:
        return None
    return (latest - older) / older * 100


def compute_strategies(funds: list[dict]) -> dict[str, Any]:
    out: dict[str, Any] = {}

    # 1. consistent — every month positive in the last 6 months
    consistent: list[tuple[int, dict]] = []
    for f in funds:
        rets = monthly_returns_from_history(f.get("price_history") or [], 6)
        if len(rets) >= 6:
            positives = sum(1 for r in rets if r > 0)
            if positives >= 5:  # 5/6 or 6/6
                consistent.append((positives, f))
    consistent.sort(key=lambda x: (-x[0], -(x[1].get("return_1a") or 0)))
    out["consistent"] = {
        "label": "İstikrarlı Yükselenler",
        "emoji": "🛡",
        "blurb": "Son 6 ay neredeyse her ay pozitif kapatan fonlar",
        "funds": [fund_to_pick(f, "consistency", f"{n}/6 ay ↑") for n, f in consistent[:3]],
    }

    # 2. ytd_stars
    ytd_pool: list[tuple[float, dict]] = []
    for f in funds:
        if (f.get("market_cap") or 0) < 100_000_000:
            continue
        y = ytd_return(f.get("price_history") or [])
        if y is not None and y > 0:
            ytd_pool.append((y, f))
    ytd_pool.sort(key=lambda x: -x[0])
    out["ytd_stars"] = {
        "label": "Bu Yılın Yıldızları",
        "emoji": "🚀",
        "blurb": "Yıl başından beri en çok kazandıran 3 fon",
        "funds": [fund_to_pick(f, "ytd", f"+{y:.1f}% YTD") for y, f in ytd_pool[:3]],
    }

    # 3. risk_adjusted (Sharpe > 1, AUM > 500M)
    ra: list[dict] = []
    for f in funds:
        sh = f.get("sharpe_ratio")
        mc = f.get("market_cap") or 0
        dd = f.get("max_drawdown") or 0
        if sh is not None and sh > 1 and mc > 500_000_000 and (dd is None or dd > -0.30):
            ra.append(f)
    ra.sort(key=lambda x: -(x.get("sharpe_ratio") or 0))
    out["risk_adjusted"] = {
        "label": "Risk Dengeli Şampiyonlar",
        "emoji": "⚖",
        "blurb": "Aldığı her birim risk başına en yüksek getiri",
        "funds": [fund_to_pick(f, "sharpe", f"Sharpe {float(f['sharpe_ratio']):.2f}") for f in ra[:3]],
    }

    # 4. low_vol (vol < 10% + return > 0)
    lv: list[dict] = []
    for f in funds:
        vol = f.get("annualized_volatility")
        ret = f.get("annualized_return")
        if vol is not None and ret is not None and abs(float(vol)) < 0.10 and float(ret) > 0.05:
            lv.append(f)
    lv.sort(key=lambda x: -(x.get("sharpe_ratio") or 0))
    out["low_vol"] = {
        "label": "Düşük Risk Yıldızlı",
        "emoji": "💎",
        "blurb": "Az dalgalanma + pozitif yıllık getiri",
        "funds": [fund_to_pick(f, "low_vol", f"Vol %{float(f['annualized_volatility'])*100:.1f}") for f in lv[:3]],
    }

    # 5. investor_inflow
    inflow: list[tuple[float, dict]] = []
    for f in funds:
        if (f.get("market_cap") or 0) < 50_000_000:
            continue
        g = investor_growth_90d(f.get("price_history") or [])
        if g is not None and g > 5:
            inflow.append((g, f))
    inflow.sort(key=lambda x: -x[0])
    out["investor_inflow"] = {
        "label": "Yatırımcı Akını",
        "emoji": "🧗",
        "blurb": "Son 90 günde yatırımcı sayısı patlayan fonlar",
        "funds": [fund_to_pick(f, "investor_growth", f"+%{g:.1f} yatırımcı") for g, f in inflow[:3]],
    }

    # 6. hidden_gem (small AUM, high Sharpe)
    hg: list[dict] = []
    for f in funds:
        sh = f.get("sharpe_ratio")
        mc = f.get("market_cap") or 0
        if sh is not None and sh > 1.5 and 10_000_000 <= mc < 200_000_000:
            hg.append(f)
    hg.sort(key=lambda x: -(x.get("sharpe_ratio") or 0))
    out["hidden_gem"] = {
        "label": "Gizli Cevher",
        "emoji": "🔍",
        "blurb": "Küçük AUM, yüksek Sharpe — radar altı",
        "funds": [fund_to_pick(f, "hidden_gem", f"Sharpe {float(f['sharpe_ratio']):.2f}") for f in hg[:3]],
    }

    return out


# ─────────────────────────────────────────────────────────────────────
# THEME computer
# ─────────────────────────────────────────────────────────────────────
def compute_themes(etfs: list[dict]) -> dict[str, Any]:
    by_symbol = {e["symbol"]: e for e in etfs}
    out: dict[str, Any] = {}
    for slug, meta in THEMES.items():
        members = [by_symbol[t] for t in meta["tickers"] if t in by_symbol]
        if not members:
            continue
        # Rank by AUM descending
        members.sort(key=lambda e: -(e.get("aum") or 0))
        out[slug] = {
            "label": meta["label"],
            "emoji": meta["emoji"],
            "blurb": meta["blurb"],
            "etfs": [
                etf_to_pick(
                    e,
                    "theme",
                    f"${(e.get('aum') or 0) / 1e9:.1f}B Fon Büyüklüğü"
                )
                for e in members[:3]
            ],
        }
    return out


# ─────────────────────────────────────────────────────────────────────
# PERSONA computer
# ─────────────────────────────────────────────────────────────────────
def compute_personas(funds: list[dict]) -> dict[str, Any]:
    out: dict[str, Any] = {}

    # Beginner — düşük gider + AUM>500M + PPF/BAF/KMF (düşük risk kategoriler)
    beginner_pool = [
        f for f in funds
        if f.get("fund_type") in {"PPF", "BAF", "KMF"}
        and (f.get("market_cap") or 0) > 500_000_000
        and (f.get("management_fee") is None or float(f.get("management_fee") or 0) < 1.5)
    ]
    beginner_pool.sort(
        key=lambda f: (
            -(f.get("sharpe_ratio") or 0),
            float(f.get("management_fee") or 99),
        )
    )
    out["beginner"] = {
        **PERSONAS["beginner"],
        "funds": [
            fund_to_pick(f, "beginner_friendly", f"Gider %{float(f.get('management_fee') or 0):.2f}")
            for f in beginner_pool[:3]
        ],
    }

    # Saver — KMF + DÖVİZ + düşük vol + 1Y positive
    saver_pool = [
        f for f in funds
        if f.get("fund_type") in {"KMF", "DÖVİZ", "BAF"}
        and f.get("annualized_volatility") is not None
        and abs(float(f["annualized_volatility"])) < 0.25
        and (f.get("annualized_return") or 0) > 0.10
    ]
    saver_pool.sort(key=lambda f: -(f.get("sharpe_ratio") or 0))
    out["saver"] = {
        **PERSONAS["saver"],
        "funds": [
            fund_to_pick(
                f,
                "balanced_growth",
                f"Yıllık %{float(f.get('annualized_return') or 0) * 100:.1f}",
            )
            for f in saver_pool[:3]
        ],
    }

    # Retirement — OKS + uzun vade pozitif
    retirement_pool = [
        f for f in funds
        if f.get("fund_type") in {"OKS", "BAF", "KFF"}
        and (f.get("return_3a") or 0) > 0.50
    ]
    retirement_pool.sort(key=lambda f: -(f.get("return_3a") or 0))
    out["retirement"] = {
        **PERSONAS["retirement"],
        "funds": [
            fund_to_pick(
                f,
                "long_term",
                f"3Y +%{(f.get('return_3a') or 0) * 100:.0f}",
            )
            for f in retirement_pool[:3]
        ],
    }

    # Trader — high vol + momentum
    trader_pool = [
        f for f in funds
        if (f.get("annualized_volatility") or 0) > 0.20
        and (f.get("monthly") or 0) > 5
        and (f.get("market_cap") or 0) > 100_000_000
    ]
    trader_pool.sort(key=lambda f: -(f.get("monthly") or 0))
    out["trader"] = {
        **PERSONAS["trader"],
        "funds": [
            fund_to_pick(
                f,
                "momentum",
                f"1A +%{float(f.get('monthly') or 0):.1f}",
            )
            for f in trader_pool[:3]
        ],
    }
    return out


# ─────────────────────────────────────────────────────────────────────
# HEDGE computer
# ─────────────────────────────────────────────────────────────────────
def compute_hedges(funds: list[dict]) -> dict[str, Any]:
    out: dict[str, Any] = {}

    # Inflation — ALTIN + Eurobond + Endeksli
    inflation_pool = [
        f for f in funds
        if f.get("fund_type") in {"ALTIN", "DÖVİZ"}
        and (f.get("market_cap") or 0) > 100_000_000
    ]
    inflation_pool.sort(key=lambda f: -(f.get("return_1a") or 0))
    out["inflation"] = {
        "label": "Enflasyon Kalkanı",
        "emoji": "🔥",
        "blurb": "Altın + döviz + eurobond — TL erozyonuna karşı",
        "funds": [
            fund_to_pick(
                f,
                "inflation_hedge",
                f"{f.get('fund_type')}: +%{(f.get('return_1a') or 0) * 100:.1f} 1Y",
            )
            for f in inflation_pool[:3]
        ],
    }

    # FX hedge — DÖVİZ + BAF Eurobond
    fx_pool = [
        f for f in funds
        if f.get("fund_type") == "DÖVİZ"
        or (f.get("fund_type") == "BAF" and "eurobond" in (f.get("name") or "").lower())
    ]
    fx_pool.sort(key=lambda f: -(f.get("return_1a") or 0))
    out["fx"] = {
        "label": "Kur Hedge",
        "emoji": "💵",
        "blurb": "Eurobond + döviz cinsinden borçlanma — devalüasyon koruması",
        "funds": [
            fund_to_pick(
                f,
                "fx_hedge",
                f"+%{(f.get('return_1a') or 0) * 100:.1f} 1Y",
            )
            for f in fx_pool[:3]
        ],
    }

    # Crisis-resilient — low beta + low DD + AUM > 1B
    crisis_pool = [
        f for f in funds
        if f.get("beta") is not None
        and abs(float(f["beta"])) < 0.5
        and f.get("max_drawdown") is not None
        and float(f["max_drawdown"]) > -0.15
        and (f.get("market_cap") or 0) > 1_000_000_000
    ]
    crisis_pool.sort(key=lambda f: -(f.get("sharpe_ratio") or 0))
    out["crisis"] = {
        "label": "Krize Dayanıklı",
        "emoji": "🌪",
        "blurb": "Düşük beta + düşük drawdown + büyük fonlar",
        "funds": [
            fund_to_pick(
                f,
                "crisis_resilient",
                f"Beta {float(f.get('beta') or 0):.2f}",
            )
            for f in crisis_pool[:3]
        ],
    }
    return out


# ─────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────
def main() -> int:
    log("compute_smart_picks starting")
    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    funds = load_funds(cur)
    log(f"  funds loaded: {len(funds)}")
    etfs = load_etfs(cur)
    log(f"  etfs loaded: {len(etfs)}")

    payload = {
        "strategies": compute_strategies(funds),
        "themes": compute_themes(etfs),
        "personas": compute_personas(funds),
        "hedges": compute_hedges(funds),
        "computed_at": datetime.now(timezone.utc).isoformat(),
    }

    for section in ("strategies", "themes", "personas", "hedges"):
        n_lists = len(payload[section])
        n_items = sum(len(v.get("funds") or v.get("etfs") or []) for v in payload[section].values())
        log(f"  {section:<12} {n_lists} lists × {n_items} items")

    # Make sure the column exists
    cur2 = conn.cursor()
    cur2.execute(
        "ALTER TABLE homepage_stats ADD COLUMN IF NOT EXISTS smart_picks JSONB"
    )
    cur2.execute(
        "UPDATE homepage_stats SET smart_picks = %s WHERE id = 1",
        (json.dumps(payload),),
    )
    conn.commit()
    log("homepage_stats.smart_picks updated")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
