from __future__ import annotations

import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from app.core.config import CACHE_TTL_SECONDS
from app.repositories import market_cache


RowsFetcher = Callable[[], Awaitable[list[dict[str, Any]]]]
RowsPredicate = Callable[[list[dict[str, Any]]], bool]

_memory_cache: dict[tuple[Any, ...], tuple[float, Any]] = {}


@dataclass(frozen=True)
class DataRows:
    rows: list[dict[str, Any]]
    source: str


def cache_get(key: tuple[Any, ...]) -> Any | None:
    cached = _memory_cache.get(key)
    if not cached:
        return None
    created_at, value = cached
    if time.monotonic() - created_at > CACHE_TTL_SECONDS:
        _memory_cache.pop(key, None)
        return None
    return value


def cache_set(key: tuple[Any, ...], value: Any) -> Any:
    _memory_cache[key] = (time.monotonic(), value)
    return value


def remember_source(interface: str, trade_date: str, source: str) -> None:
    cache_set(("data-source", interface, trade_date), source)


def data_source(interface: str, trade_date: str) -> str:
    return str(cache_get(("data-source", interface, trade_date)) or "database")


async def stats() -> dict[str, Any]:
    return await market_cache.stats()


async def latest_trade_date(interface: str = "daily") -> str | None:
    return await market_cache.latest_trade_date(interface)


async def complete_state(interface: str, trade_date: str) -> Any | None:
    return await market_cache.complete_state(interface, trade_date)


async def read_rows(
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
    return await market_cache.fetch_rows(
        interface,
        trade_date=trade_date,
        ts_code=ts_code,
        start_date=start_date,
        end_date=end_date,
        fields=fields,
        require_complete=require_complete,
        limit=limit,
    )


async def read_complete_rows(
    interface: str,
    trade_date: str,
    *,
    fields: str | None = None,
    cache_key: tuple[Any, ...] | None = None,
) -> DataRows:
    if cache_key is not None:
        cached = cache_get(cache_key)
        if cached is not None:
            return DataRows(cached, data_source(interface, trade_date))

    rows = await read_rows(interface, trade_date=trade_date, fields=fields, require_complete=True)
    if rows:
        remember_source(interface, trade_date, "database")
        if cache_key is not None:
            cache_set(cache_key, rows)
        return DataRows(rows, "database")

    state = await complete_state(interface, trade_date)
    if state and int(state["row_count"]) <= 0:
        source = str(state["source"] or "empty")
        remember_source(interface, trade_date, source)
        if cache_key is not None:
            cache_set(cache_key, [])
        return DataRows([], source)

    return DataRows([], "missing")


async def sync_complete_rows(
    interface: str,
    trade_date: str,
    *,
    fields: str | None = None,
    cache_key: tuple[Any, ...] | None = None,
    allow_online: bool = True,
    online_fetch: RowsFetcher | None = None,
    default_trade_date: str | None = None,
    persist_empty: bool = True,
    source: str = "tushare",
    empty_source: str = "tushare_empty",
) -> DataRows:
    cached = await read_complete_rows(interface, trade_date, fields=fields, cache_key=cache_key)
    if cached.source != "missing":
        return cached

    if not allow_online or online_fetch is None:
        remember_source(interface, trade_date, "not_ready")
        if cache_key is not None:
            cache_set(cache_key, [])
        return DataRows([], "not_ready")

    rows = await online_fetch()
    await market_cache.save_rows(
        interface,
        rows,
        complete=True,
        default_trade_date=default_trade_date if default_trade_date is not None else trade_date,
        source=source,
    )
    if not rows and persist_empty:
        await market_cache.mark_complete(interface, trade_date, 0, empty_source)

    remember_source(interface, trade_date, "online")
    if cache_key is not None:
        cache_set(cache_key, rows)
    return DataRows(rows, "online")


async def read_or_sync_rows(
    interface: str,
    *,
    trade_date: str | None = None,
    ts_code: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    fields: str | None = None,
    limit: int | None = None,
    cache_key: tuple[Any, ...] | None = None,
    allow_online: bool = True,
    online_fetch: RowsFetcher | None = None,
    accept_cached: RowsPredicate | None = None,
    default_trade_date: str = "",
    source: str = "tushare",
) -> DataRows:
    if cache_key is not None:
        cached = cache_get(cache_key)
        if cached is not None:
            return DataRows(cached, "memory")

    rows = await read_rows(
        interface,
        trade_date=trade_date,
        ts_code=ts_code,
        start_date=start_date,
        end_date=end_date,
        fields=fields,
        limit=limit,
    )
    if rows and (accept_cached is None or accept_cached(rows)):
        if cache_key is not None:
            cache_set(cache_key, rows)
        return DataRows(rows, "database")

    if not allow_online or online_fetch is None:
        if cache_key is not None:
            cache_set(cache_key, [])
        return DataRows([], "not_ready")

    rows = await online_fetch()
    await market_cache.save_rows(
        interface,
        rows,
        complete=False,
        default_trade_date=default_trade_date,
        source=source,
    )
    if limit is not None:
        rows = rows[:limit]
    if cache_key is not None:
        cache_set(cache_key, rows)
    return DataRows(rows, "online")


def project_fields(rows: list[dict[str, Any]], fields: str | None) -> list[dict[str, Any]]:
    return market_cache.project_fields(rows, fields)


async def get_payload(namespace: str, cache_key: str) -> Any | None:
    return await market_cache.get_payload(namespace, cache_key)


async def set_payload(namespace: str, cache_key: str, payload: Any) -> None:
    await market_cache.set_payload(namespace, cache_key, payload)
