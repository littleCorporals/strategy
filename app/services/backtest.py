from __future__ import annotations

import math
from datetime import datetime, timedelta
from typing import Any

from app.core.config import CACHE_TTL_SECONDS
from app.services import analysis, market_data


STRATEGIES: list[dict[str, Any]] = [
    {
        "id": "user_strict",
        "name": "当前严格条件",
        "note": "完全贴近你给的六条筛选条件，适合做主推荐池。",
        "pct_min": 1.8,
        "pct_max": 4.2,
        "turnover_min": 5.0,
        "turnover_max": 10.0,
        "volume_ratio_min": 1.0,
        "volume_ratio_max": 3.0,
        "market_value_min_yi": 1.0,
        "market_value_max_yi": 500.0,
        "volume_expand_min": 1.05,
        "volume_expand_max": 1.90,
    },
    {
        "id": "low_pullback",
        "name": "2%低吸优先",
        "note": "降低追涨感，偏向次日还能给低吸机会的温和上涨。",
        "pct_min": 1.2,
        "pct_max": 3.2,
        "turnover_min": 4.0,
        "turnover_max": 10.0,
        "volume_ratio_min": 1.0,
        "volume_ratio_max": 2.6,
        "market_value_min_yi": 20.0,
        "market_value_max_yi": 500.0,
        "volume_expand_min": 1.03,
        "volume_expand_max": 1.75,
    },
    {
        "id": "calm_confirm",
        "name": "温和确认",
        "note": "放宽到1%左右涨幅，但要求换手和量能不过热。",
        "pct_min": 1.0,
        "pct_max": 2.8,
        "turnover_min": 3.0,
        "turnover_max": 8.0,
        "volume_ratio_min": 0.9,
        "volume_ratio_max": 2.2,
        "market_value_min_yi": 20.0,
        "market_value_max_yi": 500.0,
        "volume_expand_min": 1.02,
        "volume_expand_max": 1.60,
    },
    {
        "id": "strong_confirm",
        "name": "强势确认",
        "note": "更强调量比和换手，适合市场宽度较强时使用。",
        "pct_min": 2.0,
        "pct_max": 4.0,
        "turnover_min": 6.0,
        "turnover_max": 12.0,
        "volume_ratio_min": 1.2,
        "volume_ratio_max": 3.2,
        "market_value_min_yi": 1.0,
        "market_value_max_yi": 300.0,
        "volume_expand_min": 1.05,
        "volume_expand_max": 2.10,
    },
    {
        "id": "mid_small_active",
        "name": "中小市值活跃",
        "note": "更偏中小市值活跃股，但过滤过热放量。",
        "pct_min": 1.5,
        "pct_max": 4.0,
        "turnover_min": 5.0,
        "turnover_max": 12.0,
        "volume_ratio_min": 1.1,
        "volume_ratio_max": 2.8,
        "market_value_min_yi": 20.0,
        "market_value_max_yi": 300.0,
        "volume_expand_min": 1.03,
        "volume_expand_max": 1.90,
    },
    {
        "id": "wide_but_not_hot",
        "name": "宽口径不过热",
        "note": "用于样本不足时扩池，重点看是否比严格条件更稳定。",
        "pct_min": 1.0,
        "pct_max": 4.0,
        "turnover_min": 3.0,
        "turnover_max": 10.0,
        "volume_ratio_min": 0.9,
        "volume_ratio_max": 2.5,
        "market_value_min_yi": 50.0,
        "market_value_max_yi": 500.0,
        "volume_expand_min": 1.00,
        "volume_expand_max": 1.70,
    },
]


def market_value_yi(row: dict[str, Any]) -> float | None:
    circ_mv = analysis.number(row, "circ_mv")
    total_mv = analysis.number(row, "total_mv")
    market_value = circ_mv if circ_mv is not None else total_mv
    return (market_value / 10000) if market_value is not None else None


