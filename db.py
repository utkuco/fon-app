#!/usr/bin/env python3
"""
KAP Fund Portfolio Database Module
===================================
SQLite database layer for the KAP fund portfolio application.

Tables:
  - managers: Fund management companies
  - funds:    Individual funds
  - reports:  Periodic portfolio reports (one per fund per period)
  - holdings: Individual stock holdings within a report

Database path: db/fonapp.db  (relative to project root)
"""

import sqlite3
import json
from pathlib import Path
from typing import Optional

# ─── PATH SETUP ──────────────────────────────────────────────────────────────

_PROJECT_ROOT = Path(__file__).resolve().parent
DB_DIR = _PROJECT_ROOT / "db"
DB_PATH = DB_DIR / "fonapp.db"

# ─── SCHEMA ──────────────────────────────────────────────────────────────────

SCHEMA_SQL = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS managers (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT    NOT NULL,
    oid         TEXT    UNIQUE,
    created_at  TEXT    DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS funds (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    code        TEXT    NOT NULL UNIQUE,
    name        TEXT    NOT NULL,
    manager_id  INTEGER,
    fund_type   TEXT,
    isin_code   TEXT,
    created_at  TEXT    DEFAULT (datetime('now')),
    FOREIGN KEY (manager_id) REFERENCES managers(id)
);

CREATE TABLE IF NOT EXISTS reports (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    fund_id       INTEGER NOT NULL,
    report_date   TEXT,
    period        TEXT,
    pdf_path      TEXT,
    nav           REAL,
    stock_pct     REAL,
    fund_info_json TEXT,
    created_at    TEXT    DEFAULT (datetime('now')),
    FOREIGN KEY (fund_id) REFERENCES funds(id),
    UNIQUE(fund_id, period)
);

CREATE TABLE IF NOT EXISTS holdings (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    report_id    INTEGER NOT NULL,
    ticker       TEXT,
    isin         TEXT,
    nominal      REAL,
    unit_price   REAL,
    date         TEXT,
    company      TEXT,
    total_value  REAL,
    weight_pct   REAL,
    created_at   TEXT    DEFAULT (datetime('now')),
    FOREIGN KEY (report_id) REFERENCES reports(id) ON DELETE CASCADE
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_funds_code        ON funds(code);
CREATE INDEX IF NOT EXISTS idx_funds_manager_id  ON funds(manager_id);
CREATE INDEX IF NOT EXISTS idx_reports_fund_id   ON reports(fund_id);
CREATE INDEX IF NOT EXISTS idx_reports_date      ON reports(report_date);
CREATE INDEX IF NOT EXISTS idx_reports_period    ON reports(period);
CREATE INDEX IF NOT EXISTS idx_holdings_report   ON holdings(report_id);
CREATE INDEX IF NOT EXISTS idx_holdings_ticker   ON holdings(ticker);
CREATE INDEX IF NOT EXISTS idx_holdings_isin     ON holdings(isin);
CREATE INDEX IF NOT EXISTS idx_managers_oid      ON managers(oid);
"""


# ─── CONNECTION HELPERS ──────────────────────────────────────────────────────

def get_connection(db_path: Optional[str] = None) -> sqlite3.Connection:
    """Return a connection to the database, creating dirs if needed."""
    path = Path(db_path) if db_path else DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


# ─── INIT ────────────────────────────────────────────────────────────────────

def init_db(db_path: Optional[str] = None) -> sqlite3.Connection:
    """Create tables and indexes if they don't exist. Returns a connection."""
    conn = get_connection(db_path)
    conn.executescript(SCHEMA_SQL)
    conn.commit()
    return conn


# ─── INTERNAL HELPERS ────────────────────────────────────────────────────────

def _ensure_manager(conn: sqlite3.Connection, name: str, oid: Optional[str] = None) -> int:
    """Insert a manager if not exists, return its id."""
    if oid:
        row = conn.execute("SELECT id FROM managers WHERE oid = ?", (oid,)).fetchone()
        if row:
            return row["id"]
    row = conn.execute("SELECT id FROM managers WHERE name = ?", (name,)).fetchone()
    if row:
        if oid:
            conn.execute("UPDATE managers SET oid = ? WHERE id = ? AND oid IS NULL",
                         (oid, row["id"]))
        return row["id"]
    cur = conn.execute("INSERT INTO managers (name, oid) VALUES (?, ?)", (name, oid))
    return cur.lastrowid


def _ensure_fund(conn: sqlite3.Connection, code: str, name: str,
                 manager_id: Optional[int] = None, fund_type: Optional[str] = None,
                 isin_code: Optional[str] = None) -> int:
    """Insert a fund if not exists, return its id. Updates metadata on conflict."""
    row = conn.execute("SELECT id FROM funds WHERE code = ?", (code,)).fetchone()
    if row:
        updates = {}
        existing = conn.execute("SELECT * FROM funds WHERE id = ?", (row["id"],)).fetchone()
        if manager_id and not existing["manager_id"]:
            updates["manager_id"] = manager_id
        if fund_type and not existing["fund_type"]:
            updates["fund_type"] = fund_type
        if isin_code and not existing["isin_code"]:
            updates["isin_code"] = isin_code
        if name and not existing["name"]:
            updates["name"] = name
        if updates:
            set_clause = ", ".join(f"{k} = ?" for k in updates)
            conn.execute(f"UPDATE funds SET {set_clause} WHERE id = ?",
                         list(updates.values()) + [row["id"]])
        return row["id"]
    cur = conn.execute(
        "INSERT INTO funds (code, name, manager_id, fund_type, isin_code) VALUES (?, ?, ?, ?, ?)",
        (code, name, manager_id, fund_type, isin_code),
    )
    return cur.lastrowid


def _parse_number(val) -> Optional[float]:
    """Parse Turkish/European formatted numbers ('1.234,56' -> 1234.56)."""
    if val is None or val == "":
        return None
    s = str(val).strip().replace("%", "")
    # Turkish format: dots as thousands sep, comma as decimal
    if "," in s:
        s = s.replace(".", "").replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


# ─── INSERT FUNCTIONS ────────────────────────────────────────────────────────

def insert_report(conn: sqlite3.Connection, *,
                  fund_code: str,
                  fund_name: str,
                  manager_name: Optional[str] = None,
                  manager_oid: Optional[str] = None,
                  fund_type: Optional[str] = None,
                  isin_code: Optional[str] = None,
                  report_date: Optional[str] = None,
                  period: Optional[str] = None,
                  pdf_path: Optional[str] = None,
                  nav: Optional[float] = None,
                  stock_pct: Optional[float] = None,
                  fund_info: Optional[dict] = None,
                  holdings: Optional[list] = None) -> int:
    """
    Insert a complete report (fund + report + holdings) into the database.
    Handles deduplication - safe to call multiple times for the same fund+period.
    Returns the report id.
    """
    manager_id = _ensure_manager(conn, manager_name, manager_oid) if manager_name else None
    fund_id = _ensure_fund(conn, fund_code, fund_name, manager_id, fund_type, isin_code)

    # Upsert report
    fund_info_json = json.dumps(fund_info, ensure_ascii=False) if fund_info else None
    existing = conn.execute(
        "SELECT id FROM reports WHERE fund_id = ? AND period = ?",
        (fund_id, period),
    ).fetchone()

    if existing:
        report_id = existing["id"]
        conn.execute(
            """UPDATE reports SET report_date = COALESCE(?, report_date),
                                  pdf_path = COALESCE(?, pdf_path),
                                  nav = COALESCE(?, nav),
                                  stock_pct = COALESCE(?, stock_pct),
                                  fund_info_json = COALESCE(?, fund_info_json)
               WHERE id = ?""",
            (report_date, pdf_path, nav, stock_pct, fund_info_json, report_id),
        )
        conn.execute("DELETE FROM holdings WHERE report_id = ?", (report_id,))
    else:
        cur = conn.execute(
            """INSERT INTO reports
               (fund_id, report_date, period, pdf_path, nav, stock_pct, fund_info_json)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (fund_id, report_date, period, pdf_path, nav, stock_pct, fund_info_json),
        )
        report_id = cur.lastrowid

    # Insert holdings
    if holdings:
        for h in holdings:
            conn.execute(
                """INSERT INTO holdings
                   (report_id, ticker, isin, nominal, unit_price, date, company, total_value, weight_pct)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    report_id,
                    h.get("ticker"),
                    h.get("isin"),
                    _parse_number(h.get("nominal")),
                    _parse_number(h.get("unit_price")),
                    h.get("date"),
                    h.get("company"),
                    _parse_number(h.get("total_value")),
                    _parse_number(h.get("weight_pct")),
                ),
            )

    conn.commit()
    return report_id


# ─── QUERY FUNCTIONS ─────────────────────────────────────────────────────────

def get_fund(conn: sqlite3.Connection, code: str) -> Optional[dict]:
    """Get fund details by code, including manager name."""
    row = conn.execute(
        """SELECT f.*, m.name AS manager_name, m.oid AS manager_oid
           FROM funds f
           LEFT JOIN managers m ON f.manager_id = m.id
           WHERE f.code = ?""",
        (code.upper(),),
    ).fetchone()
    return dict(row) if row else None


def get_holdings(conn: sqlite3.Connection, fund_code: str,
                 period: Optional[str] = None) -> list:
    """
    Get holdings for a fund. If period is None, returns holdings from the latest report.
    """
    fund = get_fund(conn, fund_code)
    if not fund:
        return []

    if period:
        report = conn.execute(
            "SELECT id FROM reports WHERE fund_id = ? AND period = ?",
            (fund["id"], period),
        ).fetchone()
    else:
        report = conn.execute(
            "SELECT id FROM reports WHERE fund_id = ? ORDER BY report_date DESC, id DESC LIMIT 1",
            (fund["id"],),
        ).fetchone()

    if not report:
        return []

    rows = conn.execute(
        """SELECT h.*, r.period AS report_period, r.report_date
           FROM holdings h
           JOIN reports r ON h.report_id = r.id
           WHERE h.report_id = ?
           ORDER BY h.total_value DESC""",
        (report["id"],),
    ).fetchall()
    return [dict(r) for r in rows]


def search_funds(conn: sqlite3.Connection, query: str) -> list:
    """Search funds by code or name (case-insensitive LIKE)."""
    pattern = f"%{query}%"
    rows = conn.execute(
        """SELECT f.*, m.name AS manager_name
           FROM funds f
           LEFT JOIN managers m ON f.manager_id = m.id
           WHERE f.code LIKE ? OR f.name LIKE ?
           ORDER BY f.code""",
        (pattern, pattern),
    ).fetchall()
    return [dict(r) for r in rows]


def get_all_funds_with_latest_report(conn: sqlite3.Connection) -> list:
    """Get all funds with their latest report info and holding count."""
    rows = conn.execute(
        """SELECT f.code, f.name, f.fund_type, m.name AS manager_name,
                  r.report_date, r.period, r.nav, r.stock_pct,
                  (SELECT COUNT(*) FROM holdings h WHERE h.report_id = r.id) AS holding_count
           FROM funds f
           LEFT JOIN managers m ON f.manager_id = m.id
           LEFT JOIN reports r ON r.id = (
               SELECT r2.id FROM reports r2
               WHERE r2.fund_id = f.id
               ORDER BY r2.report_date DESC, r2.id DESC
               LIMIT 1
           )
           ORDER BY f.code""",
    ).fetchall()
    return [dict(r) for r in rows]


# ─── CLI QUICK TEST ──────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys

    db_file = sys.argv[1] if len(sys.argv) > 1 else str(DB_PATH)
    print(f"Initializing database at {db_file} ...")
    conn = init_db(db_file)
    print("Database initialized.")

    for table in ("managers", "funds", "reports", "holdings"):
        count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        print(f"  {table}: {count} rows")

    conn.close()
