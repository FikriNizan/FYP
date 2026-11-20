CREATE TABLE ai_drafts (
 draft_id TEXT PRIMARY KEY,
 cache_key TEXT NOT NULL,
 purpose TEXT NOT NULL,
 record_id TEXT NOT NULL,
 evidence_hash TEXT NOT NULL,
 generated_at TEXT NOT NULL,
 provider TEXT NOT NULL,
 model TEXT NOT NULL,
 validation_version TEXT NOT NULL,
 content_json TEXT NOT NULL
);
CREATE INDEX ai_drafts_cache ON ai_drafts(cache_key, generated_at DESC);
CREATE TABLE ai_reservations (
 cache_key TEXT PRIMARY KEY,
 token TEXT NOT NULL,
 expires_at REAL NOT NULL
);
