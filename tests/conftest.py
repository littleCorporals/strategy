from __future__ import annotations

from collections.abc import Generator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def isolated_app(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Generator[tuple[TestClient, Path], None, None]:
    db_path = tmp_path / "market_cache.sqlite3"

    from app.clients import cninfo_client
    from app.core import config
    from app.db import cache as db_cache
    from app.main import create_app
    from app.services import market_data, model_pipeline

    monkeypatch.setattr(config, "DB_PATH", db_path)
    monkeypatch.setattr(db_cache, "DB_PATH", db_path)
    monkeypatch.setattr(model_pipeline, "MODEL_ARTIFACT_DIR", tmp_path / "models")
    db_cache._db_ready = False
    market_data._cache.clear()
    market_data._stock_basic_cache = None
    cninfo_client._stock_cache = None

    with TestClient(create_app()) as client:
        yield client, db_path

    market_data._cache.clear()
    market_data._stock_basic_cache = None
    cninfo_client._stock_cache = None
    db_cache._db_ready = False
