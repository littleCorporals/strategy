from __future__ import annotations

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
    assert Path(payload["database"]["path"]) == db_path
    assert db_path.exists()

    from app.db import cache as db_cache

    with db_cache.connect() as conn:
        versions = [row["version"] for row in conn.execute("SELECT version FROM schema_migrations")]

    assert "0001_initial_schema" in versions


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
    assert payload["model"]["artifact_path"]
    assert Path(payload["model"]["artifact_path"]).exists()
    assert Path(payload["model"]["artifact_path"]).is_relative_to(db_path.parent)
    assert payload["pipeline"]["status"] == "completed"


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

    summaries = client.get("/api/admin/predictions", params={"trade_date": "20240109"}).json()["items"]
    performance = client.get("/api/admin/performance", params={"trade_date": "20240109"}).json()["items"]
    model_performance = client.get("/api/admin/model-performance").json()["items"]
    assert summaries[0]["count"] == 3
    assert performance[0]["count"] == 3
    assert model_performance[0]["model_id"] == model_id
    assert model_performance[0]["prediction_count"] == 3
    assert model_performance[0]["validation_count"] == 3
    assert model_performance[0]["hit_rate"] is not None


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
