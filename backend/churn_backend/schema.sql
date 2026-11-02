CREATE TABLE IF NOT EXISTS batches (
    batch_id TEXT PRIMARY KEY,
    cutoff_month TEXT NOT NULL,
    source_kind TEXT NOT NULL,
    protocol_sha256 TEXT NOT NULL,
    record_count INTEGER NOT NULL,
    source_json TEXT NOT NULL,
    imported_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS predictions (
    prediction_id TEXT PRIMARY KEY,
    batch_id TEXT NOT NULL REFERENCES batches(batch_id),
    cus_id TEXT NOT NULL,
    risk REAL NOT NULL CHECK (risk >= 0 AND risk <= 1),
    review_alert INTEGER NOT NULL CHECK (review_alert IN (0,1)),
    evidence_json TEXT NOT NULL,
    features_json TEXT NOT NULL,
    customer_json TEXT NOT NULL,
    flows_json TEXT NOT NULL,
    UNIQUE (batch_id, cus_id)
);
CREATE TABLE IF NOT EXISTS reviews (
    prediction_id TEXT PRIMARY KEY REFERENCES predictions(prediction_id),
    version INTEGER NOT NULL,
    body_json TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS review_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    prediction_id TEXT NOT NULL REFERENCES predictions(prediction_id),
    version INTEGER NOT NULL,
    body_json TEXT NOT NULL,
    saved_at TEXT NOT NULL,
    UNIQUE (prediction_id, version)
);
CREATE TABLE IF NOT EXISTS actions (
    action_id TEXT PRIMARY KEY,
    prediction_id TEXT NOT NULL REFERENCES predictions(prediction_id),
    body_json TEXT NOT NULL,
    recorded_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_predictions_customer ON predictions(cus_id);
CREATE INDEX IF NOT EXISTS idx_batches_month ON batches(cutoff_month);
CREATE INDEX IF NOT EXISTS idx_actions_prediction ON actions(prediction_id);
