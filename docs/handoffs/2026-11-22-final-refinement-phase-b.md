# Handoff — final refinement, Phase B (outcomes checked automatically on upload)

Date: 22 November 2026 (Malaysia time). Branch: `final-refinement`, continuing from Phase A (`376b0b8`). Pushed to
`origin/final-refinement`. Nothing merged into `main`; no force-push; no Co-Authored-By trailers.

**The demo database was NOT built**, as instructed. Your render-7 summary re-run is only partly done (Gemini daily
quota). The builder and its tests are ready; you tell me when to run `demo_session.py build`.

## Commits

| SHA | What |
|---|---|
| `0947778` | B1 derivation + B3 conflict rule, migration 006, B2 gate script (feature not yet enabled) |
| `20087e5` | B3 hook enabled after the gate passed; B4 upload message and "Outcome check" column |
| `b6ed1a6` | B5 demo builder, `m8-demo` launch mode; API contract, runbook, roadmap |
| (this file) | Phase B handoff |

## B1 — how the outcome is derived, and why it equals the research label

**Research definition.** `audit_targets.py` (lines 10–43, read-only):
* Combined flow comes from `monthly_flows.csv` (`inbound + successful outbound`), held in integer cents.
* `baseline_sum = rolling 12-month sum ending at the cutoff t` (months t−11..t).
* `future_sum = flows t+1 + t+2 + t+3`.
* Eligible = `baseline > 0` and all three future months present.
* Label = `8 × future_sum ≤ baseline_sum`, which is the same as "the next three months' average is at most half the trailing 12-month average".

The app's file loader (`outcomes.prepare`) already used exactly this rule.

**Package fields that supply it.** Packages carry only the 78 predictors (no flow history), each defined "over N complete months ending at cutoff":
* **Baseline.** The assessment at t's `combined_flow_mean_12m_myr` × 1,200 = baseline cents. Packages already require this value to be positive.
* **Each future month.** For k = 1, 2, 3, the `combined_flow_mean_1m_myr` × 100 of the assessment published for month t+k (same customer).
* **Cross-check.** The t+3 assessment's `combined_flow_mean_3m_myr` × 300 must equal the future sum (±1 cent).
* **Rounding guard.** A value more than 0.01 cent from whole cents is not accepted, so the customer is not available.
* **Missing data.** A missing month means the assessment is "waiting"; a missing customer is "not available". Neither is ever counted as zero.

So May completes February, June completes March, and July completes April. The proof is empirical: the gate below.

## B2 — verification gate (passed before the feature was enabled)

Steps:
1. Prepared packages for May, June and July 2024 with the offline `monthly_prepare_and_verify.py prepare`. It wrote only to `--out` under `artifacts/m8-packages/`. All three `validate` runs gave PASS with 1,000 rows each.
2. Copied `m6-review.sqlite` to `artifacts/m8-gate.sqlite` with `local_session.py new-test` (SQLite backup API; origin record written).
3. Ran `scripts/verify_package_outcomes.py`. It refuses the Working, Milestone 5 and Milestone 6 files. It published the three packages through the normal path (frozen champion scoring; enrichment available), then derived Feb, Mar and Apr **in memory**. Each derivation was compared per customer with `targets_NOT_FEATURES.csv` and with the copy's stored file-derived outcomes.
4. Research-folder listing (path, size, mtime over 12,693 files): unchanged after preparation and unchanged after the gate.

| Batch | Matched / total | Unavailable | Positives | TP | FP | FN | TN | Stored outcome identical |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Feb 2024 (`5f30af7670e2`) | **1,000 / 1,000** | 0 | 164 | 86 | 122 | 78 | 714 | 1,000 / 1,000 |
| Mar 2024 (`4e3192d4d60a`) | **1,000 / 1,000** | 0 | 221 | 96 | 115 | 125 | 664 | 1,000 / 1,000 |
| Apr 2024 (`bf0e828cdd42`) | **1,000 / 1,000** | 0 | **184** | **86** | **120** | **98** | **696** | 1,000 / 1,000 |

```
GATE PASS
```

April matches the trusted figures exactly. Every derived row has evidence identical to the file-derived row, so in the Test database they are "already present" no-ops (correction 3). Package sha256 values (`artifacts/`, not committed):