def factor_strategy_conditions(row: dict[str, Any], strategy: dict[str, Any]) -> tuple[bool, dict[str, Any]]:
    pct = analysis.number(row, "pct_chg")
    volume_ratio = analysis.number(row, "volume_ratio")
    turnover = analysis.number(row, "turnover_rate")
    mv_yi = market_value_yi(row)
    ma5 = analysis.number(row, "ma_bfq_5")
    ma10 = analysis.number(row, "ma_bfq_10")
    ma20 = analysis.number(row, "ma_bfq_20")
    close = analysis.number(row, "close")
    vol = analysis.number(row, "vol")
    amount = analysis.number(row, "amount")
    ma_bullish = bool(
        ma5 is not None
        and ma10 is not None
        and ma20 is not None
        and ma5 > ma10 > ma20
        and close is not None
        and close >= ma5
    )
    volume_expand = bool(
        volume_ratio is not None
        and strategy["volume_ratio_min"] <= volume_ratio <= strategy["volume_ratio_max"]
    )
    checks = {
        "涨幅区间": pct is not None and strategy["pct_min"] <= pct <= strategy["pct_max"],
        "量比区间": volume_expand,
        "换手区间": turnover is not None and strategy["turnover_min"] <= turnover <= strategy["turnover_max"],
        "均线多头": ma_bullish,
        "成交量温和放大": volume_expand,
        "市值区间": mv_yi is not None
        and strategy["market_value_min_yi"] <= mv_yi <= strategy["market_value_max_yi"],
    }
    metrics = {
        "pct_chg": analysis.round_number(pct, 2),
        "volume_ratio": analysis.round_number(volume_ratio, 2),
        "turnover_rate": analysis.round_number(turnover, 2),
        "market_value_yi": analysis.round_number(mv_yi, 2),
        "ma5": analysis.round_number(ma5, 2),
        "ma10": analysis.round_number(ma10, 2),
        "ma20": analysis.round_number(ma20, 2),
        "today_vol": analysis.round_number(vol, 2),
        "amount": analysis.round_number(amount, 2),
    }
    return all(checks.values()), {"checks": checks, "metrics": metrics}


def screen_score(row: dict[str, Any]) -> float:
    pct = analysis.number(row, "pct_chg") or 0
    close = analysis.number(row, "close") or 0
    open_ = analysis.number(row, "open") or close
    high = analysis.number(row, "high") or close
    low = analysis.number(row, "low") or close
    amount = analysis.number(row, "amount") or 0
    turnover = analysis.number(row, "turnover_rate") or 0
    volume_ratio = analysis.number(row, "volume_ratio") or 0
    amplitude = ((high - low) / max(close, 1)) * 100 if high and low else 0
    intraday_position = ((close - low) / max(high - low, 0.01)) * 100 if high > low else 50
    score = 36 - abs(pct - 2.4) * 5
    if close >= open_:
        score += 12
    if 40 <= intraday_position <= 86:
        score += 16
    elif intraday_position > 92:
        score -= 12
    if 2 <= amplitude <= 8:
        score += 14
    elif amplitude > 10:
        score -= 16
    if 5 <= turnover <= 10:
        score += 10
    if 1.0 <= volume_ratio <= 2.2:
        score += 10
    score += min(16, math.log10(max(amount, 1)) * 2.0)
    return round(max(0, score), 2)


def build_signal(row: dict[str, Any], strategy: dict[str, Any], condition_payload: dict[str, Any]) -> dict[str, Any]:
    close = analysis.number(row, "close") or 0
    low = analysis.number(row, "low") or close
    score = screen_score(row)
    return {
        **row,
        "strategy_id": strategy["id"],
        "strategy_name": strategy["name"],
        "recommend_score": score,
        "screen_conditions": condition_payload["checks"],
        "screen_metrics": condition_payload["metrics"],
        "entry_low": round(close * 0.985, 2) if close else None,
        "entry_high": round(close * 1.012, 2) if close else None,
        "stop_price": round(max(low, close * 0.955), 2) if close else None,
        "target_price": round(close * 1.045, 2) if close else None,
    }


def validate_next_day_signal(row: dict[str, Any], next_row: dict[str, Any], next_date: str) -> dict[str, Any] | None:
    close = analysis.number(row, "close")
    if not close:
        return None
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
    open_gap_pct = ((next_open - close) / close) * 100 if next_open else None
    close_pct = ((next_close - close) / close) * 100 if next_close else None
    high_pct = ((next_high - close) / close) * 100 if next_high else None
    low_pct = ((next_low - close) / close) * 100 if next_low else None
    high_open_no_entry = bool(open_gap_pct is not None and open_gap_pct > 3 and not entry_hit)
    if target_hit:
        result = "次日触及目标"
    elif entry_hit and not stop_hit and close_pct is not None and close_pct > 0:
        result = "次日可交易"
    elif stop_hit:
        result = "次日破位"
    elif high_open_no_entry:
        result = "高开不追"
    else:
        result = "次日一般"
    return {
        "trade_date": next_date,
        "open_gap_pct": analysis.round_number(open_gap_pct, 2),
        "high_pct": analysis.round_number(high_pct, 2),
        "low_pct": analysis.round_number(low_pct, 2),
        "close_pct": analysis.round_number(close_pct, 2),
        "entry_hit": entry_hit,
        "stop_hit": stop_hit,
        "target_hit": target_hit,
        "high_open_no_entry": high_open_no_entry,
        "result": result,
    }


