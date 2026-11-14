# Milestone 5 — Observed outcomes and descriptive monitoring

Implementation checkpoint, 15 November 2026. This milestone adds a separate, explicit outcome import and a connected Monitoring screen. It does **not** claim that the saved synthetic history demonstrates retention effectiveness, live-bank performance or production readiness. The owner's representative-user acceptance remains separate.

## Contract and boundaries

* A prediction uses observed data only through its month-end cutoff. An outcome uses the **next three complete months** and is saved only after an administrator explicitly supplies an observed-through month at or beyond the horizon end. No page load, later score, human decision or follow-up event creates an outcome.
* `load-outcomes` reads the accepted trusted `data/final_v4_0_1/cleaned/monthly_flows.csv` under `TXB_RESEARCH_ROOT`, checks its size/SHA-256 against `cleaned_manifest.json`, and never loads executable input. It requires all twelve complete baseline months plus all three complete future months for each customer; missing or incomplete source rows remain unavailable, never zero. The saved 12-month feature must reconcile with the source baseline within `0.000001` MYR. The rule is `8 × future three-month sum <= trailing twelve-month sum` in integer cents, for a positive baseline.
* Migration 004 adds `observed_outcomes` keyed by **prediction ID**, with the label, sums, three future observed flows, horizon date, source SHA-256 and import time. The prior prediction, SHAP, review, case and follow-up tables are not rewritten. Same-source repeat imports are idempotent; a changed accepted outcome conflicts instead of silently replacing history. All prepared rows publish in one SQLite transaction.
* The customer detail exposes `observed_outcome` separately from predicted risk. The historical Summary chart still shows only pre-cutoff observed months. The Monitoring page reads saved outcomes; it cannot generate labels from a different assessment or a chart.
* A **documented delivery** is a linked follow-up event with status `delivered`, type `rm_visit`, `customer_contact` or `service_fix`, and an actual action date inside that prediction's next three months. Plans, attempts, cancellations, other/unclear action types and unlinked legacy notes are excluded. “No recorded delivery” does not establish that no action happened.
* Outcome rates, mean saved risk, Brier score and flagged-case positive share are descriptive for the observed records. Delivery groups are selected by human activity, not randomized. Differences between them do not estimate a counterfactual or prove that an intervention prevented a volume drop. The target is transaction **volume**, not account closure.
* Input/risk movement compares the selected batch with the nearest earlier batch under the same frozen protocol. It shows mean risk, flagged share, availability and selected feature medians/category-mix differences; no threshold, causal story or alert verdict is invented. Unloaded outcomes are absent from every performance denominator.

## Safe Windows walkthrough on a database copy

Run from the repository root in PowerShell. Use a fresh destination name; `copy_database.py` refuses overwrite. The trusted research root is read only. Starting Flask on the copied database performs the version-4 migration and creates a timestamped backup of **that copy**.

```PowerShell
Set-Location 'D:\Degree Life\FYP Full-Stack Development\corporate-attrition-app'
$env:TXB_RESEARCH_ROOT = 'C:\Users\fikri\OneDrive - Asia Pacific University of Technology And Innovation (APU)\Degree\SEM 6\Project Module (FYP)\fyp-data-refinement'
.\.venv\Scripts\python.exe scripts\copy_database.py backend\instance\churn.sqlite --destination artifacts\m5-user-check.sqlite
$env:CHURN_DB_PATH = (Resolve-Path artifacts\m5-user-check.sqlite).Path
Push-Location backend
..\.venv\Scripts\python.exe -m flask --app app load-outcomes --batch-id bf0e828cdd426ae496ff36bd207acfcd02dccd928eebd14eea5027ce45c9204a --observed-through 2024-07-31
..\.venv\Scripts\python.exe -m flask --app app load-outcomes --batch-id bf0e828cdd426ae496ff36bd207acfcd02dccd928eebd14eea5027ce45c9204a --observed-through 2024-07-31 --apply
..\.venv\Scripts\python.exe -m flask --app app load-outcomes --batch-id bf0e828cdd426ae496ff36bd207acfcd02dccd928eebd14eea5027ce45c9204a --observed-through 2024-07-31 --apply
..\.venv\Scripts\python.exe -m flask --app app run --host 127.0.0.1 --port 5075 --no-reload
```

The first import is a dry run; inspect 1,000 available / zero unavailable before applying. The second saves; the third should report `changed=0`. Open `http://127.0.0.1:5075/#/monitoring?batch_id=bf0e828cdd426ae496ff36bd207acfcd02dccd928eebd14eea5027ce45c9204a`. Open an April customer to see the separate observed outcome. A later committee decision or delivered contact cannot alter the saved label. To compare February/March, use their exact batch IDs from `/api/months` and observed-through months `2024-05-31` / `2024-06-30` respectively. Do not run the import against the active database until its backup and acceptance are deliberately approved.

## Checks and evidence

* Automated tests exercise the maturity gate, dry run, full-window label, missing/incomplete/duplicate source, idempotent/conflicting repeat, planned versus delivered window exposure, out-of-window/unclear action types, customer detail and the Monitoring UI. The repository's full `scripts/check.py` passes (69 backend, 8 root utility, 10 Node, 62 React tests and Vite build).
* On `artifacts/m5-acceptance-20261115.sqlite`, a copy of the active 3,000-prediction database, the trusted source produced 1,000 available outcomes for each February, March and April 2024 batch. An unchanged April repeat changed zero rows. April's 1,000 labels matched `data/features_v1/targets_NOT_FEATURES.csv` **by customer ID**: 184 positive, no missing or different labels. April monitoring reported mean saved risk about 0.16098, observed drop rate 0.184 and Brier score about 0.12756. This is a historical synthetic replay, not an independent real-bank evaluation.
* Chrome inspected the connected Monitoring page on the copied database at 1440, 760 and 380px: no horizontal overflow, script exceptions, response alerts or remote font requests. The April customer detail rendered its separate outcome. Screenshots and the browser result are in ignored `.impeccable/review/milestone5/` and `artifacts/m5-browser.json`.
* The active database and original research artifacts were not written. All pre-existing rows in `batches`, `predictions`, `reviews`, review history, cases, case events, follow-ups, follow-up events, supplemental evidence and review-case links matched the active database after the copied outcome imports. User acceptance and broader raw-source point-in-time assurance remain open; the latter needs real observation/ingestion timestamps (see [research reference](../research/MILESTONE_4_DOCUMENTATION_REFERENCE.md)).

