#!/usr/bin/env python3
"""
risk_free_rates.py — Fetch USD/EUR/TRY risk-free rates and write to system_rates table.

Schedule (launchd):  Mon-Fri 00:05 UTC = 03:05 TR
Usage:               python3 scripts/risk_free_rates.py

Logic:
  - USD  → Yahoo Finance ^IRX (3-month T-bill annualized yield)
  - TRY  → fallback 0.45 (45% annualized, TCMB policy rate proxy)
  - EUR  → fallback 0.0  (no reliable free API)
"""

import sys
import time
from datetime import datetime
from pathlib import Path

# Add scripts/ to path for cron_shared
sys.path.insert(0, str(Path(__file__).parent))

from cron_shared import (
    load_env, SUPABASE_URL, SUPABASE_KEY, HEADERS, upsert_system_status,
    upsert_table, get_logger,
)
import urllib.request
import json

LOG = get_logger("risk_free_rates")


def fetch_yahoo_json(url: str, timeout: int = 15) -> dict:
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0",
            "Accept": "application/json",
        })
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read())
    except Exception as e:
        LOG(f"Yahoo fetch failed: {e}", "WARN")
        return {}


def fetch_usd_rate() -> tuple[float, str]:
    """Fetch USD 3-month T-bill annualized yield from Yahoo ^IRX."""
    ticker = "^IRX"
    period2 = int(time.time())
    period1 = period2 - 7 * 86400
    url = (
        f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
        f"?period1={period1}&period2={period2}&interval=1d&events=history"
    )
    data = fetch_yahoo_json(url)
    quotes = (
        data.get("chart", {})
        .get("result", [{}])[0]
        .get("indicators", {})
        .get("quote", [{}])[0]
        .get("close", [])
    )
    closes = [c for c in quotes if c is not None and c > 0]
    if not closes:
        return 0.0, "fallback"
    # ^IRX returns annualized percentage, e.g. 5.25 = 5.25%
    # Convert to decimal for use in formulas: 0.0525
    latest = closes[-1]
    rate = round(latest / 100, 6)
    LOG(f"USD ^IRX = {latest}% → annualized {rate}")
    return rate, f"yahoo:{ticker}"


def main():
    load_env()
    LOG("Starting risk_free_rates cron")
    start = time.time()

    # TRY: no reliable free API — use TCMB policy rate proxy
    try_rate = 0.45
    # EUR: no reliable free API — keep at 0
    eur_rate = 0.0

    # USD: fetch from Yahoo
    usd_rate, usd_source = fetch_usd_rate()

    rows = [
        {
            "currency": "TRY",
            "rate_annualized": try_rate,
            "source": "fallback:tcnb_proxy",
            "updated_at": datetime.utcnow().isoformat(),
        },
        {
            "currency": "USD",
            "rate_annualized": usd_rate,
            "source": usd_source,
            "updated_at": datetime.utcnow().isoformat(),
        },
        {
            "currency": "EUR",
            "rate_annualized": eur_rate,
            "source": "fallback",
            "updated_at": datetime.utcnow().isoformat(),
        },
    ]

    ok = upsert_table("system_rates", rows, conflict_col="currency")
    if ok:
        LOG("system_rates updated successfully")
    else:
        LOG("system_rates upsert FAILED", "ERROR")

    elapsed = round(time.time() - start, 1)
    upsert_system_status(
        "last_risk_free_rates_cron",
        datetime.utcnow().isoformat(),
        "success",
        f"USD={usd_rate:.4f} ({usd_source}), TRY={try_rate}, EUR={eur_rate} in {elapsed}s",
    )
    LOG(f"Done in {elapsed}s")


if __name__ == "__main__":
    main()
