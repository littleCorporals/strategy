CREATE TABLE IF NOT EXISTS ml_model_events (
    event_id TEXT PRIMARY KEY,
    model_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    from_status TEXT,
    to_status TEXT,
    actor TEXT NOT NULL DEFAULT 'system',
    reason TEXT NOT NULL DEFAULT '',
    payload_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_ml_model_events_model_created
ON ml_model_events(model_id, created_at);

CREATE INDEX IF NOT EXISTS idx_ml_model_events_type_created
ON ml_model_events(event_type, created_at);
