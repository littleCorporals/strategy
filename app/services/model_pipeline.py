from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.core.config import DATA_DIR
from app.db import model_repo
from app.repositories import market_cache
from app.services import analysis, market_data
from modeling.datasets.supervised import build_supervised_samples
from modeling.features.builder import build_feature_row
from modeling.inference.baseline import predict_one
from modeling.labels.builder import build_label
from modeling.registry.artifacts import save_model_artifact
from modeling.training.baseline import train_baseline_model


MODEL_ARTIFACT_DIR = DATA_DIR / "models"


async def run_training_pipeline(run_id: str) -> dict[str, Any]:
    run = await model_repo.get_training_run(run_id)
    if not run:
        raise ValueError("训练任务不存在")

    await model_repo.update_training_run(run_id, status="running", started=True)
    try:
        rows = await market_cache.fetch_rows(
            "daily",
            start_date=run.get("train_start_date"),
            end_date=run.get("train_end_date"),
        )
        samples = build_supervised_samples(rows, label_set=str(run.get("label_set") or "next_high_3pct_v1"))
        artifact, metrics = train_baseline_model(
            samples,
            feature_set=str(run.get("feature_set") or "short_swing_v1"),
            label_set=str(run.get("label_set") or "next_high_3pct_v1"),
            params=run.get("params") or {},
        )
        model = await model_repo.create_model(
            {
                "name": f"{run.get('feature_set')} / {run.get('label_set')}",
                "model_type": artifact["model_type"],
                "feature_set": run.get("feature_set"),
                "label_set": run.get("label_set"),
                "metrics": metrics,
                "params": run.get("params") or {},
            }
        )
        artifact_path = save_model_artifact(str(model["model_id"]), artifact, Path(MODEL_ARTIFACT_DIR))
        model = await model_repo.update_model_artifact(str(model["model_id"]), str(artifact_path)) or model
        updated_run = await model_repo.update_training_run(
            run_id,
            status="completed",
            model_id=str(model["model_id"]),
            sample_count=len(samples),
            metrics=metrics,
            error="",
            finished=True,
        )
        pipeline = await model_repo.create_pipeline_run(
            {
                "pipeline_type": "training",
                "status": "completed",
                "payload": {
                    "run_id": run_id,
                    "model_id": model["model_id"],
                    "sample_count": len(samples),
                    "metrics": metrics,
                    "artifact_path": str(artifact_path),
                },
            }
        )
        return {"ok": True, "run": updated_run, "model": model, "pipeline": pipeline}
    except Exception as exc:
        await model_repo.update_training_run(run_id, status="failed", error=str(exc), finished=True)
        await model_repo.create_pipeline_run(
            {
                "pipeline_type": "training",
                "status": "failed",
                "payload": {"run_id": run_id},
                "error": str(exc),
            }
        )
        raise


def _load_artifact(model: dict[str, Any]) -> dict[str, Any]:
    path = model.get("artifact_path")
    if not path:
        raise ValueError("模型缺少 artifact_path")
    artifact_path = Path(str(path))
    allowed_dir = Path(MODEL_ARTIFACT_DIR).resolve()
    resolved_path = artifact_path.resolve()
    if not resolved_path.is_relative_to(allowed_dir):
        raise ValueError("Model artifact must be stored in the local model directory.")
    if not resolved_path.exists():
        raise ValueError("模型 artifact 不存在")
    return json.loads(resolved_path.read_text(encoding="utf-8"))


