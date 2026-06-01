from __future__ import annotations

import math
from datetime import datetime
from typing import Any

from modeling.features.builder import feature_columns


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


def _artifact_columns(artifact: dict[str, Any]) -> list[str]:
    columns = artifact.get("feature_columns")
    if isinstance(columns, list) and columns:
        return [str(column) for column in columns]
    return feature_columns(str(artifact.get("feature_set") or "short_swing_v1"))


def score_features(features: dict[str, float], artifact: dict[str, Any]) -> float:
    score = float(artifact.get("intercept") or 0.0)
    weights = artifact.get("weights") or {}
    means = artifact.get("feature_means") or {}
    stds = artifact.get("feature_stds") or {}
    for name in _artifact_columns(artifact):
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


def _average_metric(samples: list[dict[str, Any]], key: str) -> float | None:
    values = [float(sample[key]) for sample in samples if sample.get(key) is not None]
    return round(_mean(values), 4) if values else None


def _log_loss(samples: list[dict[str, Any]], artifact: dict[str, Any]) -> float:
    if not samples:
        return 0.0
    total = 0.0
    for sample in samples:
        label = float(sample.get("label") or 0.0)
        _prediction, probability = _predict(sample.get("features") or {}, artifact)
        probability = min(1 - 1e-8, max(1e-8, probability))
        total += -(label * math.log(probability) + (1 - label) * math.log(1 - probability))
    return round(total / len(samples), 6)


def _normalized_features(sample: dict[str, Any], columns: list[str], means: dict[str, float], stds: dict[str, float]) -> list[float]:
    features = sample.get("features") or {}
    return [
        (float(features.get(name, 0.0)) - float(means.get(name, 0.0))) / float(stds.get(name, 1.0) or 1.0)
        for name in columns
    ]


