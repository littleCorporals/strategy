from __future__ import annotations

import math
from datetime import datetime
from typing import Any

from modeling.features.builder import FEATURE_COLUMNS


def _sigmoid(value: float) -> float:
    value = max(-60.0, min(60.0, value))
    return 1.0 / (1.0 + math.exp(-value))


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _std(values: list[float], mean: float) -> float:
    if len(values) < 2:
        return 1.0
    variance = sum((value - mean) ** 2 for value in values) / len(values)
    return math.sqrt(variance) or 1.0


def score_features(features: dict[str, float], artifact: dict[str, Any]) -> float:
    score = float(artifact.get("intercept") or 0.0)
    weights = artifact.get("weights") or {}
    means = artifact.get("feature_means") or {}
    stds = artifact.get("feature_stds") or {}
    for name in FEATURE_COLUMNS:
        value = float(features.get(name, 0.0))
        score += float(weights.get(name, 0.0)) * ((value - float(means.get(name, 0.0))) / float(stds.get(name, 1.0) or 1.0))
    return score


def _predict(features: dict[str, float], artifact: dict[str, Any]) -> tuple[int, float]:
    raw_score = score_features(features, artifact)
    threshold = float(artifact.get("threshold") or 0.0)
    scale = float(artifact.get("score_scale") or 1.0) or 1.0
    probability = _sigmoid((raw_score - threshold) / scale)
    return int(raw_score >= threshold), probability


def _classification_metrics(samples: list[dict[str, Any]], artifact: dict[str, Any]) -> dict[str, float]:
    if not samples:
        return {"accuracy": 0.0, "precision": 0.0, "recall": 0.0, "f1": 0.0, "positive_rate": 0.0}
    tp = fp = tn = fn = 0
    positives = 0
    for sample in samples:
        label = int(sample.get("label") or 0)
        prediction, _probability = _predict(sample.get("features") or {}, artifact)
        positives += label
        if prediction == 1 and label == 1:
            tp += 1
        elif prediction == 1:
            fp += 1
        elif label == 1:
            fn += 1
        else:
            tn += 1
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if precision + recall else 0.0
    return {
        "accuracy": round((tp + tn) / len(samples), 4),
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "positive_rate": round(positives / len(samples), 4),
    }


def train_baseline_model(
    samples: list[dict[str, Any]],
    *,
    feature_set: str,
    label_set: str,
    params: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    if not samples:
        raise ValueError("训练样本为空，无法注册模型")

    params = params or {}
    split_ratio = float(params.get("validation_ratio", 0.2))
    split_ratio = min(0.5, max(0.1, split_ratio))
    split_index = max(1, int(len(samples) * (1 - split_ratio)))
    train_samples = samples[:split_index]
    validation_samples = samples[split_index:] or samples[-min(len(samples), 10) :]

    feature_means: dict[str, float] = {}
    feature_stds: dict[str, float] = {}
    weights: dict[str, float] = {}
    for name in FEATURE_COLUMNS:
        values = [float((sample.get("features") or {}).get(name, 0.0)) for sample in train_samples]
        mean = _mean(values)
        std = _std(values, mean)
        positives = [float((sample.get("features") or {}).get(name, 0.0)) for sample in train_samples if sample.get("label")]
        negatives = [float((sample.get("features") or {}).get(name, 0.0)) for sample in train_samples if not sample.get("label")]
        feature_means[name] = round(mean, 8)
        feature_stds[name] = round(std, 8)
        weights[name] = round((_mean(positives) - _mean(negatives)) / std, 8) if positives and negatives else 0.0

    positive_rate = _mean([float(sample.get("label") or 0) for sample in train_samples])
    artifact = {
        "model_type": "baseline_linear_ranker",
        "feature_set": feature_set,
        "label_set": label_set,
        "feature_columns": FEATURE_COLUMNS,
        "feature_means": feature_means,
        "feature_stds": feature_stds,
        "weights": weights,
        "intercept": round(math.log((positive_rate + 0.001) / (1 - positive_rate + 0.001)), 8),
        "threshold": 0.0,
        "score_scale": 1.0,
        "params": params,
        "created_at": datetime.now().isoformat(timespec="seconds"),
    }

    scores = [score_features(sample.get("features") or {}, artifact) for sample in train_samples]
    threshold_index = min(max(0, int(len(scores) * (1 - positive_rate))), len(scores) - 1) if scores else 0
    artifact["threshold"] = round(sorted(scores)[threshold_index] if scores else 0.0, 8)
    score_mean = _mean(scores)
    artifact["score_scale"] = round(_std(scores, score_mean), 8)

    train_metrics = _classification_metrics(train_samples, artifact)
    validation_metrics = _classification_metrics(validation_samples, artifact)
    metrics = {
        "sample_count": len(samples),
        "train_sample_count": len(train_samples),
        "validation_sample_count": len(validation_samples),
        "train": train_metrics,
        "validation": validation_metrics,
        "accuracy": validation_metrics["accuracy"],
        "precision": validation_metrics["precision"],
        "recall": validation_metrics["recall"],
        "f1": validation_metrics["f1"],
        "positive_rate": round(positive_rate, 4),
    }
    return artifact, metrics
