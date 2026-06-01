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
    "next_close_positive_v1": {
        "name": "次日收盘为正 v1",
        "description": "若次一交易日收盘涨幅为正，标记为 1。",
        "status": "planned",
    },
}


def list_label_sets() -> list[dict[str, str]]:
    return [{"id": key, **value} for key, value in LABEL_SETS.items()]
