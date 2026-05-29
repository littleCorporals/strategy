from __future__ import annotations

import math
from typing import Any


def number(row: dict[str, Any], key: str) -> float | None:
    value = row.get(key)
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def round_number(value: float | None, digits: int = 2) -> float | None:
    if value is None or not math.isfinite(value):
        return None
    return round(value, digits)


def avg(values: list[float]) -> float | None:
    cleaned = [value for value in values if math.isfinite(value)]
    if not cleaned:
        return None
    return sum(cleaned) / len(cleaned)


def last_number(rows: list[dict[str, Any]], key: str, span: int) -> float | None:
    if len(rows) < span:
        return None
    values = [number(row, key) for row in rows[-span:]]
    if any(value is None for value in values):
        return None
    return avg([float(value) for value in values if value is not None])


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    pct_values = [value for row in rows if (value := number(row, "pct_chg")) is not None]
    amount_values = [value for row in rows if (value := number(row, "amount")) is not None]
    total = len(rows)
    up = sum(1 for value in pct_values if value > 0)
    down = sum(1 for value in pct_values if value < 0)
    flat = sum(1 for value in pct_values if value == 0)
    up_ratio = round((up / total) * 100, 2) if total else 0

    if up_ratio >= 62 and down < up:
        temperature = "强势"
    elif up_ratio <= 38 and down > up:
        temperature = "弱势"
    else:
        temperature = "震荡"

    return {
        "total": total,
        "up": up,
        "down": down,
        "flat": flat,
        "up_ratio": up_ratio,
        "avg_pct_chg": round(sum(pct_values) / len(pct_values), 4) if pct_values else None,
        "max_pct_chg": max(pct_values) if pct_values else None,
        "min_pct_chg": min(pct_values) if pct_values else None,
        "amount_total": round(sum(amount_values), 4) if amount_values else None,
        "temperature": temperature,
    }


def support_resistance(rows: list[dict[str, Any]], close: float | None) -> dict[str, Any]:
    recent = rows[-20:] if rows else []
    lows = [value for row in recent if (value := number(row, "low")) is not None]
    highs = [value for row in recent if (value := number(row, "high")) is not None]
    support = min(lows) if lows else None
    resistance = max(highs) if highs else None
    return {
        "support": round_number(support),
        "resistance": round_number(resistance),
        "support_gap_pct": round_number(((close - support) / close) * 100, 2) if close and support else None,
        "resistance_gap_pct": round_number(((resistance - close) / close) * 100, 2)
        if close and resistance
        else None,
    }


def trend_analysis(rows: list[dict[str, Any]]) -> dict[str, Any]:
    close = number(rows[-1], "close") if rows else None
    ma5 = last_number(rows, "close", 5)
    ma10 = last_number(rows, "close", 10)
    ma20 = last_number(rows, "close", 20)
    vol5 = last_number(rows, "vol", 5)
    vol20 = last_number(rows, "vol", 20)
    pct5 = None
    pct20 = None
    if close is not None and len(rows) > 5 and (base := number(rows[-6], "close")):
        pct5 = ((close - base) / base) * 100
    if close is not None and len(rows) > 20 and (base := number(rows[-21], "close")):
        pct20 = ((close - base) / base) * 100

    score = 0
    reasons: list[str] = []
    if close is not None and ma5 is not None:
        if close >= ma5:
            score += 18
            reasons.append("收盘站上5日线")
        else:
            reasons.append("收盘低于5日线")
    if ma5 is not None and ma20 is not None:
        if ma5 >= ma20:
            score += 24
            reasons.append("短线均线在中线之上")
        else:
            reasons.append("短线均线弱于中线")
    if pct20 is not None:
        if pct20 > 8:
            score += 22
            reasons.append("20日涨幅偏强")
        elif pct20 > 0:
            score += 12
            reasons.append("20日仍为正收益")
        else:
            reasons.append("20日表现偏弱")
    if vol5 and vol20:
        if vol5 >= vol20 * 1.25:
            score += 18
            reasons.append("近5日量能放大")
        elif vol5 >= vol20 * 0.8:
            score += 10
            reasons.append("量能保持正常")
        else:
            reasons.append("量能不足")
    if rows:
        pct = number(rows[-1], "pct_chg") or 0
        if pct > 0:
            score += 8

    score = max(0, min(100, score))
    if score >= 75:
        level = "强趋势"
    elif score >= 55:
        level = "趋势尚可"
    elif score >= 35:
        level = "震荡"
    else:
        level = "偏弱"

    return {
        "score": score,
        "level": level,
        "ma5": round_number(ma5),
        "ma10": round_number(ma10),
        "ma20": round_number(ma20),
        "pct5": round_number(pct5),
        "pct20": round_number(pct20),
        "volume_ratio": round_number(vol5 / vol20, 2) if vol5 and vol20 else None,
        "reasons": reasons[:3],
    }


