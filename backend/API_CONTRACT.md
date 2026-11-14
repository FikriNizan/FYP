> Full-stack foundation v0.3.0: `/` serves the built React dashboard from `frontend/dist`; `/api` serves the API index. The evidence/review/action API contracts below are retained from backend v1.

# Backend API contract — v0.3.0

Base URL: `http://127.0.0.1:5000`. All `/api` responses are JSON. No endpoint fits or recalibrates a model.

## Evidence selection

Evidence endpoints accept `month=YYYY-MM` or a full month-end date, and optional `batch_id`. Without a selection, use the latest imported month, preferring a full export over a case sample. When both are supplied they must agree. A missing batch/month returns 404; an invalid selection returns 422.

`/api/months` returns one entry per preserved batch, including its month, source kind, count, protocol identity and provenance. Source kinds are `notebook_case_sample`, `saved_shap_export` and `prepared_month_scored`. The latter is freshly scored from uploaded prepared features, not an archived score import. Display the sample label when applicable; a sample count must never be presented as the full portfolio.

## Routes

| Method | Route | Response |
|---|---|---|
| GET | `/` | Browser dashboard (HTML) |
| GET | `/api` | API index and server version |
| GET | `/api/health` | Server version and number of batches |
| GET | `/api/metadata` | Decision/action enums, timezone and milestone capabilities |
| GET | `/api/months` | `items`: imported batches |
| POST | `/api/assessments` | Validate, freshly score, verify and atomically publish a prepared month; 201 new / 200 repeat |
| GET | `/api/summary` | Population, flagged counts, review counts, finance totals and coverage |
| GET | `/api/monitoring` | Outcome coverage, descriptive delivery groups, saved-risk metrics and earlier-batch input movement |
| GET | `/api/customers` | Filtered/paginated `items`, batch, total, limit, offset |
| GET | `/api/customers/<cus_id>` | Batch and detailed customer evidence |
| GET | `/api/customers/<cus_id>/history` | Imported monthly snapshots through the selected month |
| PUT | `/api/predictions/<prediction_id>/review` | Saved review with new version |
| GET | `/api/predictions/<prediction_id>/review-history` | All saved review versions |
| POST | `/api/predictions/<prediction_id>/actions` | New action note, HTTP 201 |
| GET | `/api/predictions/<prediction_id>/actions` | Dated notes for that prediction |

Customer listing filters: `q` matches ID/name, `flagged=true|false`, `decision=awaiting_review|prioritise|monitor|no_immediate_action` for that exact prediction's review, and `workflow=needs_review` for flagged first reviews or reassessments without an active case. `limit` defaults to 100 and permits 1–1,000; `offset` defaults to 0. Results are sorted by full-precision risk descending, then customer ID. `total` is the filtered count before pagination. Summary totals are for the complete selected batch, not the current filtered page.

## Prepared monthly publication

`POST /api/assessments` accepts exactly two multipart files named `features` (CSV) and `manifest` (JSON); no other files or form fields. It does not accept saved predictions, a model, scripts or a verification report. Raw upload bytes are checked against the manifest before exact ordered-schema parsing. CSV limit is 5 MiB; manifest limit 64 KiB, with 512 KiB multipart overhead. Existing human-note routes keep their 64 KiB limit and all writes retain same-origin enforcement.

The strict manifest requires `kind`, `package_version`, `cutoff_month`, `row_count`, `predictor_count`, `feature_version`, `feature_schema_sha256`, `protocol_sha256`, `files` and opaque `source` provenance. Kind/version are `txb_prepared_month`/`1.0.0`. The frozen application schema and protocol must match; `files` describes only `features.csv` with exact `bytes` and SHA-256. The server requires 1,000 unique customers by default (`TXB_MONTHLY_POPULATION`, administrator controlled). CSV columns must be the two keys and 78 predictors in frozen order; IDs/categories are strings, empty values are missing, finite numeric zero is retained, and twelve-month combined flow must be positive. Every cutoff must equal the manifest month-end.

