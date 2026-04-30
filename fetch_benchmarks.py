#!/usr/bin/env python3
"""
Fetch benchmark index data from Yahoo Finance.
- USD/TRY exchange rate: USTODAY
- Gold futures: GC=F
- BIST100: ^XU100

Saves to data/benchmarks.json with structure:
{
  "usd_try": [{ "date": "2025-01-15", "price": 30.5 }, ...],
  "gold": [...],
  "bist100": [...]
}
"""
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

PROJECT_DIR = Path(__file__).parent
DATA_DIR = PROJECT_DIR / "data"
BENCHMARK_FILE = DATA_DIR / "benchmarks.json"

# Try yfinance, fall back to requests if not installed
try:
    import yfinance as yf
    HAS_YFINANCE = True
except ImportError:
    HAS_YFINANCE = False

BENCHMARKS = {
    "usd_try": "TRY=X",
    "gold": "GC=F",
    "bist100": "XU100.IS",
}

BENCHMARK_LABELS = {
    "usd_try": "USD/TRY",
    "gold": "Altın (GC=F)",
    "bist100": "BIST100",
}


def parse_date(ds):
    """Parse yfinance date string to YYYY-MM-DD."""
    if isinstance(ds, str):
        return ds[:10]
    if hasattr(ds, 'strftime'):
        return ds.strftime("%Y-%m-%d")
    return str(ds)[:10]


def fetch_benchmark(ticker: str, days: int = 365) -> list[dict]:
    """Fetch daily price data for a ticker."""
    if not HAS_YFINANCE:
        return []

    try:
        data = yf.Ticker(ticker).history(period=f"{days}d", interval="1d")
        if data.empty:
            return []
        result = []
        for idx, row in data.iterrows():
            price = float(row["Close"])
            if price > 0:
                result.append({
                    "date": parse_date(idx),
                    "price": round(price, 4),
                })
        return result
    except Exception as e:
        print(f"  ERROR fetching {ticker}: {e}", file=sys.stderr)
        return []


def main():
    print("Fetching benchmark data from Yahoo Finance...")
    print(f"Using yfinance: {HAS_YFINANCE}")

    # Load existing data to merge
    existing = {}
    if BENCHMARK_FILE.exists():
        with open(BENCHMARK_FILE, "r") as f:
            existing = json.load(f)

    results = {}
    for key, ticker in BENCHMARKS.items():
        label = BENCHMARK_LABELS[key]
        print(f"\n[{key}] {label} ({ticker})...")
        new_data = fetch_benchmark(ticker, days=730)  # fetch 2 years
        print(f"  Got {len(new_data)} price points")

        # Merge: replace old dates with new data
        if new_data:
            existing_dates = set(d["date"] for d in existing.get(key, []))
            merged = existing.get(key, [])
            for point in new_data:
                if point["date"] not in existing_dates:
                    merged.append(point)
            # Sort by date
            merged.sort(key=lambda x: x["date"])
            results[key] = merged
        else:
            results[key] = existing.get(key, [])

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(BENCHMARK_FILE, "w") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    total = sum(len(v) for v in results.values())
    print(f"\nSaved {total} benchmark records to {BENCHMARK_FILE}")
    print("Keys:", list(results.keys()))


if __name__ == "__main__":
    main()
