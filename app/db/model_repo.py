from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Any

from app.db.cache import connect, ensure


MODEL_STATUSES = {"candidate", "approved", "rejected", "active", "inactive", "archived"}
ACTIVATABLE_STATUSES = {"approved", "inactive"}


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _row_to_dict(row: Any) -> dict[str, Any]:
    data = dict(row)
    for key in ("metrics_json", "params_json", "payload_json", "features_json", "result_json"):
        if key in data:
            data[key.removesuffix("_json")] = json.loads(data.pop(key) or "{}")
    return data


def _event_id() -> str:
    return f"evt_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"


def _insert_model_event_sync(
    conn: Any,
    *,
    model_id: str,
    event_type: str,
    from_status: str | None,
    to_status: str | None,
    actor: str = "system",
    reason: str = "",
    payload: dict[str, Any] | None = None,
) -> None:
    conn.execute(
        """
        INSERT INTO ml_model_events(
            event_id, model_id, event_type, from_status, to_status,
            actor, reason, payload_json, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            _event_id(),
            model_id,
            event_type,
            from_status,
            to_status,
            actor,
            reason,
            json.dumps(payload or {}, ensure_ascii=False),
            _now(),
        ),
    )


async def list_model_events(model_id: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
    await ensure()
    params: list[Any] = []
    where = ""
    if model_id:
        where = "WHERE model_id = ?"
        params.append(model_id)
    params.append(limit)
    with connect() as conn:
        rows = conn.execute(
            f"""
            SELECT *
            FROM ml_model_events
            {where}
            ORDER BY created_at DESC
            LIMIT ?
            """,
            params,
        ).fetchall()
    return [_row_to_dict(row) for row in rows]


async def list_models() -> list[dict[str, Any]]:
    await ensure()
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT *
            FROM ml_models
            ORDER BY activated_at DESC, created_at DESC
            """
        ).fetchall()
    return [_row_to_dict(row) for row in rows]


async def active_model() -> dict[str, Any] | None:
    await ensure()
    with connect() as conn:
        row = conn.execute(
            """
            SELECT *
            FROM ml_models
            WHERE status = 'active'
            ORDER BY activated_at DESC
            LIMIT 1
            """
        ).fetchone()
    return _row_to_dict(row) if row else None


async def get_model(model_id: str) -> dict[str, Any] | None:
    await ensure()
    with connect() as conn:
        row = conn.execute("SELECT * FROM ml_models WHERE model_id = ?", (model_id,)).fetchone()
    return _row_to_dict(row) if row else None


