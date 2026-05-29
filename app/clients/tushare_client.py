from __future__ import annotations

import asyncio
import math
import os
import re
import time
from datetime import date, datetime
from typing import Any

from fastapi import HTTPException

from app.core.config import DEFAULT_PROXY_URL, PROXY_ENV, TOKEN_ENV

try:
    import pandas as pd
except Exception:  # pragma: no cover
    pd = None

try:
    import tushare as ts
    from tushare.pro import client as _ts_client
except Exception:  # pragma: no cover
    ts = None
    _ts_client = None

_client_lock = asyncio.Lock()
_request_lock = asyncio.Lock()
_client: Any | None = None
_last_request_at = 0.0
_blocked_until = 0.0
_blocked_message = ""


def min_interval() -> float:
    raw = os.getenv("TUSHARE_MIN_INTERVAL", "0.65")
    try:
        return max(0.0, float(raw))
    except ValueError:
        return 0.65


def token_preview(token: str | None) -> str | None:
    if not token:
        return None
    if len(token) <= 10:
        return "***"
    return f"{token[:4]}...{token[-4:]}"


def sdk_available() -> bool:
    return ts is not None and _ts_client is not None and pd is not None


def blocked_remaining_seconds() -> int:
    return max(0, math.ceil(_blocked_until - time.monotonic()))


def blocked_message() -> str:
    return _blocked_message if blocked_remaining_seconds() else ""


def _register_error(exc: Exception) -> None:
    global _blocked_until, _blocked_message
    message = str(exc)
    match = re.search(r"remaining\s+(\d+)s", message)
    if match:
        _blocked_until = time.monotonic() + int(match.group(1))
        _blocked_message = message


def _raise_if_blocked() -> None:
    remaining = blocked_remaining_seconds()
    if remaining > 0:
        raise HTTPException(
            status_code=429,
            detail=f"Tushare 临时冷却中，约 {remaining} 秒后再刷新行情。原因：{_blocked_message}",
        )


def _require_sdk() -> None:
    if not sdk_available():
        raise HTTPException(
            status_code=503,
            detail="缺少 tushare/pandas 依赖。请先执行：python -m pip install -r requirements.txt",
        )


async def _get_client() -> Any:
    global _client
    _require_sdk()
    token = os.getenv(TOKEN_ENV)
    if not token:
        raise HTTPException(
            status_code=503,
            detail=f"未配置 {TOKEN_ENV}。请在环境变量或 .env 文件中设置 Tushare token。",
        )

    async with _client_lock:
        if _client is None:
            proxy_url = os.getenv(PROXY_ENV, DEFAULT_PROXY_URL).strip() or DEFAULT_PROXY_URL
            _ts_client.DataApi._DataApi__http_url = proxy_url
            _client = ts.pro_api(token)
    return _client


async def _wait_for_slot() -> None:
    global _last_request_at
    wait_for = min_interval() - (time.monotonic() - _last_request_at)
    if wait_for > 0:
        await asyncio.sleep(wait_for)


def _repair_text(value: str) -> str:
    if not any("\x80" <= char <= "\xff" for char in value):
        return value
    try:
        return value.encode("latin1").decode("utf-8")
    except UnicodeError:
        return value


def jsonable(value: Any) -> Any:
    if value is None:
        return None
    if pd is not None and pd.isna(value):
        return None
    if hasattr(value, "item"):
        value = value.item()
    if isinstance(value, str):
        return _repair_text(value)
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return value


def frame_to_records(df: Any) -> list[dict[str, Any]]:
    if df is None:
        return []
    records = df.to_dict(orient="records")
    return [{key: jsonable(value) for key, value in row.items()} for row in records]


async def call(method_name: str, *args: Any, timeout: float | None = None, **kwargs: Any) -> list[dict[str, Any]]:
    global _last_request_at
    _raise_if_blocked()
    client = await _get_client()
    async with _request_lock:
        _raise_if_blocked()
        await _wait_for_slot()
        try:
            fn = getattr(client, method_name)
        except AttributeError as exc:
            raise HTTPException(status_code=404, detail=f"暂不支持 {method_name}") from exc
        try:
            request = asyncio.to_thread(fn, *args, **kwargs)
            df = await asyncio.wait_for(request, timeout=timeout) if timeout else await request
        except Exception as exc:
            _register_error(exc)
            raise HTTPException(status_code=502, detail=f"Tushare 查询失败：{exc}") from exc
        finally:
            _last_request_at = time.monotonic()
            cooldown = min_interval()
            if cooldown > 0:
                await asyncio.sleep(cooldown)
    return frame_to_records(df)


async def daily(**kwargs: Any) -> list[dict[str, Any]]:
    return await call("daily", **kwargs)


async def query(interface: str, **kwargs: Any) -> list[dict[str, Any]]:
    return await call("query", interface, **kwargs)


async def named_api(api_name: str, **kwargs: Any) -> list[dict[str, Any]]:
    return await call(api_name, **kwargs)
