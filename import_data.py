#!/usr/bin/env python3
"""
Import data from raw JSON files into the SQLite database.

Reads:
  - data/raw/full_2026.json  (preferred, full dataset)
  - data/raw/progress.json   (fallback, partial dataset)

Imports all fund results including holdings into the database.
"""

import json
import sys
import os
from pathlib import Path

# Ensure project root is on path
PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

from db import init_db, insert_report


def load_json(path: Path) -> dict:
    """Load a JSON file, raising if not found."""
    if not path.exists():
        raise FileNotFoundError(f"Data file not found: {path}")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def import_results(conn, results: list, source_name: str = "") -> dict:
    """
    Import a list of result dicts into the database.
    Returns stats: {imported, skipped, errors}.
    """
    stats = {"imported": 0, "skipped": 0, "errors": []}

    for i, item in enumerate(results):
        code = item.get("fund_code", "")
        name = item.get("fund_name", "")

        if not code:
            stats["skipped"] += 1
            continue

        try:
            # Extract manager name from fund name pattern
            # Typical format: "MANAGER PORTFÖY ... FON"
            manager_name = _extract_manager(name)

            report_id = insert_report(
                conn,
                fund_code=code,
                fund_name=name,
                manager_name=manager_name,
                report_date=item.get("publish_date"),
                period=item.get("report_period"),
                fund_info=item.get("fund_info"),
                holdings=item.get("holdings", []),
                stock_pct=_pct_from_info(item.get("fund_info")),
            )
            holding_count = len(item.get("holdings", []))
            print(f"  [{i+1}/{len(results)}] {code}: {holding_count} holdings -> report #{report_id}")
            stats["imported"] += 1

        except Exception as e:
            err_msg = f"{code}: {e}"
            stats["errors"].append(err_msg)
            print(f"  ! Error importing {code}: {e}")

    return stats


def _extract_manager(fund_name: str) -> str:
    """
    Attempt to extract manager/company name from Turkish fund name.
    Most fund names follow: 'COMPANY PORTFÖY ...' or 'COMPANY ... FON'
    """
    if not fund_name:
        return None

    # Common pattern: first word(s) before 'PORTFÖY' is the manager
    parts = fund_name.split()
    if "PORTFÖY" in parts:
        idx = parts.index("PORTFÖY")
        if idx > 0:
            # Take words before PORTFÖY
            return " ".join(parts[:idx])

    # Fallback: first two words
    if len(parts) >= 2:
        return " ".join(parts[:2])

    return parts[0] if parts else None


def _pct_from_info(fund_info: dict) -> float:
    """Extract stock percentage from fund_info if available."""
    if not fund_info:
        return None
    # Try common keys
    for key in ("stock_pct", "hisse_orani", "stock_ratio", "hisse_yuzde"):
        if key in fund_info:
            return fund_info[key]
    return None


def main():
    # Determine data source
    data_dir = PROJECT_ROOT / "data" / "raw"
    full_path = data_dir / "full_2026.json"
    progress_path = data_dir / "progress.json"

    if full_path.exists():
        data_file = full_path
        print(f"Using full dataset: {full_path}")
    elif progress_path.exists():
        data_file = progress_path
        print(f"Using progress dataset: {progress_path}")
    else:
        print("ERROR: No data file found. Expected data/raw/full_2026.json or data/raw/progress.json")
        sys.exit(1)

    # Load data
    data = load_json(data_file)

    # Handle different JSON structures
    if isinstance(data, dict):
        results = data.get("results", [])
        if not results:
            print(f"No 'results' key found. Available keys: {list(data.keys())}")
            sys.exit(1)
    elif isinstance(data, list):
        results = data
    else:
        print(f"Unexpected data format: {type(data)}")
        sys.exit(1)

    print(f"Found {len(results)} fund results to import.\n")

    # Init DB
    db_path = PROJECT_ROOT / "db" / "fonapp.db"
    print(f"Database: {db_path}")
    conn = init_db(str(db_path))

    # Import
    stats = import_results(conn, results, source_name=data_file.name)

    # Summary
    print(f"\n{'='*50}")
    print(f"Import complete.")
    print(f"  Imported: {stats['imported']}")
    print(f"  Skipped:  {stats['skipped']}")
    if stats["errors"]:
        print(f"  Errors:   {len(stats['errors'])}")
        for err in stats["errors"][:10]:
            print(f"    - {err}")

    # Final DB stats
    for table in ("managers", "funds", "reports", "holdings"):
        count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        print(f"  DB {table}: {count} rows")

    conn.close()
    print("Done.")


if __name__ == "__main__":
    main()
