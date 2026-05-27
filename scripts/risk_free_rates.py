#!/usr/bin/env python3
"""
risk_free_rates.py — Refresh system_rates with annualized risk-free rates.

Ports the deleted Vercel route src/app/api/old_files/risk-free-rates-cron/route.ts
(commit c55f37b, 2026-05-08). Runs on the Mac so the Yahoo call goes from a TR
IP — US-hosted egress sometimes gets blocked.

Sources:
  USD → ^IRX (Yahoo, 3-month T-bill annualized yield, already %)
  TRY → 0.45 fallback (TCMB policy rate proxy)
  EUR → 0.0 fallback (no reliable free feed)

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

    ok_usd = upsert_rate("USD", usd_rate, usd_source)
    ok_try = upsert_rate("TRY", 0.45, "fallback:tcnb_proxy")
    ok_eur = upsert_rate("EUR", 0.0, "fallback")

    elapsed = round(time.time() - start, 1)
    LOG(f"Done in {elapsed}s — USD={usd_rate:.4f} ({usd_source}), TRY=0.45, EUR=0.0")
    LOG(f"  upsert ok: USD={ok_usd} TRY={ok_try} EUR={ok_eur}")

    upsert_system_status(
        "last_risk_free_rates_cron",
        datetime.now(timezone.utc).isoformat(),
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
