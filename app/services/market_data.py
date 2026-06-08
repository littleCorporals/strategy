from __future__ import annotations

import time
import re
from datetime import date, datetime, timedelta
from typing import Any

from fastapi import HTTPException

from app.clients import cninfo_client, tushare_client
from app.core.config import DAILY_REFRESH_AFTER
from app.services import data_gateway


DAILY_FIELDS = "ts_code,trade_date,open,high,low,close,pre_close,change,pct_chg,vol,amount"
HISTORY_FIELDS = "ts_code,trade_date,open,high,low,close,pre_close,change,pct_chg,vol,amount"
ALLOWED_QUERY_FIELDS = {
    "daily": "ts_code,trade_date,open,high,low,close,pre_close,change,pct_chg,vol,amount",
    "daily_basic": "ts_code,trade_date,close,turnover_rate,turnover_rate_f,volume_ratio,pe,pb,total_mv,circ_mv",
    "moneyflow": "ts_code,trade_date,buy_sm_amount,sell_sm_amount,buy_md_amount,sell_md_amount,buy_lg_amount,sell_lg_amount,buy_elg_amount,sell_elg_amount,net_mf_amount",
    "stock_basic": "ts_code,name,industry,area,market,list_date",
}
STK_FACTOR_FIELDS = (
    "ts_code,trade_date,open,high,low,close,pre_close,change,pct_chg,vol,amount,"
    "turnover_rate,volume_ratio,total_mv,circ_mv,ma_bfq_5,ma_bfq_10,ma_bfq_20"
)
DATE_RE = re.compile(r"^\d{8}$")

_cache = data_gateway._memory_cache
_stock_basic_cache: tuple[float, dict[str, dict[str, Any]]] | None = None


def today_trade_date() -> str:
    return date.today().strftime("%Y%m%d")


def tushare_status() -> dict[str, Any]:
    return {
        "sdk_available": tushare_client.sdk_available(),
        "min_interval": tushare_client.min_interval(),
        "blocked_remaining_seconds": tushare_client.blocked_remaining_seconds(),
        "blocked_message": tushare_client.blocked_message(),
    }


def token_preview(token: str | None) -> str | None:
    return tushare_client.token_preview(token)


def previous_calendar_date(trade_date: str) -> str:
    current = datetime.strptime(trade_date, "%Y%m%d").date()
    return (current - timedelta(days=1)).strftime("%Y%m%d")


def validate_trade_date(trade_date: str) -> str:
    if not DATE_RE.match(trade_date):
        raise HTTPException(status_code=400, detail="trade_date 必须是 YYYYMMDD 格式")
    try:
        datetime.strptime(trade_date, "%Y%m%d")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="trade_date 不是有效日期") from exc
    return trade_date


def normalize_fields(fields: str | None, default: str = DAILY_FIELDS) -> str:
    if not fields:
        return default
    cleaned = ",".join(part.strip() for part in fields.split(",") if part.strip())
    return cleaned or default


def cache_get(key: tuple[Any, ...]) -> Any | None:
    return data_gateway.cache_get(key)


def cache_set(key: tuple[Any, ...], value: Any) -> Any:
    return data_gateway.cache_set(key, value)


def refresh_after_parts() -> tuple[int, int]:
    match = re.match(r"^(\d{1,2}):(\d{2})$", DAILY_REFRESH_AFTER.strip())
    if not match:
        return 15, 10
    hour = min(23, max(0, int(match.group(1))))
    minute = min(59, max(0, int(match.group(2))))
    return hour, minute


def online_fetch_allowed_for_trade_date(trade_date: str) -> bool:
    trade_day = datetime.strptime(trade_date, "%Y%m%d").date()
    today = date.today()
    if trade_day > today:
        return False
    if trade_day < today:
        return True
    hour, minute = refresh_after_parts()
    now = datetime.now().time()
    return (now.hour, now.minute) >= (hour, minute)


def should_persist_empty_trade_date(trade_date: str) -> bool:
    trade_day = datetime.strptime(trade_date, "%Y%m%d").date()
    return trade_day < date.today()


def latest_fetchable_trade_date(end_date: str) -> str:
    checked = validate_trade_date(end_date)
    current = datetime.strptime(checked, "%Y%m%d").date()
    today = date.today()
    if current > today:
        current = today
    if current == today and not online_fetch_allowed_for_trade_date(today.strftime("%Y%m%d")):
        current -= timedelta(days=1)
    return current.strftime("%Y%m%d")


def mark_data_source(interface: str, trade_date: str, source: str) -> None:
    data_gateway.remember_source(interface, trade_date, source)


def data_source(interface: str, trade_date: str) -> str:
    return data_gateway.data_source(interface, trade_date)


async def call_daily(**kwargs: Any) -> list[dict[str, Any]]:
    return await tushare_client.daily(**kwargs)