Success JSON has `batch_id`, `cutoff_month`, `records`, `already_imported` and `timings`; new publications also report optional `enrichment` status/coverage. New publication returns 201/false; an identical byte-level package with the same frozen policy returns 200/true and the original batch ID without scoring. Open the dashboard using that exact batch ID. A different valid package at an occupied cutoff returns 409 `assessment_conflict`; there is no replacement operation. Failed scoring runs publish nothing. Processing occurs outside the atomic publication transaction, which rechecks cutoff occupancy under a SQLite write lock.

Validation returns 422 `validation_failed`; excessive request size 413; cross-origin write 403. Scoring configuration/artifact/process/verification failure returns 503 (`scoring_unavailable` or `scoring_failed`), a concurrent scorer in this process 503 `scoring_busy`, and timeout 504 `scoring_timeout`. Error messages are safe for display; local diagnostics do not appear in responses. Connection loss does not imply rollback: reload saved assessments or safely resubmit the unchanged files.

Fresh batches use `prepared_month_scored` with hashes/versions, champion identity, original manifest/provenance, scorer checks and timings in `source`. The original received CSV is used unchanged for scoring in a temporary directory, not retained as a public file. Required package content has no names or flow-history rows. Trusted optional customer/flow sources may add separately versioned supporting evidence after publication; when unavailable, names remain null and monthly history empty. A source error never changes the published scores. Prior cases keep their original anchored prediction/review while the latest assessment can advance. No outcomes are inferred.

`/api/metadata` adds `prepared_month_scoring=true` and `scoring_configured` (settings present, not a health check); the retained `live_model_scoring=false` refers to absence of live/streaming bank scoring. Optional configuration, trusted fingerprints, Windows setup and measured historical acceptance are in [MILESTONE_4.md](../docs/MILESTONE_4.md). Historical import CLI/read APIs remain supported without scorer configuration.

`review_alert` identifies the frozen model flag. Review decisions are human records and never substitute for that flag. Risk is a 0–1 probability; the frontend may format it as a percentage. It must use the saved flag, not recompute it from a rounded percentage.

## Detail response

`customer` contains `prediction_id`, `batch_id`, `cus_id`, `cutoff_month`, nullable customer/profile fields, `calibrated_risk`, `review_alert`, `probability_cutoff`, `review`, `workflow`, `finance`, `operations`, `features`, `feature_count`, `explanation`, `flow_history`, `actions`, optional `supplemental_provenance`, `observed_outcome` and the assessment-window end date.

The `explanation` is the exact saved v1 dashboard record: base, signed drivers, omitted-feature sum and clipping adjustment reconstruct calibrated risk. Values are calibrated log-odds, not probability percentage-point effects. SHAP explains the model, not the customer's confirmed cause.

`finance` fields:

| API field | Original predictor |
|---|---|
| `estimated_monthly_fee_myr` | `estimated_fee_mean_3m_myr` |
| `estimated_monthly_waiver_myr` | `estimated_waiver_mean_3m_myr` |
| `fd_balance_myr` | `fd_balance_myr` |
| `non_fd_balance_myr` | `non_fd_balance_myr` |

Fee/waiver estimates are historical mean monthly amounts over three months. They are not actual monthly invoices, net profitability or proven lost revenue. Balance amounts are exposures. Unknown values remain JSON null. Summary finance totals have `total`, `records_with_value` and `records` for both all customers and flagged customers; label partial coverage where counts differ.

`flow_history` holds up to twelve cutoff-safe monthly flow observations when loaded. Snapshot history only includes imported prediction months. Old snapshot evidence stays immutable; each snapshot has its own review. Current-month history respects the explicitly selected batch version.

Until an outcome is explicitly imported, `actual_attrition=null`, `observed_outcome=null` and `outcome_status=not_loaded`. For a fully observed and imported horizon, `actual_attrition` is the saved Boolean volume-drop result, `outcome_status=observed`, and `observed_outcome` contains the three-month window end, source-observed-through month, separate baseline/future averages, three future monthly flows and source SHA-256. These never revise the prediction, model flag, review or case. The pre-cutoff `flow_history` never includes future outcome months.

