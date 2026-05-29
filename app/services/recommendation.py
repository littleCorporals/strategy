from __future__ import annotations

import math
from datetime import date, datetime, timedelta
from typing import Any

from app.clients import ai_client
from app.repositories import market_cache
from app.services import analysis, market_data


def ai_configured() -> bool:
    return ai_client.configured()


def short_swing_conditions(row: dict[str, Any], history: list[dict[str, Any]]) -> tuple[bool, dict[str, Any]]:
    pct = analysis.number(row, "pct_chg")
    volume_ratio = analysis.number(row, "volume_ratio")
    turnover = analysis.number(row, "turnover_rate")
    circ_mv = analysis.number(row, "circ_mv")
    total_mv = analysis.number(row, "total_mv")
    market_value = circ_mv if circ_mv is not None else total_mv
    closes = [analysis.number(item, "close") for item in history]
    vols = [analysis.number(item, "vol") for item in history]
    closes = [value for value in closes if value is not None]
    vols = [value for value in vols if value is not None]
    ma5 = analysis.avg(closes[-5:]) if len(closes) >= 5 else None
    ma10 = analysis.avg(closes[-10:]) if len(closes) >= 10 else None
    ma20 = analysis.avg(closes[-20:]) if len(closes) >= 20 else None
    vol5 = analysis.avg(vols[-5:]) if len(vols) >= 5 else None
    prev_vol5 = analysis.avg(vols[-10:-5]) if len(vols) >= 10 else None
    today_vol = vols[-1] if vols else None
    volume_expand = bool(
        today_vol is not None
        and vol5 is not None
        and prev_vol5 is not None
        and today_vol >= vol5 * 1.05
        and today_vol <= vol5 * 1.9
        and vol5 >= prev_vol5 * 1.02
        and vol5 <= prev_vol5 * 1.8
    )
    ma_bullish = bool(
        ma5 is not None
        and ma10 is not None
        and ma20 is not None
        and ma5 > ma10 > ma20
        and closes
        and closes[-1] >= ma5
    )
    checks = {
        "量比>1": volume_ratio is not None and volume_ratio > 1,
        "换手5-10%": turnover is not None and 5 <= turnover <= 10,
        "均线多头": ma_bullish,
        "成交量温和放大": volume_expand,
        "市值1-500亿": market_value is not None and 10000 <= market_value <= 5_000_000,
        "涨幅2-4%": pct is not None and 1.8 <= pct <= 4.2,
    }
    metrics = {
        "pct_chg": analysis.round_number(pct, 2),
        "volume_ratio": analysis.round_number(volume_ratio, 2),
        "turnover_rate": analysis.round_number(turnover, 2),
        "market_value_yi": analysis.round_number((market_value / 10000) if market_value is not None else None, 2),
        "ma5": analysis.round_number(ma5, 2),
        "ma10": analysis.round_number(ma10, 2),
        "ma20": analysis.round_number(ma20, 2),
        "today_vol": analysis.round_number(today_vol, 2),
        "vol5": analysis.round_number(vol5, 2),
        "prev_vol5": analysis.round_number(prev_vol5, 2),
    }
    return all(checks.values()), {"checks": checks, "metrics": metrics}


