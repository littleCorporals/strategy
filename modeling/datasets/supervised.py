from __future__ import annotations

from typing import Any

from modeling.features.builder import FEATURE_COLUMNS, build_feature_row, number
from modeling.labels.builder import build_label, label_horizon


def _pct_change(base: float | None, value: float | None) -> float | None:
    if not base or value is None:
        return None
    return (value - base) / base * 100


def build_supervised_samples(
    rows: list[dict[str, Any]],
    *,
    label_set: str,
    min_history: int = 6,
) -> list[dict[str, Any]]:
    horizon = label_horizon(label_set)
    by_code: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        ts_code = str(row.get("ts_code") or "")
        trade_date = str(row.get("trade_date") or "")
        if ts_code and trade_date:
            by_code.setdefault(ts_code, []).append(row)

    samples: list[dict[str, Any]] = []
    for ts_code, items in by_code.items():
        items.sort(key=lambda item: str(item.get("trade_date") or ""))
        for index in range(min_history - 1, len(items) - horizon):
            history = items[: index + 1]
            row = items[index]
            future_rows = items[index + 1 : index + 1 + horizon]
            next_row = future_rows[0]
            features = build_feature_row(history)
            close = number(row, "close")
            next_close_pct = _pct_change(close, number(next_row, "close"))
            next_high_pct = _pct_change(close, number(next_row, "high"))
            window_highs = [value for item in future_rows if (value := number(item, "high")) is not None]
            window_high_pct = _pct_change(close, max(window_highs) if window_highs else None)
            samples.append(
                {
                    "ts_code": ts_code,
                    "trade_date": str(row.get("trade_date") or ""),
                    "next_trade_date": str(next_row.get("trade_date") or ""),
                    "label_end_trade_date": str(future_rows[-1].get("trade_date") or ""),
                    "features": {name: float(features.get(name, 0.0)) for name in FEATURE_COLUMNS},
                    "label": build_label(row, next_row, label_set, future_rows=future_rows),
                    "next_close_pct": round(next_close_pct, 4) if next_close_pct is not None else None,
                    "next_high_pct": round(next_high_pct, 4) if next_high_pct is not None else None,
                    "window_high_pct": round(window_high_pct, 4) if window_high_pct is not None else None,
                }
            )
    samples.sort(key=lambda item: (str(item.get("trade_date") or ""), str(item.get("ts_code") or "")))
    return samples