async def call_query(interface: str, **kwargs: Any) -> list[dict[str, Any]]:
    return await tushare_client.query(interface, **kwargs)


async def call_named_api(api_name: str, **kwargs: Any) -> list[dict[str, Any]]:
    return await tushare_client.named_api(api_name, **kwargs)


async def stock_basic_map(allow_online: bool = True) -> dict[str, dict[str, Any]]:
    global _stock_basic_cache
    if _stock_basic_cache:
        age = time.monotonic() - _stock_basic_cache[0]
        cached_basic = _stock_basic_cache[1]
        if cached_basic and age < 60 * 60 * 12:
            return cached_basic
        if not cached_basic and age < 60:
            return cached_basic

    try:
        result = await data_gateway.sync_complete_rows(
            "stock_basic",
            "",
            fields=ALLOWED_QUERY_FIELDS["stock_basic"],
            cache_key=("stock-basic", ALLOWED_QUERY_FIELDS["stock_basic"]),
            allow_online=allow_online,
            online_fetch=lambda: call_named_api(
                "stock_basic",
                exchange="",
                list_status="L",
                fields=ALLOWED_QUERY_FIELDS["stock_basic"],
                timeout=25,
            ),
            default_trade_date="",
            persist_empty=False,
        )
    except Exception:
        if _stock_basic_cache and _stock_basic_cache[1]:
            return _stock_basic_cache[1]
        _stock_basic_cache = (time.monotonic(), {})
        return {}

    basic = {str(row.get("ts_code")): row for row in result.rows if row.get("ts_code")}
    _stock_basic_cache = (time.monotonic(), basic)
    return basic


async def cached_stock_basic_map() -> dict[str, dict[str, Any]]:
    db_rows = await data_gateway.read_rows("stock_basic", trade_date="")
    return {str(row.get("ts_code")): row for row in db_rows if row.get("ts_code")}


async def cninfo_basic_map(allow_online: bool = True) -> dict[str, dict[str, Any]]:
    if not allow_online:
        return {}
    try:
        stock_map = await cninfo_client.stock_map()
    except Exception:
        return {}
    basic: dict[str, dict[str, Any]] = {}
    for code, info in stock_map.items():
        name = info.get("zwjc")
        if not name:
            continue
        for suffix in ("SZ", "SH", "BJ"):
            basic[f"{code}.{suffix}"] = {"name": name}
    return basic


async def cninfo_stock_map() -> dict[str, dict[str, Any]]:
    return await cninfo_client.stock_map()


async def cninfo_announcements(ts_code: str, start_day: date, end_day: date) -> list[dict[str, Any]]:
    return await cninfo_client.announcements(ts_code, start_day, end_day)


async def attach_stock_basic(rows: list[dict[str, Any]], allow_online: bool = True) -> list[dict[str, Any]]:
    if not rows:
        return rows
    basic = await stock_basic_map(allow_online=allow_online)
    cninfo_basic = await cninfo_basic_map(allow_online=allow_online)
    merged: list[dict[str, Any]] = []
    for row in rows:
        ts_code = str(row.get("ts_code") or "")
        info = basic.get(ts_code, {})
        cninfo_info = cninfo_basic.get(ts_code, {})
        merged.append(
            {
                **row,
                "name": row.get("name") or info.get("name") or cninfo_info.get("name"),
                "industry": row.get("industry") or info.get("industry"),
                "area": row.get("area") or info.get("area"),
            }
        )
    return merged


