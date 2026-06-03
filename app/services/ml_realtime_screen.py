from __future__ import annotations

import math
from datetime import datetime
from typing import Any

from app.db import model_repo
from app.services import analysis, market_data, realtime_quote


MIN_REALTIME_PCT = -1.0
MAX_REALTIME_PCT = 4.2
MAX_AMPLITUDE_PCT = 12.0
MIN_INTRADAY_POSITION = 35.0
MAX_INTRADAY_POSITION = 88.0
MIN_AMOUNT_YI = 1.5
QUOTE_CHUNK_SIZE = 80


def _number(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _round(value: float | None, digits: int = 2) -> float | None:
    return analysis.round_number(value, digits) if value is not None else None


def _plain_stock_code(ts_code: str) -> str:
    return str(ts_code or "").split(".", 1)[0]


def _baidu_url(ts_code: str) -> str:
    return f"https://gushitong.baidu.com/stock/ab-{_plain_stock_code(ts_code)}"


def _risk_name(name: str | None) -> bool:
    normalized = str(name or "").strip().upper()
    if not normalized:
        return False
    if "ST" in normalized or "退" in normalized:
        return True
    return normalized.endswith("-U") or normalized.endswith("-W") or normalized.endswith(" U") or normalized.endswith(" W")


def _quote_metrics(quote: dict[str, Any]) -> dict[str, Any]:
    price = _number(quote.get("price"))
    high = _number(quote.get("high"))
    low = _number(quote.get("low"))
    pre_close = _number(quote.get("pre_close")) or price
    amount_yi = _number(quote.get("amount_yi"))
    if amount_yi is None:
        amount_yuan = _number(quote.get("amount_yuan"))
        amount_yi = amount_yuan / 100_000_000 if amount_yuan is not None else None

    amplitude = None
    if high is not None and low is not None and pre_close and pre_close > 0:
        amplitude = ((high - low) / pre_close) * 100

    position = None
    if price is not None and high is not None and low is not None and high > low:
        position = ((price - low) / (high - low)) * 100

    return {
        "price": price,
        "pct_chg": _number(quote.get("pct_chg")),
        "high": high,
        "low": low,
        "pre_close": pre_close,
        "amount_yi": amount_yi,
        "amplitude_pct": amplitude,
        "intraday_position": position,
    }


def _rejection_reasons(ts_code: str, name: str, quote: dict[str, Any], metrics: dict[str, Any]) -> list[str]:
    reasons: list[str] = []
    pct = _number(metrics.get("pct_chg"))
    amount_yi = _number(metrics.get("amount_yi"))
    amplitude = _number(metrics.get("amplitude_pct"))
    position = _number(metrics.get("intraday_position"))

    if not quote.get("available"):
        reasons.append("实时行情不可用")
    if ts_code.endswith(".BJ") or _plain_stock_code(ts_code).startswith(("8", "9")):
        reasons.append("北交所暂不纳入")
    if _risk_name(name):
        reasons.append("ST/退市/U/W 风险")
    if pct is None or pct < MIN_REALTIME_PCT:
        reasons.append("实时跌幅<-1%")
    if pct is not None and pct > MAX_REALTIME_PCT:
        reasons.append("涨幅>4.2%过热")
    if amplitude is None or amplitude > MAX_AMPLITUDE_PCT:
        reasons.append("日内振幅>12%")
    if position is None or position < MIN_INTRADAY_POSITION:
        reasons.append("日内位置<35%")
    if position is not None and pct is not None and position > MAX_INTRADAY_POSITION and pct > 2:
        reasons.append("高位且涨幅>2%")
    if amount_yi is None or amount_yi < MIN_AMOUNT_YI:
        reasons.append("成交额<1.5亿")
    return reasons


def _entry_plan(price: float | None, low: float | None) -> dict[str, Any]:
    if price is None:
        return {"entry_low": None, "entry_high": None, "stop_price": None, "target_price": None}
    return {
        "entry_low": round(price * 0.985, 2),
        "entry_high": round(price * 1.008, 2),
        "stop_price": round(max(low or 0, price * 0.965), 2),
        "target_price": round(price * 1.045, 2),
    }


def _rank_score(prediction: dict[str, Any], metrics: dict[str, Any]) -> float:
    probability = _number(prediction.get("probability")) or 0
    pct = _number(metrics.get("pct_chg")) or 0
    amount_yi = _number(metrics.get("amount_yi")) or 0
    position = _number(metrics.get("intraday_position")) or 65

    pct_score = 1 - abs(pct - 1.2) / 5
    position_score = 1 - abs(position - 68) / 68
    amount_score = min(math.log10(max(amount_yi, 0.01)) / 1.5, 1.5)
    chasing_penalty = max(0.0, pct - 3.2) * 3
    return round(
        probability * 100
        + max(0.0, pct_score) * 12
        + max(0.0, position_score) * 10
        + amount_score * 8
        - chasing_penalty,
        2,
    )


def _screen_metrics(metrics: dict[str, Any]) -> dict[str, Any]:
    return {
        "realtime_pct": _round(_number(metrics.get("pct_chg")), 2),
        "amount_yi": _round(_number(metrics.get("amount_yi")), 2),
        "amplitude_pct": _round(_number(metrics.get("amplitude_pct")), 2),
        "intraday_position": _round(_number(metrics.get("intraday_position")), 1),
    }


def _topn(payload: dict[str, Any], size: str = "50") -> dict[str, Any]:
    return (((payload.get("ranking") or {}).get("validation") or {}).get("top_n") or {}).get(size) or {}


def _latest_topn(payload: dict[str, Any] | None, size: str = "50") -> dict[str, Any]:
    if not payload:
        return {}
    return ((payload.get("ranking") or {}).get("top_n") or {}).get(size) or {}


def _fit_summary(metrics: dict[str, Any]) -> dict[str, Any]:
    train = metrics.get("train") or {}
    validation = metrics.get("validation") or {}
    train_log_loss = _number(train.get("log_loss"))
    validation_log_loss = _number(validation.get("log_loss"))
    train_f1 = _number(train.get("f1"))
    validation_f1 = _number(validation.get("f1") or metrics.get("f1"))
    log_loss_gap = (
        round(validation_log_loss - train_log_loss, 6)
        if train_log_loss is not None and validation_log_loss is not None
        else None
    )
    f1_gap = round(train_f1 - validation_f1, 4) if train_f1 is not None and validation_f1 is not None else None
    if log_loss_gap is None:
        level = "unknown"
        note = "缺少训练/验证 Log Loss，无法判断拟合差距。"
    elif log_loss_gap <= 0.03:
        level = "stable"
        note = "训练和验证损失接近，暂未看到明显过拟合。"
    elif log_loss_gap <= 0.1:
        level = "watch"
        note = "验证损失高于训练损失，存在一定泛化折损。"
    else:
        level = "overfit_risk"
        note = "验证损失明显高于训练损失，过拟合风险偏高。"
    return {
        "level": level,
        "note": note,
        "train_log_loss": train_log_loss,
        "validation_log_loss": validation_log_loss,
        "log_loss_gap": log_loss_gap,
        "train_f1": train_f1,
        "validation_f1": validation_f1,
        "f1_gap": f1_gap,
    }


def _model_reference(model: dict[str, Any], latest_validation: dict[str, Any] | None) -> dict[str, Any]:
    metrics = model.get("metrics") or {}
    validation = metrics.get("validation") or {}
    ranking_validation = ((metrics.get("ranking") or {}).get("validation") or {})
    latest_top50 = _latest_topn(latest_validation, "50")
    return {
        "model_id": model.get("model_id"),
        "name": model.get("name"),
        "model_type": model.get("model_type"),
        "feature_set": model.get("feature_set"),
        "label_set": model.get("label_set"),
        "activated_at": model.get("activated_at"),
        "sample_count": metrics.get("sample_count"),
        "train_sample_count": metrics.get("train_sample_count"),
        "validation_sample_count": metrics.get("validation_sample_count"),
        "validation": {
            "accuracy": validation.get("accuracy") or metrics.get("accuracy"),
            "precision": validation.get("precision") or metrics.get("precision"),
            "recall": validation.get("recall") or metrics.get("recall"),
            "f1": validation.get("f1") or metrics.get("f1"),
            "log_loss": validation.get("log_loss"),
            "positive_rate": validation.get("positive_rate"),
        },
        "fit": _fit_summary(metrics),
        "ranking_validation": {
            "market_hit_rate": ranking_validation.get("market_hit_rate"),
            "top20": _topn(metrics, "20"),
            "top50": _topn(metrics, "50"),
            "top100": _topn(metrics, "100"),
        },
        "latest_prediction_validation": {
            "trade_date": latest_validation.get("trade_date") if latest_validation else None,
            "next_trade_date": latest_validation.get("next_trade_date") if latest_validation else None,
            "count": latest_validation.get("count") if latest_validation else None,
            "hit_rate": latest_validation.get("hit_rate") if latest_validation else None,
            "market_hit_rate": ((latest_validation or {}).get("ranking") or {}).get("market_hit_rate"),
            "top20": _latest_topn(latest_validation, "20"),
            "top50": latest_top50,
            "top100": _latest_topn(latest_validation, "100"),
        },
        "objective_note": "当前标签优化的是下一交易日最高价触及 3%，不是收盘盈利，也不是直接买入信号。",
    }


async def _quotes_for(ts_codes: list[str]) -> dict[str, dict[str, Any]]:
    quotes: dict[str, dict[str, Any]] = {}
    for index in range(0, len(ts_codes), QUOTE_CHUNK_SIZE):
        chunk = ts_codes[index : index + QUOTE_CHUNK_SIZE]
        quotes.update(await realtime_quote.sina_quotes(chunk))
    return quotes


async def ml_late_session_screen(
    trade_date: str,
    *,
    limit: int = 20,
    prediction_limit: int = 500,
) -> dict[str, Any]:
    model = await model_repo.active_model()
    if not model:
        return {
            "requested_trade_date": trade_date,
            "trade_date": trade_date,
            "model": None,
            "rows": [],
            "raw_top": [],
            "rejected_counts": {"无激活模型": 1},
            "prediction_count": 0,
            "quote_count": 0,
            "fallback_used": False,
        }

    model_id = str(model["model_id"])
    latest_validation = await model_repo.latest_validation_payload(model_id)
    actual_trade_date = trade_date
    predictions = await model_repo.list_predictions(model_id, actual_trade_date)
    fallback_used = False
    if not predictions:
        latest = await model_repo.latest_prediction_trade_date(model_id)
        if latest:
            actual_trade_date = latest
            fallback_used = actual_trade_date != trade_date
            predictions = await model_repo.list_predictions(model_id, actual_trade_date)

    predictions = predictions[: max(limit, prediction_limit)]
    ts_codes = [str(row.get("ts_code")) for row in predictions if row.get("ts_code")]
    quotes = await _quotes_for(ts_codes)

    daily_rows = await market_data.daily_rows(actual_trade_date, market_data.DAILY_FIELDS)
    basic_map = await market_data.stock_basic_map(allow_online=False)
    daily_by_code = {str(row.get("ts_code")): row for row in daily_rows if row.get("ts_code")}

    accepted: list[dict[str, Any]] = []
    raw_top: list[dict[str, Any]] = []
    rejected_counts: dict[str, int] = {}

    for rank, prediction in enumerate(predictions, start=1):
        ts_code = str(prediction.get("ts_code") or "")
        quote = quotes.get(ts_code, {})
        daily = daily_by_code.get(ts_code, {})
        basic = basic_map.get(ts_code, {})
        name = str(quote.get("name") or daily.get("name") or basic.get("name") or ts_code)
        industry = daily.get("industry") or basic.get("industry")
        area = daily.get("area") or basic.get("area")
        metrics = _quote_metrics(quote)
        plan = _entry_plan(_number(metrics.get("price")), _number(metrics.get("low")))

        base_row = {
            "ts_code": ts_code,
            "trade_date": actual_trade_date,
            "name": name,
            "industry": industry,
            "area": area,
            "ml_rank": rank,
            "probability": _round(_number(prediction.get("probability")), 4),
            "ml_score": _round(_number(prediction.get("ml_score")), 4),
            "recommend_type": "模型尾盘",
            "recommend_reason": "模型分进入 Top500，并通过实时风险闸门。",
            "strategy_name": "ML+实时风险闸门",
            "screen_conditions": {},
            "screen_metrics": _screen_metrics(metrics),
            "baidu_url": _baidu_url(ts_code),
            **plan,
        }

        display_quote = {
            **quote,
            "amount_yi": _round(_number(metrics.get("amount_yi")), 2),
            "amplitude_pct": _round(_number(metrics.get("amplitude_pct")), 2),
            "intraday_position": _round(_number(metrics.get("intraday_position")), 1),
        }
        raw_item = {
            **base_row,
            "late_session": {
                "action": "原始模型排序",
                "level": "raw",
                "reason": "未经过实时风险闸门，仅用于对比。",
                "quote": display_quote,
                "rank_score": _rank_score(prediction, metrics),
                "t_plus_1_note": "A股 T+1：今天买入最快下个交易日才能卖，尾盘候选必须避免追高。",
            },
        }
        if len(raw_top) < 20:
            raw_top.append(raw_item)

        reasons = _rejection_reasons(ts_code, name, quote, metrics)
        if reasons:
            first_reason = reasons[0]
            rejected_counts[first_reason] = rejected_counts.get(first_reason, 0) + 1
            continue

        rank_score = _rank_score(prediction, metrics)
        accepted.append(
            {
                **base_row,
                "recommend_score": rank_score,
                "late_session": {
                    "action": "可继续观察",
                    "level": "ml_realtime_pass",
                    "reason": "实时涨跌、成交额、日内位置和 T+1 追高风险均通过过滤。",
                    "quote": display_quote,
                    "rank_score": rank_score,
                    "model_rank": rank,
                    "t_plus_1_note": "A股 T+1：今天买入最快下个交易日才能卖，尾盘候选必须避免追高。",
                },
            }
        )

    accepted.sort(key=lambda row: row["late_session"]["rank_score"], reverse=True)
    return {
        "requested_trade_date": trade_date,
        "trade_date": actual_trade_date,
        "model": {
            "model_id": model.get("model_id"),
            "name": model.get("name"),
            "model_type": model.get("model_type"),
            "feature_set": model.get("feature_set"),
            "label_set": model.get("label_set"),
            "activated_at": model.get("activated_at"),
        },
        "model_reference": _model_reference(model, latest_validation),
        "rows": accepted[:limit],
        "raw_top": raw_top,
        "rejected_counts": rejected_counts,
        "prediction_count": len(predictions),
        "quote_count": sum(1 for quote in quotes.values() if quote.get("available")),
        "accepted_count": len(accepted),
        "fallback_used": fallback_used,
        "fetched_at": datetime.now().isoformat(timespec="seconds"),
    }
