from __future__ import annotations

from typing import Any


PIPELINE_STAGES: list[dict[str, str]] = [
    {"id": "dataset", "name": "构建训练集", "status": "planned"},
    {"id": "features", "name": "生成特征", "status": "planned"},
    {"id": "train", "name": "训练模型", "status": "planned"},
    {"id": "evaluate", "name": "时间序列验证", "status": "planned"},
    {"id": "register", "name": "注册模型版本", "status": "planned"},
    {"id": "predict", "name": "生成每日预测", "status": "planned"},
    {"id": "validate", "name": "次日表现验证", "status": "planned"},
]


def planned_pipeline() -> dict[str, Any]:
    return {"stages": [dict(stage) for stage in PIPELINE_STAGES]}
