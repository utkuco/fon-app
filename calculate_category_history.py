#!/usr/bin/env python3
"""
Calculate historical category average price index from fund price histories.
Reads from Supabase REST API, writes to data/category_history.json

Each category's avg_price_index = normalized average price of all funds in that category,
normalized so that period-start = 100 (like a market index).
"""

import json
import os
import requests
from collections import defaultdict
from datetime import datetime, date

SUPABASE_URL = "https://oqkobptbvcazifpvjwfz.supabase.co"
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "sb_secret_PkAEAOU2YO4YS-ELYpwS5w_SsVg2kqi")
HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
}


def parse_date(s):
    if isinstance(s, date):
        return s
    return datetime.strptime(str(s)[:10], "%Y-%m-%d").date()


def fetch_all(table: str, select: str, batch=1000, offset=0):
    """Paginated fetch from Supabase REST API."""
    rows = []
    while True:
        url = f"{SUPABASE_URL}/rest/v1/{table}?select={select}&limit={batch}&offset={offset}"
        resp = requests.get(url, headers=HEADERS, timeout=30)
        resp.raise_for_status()
        batch = resp.json()
        if not batch:
            break
        rows.extend(batch)
        offset += len(batch)
        print(f"    fetched {len(rows)} rows...")
        if len(batch) < 1000:
            break
    return rows


def main():
    print("Fetching funds with price_history from Supabase...")
    funds = fetch_all("funds", "code,fund_type,price_history")
    print(f"  Got {len(funds)} funds")

    # Group price history by fund_type
    by_type: dict = defaultdict(lambda: defaultdict(list))

    for fund in funds:
        ftype = fund.get("fund_type") or "OTHER"
        ph = fund.get("price_history") or []
        if not ph:
            continue
        sorted_ph = sorted(ph, key=lambda p: str(p.get("date", "")))
        for p in sorted_ph:
            d = parse_date(p.get("date"))
            price = float(p.get("price") or 0)
            if price > 0:
                by_type[ftype][d].append(price)

    fund_types = sorted(by_type.keys())
    all_dates = set()
    for ft_data in by_type.values():
        all_dates.update(ft_data.keys())

    if not all_dates:
        print("No data found!")
        return

    print(f"  Date range: {min(all_dates)} → {max(all_dates)}")
    print(f"  Fund types: {', '.join(fund_types)}")

    category_history = {}

    for ftype in fund_types:
        date_prices = by_type[ftype]
        type_dates = sorted(date_prices.keys())
        if len(type_dates) < 2:
            continue

        # Daily average price
        daily_avg_prices = [(d, sum(date_prices[d]) / len(date_prices[d])) for d in type_dates]

        # Normalize to index (base = first day's avg price = 100)
        base_price = daily_avg_prices[0][1]
        indexed = [(d, round((avg / base_price) * 100, 4)) for d, avg in daily_avg_prices]

        # Daily return %
        records = []
        for i, (d, idx) in enumerate(indexed):
            if i == 0:
                ret = 0.0
            else:
                prev = indexed[i - 1][1]
                ret = round((idx - prev) / prev * 100, 6) if prev != 0 else 0.0
            records.append({
                "date": d.isoformat(),
                "avg_price_index": idx,
                "avg_return": ret,
            })

        category_history[ftype] = records
        print(f"  {ftype}: {len(records)} points, base={base_price:.4f}, latest_index={records[-1]['avg_price_index']:.2f}")

    # Write output
    out_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "category_history.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(category_history, f, ensure_ascii=False, indent=2)

    print(f"\nWritten: {out_path}")
    total = sum(len(v) for v in category_history.values())
    print(f"Total records: {total}")


if __name__ == "__main__":
    main()
