from __future__ import annotations

from datetime import datetime
from typing import Any

from app.core.config import CACHE_TTL_SECONDS
from app.repositories import market_cache
from app.services import analysis, market_data, recommendation


async def analysis_payload(ts_code: str, end_date: str) -> dict[str, Any]:
    key = ("analysis", ts_code, end_date)
    cached = market_data.cache_get(key)
    if cached is not None:
        return cached

    history = await market_data.stock_history(ts_code, end_date, 80)
    latest_daily = history[-1] if history else {}
    actual_trade_date = str(latest_daily.get("trade_date") or "")
    lookup_trade_date = actual_trade_date or end_date
    daily_basic = await market_data.single_query_row("daily_basic", ts_code=ts_code, trade_date=lookup_trade_date)
    moneyflow = await market_data.single_query_row("moneyflow", ts_code=ts_code, trade_date=lookup_trade_date)
    close = analysis.number(latest_daily, "close") if latest_daily else None
    trend = analysis.trend_analysis(history)
    money = analysis.money_analysis(moneyflow, latest_daily)
    valuation = analysis.valuation_analysis(daily_basic)
    support_resistance = analysis.support_resistance(history, close)
    risk = analysis.risk_summary(trend, money, valuation, support_resistance)
    forecast = analysis.next_day_forecast(latest_daily, trend, money, valuation, support_resistance, risk)

    payload = {
        "ts_code": ts_code,
        "requested_end_date": end_date,
        "trade_date": lookup_trade_date,
        "actual_trade_date": actual_trade_date or None,
        "trend": trend,
        "money": money,
        "valuation": valuation,
        "support_resistance": support_resistance,
        "risk": risk,
        "forecast": forecast,
        "daily_basic": daily_basic,
        "moneyflow": moneyflow,
        "cached_for_seconds": CACHE_TTL_SECONDS,
        "fetched_at": datetime.now().isoformat(timespec="seconds"),
    }
    return market_data.cache_set(key, payload)


async def recommendation_payload(ts_code: str, end_date: str, ai_model_key: str = "") -> dict[str, Any]:
    key = ("recommendation", ts_code, end_date, ai_model_key)
    cached = market_data.cache_get(key)
    if cached is not None:
        return cached

    db_key = f"v2:{ts_code}:{end_date}:{ai_model_key}"
    db_cached = await market_cache.get_payload("stock_recommendation", db_key)
    if db_cached is not None:
        return market_data.cache_set(key, db_cached)

    stock_analysis = await analysis_payload(ts_code, end_date)
    actual_trade_date = str(stock_analysis.get("actual_trade_date") or stock_analysis.get("trade_date") or end_date)
    sources = await recommendation.message_sources(ts_code, actual_trade_date)
    advice = await recommendation.ai_recommendation(
        stock_analysis,
        sources,
        recommendation.ai_configured(),
    )
    payload = {
        "ts_code": ts_code,
        "requested_end_date": end_date,
        "trade_date": actual_trade_date,
        "actual_trade_date": actual_trade_date,
        "analysis": stock_analysis,
        "sources": sources,
        "recommendation": advice,
        "ai_configured": recommendation.ai_configured(),
        "cached_for_seconds": CACHE_TTL_SECONDS,
        "fetched_at": datetime.now().isoformat(timespec="seconds"),
    }
    await market_cache.set_payload("stock_recommendation", db_key, payload)
    return market_data.cache_set(key, payload)
