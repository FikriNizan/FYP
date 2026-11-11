# Milestone 4, Step 3 — Prepared monthly scoring and publication

The Step 3 replay below records the initial two-file scoring implementation. The later [supporting evidence and case continuity](#supporting-evidence-and-case-continuity) section documents the subsequent refinement for an **already published April batch**. April is not re-uploaded or rescored for that refinement.

Implemented on `architect-theme`. Step 3 has automated checks and an actual historical April browser replay. This does **not** mark Milestone 4 complete: the owner's separate Step 4 damaged-copy/repeat exercise, upstream temporal audit and representative-user sign-off remain outstanding.

## Implemented contract

* Monthly Assessments accepts `features.csv` and `manifest.json`, not raw tables, scores, labels, models, Python scripts or verification reports. Previous months stay in SQLite. No raw ETL, retraining, monitoring, OPR or AI service is introduced.
* The CSV has exactly `cus_id`, `cutoff_month`, then the frozen 78 predictors in order (75 numeric, three categorical). The app's byte-hashed `backend/churn_backend/feature_schema.json` is authoritative. IDs/categories remain strings, blank means missing, and zero remains zero. Numeric text must be finite; each twelve-month combined-flow baseline must be positive.
* Strict JSON manifest: `kind=txb_prepared_month`, `package_version=1.0.0`, feature/schema/protocol versions and hashes, predictor/row counts, exact month-end, `files.features.csv.{bytes,sha256}`, and a `source` object. Source provenance is preserved as opaque JSON; it never selects a path or code to execute. Duplicate JSON keys, invalid dates, malformed CSV rows, duplicate customers and mixed months fail validation.
* CSV hash and byte length are checked on the original received bytes before parsing. Checksums establish package consistency, not raw-data truth. No uploaded filename is used as a filesystem path. Temporary scorer input preserves those bytes and is deleted after processing.
* Default server population is exactly 1,000 unique customers; `TXB_MONTHLY_POPULATION` is an explicit administrator setting, never a multipart parameter. This is a count policy, not proof that upstream raw records are correct.
* Upload bounds are 5 MiB CSV, 64 KiB manifest, plus 512 KiB multipart overhead. Other endpoints retain the existing 64 KiB limit; same-origin checks remain in place.
* The worker verifies the checked-in `scorer_contract.json` fingerprints for the trusted original research source, frozen protocol, refit manifests and companion artifacts before importing/loading, and again after scoring. It calls `load_context`, `explain_rows` and `dashboard_record(top_k=5)` on unlabelled features. `load_context` validates/loads the original companion bundles; no evaluation CLI, fitting or calibration fitting runs.
* The fitted preprocessing, champion CatBoost, sigmoid and native SHAP behavior are unchanged. Raw and calibrated probabilities stay separate; the saved raw boundary is applied at full precision. Parent-process saved-evidence validation checks every returned key, flag/policy, explanation reconstruction and displayed feature value before publication.
* Champion SHA-256: `3d31eb0cfc36c2a8bb7fb072f9a63664ae2c3a940552c53c0f58ba94394346ec`; protocol: `6ae6d17ef0dcb7c3b0b7e090bed0dbae475024f5c0606f71ad100411adb5a4dc`. Raw boundary `0.2991379097436803`; calibrated display threshold `0.2586013233784648`.
* Validation/scoring/verification occur outside the publication transaction. `BEGIN IMMEDIATE` rechecks the cutoff and commits the batch plus every prediction together. No migration was needed. Existing import CLI/read contracts remain available.
* Same original CSV bytes + manifest bytes + frozen policy/champion/schema return the existing batch without scoring again. Manifest formatting changes count as a different package. A different valid package at an occupied cutoff returns conflict; simultaneous publication attempts cannot replace or duplicate it.
* Fresh batches use `prepared_month_scored`; provenance records input hashes, versions, model identity, source manifest, scorer fingerprint/checks and timings. No names or monthly flow series are fabricated. Existing cases show the latest customer assessment while their original prediction/decision and follow-ups remain anchored.

## Windows setup and safe replay

Use PowerShell from the app root. Keep the original research environment intact; do not install its modelling dependencies into Flask just for this adapter. The trusted root must contain the unchanged original source and all frozen/refit artifacts pinned by `scorer_contract.json`. A fingerprint mismatch requires investigation, not regeneration of the ledger to bypass it.

```PowerShell
Set-Location 'D:\Degree Life\FYP Full-Stack Development\corporate-attrition-app'
$researchRoot = 'C:\Users\fikri\OneDrive - Asia Pacific University of Technology And Innovation (APU)\Degree\SEM 6\Project Module (FYP)\fyp-data-refinement'
$env:TXB_RESEARCH_ROOT = $researchRoot
$env:TXB_MODEL_PYTHON = 'C:\Users\fikri\fyp-model-env\Scripts\python.exe'
$env:TXB_SCORING_TIMEOUT_SECONDS = '120'
$env:TXB_MONTHLY_POPULATION = '1000'
.\.venv\Scripts\python.exe scripts\copy_database.py backend\instance\churn.sqlite --destination artifacts\my-april-replay.sqlite
$env:CHURN_DB_PATH = (Resolve-Path artifacts\my-april-replay.sqlite).Path
Push-Location frontend
npm run build
Pop-Location
Push-Location backend
..\.venv\Scripts\python.exe -m flask --app app run --host 127.0.0.1 --port 5072 --no-reload
```

The copy command refuses an existing destination. Choose a new name for another clean replay; do not delete April from a published database. Start from a February/March copy with April absent. The application can still serve saved evidence when scorer settings are absent; only a fresh upload fails with a configuration message.

In the browser:

1. Open `http://127.0.0.1:5072/#/assessments` and confirm February/March are present.
2. Select `$researchRoot\data\milestone4\prepared-2024-04\features.csv` and its `manifest.json`. Do not select `verification.json`.
3. Choose **Validate, score and publish**. The indeterminate state lasts until the bounded request responds; no simulated stages or background broker are used.
4. Confirm April 2024, 1,000 scored customers, and choose **Open published assessment**. Its URL must carry that exact batch ID. April 30 predicts May–July 2024; those outcomes are not supplied by this upload.
5. Check an earlier case: latest evidence may be April, but the original month, committee decision, task events and case status stay unchanged. April has customer IDs and unavailable monthly history, not copied historical charts.
6. Stop/restart the same copied-database server and reopen April. Resubmit the unchanged two files: it must say **Assessment already published** and create no rows.

After publication, in another PowerShell terminal from the app root, copy the batch ID from the published link:

```PowerShell
$researchRoot = 'C:\Users\fikri\OneDrive - Asia Pacific University of Technology And Innovation (APU)\Degree\SEM 6\Project Module (FYP)\fyp-data-refinement'
$publishedBatch = 'PASTE_THE_EXACT_PUBLISHED_BATCH_ID'
.\.venv\Scripts\python.exe scripts\compare_monthly.py --database artifacts\my-april-replay.sqlite --batch-id $publishedBatch --reference "$researchRoot\data\models\shap_explainability_v1\dashboard_explanations.jsonl" --reference-manifest "$researchRoot\data\models\shap_explainability_v1\explainability_manifest.json" --verification "$researchRoot\data\milestone4\verification-2024-04\verification.json" --package-manifest "$researchRoot\data\milestone4\prepared-2024-04\manifest.json"
```

This command opens SQLite read-only and compares the **published app rows**, not the offline summary alone. It checks reference/package identity against the offline report and explanation manifest, all 1,000 keys, exact policy/flags/driver identities and directions, probabilities within `1e-12`, SHAP terms within `1e-8`, and the original explanation reconstruction. The reference archive is used only by this acceptance command, never normal upload/scoring. The archive was accessible, so no replay-file fallback was needed.

## Verification performed on 11 November 2026

* `scripts/check.py`: 54 backend tests, eight root utility tests, ten Node API/format tests, 58 React tests, and Vite production build. Existing tests remain; the obsolete disabled-upload preview test was replaced because the real workflow intentionally supersedes that preview.
* New automated checks cover strict manifest/schema/numeric/missing validation, checksum and rehashed invalid header/duplicate customer, scoring/verification failure, timeout/process failure, idempotence/conflict, transactional rollback, simultaneous cutoff publication, no enrichment, same-origin and note-size preservation. React/API checks cover exact multipart files, honest processing, recovery/resubmission, list refresh and exact published navigation.
* Real Chrome file inputs submitted the original April files to an isolated copy of the active February/March SQLite database. The original research Python and saved champion produced fresh scores; no scoring stubs or archive imports were used for this replay.
* Published batch: `bf0e828cdd426ae496ff36bd207acfcd02dccd928eebd14eea5027ce45c9204a`, cutoff `2024-04-30`, exactly 1,000 predictions. After publication all 1,000 keys matched archived April; maximum absolute raw, calibrated and SHAP-term differences were each **0.0**. Flags, policy and top-driver identities/directions agreed exactly.
* Final-code measured timing: validation **0.126s**, subprocess/model/SHAP **5.594s**, parent evidence verification **0.039s**, publication before commit **0.109s**; browser submission-to-success **5.995s**. Persisted publication timing explicitly excludes commit. Earlier unchanged-package browser resubmission returned in **0.217s**. These local measurements support a synchronous 120-second bounded request; they are not production latency targets or live-bank performance claims.
* Restart persistence verified on the first replay copy. The active database and clean input files were preserved. All original two batches/2,000 predictions, five reviews/review histories, five cases, eleven case events, two follow-ups and three follow-up events were compared unchanged. All five cases show April as latest while retaining original February/March context.
* HTTP checksum/schema/duplicate failures and a valid conflicting April package left the copied database unchanged. Model failures and partial-insert rollback are covered in isolated automated tests. Normal saved reads work without configured scoring.
* Browser checked exact batch navigation, missing April names/history, no JavaScript errors, no remote font requests, and 1440px/380px layouts with the existing scrollable assessment table. The Architect stylesheets and print output were not edited.
* Local evidence: `artifacts/monthly-comparison.json`, `monthly-browser.json`, `monthly-preservation.json`, `monthly-check.log`; screenshots under `.impeccable/review/milestone4/`. These and replay databases are ignored local artifacts, not submitted customer datasets.

## Limits and pending sign-off

* The owner's Step 4 damaged-copy/manual exercise remains separate and pending. This historical replay does not establish raw-source validity, label maturity, live-bank performance, production readiness or completion of all roadmap audits.
* The synchronous adapter permits one scorer subprocess at a time per Flask process; other attempts receive a retryable busy response. SQLite independently serializes publication across processes. There is no durable background job or cancellation endpoint. A lost browser connection may outlive processing: check saved assessments, then safely resubmit the same package.
* The exact trusted original Windows research environment is required; other model/artifact versions deliberately fail closed. Timeout is administrator-controlled from 1–600 seconds. No scoring fallback exists.
* `PRODUCT.md` still describes monthly upload/scoring as unavailable (product-register text from before this integration). It was left unchanged; this task implements that newly requested scope. Its uncertainty, human-decision and financial semantics remain preserved.

## Files changed and purpose

* `backend/churn_backend/monthly.py`: byte-level package validation, bounded subprocess orchestration and complete evidence verification.
* `backend/churn_backend/model_worker.py`, `scorer_contract.json`: original unlabelled scorer adapter and trusted source/artifact fingerprints.
* `backend/churn_backend/repository.py`: atomic cutoff-guarded monthly publication and provenance timings; historical import remains intact.
* `backend/churn_backend/__init__.py`, `api.py`: optional scorer settings, safe error responses, multipart route and capability metadata.
* `frontend/src/api.js`, `App.jsx`: multipart client and refresh of existing assessment state.
* `frontend/src/pages/MonthlyAssessments.jsx`, `Guide.jsx`: real two-file workflow, recovery/success links, source distinction and current capability wording.
* `backend/tests/test_monthly.py`, `frontend/tests/monthly-api.test.mjs`, `workspace.test.jsx`: focused package/transaction/adapter and UI regression checks.
* `scripts/compare_monthly.py`: read-only post-publication row-level acceptance comparison.
* `backend/API_CONTRACT.md`, `docs/UI_DESIGN.md`, `docs/ROADMAP.md`, `README.md`, this document: route contract, implemented workflow, setup, evidence and pending sign-off.

## Supporting evidence and case continuity

The active local database already has April 2024. The refinement attaches supporting names/observed flows and links any deliberate later committee review to the same ongoing case. The frozen feature CSV, model, policy, probabilities, SHAP and prediction IDs are unchanged. The two-file upload contract remains intact. The trusted source paths are derived only from `TXB_RESEARCH_ROOT`:

* `data\final_v4_0_1\cleaned\company_population_clean.csv` (`cus_id`, `cus_name`)
* `data\final_v4_0_1\cleaned\monthly_flows.csv` (recorded customer/month flows)

Migration 003 adds `supplemental_evidence`, `supplemental_history` and `review_case_links` with no rewrite of scored rows. The application creates a SQLite backup before upgrading a version-2 database, then commits the migration transaction. The supplemental row is keyed by exact prediction ID. Each accepted version stores a source fingerprint, actual batch/cutoff coverage and application time; an explicit replacement archives its prior version. Names join by exact string ID, so leading zero IDs are preserved. Flows join by customer and month, require complete, nonnegative, reconciling source rows, and use the twelve most recent recorded observations no later than the batch cutoff. Missing months remain gaps. Missing source files or missing customer coverage yield unavailable/partial support. A malformed source rejects the entire enrichment attempt before writing. Accepted evidence is read from SQLite on future page loads; mutable research files are never silently re-read into a dashboard.

For a **new** successfully scored month, the server attempts optional enrichment after publishing the verified scores. Enrichment failure returns a published result with a separate unavailable status and useful local diagnostic. An unchanged upload remains idempotent and does not refresh accepted support. New source corrections require the explicit batch operation below. A future month needs its upstream recorded-flow source updated; an April historical backfill does not supply future observations.

Each customer response now has `review` for that exact prediction and separate server-derived `workflow` context. The workflow states distinguish reviewed, existing open/deferred case, multiple-active-case conflict, below-threshold, first review and reassessment. `needs_committee_review` and the queue's workflow filter use the same flagged first-review/reassessment rule; the model-flagged portfolio total is unchanged. A later score never creates or closes a case or changes a human decision. A deliberate new review against April requires the current case version; the write transaction rechecks it, saves the April review, links it to the original case and records `committee_reassessment`. The effective case decision is the saved review from the latest assessment cutoff, then latest saved timestamp, then prediction ID. Revising an older review cannot replace the effective decision from a later month. The opening judgement, origin prediction, case ID and tasks remain intact. Multiple legacy active cases require explicit selection; a closed case stays history and a new flagged deliberate review opens a new episode.

The worklist, Customer Review, Case Detail, briefing JSON and PDF use the same stored supplemental evidence and current case decision. A later Monitor/No immediate action review makes a previously prioritised case ineligible for the RM briefing; the original Prioritise judgement remains in the audit history. The Architect CSS, shell and routes were preserved.

### Copyable Windows acceptance steps

Run these in PowerShell from the app root. `copy_database.py` uses SQLite's online backup API and refuses an existing destination. It reads the active database and writes only the new copy. Choose a fresh copy name for another run.

```PowerShell
Set-Location 'D:\Degree Life\FYP Full-Stack Development\corporate-attrition-app'
$researchRoot = 'C:\Users\fikri\OneDrive - Asia Pacific University of Technology And Innovation (APU)\Degree\SEM 6\Project Module (FYP)\fyp-data-refinement'
$env:TXB_RESEARCH_ROOT = $researchRoot
$env:CHURN_DB_PATH = (Join-Path (Get-Location) 'artifacts\april-enrichment-review.sqlite')
.\.venv\Scripts\python.exe scripts\copy_database.py backend\instance\churn.sqlite --destination $env:CHURN_DB_PATH
$aprilBatch = 'bf0e828cdd426ae496ff36bd207acfcd02dccd928eebd14eea5027ce45c9204a'
Push-Location backend
..\.venv\Scripts\python.exe -m flask --app app enrich-batch --batch-id $aprilBatch
..\.venv\Scripts\python.exe -m flask --app app enrich-batch --batch-id $aprilBatch --apply
..\.venv\Scripts\python.exe -m flask --app app enrich-batch --batch-id $aprilBatch --apply
Pop-Location
```

The first command after `Push-Location` is a **dry run**: inspect `coverage`, file SHA-256 and `changed=1000` before applying. With the current trusted April sources, the second command applies 1,000 supplemental rows; the third reports `changed=0`. If sources later change, preview reports `replacement_needed=true`. Only after checking the correction should an administrator use `--apply --replace`; this archives the accepted old version. Do not edit the clean April scoring inputs or the research sources for this exercise.

Build and run the copied dashboard; leave the active application/database alone:

```PowerShell
Push-Location frontend
npm run build
Pop-Location
Push-Location backend
..\.venv\Scripts\python.exe -m flask --app app run --host 127.0.0.1 --port 5074 --no-reload
```

In the browser, open `http://127.0.0.1:5074/#/assessments`. April should show 1,000 of 1,000 names and flows available. Open April, search for a known customer ID such as `944`, inspect the real name and exact observed amounts through April 2024, and confirm no May or later month appears. Open that customer's existing case. Compare its original assessment/committee decision with the April risk and recorded history; continue the same follow-up. If you deliberately save an April committee reassessment, use the current case link/form, then inspect the unchanged case ID and original judgement, new linked review and event, and current decision. A Monitor/No immediate action reassessment removes briefing eligibility; no case closure or delivered intervention is inferred. Restart the copied server and confirm the name, history and decision persist.

For an audit without a second review, use the copied database and `scripts/compare_monthly.py` command above. It still reports the exact published April scores; supplemental evidence has no effect on probability/SHAP comparisons.

### Checks performed locally

* The actual April batch was already present in the active database. A safe online backup created a separate test copy; only that copy was upgraded and enriched. CLI dry run found **1,000 names and 1,000 valid histories**, `--apply` added 1,000 supplemental rows, and a second apply changed **0**. Customer 944 had exactly twelve stored observations from May 2023 through April 2024; April combined flow equalled its saved one-month feature. February/March still showed only observations through their own cutoffs.
* The copy's original `batches`, all 3,000 `predictions`, reviews, review history, cases, case events and follow-ups matched the active database row for row. The original score/SHAP hashes and IDs were unchanged. Reopening the copy with an unavailable research path still returned the accepted names/histories, proving reads use stored supplemental evidence.
* A second isolated copy exercised a **real April reassessment** for an existing March prioritised case: its case ID, originating prediction and follow-ups were preserved; current decision changed to Monitor, one `committee_reassessment` event was added, briefing became ineligible, and the result persisted after restart. No active database row was written by this exercise.
* Final `scripts/check.py` in the project `.venv` passed: **64 backend tests, 8 root utility tests, 10 Node tests, 60 React tests and the Vite build**. Isolated fixtures cover missing/partial and invalid sources (including duplicate and negative flow rows), zero versus missing, cutoff safety, repeat enrichment, explicit correction history, case continuity, later-review linking, older-review ordering, closed/deferred cases, multiple active case selection and workload counts.
* On the enriched copy, resubmitting the original April two-file package returned the existing batch (`already_imported=true`) and left batch, prediction, review, case, follow-up and supplemental row counts unchanged. The read-only archived comparison still matched all 1,000 April customer-month keys after enrichment, with maximum absolute raw, calibrated and SHAP log-odds differences of **0.0**.
* A headless Chrome walkthrough of the enriched copy checked April coverage, customer 944's name/history and existing case navigation at 1440px and 380px. It found no horizontal overflow, JavaScript errors or remote font requests. The owner's Step 4 damaged-package exercise and final manual sign-off remain separate.