async def create_model(payload: dict[str, Any]) -> dict[str, Any]:
    await ensure()
    now = _now()
    model_id = payload.get("model_id") or f"model_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
    status = str(payload.get("status") or "candidate")
    if status not in MODEL_STATUSES:
        status = "candidate"
    if status == "active":
        status = "candidate"
    row = {
        "model_id": model_id,
        "name": payload.get("name") or model_id,
        "status": status,
        "model_type": payload.get("model_type") or "supervised_time_series",
        "feature_set": payload.get("feature_set") or "short_swing_v2",
        "label_set": payload.get("label_set") or "next_high_3pct_v1",
        "artifact_path": payload.get("artifact_path"),
        "metrics_json": json.dumps(payload.get("metrics") or {}, ensure_ascii=False),
        "params_json": json.dumps(payload.get("params") or {}, ensure_ascii=False),
        "created_at": now,
        "activated_at": None,
    }
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO ml_models(
                model_id, name, status, model_type, feature_set, label_set,
                artifact_path, metrics_json, params_json, created_at, activated_at
            )
            VALUES (
                :model_id, :name, :status, :model_type, :feature_set, :label_set,
                :artifact_path, :metrics_json, :params_json, :created_at, :activated_at
            )
            """,
            row,
        )
        _insert_model_event_sync(
            conn,
            model_id=model_id,
            event_type="registered",
            from_status=None,
            to_status=status,
            reason=str(payload.get("reason") or ""),
            payload={
                "name": row["name"],
                "model_type": row["model_type"],
                "feature_set": row["feature_set"],
                "label_set": row["label_set"],
            },
        )
        conn.commit()
    return await get_model(model_id) or {"model_id": model_id}


async def activate_model(model_id: str) -> bool:
    await ensure()
    now = _now()
    with connect() as conn:
        target = conn.execute(
            "SELECT status FROM ml_models WHERE model_id = ?",
            (model_id,),
        ).fetchone()
        if not target:
            return False
        if str(target["status"]) not in ACTIVATABLE_STATUSES:
            return False
        active_rows = conn.execute("SELECT model_id, status FROM ml_models WHERE status = 'active'").fetchall()
        conn.execute("UPDATE ml_models SET status = 'inactive', activated_at = NULL WHERE status = 'active'")
        for active in active_rows:
            _insert_model_event_sync(
                conn,
                model_id=str(active["model_id"]),
                event_type="superseded",
                from_status=str(active["status"]),
                to_status="inactive",
                payload={"activated_model_id": model_id},
            )
        conn.execute(
            "UPDATE ml_models SET status = 'active', activated_at = ? WHERE model_id = ?",
            (now, model_id),
        )
        _insert_model_event_sync(
            conn,
            model_id=model_id,
            event_type="activated",
            from_status=str(target["status"]),
            to_status="active",
        )
        conn.commit()
    return True


async def approve_model(model_id: str, reason: str = "") -> bool:
    await ensure()
    with connect() as conn:
        model = conn.execute("SELECT status FROM ml_models WHERE model_id = ?", (model_id,)).fetchone()
        if not model:
            return False
        from_status = str(model["status"])
        if from_status not in {"candidate", "rejected"}:
            return False
        conn.execute("UPDATE ml_models SET status = 'approved', activated_at = NULL WHERE model_id = ?", (model_id,))
        _insert_model_event_sync(
            conn,
            model_id=model_id,
            event_type="approved",
            from_status=from_status,
            to_status="approved",
            reason=reason,
        )
        conn.commit()
    return True


async def reject_model(model_id: str, reason: str = "") -> bool:
    await ensure()
    with connect() as conn:
        model = conn.execute("SELECT status FROM ml_models WHERE model_id = ?", (model_id,)).fetchone()
        if not model:
            return False
        from_status = str(model["status"])
        if from_status not in {"candidate", "approved"}:
            return False
        conn.execute("UPDATE ml_models SET status = 'rejected', activated_at = NULL WHERE model_id = ?", (model_id,))
        _insert_model_event_sync(
            conn,
            model_id=model_id,
            event_type="rejected",
            from_status=from_status,
            to_status="rejected",
            reason=reason,
        )
        conn.commit()
    return True


async def deactivate_model(model_id: str) -> bool:
    await ensure()
    with connect() as conn:
        model = conn.execute("SELECT status FROM ml_models WHERE model_id = ?", (model_id,)).fetchone()
        if not model:
            return False
        conn.execute(
            "UPDATE ml_models SET status = 'inactive', activated_at = NULL WHERE model_id = ?",
            (model_id,),
        )
        _insert_model_event_sync(
            conn,
            model_id=model_id,
            event_type="deactivated",
            from_status=str(model["status"]),
            to_status="inactive",
        )
        conn.commit()
    return True


async def archive_model(model_id: str) -> bool:
    await ensure()
    with connect() as conn:
        model = conn.execute("SELECT status FROM ml_models WHERE model_id = ?", (model_id,)).fetchone()
        if not model:
            return False
        conn.execute(
            "UPDATE ml_models SET status = 'archived', activated_at = NULL WHERE model_id = ?",
            (model_id,),
        )
        _insert_model_event_sync(
            conn,
            model_id=model_id,
            event_type="archived",
            from_status=str(model["status"]),
            to_status="archived",
        )
        conn.commit()
    return True


async def rollback_active_model(reason: str = "") -> dict[str, Any] | None:
    await ensure()
    now = _now()
    with connect() as conn:
        active = conn.execute(
            """
            SELECT model_id, status
            FROM ml_models
            WHERE status = 'active'
            ORDER BY activated_at DESC
            LIMIT 1
            """
        ).fetchone()
        target = conn.execute(
            """
            SELECT m.model_id, m.status
            FROM ml_models m
            JOIN ml_model_events e ON e.model_id = m.model_id
            WHERE m.status = 'inactive'
              AND e.event_type = 'superseded'
            ORDER BY e.created_at DESC
            LIMIT 1
            """
        ).fetchone()
        if not target:
            target = conn.execute(
                """
                SELECT model_id, status
                FROM ml_models
                WHERE status = 'inactive'
                ORDER BY created_at DESC
                LIMIT 1
                """
            ).fetchone()
        if not target:
            return None
        if active:
            conn.execute(
                "UPDATE ml_models SET status = 'inactive', activated_at = NULL WHERE model_id = ?",
                (active["model_id"],),
            )
            _insert_model_event_sync(
                conn,
                model_id=str(active["model_id"]),
                event_type="rollback_from",
                from_status=str(active["status"]),
                to_status="inactive",
                reason=reason,
                payload={"rollback_to": str(target["model_id"])},
            )
        conn.execute(
            "UPDATE ml_models SET status = 'active', activated_at = ? WHERE model_id = ?",
            (now, target["model_id"]),
        )
        _insert_model_event_sync(
            conn,
            model_id=str(target["model_id"]),
            event_type="rollback_to",
            from_status=str(target["status"]),
            to_status="active",
            reason=reason,
            payload={"rollback_from": str(active["model_id"]) if active else None},
        )
        conn.commit()
    return await active_model()


async def update_model_artifact(model_id: str, artifact_path: str) -> dict[str, Any] | None:
    await ensure()
    with connect() as conn:
        exists = conn.execute("SELECT 1 FROM ml_models WHERE model_id = ?", (model_id,)).fetchone()
        if not exists:
            return None
        conn.execute(
            "UPDATE ml_models SET artifact_path = ? WHERE model_id = ?",
            (artifact_path, model_id),
        )
        _insert_model_event_sync(
            conn,
            model_id=model_id,
            event_type="artifact_updated",
            from_status=None,
            to_status=None,
            payload={"artifact_path": artifact_path},
        )
        conn.commit()
    return await get_model(model_id)


async def update_training_run(
    run_id: str,
    *,
    status: str | None = None,
    model_id: str | None = None,
    sample_count: int | None = None,
    metrics: dict[str, Any] | None = None,
    error: str | None = None,
    started: bool = False,
    finished: bool = False,
) -> dict[str, Any] | None:
    await ensure()
    now = _now()
    assignments: list[str] = []
    params: dict[str, Any] = {"run_id": run_id}
    if status is not None:
        assignments.append("status = :status")
        params["status"] = status
    if model_id is not None:
        assignments.append("model_id = :model_id")
        params["model_id"] = model_id
    if sample_count is not None:
        assignments.append("sample_count = :sample_count")
        params["sample_count"] = sample_count
    if metrics is not None:
        assignments.append("metrics_json = :metrics_json")
        params["metrics_json"] = json.dumps(metrics, ensure_ascii=False)
    if error is not None:
        assignments.append("error = :error")
        params["error"] = error
    if started:
        assignments.append("started_at = :started_at")
        params["started_at"] = now
    if finished:
        assignments.append("finished_at = :finished_at")
        params["finished_at"] = now
    if not assignments:
        return await get_training_run(run_id)
    with connect() as conn:
        conn.execute(
            f"UPDATE ml_training_runs SET {', '.join(assignments)} WHERE run_id = :run_id",
            params,
        )
        conn.commit()
    return await get_training_run(run_id)


async def create_training_run(payload: dict[str, Any]) -> dict[str, Any]:
    await ensure()
    now = _now()
    run_id = f"train_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
    row = {
        "run_id": run_id,
        "model_id": payload.get("model_id"),
        "status": "queued",
        "dataset_version": payload.get("dataset_version") or "market_cache_v1",
        "feature_set": payload.get("feature_set") or "short_swing_v2",
        "label_set": payload.get("label_set") or "next_high_3pct_v1",
        "train_start_date": payload.get("train_start_date"),
        "train_end_date": payload.get("train_end_date"),
        "sample_count": 0,
        "metrics_json": json.dumps({}, ensure_ascii=False),
        "params_json": json.dumps(payload.get("params") or {}, ensure_ascii=False),
        "notes": payload.get("notes") or "",
        "created_at": now,
        "started_at": None,
        "finished_at": None,
        "error": "",
    }
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO ml_training_runs(
                run_id, model_id, status, dataset_version, feature_set, label_set,
                train_start_date, train_end_date, sample_count, metrics_json,
                params_json, notes, created_at, started_at, finished_at, error
            )
            VALUES (
                :run_id, :model_id, :status, :dataset_version, :feature_set, :label_set,
                :train_start_date, :train_end_date, :sample_count, :metrics_json,
                :params_json, :notes, :created_at, :started_at, :finished_at, :error
            )
            """,
            row,
        )
        conn.commit()
    return await get_training_run(run_id) or {"run_id": run_id}