def _history_by_code(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    by_code: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        ts_code = str(row.get("ts_code") or "")
        if ts_code:
            by_code.setdefault(ts_code, []).append(row)
    for items in by_code.values():
        items.sort(key=lambda row: str(row.get("trade_date") or ""))
    return by_code


async def run_daily_prediction(trade_date: str, *, limit: int = 500) -> dict[str, Any]:
    model = await model_repo.active_model()
    if not model:
        raise ValueError("没有激活模型")
    artifact = _load_artifact(model)

    end_date, day_rows = await market_data.latest_raw_daily_rows(trade_date, market_data.HISTORY_FIELDS)
    if not day_rows:
        raise ValueError("没有可预测的行情数据")

    start_date = market_data.previous_calendar_date(end_date)
    rows = await market_cache.fetch_rows("daily", start_date="19000101", end_date=end_date)
    by_code = _history_by_code(rows)
    predictions: list[dict[str, Any]] = []
    for row in day_rows:
        ts_code = str(row.get("ts_code") or "")
        history = [item for item in by_code.get(ts_code, []) if str(item.get("trade_date") or "") <= end_date]
        if len(history) < 6:
            continue
        features = build_feature_row(history)
        prediction = predict_one(features, artifact)
        predictions.append(
            {
                "ts_code": ts_code,
                "trade_date": end_date,
                "probability": prediction["probability"],
                "ml_score": prediction["ml_score"],
                "features": features,
            }
        )

    predictions.sort(key=lambda item: (item["probability"], item["ml_score"]), reverse=True)
    predictions = predictions[: max(1, limit)]
    await model_repo.save_predictions(str(model["model_id"]), end_date, predictions)
    pipeline = await model_repo.create_pipeline_run(
        {
            "pipeline_type": "prediction",
            "status": "completed",
            "trade_date": end_date,
            "payload": {
                "model_id": model["model_id"],
                "requested_trade_date": trade_date,
                "trade_date": end_date,
                "count": len(predictions),
            },
        }
    )
    return {"ok": True, "model": model, "trade_date": end_date, "count": len(predictions), "items": predictions, "pipeline": pipeline}


def _validation_result(
    prediction: dict[str, Any],
    current_row: dict[str, Any],
    next_row: dict[str, Any],
    *,
    label_set: str,
) -> dict[str, Any]:
    close = analysis.number(current_row, "close")
    next_close = analysis.number(next_row, "close")
    next_high = analysis.number(next_row, "high")
    next_close_pct = ((next_close - close) / close * 100) if close and next_close is not None else None
    next_high_pct = ((next_high - close) / close * 100) if close and next_high is not None else None
    label_value = build_label(current_row, next_row, label_set)
    return {
        "ts_code": prediction["ts_code"],
        "label_value": label_value,
        "next_trade_date": str(next_row.get("trade_date") or ""),
        "next_close_pct": round(next_close_pct, 4) if next_close_pct is not None else None,
        "next_high_pct": round(next_high_pct, 4) if next_high_pct is not None else None,
        "result": {
            "probability": prediction.get("probability"),
            "ml_score": prediction.get("ml_score"),
            "label_set": label_set,
        },
    }


async def run_next_day_validation(trade_date: str) -> dict[str, Any]:
    model = await model_repo.active_model()
    if not model:
        raise ValueError("没有激活模型")

    predictions = await model_repo.list_predictions(str(model["model_id"]), trade_date)
    if not predictions:
        raise ValueError("没有可验证的预测结果")

    current_rows = await market_cache.fetch_rows("daily", trade_date=trade_date)
    next_date, next_rows = await market_data.next_trade_rows_raw(trade_date, market_data.HISTORY_FIELDS)
    if not next_date or not next_rows:
        raise ValueError("没有下一交易日行情，暂不能验证")

    current_map = {str(row.get("ts_code") or ""): row for row in current_rows}
    next_map = {str(row.get("ts_code") or ""): row for row in next_rows}
    label_set = str(model.get("label_set") or "next_high_3pct_v1")
    results: list[dict[str, Any]] = []
    for prediction in predictions:
        ts_code = str(prediction.get("ts_code") or "")
        if ts_code in current_map and ts_code in next_map:
            results.append(
                _validation_result(
                    prediction,
                    current_map[ts_code],
                    next_map[ts_code],
                    label_set=label_set,
                )
            )

    await model_repo.save_validation_results(str(model["model_id"]), trade_date, results)
    hit_rate = analysis.avg([float(item["label_value"]) for item in results]) if results else 0.0
    pipeline = await model_repo.create_pipeline_run(
        {
            "pipeline_type": "validation",
            "status": "completed",
            "trade_date": trade_date,
            "payload": {
                "model_id": model["model_id"],
                "trade_date": trade_date,
                "next_trade_date": next_date,
                "count": len(results),
                "hit_rate": round(hit_rate or 0.0, 4),
            },
        }
    )
    return {
        "ok": True,
        "model": model,
        "trade_date": trade_date,
        "next_trade_date": next_date,
        "count": len(results),
        "hit_rate": round(hit_rate or 0.0, 4),
        "items": results,
        "pipeline": pipeline,
    }