def money_analysis(row: dict[str, Any] | None, daily_row: dict[str, Any] | None = None) -> dict[str, Any]:
    if not row:
        return {
            "net": None,
            "big_net": None,
            "extra_large_net": None,
            "large_net": None,
            "medium_net": None,
            "small_net": None,
            "main_net": None,
            "main_ratio_pct": None,
            "strength": 0,
            "level": "暂无资金数据",
            "direction": "看不清",
            "detail": "资金流接口没有返回记录",
            "readable": "资金流接口没有返回记录，先不要凭感觉判断主力。",
        }
    net = number(row, "net_mf_amount")
    extra_large_net = (number(row, "buy_elg_amount") or 0) - (number(row, "sell_elg_amount") or 0)
    large_net = (number(row, "buy_lg_amount") or 0) - (number(row, "sell_lg_amount") or 0)
    medium_net = (number(row, "buy_md_amount") or 0) - (number(row, "sell_md_amount") or 0)
    small_net = (number(row, "buy_sm_amount") or 0) - (number(row, "sell_sm_amount") or 0)
    big_net = extra_large_net + large_net
    amount = number(daily_row or {}, "amount")
    amount_wan = amount * 0.1 if amount is not None else None
    main_ratio_pct = (big_net / amount_wan * 100) if amount_wan and amount_wan > 0 else None
    strength = 0
    if main_ratio_pct is not None:
        strength = int(min(100, max(0, abs(main_ratio_pct) * 8)))
    elif big_net:
        strength = 45

    if net is None:
        level = "资金不明"
        direction = "看不清"
    elif big_net > 0 and net > 0:
        level = "主力流入"
        direction = "偏流入"
    elif big_net > 0 and net <= 0:
        level = "主力吸筹"
        direction = "主力流入但盘面分歧"
    elif big_net < 0 and net < 0:
        level = "主力流出"
        direction = "偏流出"
    elif big_net < 0:
        level = "主力减仓"
        direction = "主力流出但总资金分歧"
    else:
        level = "资金分歧"
        direction = "分歧"

    if big_net > 0:
        readable = "大单和超大单合计净流入，说明主动买盘更占优。"
    elif big_net < 0:
        readable = "大单和超大单合计净流出，说明主力资金偏谨慎。"
    else:
        readable = "大单和超大单没有明显方向，资金信号不强。"
    return {
        "net": round_number(net),
        "big_net": round_number(big_net),
        "extra_large_net": round_number(extra_large_net),
        "large_net": round_number(large_net),
        "medium_net": round_number(medium_net),
        "small_net": round_number(small_net),
        "main_net": round_number(big_net),
        "main_ratio_pct": round_number(main_ratio_pct, 2),
        "strength": strength,
        "level": level,
        "direction": direction,
        "detail": f"主力净额 {round_number(big_net) if big_net else 0}",
        "readable": readable,
    }


