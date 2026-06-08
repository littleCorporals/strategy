from __future__ import annotations

import asyncio
import ipaddress
import os
from urllib.parse import urlparse
from typing import Any, Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from app.core.config import ADMIN_TOKEN_ENV, STATIC_DIR
from app.db import model_repo
from app.services import data_gateway
from app.services import model_pipeline
from modeling.features.registry import list_feature_sets
from modeling.labels.builder import label_horizon
from modeling.labels.registry import list_label_sets
from modeling.pipelines.service import planned_pipeline


def _is_loopback(host: str | None) -> bool:
    if not host:
        return False
    if host in {"testclient", "testserver"}:
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return host in {"localhost", "localhost.localdomain"}


def _is_local_host_header(host: str | None) -> bool:
    if not host:
        return True
    return _is_loopback(host.split(":", 1)[0].strip("[]"))


def _is_local_origin(value: str | None) -> bool:
    if not value:
        return True
    parsed = urlparse(value)
    return _is_loopback(parsed.hostname)


async def require_admin_access(
    request: Request,
    origin: Annotated[str | None, Header(alias="Origin")] = None,
    referer: Annotated[str | None, Header(alias="Referer")] = None,
    x_admin_token: Annotated[str | None, Header(alias="X-Admin-Token")] = None,
) -> None:
    client_host = request.client.host if request.client else None
    if not _is_loopback(client_host) or not _is_local_host_header(request.headers.get("host")):
        raise HTTPException(status_code=403, detail="Admin API is only available from this machine.")
    if not _is_local_origin(origin) or not _is_local_origin(referer):
        raise HTTPException(status_code=403, detail="Cross-site admin requests are blocked.")
    expected_token = os.getenv(ADMIN_TOKEN_ENV, "").strip()
    if expected_token and x_admin_token != expected_token:
        raise HTTPException(status_code=401, detail="Admin token required.")


router = APIRouter(dependencies=[Depends(require_admin_access)])


async def _run_pipeline_in_worker(coro_factory: Any) -> dict[str, Any]:
    return await asyncio.to_thread(lambda: asyncio.run(coro_factory()))


async def pipeline_overview() -> dict[str, Any]:
    return {
        **planned_pipeline(),
        "recent_runs": await model_repo.list_pipeline_runs(),
    }


async def workflow_state() -> dict[str, Any]:
    active = await model_repo.active_model()
    latest_market_date = await data_gateway.latest_trade_date("daily")
    active_model_id = str(active["model_id"]) if active else None
    latest_prediction_date = await model_repo.latest_prediction_trade_date(active_model_id)
    suggested_prediction_date = latest_market_date or ""
    suggested_validation_date = ""
    validation_next_trade_date = ""
    validation_ready = False
    validation_reason = "没有激活模型。"
    if active:
        validation_reason = "还没有生成预测。"
        horizon = label_horizon(str(active.get("label_set") or "next_high_3pct_v1"))
        prediction_dates = await model_repo.recent_prediction_trade_dates(model_id=active_model_id, limit=30)
        for trade_date in prediction_dates:
            available_days = await model_pipeline.available_validation_trade_days(trade_date, horizon=horizon)
            if len(available_days) >= horizon:
                suggested_validation_date = trade_date
                validation_next_trade_date = available_days[0][0] or ""
                validation_ready = True
                validation_reason = "已有足够后续行情，可以验证。"
                break
        if not validation_ready and latest_prediction_date:
            suggested_validation_date = latest_prediction_date
            validation_reason = f"当前标签需要预测日后 {horizon} 个交易日行情，数据还不够。"
    return {
        "latest_market_date": latest_market_date,
        "latest_prediction_date": latest_prediction_date,
        "suggested_prediction_date": suggested_prediction_date,
        "suggested_validation_date": suggested_validation_date,
        "validation_next_trade_date": validation_next_trade_date,
        "validation_ready": validation_ready,
        "validation_reason": validation_reason,
    }


class TrainingRunRequest(BaseModel):
    dataset_version: str = Field(default="market_cache_v1", min_length=1)
    feature_set: str = Field(default="short_swing_v2", min_length=1)
    label_set: str = Field(default="next_high_3pct_v1", min_length=1)
    train_start_date: str | None = None
    train_end_date: str | None = None
    params: dict[str, Any] = Field(default_factory=dict)
    notes: str = ""


class HistoryBackfillRequest(BaseModel):
    start_date: str = Field(min_length=8, max_length=8)
    end_date: str | None = Field(default=None, min_length=8, max_length=8)
    max_days: int = Field(default=260, ge=1, le=520)


