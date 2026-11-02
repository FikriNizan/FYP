> Full-stack foundation v0.2.0: `/` serves the browser dashboard; `/api` serves the API index. The evidence/review/action API contracts below are retained from backend v1.

# Backend API contract — v0.2.0

Base URL: `http://127.0.0.1:5000`. All `/api` responses are JSON. No endpoint fits or recalibrates a model.

## Evidence selection

Evidence endpoints accept `month=YYYY-MM` or a full month-end date, and optional `batch_id`. Without a selection, use the latest imported month, preferring a full export over a case sample. When both are supplied they must agree. A missing batch/month returns 404; an invalid selection returns 422.

`/api/months` returns one entry per preserved batch, including its month, source kind, count, protocol identity and provenance. Source kinds are `notebook_case_sample` and `saved_shap_export`. Display the sample label when applicable; a sample count must never be presented as the full portfolio.

## Routes

| Method | Route | Response |
|---|---|---|
| GET | `/` | Browser dashboard (HTML) |
| GET | `/api` | API index and server version |
| GET | `/api/health` | Server version and number of batches |
| GET | `/api/metadata` | Decision/action enums, timezone and milestone capabilities |
| GET | `/api/months` | `items`: imported batches |
| GET | `/api/summary` | Population, flagged counts, review counts, finance totals and coverage |
| GET | `/api/customers` | Filtered/paginated `items`, batch, total, limit, offset |
| GET | `/api/customers/<cus_id>` | Batch and detailed customer evidence |
| GET | `/api/customers/<cus_id>/history` | Imported monthly snapshots through the selected month |
| PUT | `/api/predictions/<prediction_id>/review` | Saved review with new version |
| GET | `/api/predictions/<prediction_id>/review-history` | All saved review versions |
| POST | `/api/predictions/<prediction_id>/actions` | New action note, HTTP 201 |
| GET | `/api/predictions/<prediction_id>/actions` | Dated notes for that prediction |

Customer listing filters: `q` matches ID/name, `flagged=true|false`, `decision=awaiting_review|prioritise|monitor|no_immediate_action`. `limit` defaults to 100 and permits 1–1,000; `offset` defaults to 0. Results are sorted by full-precision risk descending, then customer ID. `total` is the filtered count before pagination. Summary totals are for the complete selected batch, not the current filtered page.

`review_alert` identifies the frozen model flag. Review decisions are human records and never substitute for that flag. Risk is a 0–1 probability; the frontend may format it as a percentage. It must use the saved flag, not recompute it from a rounded percentage.

## Detail response

`customer` contains `prediction_id`, `batch_id`, `cus_id`, `cutoff_month`, nullable customer/profile fields, `calibrated_risk`, `review_alert`, `probability_cutoff`, `review`, `finance`, `operations`, `features`, `feature_count`, `explanation`, `flow_history`, `actions` and the assessment-window end date.

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

`actual_attrition=null` and `outcome_status=not_loaded` are deliberate in this milestone. Historical labels printed elsewhere in the notebook are not imported into dashboard evidence.

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

All fields are required. An action is append-only, linked to a particular prediction/customer-month, and leaves evidence and outcome untouched. Group service fixes and systematic intervention-exposure derivation are later functionality. No retained-customer benefit is inferred from these notes.

## Errors and frontend connection

Errors have `{"error":{"code":"validation_failed","message":"..."}}`. Typical statuses: 404 missing resource, 422 invalid input, 409 stale review, 403 rejected cross-origin write, 413 excessive request body. Request bodies require JSON. The body size limit is 64 KiB, suitable for human notes; this milestone has no HTTP file-upload endpoint.

Use a Vite `/api` proxy to `http://127.0.0.1:5000` for a separate frontend dev server. This preserves same-origin requests without widening CORS. With a future same-host frontend, use relative `/api/...` paths. Escape text notes through normal frontend text rendering; do not render notes as raw HTML.

Imports are CLI operations against local trusted exports. Invalid imports do not publish a batch. File integrity checks establish consistency with the supplied export manifest; this app does not rerun the original experiment or independently verify its original raw data. The research modules and their original integrity checks remain untouched.
