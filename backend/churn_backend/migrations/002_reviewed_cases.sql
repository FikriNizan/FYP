CREATE TABLE reviewed_cases (
    case_id TEXT PRIMARY KEY,
    prediction_id TEXT NOT NULL UNIQUE REFERENCES predictions(prediction_id),
    original_review_json TEXT NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('open','deferred','closed')),
    owner TEXT NOT NULL,
    next_action_date TEXT,
    version INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
INSERT INTO reviewed_cases
SELECT r.prediction_id, r.prediction_id,
       COALESCE((SELECT h.body_json FROM review_history h WHERE h.prediction_id=r.prediction_id ORDER BY h.version LIMIT 1), r.body_json),
       'open', COALESCE(json_extract(r.body_json,'$.owner'),''), json_extract(r.body_json,'$.next_action_date'), 1,
       COALESCE((SELECT h.saved_at FROM review_history h WHERE h.prediction_id=r.prediction_id ORDER BY h.version LIMIT 1),r.updated_at), r.updated_at
FROM reviews r;
CREATE TABLE case_events (
    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
    case_id TEXT NOT NULL REFERENCES reviewed_cases(case_id),
    version INTEGER NOT NULL,
    body_json TEXT NOT NULL,
    recorded_at TEXT NOT NULL,
    UNIQUE(case_id,version)
);
INSERT INTO case_events(case_id,version,body_json,recorded_at)
SELECT case_id,1,json_object('kind','case_created','status','open','recorded_by',COALESCE(json_extract(original_review_json,'$.reviewer'),'Unknown'),'notes','Existing review preserved during migration.'),created_at FROM reviewed_cases;
CREATE TABLE follow_ups (
    follow_up_id TEXT PRIMARY KEY,
    case_id TEXT NOT NULL REFERENCES reviewed_cases(case_id),
    action_type TEXT NOT NULL,
    planned_date TEXT,
    created_at TEXT NOT NULL
);
CREATE TABLE follow_up_events (
    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
    follow_up_id TEXT NOT NULL REFERENCES follow_ups(follow_up_id),
    body_json TEXT NOT NULL,
    recorded_at TEXT NOT NULL
);
CREATE INDEX idx_follow_ups_case ON follow_ups(case_id);
CREATE INDEX idx_follow_up_events_task ON follow_up_events(follow_up_id,event_id);
