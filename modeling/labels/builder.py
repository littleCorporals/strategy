from __future__ import annotations

from typing import Any

from modeling.features.builder import number


def label_horizon(label_set: str) -> int:
    return 3 if label_set == "next_3d_high_3pct_v1" else 1


def _high_hit(row: dict[str, Any], future_rows: list[dict[str, Any]], threshold: float) -> int:
    close = number(row, "close")
    if not close:
        return 0
    future_highs = [value for item in future_rows if (value := number(item, "high")) is not None]
    return int(bool(future_highs) and ((max(future_highs) - close) / close) >= threshold)


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
    return _high_hit(row, future[:1], 0.03)
