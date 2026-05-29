PRAGMA journal_mode=WAL;

CREATE TABLE IF NOT EXISTS market_rows (
    interface TEXT NOT NULL,
    ts_code TEXT NOT NULL,
    trade_date TEXT NOT NULL,
    row_json TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (interface, ts_code, trade_date)
);

CREATE TABLE IF NOT EXISTS sync_state (
    interface TEXT NOT NULL,
    trade_date TEXT NOT NULL,
    scope TEXT NOT NULL,
    row_count INTEGER NOT NULL,
    source TEXT NOT NULL,
    fetched_at TEXT NOT NULL,
    PRIMARY KEY (interface, trade_date, scope)
);

CREATE TABLE IF NOT EXISTS cached_payloads (
    namespace TEXT NOT NULL,
    cache_key TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (namespace, cache_key)
);

CREATE INDEX IF NOT EXISTS idx_market_rows_interface_date
ON market_rows(interface, trade_date);

CREATE INDEX IF NOT EXISTS idx_market_rows_interface_code_date
ON market_rows(interface, ts_code, trade_date);

CREATE TABLE IF NOT EXISTS ml_models (
    model_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    status TEXT NOT NULL,
    model_type TEXT NOT NULL,
    feature_set TEXT NOT NULL,
    label_set TEXT NOT NULL,
    artifact_path TEXT,
    metrics_json TEXT NOT NULL,
    params_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    activated_at TEXT
);

CREATE TABLE IF NOT EXISTS ml_training_runs (
    run_id TEXT PRIMARY KEY,
    model_id TEXT,
    status TEXT NOT NULL,
    dataset_version TEXT NOT NULL,
    feature_set TEXT NOT NULL,
    label_set TEXT NOT NULL,
    train_start_date TEXT,
    train_end_date TEXT,
    sample_count INTEGER NOT NULL DEFAULT 0,
    metrics_json TEXT NOT NULL,
    params_json TEXT NOT NULL,
    notes TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    started_at TEXT,
    finished_at TEXT,
    error TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS ml_pipeline_runs (
    pipeline_id TEXT PRIMARY KEY,
    pipeline_type TEXT NOT NULL,
    status TEXT NOT NULL,
    trade_date TEXT,
    payload_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    started_at TEXT,
    finished_at TEXT,
    error TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS ml_predictions (
    model_id TEXT NOT NULL,
    trade_date TEXT NOT NULL,
    ts_code TEXT NOT NULL,
    probability REAL NOT NULL,
    ml_score REAL NOT NULL,
    features_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (model_id, trade_date, ts_code)
);

CREATE TABLE IF NOT EXISTS ml_validation_results (
    model_id TEXT NOT NULL,
    trade_date TEXT NOT NULL,
    ts_code TEXT NOT NULL,
    label_value INTEGER NOT NULL,
    next_trade_date TEXT NOT NULL,
    next_close_pct REAL,
    next_high_pct REAL,
    result_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (model_id, trade_date, ts_code)
);

CREATE INDEX IF NOT EXISTS idx_ml_training_runs_created
ON ml_training_runs(created_at);

CREATE INDEX IF NOT EXISTS idx_ml_pipeline_runs_created
ON ml_pipeline_runs(created_at);

CREATE INDEX IF NOT EXISTS idx_ml_predictions_date
ON ml_predictions(trade_date, model_id);