async def get_training_run(run_id: str) -> dict[str, Any] | None:
    await ensure()
    with connect() as conn:
        row = conn.execute("SELECT * FROM ml_training_runs WHERE run_id = ?", (run_id,)).fetchone()
    return _row_to_dict(row) if row else None


async def list_training_runs(limit: int = 30) -> list[dict[str, Any]]:
    await ensure()
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT *
            FROM ml_training_runs
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [_row_to_dict(row) for row in rows]


async def list_pipeline_runs(limit: int = 30) -> list[dict[str, Any]]:
    await ensure()
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT *
            FROM ml_pipeline_runs
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [_row_to_dict(row) for row in rows]


async def create_pipeline_run(payload: dict[str, Any]) -> dict[str, Any]:
    await ensure()
    now = _now()
    pipeline_id = payload.get("pipeline_id") or f"pipe_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
    row = {
        "pipeline_id": pipeline_id,
        "pipeline_type": payload.get("pipeline_type") or "training",
        "status": payload.get("status") or "completed",
        "trade_date": payload.get("trade_date"),
        "payload_json": json.dumps(payload.get("payload") or {}, ensure_ascii=False),
        "created_at": now,
        "started_at": payload.get("started_at") or now,
        "finished_at": payload.get("finished_at") or now,
        "error": payload.get("error") or "",
    }
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO ml_pipeline_runs(
                pipeline_id, pipeline_type, status, trade_date, payload_json,
                created_at, started_at, finished_at, error
            )
            VALUES (
                :pipeline_id, :pipeline_type, :status, :trade_date, :payload_json,
                :created_at, :started_at, :finished_at, :error
            )
            """,
            row,
        )
        conn.commit()
    with connect() as conn:
        stored = conn.execute("SELECT * FROM ml_pipeline_runs WHERE pipeline_id = ?", (pipeline_id,)).fetchone()
    return _row_to_dict(stored) if stored else {"pipeline_id": pipeline_id}


async def save_predictions(model_id: str, trade_date: str, rows: list[dict[str, Any]]) -> None:
    await ensure()
    now = _now()
    with connect() as conn:
        for row in rows:
            conn.execute(
                """
                INSERT INTO ml_predictions(
                    model_id, trade_date, ts_code, probability, ml_score, features_json, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(model_id, trade_date, ts_code)
                DO UPDATE SET
                    probability = excluded.probability,
                    ml_score = excluded.ml_score,
                    features_json = excluded.features_json,
                    created_at = excluded.created_at
                """,
                (
                    model_id,
                    trade_date,
                    row["ts_code"],
                    float(row["probability"]),
                    float(row["ml_score"]),
                    json.dumps(row.get("features") or {}, ensure_ascii=False),
                    now,
                ),
            )
        conn.commit()


async def list_predictions(model_id: str, trade_date: str) -> list[dict[str, Any]]:
    await ensure()
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT *
            FROM ml_predictions
            WHERE model_id = ? AND trade_date = ?
            ORDER BY probability DESC, ml_score DESC
            """,
            (model_id, trade_date),
        ).fetchall()
    return [_row_to_dict(row) for row in rows]


