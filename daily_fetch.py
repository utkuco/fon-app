#!/usr/bin/env python3
"""
KAP Daily Portfolio Fetcher
============================
Fetches yesterday's portfolio distribution reports from KAP,
parses them, and appends to the daily data file.

Designed to run as a daily cron job.
"""

import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

PROJECT_DIR = Path(__file__).parent
sys.path.insert(0, str(PROJECT_DIR))

from portfolio_pipeline import run_pipeline

DATA_DIR = PROJECT_DIR / "data"
DAILY_DIR = DATA_DIR / "daily"
DAILY_DIR.mkdir(parents=True, exist_ok=True)


def main():
    # Yesterday's date range
    yesterday = datetime.now() - timedelta(days=1)
    # If yesterday is weekend, go back to Friday
    while yesterday.weekday() >= 5:  # Sat=5, Sun=6
        yesterday = yesterday - timedelta(days=1)
    
    date_str = yesterday.strftime("%d.%m.%Y")
    file_date = yesterday.strftime("%Y-%m-%d")
    
    print(f"Fetching portfolio reports for {date_str}")
    
    results = run_pipeline(date_str, date_str, max_funds=None)
    
    if results:
        output_file = DAILY_DIR / f"portfoy_{file_date}.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        print(f"\nSaved to {output_file}")
        
        # Summary
        with_stocks = sum(1 for r in results if r['stock_count'] > 0)
        total_holdings = sum(r['stock_count'] for r in results)
        print(f"Summary: {len(results)} funds, {with_stocks} with stocks, {total_holdings} total holdings")
    else:
        print("No reports found for this date.")
    
    return len(results) if results else 0


if __name__ == "__main__":
    main()