## Mature outcome import and monitoring

`flask --app app load-outcomes --batch-id ID --observed-through YYYY-MM-DD` previews a trusted recorded-flow import; add `--apply` to publish after checking coverage. This is an **administrator CLI**, not a dashboard upload. `TXB_RESEARCH_ROOT` selects the trusted research tree; the fixed file is `data/final_v4_0_1/cleaned/monthly_flows.csv` with its accepted `cleaned_manifest.json`. Import requires a complete twelve-month baseline and all next three complete customer-month flows by the declared observed-through date. It validates source hash, row shape, duplicate keys, cents reconciliation and the saved baseline, then saves each mature outcome under its prediction ID in one transaction. Missing/incomplete months remain unavailable. A repeated same-source import changes zero rows; conflicting accepted evidence is rejected. See [Milestone 5](../docs/MILESTONE_5.md).

`GET /api/monitoring?batch_id=ID` returns `outcome_month`, prediction count, `outcome_coverage` (`loaded`, `unavailable`, `documented_delivery`, `without_recorded_delivery`), `observed_all`, two descriptive delivery-group metric objects, delivered type counts and `drift`. Group metrics have records, positives, observed rate, mean saved calibrated risk, Brier score, flagged count and flagged-positive share; rates/scores are JSON null when their denominator is absent. Delivery is derived from saved linked follow-up events with status `delivered`, a named type (RM visit, customer contact or service fix) and action date inside that prediction's future window. Plans/attempts/legacy notes do not count. No recorded delivery is **not** a verified untreated control. `drift` compares the nearest earlier batch under the same protocol, with saved risk/flag rates and per-feature availability/medians or category total-variation; it is null if no earlier batch exists. No live outcome feed, causal estimate or automatic retraining is implied.

## Review body

```json
{
  "decision": "prioritise",
  "reason": "Investigate the recorded change in usage.",
  "operations_notes": "Confirm whether service friction was experienced.",
  "finance_notes": "Review available fee estimates.",
  "owner": "Example RM",
  "next_action_date": "2026-10-20",
  "reviewer": "Example reviewer",
  "expected_version": 0
}
```

Required: decision, non-empty reason, non-empty reviewer and expected_version. Text notes are limited to 4,000 characters; owner/reviewer to 200. The next-action date is optional (`null` or YYYY-MM-DD). The initial review has version 0 and decision `awaiting_review`. Saved records increment the version. HTTP 409 means another save changed the review; fetch its latest version before deciding again. PUT replaces editable fields; send all notes you want retained.

`reviewer` is user-entered attribution in this local milestone, not an authenticated bank identity. Returned timestamps are UTC ISO 8601; format them in Asia/Kuala_Lumpur in the frontend. Calendar dates are preserved as entered.

## Action body

```json
{
  "action_type": "rm_visit",
  "action_status": "planned",
  "action_date": "2026-10-20",
  "notes": "Prepare questions about usage and service friction.",
  "recorded_by": "Example RM"
}
```

All fields are required. An action is append-only, linked to a particular prediction/customer-month, and leaves evidence and outcome untouched. Legacy action notes do not count as documented delivery in Monitoring; only an explicit completed linked follow-up with an eligible type/date does. No retained-customer benefit is inferred from these notes.

## Errors and frontend connection

Errors have `{"error":{"code":"validation_failed","message":"..."}}`. Typical statuses: 404 missing resource, 422 invalid input, 409 stale review or occupied assessment cutoff, 403 rejected cross-origin write, 413 excessive request body. Human-note request bodies require JSON and retain the 64 KiB limit. The prepared-month endpoint is the multipart exception with its separate bounds documented above.

Use a Vite `/api` proxy to `http://127.0.0.1:5000` for a separate frontend dev server. This preserves same-origin requests without widening CORS. With a future same-host frontend, use relative `/api/...` paths. Escape text notes through normal frontend text rendering; do not render notes as raw HTML.

