from __future__ import annotations

import csv
import io
import os
import re
from datetime import date, datetime, timedelta
from typing import Annotated, Any

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import HTMLResponse, Response

from app.core.config import (
    AI_MODEL_ENV,
    CACHE_TTL_SECONDS,
    DAILY_REFRESH_AFTER,
    DEFAULT_PROXY_URL,
    PROXY_ENV,
    STATIC_DIR,
    TOKEN_ENV,
)
from app.repositories import market_cache
from app.schemas.market import (
    BacktestResponse,
    HealthResponse,
    IndustryTrendsResponse,
    MarketRowsResponse,
    QueryResponse,
    StatusResponse,
    StockAnalysisResponse,
    StockBasicResponse,
    StockHistoryResponse,
    StockRecommendationResponse,
)
from app.services import analysis
from app.services import backtest
from app.services import market_data
from app.services import ml_realtime_screen
from app.services import recommendation
from app.services import stock_decision

try:
    from dotenv import load_dotenv
except Exception:  # pragma: no cover
    load_dotenv = None

DAILY_FIELDS = market_data.DAILY_FIELDS
ALLOWED_QUERY_FIELDS = market_data.ALLOWED_QUERY_FIELDS
DATE_RE = re.compile(r"^\d{8}$")
TS_CODE_RE = re.compile(r"^[0-9A-Z]{6}\.(SZ|SH|BJ)$")

if load_dotenv:
    load_dotenv()


router = APIRouter()


def _today_trade_date() -> str:
    return date.today().strftime("%Y%m%d")


def _previous_calendar_date(trade_date: str) -> str:
    current = datetime.strptime(trade_date, "%Y%m%d").date()
    return (current - timedelta(days=1)).strftime("%Y%m%d")


def _token_preview(token: str | None) -> str | None:
    return market_data.token_preview(token)


def _ai_configured() -> bool:
    return recommendation.ai_configured()


def _validate_trade_date(trade_date: str) -> str:
    if not DATE_RE.match(trade_date):
        raise HTTPException(status_code=400, detail="trade_date 必须是 YYYYMMDD 格式")
    try:
        datetime.strptime(trade_date, "%Y%m%d")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="trade_date 不是有效日期") from exc
    return trade_date


def _validate_ts_code(ts_code: str) -> str:
    normalized = ts_code.strip().upper()
    if not TS_CODE_RE.match(normalized):
        raise HTTPException(status_code=400, detail="ts_code 必须类似 000001.SZ")
    return normalized


def _normalize_fields(fields: str | None, default: str = DAILY_FIELDS) -> str:
    return market_data.normalize_fields(fields, default)


def _cache_get(key: tuple[Any, ...]) -> Any | None:
    return market_data.cache_get(key)


def _cache_set(key: tuple[Any, ...], value: Any) -> Any:
    return market_data.cache_set(key, value)


def _latest_fetchable_trade_date(end_date: str) -> str:
    return market_data.latest_fetchable_trade_date(end_date)


def _data_source(interface: str, trade_date: str) -> str:
    return market_data.data_source(interface, trade_date)


def _summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return analysis.summarize(rows)