| Package | `features.csv` | `manifest.json` |
|---|---|---|
| May 2024 | `92af1df8…9058` | `7e01b968…5db4` |
| June 2024 | `ba4bf88e…9127` | `69bec6ae…2496` |
| July 2024 | `e90a2dfd…472d` | `1dbe9cfc…45f4` |

## What changed and why, per file

* `backend/churn_backend/outcomes.py`
  * `insert_rows`: the shared transactional writer, also used by `load-outcomes`, with named columns.
    * The same evidence as an existing row is a no-op that keeps that row ("already present").
    * A different label is a `ConflictError` that rolls back the whole assessment.
  * `whole_cents`, `published_batch` (exactly one full batch per month under the protocol, otherwise "not available"), `horizon_months`, `package_coverage`.
  * `derive` (in memory, never writes).
  * `publish_derived`, with statuses `checked`, `already_present`, `waiting`, `not_available` and `conflict`. It never raises on a conflict.
  * `derive_after_publish`: every earlier assessment whose window includes the new month.
  * `outcome_check`: data-based readiness, `checked` / `waiting` (with `waiting_for_month`) / `not_checked`. It is added to `report()` and to every trend item.
* `backend/churn_backend/migrations/006_outcome_provenance.sql` and `db.py`
  * Migration 006 adds nullable `source_kind` and `source_batches_json`. Existing rows keep NULL, meaning the research file.
  * `LATEST = 6`; the migration runner now applies 005 only when needed, then 006.
  * Working and Milestone 5 protection is unchanged. The usual automatic pre-migration backup applies.
* `backend/churn_backend/monthly.py`
  * After publication, and on an idempotent resubmission, `check_earlier_outcomes` runs.
  * The response adds `flagged` and `outcome_checks`.
  * Errors in derivation never undo or fail the publication.
* `backend/churn_backend/repository.py`: `/api/months` items add `outcome_check`.
* `backend/churn_backend/api.py`: the runtime context recognises `m8-demo` (its own confirmed file).
* `frontend/src/pages/MonthlyAssessments.jsx`
  * The full saved-assessments table is kept (Assessment, Coverage, Available evidence with Source details, Imported, Action with Open overview), plus one new column, "Outcome check" ("Checked", "Waiting for <Month> data" or "Not checked").
  * Upload result: "<Month> published · N scored customers, F flagged for review", then for each completed month "<Month> is now ready to check. Outcomes derived from <Mar–May 2024> activity for N of N customers." with "Open Monitoring for <Month>".
  * Already-present and conflict lines say that existing outcomes were kept.
  * No reset control.
* `frontend/src/App.jsx`: the local database indicator labels `m8-demo` as "Demo Test database".
* `scripts/verify_package_outcomes.py` (new): the gate.
* `scripts/demo_session.py` (new): the B5 builder; not run.
* `scripts/local_session.py`
  * `m8-demo` mode, with a check that it is its own confirmed file.
  * Schema guard raised to 6.
  * After launch the backend must report schema 6, replacing the old "m6-test requires schema 5" check.
* Docs:
  * `backend/API_CONTRACT.md`: derivation rule, response fields, provenance, `outcome_check`.
  * `docs/LOCAL_DATABASE_WORKFLOW.md`: gate and demo commands, schema 6.
  * `docs/ROADMAP.md`: status row.
* Tests:
  * `backend/tests/test_outcomes.py`: 9 new tests:
    * the rule including the exact boundary (8 × 15,000 = 120,000 counts as a drop);
    * waiting, missing customer and missing value are never guessed;
    * the cross-check;
    * provenance and idempotency;
    * **same existing outcome kept as already present**;
    * **different existing outcome is a conflict with rollback and nothing overwritten**;
    * only assessments the new month completes are checked; sample and other-protocol batches are excluded;
    * monitoring uses the derived outcomes;
    * migration 006 preserves rows.
  * `backend/tests/test_monthly.py`: the end-to-end upload hook (mocked scorer), including the idempotent resubmission.
  * `tests/test_demo_session.py` (new, 4 tests, temporary files only).
  * `frontend/tests/monthly-upload.test.jsx`: 3 new tests (ready line and Monitoring link; already-present and conflict lines; all columns kept plus Outcome check; no reset).

## Every changed assertion and why

