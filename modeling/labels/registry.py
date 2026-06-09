from __future__ import annotations


LABEL_SETS = {
    "next_high_3pct_v1": {
        "name": "次日最高涨幅 3% v1",
        "description": "若次一交易日最高价相对信号日收盘价达到 3%，标记为 1。",
        "status": "planned",
    },
    "next_high_2pct_v1": {
        "name": "次日最高涨幅 2% v1",
        "description": "若次一交易日最高价相对信号日收盘价达到 2%，标记为 1。",
        "status": "planned",
    },
    "next_3d_high_3pct_v1": {
        "name": "未来 3 日最高涨幅 3% v1",
        "description": "若未来三个交易日内最高价相对信号日收盘价达到 3%，标记为 1。",
        "status": "planned",
    },
    "next_high_3pct_no_deep_drawdown_v1": {
        "name": "次日冲高且无深回撤 v1",
        "description": "若次一交易日最高价达到 3%，且最低价相对信号日收盘价回撤不超过 3%，标记为 1。",
        "status": "planned",
    },
    "next_close_positive_v1": {
        "name": "次日收盘为正 v1",
        "description": "若次一交易日收盘涨幅为正，标记为 1。",
        "status": "planned",
    },
    "next_low_drawdown_3pct_v1": {
        "name": "次日低点回撤 3% v1",
        "description": "若次一交易日最低价相对信号日收盘价回撤超过 3%，标记为 1，作为风险标签。",
        "status": "planned",
    },
    "next_open_gap_down_2pct_v1": {
        "name": "次日低开 2% v1",
        "description": "若次一交易日开盘价相对信号日收盘价低开超过 2%，标记为 1，作为 T+1 风险标签。",
        "status": "planned",
    },
}


def list_label_sets() -> list[dict[str, str]]:
    return [{"id": key, **value} for key, value in LABEL_SETS.items()]
