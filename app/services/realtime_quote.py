from __future__ import annotations

import re
from datetime import datetime
from typing import Any

import httpx


SINA_QUOTE_URL = "https://hq.sinajs.cn/list={symbols}"
SINA_HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Referer": "https://finance.sina.com.cn/",
}
TS_CODE_RE = re.compile(r"^(\d{6})\.(SH|SZ)$")


def _sina_symbol(ts_code: str) -> str | None:
    match = TS_CODE_RE.match(str(ts_code).upper())
    if not match:
        return None
    code, exchange = match.groups()
    prefix = "sh" if exchange == "SH" else "sz"
    return f"{prefix}{code}"


def _round(value: float | None, digits: int = 2) -> float | None:
    if value is None:
        return None
    return round(value, digits)


def _float_at(fields: list[str], index: int) -> float | None:
    try:
        value = fields[index]
    except IndexError:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _int_at(fields: list[str], index: int) -> int | None:
    value = _float_at(fields, index)
    return int(value) if value is not None else None


def _parse_line(line: str, symbol_to_code: dict[str, str]) -> tuple[str, dict[str, Any]] | None:
    match = re.match(r'var hq_str_(sh|sz)(\d{6})="(.*)";', line.strip())
    if not match:
        return None
    prefix, code, payload = match.groups()
    ts_code = symbol_to_code.get(f"{prefix}{code}")
    if not ts_code:
        return None
    fields = payload.split(",")
    if len(fields) < 32 or not fields[0]:
        return ts_code, {"ts_code": ts_code, "source": "sina", "available": False}

    pre_close = _float_at(fields, 2)
    current = _float_at(fields, 3)
    pct = ((current - pre_close) / pre_close * 100) if current is not None and pre_close else None
    amount_yuan = _float_at(fields, 9)
    return ts_code, {
        "ts_code": ts_code,
        "name": fields[0],
        "source": "sina",
        "available": current is not None and current > 0,
        "open": _float_at(fields, 1),
        "pre_close": pre_close,
        "price": current,
        "pct_chg": _round(pct, 2),
        "high": _float_at(fields, 4),
        "low": _float_at(fields, 5),
        "bid1": _float_at(fields, 11),
        "ask1": _float_at(fields, 21),
        "volume": _int_at(fields, 8),
        "amount_yuan": amount_yuan,
        "amount_yi": _round((amount_yuan / 100_000_000) if amount_yuan is not None else None, 2),
        "quote_date": fields[30] if len(fields) > 30 else "",
        "quote_time": fields[31] if len(fields) > 31 else "",
        "fetched_at": datetime.now().isoformat(timespec="seconds"),
    }


async def sina_quotes(ts_codes: list[str]) -> dict[str, dict[str, Any]]:
    symbol_to_code: dict[str, str] = {}
    for ts_code in ts_codes:
        symbol = _sina_symbol(ts_code)
        if symbol:
            symbol_to_code[symbol] = ts_code
    if not symbol_to_code:
        return {}

    async with httpx.AsyncClient(timeout=12, headers=SINA_HEADERS) as client:
        response = await client.get(SINA_QUOTE_URL.format(symbols=",".join(symbol_to_code)))
        response.raise_for_status()

    text = response.content.decode("gbk", errors="replace")
    quotes: dict[str, dict[str, Any]] = {}
    for line in text.splitlines():
        parsed = _parse_line(line, symbol_to_code)
        if parsed:
            ts_code, quote = parsed
            quotes[ts_code] = quote
    return quotes
