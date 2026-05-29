from __future__ import annotations

from typing import Any

from modeling.features.builder import number


def build_label(row: dict[str, Any], next_row: dict[str, Any], label_set: str) -> int:
    close = number(row, "close")
    if not close:
        return 0
    if label_set == "next_close_positive_v1":
        next_close = number(next_row, "close")
        return int(next_close is not None and next_close > close)
    next_high = number(next_row, "high")
    return int(next_high is not None and ((next_high - close) / close) >= 0.03)
