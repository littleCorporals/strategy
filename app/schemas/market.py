from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class StatusResponse(BaseModel):
    ok: bool
    sdk_available: bool
    token_configured: bool
    token_preview: str | None = None
    proxy_url: str
    min_interval: float
    cache_ttl_seconds: int
    database: dict[str, Any]
    database_ready: bool
    default_trade_date: str
    latest_db_trade_date: str | None = None
    online_refresh_after: str
    tushare_blocked_remaining_seconds: int
    tushare_block_message: str


class StockBasicResponse(BaseModel):
    count: int
    items: dict[str, dict[str, Any]]
    fetched_at: str


class MarketRowsResponse(BaseModel):
    requested_trade_date: str | None = None
    trade_date: str | None = None
    fallback_used: bool | None = None
    data_source: str | None = None
    database_cached: bool | None = None
    online_refresh_after: str | None = None
    columns: list[str] | None = None
    rows: list[dict[str, Any]]
    count: int | None = None
    summary: dict[str, Any] | None = None
    cached_for_seconds: int
    fetched_at: str


class IndustryTrendsResponse(BaseModel):
    requested_trade_date: str
    trade_date: str
    data_source: str
    rows: list[dict[str, Any]]
    count: int
    cached_for_seconds: int
    fetched_at: str


class BacktestResponse(BaseModel):
    requested_end_date: str
    end_date: str
    validated_until: str | None = None
    signal_dates: list[str]
    tested_days: int
    per_day_limit: int | None = None
    results: list[dict[str, Any]]
    suggestion: dict[str, Any]
    cached_for_seconds: int | None = None
    fetched_at: str


class StockHistoryResponse(BaseModel):
    ts_code: str
    end_date: str
    requested_end_date: str
    data_source: str
    rows: list[dict[str, Any]]
    summary: dict[str, Any]
    cached_for_seconds: int
    fetched_at: str


class StockAnalysisResponse(BaseModel):
    ts_code: str
    requested_end_date: str | None = None
    trade_date: str
    actual_trade_date: str | None = None
    trend: dict[str, Any]
    money: dict[str, Any]
    valuation: dict[str, Any]
    support_resistance: dict[str, Any]
    risk: dict[str, Any]
    forecast: dict[str, Any]
    daily_basic: dict[str, Any] | None = None
    moneyflow: dict[str, Any] | None = None
    cached_for_seconds: int
    fetched_at: str


class StockRecommendationResponse(BaseModel):
    ts_code: str
    requested_end_date: str | None = None
    trade_date: str
    actual_trade_date: str | None = None
    analysis: dict[str, Any]
    sources: dict[str, Any]
    recommendation: dict[str, Any]
    ai_configured: bool
    cached_for_seconds: int
    fetched_at: str


class QueryResponse(BaseModel):
    interface: str
    columns: list[str]
    rows: list[dict[str, Any]]
    count: int
    data_source: str
    cached_for_seconds: int
    fetched_at: str


class HealthResponse(BaseModel):
    ok: bool = Field(default=True)
