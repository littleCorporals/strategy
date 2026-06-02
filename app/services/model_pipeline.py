from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from app.core.config import DATA_DIR
from app.db import model_repo
from app.repositories import market_cache
from app.services import analysis, market_data
from modeling.datasets.supervised import build_supervised_samples
from modeling.features.builder import build_feature_row
from modeling.inference.baseline import predict_one
from modeling.labels.builder import build_label, label_horizon
from modeling.registry.artifacts import save_model_artifact
from modeling.training.baseline import train_baseline_model


MODEL_ARTIFACT_DIR = DATA_DIR / "models"
DEFAULT_MATRIX_LABEL_SETS = ("next_high_3pct_v1", "next_high_2pct_v1", "next_3d_high_3pct_v1")


def _parse_yyyymmdd(value: str | None, field_name: str) -> date:
    text = str(value or "").strip()
    if len(text) != 8 or not text.isdigit():
        raise ValueError(f"{field_name} 必须是 YYYYMMDD 格式")
    try:
        return datetime.strptime(text, "%Y%m%d").date()
    except ValueError as exc:
        raise ValueError(f"{field_name} 不是有效日期") from exc


def _weekday_trade_dates(start: date, end: date) -> list[str]:
    days: list[str] = []
    current = start
    while current <= end:
        if current.weekday() < 5:
            days.append(current.strftime("%Y%m%d"))
        current += timedelta(days=1)
    return days


def _top50_score(metrics: dict[str, Any]) -> tuple[float, float, float, int]:
    validation_ranking = ((metrics.get("ranking") or {}).get("validation") or {})
    top50 = ((validation_ranking.get("top_n") or {}).get("50") or {})
    validation = metrics.get("validation") or {}
    return (
        float(top50.get("lift") or 0.0),
        float(top50.get("hit_rate") or 0.0),
        float(validation.get("f1") or metrics.get("f1") or 0.0),
        int(metrics.get("validation_sample_count") or 0),
    )


def _metric_summary(metrics: dict[str, Any]) -> dict[str, Any]:
    validation_ranking = ((metrics.get("ranking") or {}).get("validation") or {})
    top50 = ((validation_ranking.get("top_n") or {}).get("50") or {})
    return {
        "sample_count": metrics.get("sample_count"),
        "validation_sample_count": metrics.get("validation_sample_count"),
        "f1": metrics.get("f1"),
        "market_hit_rate": validation_ranking.get("market_hit_rate"),
        "top50_hit_rate": top50.get("hit_rate"),
        "top50_lift": top50.get("lift"),
        "top50_avg_window_high_pct": top50.get("avg_window_high_pct"),
    }


async def backfill_daily_history(
    *,
    start_date: str,
    end_date: str | None = None,
    max_days: int = 260,
) -> dict[str, Any]:
    start = _parse_yyyymmdd(start_date, "start_date")
    requested_end = _parse_yyyymmdd(end_date or market_data.today_trade_date(), "end_date")
    fetchable_end = _parse_yyyymmdd(
        market_data.latest_fetchable_trade_date(requested_end.strftime("%Y%m%d")),
        "end_date",
    )
    if start > fetchable_end:
        raise ValueError("start_date 不能晚于可回填的 end_date")

    days = _weekday_trade_dates(start, fetchable_end)
    max_days = min(520, max(1, int(max_days or 1)))
    if len(days) > max_days:
        raise ValueError(f"本次最多回填 {max_days} 个工作日，请缩小日期范围或调大 max_days")

    items: list[dict[str, Any]] = []
    cached_days = 0
    fetched_days = 0
    empty_days = 0
    failed_days = 0
    total_rows = 0
    for trade_date in days:
        state = await market_cache.complete_state("daily", trade_date)
        if state:
            row_count = int(state["row_count"] or 0)
            total_rows += max(0, row_count)
            if row_count > 0:
                cached_days += 1
                status = "cached"
            else:
                empty_days += 1
                status = "empty_cached"
            items.append({"trade_date": trade_date, "status": status, "row_count": row_count})
            continue

        try:
            rows = await market_data.daily_rows_raw(trade_date, market_data.HISTORY_FIELDS)
        except Exception as exc:  # keep partial progress visible to the admin caller
            failed_days += 1
            items.append({"trade_date": trade_date, "status": "failed", "row_count": 0, "error": str(exc)})
            break

        row_count = len(rows)
        total_rows += row_count
        if row_count:
            fetched_days += 1
            status = "fetched"
        else:
            empty_days += 1
            status = "empty"
        items.append({"trade_date": trade_date, "status": status, "row_count": row_count})

    return {
        "ok": failed_days == 0,
        "start_date": start.strftime("%Y%m%d"),
        "end_date": fetchable_end.strftime("%Y%m%d"),
        "requested_weekdays": len(days),
        "processed_days": len(items),
        "cached_days": cached_days,
        "fetched_days": fetched_days,
        "empty_days": empty_days,
        "failed_days": failed_days,
        "row_count": total_rows,
        "items": items,
    }


