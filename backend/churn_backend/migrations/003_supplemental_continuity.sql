CREATE TABLE supplemental_evidence (
    prediction_id TEXT PRIMARY KEY REFERENCES predictions(prediction_id),
    customer_json TEXT NOT NULL,
    flows_json TEXT NOT NULL,
    provenance_json TEXT NOT NULL,
    version INTEGER NOT NULL,
    applied_at TEXT NOT NULL
);
CREATE TABLE supplemental_history (
    prediction_id TEXT NOT NULL REFERENCES predictions(prediction_id),
    version INTEGER NOT NULL,
    customer_json TEXT NOT NULL,
    flows_json TEXT NOT NULL,
    provenance_json TEXT NOT NULL,
    applied_at TEXT NOT NULL,
    PRIMARY KEY(prediction_id,version)
);
CREATE TABLE review_case_links (
    prediction_id TEXT PRIMARY KEY REFERENCES predictions(prediction_id),
    case_id TEXT NOT NULL REFERENCES reviewed_cases(case_id),
    review_version INTEGER NOT NULL,
    linked_at TEXT NOT NULL
);
CREATE INDEX idx_review_case_links_case ON review_case_links(case_id);