def _csv_response(rows: list[dict[str, Any]], filename: str) -> Response:
    buffer = io.StringIO(newline="")
    if rows:
        writer = csv.DictWriter(buffer, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    content = buffer.getvalue().encode("utf-8-sig")
    return Response(
        content,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


async def _stock_basic_map(allow_online: bool = True) -> dict[str, dict[str, Any]]:
    return await market_data.stock_basic_map(allow_online=allow_online)


async def _attach_stock_basic(rows: list[dict[str, Any]], allow_online: bool = True) -> list[dict[str, Any]]:
    return await market_data.attach_stock_basic(rows, allow_online=allow_online)


async def _daily_rows(trade_date: str, fields: str | None = None) -> list[dict[str, Any]]:
    return await market_data.daily_rows(trade_date, fields)


async def _daily_basic_map(trade_date: str) -> dict[str, dict[str, Any]]:
    return await market_data.daily_basic_map(trade_date)


async def _stock_history(
    ts_code: str,
    end_date: str,
    days: int,
    fields: str | None = None,
) -> list[dict[str, Any]]:
    return await market_data.stock_history(ts_code, end_date, days, fields)


async def _short_swing_backtest_payload(
    end_date: str,
    trade_days: int,
    per_day_limit: int,
) -> dict[str, Any]:
    return await backtest.short_swing_backtest_payload(end_date, trade_days, per_day_limit)


async def _recommendation_pool(
    rows: list[dict[str, Any]],
    end_date: str,
    limit: int = 30,
) -> list[dict[str, Any]]:
    return await recommendation.recommendation_pool(rows, end_date, limit)


async def _attach_next_day_validation(picks: list[dict[str, Any]], trade_date: str) -> list[dict[str, Any]]:
    return await recommendation.attach_next_day_validation(picks, trade_date)


async def _late_session_recommendation_pool(
    rows: list[dict[str, Any]],
    end_date: str,
    limit: int = 20,
) -> list[dict[str, Any]]:
    return await recommendation.late_session_recommendation_pool(rows, end_date, limit)


async def _ml_late_session_screen(
    trade_date: str,
    *,
    limit: int = 20,
    prediction_limit: int = 500,
) -> dict[str, Any]:
    return await ml_realtime_screen.ml_late_session_screen(
        trade_date,
        limit=limit,
        prediction_limit=prediction_limit,
    )


def _industry_trends(rows: list[dict[str, Any]], limit: int = 20) -> list[dict[str, Any]]:
    return recommendation.industry_trends(rows, limit)


async def _latest_daily_rows(
    trade_date: str,
    fields: str | None = None,
    lookback_days: int = 10,
) -> tuple[str, list[dict[str, Any]]]:
    return await market_data.latest_daily_rows(trade_date, fields, lookback_days)


async def _query_rows_cached(interface: str, params: dict[str, Any]) -> tuple[list[dict[str, Any]], str]:
    return await market_data.query_rows_cached(interface, params)


@router.get("/", response_class=HTMLResponse)
async def index() -> HTMLResponse:
    return HTMLResponse((STATIC_DIR / "index.html").read_text(encoding="utf-8"))


@router.get("/api/status", response_model=StatusResponse)
async def status() -> dict[str, Any]:
    token = os.getenv(TOKEN_ENV)
    db_stats = await market_cache.stats()
    safe_db_stats = {
        **db_stats,
        "path": "local sqlite cache" if db_stats.get("path") else "",
    }
    latest_db_trade_date = await market_cache.latest_trade_date("daily")
    default_trade_date = latest_db_trade_date or _latest_fetchable_trade_date(_today_trade_date())
    ts_status = market_data.tushare_status()
    return {
        "ok": True,
        "sdk_available": ts_status["sdk_available"],
        "token_configured": bool(token),
        "token_preview": None,
        "proxy_url": None,
        "min_interval": ts_status["min_interval"],
        "cache_ttl_seconds": CACHE_TTL_SECONDS,
        "database": safe_db_stats,
        "database_ready": True,
        "default_trade_date": default_trade_date,
        "latest_db_trade_date": latest_db_trade_date,
        "online_refresh_after": DAILY_REFRESH_AFTER,
        "tushare_blocked_remaining_seconds": ts_status["blocked_remaining_seconds"],
        "tushare_block_message": "upstream temporarily cooling down" if ts_status["blocked_message"] else "",
    }


@router.get("/api/stock-basic", response_model=StockBasicResponse)
async def stock_basic() -> dict[str, Any]:
    basic = await _stock_basic_map()
    return {
        "count": len(basic),
        "items": basic,
        "fetched_at": datetime.now().isoformat(timespec="seconds"),
    }


@router.get("/api/daily", response_model=MarketRowsResponse)
async def daily(
    trade_date: Annotated[str | None, Query()] = None,
    fields: Annotated[str | None, Query()] = None,
    auto_fallback: Annotated[bool, Query()] = False,
) -> dict[str, Any]:
    requested_date = _validate_trade_date(trade_date or _today_trade_date())
    if auto_fallback:
        actual_date, rows = await _latest_daily_rows(requested_date, fields)
    else:
        actual_date = requested_date
        rows = await _daily_rows(requested_date, fields)
    source = _data_source("daily", actual_date)
    return {
        "requested_trade_date": requested_date,
        "trade_date": actual_date,
        "fallback_used": actual_date != requested_date,
        "data_source": source,
        "database_cached": source == "database",
        "online_refresh_after": DAILY_REFRESH_AFTER,
        "columns": list(rows[0].keys()) if rows else _normalize_fields(fields).split(","),
        "rows": rows,
        "summary": _summarize(rows),
        "cached_for_seconds": CACHE_TTL_SECONDS,
        "fetched_at": datetime.now().isoformat(timespec="seconds"),
    }


@router.get("/api/recommendations", response_model=MarketRowsResponse)
async def recommendations(
    trade_date: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(ge=5, le=60)] = 30,
) -> dict[str, Any]:
    requested_date = _validate_trade_date(trade_date or _previous_calendar_date(_today_trade_date()))
    actual_date, rows = await _latest_daily_rows(requested_date, DAILY_FIELDS)
    daily_source = _data_source("daily", actual_date)
    rows = await _attach_stock_basic(rows, allow_online=daily_source != "database")
    basic_map = await _daily_basic_map(actual_date)
    rows = [{**row, **basic_map.get(str(row.get("ts_code")), {})} for row in rows]
    picks = await _recommendation_pool(rows, actual_date, limit)
    picks = await _attach_next_day_validation(picks, actual_date)
    return {
        "requested_trade_date": requested_date,
        "trade_date": actual_date,
        "data_source": daily_source,
        "rows": picks,
        "count": len(picks),
        "summary": _summarize(rows),
        "cached_for_seconds": CACHE_TTL_SECONDS,
        "fetched_at": datetime.now().isoformat(timespec="seconds"),
    }


@router.get("/api/recommendations/late-session", response_model=MarketRowsResponse)
async def late_session_recommendations(
    trade_date: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(ge=5, le=60)] = 20,
) -> dict[str, Any]:
    requested_date = _validate_trade_date(trade_date or _previous_calendar_date(_today_trade_date()))
    actual_date, rows = await _latest_daily_rows(requested_date, DAILY_FIELDS)
    daily_source = _data_source("daily", actual_date)
    rows = await _attach_stock_basic(rows, allow_online=daily_source != "database")
    basic_map = await _daily_basic_map(actual_date)
    rows = [{**row, **basic_map.get(str(row.get("ts_code")), {})} for row in rows]
    picks = await _late_session_recommendation_pool(rows, actual_date, limit)
    return {
        "requested_trade_date": requested_date,
        "trade_date": actual_date,
        "data_source": f"{daily_source}+realtime",
        "rows": picks,
        "count": len(picks),
        "summary": _summarize(rows),
        "cached_for_seconds": CACHE_TTL_SECONDS,
        "fetched_at": datetime.now().isoformat(timespec="seconds"),
    }