Imports are CLI operations against local trusted exports. Invalid imports do not publish a batch. File integrity checks establish consistency with the supplied export manifest; this app does not rerun the original experiment or independently verify its original raw data. The research modules and their original integrity checks remain untouched.
# Milestone 2 case API addition — 6 November 2026

These endpoints span assessments; no `batch_id` is required. Existing prediction/review/action contracts remain supported.

| Method/path | Behaviour |
|---|---|
| `GET /api/cases` | Worklist; optional `q`, `owner`, `status`, `decision`, `offset`, `limit` (1–100; default 50). Decision filters the current linked committee decision. Returns `items`, `total`, `offset`, `limit`. |
| `GET /api/cases/<case_id>` | Returns `case` with original/latest customer evidence, original review, current case state, follow-ups, case events, committee review history and legacy action notes. |
| `PUT /api/cases/<case_id>` | Replaces case-editable state: `status` (`open`, `deferred`, `closed`), `owner`, nullable `next_action_date`, required `notes`, required `recorded_by`, required integer `expected_version`. Returns updated `case`. |
| `POST /api/cases/<case_id>/follow-ups` | Creates a task with its first event; required `action_type`, `action_status`, `action_date`, `notes`, `recorded_by`, integer `expected_version`. Returns updated `case`, HTTP 201. |
| `POST /api/cases/<case_id>/follow-ups/<follow_up_id>/events` | Appends an event to the same task, with the same fields as creation. Returns updated `case`, HTTP 201. |

Case IDs equal their original prediction IDs. A case is created atomically on the first review save; migration backfills existing reviews. Later imports do not move or close it. Deliberate reviews for later predictions link to the existing open/deferred case and append a `committee_reassessment` event. `original_review` preserves the opening judgement; `current_review` is the latest deliberate review by **assessment cutoff descending**, then saved-review timestamp descending, then prediction ID. Updating an older month's review cannot replace a newer month's current decision. `original.review` remains the review of its exact original prediction. Owner/date/status are independently managed case fields.

Action types retain `customer_contact`, `rm_visit`, `service_fix`, `other`. States retain `planned`, `attempted`, `delivered`, `cancelled`; the UI calls `delivered` Completed. A task may start as planned, attempted or delivered. Planned/attempted tasks accept attempted/delivered/cancelled events; terminal tasks require a new task for further work. Type cannot change on an existing task. `planned_date` is the initial plan, while each event's `action_date` is its own date. Non-planned dates cannot be in the future using the Malaysian business date; events after an attempt cannot predate that attempt. A closed case must be reopened before further task events.

Every successful case/task mutation increments the shared case version and appends a case event. Version mismatches return 409 and do not change data. Invalid fields, dates, states or missing attribution/reason return 422; missing cases/tasks return 404. Same-origin write protection and the 64 KiB request limit remain enabled. No task/event write changes predictions or loads realised outcomes.

## RM briefing payload refinement ? 11 November 2026

The existing briefing response's `items` gain the fields below. The GET/POST endpoints, `{case_ids, snapshots}` download body, snapshot fields, evidence hash and 409 review-before-retry contract are unchanged. No client HTML or amounts are accepted.

| Item field | Type and meaning |
|---|---|
| `glance` | Four ordered objects with `label`, `value` and `note` strings: committee decision/case state, latest risk/original-risk context, activity versus usual, and case due date/owner/planned-contact note. A case due date is distinct from planned or recorded contact. |
| `risk_definition` | Deterministic explanatory string for the volume-attrition risk; not account-closure risk. |
| `prepared_on` | Formatted Malaysian calendar date when this representation was prepared; not an assessment cutoff or saved-review date. |
| `followups` | Nullable standard section object (`title`, `paragraphs`, `rows`, `items`); recorded follow-up label/value rows now live in `followups.rows`. Null when no follow-up rows exist. |
| `signals.rows` | Ordered `[label, text]` pairs carrying recorded values and model-influence direction; replaces populated `signals.items`. The generic section shape is retained. |
| `decision.rows` | Current reviewer, review-saved date, case owner, case due date and case status. Follow-up rows have moved to `followups.rows`. |