async def attach_cached_stock_basic(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not rows:
        return rows
    basic = await cached_stock_basic_map()
    if not basic:
        return rows
    merged: list[dict[str, Any]] = []
    for row in rows:
        ts_code = str(row.get("ts_code") or "")
        info = basic.get(ts_code, {})
        merged.append(
            {
                **row,
                "name": row.get("name") or info.get("name"),
                "industry": row.get("industry") or info.get("industry"),
                "area": row.get("area") or info.get("area"),
            }
        )
    return merged


async def daily_rows(trade_date: str, fields: str | None = None) -> list[dict[str, Any]]:
    normalized_fields = normalize_fields(fields, DAILY_FIELDS)
    key = ("daily", trade_date, normalized_fields)
    cached = cache_get(key)
    if cached is not None:
        return cached

    result = await data_gateway.sync_complete_rows(
        "daily",
        trade_date,
        fields=normalized_fields,
        allow_online=online_fetch_allowed_for_trade_date(trade_date),
        online_fetch=lambda: call_daily(trade_date=trade_date, fields=normalized_fields),
        persist_empty=should_persist_empty_trade_date(trade_date),
    )
    rows = result.rows
    if rows:
        rows = await attach_stock_basic(rows) if result.source == "online" else await attach_cached_stock_basic(rows)
    return cache_set(key, rows)


async def daily_rows_raw(trade_date: str, fields: str | None = None) -> list[dict[str, Any]]:
    normalized_fields = normalize_fields(fields, HISTORY_FIELDS)
    key = ("daily-raw", trade_date, normalized_fields)
    result = await data_gateway.sync_complete_rows(
        "daily",
        trade_date,
        fields=normalized_fields,
        cache_key=key,
        allow_online=online_fetch_allowed_for_trade_date(trade_date),
        online_fetch=lambda: call_daily(trade_date=trade_date, fields=normalized_fields),
        persist_empty=should_persist_empty_trade_date(trade_date),
    )
    return result.rows


async def daily_basic_map(trade_date: str) -> dict[str, dict[str, Any]]:
    fields = ALLOWED_QUERY_FIELDS["daily_basic"]
    key = ("daily-basic-map", trade_date, fields)
    cached = cache_get(key)
    if cached is not None:
        return cached

    result = await data_gateway.sync_complete_rows(
        "daily_basic",
        trade_date,
        fields=fields,
        allow_online=online_fetch_allowed_for_trade_date(trade_date),
        online_fetch=lambda: call_query("daily_basic", trade_date=trade_date, fields=fields),
        persist_empty=should_persist_empty_trade_date(trade_date),
    )
    mapping = {str(row.get("ts_code")): row for row in result.rows if row.get("ts_code")}
    return cache_set(key, mapping)


async def recent_daily_by_code(
    end_date: str,
    trade_days: int = 24,
    lookback_calendar_days: int = 45,
) -> dict[str, list[dict[str, Any]]]:
    key = ("recent-daily-by-code", end_date, trade_days, lookback_calendar_days)
    cached = cache_get(key)
    if cached is not None:
        return cached

    current = datetime.strptime(end_date, "%Y%m%d").date()
    day_rows: list[list[dict[str, Any]]] = []
    checked = 0
    while len(day_rows) < trade_days and checked < lookback_calendar_days:
        if current.weekday() < 5:
            rows = await daily_rows_raw(current.strftime("%Y%m%d"), HISTORY_FIELDS)
            if rows:
                day_rows.append(rows)
        current -= timedelta(days=1)
        checked += 1

    by_code: dict[str, list[dict[str, Any]]] = {}
    for rows in reversed(day_rows):
        for row in rows:
            ts_code = str(row.get("ts_code") or "")
            if ts_code:
                by_code.setdefault(ts_code, []).append(row)
    return cache_set(key, by_code)


async def stock_history(
    ts_code: str,
    end_date: str,
    days: int,
    fields: str | None = None,
) -> list[dict[str, Any]]:
    normalized_fields = normalize_fields(fields, HISTORY_FIELDS)
    fetchable_end = latest_fetchable_trade_date(end_date)
    end = datetime.strptime(fetchable_end, "%Y%m%d").date()
    start_date = (end - timedelta(days=max(days * 2, 90))).strftime("%Y%m%d")
    key = ("history", ts_code, start_date, fetchable_end, days, normalized_fields)
    cached = cache_get(key)
    if cached is not None:
        return cached

    result = await data_gateway.read_or_sync_rows(
        "daily",
        ts_code=ts_code,
        start_date=start_date,
        end_date=fetchable_end,
        fields=normalized_fields,
        allow_online=online_fetch_allowed_for_trade_date(fetchable_end),
        online_fetch=lambda: call_daily(
            ts_code=ts_code,
            start_date=start_date,
            end_date=fetchable_end,
            fields=normalized_fields,
        ),
        accept_cached=lambda rows: len(rows) >= min(days, 20),
    )
    rows = result.rows
    rows.sort(key=lambda row: str(row.get("trade_date") or ""))
    return cache_set(key, rows[-days:])


async def single_query_row(interface: str, **params: Any) -> dict[str, Any] | None:
    fields = ALLOWED_QUERY_FIELDS[interface]
    key = ("single-query", interface, tuple(sorted({**params, "fields": fields}.items())))
    cached = cache_get(key)
    if cached is not None:
        return cached

    trade_date = params.get("trade_date")
    ts_code = params.get("ts_code")
    result = await data_gateway.read_or_sync_rows(
        interface,
        trade_date=str(trade_date) if trade_date and ts_code else None,
        ts_code=str(ts_code) if ts_code else None,
        fields=fields,
        allow_online=online_fetch_allowed_for_trade_date(str(trade_date)) if trade_date else True,
        online_fetch=lambda: call_query(interface, fields=fields, **params),
        default_trade_date=str(trade_date or ""),
    )
    row = result.rows[0] if result.rows else None
    return cache_set(key, row)


async def latest_raw_daily_rows(
    trade_date: str,
    fields: str | None = None,
    lookback_days: int = 12,
) -> tuple[str, list[dict[str, Any]]]:
    checked_date = validate_trade_date(trade_date)
    current = checked_date
    for _ in range(max(1, lookback_days)):
        rows = await daily_rows_raw(current, fields)
        if rows:
            return current, rows
        current = previous_calendar_date(current)
    return checked_date, []


async def stk_factor_rows(trade_date: str) -> list[dict[str, Any]]:
    key = ("stk-factor-pro", trade_date, STK_FACTOR_FIELDS)

    async def fetch_factor() -> list[dict[str, Any]]:
        try:
            return await call_named_api(
                "stk_factor_pro",
                trade_date=trade_date,
                fields=STK_FACTOR_FIELDS,
                timeout=75,
            )
        except HTTPException:
            return []

    result = await data_gateway.sync_complete_rows(
        "stk_factor_pro",
        trade_date,
        fields=STK_FACTOR_FIELDS,
        cache_key=key,
        allow_online=online_fetch_allowed_for_trade_date(trade_date),
        online_fetch=fetch_factor,
        persist_empty=should_persist_empty_trade_date(trade_date),
    )
    return result.rows


async def latest_factor_rows(
    trade_date: str,
    lookback_days: int = 12,
) -> tuple[str, list[dict[str, Any]]]:
    checked_date = validate_trade_date(trade_date)
    current = checked_date
    for _ in range(max(1, lookback_days)):
        rows = await stk_factor_rows(current)
        if rows:
            return current, rows
        current = previous_calendar_date(current)
    return checked_date, []


async def next_trade_rows_raw(
    trade_date: str,
    fields: str | None = None,
    lookahead_days: int = 10,
) -> tuple[str | None, list[dict[str, Any]]]:
    current = datetime.strptime(trade_date, "%Y%m%d").date() + timedelta(days=1)
    for _ in range(max(1, lookahead_days)):
        if current.weekday() < 5:
            day = current.strftime("%Y%m%d")
            rows = await daily_rows_raw(day, fields)
            if rows:
                return day, rows
        current += timedelta(days=1)
    return None, []


async def next_trade_rows(
    trade_date: str,
    fields: str | None = None,
    lookahead_days: int = 10,
) -> tuple[str | None, list[dict[str, Any]]]:
    current = datetime.strptime(trade_date, "%Y%m%d").date() + timedelta(days=1)
    for _ in range(max(1, lookahead_days)):
        day = current.strftime("%Y%m%d")
        rows = await daily_rows(day, fields)
        if rows:
            return day, rows
        current += timedelta(days=1)
    return None, []


async def latest_daily_rows(
    trade_date: str,
    fields: str | None = None,
    lookback_days: int = 10,
) -> tuple[str, list[dict[str, Any]]]:
    checked_date = validate_trade_date(trade_date)
    checked_date = latest_fetchable_trade_date(checked_date)
    current = checked_date
    for _ in range(max(1, lookback_days)):
        rows = await daily_rows(current, fields)
        if rows:
            return current, rows
        current = previous_calendar_date(current)
    return checked_date, []


async def query_rows_cached(interface: str, params: dict[str, Any]) -> tuple[list[dict[str, Any]], str]:
    fields = str(params.get("fields") or ALLOWED_QUERY_FIELDS[interface])
    trade_date = params.get("trade_date")
    ts_code = params.get("ts_code")
    start_date = params.get("start_date")
    end_date = params.get("end_date")

    if interface == "stock_basic":
        rows = list((await stock_basic_map()).values())
        return data_gateway.project_fields(rows, fields), "database"

    if trade_date and not (ts_code or start_date or end_date):
        result = await data_gateway.sync_complete_rows(
            interface,
            str(trade_date),
            fields=fields,
            allow_online=online_fetch_allowed_for_trade_date(str(trade_date)),
            online_fetch=lambda: call_query(interface, **params),
            persist_empty=should_persist_empty_trade_date(str(trade_date)),
        )
        return result.rows, result.source

    if ts_code or start_date or end_date:
        result = await data_gateway.read_or_sync_rows(
            interface,
            ts_code=str(ts_code) if ts_code else None,
            start_date=str(start_date) if start_date else None,
            end_date=str(end_date) if end_date else None,
            fields=fields,
            limit=6000,
            allow_online=online_fetch_allowed_for_trade_date(str(trade_date or end_date or today_trade_date())),
            online_fetch=lambda: call_query(interface, **params),
            default_trade_date=str(trade_date or ""),
        )
        return result.rows, result.source

    result = await data_gateway.read_or_sync_rows(
        interface,
        fields=fields,
        limit=6000,
        online_fetch=lambda: call_query(interface, **params),
        default_trade_date=str(trade_date or ""),
    )
    return result.rows, result.source