async def save_validation_results(model_id: str, trade_date: str, rows: list[dict[str, Any]]) -> None:
    await ensure()
    now = _now()
    with connect() as conn:
        for row in rows:
            conn.execute(
                """
                INSERT INTO ml_validation_results(
                    model_id, trade_date, ts_code, label_value, next_trade_date,
                    next_close_pct, next_high_pct, result_json, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(model_id, trade_date, ts_code)
                DO UPDATE SET
                    label_value = excluded.label_value,
                    next_trade_date = excluded.next_trade_date,
                    next_close_pct = excluded.next_close_pct,
                    next_high_pct = excluded.next_high_pct,
                    result_json = excluded.result_json,
                    created_at = excluded.created_at
                """,
                (
                    model_id,
                    trade_date,
                    row["ts_code"],
                    int(row["label_value"]),
                    row["next_trade_date"],
                    row.get("next_close_pct"),
                    row.get("next_high_pct"),
                    json.dumps(row.get("result") or {}, ensure_ascii=False),
                    now,
                ),
            )
        conn.commit()


async def prediction_summary(trade_date: str | None = None) -> dict[str, Any]:
    await ensure()
    params: list[Any] = []
    where = ""
    if trade_date:
        where = "WHERE trade_date = ?"
        params.append(trade_date)
    with connect() as conn:
        rows = conn.execute(
            f"""
            SELECT model_id, trade_date, COUNT(*) AS count, AVG(probability) AS avg_probability
            FROM ml_predictions
            {where}
            GROUP BY model_id, trade_date
            ORDER BY trade_date DESC, model_id
            LIMIT 50
            """,
            params,
        ).fetchall()
    return {"items": [dict(row) for row in rows]}


