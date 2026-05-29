from __future__ import annotations

import asyncio
import json
import re
import time
from datetime import date, datetime
from typing import Any
from urllib import parse as urlparse
from urllib import request as urlrequest

_stock_cache: tuple[float, dict[str, dict[str, Any]]] | None = None


def http_json(url: str, data: dict[str, Any] | None = None, timeout: int = 20) -> dict[str, Any]:
    encoded = None if data is None else urlparse.urlencode(data).encode("utf-8")
    req = urlrequest.Request(
        url,
        data=encoded,
        method="POST" if data is not None else "GET",
        headers={
            "User-Agent": "Mozilla/5.0",
            "Referer": "http://www.cninfo.com.cn/new/commonUrl/pageOfSearch?url=disclosure/list/search",
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "Accept": "application/json,text/javascript,*/*;q=0.01",
        },
    )
    with urlrequest.urlopen(req, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


async def stock_map() -> dict[str, dict[str, Any]]:
    global _stock_cache
    if _stock_cache and time.monotonic() - _stock_cache[0] < 60 * 60 * 24:
        return _stock_cache[1]

    def _load() -> dict[str, dict[str, Any]]:
        payload = http_json("http://www.cninfo.com.cn/new/data/szse_stock.json", timeout=25)
        return {
            str(item.get("code")): item
            for item in payload.get("stockList", [])
            if item.get("code") and item.get("orgId")
        }

    mapping = await asyncio.to_thread(_load)
    _stock_cache = (time.monotonic(), mapping)
    return mapping


async def announcements(ts_code: str, start_day: date, end_day: date) -> list[dict[str, Any]]:
    code = ts_code.split(".")[0]
    exchange = ts_code.split(".")[-1]
    info = (await stock_map()).get(code)
    if not info:
        return []
    column = "sse" if exchange == "SH" else "szse"
    params = {
        "pageNum": 1,
        "pageSize": 12,
        "column": column,
        "tabName": "fulltext",
        "plate": "",
        "stock": f"{code},{info['orgId']}",
        "searchkey": "",
        "secid": "",
        "category": "",
        "trade": "",
        "seDate": f"{start_day.strftime('%Y-%m-%d')}~{end_day.strftime('%Y-%m-%d')}",
        "sortName": "",
        "sortType": "",
        "isHLtitle": "true",
    }

    def _load() -> list[dict[str, Any]]:
        payload = http_json("http://www.cninfo.com.cn/new/hisAnnouncement/query", params, timeout=25)
        rows = payload.get("announcements") or []
        normalized: list[dict[str, Any]] = []
        for row in rows:
            title = re.sub("<.*?>", "", row.get("announcementTitle") or "")
            adjunct_url = row.get("adjunctUrl") or ""
            normalized.append(
                {
                    "source": "巨潮资讯",
                    "source_level": "一级来源",
                    "sec_code": row.get("secCode"),
                    "sec_name": row.get("secName"),
                    "title": title,
                    "date": datetime.fromtimestamp((row.get("announcementTime") or 0) / 1000).strftime("%Y-%m-%d")
                    if row.get("announcementTime")
                    else "",
                    "url": f"http://static.cninfo.com.cn/{adjunct_url}" if adjunct_url else "",
                }
            )
        return normalized

    return await asyncio.to_thread(_load)
