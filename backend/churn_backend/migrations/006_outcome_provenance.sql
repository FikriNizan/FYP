-- Milestone 8 (final refinement, Phase B): outcome provenance. Existing rows keep NULL, meaning the
-- trusted research file loaded by flask load-outcomes. Package-derived rows record the published batches.
ALTER TABLE observed_outcomes ADD COLUMN source_kind TEXT;
ALTER TABLE observed_outcomes ADD COLUMN source_batches_json TEXT
