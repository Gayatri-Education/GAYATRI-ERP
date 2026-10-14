"""Pytest root configuration and fixtures for Gayatri AI platform test suite.

Hardened for Phase 01: Test database isolation (GQA-007).
Ensures tests execute against an isolated temporary SQLite database rather than mutating
the developer's local gayatri_local.db.
"""
from __future__ import annotations

import os
from pathlib import Path
import shutil
import sqlite3
import pytest

from scripts.migrate_db import run_all_migrations


@pytest.fixture(scope="session", autouse=True)
def ensure_isolated_test_database(tmp_path_factory):
    """Ensure tests run against an isolated disposable database instance (GQA-007)."""
    root = Path(__file__).resolve().parent.parent
    root_db = root / "gayatri_local.db"

    db_dir = tmp_path_factory.mktemp("gayatri_isolated_db")
    isolated_db_path = db_dir / "gayatri_isolated_test.db"

    # Copy fixture template into disposable temporary sandbox so developer database is never mutated
    if root_db.exists():
        shutil.copy2(root_db, isolated_db_path)

    # Apply all migrations to the isolated test database
    conn = sqlite3.connect(str(isolated_db_path))
    try:
        conn.execute("PRAGMA foreign_keys = ON;")
        run_all_migrations(conn)
    finally:
        conn.close()

    # Set authoritative environment variable for tests
    old_db_path = os.environ.get("GAYATRI_DB_PATH")
    os.environ["GAYATRI_DB_PATH"] = str(isolated_db_path)

    try:
        import central_platform.auth.dependencies as auth_deps
        auth_deps._DB_INSTANCE = None
    except Exception:
        pass

    yield isolated_db_path

    # Teardown / restore
    try:
        import central_platform.auth.dependencies as auth_deps
        auth_deps._DB_INSTANCE = None
    except Exception:
        pass

    if old_db_path is not None:
        os.environ["GAYATRI_DB_PATH"] = old_db_path
    else:
        os.environ.pop("GAYATRI_DB_PATH", None)


@pytest.fixture
def fresh_isolated_db(tmp_path):
    """Provide a completely isolated per-test database with all migrations applied."""
    db_file = tmp_path / "fresh_test.db"
    conn = sqlite3.connect(str(db_file))
    try:
        conn.execute("PRAGMA foreign_keys = ON;")
        run_all_migrations(conn)
    finally:
        conn.close()
    return db_file
