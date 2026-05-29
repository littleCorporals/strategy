from __future__ import annotations

from typing import Any

from modeling.training.baseline import _sigmoid, score_features


def predict_one(features: dict[str, float], artifact: dict[str, Any]) -> dict[str, float]:
    score = score_features(features, artifact)
    threshold = float(artifact.get("threshold") or 0.0)
    scale = float(artifact.get("score_scale") or 1.0) or 1.0
    probability = _sigmoid((score - threshold) / scale)
    return {"ml_score": round(score, 8), "probability": round(probability, 8)}
