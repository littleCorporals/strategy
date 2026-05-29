from __future__ import annotations


FEATURE_SETS = {
    "short_swing_v1": {
        "name": "短线形态基础特征 v1",
        "description": "价格、涨跌幅、成交额、量能、均线偏离、换手、资金流等基础表格特征。",
        "status": "planned",
    }
}


def list_feature_sets() -> list[dict[str, str]]:
    return [{"id": key, **value} for key, value in FEATURE_SETS.items()]
