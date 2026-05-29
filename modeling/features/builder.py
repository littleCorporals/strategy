from __future__ import annotations

import math
from typing import Any


FEATURE_COLUMNS = [
    "pct_chg",
    "amplitude_pct",
    "close_position_pct",
    "momentum_3",
    "momentum_5",
    "volume_ratio_5",
    "amount_ratio_5",
]


def number(row: dict[str, Any], key: str) -> float | None:
    value = row.get(key)
    if isinstance(value, (int, float)):
        return float(value) if math.isfinite(float(value)) else None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None


def avg(values: list[float]) -> float | None:
    cleaned = [value for value in values if math.isfinite(value)]
    return sum(cleaned) / len(cleaned) if cleaned else None


def _ratio(current: float | None, baseline: float | None) -> float:
    if current is None or baseline in (None, 0):
        return 0.0
    return current / float(baseline)


def build_feature_row(history: list[dict[str, Any]]) -> dict[str, float]:
    row = history[-1] if history else {}
    close = number(row, "close")
    high = number(row, "high")
    low = number(row, "low")
    vol = number(row, "vol")
    amount = number(row, "amount")
    pct_chg = number(row, "pct_chg") or 0.0
    amplitude = ((high - low) / close * 100) if close and high is not None and low is not None else 0.0
    close_position = ((close - low) / (high - low) * 100) if close and high and low is not None and high != low else 50.0

    closes = [value for item in history if (value := number(item, "close")) is not None]
    vols = [value for item in history if (value := number(item, "vol")) is not None]
    amounts = [value for item in history if (value := number(item, "amount")) is not None]
    momentum_3 = ((close - closes[-4]) / closes[-4] * 100) if close and len(closes) >= 4 and closes[-4] else 0.0
    momentum_5 = ((close - closes[-6]) / closes[-6] * 100) if close and len(closes) >= 6 and closes[-6] else 0.0
    vol5 = avg(vols[-6:-1]) if len(vols) >= 6 else avg(vols[:-1])
    amount5 = avg(amounts[-6:-1]) if len(amounts) >= 6 else avg(amounts[:-1])

    return {
        "pct_chg": pct_chg,
        "amplitude_pct": amplitude,
        "close_position_pct": close_position,
        "momentum_3": momentum_3,
        "momentum_5": momentum_5,
        "volume_ratio_5": _ratio(vol, vol5),
        "amount_ratio_5": _ratio(amount, amount5),
    }
