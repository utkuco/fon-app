#!/usr/bin/env python3
"""
cron_shared.py — Shared Supabase client + system_status helpers for all cron jobs.

Used by all local Mac launchd cron scripts.
Environment variables loaded from web/.env.local or .env at project root.
"""

import os
import json
import urllib.request
import urllib.parse
import fcntl
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Optional

# ─── Project root ────────────────────────────────────────────────────────────

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ENV_FILES = [
    PROJECT_ROOT / "web/.env.local",
    PROJECT_ROOT / "web/.env",
    PROJECT_ROOT / ".env",
]


def load_env() -> None:
    """Load .env files into os.environ, merging all that exist.
    Later files override earlier ones (unlike setdefault).
    """
    for env_path in ENV_FILES:
        if env_path.exists():
            with open(env_path) as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    if "=" in line:
                        key, _, value = line.partition("=")
                        value = value.strip().strip('"').strip("'")
                        os.environ[key.strip()] = value


load_env()

# ─── Supabase credentials ────────────────────────────────────────────────────

SUPABASE_URL = os.environ.get("NEXT_PUBLIC_SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")
SUPABASE_DB_URL = os.environ.get("SUPABASE_DB_URL", "")

HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=representation",
}


# ─── REST helpers ──────────────────────────────────────────────────────────

def rest_get(url: str, timeout: int = 30) -> list:
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = resp.read()
            if not data:
                return []
            return json.loads(data)
    except Exception as e:
        print(f"[rest_get] ERROR {url}: {e}")
        return []


def rest_post(
    url: str,
    payload: list[dict],
    conflict_col: Optional[str] = None,
    timeout: int = 60,
) -> bool:
    if not payload:
        return True
    data = json.dumps(payload)
    headers = {**HEADERS}
    if conflict_col:
        headers["Prefer"] = f"resolution=merge-duplicates, conflict={conflict_col}"
    req = urllib.request.Request(url, data=data.encode(), method="POST", headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status in (200, 201)
    except Exception as e:
        print(f"[rest_post] ERROR {url}: {e}")
        return False


def rest_patch(url: str, payload: dict, timeout: int = 30) -> bool:
    data = json.dumps(payload)
    req = urllib.request.Request(url, data=data.encode(), method="PATCH", headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status in (200, 204)
    except Exception as e:
        print(f"[rest_patch] ERROR {url}: {e}")
        return False


def upsert_table(
    table: str,
    rows: list[dict],
    conflict_col: Optional[str] = None,
) -> bool:
    """Upsert rows. Uses PATCH (update-or-insert) for conflict_col case,
    falls back to POST with Prefer header for simple upserts."""
    url = f"{SUPABASE_URL}/rest/v1/{table}"
    if not rows:
        return True
    ok_all = True
    for row in rows:
        if conflict_col and conflict_col in row:
            # Use PATCH with filter — update if exists
            val = row[conflict_col]
            filter_url = f"{url}?{conflict_col}=eq.{urllib.parse.quote(str(val))}"
            payload = {k: v for k, v in row.items() if k != conflict_col}
            try:
                rest_patch(filter_url, payload)
            except Exception:
                ok_all = False
        else:
            if not rest_post(url, [row]):
                ok_all = False
    return ok_all


def query_table(
    table: str,
    select: str = "*",
    filters: Optional[dict] = None,
    order: Optional[str] = None,
    limit: Optional[int] = None,
    offset: int = 0,
) -> list:
    params = [("select", select), ("offset", str(offset))]
    if order:
        params.append(("order", order))
    if limit:
        params.append(("limit", str(limit)))
    if filters:
        for k, v in filters.items():
            params.append((k, str(v)))
    encoded = urllib.parse.urlencode(params)
    url = f"{SUPABASE_URL}/rest/v1/{table}?{encoded}"
    return rest_get(url)


def query_table_paginated(
    table: str,
    select: str = "*",
    filters: Optional[dict] = None,
    page_size: int = 1000,
) -> list:
    """Fetch all rows from a table using cursor-based pagination."""
    rows = []
    offset = 0
    while True:
        batch = query_table(table, select, filters, limit=page_size, offset=offset)
        if not batch:
            break
        rows.extend(batch)
        if len(batch) < page_size:
            break
        offset += page_size
    return rows


# ─── system_status helpers ──────────────────────────────────────────────────

def upsert_system_status(
    key: str,
    value: str,
    status: str = "success",
    detail: str = "",
) -> None:
    """Write a timestamp + status to system_status table.
    Note: system_status only has columns key, value, updated_at (no status/detail).
    """
    payload = [{
        "key": key,
        "value": value,
        "updated_at": datetime.utcnow().isoformat(),
    }]
    url = f"{SUPABASE_URL}/rest/v1/system_status"
    # system_status only has key+value+updated_at — no status/detail columns
    rest_post(url, payload, conflict_col="key")


# ─── Lock file ──────────────────────────────────────────────────────────────

LOCK_DIR = Path("/tmp")


def acquire_lock(lock_name: str) -> Optional[int]:
    """Acquire a file-based lock. Returns lock_fd on success, exits on failure."""
    lock_path = LOCK_DIR / f"{lock_name}.lock"
    lock_fd = open(lock_path, "w")
    try:
        fcntl.flock(lock_fd.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        lock_fd.write(str(os.getpid()))
        lock_fd.flush()
        return lock_fd.fileno()
    except BlockingIOError:
        print(f"[LOCK] {lock_name}: already held — exiting")
        lock_fd.close()
        return None


def release_lock(lock_fd: int, lock_name: str) -> None:
    """Release the file lock."""
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_UN)
        os.unlink(LOCK_DIR / f"{lock_name}.lock")
    except Exception:
        pass


# ─── Logging ────────────────────────────────────────────────────────────────

LOG_DIR = PROJECT_ROOT / "logs"
LOG_DIR.mkdir(exist_ok=True)


def get_logger(name: str):
    """Simple timestamped logger that also writes to logs/<name>.log."""
    log_path = LOG_DIR / f"{name}.log"

    def log(msg: str, level: str = "INFO"):
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        line = f"[{ts}] [{level}] {msg}"
        print(line)
        with open(log_path, "a") as f:
            f.write(line + "\n")

    return log


# ─── psycopg2 (direct Postgres) ────────────────────────────────────────────

def get_pg_connection():
    """Return a psycopg2 connection for SUPABASE_DB_URL (local direct Postgres)."""
    if not SUPABASE_DB_URL:
        return None
    try:
        import psycopg2
        return psycopg2.connect(SUPABASE_DB_URL)
    except ImportError:
        print("[pg] psycopg2 not installed — falling back to REST API")
        return None