class TrainingMatrixRequest(BaseModel):
    dataset_version: str = Field(default="market_cache_v1", min_length=1)
    feature_sets: list[str] = Field(default_factory=lambda: ["short_swing_v2"])
    label_sets: list[str] = Field(
        default_factory=lambda: ["next_high_3pct_v1", "next_high_2pct_v1", "next_3d_high_3pct_v1"]
    )
    train_windows: list[dict[str, Any]] = Field(default_factory=list)
    params: dict[str, Any] = Field(default_factory=dict)
    activate_best: bool = False
    notes: str = ""


class ContinuousTrainingRequest(BaseModel):
    rounds: int = Field(default=3, ge=1, le=20)
    dataset_version: str = Field(default="market_cache_v1", min_length=1)
    feature_sets: list[str] = Field(default_factory=list)
    label_sets: list[str] = Field(default_factory=list)
    train_windows: list[dict[str, Any]] = Field(default_factory=list)
    params: dict[str, Any] = Field(default_factory=dict)
    activate_if_better: bool = True
    notes: str = ""


class ModelRegisterRequest(BaseModel):
    model_id: str | None = None
    name: str = Field(default="短线预测候选模型", min_length=1)
    model_type: str = Field(default="supervised_time_series", min_length=1)
    feature_set: str = Field(default="short_swing_v2", min_length=1)
    label_set: str = Field(default="next_high_3pct_v1", min_length=1)
    artifact_path: str | None = None
    metrics: dict[str, Any] = Field(default_factory=dict)
    params: dict[str, Any] = Field(default_factory=dict)


class PredictionRunRequest(BaseModel):
    trade_date: str | None = Field(default=None, min_length=8, max_length=8)
    limit: int = Field(default=500, ge=1, le=6000)


class ValidationRunRequest(BaseModel):
    trade_date: str | None = Field(default=None, min_length=8, max_length=8)


class RollbackRequest(BaseModel):
    reason: str = ""


class ModelDecisionRequest(BaseModel):
    reason: str = ""


@router.get("/admin", response_class=HTMLResponse)
async def admin_index() -> HTMLResponse:
    return HTMLResponse((STATIC_DIR / "admin.html").read_text(encoding="utf-8"))


@router.get("/api/admin/overview")
async def overview() -> dict[str, Any]:
    return {
        "active_model": await model_repo.active_model(),
        "models": await model_repo.list_models(),
        "model_events": await model_repo.list_model_events(limit=12),
        "model_performance": (await model_repo.model_performance_overview())["items"],
        "training_runs": await model_repo.list_training_runs(limit=10),
        "pipelines": await pipeline_overview(),
        "workflow": await workflow_state(),
        "feature_sets": list_feature_sets(),
        "label_sets": list_label_sets(),
    }


@router.get("/api/admin/models")
async def models() -> dict[str, Any]:
    return {
        "active_model": await model_repo.active_model(),
        "items": await model_repo.list_models(),
    }