async def recommendation_pool(
    rows: list[dict[str, Any]],
    end_date: str,
    limit: int = 30,
) -> list[dict[str, Any]]:
    picked: list[dict[str, Any]] = []
    prefiltered: list[dict[str, Any]] = []
    for row in rows:
        pct = analysis.number(row, "pct_chg")
        volume_ratio = analysis.number(row, "volume_ratio")
        turnover = analysis.number(row, "turnover_rate")
        circ_mv = analysis.number(row, "circ_mv")
        total_mv = analysis.number(row, "total_mv")
        market_value = circ_mv if circ_mv is not None else total_mv
        if pct is None or not 1.8 <= pct <= 4.2:
            continue
        if volume_ratio is None or volume_ratio <= 1:
            continue
        if turnover is None or not 5 <= turnover <= 10:
            continue
        if market_value is None or not 10000 <= market_value <= 5_000_000:
            continue
        prefiltered.append(row)
    prefiltered.sort(key=lambda item: analysis.number(item, "amount") or 0, reverse=True)

    for row in prefiltered[: min(max(limit * 2, 24), 36)]:
        history = await market_data.stock_history(str(row.get("ts_code")), end_date, 24)
        passed, condition_payload = short_swing_conditions(row, history)
        if not passed:
            continue
        pct = analysis.number(row, "pct_chg") or 0
        close = analysis.number(row, "close") or 0
        open_ = analysis.number(row, "open") or close
        high = analysis.number(row, "high") or close
        low = analysis.number(row, "low") or close
        amount = analysis.number(row, "amount") or 0
        vol = analysis.number(row, "vol") or 0
        near_high = high > 0 and close / high > 0.985
        amplitude = ((high - low) / max(close, 1)) * 100
        intraday_position = ((close - low) / max(high - low, 0.01)) * 100 if high > low else 50
        if amount <= 0 or close <= 0:
            continue
        if amplitude > 12:
            continue
        score = 0.0
        reasons: list[str] = []
        if 1.8 <= pct <= 3.2:
            score += 34
            reasons.append("涨幅约2%-3%")
        elif 3.2 < pct <= 4.2:
            score += 28
            reasons.append("涨幅接近4%")
        if close >= open_:
            score += 16
            reasons.append("收盘强于开盘")
        if 45 <= intraday_position <= 88:
            score += 18
            reasons.append("收盘位置可交易")
        elif intraday_position > 88:
            score -= 10
            reasons.append("接近日内高点")
        if 2 <= amplitude <= 8:
            score += 16
            reasons.append("波动不过热")
        elif amplitude < 2:
            score += 6
            reasons.append("波动偏窄")
        score += min(22, math.log10(max(amount, 1)) * 2.8)
        if near_high:
            score -= 8
        if vol > 0:
            score += min(6, math.log10(max(vol, 1)) * 0.5)
        if score < 45:
            continue
        plan_type = "短线回踩" if pct > 3.2 else "短线低吸"
        if close < open_:
            plan_type = "只观察"
        reason = "、".join(reasons[:4]) or "满足短线形态条件"
        picked.append(
            {
                **row,
                "recommend_score": round(score, 2),
                "recommend_reason": reason,
                "recommend_type": plan_type,
                "strategy_name": "短线形态筛选",
                "screen_conditions": condition_payload["checks"],
                "screen_metrics": condition_payload["metrics"],
                "entry_low": round(close * 0.985, 2),
                "entry_high": round(close * 1.015, 2),
                "stop_price": round(max(low, close * 0.955), 2),
                "target_price": round(close * 1.055, 2),
                "intraday_position": round(intraday_position, 2),
            }
        )
    picked.sort(key=lambda item: item["recommend_score"], reverse=True)
    return picked[:limit]


async def attach_next_day_validation(picks: list[dict[str, Any]], trade_date: str) -> list[dict[str, Any]]:
    if not picks:
        return picks
    next_date, rows = await market_data.next_trade_rows(trade_date, market_data.DAILY_FIELDS)
    if not next_date or not rows:
        return picks
    next_by_code = {str(row.get("ts_code")): row for row in rows if row.get("ts_code")}
    validated: list[dict[str, Any]] = []
    for row in picks:
        close = analysis.number(row, "close")
        next_row = next_by_code.get(str(row.get("ts_code")))
        if not close or not next_row:
            validated.append(row)
            continue
        next_open = analysis.number(next_row, "open")
        next_high = analysis.number(next_row, "high")
        next_low = analysis.number(next_row, "low")
        next_close = analysis.number(next_row, "close")
        entry_low = analysis.number(row, "entry_low")
        entry_high = analysis.number(row, "entry_high")
        stop_price = analysis.number(row, "stop_price")
        target_price = analysis.number(row, "target_price")
        entry_hit = bool(
            entry_low is not None
            and entry_high is not None
            and next_low is not None
            and next_high is not None
            and next_low <= entry_high
            and next_high >= entry_low
        )
        stop_hit = bool(stop_price is not None and next_low is not None and next_low <= stop_price)
        target_hit = bool(target_price is not None and next_high is not None and next_high >= target_price)
        validation = {
            "trade_date": next_date,
            "open_gap_pct": analysis.round_number(((next_open - close) / close) * 100, 2) if next_open else None,
            "high_pct": analysis.round_number(((next_high - close) / close) * 100, 2) if next_high else None,
            "low_pct": analysis.round_number(((next_low - close) / close) * 100, 2) if next_low else None,
            "close_pct": analysis.round_number(((next_close - close) / close) * 100, 2) if next_close else None,
            "entry_hit": entry_hit,
            "stop_hit": stop_hit,
            "target_hit": target_hit,
        }
        if target_hit:
            result = "次日触及目标"
        elif entry_hit and not stop_hit and validation["close_pct"] is not None and validation["close_pct"] > 0:
            result = "次日可交易"
        elif stop_hit:
            result = "次日破位"
        elif validation["open_gap_pct"] is not None and validation["open_gap_pct"] > 3:
            result = "高开不追"
        else:
            result = "次日一般"
        validation["result"] = result
        validated.append({**row, "next_day": validation})
    return validated