@router.get("/api/recommendations/ml-late-session", response_model=MarketRowsResponse)
async def ml_late_session_recommendations(
    trade_date: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(ge=5, le=60)] = 20,
    prediction_limit: Annotated[int, Query(ge=50, le=1000)] = 500,
) -> dict[str, Any]:
    requested_date = _validate_trade_date(trade_date or _previous_calendar_date(_today_trade_date()))
    payload = await _ml_late_session_screen(
        requested_date,
        limit=limit,
        prediction_limit=prediction_limit,
    )
    actual_date = str(payload.get("trade_date") or requested_date)
    rows = await _daily_rows(actual_date, DAILY_FIELDS)
    market_summary = _summarize(rows)
    market_summary.update(
        {
            "model": payload.get("model"),
            "model_reference": payload.get("model_reference"),
            "prediction_count": payload.get("prediction_count", 0),
            "quote_count": payload.get("quote_count", 0),
            "accepted_count": payload.get("accepted_count", len(payload.get("rows") or [])),
            "rejected_counts": payload.get("rejected_counts") or {},
            "raw_top": payload.get("raw_top") or [],
            "rules": {
                "exclude": [
                    "北交所",
                    "ST/退市/U/W",
                    "实时跌幅<-1%",
                    "涨幅>4.2%过热",
                    "日内振幅>12%",
                    "日内位置<35%",
                    "高位且涨幅>2%",
                    "成交额<1.5亿",
                ],
                "note": "原始模型排序只作第一层召回，最终候选必须通过实时风险闸门。",
            },
        }
    )
    return {
        "requested_trade_date": requested_date,
        "trade_date": actual_date,
        "fallback_used": payload.get("fallback_used"),
        "data_source": "ml_predictions+realtime",
        "rows": payload.get("rows") or [],
        "count": len(payload.get("rows") or []),
        "summary": market_summary,
        "cached_for_seconds": CACHE_TTL_SECONDS,
        "fetched_at": datetime.now().isoformat(timespec="seconds"),
    }


@router.get("/api/industry-trends", response_model=IndustryTrendsResponse)
async def industry_trends(
    trade_date: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(ge=5, le=60)] = 20,
) -> dict[str, Any]:
    requested_date = _validate_trade_date(trade_date or _previous_calendar_date(_today_trade_date()))
    actual_date, rows = await _latest_daily_rows(requested_date, DAILY_FIELDS)
    daily_source = _data_source("daily", actual_date)
    if daily_source != "database":
        await _stock_basic_map()
    rows = await _attach_stock_basic(rows, allow_online=daily_source != "database")
    trends = _industry_trends(rows, limit)
    return {
        "requested_trade_date": requested_date,
        "trade_date": actual_date,
        "data_source": daily_source,
        "rows": trends,
        "count": len(trends),
        "cached_for_seconds": CACHE_TTL_SECONDS,
        "fetched_at": datetime.now().isoformat(timespec="seconds"),
    }