1. `backend/tests/test_ai_drafts.py` (additive-migration test): the expected `max(version)` changes from 5 to 6. To simulate a version-4 database, the test now also drops the 006 columns and deletes versions ≥ 5. **Why:** migration 006 is the approved Phase B schema change. Every business-row equality assertion is unchanged.
2. `backend/tests/test_cases.py:182`: the expected `COUNT(*) FROM schema_migrations` changes from 5 to 6. **Why:** migration 006.
3. `tests/test_local_session.py`: the mocked backend context now reports `schema_version` 6 instead of 5. **Why:** the launcher now requires schema 6.
4. Fixture setup only, not an assertion: `test_ai_drafts.py:103` inserts an outcome with named columns (the table gained two columns).

## Commands run and actual outputs

* Package preparation and validation (May, June, July): each validate run reports `"row_count": 1000`, `"scope": "Package validation only"`. Research listing unchanged.
* Gate: the table above, with `GATE PASS` and the research listing unchanged. The publication of the three packages took about 25 s in total.
* `.\.venv\Scripts\python.exe scripts\check.py`, exit 0:
  * backend `Ran 211 tests — OK (skipped=1)`;
  * utility `Ran 35 tests — OK (skipped=11)` (the generator real-data tests run only in fyp-model-env);
  * Node `tests 10, pass 10, fail 0`;
  * React `Test Files 13 passed, Tests 112 passed`;
  * build `✓ built in 322ms`.
* No demo was built, and `artifacts/m8-demo.sqlite` does not exist.

## Exactly how you run the new things (PowerShell, repository root, `$R` = research folder)

1. **After your summary re-run is complete**, tell me, or build the demo yourself:
   ```PowerShell
   .\.venv\Scripts\python.exe scripts\demo_session.py build --research-root $R
   ```
   This copies `artifacts\m6-review.sqlite` (with its current summaries) to `artifacts\m8-demo.sqlite`. It checks the copy holds exactly February to April 2024, removes the outcomes **in the copy only**, and confirms the May package. It never copies the Working database.

   To rebuild after another summary run:
   ```PowerShell
   .\.venv\Scripts\python.exe scripts\demo_session.py build --research-root $R --rebuild
   ```
   `--rebuild` replaces only the demo file.
2. Launch the demo on separate ports. The scoring settings are needed so the May upload can be scored:
   ```PowerShell
   $env:TXB_RESEARCH_ROOT = $R; $env:TXB_MODEL_PYTHON = 'C:\Users\fikri\fyp-model-env\Scripts\python.exe'
   .\.venv\Scripts\python.exe scripts\local_session.py m8-demo --backend-port 5086 --frontend-port 5196
   ```
   The first launch migrates the copy to schema 6 with an automatic backup.
3. In the browser (`http://127.0.0.1:5196`):
   1. Open Monthly Assessments and upload `artifacts\m8-packages\prepared-2024-05\features.csv` and `manifest.json`.
   2. Expect "February 2024 is now ready to check. Outcomes derived from Mar–May 2024 activity for 1,000 of 1,000 customers." and the Monitoring link.
   3. In the table, February shows "Checked"; March shows "Waiting for June 2024 data"; April shows "Waiting for June 2024 data". April's window is May–July and June is its first missing month.
4. Your `m6-test` session will also migrate to schema 6 on its next launch, with a `-pre-migration-*` backup. Its 3,000 file-derived outcomes are unchanged.
5. To re-run the gate: the gate copy already has May to July published, so run it again without `--publish`. It only derives and compares; nothing is written.
   ```PowerShell
   .\.venv\Scripts\python.exe scripts\verify_package_outcomes.py --db artifacts\m8-gate.sqlite --research-root $R
   ```

## Open questions

* **Waiting month for April.** It shows "Waiting for June 2024 data" after May is uploaded, because June is the first missing month of its May–July window. If you would rather show the window end ("Waiting for July 2024 data"), it is a one-line change.
* **Monitoring readiness.** The page still shows its existing state labels. The data-based readiness cards and empty state are Phase C (C7).

## Known limitations

* The derivation relies on the packages' own aggregate features. It cannot independently re-verify individual monthly source rows, the same limit noted for stored baselines in Milestone 5.
* The verified OPR table ends on 10 Jul 2024, so the July package's Finance contribution shows as unavailable (fail-closed). Outcomes are unaffected.
* This is a synthetic historical replay of one bank's data, not live-bank validation.
