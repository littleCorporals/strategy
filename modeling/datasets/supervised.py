from __future__ import annotations

from typing import Any

from modeling.features.builder import FEATURE_COLUMNS, build_feature_row
from modeling.labels.builder import build_label


def build_supervised_samples(
    rows: list[dict[str, Any]],
    *,
    label_set: str,
    min_history: int = 6,
) -> list[dict[str, Any]]:
    by_code: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        ts_code = str(row.get("ts_code") or "")
        trade_date = str(row.get("trade_date") or "")
        if ts_code and trade_date:
            by_code.setdefault(ts_code, []).append(row)

    samples: list[dict[str, Any]] = []
    for ts_code, items in by_code.items():
        items.sort(key=lambda item: str(item.get("trade_date") or ""))
        for index in range(min_history - 1, len(items) - 1):
            history = items[: index + 1]
            row = items[index]
            next_row = items[index + 1]
            features = build_feature_row(history)
            samples.append(
                {
                    "ts_code": ts_code,
                    "trade_date": str(row.get("trade_date") or ""),
                    "next_trade_date": str(next_row.get("trade_date") or ""),
                    "features": {name: float(features.get(name, 0.0)) for name in FEATURE_COLUMNS},
                    "label": build_label(row, next_row, label_set),
                }
            )
    samples.sort(key=lambda item: (str(item.get("trade_date") or ""), str(item.get("ts_code") or "")))
    return samples