def next_day_forecast(
    row: dict[str, Any] | None,
    trend: dict[str, Any],
    money: dict[str, Any],
    valuation: dict[str, Any],
    sr: dict[str, Any],
    risk: dict[str, Any],
) -> dict[str, Any]:
    if not row:
        return {
            "title": "等待个股数据",
            "direction": "不推演",
            "confidence": 0,
            "summary": "没有拿到日线数据，不能做次日推演。",
            "entry_zone": "--",
            "stop_price": "--",
            "target_zone": "--",
            "position": "--",
            "buy_signal": "先等待数据完整。",
            "avoid_signal": "数据缺失时不交易。",
            "evidence": [],
        }

    close = number(row, "close") or 0
    open_ = number(row, "open") or close
    high = number(row, "high") or close
    low = number(row, "low") or close
    pct = number(row, "pct_chg") or 0
    trend_score = int(trend.get("score") or 0)
    risk_score = int(risk.get("score") or 100)
    main_net = number(money, "main_net")
    main_ratio = number(money, "main_ratio_pct")
    volume_ratio = number(trend, "volume_ratio")
    support = number(sr, "support")
    resistance = number(sr, "resistance")
    turnover = number(valuation, "turnover")

    score = trend_score
    evidence: list[str] = []
    if main_net is not None:
        if main_net > 0:
            score += 12
            evidence.append("主力资金净流入")
        elif main_net < 0:
            score -= 16
            evidence.append("主力资金净流出")
    if pct > 0 and close >= open_:
        score += 8
        evidence.append("收盘强于开盘")
    if high > low:
        intraday_position = ((close - low) / (high - low)) * 100
        if intraday_position >= 65:
            score += 8
            evidence.append("收盘位置偏强")
        elif intraday_position <= 35:
            score -= 8
            evidence.append("收盘位置偏弱")
    if volume_ratio is not None:
        if 0.9 <= volume_ratio <= 2.2:
            score += 6
            evidence.append("量能健康")
        elif volume_ratio > 2.8:
            score -= 8
            evidence.append("放量过热")
    if turnover is not None and turnover > 15:
        score -= 8
        evidence.append("换手偏热")
    score -= max(0, risk_score - 45) * 0.35
    score = int(max(0, min(100, round(score))))

    if score >= 72 and risk_score < 62:
        title = "明日偏强"
        direction = "回踩承接后更值得看"
        summary = "趋势和资金同时支持，明天重点看低开或小回踩后是否有人接。"
        position = "1 到 3 成"
    elif score >= 52:
        title = "明日震荡观察"
        direction = "等确认，不追"
        summary = "信号不差但优势不够大，明天只看计划价附近的确认。"
        position = "0 到 2 成"
    else:
        title = "明日谨慎"
        direction = "先回避"
        summary = "趋势、资金或风险项不够友好，明天不适合主动追买。"
        position = "0 到 1 成"

    entry_low = close * 0.985
    entry_high = close * 1.01
    if pct >= 6:
        entry_low = close * 0.96
        entry_high = close * 0.995
    elif main_net is not None and main_net < 0:
        entry_low = close * 0.97
        entry_high = close * 0.99

    stop_base = support if support and support < close else max(low, close * 0.955)
    target_base = resistance if resistance and resistance > close else close * 1.055
    if target_base <= close:
        target_base = close * 1.045

    buy_signal = f"只看 {round(entry_low, 2)} 到 {round(entry_high, 2)} 附近承接，放量站稳再考虑。"
    avoid_signal = f"跌破 {round(stop_base, 2)} 或高开超过 3% 后快速回落，就放弃。"
    if main_ratio is not None:
        evidence.append(f"主力净额占成交约 {round(main_ratio, 2)}%")

    return {
        "title": title,
        "direction": direction,
        "confidence": score,
        "summary": summary,
        "entry_zone": f"{round(entry_low, 2)} 到 {round(entry_high, 2)}",
        "stop_price": f"{round(stop_base, 2)}",
        "target_zone": f"{round(target_base, 2)} 附近",
        "position": position,
        "buy_signal": buy_signal,
        "avoid_signal": avoid_signal,
        "evidence": evidence[:5],
    }


def valuation_analysis(row: dict[str, Any] | None) -> dict[str, Any]:
    if not row:
        return {"level": "暂无估值", "pe": None, "pb": None, "turnover": None, "volume_ratio": None}
    pe = number(row, "pe")
    pb = number(row, "pb")
    turnover = number(row, "turnover_rate")
    volume_ratio = number(row, "volume_ratio")
    risk = 0
    notes: list[str] = []
    if pe is not None:
        if pe > 120 or pe < 0:
            risk += 28
            notes.append("市盈率异常偏高或为负")
        elif pe > 60:
            risk += 16
            notes.append("市盈率偏高")
    if pb is not None and pb > 8:
        risk += 16
        notes.append("市净率偏高")
    if turnover is not None and turnover > 18:
        risk += 18
        notes.append("换手过热")
    if volume_ratio is not None and volume_ratio > 2.5:
        risk += 14
        notes.append("量比偏高")
    level = "风险较高" if risk >= 40 else "估值偏热" if risk >= 22 else "估值正常"
    return {
        "level": level,
        "risk": risk,
        "pe": round_number(pe),
        "pb": round_number(pb),
        "turnover": round_number(turnover),
        "volume_ratio": round_number(volume_ratio),
        "notes": notes[:3],
    }


def risk_summary(
    trend: dict[str, Any],
    money: dict[str, Any],
    valuation: dict[str, Any],
    sr: dict[str, Any],
) -> dict[str, Any]:
    risk = 100 - int(trend.get("score") or 0)
    if money.get("net") is not None and money.get("net") < 0:
        risk += 12
    risk += int(valuation.get("risk") or 0)
    if sr.get("support_gap_pct") is not None and sr["support_gap_pct"] > 12:
        risk += 10
    risk = max(0, min(100, risk))
    if risk >= 70:
        level = "高风险"
        action = "只观察，不追高"
    elif risk >= 45:
        level = "中风险"
        action = "等回踩确认"
    else:
        level = "风险可控"
        action = "按计划小仓试错"
    return {"score": risk, "level": level, "action": action}
