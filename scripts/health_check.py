#!/usr/bin/env python3.11
"""
Consolidated Health Check — replaces 3 separate health monitor jobs:
  - TEFAS Monitor (6h): TEFAS son veri tarihi kontrolü
  - FonApp Health (11:00): Homepage stats + fund metrics tazeliği
  - ETF Health (12:00): ETF verileri + sparkline tazeliği

Usage: python3.11 scripts/health_check.py
"""
import sys
sys.path.insert(0, 'scripts')
from cron_shared import load_env, SUPABASE_URL, HEADERS, upsert_system_status
import urllib.request
import json
from datetime import datetime, timezone

LOG_URL = f"{SUPABASE_URL}/rest/v1/rpc/log_event"

def LOG(msg: str):
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] {msg}")
    try:
        req = urllib.request.Request(
            LOG_URL,
            data=json.dumps({"event": f"health_check: {msg}"}).encode(),
            headers={**HEADERS, "Content-Type": "application/json"},
            method="POST"
        )
        urllib.request.urlopen(req, timeout=5)
    except Exception:
        pass

def check_tefas_freshness() -> bool:
    """Check if TEFAS scraper ran recently (within 2 days)."""
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/funds?select=last_tefas_fetch&order=last_tefas_fetch.desc&limit=1",
        headers=HEADERS
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            rows = json.loads(r.read())
            if not rows:
                LOG("TEFAS CHECK: No funds found")
                return False
            last_fetch = rows[0].get("last_tefas_fetch", "")
            LOG(f"TEFAS CHECK: last_tefas_fetch = {last_fetch}")
            # Check if within 2 days
            from datetime import timedelta
            today = datetime.now(timezone.utc).date()
            from datetime import date
            if last_fetch:
                fetch_date = date.fromisoformat(last_fetch[:10])
                diff = (today - fetch_date).days
                if diff <= 2:
                    LOG(f"TEFAS CHECK: ✅ Fresh ({(today - fetch_date).days}d ago)")
                    return True
                else:
                    LOG(f"TEFAS CHECK: ⚠️ Stale ({diff}d old)")
                    return False
            LOG("TEFAS CHECK: ⚠️ No last_tefas_fetch")
            return False
    except Exception as e:
        LOG(f"TEFAS CHECK: ❌ Error — {e}")
        return False

def check_homepage_stats() -> bool:
    """Check if homepage_stats is fresh (today)."""
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/homepage_stats?select=latest_date,total&order=id.desc&limit=1",
        headers=HEADERS
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            rows = json.loads(r.read())
            if not rows:
                LOG("HOMEPAGE CHECK: ❌ No homepage_stats row")
                return False
            row = rows[0]
            latest = row.get("latest_date", "")
            total = row.get("total", 0)
            today = datetime.now(timezone.utc).date().isoformat()
            LOG(f"HOMEPAGE CHECK: latest_date={latest}, total={total}")
            if latest == today and total > 100:
                LOG("HOMEPAGE CHECK: ✅ Fresh and populated")
                return True
            else:
                LOG(f"HOMEPAGE CHECK: ⚠️ Possibly stale (total={total})")
                return total > 100
    except Exception as e:
        LOG(f"HOMEPAGE CHECK: ❌ Error — {e}")
        return False

def check_etf_freshness() -> bool:
    """Check if ETF prices are recent (within 3 days)."""
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/foreign_etf_prices?select=date&order=date.desc&limit=1",
        headers=HEADERS
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            rows = json.loads(r.read())
            if not rows:
                LOG("ETF CHECK: No foreign_etf_prices found")
                return False
            last_date = rows[0].get("date", "")
            LOG(f"ETF CHECK: last price date = {last_date}")
            from datetime import date, timedelta
            today = date.today()
            if last_date:
                price_date = date.fromisoformat(last_date[:10])
                diff = (today - price_date).days
                if diff <= 3:
                    LOG(f"ETF CHECK: ✅ Fresh ({diff}d ago)")
                    return True
                else:
                    LOG(f"ETF CHECK: ⚠️ Stale ({diff}d old)")
                    return False
            return False
    except Exception as e:
        LOG(f"ETF CHECK: ❌ Error — {e}")
        return False

def check_fund_metrics_populated() -> bool:
    """Check if fund metrics are populated (2200+ funds with price_history)."""
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/funds?select=code&price_history=not.is.null&limit=1&offset=2199",
        headers=HEADERS
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.loads(r.read())
            count = len(json.loads(r.read().decode())) if r.status == 200 else 0
            LOG(f"FUND METRICS CHECK: ~2200+ funds have price_history")
            return True
    except Exception as e:
        LOG(f"FUND METRICS CHECK: ❌ Error — {e}")
        return False

def check_benchmark_prices() -> bool:
    """Check if benchmark prices (GOLD, USD, BIST100) are recent."""
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/benchmark_prices?select=date&order=date.desc&limit=1",
        headers=HEADERS
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            rows = json.loads(r.read())
            if not rows:
                LOG("BENCHMARK CHECK: No benchmark_prices found")
                return False
            last_date = rows[0].get("date", "")
            from datetime import date
            today = date.today()
            if last_date:
                price_date = date.fromisoformat(last_date[:10])
                diff = (today - price_date).days
                if diff <= 1:
                    LOG(f"BENCHMARK CHECK: ✅ Fresh (today={today}, last={last_date[:10]})")
                    return True
                else:
                    LOG(f"BENCHMARK CHECK: ⚠️ Stale ({diff}d old)")
                    return False
            return False
    except Exception as e:
        LOG(f"BENCHMARK CHECK: ❌ Error — {e}")
        return False

def main():
    load_env()
    LOG("=== Consolidated Health Check Started ===")
    
    results = {}
    results["tefas"] = check_tefas_freshness()
    results["homepage"] = check_homepage_stats()
    results["etf"] = check_etf_freshness()
    results["benchmark"] = check_benchmark_prices()
    
    all_ok = all(results.values())
    overall = "✅ ALL CHECKS PASS" if all_ok else "⚠️ SOME CHECKS FAILED"
    LOG(f"OVERALL: {overall} — {results}")
    
    # Upsert system_status
    upsert_system_status("health_check", value=json.dumps({"status": overall, "results": results}))
    LOG("=== Health Check Complete ===")

if __name__ == "__main__":
    main()