async def recent_factor_dates(end_date: str, trade_days: int) -> tuple[str, list[str]]:
    actual_end, _rows = await market_data.latest_factor_rows(end_date)
    current = datetime.strptime(actual_end, "%Y%m%d").date()
    dates: list[str] = []
    checked = 0
    while len(dates) < trade_days and checked < trade_days * 4:
        if current.weekday() < 5:
            day = current.strftime("%Y%m%d")
            rows = await market_data.stk_factor_rows(day)
            if rows:
                dates.append(day)
        current -= timedelta(days=1)
        checked += 1
    dates.reverse()
    return actual_end, dates


def aggregate_backtest_events(
    strategy: dict[str, Any],
    events: list[dict[str, Any]],
    tested_days: int,
) -> dict[str, Any]:
    count = len(events)
    close_returns = [
        value for item in events if (value := analysis.number(item.get("next_day", {}), "close_pct")) is not None
    ]
    high_returns = [
        value for item in events if (value := analysis.number(item.get("next_day", {}), "high_pct")) is not None
    ]
    low_returns = [
        value for item in events if (value := analysis.number(item.get("next_day", {}), "low_pct")) is not None
    ]
    wins = sum(1 for value in close_returns if value > 0)
    entry_hits = sum(1 for item in events if item.get("next_day", {}).get("entry_hit"))
    target_hits = sum(1 for item in events if item.get("next_day", {}).get("target_hit"))
    stop_hits = sum(1 for item in events if item.get("next_day", {}).get("stop_hit"))
    high_open_no_entry = sum(1 for item in events if item.get("next_day", {}).get("high_open_no_entry"))
    tradable_wins = sum(
        1
        for item in events
        if item.get("next_day", {}).get("entry_hit")
        and not item.get("next_day", {}).get("stop_hit")
        and (analysis.number(item.get("next_day", {}), "close_pct") or 0) > 0
    )
    win_rate = (wins / count) * 100 if count else 0
    entry_hit_rate = (entry_hits / count) * 100 if count else 0
    tradable_win_rate = (tradable_wins / max(entry_hits, 1)) * 100 if entry_hits else 0
    target_hit_rate = (target_hits / count) * 100 if count else 0
    stop_hit_rate = (stop_hits / count) * 100 if count else 0
    no_entry_rate = (high_open_no_entry / count) * 100 if count else 0
    avg_close = analysis.avg(close_returns) or 0
    avg_high = analysis.avg(high_returns) or 0
    avg_low = analysis.avg(low_returns) or 0
    sample_score = min(10, math.log1p(count) * 3.0) if count else 0
    quality = win_rate * 0.42 + target_hit_rate * 0.22 + avg_close * 7 + avg_high * 1.5
    quality -= stop_hit_rate * 0.20 + no_entry_rate * 0.10
    quality += sample_score
    if count < max(5, tested_days // 2):
        quality -= 10
    quality = max(0, min(100, quality))
    examples = sorted(
        events,
        key=lambda item: (str(item.get("trade_date") or ""), item.get("recommend_score") or 0),
        reverse=True,
    )[:8]
    return {
        "id": strategy["id"],
        "name": strategy["name"],
        "note": strategy["note"],
        "params": {key: strategy[key] for key in strategy if key not in {"id", "name", "note"}},
        "tested_days": tested_days,
        "signal_count": count,
        "avg_signals_per_day": analysis.round_number(count / tested_days if tested_days else 0, 2),
        "win_rate": analysis.round_number(win_rate, 2),
        "entry_hit_rate": analysis.round_number(entry_hit_rate, 2),
        "tradable_win_rate": analysis.round_number(tradable_win_rate, 2),
        "target_hit_rate": analysis.round_number(target_hit_rate, 2),
        "stop_hit_rate": analysis.round_number(stop_hit_rate, 2),
        "high_open_no_entry_rate": analysis.round_number(no_entry_rate, 2),
        "avg_next_close_pct": analysis.round_number(avg_close, 3),
        "avg_next_high_pct": analysis.round_number(avg_high, 3),
        "avg_next_low_pct": analysis.round_number(avg_low, 3),
        "quality_score": analysis.round_number(quality, 2),
        "quality_label": "可做主策略" if quality >= 62 and count >= 6 else "适合观察" if quality >= 48 else "暂不优先",
        "examples": examples,
    }


def backtest_suggestion(results: list[dict[str, Any]], tested_days: int) -> dict[str, Any]:
    qualified = [item for item in results if item["signal_count"] >= max(5, tested_days // 2)]
    ranked = qualified or [item for item in results if item["signal_count"] > 0]
    if not ranked:
        return {
            "title": "样本不足，暂不调整策略",
            "text": "这段历史里没有足够候选股同时满足趋势、量能、换手和市值条件。",
            "rules": ["先扩大回测交易日数", "或者临时放宽涨幅到1%-4%", "没有样本时不应强行推荐"],
        }
    best = ranked[0]
    params = best["params"]
    rules: list[str] = []
    if params["pct_max"] <= 3.2:
        rules.append("推荐优先看1%-3%左右的温和上涨，减少追4%以上的票。")
    else:
        rules.append("涨幅可以保留到4%左右，但必须配合均线和量能确认。")
    if params["turnover_min"] < 5:
        rules.append("换手下限可以从5%放宽到3%-4%，但低于3%活跃度不够。")
    else:
        rules.append("换手继续控制在5%以上，保证短线有交易热度。")
    if params["volume_ratio_max"] <= 2.5:
        rules.append("量比上限建议压在2.5以内，过热放量次日容易高开或回落。")
    else:
        rules.append("强势市场允许量比到3附近，但要降低仓位。")
    if params["market_value_min_yi"] >= 20:
        rules.append("过滤1-20亿过小市值，减少流动性和异动风险。")
    return {
        "title": f"当前更适合：{best['name']}",
        "text": (
            f"近{tested_days}个可验证交易日里，{best['name']} 的综合分最高；"
            f"次日收盘胜率 {best['win_rate']}%，平均次日收盘 {best['avg_next_close_pct']}%，"
            f"止损触及 {best['stop_hit_rate']}%。"
        ),
        "rules": rules,
        "best_strategy_id": best["id"],
    }


async def short_swing_backtest_payload(
    end_date: str,
    trade_days: int,
    per_day_limit: int,
) -> dict[str, Any]:
    key = ("short-swing-backtest", end_date, trade_days, per_day_limit, tuple(item["id"] for item in STRATEGIES))
    cached = market_data.cache_get(key)
    if cached is not None:
        return cached

    actual_end, signal_dates = await recent_factor_dates(end_date, trade_days)
    if not signal_dates:
        payload = {
            "requested_end_date": end_date,
            "end_date": actual_end,
            "signal_dates": [],
            "tested_days": 0,
            "results": [],
            "suggestion": {
                "title": "历史数据不足",
                "text": "没有取到足够的交易日，无法做历史推演。",
                "rules": ["换一个更晚的结束日", "或稍后再试"],
            },
            "fetched_at": datetime.now().isoformat(timespec="seconds"),
        }
        return market_data.cache_set(key, payload)

    events_by_strategy: dict[str, list[dict[str, Any]]] = {strategy["id"]: [] for strategy in STRATEGIES}
    tested_signal_dates: list[str] = []
    validated_until = actual_end

    for signal_date in signal_dates:
        rows = await market_data.stk_factor_rows(signal_date)
        next_date, next_rows = await market_data.next_trade_rows_raw(signal_date, market_data.HISTORY_FIELDS)
        if not rows or not next_date or not next_rows:
            continue
        next_map = {str(row.get("ts_code")): row for row in next_rows if row.get("ts_code")}
        validated_until = max(validated_until, next_date)
        strategy_candidates: dict[str, list[dict[str, Any]]] = {strategy["id"]: [] for strategy in STRATEGIES}
        tested_signal_dates.append(signal_date)

        for raw_row in rows:
            ts_code = str(raw_row.get("ts_code") or "")
            if not ts_code or ts_code not in next_map:
                continue
            for strategy in STRATEGIES:
                passed, condition_payload = factor_strategy_conditions(raw_row, strategy)
                if not passed:
                    continue
                signal = build_signal(raw_row, strategy, condition_payload)
                strategy_candidates[strategy["id"]].append(signal)

        for strategy in STRATEGIES:
            candidates = sorted(
                strategy_candidates[strategy["id"]],
                key=lambda item: item.get("recommend_score") or 0,
                reverse=True,
            )[:per_day_limit]
            for signal in candidates:
                ts_code = str(signal.get("ts_code") or "")
                validation = validate_next_day_signal(signal, next_map.get(ts_code, {}), next_date)
                if not validation:
                    continue
                events_by_strategy[strategy["id"]].append({**signal, "next_day": validation})

    tested_days = len(tested_signal_dates)
    results = [
        aggregate_backtest_events(strategy, events_by_strategy[strategy["id"]], tested_days)
        for strategy in STRATEGIES
    ]
    results.sort(key=lambda item: (item["quality_score"], item["signal_count"]), reverse=True)
    for result in results:
        if result["examples"]:
            result["examples"] = await market_data.attach_stock_basic(result["examples"])

    payload = {
        "requested_end_date": end_date,
        "end_date": actual_end,
        "validated_until": validated_until,
        "signal_dates": tested_signal_dates,
        "tested_days": tested_days,
        "per_day_limit": per_day_limit,
        "results": results,
        "suggestion": backtest_suggestion(results, tested_days),
        "cached_for_seconds": CACHE_TTL_SECONDS,
        "fetched_at": datetime.now().isoformat(timespec="seconds"),
    }
    return market_data.cache_set(key, payload)