async def latest_prediction_trade_date(model_id: str | None = None) -> str | None:
    await ensure()
    dates = await recent_prediction_trade_dates(model_id=model_id, limit=1)
    return dates[0] if dates else None


async def recent_prediction_trade_dates(model_id: str | None = None, limit: int = 30) -> list[str]:
    await ensure()
    params: list[Any] = []
    where = ""
    if model_id:
        where = "WHERE model_id = ?"
        params.append(model_id)
    params.append(limit)
    with connect() as conn:
        rows = conn.execute(
            f"""
            SELECT trade_date
            FROM ml_predictions
            {where}
            GROUP BY trade_date
            ORDER BY trade_date DESC
            LIMIT ?
            """,
            params,
        ).fetchall()
    return [str(row["trade_date"]) for row in rows if row["trade_date"]]


async def validation_summary(trade_date: str | None = None) -> dict[str, Any]:
    await ensure()
    params: list[Any] = []
    where = ""
    if trade_date:
        where = "WHERE trade_date = ?"
        params.append(trade_date)
    with connect() as conn:
        rows = conn.execute(
            f"""
            SELECT
                model_id,
                trade_date,
                COUNT(*) AS count,
                AVG(label_value) AS hit_rate,
                AVG(next_close_pct) AS avg_next_close_pct,
                AVG(next_high_pct) AS avg_next_high_pct
            FROM ml_validation_results
            {where}
            GROUP BY model_id, trade_date
            ORDER BY trade_date DESC, model_id
            LIMIT 50
            """,
            params,
        ).fetchall()
    return {"items": [dict(row) for row in rows]}


async def latest_validation_payload(model_id: str | None = None) -> dict[str, Any] | None:
    await ensure()
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT payload_json
            FROM ml_pipeline_runs
            WHERE pipeline_type = 'validation'
              AND status = 'completed'
            ORDER BY trade_date DESC, created_at DESC
            LIMIT 100
            """
        ).fetchall()
    for row in rows:
        payload = json.loads(row["payload_json"] or "{}")
        if model_id and str(payload.get("model_id") or "") != str(model_id):
            continue
        return payload
    return None


async def model_performance_overview() -> dict[str, Any]:
    await ensure()
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT
                m.model_id,
                m.name,
                m.status,
                m.feature_set,
                m.label_set,
                COUNT(DISTINCT p.trade_date || ':' || p.ts_code) AS prediction_count,
                COUNT(DISTINCT v.trade_date || ':' || v.ts_code) AS validation_count,
                AVG(v.label_value) AS hit_rate,
                AVG(v.next_close_pct) AS avg_next_close_pct,
                AVG(v.next_high_pct) AS avg_next_high_pct,
                MAX(v.trade_date) AS latest_validation_date
            FROM ml_models m
            LEFT JOIN ml_predictions p ON p.model_id = m.model_id
            LEFT JOIN ml_validation_results v ON v.model_id = m.model_id
            GROUP BY m.model_id
            ORDER BY m.status = 'active' DESC, latest_validation_date DESC, m.created_at DESC
            """
        ).fetchall()
        ranking_rows = conn.execute(
            """
            SELECT p1.payload_json
            FROM ml_pipeline_runs p1
            WHERE p1.pipeline_type = 'validation'
              AND p1.status = 'completed'
            ORDER BY p1.trade_date DESC, p1.created_at DESC
            """
        ).fetchall()
    latest_rankings: dict[str, dict[str, Any]] = {}
    for row in ranking_rows:
        payload = json.loads(row["payload_json"] or "{}")
        model_id = str(payload.get("model_id") or "")
        ranking = payload.get("ranking")
        if model_id and isinstance(ranking, dict) and model_id not in latest_rankings:
            latest_rankings[model_id] = ranking
    items: list[dict[str, Any]] = []
    for row in rows:
        item = dict(row)
        for key in ("hit_rate", "avg_next_close_pct", "avg_next_high_pct"):
            item[key] = round(float(item[key]), 4) if item[key] is not None else None
        item["ranking"] = latest_rankings.get(str(item["model_id"]))
        items.append(item)
    return {"items": items}
