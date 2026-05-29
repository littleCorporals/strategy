from __future__ import annotations

import sqlite3
from pathlib import Path


MIGRATIONS_DIR = Path(__file__).resolve().parents[2] / "migrations"


def _migration_files() -> list[Path]:
    return sorted(
        path
        for path in MIGRATIONS_DIR.glob("*.sql")
        if path.name[:4].isdigit()
    )


def _ensure_migration_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version TEXT PRIMARY KEY,
            applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )


def applied_versions(conn: sqlite3.Connection) -> set[str]:
    _ensure_migration_table(conn)
    rows = conn.execute("SELECT version FROM schema_migrations").fetchall()
    return {str(row["version"] if isinstance(row, sqlite3.Row) else row[0]) for row in rows}


def run_pending(conn: sqlite3.Connection) -> list[str]:
    _ensure_migration_table(conn)
    applied = applied_versions(conn)
    applied_now: list[str] = []
    for path in _migration_files():
        version = path.stem
        if version in applied:
            continue
        sql = path.read_text(encoding="utf-8")
        conn.executescript(sql)
        conn.execute("INSERT INTO schema_migrations(version) VALUES (?)", (version,))
        applied_now.append(version)
    conn.commit()
    return applied_now
