#!/usr/bin/env python3
"""
risk_free_rates.py — Refresh system_rates with annualized risk-free rates.

Sources:
  USD → ^IRX (Yahoo, 3-month T-bill annualized yield, already %)
  TRY → TCMB.gov.tr homepage scrape (1-week repo policy rate). Falls back
        to the last persisted value when the scrape fails — the rate only
        moves on PPK meeting days so a 1-2 day staleness is harmless.
  EUR → 0.0 fallback (no reliable free feed)

The TRY rate had been hardcoded at 0.45 ("fallback:tcnb_proxy") for months
while the actual policy rate fell to 37% — every Sharpe / Sortino computed
in fund_metrics used the stale number as the risk-free anchor, biasing
risk-adjusted returns lower across every fund.

Schedule (launchd): daily 00:05 UTC (03:05 TR)
"""

import json
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent))

from cron_shared import (
    SUPABASE_URL,
    HEADERS,
    load_env,
    rest_post,
    upsert_system_status,
    get_logger,
)

load_env()
LOG = get_logger("risk_free_rates")


def fetch_usd_rate() -> tuple[float, str]:
    """Last close of ^IRX (3-month T-bill yield) as a ratio (e.g. 5.25 → 0.0525)."""
    end = int(time.time())
    start = end - 7 * 86400
    url = (
        "https://query1.finance.yahoo.com/v8/finance/chart/%5EIRX"
        f"?period1={start}&period2={end}&interval=1d&events=history"
    )
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
    except Exception as e:  # noqa: BLE001
        LOG(f"  USD ^IRX fetch failed: {e}", "WARN")
        return 0.0, "fallback"

    try:
        quotes = (
            data["chart"]["result"][0]
            ["indicators"]["quote"][0]
            ["close"]
        )
    except (KeyError, IndexError, TypeError):
        LOG("  USD ^IRX: unexpected payload shape", "WARN")
        return 0.0, "fallback"

    closes = [c for c in quotes if c is not None]
    if not closes:
        LOG("  USD ^IRX: no quotes", "WARN")
        return 0.0, "fallback"

    latest = closes[-1]
    rate = latest / 100  # ^IRX is already in % → convert to ratio
    LOG(f"  USD ^IRX = {latest}% → {rate} annualized")
    return rate, "yahoo:^IRX"


def fetch_try_rate() -> tuple[float, str]:
    """Scrape the TCMB policy rate from tcmb.gov.tr home page.

    The PPK announcement text on the homepage looks like:
        '...politika faizi olan bir hafta vadeli repo ihale faiz oranının
         yüzde 37&rsquo;de sabit tutulmasına karar vermiştir.'
    so we grep for `politika faizi … yüzde N`."""
    import re
    try:
        req = urllib.request.Request(
            "https://www.tcmb.gov.tr/",
            headers={"User-Agent": "Mozilla/5.0", "Accept-Language": "tr-TR,tr;q=0.9"},
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            body = resp.read().decode("utf-8", errors="ignore")
    except Exception as e:  # noqa: BLE001
        LOG(f"  TRY tcmb fetch failed: {e}", "WARN")
        return _last_try_rate()
    m = re.search(
        r"politika faizi[^%]{0,160}?yüzde\s*(\d{1,2}(?:[.,]\d{1,2})?)",
        body,
        re.IGNORECASE,
    )
    if not m:
        LOG("  TRY: 'politika faizi … yüzde N' kalıbı eşleşmedi", "WARN")
        return _last_try_rate()
    raw = m.group(1).replace(",", ".")
    try:
        pct = float(raw)
    except ValueError:
        LOG(f"  TRY: '{raw}' parse edilemedi", "WARN")
        return _last_try_rate()
    if not 5 <= pct <= 150:
        LOG(f"  TRY: %{pct} mantıksız (5-150 aralığı dışı), fallback'e dönülüyor", "WARN")
        return _last_try_rate()
    rate = pct / 100
    LOG(f"  TRY TCMB politika faizi = {pct}% → {rate} annualized")
    return rate, f"tcmb:policy_rate"


def _last_try_rate() -> tuple[float, str]:
    """Best-effort fallback: keep the last persisted TRY rate so a transient
    TCMB outage doesn't reset Sharpe/Sortino calcs across the site."""
    import urllib.parse
    try:
        url = f"{SUPABASE_URL}/rest/v1/system_rates?currency=eq.TRY&select=rate_annualized&limit=1"
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=10) as resp:
            rows = json.loads(resp.read())
        if rows and rows[0].get("rate_annualized") is not None:
            v = float(rows[0]["rate_annualized"])
            return v, "preserved:last_known"
    except Exception:
        pass
    return 0.37, "fallback:tcmb_2026"


def upsert_rate(currency: str, rate: float, source: str) -> bool:
    url = f"{SUPABASE_URL}/rest/v1/system_rates?on_conflict=currency"
    payload = [{
        "currency": currency,
        "rate_annualized": rate,
        "source": source,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }]
    return rest_post(url, payload, conflict_col="currency")


def main() -> int:
    start = time.time()
    LOG("Starting risk_free_rates")

    usd_rate, usd_source = fetch_usd_rate()
    try_rate, try_source = fetch_try_rate()

    ok_usd = upsert_rate("USD", usd_rate, usd_source)
    ok_try = upsert_rate("TRY", try_rate, try_source)
    ok_eur = upsert_rate("EUR", 0.0, "fallback")

    elapsed = round(time.time() - start, 1)
    LOG(
        f"Done in {elapsed}s — USD={usd_rate:.4f} ({usd_source}), "
        f"TRY={try_rate:.4f} ({try_source}), EUR=0.0"
    )
    LOG(f"  upsert ok: USD={ok_usd} TRY={ok_try} EUR={ok_eur}")

    upsert_system_status(
        "last_risk_free_rates_cron",
        datetime.now(timezone.utc).isoformat(),
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
