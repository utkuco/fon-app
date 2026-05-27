#!/usr/bin/env python3.11
"""
health_check.py — Daily sanity check across the data pipeline.

Looks at the underlying data tables (not the cron's self-reported timestamps)
and decides whether each pipeline is ok. Result is JSON-encoded into
system_status.health_check so the /admin/system page can render it.

Each check returns one of:
  - "ok"     fresh within its tolerance
  - "stale"  past tolerance but the table has rows
  - "empty"  expected rows missing
  - "error"  query failed
"""

import json
import sys
import urllib.request
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent))

from cron_shared import (
    SUPABASE_URL,
    HEADERS,
    load_env,
    upsert_system_status,
    get_logger,
)

load_env()
LOG = get_logger("health_check")


def _rest(url: str, timeout: int = 10) -> list:
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        body = r.read()
        return json.loads(body) if body else []


def _days_since(iso: Optional[str]) -> Optional[int]:
    if not iso:
        return None
    try:
        d = date.fromisoformat(iso[:10])
        return (date.today() - d).days
    except Exception:
        return None


def _classify(days: Optional[int], max_days: int) -> str:
    if days is None:
        return "empty"
    return "ok" if days <= max_days else "stale"


# ─── Individual checks ───────────────────────────────────────────────────────

def check_tefas() -> dict:
    try:
        rows = _rest(
            f"{SUPABASE_URL}/rest/v1/funds?select=last_tefas_fetch"
            f"&order=last_tefas_fetch.desc&limit=1"
        )
        latest = rows[0].get("last_tefas_fetch") if rows else None
        days = _days_since(latest)
        return {"status": _classify(days, 2), "latest": latest, "days_old": days}
    except Exception as e:  # noqa: BLE001
        return {"status": "error", "error": str(e)}


def check_etf_prices() -> dict:
    try:
        rows = _rest(
            f"{SUPABASE_URL}/rest/v1/foreign_etf_prices?select=date"
            f"&order=date.desc&limit=1"
        )
        latest = rows[0].get("date") if rows else None
        days = _days_since(latest)
        return {"status": _classify(days, 3), "latest": latest, "days_old": days}
    except Exception as e:  # noqa: BLE001
        return {"status": "error", "error": str(e)}


def check_benchmark_prices() -> dict:
    try:
        rows = _rest(
            f"{SUPABASE_URL}/rest/v1/benchmark_prices?select=date"
            f"&order=date.desc&limit=1"
        )
        latest = rows[0].get("date") if rows else None
        days = _days_since(latest)
        return {"status": _classify(days, 3), "latest": latest, "days_old": days}
    except Exception as e:  # noqa: BLE001
        return {"status": "error", "error": str(e)}


def check_homepage_stats() -> dict:
    try:
        rows = _rest(
            f"{SUPABASE_URL}/rest/v1/homepage_stats?select=updated_at,total&limit=1"
        )
        if not rows:
            return {"status": "empty"}
        latest = rows[0].get("updated_at")
        total = rows[0].get("total") or 0
        days = _days_since(latest)
        status = _classify(days, 1)
        if status == "ok" and total < 100:
            status = "stale"
        return {"status": status, "latest": latest, "days_old": days, "total": total}
    except Exception as e:  # noqa: BLE001
        return {"status": "error", "error": str(e)}


def check_fund_metrics() -> dict:
    try:
        rows = _rest(
            f"{SUPABASE_URL}/rest/v1/fund_metrics?select=updated_at"
            f"&order=updated_at.desc&limit=1"
        )
        latest = rows[0].get("updated_at") if rows else None
        days = _days_since(latest)
        return {"status": _classify(days, 2), "latest": latest, "days_old": days}
    except Exception as e:  # noqa: BLE001
        return {"status": "error", "error": str(e)}


def check_system_rates() -> dict:
    try:
        rows = _rest(
            f"{SUPABASE_URL}/rest/v1/system_rates?select=currency,rate_annualized,updated_at"
        )
        if not rows:
            return {"status": "empty"}
        latest = max((r.get("updated_at") for r in rows if r.get("updated_at")), default=None)
        days = _days_since(latest)
        return {
            "status": _classify(days, 2),
            "latest": latest,
            "days_old": days,
            "currencies": {r["currency"]: float(r.get("rate_annualized") or 0) for r in rows},
        }
    except Exception as e:  # noqa: BLE001
        return {"status": "error", "error": str(e)}


def check_foreign_etfs_metadata() -> dict:
    try:
        rows = _rest(
            f"{SUPABASE_URL}/rest/v1/foreign_etfs?select=updated_at"
            f"&is_active=eq.true&order=updated_at.desc&limit=1"
        )
        latest = rows[0].get("updated_at") if rows else None
        days = _days_since(latest)
        # Weekly cron — 8 day tolerance.
        return {"status": _classify(days, 8), "latest": latest, "days_old": days}
    except Exception as e:  # noqa: BLE001
        return {"status": "error", "error": str(e)}


def check_kap_portfolio() -> dict:
    try:
        rows = _rest(
            f"{SUPABASE_URL}/rest/v1/portfolio_breakdown?select=report_date"
            f"&order=report_date.desc&limit=1"
        )
        latest = rows[0].get("report_date") if rows else None
        days = _days_since(latest)
        # KAP only posts when funds publish portfolios — can legitimately go
        # quiet for weeks. 14 days is generous but anything beyond means the
        # pipeline itself is dead.
        return {"status": _classify(days, 14), "latest": latest, "days_old": days}
    except Exception as e:  # noqa: BLE001
        return {"status": "error", "error": str(e)}


# ─── Driver ──────────────────────────────────────────────────────────────────

def main() -> int:
    LOG("=== health_check starting ===")

    results = {
        "tefas": check_tefas(),
        "etf_prices": check_etf_prices(),
        "benchmark_prices": check_benchmark_prices(),
        "homepage_stats": check_homepage_stats(),
        "fund_metrics": check_fund_metrics(),
        "system_rates": check_system_rates(),
        "etf_metadata": check_foreign_etfs_metadata(),
        "kap_portfolio": check_kap_portfolio(),
    }

    for name, r in results.items():
        status = r.get("status")
        days = r.get("days_old")
        suffix = f" ({days}d)" if days is not None else ""
        LOG(f"  {name:18s} → {status}{suffix}")

    statuses = [r.get("status") for r in results.values()]
    if all(s == "ok" for s in statuses):
        overall = "✅ ALL CHECKS PASS"
    elif any(s == "error" for s in statuses):
        overall = "❌ ERROR IN ONE OR MORE CHECKS"
    else:
        overall = "⚠️ SOME CHECKS FAILED"

    LOG(f"OVERALL: {overall}")

    upsert_system_status(
        "health_check",
        value=json.dumps({
            "status": overall,
            "results": results,
            "checked_at": datetime.now(timezone.utc).isoformat(),
        }),
    )

    LOG("=== health_check done ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
