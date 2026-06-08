from __future__ import annotations

from typing import Any

from app.db import cache as db_cache


async def stats() -> dict[str, Any]:
    return await db_cache.stats()


async def latest_trade_date(interface: str) -> str | None:
    return await db_cache.latest_trade_date(interface)


async def complete_state(interface: str, trade_date: str) -> Any | None:
    return await db_cache.complete_state(interface, trade_date)


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
    return await db_cache.fetch_rows(
        interface,
        trade_date=trade_date,
        ts_code=ts_code,
        start_date=start_date,
        end_date=end_date,
        fields=fields,
        require_complete=require_complete,
        limit=limit,
    )


async def save_rows(
    interface: str,
    rows: list[dict[str, Any]],
    *,
    complete: bool = False,
    default_trade_date: str = "",
    source: str = "tushare",
) -> None:
    await db_cache.save_rows(interface, rows, complete=complete, default_trade_date=default_trade_date, source=source)


async def mark_complete(interface: str, trade_date: str, row_count: int, source: str) -> None:
    await db_cache.mark_complete(interface, trade_date, row_count, source)


def project_fields(rows: list[dict[str, Any]], fields: str | None) -> list[dict[str, Any]]:
    return db_cache.project_fields(rows, fields)


async def get_payload(namespace: str, cache_key: str) -> Any | None:
    return await db_cache.get_payload(namespace, cache_key)


async def set_payload(namespace: str, cache_key: str, payload: Any) -> None:
    await db_cache.set_payload(namespace, cache_key, payload)