Other item keys remain `original`, `latest`, `activity`, `operations`, `finance`, `questions`, `traceability`, `ai_context`, `sample_note`, `snapshot`, `case_id`, `customer_id` and `name`. Existing section keys remain intact. `ai_context` still contains only `cutoff_month` and `calibrated_risk`; discussion-question wording and the read-only eligibility/freshness rules are unchanged.

## Supplemental evidence and case continuity — November 2026

The required scoring contract remains exactly the two upload files. Optional support comes from the trusted server paths under `TXB_RESEARCH_ROOT`: `data/final_v4_0_1/cleaned/company_population_clean.csv` (`cus_id`, `cus_name`) and `data/final_v4_0_1/cleaned/monthly_flows.csv`. The uploaded manifest never chooses these paths. Missing sources produce missing/partial presentation evidence; malformed configured sources fail enrichment before any supplemental write. The score stays published. New successful uploads attempt enrichment automatically after scoring publication. An unchanged resubmission stays idempotent and does not silently refresh supporting evidence.

`flask --app app enrich-batch --batch-id ID` previews a saved batch. Add `--apply` to accept fully validated names/flows in one transaction. If accepted source content changes, preview reports `replacement_needed`; only explicit `--apply --replace` versions the correction. Both accepted and superseded supplemental rows retain file SHA-256, batch/cutoff, coverage and application timestamp. The original `batches`, `predictions` and scored evidence are never rewritten. `source.evidence_coverage` in `/api/months` reports effective available names/histories over exact batch records, including embedded evidence on older batches; the booleans remain for older clients. All customer/list/case/briefing reads use the stored effective support data. Recorded flows are joined by customer/month, validated for nonnegative values/counts and reconciliation, and limited to the twelve most recent observations through the exact cutoff. A missing month stays missing.

`customer.workflow` is server-derived and distinct from `customer.review`. It has `state`, optional active `case_id`/`case_version`/`case_status`, original case month/risk/decision, `active_cases` and `prior_review`. States are `reviewed` (this prediction has a saved human review), `existing_case` (open/deferred case; this prediction may still be unreviewed), `case_conflict` (more than one active legacy case; select explicitly), `below_threshold`, `needs_reassessment` (flagged with earlier review/closed case history), and `needs_first_review` (flagged with no history). Current/later case context carries its own origin month when an older assessment is selected. `/api/summary` adds `workflow_counts` and `needs_committee_review`; the latter counts flagged `needs_first_review` plus `needs_reassessment`. Model `flagged` remains unchanged. `/api/customers?workflow=needs_review` applies the same rule before pagination. A below-threshold customer with an open case remains in `/api/cases`.

`PUT /api/predictions/<id>/review` still saves against the exact prediction and uses `expected_version` for that review. When it updates an existing case, include `case_id` and `expected_case_version`; a stale case returns 409 without any review write. If exactly one active case exists for the customer it is the default; multiple active cases require an explicit matching `case_id`. There is no automatic merge, replacement or duplicate case. If only closed history exists, a deliberate new review opens a new episode and records previous closed case IDs in its opening event. Reviews on older predictions remain in history and cannot overwrite the current case decision from a later assessment. Briefing preview/PDF eligibility uses `current_review.decision`; a deliberate Monitor/No immediate action reassessment makes the prior Prioritise briefing ineligible. Preview snapshots include the case version and effective evidence, so changed decisions or enrichment require review before PDF download.

Migration 003 adds only `supplemental_evidence`, `supplemental_history` and `review_case_links`. The existing application initializer backs up a version-2 database through SQLite's backup API before upgrading, applies migration 003 in one transaction and refuses a newer unknown version. Use a separate database copy for acceptance; see [MILESTONE_4.md](../docs/MILESTONE_4.md#supporting-evidence-and-case-continuity) for exact PowerShell commands and measured April checks.
