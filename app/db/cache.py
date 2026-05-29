from __future__ import annotations

import asyncio
import json
import re
import sqlite3
from datetime import date, datetime
from typing import Any

from app.core.config import DB_PATH
from app.db import migrations


DATE_RE = re.compile(r"^\d{8}$")
_db_ready = False
_db_lock = asyncio.Lock()


def connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _jsonable(value: Any) -> Any:
    if value is None:
        return None
    if hasattr(value, "item"):
        value = value.item()
    if isinstance(value, float):
        return value if value == value and value not in {float("inf"), float("-inf")} else None
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return value


def init_sync() -> None:
    with connect() as conn:
        migrations.run_pending(conn)


async def ensure() -> None:
    global _db_ready
    if _db_ready:
        return
    async with _db_lock:
        if _db_ready:
            return
        await asyncio.to_thread(init_sync)
        _db_ready = True


def _normalize_trade_date(value: Any) -> str:
    text = str(value or "")
    return text if DATE_RE.match(text) else ""


def _normalize_ts_code(value: Any) -> str:
    return str(value or "").strip().upper()


def _row_sort_key(row: dict[str, Any]) -> tuple[str, str]:
    return (str(row.get("trade_date") or ""), str(row.get("ts_code") or ""))


def project_fields(rows: list[dict[str, Any]], fields: str | None) -> list[dict[str, Any]]:
    if not fields:
        return rows
    columns = [part.strip() for part in fields.split(",") if part.strip()]
    if not columns:
        return rows
    return [{column: row.get(column) for column in columns} for row in rows]


def complete_state_sync(interface: str, trade_date: str) -> sqlite3.Row | None:
    with connect() as conn:
        return conn.execute(
            """
            SELECT row_count, fetched_at, source
            FROM sync_state
            WHERE interface = ? AND trade_date = ? AND scope = 'complete'
            """,
            (interface, trade_date),
        ).fetchone()


async def complete_state(interface: str, trade_date: str) -> sqlite3.Row | None:
    await ensure()
    return await asyncio.to_thread(complete_state_sync, interface, trade_date)


