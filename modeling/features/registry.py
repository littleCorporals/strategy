from __future__ import annotations


FEATURE_SETS = {
    "short_swing_v1": {
        "name": "短线形态基础特征 v1",
        "description": "价格、涨跌幅、成交额、量能和 3/5 日动量等基础日线特征。",
        "status": "planned",
    },
    "short_swing_v2": {
        "name": "短线形态增强特征 v2",
        "description": "在 v1 基础上增加 10/20 日趋势、均线偏离、波动率、量能加速、影线、跳空和近 20 日位置特征。",
        "status": "planned",
    }
}


def list_feature_sets() -> list[dict[str, str]]:
    return [{"id": key, **value} for key, value in FEATURE_SETS.items()]
