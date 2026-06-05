from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient


def test_status_initializes_temp_database(isolated_app: tuple[TestClient, Path]) -> None:
    client, db_path = isolated_app

    response = client.get("/api/status")

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["database_ready"] is True
    assert payload["database"]["path"] == "local sqlite cache"
    assert payload["token_preview"] is None
    assert payload["proxy_url"] is None
    assert db_path.exists()

    from app.db import cache as db_cache

    with db_cache.connect() as conn:
        versions = [row["version"] for row in conn.execute("SELECT version FROM schema_migrations")]

    assert "0001_initial_schema" in versions


def test_admin_api_rejects_non_loopback_clients(isolated_app: tuple[TestClient, Path]) -> None:
    client, _db_path = isolated_app

    response = client.get("/api/admin/overview", headers={"host": "example.test"})

    assert response.status_code == 403


def test_daily_uses_database_before_online_fetch(
    isolated_app: tuple[TestClient, Path],
    monkeypatch,
) -> None:
    client, _db_path = isolated_app

    from app.db import cache as db_cache
    from app.services import market_data

    db_cache.init_sync()
    db_cache.save_rows_sync(
        "daily",
        [
            {
                "ts_code": "000001.SZ",
                "trade_date": "20240102",
                "open": 10.0,
                "high": 11.0,
                "low": 9.8,
                "close": 10.6,
                "pre_close": 10.1,
                "change": 0.5,
                "pct_chg": 4.95,
                "vol": 1000,
                "amount": 10600,
            }
        ],
        complete=True,
        default_trade_date="20240102",
        source="test",
    )

    async def fail_online_fetch(**_kwargs: Any) -> list[dict[str, Any]]:
        raise AssertionError("daily rows should be read from local database")

    monkeypatch.setattr(market_data, "call_daily", fail_online_fetch)

    response = client.get("/api/daily", params={"trade_date": "20240102"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["data_source"] == "database"
    assert payload["database_cached"] is True
    assert payload["rows"][0]["ts_code"] == "000001.SZ"
    assert payload["rows"][0]["close"] == 10.6


def test_daily_cache_miss_fetches_once_and_persists(
    isolated_app: tuple[TestClient, Path],
    monkeypatch,
) -> None:
    client, _db_path = isolated_app

    from app.services import market_data

    calls = {"daily": 0}

    async def fake_daily(**_kwargs: Any) -> list[dict[str, Any]]:
        calls["daily"] += 1
        return [
            {
                "ts_code": "000002.SZ",
                "trade_date": "20240103",
                "open": 20.0,
                "high": 21.5,
                "low": 19.8,
                "close": 21.0,
                "pre_close": 20.0,
                "change": 1.0,
                "pct_chg": 5.0,
                "vol": 2000,
                "amount": 42000,
            }
        ]

    async def passthrough_basic(rows: list[dict[str, Any]], allow_online: bool = True) -> list[dict[str, Any]]:
        return rows

    monkeypatch.setattr(market_data, "call_daily", fake_daily)
    monkeypatch.setattr(market_data, "attach_stock_basic", passthrough_basic)

    first = client.get("/api/daily", params={"trade_date": "20240103"})
    market_data._cache.clear()
    second = client.get("/api/daily", params={"trade_date": "20240103"})

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["data_source"] == "online"
    assert second.json()["data_source"] == "database"
    assert calls["daily"] == 1
    assert second.json()["database_cached"] is True
    assert second.json()["rows"][0]["ts_code"] == "000002.SZ"


def test_admin_overview_has_model_management_sections(isolated_app: tuple[TestClient, Path]) -> None:
    client, _db_path = isolated_app

    response = client.get("/api/admin/overview")

    assert response.status_code == 200
    payload = response.json()
    assert "models" in payload
    assert "training_runs" in payload
    assert "pipelines" in payload
    assert "feature_sets" in payload
    assert "label_sets" in payload
    assert "workflow" in payload
    assert "suggested_prediction_date" in payload["workflow"]
    assert "suggested_validation_date" in payload["workflow"]


def test_training_run_can_be_queued(isolated_app: tuple[TestClient, Path]) -> None:
    client, _db_path = isolated_app

    response = client.post(
        "/api/admin/training-runs",
        json={
            "dataset_version": "market_cache_v1",
            "feature_set": "short_swing_v1",
            "label_set": "next_high_3pct_v1",
            "params": {"max_depth": 3},
            "notes": "pytest",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["item"]["status"] == "queued"
    assert payload["item"]["dataset_version"] == "market_cache_v1"

    list_response = client.get("/api/admin/training-runs")
    run_ids = {item["run_id"] for item in list_response.json()["items"]}
    assert payload["item"]["run_id"] in run_ids


def test_model_lifecycle_register_activate_deactivate_archive(isolated_app: tuple[TestClient, Path]) -> None:
    client, _db_path = isolated_app

    first = client.post(
        "/api/admin/models",
        json={
            "name": "candidate-a",
            "feature_set": "short_swing_v1",
            "label_set": "next_high_3pct_v1",
            "metrics": {"auc": 0.61},
        },
    )
    second = client.post(
        "/api/admin/models",
        json={
            "name": "candidate-b",
            "feature_set": "short_swing_v1",
            "label_set": "next_close_positive_v1",
            "metrics": {"auc": 0.64},
        },
    )

    assert first.status_code == 200
    assert second.status_code == 200
    first_model = first.json()["item"]
    second_model = second.json()["item"]
    assert first_model["status"] == "candidate"
    assert first_model["metrics"]["auc"] == 0.61

    direct_activate = client.post(f"/api/admin/models/{first_model['model_id']}/activate")
    approve_first = client.post(f"/api/admin/models/{first_model['model_id']}/approve", json={"reason": "pytest approve"})
    approve_second = client.post(f"/api/admin/models/{second_model['model_id']}/approve", json={"reason": "pytest approve"})
    activate_first = client.post(f"/api/admin/models/{first_model['model_id']}/activate")
    activate_second = client.post(f"/api/admin/models/{second_model['model_id']}/activate")

    assert direct_activate.status_code == 400
    assert approve_first.status_code == 200
    assert approve_first.json()["item"]["status"] == "approved"
    assert approve_second.status_code == 200
    assert activate_first.status_code == 200
    assert activate_first.json()["active_model"]["model_id"] == first_model["model_id"]
    assert activate_second.status_code == 200
    assert activate_second.json()["active_model"]["model_id"] == second_model["model_id"]

    models = {item["model_id"]: item for item in client.get("/api/admin/models").json()["items"]}
    assert models[first_model["model_id"]]["status"] == "inactive"
    assert models[second_model["model_id"]]["status"] == "active"

    deactivate = client.post(f"/api/admin/models/{second_model['model_id']}/deactivate")
    archive = client.post(f"/api/admin/models/{first_model['model_id']}/archive")

    assert deactivate.status_code == 200
    assert deactivate.json()["item"]["status"] == "inactive"
    assert deactivate.json()["active_model"] is None
    assert archive.status_code == 200
    assert archive.json()["item"]["status"] == "archived"


def test_model_events_and_rollback(isolated_app: tuple[TestClient, Path]) -> None:
    client, _db_path = isolated_app

    first = client.post(
        "/api/admin/models",
        json={"name": "rollback-a", "feature_set": "short_swing_v1", "label_set": "next_high_3pct_v1"},
    ).json()["item"]
    second = client.post(
        "/api/admin/models",
        json={"name": "rollback-b", "feature_set": "short_swing_v1", "label_set": "next_high_3pct_v1"},
    ).json()["item"]

    assert client.post(f"/api/admin/models/{first['model_id']}/approve", json={}).status_code == 200
    assert client.post(f"/api/admin/models/{second['model_id']}/approve", json={}).status_code == 200
    assert client.post(f"/api/admin/models/{first['model_id']}/activate").status_code == 200
    assert client.post(f"/api/admin/models/{second['model_id']}/activate").status_code == 200

    rollback = client.post("/api/admin/models/rollback", json={"reason": "pytest rollback"})

    assert rollback.status_code == 200
    assert rollback.json()["active_model"]["model_id"] == first["model_id"]

    events = client.get("/api/admin/model-events").json()["items"]
    event_types = [item["event_type"] for item in events]
    assert "registered" in event_types
    assert "activated" in event_types
    assert "superseded" in event_types
    assert "rollback_from" in event_types
    assert "rollback_to" in event_types

    first_events = client.get("/api/admin/model-events", params={"model_id": first["model_id"]}).json()["items"]
    assert any(item["event_type"] == "rollback_to" for item in first_events)


def test_rejected_model_cannot_be_activated(isolated_app: tuple[TestClient, Path]) -> None:
    client, _db_path = isolated_app

    model = client.post(
        "/api/admin/models",
        json={"name": "rejected-model", "feature_set": "short_swing_v1", "label_set": "next_high_3pct_v1"},
    ).json()["item"]

    reject = client.post(f"/api/admin/models/{model['model_id']}/reject", json={"reason": "bad metrics"})
    activate = client.post(f"/api/admin/models/{model['model_id']}/activate")

    assert reject.status_code == 200
    assert reject.json()["item"]["status"] == "rejected"
    assert activate.status_code == 400


def test_prediction_rejects_artifact_outside_model_directory(isolated_app: tuple[TestClient, Path]) -> None:
    client, db_path = isolated_app

    model = client.post(
        "/api/admin/models",
        json={
            "name": "unsafe-artifact",
            "feature_set": "short_swing_v1",
            "label_set": "next_high_3pct_v1",
            "artifact_path": str(db_path),
        },
    ).json()["item"]

    assert client.post(f"/api/admin/models/{model['model_id']}/approve", json={}).status_code == 200
    assert client.post(f"/api/admin/models/{model['model_id']}/activate").status_code == 200

    response = client.post("/api/admin/predictions/run", json={"trade_date": "20240109"})

    assert response.status_code == 400
    assert "local model directory" in response.json()["detail"]


def test_training_run_executes_pipeline_and_registers_candidate_model(
    isolated_app: tuple[TestClient, Path],
) -> None:
    client, db_path = isolated_app

    from app.db import cache as db_cache

    rows: list[dict[str, Any]] = []
    for code_index, ts_code in enumerate(["000001.SZ", "000002.SZ", "000003.SZ"]):
        base = 10 + code_index
        for day in range(1, 10):
            close = base + day * (0.12 + code_index * 0.03)
            rows.append(
                {
                    "ts_code": ts_code,
                    "trade_date": f"202401{day:02d}",
                    "open": round(close - 0.08, 3),
                    "high": round(close * (1.01 + day * 0.002), 3),
                    "low": round(close * 0.985, 3),
                    "close": round(close, 3),
                    "pre_close": round(close - 0.1, 3),
                    "change": 0.1,
                    "pct_chg": round(1 + day * 0.1, 3),
                    "vol": 1000 + day * 25 + code_index * 40,
                    "amount": 10000 + day * 400 + code_index * 500,
                }
            )
    db_cache.init_sync()
    db_cache.save_rows_sync("daily", rows, complete=False)

    queued = client.post(
        "/api/admin/training-runs",
        json={
            "dataset_version": "market_cache_v1",
            "feature_set": "short_swing_v1",
            "label_set": "next_high_3pct_v1",
            "params": {"validation_ratio": 0.25},
        },
    ).json()["item"]

    response = client.post(f"/api/admin/training-runs/{queued['run_id']}/run")

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["run"]["status"] == "completed"
    assert payload["run"]["sample_count"] > 0
    assert payload["model"]["status"] == "candidate"
    assert payload["model"]["model_type"] == "logistic_ranker_v1"
    assert payload["model"]["artifact_path"]
    assert Path(payload["model"]["artifact_path"]).exists()
    assert Path(payload["model"]["artifact_path"]).is_relative_to(db_path.parent)
    assert payload["run"]["metrics"]["validation"]["log_loss"] > 0
    assert payload["run"]["metrics"]["ranking"]["validation"]["top_n"]["20"]["count"] > 0
    assert "market_hit_rate" in payload["run"]["metrics"]["ranking"]["validation"]
    assert payload["pipeline"]["status"] == "completed"

    rerun = client.post(f"/api/admin/training-runs/{queued['run_id']}/run")
    assert rerun.status_code == 200
    assert rerun.json()["reused"] is True
    assert rerun.json()["model"]["model_id"] == payload["model"]["model_id"]
    assert len(client.get("/api/admin/models").json()["items"]) == 1


def test_history_backfill_fetches_missing_daily_rows(
    isolated_app: tuple[TestClient, Path],
    monkeypatch,
) -> None:
    client, _db_path = isolated_app

    from app.services import market_data

    calls: list[str] = []

    async def fake_daily(**kwargs: Any) -> list[dict[str, Any]]:
        trade_date = str(kwargs["trade_date"])
        calls.append(trade_date)
        return [
            {
                "ts_code": "000001.SZ",
                "trade_date": trade_date,
                "open": 10.0,
                "high": 10.6,
                "low": 9.8,
                "close": 10.2,
                "pre_close": 10.0,
                "change": 0.2,
                "pct_chg": 2.0,
                "vol": 1000,
                "amount": 10200,
            }
        ]

    monkeypatch.setattr(market_data, "call_daily", fake_daily)

    response = client.post(
        "/api/admin/history/backfill",
        json={"start_date": "20240102", "end_date": "20240103", "max_days": 5},
    )
    second = client.post(
        "/api/admin/history/backfill",
        json={"start_date": "20240102", "end_date": "20240103", "max_days": 5},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["fetched_days"] == 2
    assert payload["row_count"] == 2
    assert calls == ["20240102", "20240103"]
    assert second.status_code == 200
    assert second.json()["cached_days"] == 2
    assert calls == ["20240102", "20240103"]


def test_training_matrix_runs_multiple_labels_and_can_activate_best(
    isolated_app: tuple[TestClient, Path],
) -> None:
    client, _db_path = isolated_app

    from app.db import cache as db_cache

    rows: list[dict[str, Any]] = []
    for code_index, ts_code in enumerate(["000001.SZ", "000002.SZ", "000003.SZ", "000004.SZ"]):
        base = 10 + code_index
        for day in range(1, 16):
            close = base + day * (0.08 + code_index * 0.02)
            rows.append(
                {
                    "ts_code": ts_code,
                    "trade_date": f"202401{day:02d}",
                    "open": round(close - 0.05, 3),
                    "high": round(close * (1.015 + (day % 4) * 0.008 + code_index * 0.002), 3),
                    "low": round(close * 0.985, 3),
                    "close": round(close, 3),
                    "pre_close": round(close - 0.08, 3),
                    "change": 0.08,
                    "pct_chg": round(0.8 + (day % 5) * 0.15 + code_index * 0.08, 3),
                    "vol": 1000 + day * 35 + code_index * 50,
                    "amount": 10000 + day * 420 + code_index * 650,
                }
            )
    db_cache.init_sync()
    db_cache.save_rows_sync("daily", rows, complete=False)
    for day in range(1, 16):
        db_cache.mark_complete_sync("daily", f"202401{day:02d}", 4, "test")

    response = client.post(
        "/api/admin/training-matrix/run",
        json={
            "feature_sets": ["short_swing_v1"],
            "label_sets": ["next_high_2pct_v1", "next_high_3pct_v1"],
            "train_windows": [
                {
                    "name": "pytest_window",
                    "train_start_date": "20240101",
                    "train_end_date": "20240115",
                }
            ],
            "params": {"validation_ratio": 0.25, "max_iter": 40, "patience": 8},
            "activate_best": True,
            "notes": "pytest matrix",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["completed_count"] == 2
    assert payload["failed_count"] == 0
    assert payload["best"]["model"]["status"] == "active"
    assert payload["active_model"]["model_id"] == payload["best"]["model"]["model_id"]
    assert payload["best"]["metrics_summary"]["top50_hit_rate"] is not None
    assert {item["label_set"] for item in payload["items"]} == {"next_high_2pct_v1", "next_high_3pct_v1"}


def test_multi_day_label_builds_samples() -> None:
    from modeling.datasets.supervised import build_supervised_samples

    rows: list[dict[str, Any]] = []
    for day in range(1, 10):
        close = 10 + day * 0.1
        rows.append(
            {
                "ts_code": "000001.SZ",
                "trade_date": f"202401{day:02d}",
                "open": close,
                "high": close * (1.01 if day < 8 else 1.04),
                "low": close * 0.99,
                "close": close,
                "pct_chg": 1.0,
                "vol": 1000 + day,
                "amount": 10000 + day,
            }
        )

    one_day = build_supervised_samples(rows, label_set="next_high_3pct_v1")
    three_day = build_supervised_samples(rows, label_set="next_3d_high_3pct_v1")

    assert len(three_day) < len(one_day)
    assert three_day[0]["label_end_trade_date"] == "20240109"
    assert three_day[0]["label"] == 1
    assert three_day[0]["window_high_pct"] is not None


def test_short_swing_v2_adds_enhanced_daily_features() -> None:
    from modeling.datasets.supervised import build_supervised_samples
    from modeling.features.builder import feature_columns

    rows: list[dict[str, Any]] = []
    for day in range(1, 30):
        close = 10 + day * 0.12
        rows.append(
            {
                "ts_code": "000001.SZ",
                "trade_date": f"202401{day:02d}",
                "open": close - 0.05,
                "high": close * 1.02,
                "low": close * 0.98,
                "close": close,
                "pre_close": close - 0.1,
                "pct_chg": 1.0,
                "vol": 1000 + day * 10,
                "amount": 10000 + day * 100,
            }
        )

    samples = build_supervised_samples(rows, feature_set="short_swing_v2", label_set="next_high_3pct_v1")

    assert len(feature_columns("short_swing_v2")) > len(feature_columns("short_swing_v1"))
    assert "momentum_20" in samples[0]["features"]
    assert "upper_shadow_pct" in samples[0]["features"]


def test_prediction_and_validation_pipeline(
    isolated_app: tuple[TestClient, Path],
) -> None:
    client, _db_path = isolated_app

    from app.db import cache as db_cache

    rows: list[dict[str, Any]] = []
    for code_index, ts_code in enumerate(["000001.SZ", "000002.SZ", "000003.SZ"]):
        base = 10 + code_index
        for day in range(1, 11):
            close = base + day * (0.1 + code_index * 0.05)
            rows.append(
                {
                    "ts_code": ts_code,
                    "trade_date": f"202401{day:02d}",
                    "open": round(close - 0.08, 3),
                    "high": round(close * (1.02 + code_index * 0.005), 3),
                    "low": round(close * 0.985, 3),
                    "close": round(close, 3),
                    "pre_close": round(close - 0.1, 3),
                    "change": 0.1,
                    "pct_chg": round(1 + day * 0.08 + code_index * 0.1, 3),
                    "vol": 1000 + day * 30 + code_index * 60,
                    "amount": 10000 + day * 450 + code_index * 600,
                }
            )
    db_cache.init_sync()
    db_cache.save_rows_sync("daily", rows, complete=False)
    for day in range(1, 11):
        db_cache.mark_complete_sync("daily", f"202401{day:02d}", 3, "test")

    queued = client.post(
        "/api/admin/training-runs",
        json={
            "dataset_version": "market_cache_v1",
            "feature_set": "short_swing_v1",
            "label_set": "next_high_3pct_v1",
            "train_end_date": "20240108",
        },
    ).json()["item"]
    trained = client.post(f"/api/admin/training-runs/{queued['run_id']}/run").json()
    model_id = trained["model"]["model_id"]
    assert client.post(f"/api/admin/models/{model_id}/approve", json={}).status_code == 200
    assert client.post(f"/api/admin/models/{model_id}/activate").status_code == 200

    prediction = client.post(
        "/api/admin/predictions/run",
        json={"trade_date": "20240109", "limit": 10},
    )
    validation = client.post(
        "/api/admin/validations/run",
        json={"trade_date": "20240109"},
    )

    assert prediction.status_code == 200
    prediction_payload = prediction.json()
    assert prediction_payload["trade_date"] == "20240109"
    assert prediction_payload["count"] == 3
    assert prediction_payload["items"][0]["probability"] >= prediction_payload["items"][-1]["probability"]

    assert validation.status_code == 200
    validation_payload = validation.json()
    assert validation_payload["trade_date"] == "20240109"
    assert validation_payload["next_trade_date"] == "20240110"
    assert validation_payload["count"] == 3
    assert validation_payload["ranking"]["market_count"] == 3
    assert validation_payload["ranking"]["top_n"]["20"]["count"] == 3
    assert "lift" in validation_payload["ranking"]["top_n"]["20"]

    summaries = client.get("/api/admin/predictions", params={"trade_date": "20240109"}).json()["items"]
    performance = client.get("/api/admin/performance", params={"trade_date": "20240109"}).json()["items"]
    model_performance = client.get("/api/admin/model-performance").json()["items"]
    diagnostics = client.get("/api/admin/model-diagnostics", params={"model_id": model_id}).json()
    assert summaries[0]["count"] == 3
    assert performance[0]["count"] == 3
    assert model_performance[0]["model_id"] == model_id
    assert model_performance[0]["prediction_count"] == 3
    assert model_performance[0]["validation_count"] == 3
    assert model_performance[0]["hit_rate"] is not None
    assert model_performance[0]["ranking"]["top_n"]["20"]["count"] == 3
    assert diagnostics["model"]["model_id"] == model_id
    assert diagnostics["diagnostics"]["feature_count"] > 0
    assert diagnostics["diagnostics"]["training"]["iterations"] > 0
    assert diagnostics["diagnostics"]["top_weights"]


def test_admin_prediction_and_validation_can_use_workflow_defaults(
    isolated_app: tuple[TestClient, Path],
) -> None:
    client, _db_path = isolated_app

    from app.db import cache as db_cache

    rows: list[dict[str, Any]] = []
    for code_index, ts_code in enumerate(["000001.SZ", "000002.SZ", "000003.SZ"]):
        base = 10 + code_index
        for day in range(1, 11):
            close = base + day * (0.1 + code_index * 0.05)
            rows.append(
                {
                    "ts_code": ts_code,
                    "trade_date": f"202401{day:02d}",
                    "open": round(close - 0.08, 3),
                    "high": round(close * 1.03, 3),
                    "low": round(close * 0.985, 3),
                    "close": round(close, 3),
                    "pre_close": round(close - 0.1, 3),
                    "change": 0.1,
                    "pct_chg": round(1 + day * 0.08, 3),
                    "vol": 1000 + day * 30,
                    "amount": 10000 + day * 450,
                }
            )
    db_cache.init_sync()
    db_cache.save_rows_sync("daily", rows, complete=False)
    for day in range(1, 11):
        db_cache.mark_complete_sync("daily", f"202401{day:02d}", 3, "test")

    queued = client.post(
        "/api/admin/training-runs",
        json={
            "dataset_version": "market_cache_v1",
            "feature_set": "short_swing_v1",
            "label_set": "next_high_3pct_v1",
            "train_end_date": "20240108",
        },
    ).json()["item"]
    trained = client.post(f"/api/admin/training-runs/{queued['run_id']}/run").json()
    model_id = trained["model"]["model_id"]
    assert client.post(f"/api/admin/models/{model_id}/approve", json={}).status_code == 200
    assert client.post(f"/api/admin/models/{model_id}/activate").status_code == 200

    earlier_prediction = client.post(
        "/api/admin/predictions/run",
        json={"trade_date": "20240109", "limit": 10},
    )
    prediction = client.post("/api/admin/predictions/run", json={"limit": 10})
    overview_after_prediction = client.get("/api/admin/overview").json()
    validation = client.post("/api/admin/validations/run", json={})

    assert earlier_prediction.status_code == 200
    assert earlier_prediction.json()["trade_date"] == "20240109"
    assert prediction.status_code == 200
    assert prediction.json()["trade_date"] == "20240110"
    assert overview_after_prediction["workflow"]["suggested_prediction_date"] == "20240110"
    assert overview_after_prediction["workflow"]["suggested_validation_date"] == "20240109"
    assert overview_after_prediction["workflow"]["validation_ready"] is True
    assert validation.status_code == 200
    assert validation.json()["trade_date"] == "20240109"
    assert validation.json()["next_trade_date"] == "20240110"


def test_stock_analysis_reports_actual_trade_date(
    isolated_app: tuple[TestClient, Path],
    monkeypatch,
) -> None:
    client, _db_path = isolated_app

    from app.services import market_data

    async def fake_stock_history(
        ts_code: str,
        end_date: str,
        days: int,
        fields: str | None = None,
    ) -> list[dict[str, Any]]:
        assert ts_code == "000001.SZ"
        assert end_date == "20240108"
        return [
            {
                "ts_code": "000001.SZ",
                "trade_date": f"202312{day:02d}",
                "open": 10 + index * 0.1,
                "high": 10.5 + index * 0.1,
                "low": 9.8 + index * 0.1,
                "close": 10.2 + index * 0.1,
                "pre_close": 10 + index * 0.1,
                "change": 0.2,
                "pct_chg": 1.0,
                "vol": 1000 + index * 10,
                "amount": 10000 + index * 100,
            }
            for index, day in enumerate(range(1, 22))
        ]

    requested_query_dates: list[str] = []

    async def fake_single_query_row(interface: str, **params: Any) -> dict[str, Any] | None:
        requested_query_dates.append(str(params["trade_date"]))
        if interface == "daily_basic":
            return {
                "ts_code": params["ts_code"],
                "trade_date": params["trade_date"],
                "turnover_rate": 4.2,
                "volume_ratio": 1.1,
                "pe": 12.5,
                "pb": 1.4,
            }
        if interface == "moneyflow":
            return {
                "ts_code": params["ts_code"],
                "trade_date": params["trade_date"],
                "net_mf_amount": 100,
                "buy_elg_amount": 300,
                "sell_elg_amount": 120,
                "buy_lg_amount": 240,
                "sell_lg_amount": 180,
                "buy_md_amount": 80,
                "sell_md_amount": 90,
                "buy_sm_amount": 60,
                "sell_sm_amount": 70,
            }
        return None

    monkeypatch.setattr(market_data, "stock_history", fake_stock_history)
    monkeypatch.setattr(market_data, "single_query_row", fake_single_query_row)

    response = client.get("/api/stock/000001.SZ/analysis", params={"end_date": "20240108"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["requested_end_date"] == "20240108"
    assert payload["trade_date"] == "20231221"
    assert payload["actual_trade_date"] == "20231221"
    assert requested_query_dates == ["20231221", "20231221"]


def test_late_session_recommendations_attach_realtime_tplus1_status(
    isolated_app: tuple[TestClient, Path],
    monkeypatch,
) -> None:
    client, _db_path = isolated_app

    from app.db import cache as db_cache
    from app.services import market_data, realtime_quote

    rows: list[dict[str, Any]] = []
    for day in range(1, 25):
        close = 10 + day * 0.12
        vol = 1000 + day * 18
        rows.append(
            {
                "ts_code": "000001.SZ",
                "trade_date": f"202401{day:02d}",
                "open": round(close - 0.05, 2),
                "high": round(close + 0.2, 2),
                "low": round(close - 0.2, 2),
                "close": round(close, 2),
                "pre_close": round(close - 0.1, 2),
                "change": 0.1,
                "pct_chg": 2.4 if day == 24 else 1.0,
                "vol": vol,
                "amount": 12000 + day * 100,
            }
        )
    rows[-1].update(
        {
            "open": 12.55,
            "high": 12.95,
            "low": 12.45,
            "close": 12.75,
            "pre_close": 12.45,
            "change": 0.3,
            "vol": 1700,
            "amount": 50000,
        }
    )

    db_cache.init_sync()
    db_cache.save_rows_sync("daily", rows, complete=False)
    db_cache.save_rows_sync(
        "daily_basic",
        [
            {
                "ts_code": "000001.SZ",
                "trade_date": "20240124",
                "turnover_rate": 6.2,
                "turnover_rate_f": 7.1,
                "volume_ratio": 1.4,
                "total_mv": 300000,
                "circ_mv": 200000,
                "pe": 15,
                "pb": 1.6,
            }
        ],
        complete=False,
    )
    db_cache.save_rows_sync(
        "stock_basic",
        [{"ts_code": "000001.SZ", "name": "测试银行", "industry": "银行", "area": "深圳"}],
        complete=False,
        default_trade_date="",
    )
    for day in range(1, 25):
        db_cache.mark_complete_sync("daily", f"202401{day:02d}", 1, "test")
    db_cache.mark_complete_sync("daily_basic", "20240124", 1, "test")

    async def fake_quotes(ts_codes: list[str]) -> dict[str, dict[str, Any]]:
        assert ts_codes == ["000001.SZ"]
        return {
            "000001.SZ": {
                "ts_code": "000001.SZ",
                "source": "test",
                "available": True,
                "price": 12.8,
                "pct_chg": 0.4,
                "amount_yi": 1.2,
                "quote_date": "2024-01-25",
                "quote_time": "14:30:00",
            }
        }

    monkeypatch.setattr(realtime_quote, "sina_quotes", fake_quotes)

    async def fake_daily_basic_map(trade_date: str) -> dict[str, dict[str, Any]]:
        assert trade_date == "20240124"
        return {
            "000001.SZ": {
                "turnover_rate": 6.2,
                "turnover_rate_f": 7.1,
                "volume_ratio": 1.4,
                "total_mv": 300000,
                "circ_mv": 200000,
                "pe": 15,
                "pb": 1.6,
            }
        }

    async def fake_attach_stock_basic(rows_to_attach: list[dict[str, Any]], allow_online: bool = True) -> list[dict[str, Any]]:
        return [{**row, "name": "测试银行", "industry": "银行", "area": "深圳"} for row in rows_to_attach]

    monkeypatch.setattr(market_data, "daily_basic_map", fake_daily_basic_map)
    monkeypatch.setattr(market_data, "attach_stock_basic", fake_attach_stock_basic)

    async def fake_stock_history(
        ts_code: str,
        end_date: str,
        days: int,
        fields: str | None = None,
    ) -> list[dict[str, Any]]:
        assert ts_code == "000001.SZ"
        assert end_date == "20240124"
        return rows[-days:]

    monkeypatch.setattr(market_data, "stock_history", fake_stock_history)

    response = client.get("/api/recommendations/late-session", params={"trade_date": "20240124"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["data_source"] == "database+realtime"
    assert payload["count"] == 1
    item = payload["rows"][0]
    assert item["late_session"]["quote"]["price"] == 12.8
    assert item["late_session"]["action"] in {"可继续观察", "等回踩"}
    assert "T+1" in item["late_session"]["t_plus_1_note"]


def test_ml_late_session_filters_raw_model_predictions_with_realtime_gate(
    isolated_app: tuple[TestClient, Path],
    monkeypatch,
) -> None:
    client, _db_path = isolated_app

    from app.db import cache as db_cache
    from app.services import realtime_quote

    db_cache.init_sync()
    db_cache.save_rows_sync(
        "daily",
        [
            {
                "ts_code": "000001.SZ",
                "trade_date": "20240124",
                "open": 10.0,
                "high": 10.3,
                "low": 9.8,
                "close": 10.1,
                "pre_close": 9.9,
                "change": 0.2,
                "pct_chg": 2.02,
                "vol": 2000,
                "amount": 20200,
            },
            {
                "ts_code": "000002.SZ",
                "trade_date": "20240124",
                "open": 20.0,
                "high": 20.4,
                "low": 19.5,
                "close": 20.1,
                "pre_close": 19.9,
                "change": 0.2,
                "pct_chg": 1.01,
                "vol": 2200,
                "amount": 44200,
            },
            {
                "ts_code": "000003.SZ",
                "trade_date": "20240124",
                "open": 30.0,
                "high": 31.0,
                "low": 29.8,
                "close": 30.8,
                "pre_close": 30.0,
                "change": 0.8,
                "pct_chg": 2.67,
                "vol": 2400,
                "amount": 73920,
            },
        ],
        complete=True,
        default_trade_date="20240124",
        source="test",
    )
    db_cache.save_rows_sync(
        "stock_basic",
        [
            {"ts_code": "000001.SZ", "name": "合格股份", "industry": "元器件", "area": "深圳"},
            {"ts_code": "000002.SZ", "name": "走弱股份", "industry": "元器件", "area": "深圳"},
            {"ts_code": "000003.SZ", "name": "过热股份", "industry": "半导体", "area": "上海"},
        ],
        complete=True,
        default_trade_date="",
        source="test",
    )

    now = "2024-01-25T14:30:00"
    metrics = {
        "sample_count": 300,
        "train_sample_count": 240,
        "validation_sample_count": 60,
        "train": {"f1": 0.5, "log_loss": 0.52},
        "validation": {"accuracy": 0.7, "precision": 0.55, "recall": 0.6, "f1": 0.57, "log_loss": 0.61},
        "ranking": {
            "validation": {
                "market_hit_rate": 0.3,
                "top_n": {"50": {"count": 3, "hit_rate": 0.66, "lift": 0.36}},
            }
        },
    }
    with db_cache.connect() as conn:
        conn.execute(
            """
            INSERT INTO ml_models(
                model_id, name, status, model_type, feature_set, label_set,
                artifact_path, metrics_json, params_json, created_at, activated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "model_pytest_realtime",
                "pytest realtime",
                "active",
                "logistic_ranker_v1",
                "short_swing_v2",
                "next_high_3pct_v1",
                None,
                json.dumps(metrics, ensure_ascii=False),
                "{}",
                now,
                now,
            ),
        )
        for ts_code, probability in [
            ("000002.SZ", 0.99),
            ("000003.SZ", 0.98),
            ("000001.SZ", 0.97),
        ]:
            conn.execute(
                """
                INSERT INTO ml_predictions(
                    model_id, trade_date, ts_code, probability, ml_score, features_json, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                ("model_pytest_realtime", "20240124", ts_code, probability, probability, "{}", now),
            )
        conn.commit()

    async def fake_quotes(ts_codes: list[str]) -> dict[str, dict[str, Any]]:
        assert set(ts_codes) == {"000001.SZ", "000002.SZ", "000003.SZ"}
        return {
            "000001.SZ": {
                "ts_code": "000001.SZ",
                "name": "合格股份",
                "source": "test",
                "available": True,
                "pre_close": 10.0,
                "price": 10.2,
                "pct_chg": 2.0,
                "high": 10.5,
                "low": 9.8,
                "amount_yi": 2.6,
                "quote_date": "2024-01-25",
                "quote_time": "14:30:00",
            },
            "000002.SZ": {
                "ts_code": "000002.SZ",
                "name": "走弱股份",
                "source": "test",
                "available": True,
                "pre_close": 20.0,
                "price": 19.2,
                "pct_chg": -4.0,
                "high": 20.3,
                "low": 19.1,
                "amount_yi": 3.1,
                "quote_date": "2024-01-25",
                "quote_time": "14:30:00",
            },
            "000003.SZ": {
                "ts_code": "000003.SZ",
                "name": "过热股份",
                "source": "test",
                "available": True,
                "pre_close": 30.0,
                "price": 31.8,
                "pct_chg": 6.0,
                "high": 32.0,
                "low": 30.5,
                "amount_yi": 4.2,
                "quote_date": "2024-01-25",
                "quote_time": "14:30:00",
            },
        }

    monkeypatch.setattr(realtime_quote, "sina_quotes", fake_quotes)

    response = client.get(
        "/api/recommendations/ml-late-session",
        params={"trade_date": "20240124", "limit": 5, "prediction_limit": 50},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["data_source"] == "ml_predictions+realtime"
    assert payload["count"] == 1
    assert payload["rows"][0]["ts_code"] == "000001.SZ"
    assert payload["rows"][0]["recommend_type"] == "模型尾盘"
    assert payload["rows"][0]["late_session"]["quote"]["price"] == 10.2
    assert payload["summary"]["prediction_count"] == 3
    assert payload["summary"]["accepted_count"] == 1
    assert payload["summary"]["model_reference"]["validation"]["f1"] == 0.57
    assert payload["summary"]["model_reference"]["ranking_validation"]["top50"]["hit_rate"] == 0.66
    assert payload["summary"]["model_reference"]["fit"]["log_loss_gap"] == 0.09
    assert payload["summary"]["rejected_counts"]["实时跌幅<-1%"] == 1
    assert payload["summary"]["rejected_counts"]["涨幅>4.2%过热"] == 1