def fetch_rows_sync(
    interface: str,
    *,
    trade_date: str | None = None,
    ts_code: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    fields: str | None = None,
    require_complete: bool = False,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    params: list[Any] = [interface]
    clauses = ["interface = ?"]
    if trade_date is not None:
        clauses.append("trade_date = ?")
        params.append(trade_date)
    if ts_code:
        clauses.append("ts_code = ?")
        params.append(_normalize_ts_code(ts_code))
    if start_date:
        clauses.append("trade_date >= ?")
        params.append(start_date)
    if end_date:
        clauses.append("trade_date <= ?")
        params.append(end_date)

    sql = f"SELECT row_json FROM market_rows WHERE {' AND '.join(clauses)} ORDER BY trade_date, ts_code"
    if limit is not None:
        sql += " LIMIT ?"
        params.append(limit)

    with connect() as conn:
        if require_complete:
            checked_date = trade_date if trade_date is not None else ""
            state = conn.execute(
                """
                SELECT row_count
                FROM sync_state
                WHERE interface = ? AND trade_date = ? AND scope = 'complete'
                """,
                (interface, checked_date),
            ).fetchone()
            if not state or int(state["row_count"]) <= 0:
                return []
        rows = [json.loads(item["row_json"]) for item in conn.execute(sql, params).fetchall()]
    rows.sort(key=_row_sort_key)
    return project_fields(rows, fields)


async def fetch_rows(
    interface: str,
    *,
    trade_date: str | None = None,
    ts_code: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    fields: str | None = None,
    require_complete: bool = False,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    await ensure()
    return await asyncio.to_thread(
        fetch_rows_sync,
        interface,
        trade_date=trade_date,
        ts_code=ts_code,
        start_date=start_date,
        end_date=end_date,
        fields=fields,
        require_complete=require_complete,
        limit=limit,
    )


def save_rows_sync(
    interface: str,
    rows: list[dict[str, Any]],
    *,
    complete: bool = False,
    default_trade_date: str = "",
    source: str = "tushare",
) -> None:
    if not rows:
        return
    now = datetime.now().isoformat(timespec="seconds")
    counts: dict[str, int] = {}
    with connect() as conn:
        for row in rows:
            trade_date = _normalize_trade_date(row.get("trade_date")) or default_trade_date
            ts_code = _normalize_ts_code(row.get("ts_code"))
            if not ts_code and interface != "stock_basic":
                continue
            cleaned = {key: _jsonable(value) for key, value in row.items()}
            cleaned["trade_date"] = trade_date
            conn.execute(
                """
                INSERT INTO market_rows(interface, ts_code, trade_date, row_json, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(interface, ts_code, trade_date)
                DO UPDATE SET row_json = excluded.row_json, updated_at = excluded.updated_at
                """,
                (interface, ts_code, trade_date, json.dumps(cleaned, ensure_ascii=False), now),
            )
            counts[trade_date] = counts.get(trade_date, 0) + 1

        scope = "complete" if complete else "partial"
        for trade_date, row_count in counts.items():
            conn.execute(
                """
                INSERT INTO sync_state(interface, trade_date, scope, row_count, source, fetched_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(interface, trade_date, scope)
                DO UPDATE SET
                    row_count = excluded.row_count,
                    source = excluded.source,
                    fetched_at = excluded.fetched_at
                """,
                (interface, trade_date, scope, row_count, source, now),
            )
        conn.commit()


async def save_rows(
    interface: str,
    rows: list[dict[str, Any]],
    *,
    complete: bool = False,
    default_trade_date: str = "",
    source: str = "tushare",
) -> None:
    await ensure()
    await asyncio.to_thread(
        save_rows_sync,
        interface,
        rows,
        complete=complete,
        default_trade_date=default_trade_date,
        source=source,
    )


def mark_complete_sync(interface: str, trade_date: str, row_count: int, source: str) -> None:
    now = datetime.now().isoformat(timespec="seconds")
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO sync_state(interface, trade_date, scope, row_count, source, fetched_at)
            VALUES (?, ?, 'complete', ?, ?, ?)
            ON CONFLICT(interface, trade_date, scope)
            DO UPDATE SET
                row_count = excluded.row_count,
                source = excluded.source,
                fetched_at = excluded.fetched_at
            """,
            (interface, trade_date, row_count, source, now),
        )
        conn.commit()


async def mark_complete(interface: str, trade_date: str, row_count: int, source: str) -> None:
    await ensure()
    await asyncio.to_thread(mark_complete_sync, interface, trade_date, row_count, source)


def latest_trade_date_sync(interface: str = "daily") -> str | None:
    with connect() as conn:
        row = conn.execute(
            """
            SELECT MAX(trade_date) AS trade_date
            FROM sync_state
            WHERE interface = ? AND scope = 'complete' AND row_count > 0 AND trade_date <> ''
            """,
            (interface,),
        ).fetchone()
    return str(row["trade_date"]) if row and row["trade_date"] else None


async def latest_trade_date(interface: str = "daily") -> str | None:
    await ensure()
    return await asyncio.to_thread(latest_trade_date_sync, interface)


def stats_sync() -> dict[str, Any]:
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT interface, COUNT(*) AS row_count, MAX(trade_date) AS latest_trade_date
            FROM market_rows
            GROUP BY interface
            ORDER BY interface
            """
        ).fetchall()
    return {
        "path": str(DB_PATH),
        "interfaces": {
            str(row["interface"]): {
                "rows": int(row["row_count"]),
                "latest_trade_date": row["latest_trade_date"] or None,
            }
            for row in rows
        },
    }


async def stats() -> dict[str, Any]:
    await ensure()
    return await asyncio.to_thread(stats_sync)


def get_payload_sync(namespace: str, cache_key: str) -> Any | None:
    with connect() as conn:
        row = conn.execute(
            """
            SELECT payload_json
            FROM cached_payloads
            WHERE namespace = ? AND cache_key = ?
            """,
            (namespace, cache_key),
        ).fetchone()
    return json.loads(row["payload_json"]) if row else None


async def get_payload(namespace: str, cache_key: str) -> Any | None:
    await ensure()
    return await asyncio.to_thread(get_payload_sync, namespace, cache_key)


def set_payload_sync(namespace: str, cache_key: str, payload: Any) -> None:
    now = datetime.now().isoformat(timespec="seconds")
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO cached_payloads(namespace, cache_key, payload_json, updated_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(namespace, cache_key)
            DO UPDATE SET payload_json = excluded.payload_json, updated_at = excluded.updated_at
            """,
            (namespace, cache_key, json.dumps(payload, ensure_ascii=False), now),
        )
        conn.commit()


async def set_payload(namespace: str, cache_key: str, payload: Any) -> None:
    await ensure()
    await asyncio.to_thread(set_payload_sync, namespace, cache_key, payload)
