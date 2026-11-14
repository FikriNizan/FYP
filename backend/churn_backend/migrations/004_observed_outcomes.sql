CREATE TABLE observed_outcomes (
    prediction_id TEXT PRIMARY KEY REFERENCES predictions(prediction_id),
    outcome_month TEXT NOT NULL,
    observed_through TEXT NOT NULL,
    baseline_sum_cents INTEGER NOT NULL CHECK(baseline_sum_cents > 0),
    future_sum_cents INTEGER NOT NULL CHECK(future_sum_cents >= 0),
    target_churn INTEGER NOT NULL CHECK(target_churn IN (0,1)),
    future_flows_json TEXT NOT NULL,
    source_sha256 TEXT NOT NULL,
    imported_at TEXT NOT NULL
);
CREATE INDEX idx_outcomes_month ON observed_outcomes(outcome_month);
