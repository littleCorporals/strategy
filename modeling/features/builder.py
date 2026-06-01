from __future__ import annotations

import math
from typing import Any


V1_FEATURE_COLUMNS = [
    "pct_chg",
    "amplitude_pct",
    "close_position_pct",
    "momentum_3",
    "momentum_5",
    "volume_ratio_5",
    "amount_ratio_5",
]

V2_EXTRA_COLUMNS = [
    "momentum_10",
    "momentum_20",
    "ma_gap_5",
    "ma_gap_10",
    "ma_gap_20",
    "volatility_5",
    "volatility_10",
    "volume_ratio_10",
    "volume_ratio_20",
    "amount_ratio_10",
    "amount_ratio_20",
    "volume_acceleration_5_10",
    "amount_acceleration_5_10",
    "close_to_high_20",
    "close_to_low_20",
    "high_breakout_20",
    "low_breakdown_20",
    "body_pct",
    "upper_shadow_pct",
    "lower_shadow_pct",
    "gap_pct",
    "up_days_5",
    "down_days_5",
]

V2_FEATURE_COLUMNS = [*V1_FEATURE_COLUMNS, *V2_EXTRA_COLUMNS]

# Backward-compatible default for older call sites and artifacts.
FEATURE_COLUMNS = V1_FEATURE_COLUMNS


def feature_columns(feature_set: str = "short_swing_v1") -> list[str]:
    if feature_set == "short_swing_v2":
        return V2_FEATURE_COLUMNS
    return V1_FEATURE_COLUMNS


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


def _pct_change(current: float | None, previous: float | None) -> float:
    if current is None or previous in (None, 0):
        return 0.0
    return (current - float(previous)) / float(previous) * 100


def _rolling_mean(values: list[float], window: int) -> float | None:
    return avg(values[-window:]) if len(values) >= window else avg(values)


def _rolling_std_pct(values: list[float], window: int) -> float:
    picked = values[-window:] if len(values) >= window else values
    if len(picked) < 2:
        return 0.0
    mean = avg(picked) or 0.0
    if not mean:
        return 0.0
    variance = sum((value - mean) ** 2 for value in picked) / len(picked)
    return math.sqrt(variance) / abs(mean) * 100


def _ma_gap(close: float | None, closes: list[float], window: int) -> float:
    ma = _rolling_mean(closes, window)
    return _pct_change(close, ma)


def build_feature_row(history: list[dict[str, Any]], *, feature_set: str = "short_swing_v1") -> dict[str, float]:
    row = history[-1] if history else {}
    previous_row = history[-2] if len(history) >= 2 else {}
    open_price = number(row, "open")
    close = number(row, "close")
    high = number(row, "high")
    low = number(row, "low")
    previous_close = number(previous_row, "close")
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

    features = {
        "pct_chg": pct_chg,
        "amplitude_pct": amplitude,
        "close_position_pct": close_position,
        "momentum_3": momentum_3,
        "momentum_5": momentum_5,
        "volume_ratio_5": _ratio(vol, vol5),
        "amount_ratio_5": _ratio(amount, amount5),
    }
    if feature_set == "short_swing_v2":
        recent = history[-5:]
        up_days_5 = sum(1 for item in recent if (number(item, "pct_chg") or 0.0) > 0)
        down_days_5 = sum(1 for item in recent if (number(item, "pct_chg") or 0.0) < 0)
        high20 = max([value for item in history[-20:] if (value := number(item, "high")) is not None], default=None)
        low20 = min([value for item in history[-20:] if (value := number(item, "low")) is not None], default=None)
        vol10 = avg(vols[-11:-1]) if len(vols) >= 11 else avg(vols[:-1])
        vol20 = avg(vols[-21:-1]) if len(vols) >= 21 else avg(vols[:-1])
        amount10 = avg(amounts[-11:-1]) if len(amounts) >= 11 else avg(amounts[:-1])
        amount20 = avg(amounts[-21:-1]) if len(amounts) >= 21 else avg(amounts[:-1])
        body_pct = ((close - open_price) / close * 100) if close and open_price is not None else 0.0
        upper_shadow = ((high - max(open_price, close)) / close * 100) if close and high is not None and open_price is not None else 0.0
        lower_shadow = ((min(open_price, close) - low) / close * 100) if close and low is not None and open_price is not None else 0.0
        features.update(
            {
                "momentum_10": _pct_change(close, closes[-11] if len(closes) >= 11 else None),
                "momentum_20": _pct_change(close, closes[-21] if len(closes) >= 21 else None),
                "ma_gap_5": _ma_gap(close, closes, 5),
                "ma_gap_10": _ma_gap(close, closes, 10),
                "ma_gap_20": _ma_gap(close, closes, 20),
                "volatility_5": _rolling_std_pct(closes, 5),
                "volatility_10": _rolling_std_pct(closes, 10),
                "volume_ratio_10": _ratio(vol, vol10),
                "volume_ratio_20": _ratio(vol, vol20),
                "amount_ratio_10": _ratio(amount, amount10),
                "amount_ratio_20": _ratio(amount, amount20),
                "volume_acceleration_5_10": _ratio(features["volume_ratio_5"], _ratio(vol, vol10)),
                "amount_acceleration_5_10": _ratio(features["amount_ratio_5"], _ratio(amount, amount10)),
                "close_to_high_20": _pct_change(close, high20),
                "close_to_low_20": _pct_change(close, low20),
                "high_breakout_20": _pct_change(high, high20),
                "low_breakdown_20": _pct_change(low, low20),
                "body_pct": body_pct,
                "upper_shadow_pct": upper_shadow,
                "lower_shadow_pct": lower_shadow,
                "gap_pct": _pct_change(open_price, previous_close),
                "up_days_5": float(up_days_5),
                "down_days_5": float(down_days_5),
            }
        )
    return {name: float(features.get(name, 0.0)) for name in feature_columns(feature_set)}
