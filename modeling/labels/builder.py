from __future__ import annotations

from typing import Any

from modeling.features.builder import number


EPSILON = 1e-9


def label_horizon(label_set: str) -> int:
    return 3 if label_set == "next_3d_high_3pct_v1" else 1


def _high_hit(row: dict[str, Any], future_rows: list[dict[str, Any]], threshold: float) -> int:
    close = number(row, "close")
    if not close:
        return 0
    future_highs = [value for item in future_rows if (value := number(item, "high")) is not None]
    return int(bool(future_highs) and ((max(future_highs) - close) / close) >= threshold - EPSILON)


def _next_low_drawdown_pct(row: dict[str, Any], next_row: dict[str, Any]) -> float | None:
    close = number(row, "close")
    next_low = number(next_row, "low")
    if not close or next_low is None:
        return None
    return (next_low - close) / close


def _next_low_drawdown_hit(row: dict[str, Any], next_row: dict[str, Any], threshold: float) -> int:
    drawdown_pct = _next_low_drawdown_pct(row, next_row)
    return int(drawdown_pct is not None and drawdown_pct < -threshold - EPSILON)


def _next_low_drawdown_within(row: dict[str, Any], next_row: dict[str, Any], threshold: float) -> int:
    drawdown_pct = _next_low_drawdown_pct(row, next_row)
    return int(drawdown_pct is not None and drawdown_pct >= -threshold - EPSILON)


def _next_open_gap_down_hit(row: dict[str, Any], next_row: dict[str, Any], threshold: float) -> int:
    close = number(row, "close")
    next_open = number(next_row, "open")
    if not close or next_open is None:
        return 0
    return int(((next_open - close) / close) < -threshold - EPSILON)


def build_label(
    row: dict[str, Any],
    next_row: dict[str, Any],
    label_set: str,
    *,
    future_rows: list[dict[str, Any]] | None = None,
) -> int:
    future = future_rows or [next_row]
    if label_set == "next_close_positive_v1":
        close = number(row, "close")
        if not close:
            return 0
        next_close = number(next_row, "close")
        return int(next_close is not None and next_close > close)
    if label_set == "next_high_2pct_v1":
        return _high_hit(row, future[:1], 0.02)
    if label_set == "next_3d_high_3pct_v1":
        return _high_hit(row, future[:3], 0.03)
    if label_set == "next_high_3pct_no_deep_drawdown_v1":
        return int(_high_hit(row, future[:1], 0.03) and _next_low_drawdown_within(row, next_row, 0.03))
    if label_set == "next_low_drawdown_3pct_v1":
        return _next_low_drawdown_hit(row, next_row, 0.03)
    if label_set == "next_open_gap_down_2pct_v1":
        return _next_open_gap_down_hit(row, next_row, 0.02)
    return _high_hit(row, future[:1], 0.03)