def industry_trends(rows: list[dict[str, Any]], limit: int = 20) -> list[dict[str, Any]]:
    groups: dict[str, dict[str, Any]] = {}
    for row in rows:
        industry = str(row.get("industry") or "未分类")
        group = groups.setdefault(
            industry,
            {
                "industry": industry,
                "count": 0,
                "up": 0,
                "down": 0,
                "strong": 0,
                "pct_sum": 0.0,
                "amount_total": 0.0,
                "top_stock": None,
                "top_pct": -999.0,
            },
        )
        pct = analysis.number(row, "pct_chg") or 0
        amount = analysis.number(row, "amount") or 0
        group["count"] += 1
        group["pct_sum"] += pct
        group["amount_total"] += amount
        if pct > 0:
            group["up"] += 1
        elif pct < 0:
            group["down"] += 1
        if pct >= 5:
            group["strong"] += 1
        if pct > group["top_pct"]:
            group["top_pct"] = pct
            group["top_stock"] = {
                "ts_code": row.get("ts_code"),
                "name": row.get("name"),
                "pct_chg": pct,
            }

    trends: list[dict[str, Any]] = []
    for group in groups.values():
        count = group["count"]
        up_ratio = (group["up"] / count) * 100 if count else 0
        avg_pct = group["pct_sum"] / count if count else 0
        score = avg_pct * 8 + up_ratio * 0.45 + group["strong"] * 2 + math.log10(max(group["amount_total"], 1)) * 5
        trends.append(
            {
                "industry": group["industry"],
                "count": count,
                "up": group["up"],
                "down": group["down"],
                "strong": group["strong"],
                "up_ratio": round(up_ratio, 2),
                "avg_pct_chg": round(avg_pct, 4),
                "amount_total": round(group["amount_total"], 4),
                "score": round(score, 2),
                "top_stock": group["top_stock"],
            }
        )
    trends.sort(key=lambda item: item["score"], reverse=True)
    return trends[:limit]


async def message_sources(ts_code: str, trade_date: str) -> dict[str, Any]:
    cache_key = f"{ts_code}:{trade_date}"
    cached = await market_cache.get_payload("message_sources", cache_key)
    if cached is not None:
        return cached

    start_day = datetime.strptime(trade_date, "%Y%m%d").date() - timedelta(days=30)
    sources: dict[str, Any] = {"announcements": [], "cninfo": [], "news": [], "errors": []}
    try:
        sources["cninfo"] = await market_data.cninfo_announcements(
            ts_code,
            start_day,
            datetime.strptime(trade_date, "%Y%m%d").date(),
        )
    except Exception as exc:
        sources["errors"].append(f"巨潮公告未取到：{exc}")
    sources["errors"].append("已停用 Tushare 付费新闻/公告接口，避免未授权请求触发临时封禁")
    await market_cache.set_payload("message_sources", cache_key, sources)
    return sources


async def cninfo_stock_map() -> dict[str, dict[str, Any]]:
    return await market_data.cninfo_stock_map()


async def cninfo_announcements(ts_code: str, start_day: date, end_day: date) -> list[dict[str, Any]]:
    return await market_data.cninfo_announcements(ts_code, start_day, end_day)


def fallback_recommendation(stock_analysis: dict[str, Any], sources: dict[str, Any]) -> dict[str, Any]:
    trend = stock_analysis.get("trend", {})
    money = stock_analysis.get("money", {})
    valuation = stock_analysis.get("valuation", {})
    risk = stock_analysis.get("risk", {})
    source_count = (
        len(sources.get("cninfo", []))
        + len(sources.get("announcements", []))
        + len(sources.get("news", []))
    )
    if not source_count:
        verification = "未验证：没有拿到公告或新闻来源"
    elif sources.get("cninfo"):
        verification = "已核验：取到巨潮资讯公告（一手披露来源）"
    elif sources.get("errors"):
        verification = "部分验证：部分消息源不可用"
    else:
        verification = "已取到消息源，需人工点开原文复核"

    trend_score = int(trend.get("score") or 0)
    risk_score = int(risk.get("score") or 100)
    money_net = money.get("net")
    if trend_score >= 75 and risk_score < 65 and (money_net is None or money_net >= 0):
        action = "观察买入"
        confidence = 72 if source_count else 55
    elif trend_score >= 55 and risk_score < 75:
        action = "等待回踩"
        confidence = 62 if source_count else 48
    else:
        action = "暂不买入"
        confidence = 58
    reasons = [
        f"趋势：{trend.get('level', '--')}，强度 {trend_score}",
        f"资金：{money.get('level', '--')}",
        f"估值：{valuation.get('level', '--')}",
        f"风险：{risk.get('level', '--')}",
    ]
    return {
        "action": action,
        "confidence": confidence,
        "verification": verification,
        "reasons": reasons,
        "risks": valuation.get("notes") or ["消息源不足时不应重仓"],
        "conditions": ["等回踩不破支撑", "放量但不过热", "消息原文无重大利空"],
        "source_count": source_count,
        "model_used": "rules",
    }


async def ai_recommendation(
    stock_analysis: dict[str, Any],
    sources: dict[str, Any],
    ai_configured: bool,
) -> dict[str, Any]:
    if not ai_configured:
        return fallback_recommendation(stock_analysis, sources)

    try:
        return await ai_client.stock_recommendation(stock_analysis, sources)
    except ai_client.AI_CLIENT_ERRORS as exc:
        fallback = fallback_recommendation(stock_analysis, sources)
        fallback["model_used"] = "rules_fallback"
        fallback["verification"] = f"{fallback['verification']}；AI 调用失败，已使用本地规则"
        fallback["ai_error"] = str(exc)
        return fallback