@router.get("/api/admin/model-events")
async def model_events(
    model_id: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> dict[str, Any]:
    return {"items": await model_repo.list_model_events(model_id=model_id, limit=limit)}


@router.post("/api/admin/models")
async def register_model(payload: ModelRegisterRequest) -> dict[str, Any]:
    data = payload.model_dump() if hasattr(payload, "model_dump") else payload.dict()
    return {"ok": True, "item": await model_repo.create_model(data)}


@router.post("/api/admin/models/{model_id}/activate")
async def activate_model(model_id: str) -> dict[str, Any]:
    ok = await model_repo.activate_model(model_id)
    if not ok:
        raise HTTPException(status_code=400, detail="模型不存在或状态不允许上线")
    return {"ok": True, "active_model": await model_repo.active_model()}


@router.post("/api/admin/models/{model_id}/approve")
async def approve_model(model_id: str, payload: ModelDecisionRequest) -> dict[str, Any]:
    ok = await model_repo.approve_model(model_id, reason=payload.reason)
    if not ok:
        raise HTTPException(status_code=400, detail="模型不存在或状态不允许审批通过")
    return {"ok": True, "item": await model_repo.get_model(model_id)}


@router.post("/api/admin/models/{model_id}/reject")
async def reject_model(model_id: str, payload: ModelDecisionRequest) -> dict[str, Any]:
    ok = await model_repo.reject_model(model_id, reason=payload.reason)
    if not ok:
        raise HTTPException(status_code=400, detail="模型不存在或状态不允许拒绝")
    return {"ok": True, "item": await model_repo.get_model(model_id)}


@router.post("/api/admin/models/{model_id}/deactivate")
async def deactivate_model(model_id: str) -> dict[str, Any]:
    ok = await model_repo.deactivate_model(model_id)
    if not ok:
        raise HTTPException(status_code=404, detail="模型不存在")
    return {"ok": True, "item": await model_repo.get_model(model_id), "active_model": await model_repo.active_model()}


@router.post("/api/admin/models/{model_id}/archive")
async def archive_model(model_id: str) -> dict[str, Any]:
    ok = await model_repo.archive_model(model_id)
    if not ok:
        raise HTTPException(status_code=404, detail="模型不存在")
    return {"ok": True, "item": await model_repo.get_model(model_id), "active_model": await model_repo.active_model()}


@router.post("/api/admin/models/rollback")
async def rollback_model(payload: RollbackRequest) -> dict[str, Any]:
    active = await model_repo.rollback_active_model(reason=payload.reason)
    if not active:
        raise HTTPException(status_code=404, detail="没有可回滚的模型")
    return {"ok": True, "active_model": active}


@router.get("/api/admin/training-runs")
async def training_runs(limit: Annotated[int, Query(ge=1, le=100)] = 30) -> dict[str, Any]:
    return {"items": await model_repo.list_training_runs(limit=limit)}


@router.post("/api/admin/training-runs")
async def create_training_run(payload: TrainingRunRequest) -> dict[str, Any]:
    data = payload.model_dump() if hasattr(payload, "model_dump") else payload.dict()
    return {"ok": True, "item": await model_repo.create_training_run(data)}


@router.post("/api/admin/training-runs/{run_id}/run")
async def run_training(run_id: str) -> dict[str, Any]:
    try:
        return await _run_pipeline_in_worker(lambda: model_pipeline.run_training_pipeline(run_id))
    except ValueError as exc:
        status_code = 404 if "不存在" in str(exc) else 409
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/api/admin/history/backfill")
async def backfill_history(payload: HistoryBackfillRequest) -> dict[str, Any]:
    try:
        return await model_pipeline.backfill_daily_history(
            start_date=payload.start_date,
            end_date=payload.end_date,
            max_days=payload.max_days,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/api/admin/training-matrix/run")
async def run_training_matrix(payload: TrainingMatrixRequest) -> dict[str, Any]:
    try:
        return await _run_pipeline_in_worker(
            lambda: model_pipeline.run_training_matrix(
                dataset_version=payload.dataset_version,
                feature_sets=payload.feature_sets,
                label_sets=payload.label_sets,
                train_windows=payload.train_windows or None,
                params=payload.params,
                activate_best=payload.activate_best,
                notes=payload.notes,
            )
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/api/admin/training-continuous/run")
async def run_continuous_training(payload: ContinuousTrainingRequest) -> dict[str, Any]:
    try:
        return await _run_pipeline_in_worker(
            lambda: model_pipeline.run_continuous_training(
                rounds=payload.rounds,
                dataset_version=payload.dataset_version,
                feature_sets=payload.feature_sets or None,
                label_sets=payload.label_sets or None,
                train_windows=payload.train_windows or None,
                params=payload.params,
                activate_if_better=payload.activate_if_better,
                notes=payload.notes,
            )
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/api/admin/pipelines")
async def pipelines() -> dict[str, Any]:
    return await pipeline_overview()


@router.get("/api/admin/predictions")
async def predictions(trade_date: Annotated[str | None, Query()] = None) -> dict[str, Any]:
    return await model_repo.prediction_summary(trade_date)


@router.post("/api/admin/predictions/run")
async def run_prediction(payload: PredictionRunRequest) -> dict[str, Any]:
    try:
        trade_date = payload.trade_date or (await workflow_state())["suggested_prediction_date"]
        if not trade_date:
            raise ValueError("没有可预测的行情日期")
        return await model_pipeline.run_daily_prediction(trade_date, limit=payload.limit)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/api/admin/performance")
async def performance(trade_date: Annotated[str | None, Query()] = None) -> dict[str, Any]:
    return await model_repo.validation_summary(trade_date)


@router.get("/api/admin/model-performance")
async def model_performance() -> dict[str, Any]:
    return await model_repo.model_performance_overview()


@router.get("/api/admin/model-diagnostics")
async def model_diagnostics(model_id: Annotated[str | None, Query()] = None) -> dict[str, Any]:
    model = await model_repo.get_model(model_id) if model_id else await model_repo.active_model()
    if not model:
        raise HTTPException(status_code=404, detail="模型不存在")
    diagnostics = model_pipeline.model_artifact_diagnostics(model)
    return {
        "model": model,
        "diagnostics": diagnostics,
    }


@router.post("/api/admin/validations/run")
async def run_validation(payload: ValidationRunRequest) -> dict[str, Any]:
    try:
        trade_date = payload.trade_date or (await workflow_state())["suggested_validation_date"]
        if not trade_date:
            raise ValueError("没有可验证的预测日期")
        return await model_pipeline.run_next_day_validation(trade_date)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