def _topn_metrics(samples: list[dict[str, Any]], artifact: dict[str, Any], sizes: tuple[int, ...] = (20, 50, 100)) -> dict[str, Any]:
    if not samples:
        return {
            "market_hit_rate": 0.0,
            "top_n": {},
        }
    scored = [
        {
            **sample,
            "ml_score": score_features(sample.get("features") or {}, artifact),
        }
        for sample in samples
    ]
    scored.sort(key=lambda item: float(item["ml_score"]), reverse=True)
    market_hit_rate = round(_mean([float(sample.get("label") or 0) for sample in samples]), 4)
    top_n: dict[str, Any] = {}
    for size in sizes:
        picked = scored[: min(size, len(scored))]
        hit_rate = round(_mean([float(sample.get("label") or 0) for sample in picked]), 4) if picked else 0.0
        top_n[str(size)] = {
            "count": len(picked),
            "hit_rate": hit_rate,
            "lift": round(hit_rate - market_hit_rate, 4),
            "avg_next_close_pct": _average_metric(picked, "next_close_pct"),
            "avg_next_high_pct": _average_metric(picked, "next_high_pct"),
            "avg_window_high_pct": _average_metric(picked, "window_high_pct"),
        }
    return {
        "market_hit_rate": market_hit_rate,
        "top_n": top_n,
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
    columns = feature_columns(feature_set)
    split_ratio = float(params.get("validation_ratio", 0.2))
    split_ratio = min(0.5, max(0.1, split_ratio))
    split_index = max(1, int(len(samples) * (1 - split_ratio)))
    train_samples = samples[:split_index]
    validation_samples = samples[split_index:] or samples[-min(len(samples), 10) :]

    feature_means: dict[str, float] = {}
    feature_stds: dict[str, float] = {}
    for name in columns:
        values = [float((sample.get("features") or {}).get(name, 0.0)) for sample in train_samples]
        mean = _mean(values)
        std = _std(values, mean)
        feature_means[name] = round(mean, 8)
        feature_stds[name] = round(std, 8)

    positive_rate = _mean([float(sample.get("label") or 0) for sample in train_samples])
    weights_vector = [0.0 for _ in columns]
    intercept = math.log((positive_rate + 0.001) / (1 - positive_rate + 0.001))
    learning_rate = float(params.get("learning_rate", 0.06 if feature_set == "short_swing_v2" else 0.08))
    l2 = float(params.get("l2", 0.001))
    max_iter = int(params.get("max_iter", 450 if feature_set == "short_swing_v2" else 260))
    patience = int(params.get("patience", 35))
    train_matrix = [_normalized_features(sample, columns, feature_means, feature_stds) for sample in train_samples]
    validation_matrix = [_normalized_features(sample, columns, feature_means, feature_stds) for sample in validation_samples]
    train_labels = [float(sample.get("label") or 0.0) for sample in train_samples]
    validation_labels = [float(sample.get("label") or 0.0) for sample in validation_samples]

    best_loss = float("inf")
    best_iteration = 0
    best_weights = list(weights_vector)
    best_intercept = intercept
    rounds_without_improvement = 0
    history: list[dict[str, float | int]] = []
    for iteration in range(1, max_iter + 1):
        grad_weights = [0.0 for _ in columns]
        grad_intercept = 0.0
        train_loss = 0.0
        for values, label in zip(train_matrix, train_labels):
            raw = intercept + sum(weight * value for weight, value in zip(weights_vector, values))
            probability = _sigmoid(raw)
            error = probability - label
            probability = min(1 - 1e-8, max(1e-8, probability))
            train_loss += -(label * math.log(probability) + (1 - label) * math.log(1 - probability))
            grad_intercept += error
            for index, value in enumerate(values):
                grad_weights[index] += error * value
        sample_count = max(1, len(train_matrix))
        train_loss = train_loss / sample_count + l2 * sum(weight * weight for weight in weights_vector) / 2
        for index, weight in enumerate(weights_vector):
            grad = grad_weights[index] / sample_count + l2 * weight
            weights_vector[index] -= learning_rate * grad
        intercept -= learning_rate * grad_intercept / sample_count

        validation_loss = 0.0
        for values, label in zip(validation_matrix, validation_labels):
            raw = intercept + sum(weight * value for weight, value in zip(weights_vector, values))
            probability = min(1 - 1e-8, max(1e-8, _sigmoid(raw)))
            validation_loss += -(label * math.log(probability) + (1 - label) * math.log(1 - probability))
        validation_loss = validation_loss / max(1, len(validation_matrix))
        if iteration == 1 or iteration % 25 == 0:
            history.append(
                {
                    "iteration": iteration,
                    "train_log_loss": round(train_loss, 6),
                    "validation_log_loss": round(validation_loss, 6),
                }
            )
        if validation_loss + 1e-6 < best_loss:
            best_loss = validation_loss
            best_iteration = iteration
            best_weights = list(weights_vector)
            best_intercept = intercept
            rounds_without_improvement = 0
        else:
            rounds_without_improvement += 1
        if rounds_without_improvement >= patience:
            break

    weights = {name: round(best_weights[index], 8) for index, name in enumerate(columns)}
    artifact = {
        "model_type": "logistic_ranker_v1",
        "feature_set": feature_set,
        "label_set": label_set,
        "feature_columns": columns,
        "feature_means": feature_means,
        "feature_stds": feature_stds,
        "weights": weights,
        "intercept": round(best_intercept, 8),
        "threshold": 0.0,
        "score_scale": 1.0,
        "params": {
            **params,
            "learning_rate": learning_rate,
            "l2": l2,
            "max_iter": max_iter,
            "patience": patience,
        },
        "training": {
            "algorithm": "batch_gradient_descent_logistic_regression",
            "iterations": iteration,
            "best_iteration": best_iteration,
            "best_validation_log_loss": round(best_loss, 6),
            "history": history[-20:],
        },
        "created_at": datetime.now().isoformat(timespec="seconds"),
    }

    scores = [score_features(sample.get("features") or {}, artifact) for sample in train_samples]
    threshold_index = min(max(0, int(len(scores) * (1 - positive_rate))), len(scores) - 1) if scores else 0
    artifact["threshold"] = round(sorted(scores)[threshold_index] if scores else 0.0, 8)
    score_mean = _mean(scores)
    artifact["score_scale"] = round(_std(scores, score_mean), 8)

    train_metrics = _classification_metrics(train_samples, artifact)
    validation_metrics = _classification_metrics(validation_samples, artifact)
    train_metrics["log_loss"] = _log_loss(train_samples, artifact)
    validation_metrics["log_loss"] = _log_loss(validation_samples, artifact)
    train_ranking = _topn_metrics(train_samples, artifact)
    validation_ranking = _topn_metrics(validation_samples, artifact)
    metrics = {
        "sample_count": len(samples),
        "train_sample_count": len(train_samples),
        "validation_sample_count": len(validation_samples),
        "train": train_metrics,
        "validation": validation_metrics,
        "ranking": {
            "train": train_ranking,
            "validation": validation_ranking,
        },
        "accuracy": validation_metrics["accuracy"],
        "precision": validation_metrics["precision"],
        "recall": validation_metrics["recall"],
        "f1": validation_metrics["f1"],
        "positive_rate": round(positive_rate, 4),
    }
    return artifact, metrics