@router.get("/api/backtest/short-swing", response_model=BacktestResponse)
async def short_swing_backtest(
    end_date: Annotated[str | None, Query()] = None,
    trade_days: Annotated[int, Query(ge=4, le=20)] = 8,
    per_day_limit: Annotated[int, Query(ge=3, le=15)] = 8,
) -> dict[str, Any]:
    checked_end = _validate_trade_date(end_date or _previous_calendar_date(_today_trade_date()))
    return await _short_swing_backtest_payload(checked_end, trade_days, per_day_limit)


@router.get("/api/stock/{ts_code}/history", response_model=StockHistoryResponse)
async def stock_history(
    ts_code: str,
    end_date: Annotated[str | None, Query()] = None,
    days: Annotated[int, Query(ge=20, le=240)] = 80,
) -> dict[str, Any]:
    checked_code = _validate_ts_code(ts_code)
    checked_end = _validate_trade_date(end_date or _today_trade_date())
    rows = await _stock_history(checked_code, checked_end, days)
    return {
        "ts_code": checked_code,
        "end_date": rows[-1].get("trade_date") if rows else checked_end,
        "requested_end_date": checked_end,
        "data_source": _data_source("daily", str(rows[-1].get("trade_date"))) if rows else "empty",
        "rows": rows,
        "summary": _summarize(rows),
        "cached_for_seconds": CACHE_TTL_SECONDS,
        "fetched_at": datetime.now().isoformat(timespec="seconds"),
    }


async def _analysis_payload(ts_code: str, end_date: str) -> dict[str, Any]:
    checked_code = _validate_ts_code(ts_code)
    checked_end = _validate_trade_date(end_date)
    return await stock_decision.analysis_payload(checked_code, checked_end)


@router.get("/api/stock/{ts_code}/analysis", response_model=StockAnalysisResponse)
async def stock_analysis(
    ts_code: str,
    end_date: Annotated[str | None, Query()] = None,
) -> dict[str, Any]:
    return await _analysis_payload(ts_code, end_date or _previous_calendar_date(_today_trade_date()))


@router.get("/api/stock/{ts_code}/recommendation", response_model=StockRecommendationResponse)
async def stock_recommendation(
    ts_code: str,
    end_date: Annotated[str | None, Query()] = None,
) -> dict[str, Any]:
    checked_code = _validate_ts_code(ts_code)
    checked_end = _validate_trade_date(end_date or _previous_calendar_date(_today_trade_date()))
    return await stock_decision.recommendation_payload(
        checked_code,
        checked_end,
        os.getenv(AI_MODEL_ENV, ""),
    )


@router.get("/api/query/{interface}", response_model=QueryResponse)
async def query_interface(
    interface: str,
    ts_code: Annotated[str | None, Query()] = None,
    trade_date: Annotated[str | None, Query()] = None,
    start_date: Annotated[str | None, Query()] = None,
    end_date: Annotated[str | None, Query()] = None,
) -> dict[str, Any]:
    if interface not in ALLOWED_QUERY_FIELDS:
        raise HTTPException(status_code=404, detail="暂不支持这个接口")

    params: dict[str, Any] = {"fields": ALLOWED_QUERY_FIELDS[interface]}
    if interface == "stock_basic":
        params["list_status"] = "L"
    else:
        if ts_code:
            params["ts_code"] = _validate_ts_code(ts_code)
        if trade_date:
            params["trade_date"] = _validate_trade_date(trade_date)
        if start_date:
            params["start_date"] = _validate_trade_date(start_date)
        if end_date:
            params["end_date"] = _validate_trade_date(end_date)

    if interface in {"daily", "daily_basic", "moneyflow"} and not (
        params.get("ts_code") or params.get("trade_date") or params.get("start_date")
    ):
        params["trade_date"] = _previous_calendar_date(_today_trade_date())

    key = ("query", interface, tuple(sorted(params.items())))
    cached = _cache_get(key)
    source = "memory"
    if cached is None:
        rows, source = await _query_rows_cached(interface, params)
        cached = _cache_set(key, rows[:6000])

    return {
        "interface": interface,
        "columns": list(cached[0].keys()) if cached else ALLOWED_QUERY_FIELDS[interface].split(","),
        "rows": cached,
        "count": len(cached),
        "data_source": source,
        "cached_for_seconds": CACHE_TTL_SECONDS,
        "fetched_at": datetime.now().isoformat(timespec="seconds"),
    }


@router.get("/api/daily.csv")
async def daily_csv(
    trade_date: Annotated[str | None, Query()] = None,
    fields: Annotated[str | None, Query()] = None,
) -> Response:
    checked_date = _validate_trade_date(trade_date or _today_trade_date())
    rows = await _daily_rows(checked_date, fields)
    return _csv_response(rows, f"tushare_daily_{checked_date}.csv")


@router.get("/api/health", response_model=HealthResponse)
async def health() -> dict[str, bool]:
    return {"ok": True}