async def default_training_windows(max_windows: int = 1) -> list[dict[str, Any]]:
    rows = await market_cache.fetch_rows("daily", fields="trade_date")
    dates = sorted({str(row.get("trade_date") or "") for row in rows if row.get("trade_date")})
    if not dates:
        return [{"name": "all_cached", "train_start_date": None, "train_end_date": None}]

    windows: list[dict[str, Any]] = [
        {
            "name": "all_cached",
            "train_start_date": dates[0],
            "train_end_date": dates[-1],
        }
    ]
    for size in (120, 60):
        if len(dates) > size:
            windows.append(
                {
                    "name": f"recent_{size}_trade_days",
                    "train_start_date": dates[-size],
                    "train_end_date": dates[-1],
                }
            )
    return windows[: max(1, max_windows)]


async def run_training_matrix(
    *,
    dataset_version: str = "market_cache_v1",
    feature_sets: list[str] | None = None,
    label_sets: list[str] | None = None,
    train_windows: list[dict[str, Any]] | None = None,
    params: dict[str, Any] | None = None,
    activate_best: bool = False,
    notes: str = "",
) -> dict[str, Any]:
    selected_features = [item for item in (feature_sets or ["short_swing_v2"]) if item]
    selected_labels = [item for item in (label_sets or list(DEFAULT_MATRIX_LABEL_SETS)) if item]
    windows = train_windows or await default_training_windows()
    params = params or {}
    if not selected_features:
        raise ValueError("至少需要一个 feature_set")
    if not selected_labels:
        raise ValueError("至少需要一个 label_set")
    if not windows:
        raise ValueError("至少需要一个训练窗口")

    results: list[dict[str, Any]] = []
    for window in windows:
        window_name = str(window.get("name") or "window")
        train_start_date = window.get("train_start_date")
        train_end_date = window.get("train_end_date")
        for feature_set in selected_features:
            for label_set in selected_labels:
                run = await model_repo.create_training_run(
                    {
                        "dataset_version": dataset_version,
                        "feature_set": feature_set,
                        "label_set": label_set,
                        "train_start_date": train_start_date,
                        "train_end_date": train_end_date,
                        "params": params,
                        "notes": notes or f"training matrix {window_name}",
                    }
                )
                try:
                    trained = await run_training_pipeline(str(run["run_id"]))
                    metrics = trained["run"].get("metrics") or {}
                    results.append(
                        {
                            "ok": True,
                            "window": window_name,
                            "feature_set": feature_set,
                            "label_set": label_set,
                            "run": trained["run"],
                            "model": trained["model"],
                            "score": _top50_score(metrics),
                            "metrics_summary": _metric_summary(metrics),
                        }
                    )
                except Exception as exc:
                    results.append(
                        {
                            "ok": False,
                            "window": window_name,
                            "feature_set": feature_set,
                            "label_set": label_set,
                            "run": await model_repo.get_training_run(str(run["run_id"])) or run,
                            "error": str(exc),
                        }
                    )

    completed = [item for item in results if item.get("ok")]
    best = max(completed, key=lambda item: tuple(item.get("score") or (0.0, 0.0, 0.0, 0))) if completed else None
    active = await model_repo.active_model()
    if best and activate_best:
        model_id = str((best.get("model") or {}).get("model_id") or "")
        if model_id:
            await model_repo.approve_model(model_id, reason="training matrix best candidate")
            await model_repo.activate_model(model_id)
            best["model"] = await model_repo.get_model(model_id) or best["model"]
            active = await model_repo.active_model()

    pipeline = await model_repo.create_pipeline_run(
        {
            "pipeline_type": "training_matrix",
            "status": "completed" if completed else "failed",
            "payload": {
                "completed_count": len(completed),
                "failed_count": len(results) - len(completed),
                "best_model_id": (best.get("model") or {}).get("model_id") if best else None,
                "best_score": best.get("score") if best else None,
                "activate_best": activate_best,
                "windows": windows,
                "feature_sets": selected_features,
                "label_sets": selected_labels,
            },
            "error": "" if completed else "training matrix produced no completed models",
        }
    )
    return {
        "ok": bool(completed),
        "completed_count": len(completed),
        "failed_count": len(results) - len(completed),
        "best": best,
        "active_model": active,
        "items": results,
        "pipeline": pipeline,
    }


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
        samples = build_supervised_samples(
            rows,
            feature_set=str(run.get("feature_set") or "short_swing_v2"),
            label_set=str(run.get("label_set") or "next_high_3pct_v1"),
        )
        artifact, metrics = train_baseline_model(
            samples,
            feature_set=str(run.get("feature_set") or "short_swing_v2"),
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


def model_artifact_diagnostics(model: dict[str, Any]) -> dict[str, Any]:
    artifact = _load_artifact(model)
    weights = artifact.get("weights") or {}
    weight_items = []
    if isinstance(weights, dict):
        for feature, value in weights.items():
            try:
                number = float(value)
            except (TypeError, ValueError):
                number = 0.0
            weight_items.append(
                {
                    "feature": str(feature),
                    "weight": round(number, 8),
                    "abs_weight": round(abs(number), 8),
                }
            )
    weight_items.sort(key=lambda item: item["abs_weight"], reverse=True)
    feature_columns = artifact.get("feature_columns") or []
    return {
        "model_type": artifact.get("model_type"),
        "feature_set": artifact.get("feature_set"),
        "label_set": artifact.get("label_set"),
        "feature_count": len(feature_columns) if isinstance(feature_columns, list) else 0,
        "feature_columns": feature_columns if isinstance(feature_columns, list) else [],
        "non_zero_weight_count": sum(1 for item in weight_items if item["abs_weight"] > 0),
        "top_weights": weight_items,
        "training": artifact.get("training") or {},
        "params": artifact.get("params") or {},
        "threshold": artifact.get("threshold"),
        "score_scale": artifact.get("score_scale"),
        "created_at": artifact.get("created_at"),
    }


def _history_by_code(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    by_code: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        ts_code = str(row.get("ts_code") or "")
        if ts_code:
            by_code.setdefault(ts_code, []).append(row)
    for items in by_code.values():
        items.sort(key=lambda row: str(row.get("trade_date") or ""))
    return by_code


def _future_rows_for_code(
    by_code: dict[str, list[dict[str, Any]]],
    ts_code: str,
    trade_date: str,
    horizon: int,
) -> list[dict[str, Any]]:
    return [
        item
        for item in by_code.get(ts_code, [])
        if str(item.get("trade_date") or "") > trade_date
    ][:horizon]


def _average(values: list[float | None]) -> float | None:
    cleaned = [float(value) for value in values if value is not None]
    return round(sum(cleaned) / len(cleaned), 4) if cleaned else None


def _topn_validation_summary(
    results: list[dict[str, Any]],
    market_results: list[dict[str, Any]],
    sizes: tuple[int, ...] = (20, 50, 100),
) -> dict[str, Any]:
    market_hit_rate = analysis.avg([float(item["label_value"]) for item in market_results]) if market_results else 0.0
    market_hit_rate = round(float(market_hit_rate or 0.0), 4)
    sorted_results = sorted(
        results,
        key=lambda item: (
            float((item.get("result") or {}).get("probability") or 0.0),
            float((item.get("result") or {}).get("ml_score") or 0.0),
        ),
        reverse=True,
    )
    top_n: dict[str, Any] = {}
    for size in sizes:
        picked = sorted_results[: min(size, len(sorted_results))]
        hit_rate = analysis.avg([float(item["label_value"]) for item in picked]) if picked else 0.0
        hit_rate = round(float(hit_rate or 0.0), 4)
        top_n[str(size)] = {
            "count": len(picked),
            "hit_rate": hit_rate,
            "lift": round(hit_rate - market_hit_rate, 4),
            "avg_next_close_pct": _average([item.get("next_close_pct") for item in picked]),
            "avg_next_high_pct": _average([item.get("next_high_pct") for item in picked]),
            "avg_window_high_pct": _average([item.get("window_high_pct") for item in picked]),
        }
    return {
        "market_count": len(market_results),
        "market_hit_rate": market_hit_rate,
        "top_n": top_n,
    }


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
        features = build_feature_row(history, feature_set=str(model.get("feature_set") or "short_swing_v2"))
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


async def next_available_validation_rows(trade_date: str) -> tuple[str | None, list[dict[str, Any]]]:
    days = await available_validation_trade_days(trade_date, horizon=1)
    return days[0] if days else (None, [])


async def available_validation_trade_days(
    trade_date: str,
    *,
    horizon: int = 1,
    lookahead_days: int = 15,
    allow_online: bool = False,
) -> list[tuple[str, list[dict[str, Any]]]]:
    days: list[tuple[str, list[dict[str, Any]]]] = []
    current = datetime.strptime(trade_date, "%Y%m%d").date() + timedelta(days=1)
    for _ in range(max(1, lookahead_days)):
        if current.weekday() < 5:
            day = current.strftime("%Y%m%d")
            if allow_online:
                rows = await market_data.daily_rows_raw(day, market_data.HISTORY_FIELDS)
            else:
                rows = await market_cache.fetch_rows(
                    "daily",
                    trade_date=day,
                    fields=market_data.HISTORY_FIELDS,
                    require_complete=True,
                )
            if rows:
                days.append((day, rows))
                if len(days) >= horizon:
                    break
        current += timedelta(days=1)
    return days


def _validation_result(
    prediction: dict[str, Any],
    current_row: dict[str, Any],
    next_row: dict[str, Any],
    *,
    label_set: str,
    future_rows: list[dict[str, Any]] | None = None,
    rank: int | None = None,
) -> dict[str, Any]:
    close = analysis.number(current_row, "close")
    next_close = analysis.number(next_row, "close")
    next_high = analysis.number(next_row, "high")
    next_close_pct = ((next_close - close) / close * 100) if close and next_close is not None else None
    next_high_pct = ((next_high - close) / close * 100) if close and next_high is not None else None
    future = future_rows or [next_row]
    future_highs = [value for item in future if (value := analysis.number(item, "high")) is not None]
    window_high_pct = ((max(future_highs) - close) / close * 100) if close and future_highs else None
    label_value = build_label(current_row, next_row, label_set, future_rows=future)
    return {
        "ts_code": prediction["ts_code"],
        "label_value": label_value,
        "next_trade_date": str(next_row.get("trade_date") or ""),
        "next_close_pct": round(next_close_pct, 4) if next_close_pct is not None else None,
        "next_high_pct": round(next_high_pct, 4) if next_high_pct is not None else None,
        "window_high_pct": round(window_high_pct, 4) if window_high_pct is not None else None,
        "result": {
            "probability": prediction.get("probability"),
            "ml_score": prediction.get("ml_score"),
            "label_set": label_set,
            "rank": rank,
            "label_horizon": len(future),
        },
    }


async def run_next_day_validation(trade_date: str) -> dict[str, Any]:
    model = await model_repo.active_model()
    if not model:
        raise ValueError("没有激活模型")

    predictions = await model_repo.list_predictions(str(model["model_id"]), trade_date)
    if not predictions:
        raise ValueError("没有可验证的预测结果")

    label_set = str(model.get("label_set") or "next_high_3pct_v1")
    horizon = label_horizon(label_set)
    current_rows = await market_cache.fetch_rows("daily", trade_date=trade_date)
    available_days = await available_validation_trade_days(trade_date, horizon=horizon, allow_online=True)
    if len(available_days) < horizon:
        raise ValueError("预测日后的行情天数还不够，暂不能验证")
    next_date, next_rows = available_days[0]
    all_rows = await market_cache.fetch_rows("daily", start_date=trade_date)
    by_code = _history_by_code(all_rows)

    current_map = {str(row.get("ts_code") or ""): row for row in current_rows}
    next_map = {str(row.get("ts_code") or ""): row for row in next_rows}
    market_results: list[dict[str, Any]] = []
    for ts_code, current_row in current_map.items():
        future_rows = _future_rows_for_code(by_code, ts_code, trade_date, horizon)
        next_row = future_rows[0] if future_rows else next_map.get(ts_code)
        if next_row and len(future_rows or [next_row]) >= horizon:
            market_results.append(
                _validation_result(
                    {"ts_code": ts_code},
                    current_row,
                    next_row,
                    label_set=label_set,
                    future_rows=future_rows or [next_row],
                )
            )

    results: list[dict[str, Any]] = []
    for rank, prediction in enumerate(predictions, start=1):
        ts_code = str(prediction.get("ts_code") or "")
        future_rows = _future_rows_for_code(by_code, ts_code, trade_date, horizon)
        next_row = future_rows[0] if future_rows else next_map.get(ts_code)
        if ts_code in current_map and next_row and len(future_rows or [next_row]) >= horizon:
            results.append(
                _validation_result(
                    prediction,
                    current_map[ts_code],
                    next_row,
                    label_set=label_set,
                    future_rows=future_rows or [next_row],
                    rank=rank,
                )
            )

    await model_repo.save_validation_results(str(model["model_id"]), trade_date, results)
    hit_rate = analysis.avg([float(item["label_value"]) for item in results]) if results else 0.0
    ranking = _topn_validation_summary(results, market_results)
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
                "ranking": ranking,
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
        "ranking": ranking,
        "items": results,
        "pipeline": pipeline,
    }
