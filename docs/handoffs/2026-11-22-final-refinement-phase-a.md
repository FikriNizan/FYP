# Handoff — final refinement, Phase A (correctness pass)

Date: 22 November 2026 (Malaysia time). Branch: `final-refinement`, created from `origin/milestone-7` (`4bdc694`),
which already contains `finance-metrics` and `summary-rejections` (both checked as ancestors).
Pushed to `origin/final-refinement`. Nothing merged into `main`; no force-push; no Co-Authored-By trailers.

Scope: the accepted findings 1–6 and wider-project issues of `docs/reviews/MILESTONE_7_REVIEW.md`, plus the
owner decisions in the Phase A brief. No new features. Phases B and C have not started.

## Commits

| SHA | What |
|---|---|
| `03e4e9e` | Inputs: `docs/reviews/MILESTONE_7_REVIEW.md` and `docs/design/ui-refresh-mockup.html` (previously untracked) |
| `827bef3` | A1 check-B owner rule, render-7, OPR coverage reason, "Combined flow" terminology |
| `2f363fd` | A2 OPR generator `m7-opr-2`: conservative maturity rule and honest event counts |
| `0137060` | A3 scenario-package contract + shared fixture; A5 OPR page wording |
| `4cb48c6` | A4 portable launcher runtime resolution (CI on Ubuntu) |
| `fa40d39` | A6 docs: one current status per capability, OPR coverage note |
| (this file) | Phase A handoff |

## What changed and why, per file

### A1 — Finance check B (owner rule)
* `backend/churn_backend/finance_metrics.py`
  * **Check B:** `shortfall = assumed transaction cost − fee income`. Flagged only if `shortfall > 0` **and** `max(deposit earnings, 0) < shortfall`. Uncovered = `shortfall − max(deposit earnings, 0)`.
  * Negative deposit earnings are no longer folded into B. They stay visible as their own component and in `negative_fd_earnings`.
  * The returned `shortfall` field is still `max(0, cost − fee)`.
  * The portfolio and both sensitivities reuse this function, so they follow automatically.
  * **Fail-closed reason:** `OPR_UNVERIFIED` is derived from `OPR_TABLE` and reads "OPR not verified for this cutoff (verified rates end 10 Jul 2024)".
  * The cost-proxy comment now says the direction of bias is uncertain (review: a price cap does not prove overstatement).
* `backend/churn_backend/ai_render.py`: `VERSION = 'render-7'`. The check-B card text is unchanged; it still follows the flag.
* `frontend/src/components/FinanceMetrics.jsx`
  * Labels "Assumed transaction cost" and "Deposit earnings (estimate)", in the components list and the sensitivity row labels.
  * The check-B detail now describes uncovered transaction cost ("Uncovered: RM X a month").
* `docs/FINANCE_METRICS.md`:
  * the new rule, worked example and labels;
  * the April before/after table;
  * the bias wording;
  * the OPR end date and fail-closed reason;
  * "substantial, not minor" → "substantial";
  * render-7.
* `backend/tests/test_finance_metrics.py`: four new tests:
  * the review probe;
  * shortfall with FD ≤ 0 is uncovered in full;
  * positive FD fully or partly covers;
  * RaR and both sensitivity RaR rows do not depend on B.

### Terminology: "Transaction value" → "Combined flow"
* `ai_render.py` (driver labels, bottom line, finance sentence, family name, template question), `ai_evidence.py` (label; `VERSION = 'm6-evidence-6'`), `briefings.py`, `ai_drafts.py` (prompt example only), `frontend/src/format.js`, `frontend/src/main.js`.
* This goes in Phase A so **one** live summary re-run covers render-7 and m6-evidence-6 together.

### A2 — OPR scenarios `m7-opr-2` (`scripts/opr_scenarios.py`)
* **`apply_scenario`, conservative rule:** only FD rows dated on or after the FD's maturity (and no later than the cutoff) that the **baseline shows ACTIVE** are transformed.
  * Baseline closures are preserved and nothing is re-opened.
  * A missing post-maturity snapshot is **never created**; it is counted as `fds_missing_post_maturity_snapshots`.
  * An event counts only if at least one cell really changes.
* **New counters:**
  * `assigned_exit_customers`
  * `eligible_exit_customers` / `eligible_exit_fds` (assigned and maturing in the window)
  * `exit_affected_customers` / `exit_affected_fds`
  * `repriced_customers` / `repriced_fds`
  * `fds_no_active_post_maturity`
  * `fds_rate_missing`
  * `cells_changed`
  * `customers_score_changed`

  The old ambiguous `migrants`, `fds_closed`, `fds_repriced` and `migrants_with_closures` are removed.
* **Register:**
  * conditional rule wording;
  * `competitor_pass_through_use = 'context only; not used in the transformation'`;
  * `pass_through_note` (the approved competitor sentence);
  * `transaction_response` (input values held constant; scenario SHAP not computed).
* `backend/churn_backend/drift.py`:
  * `compare()` adds `reference_available`, `current_available` (non-missing counts) and `reading`;
  * `reading(0)` is "No shift";
  * the KS docstring explains why there are no p-values (paired copies). The "n = 1,000 makes tiny shifts significant" claim is removed.
* `scripts/local_session.py`: the default `TXB_SCENARIO_DIR` is now `artifacts/m7-scenarios/m7-opr-2`.
* `tests/test_opr_scenarios.py`: the register pin, the existing maturity test on the new counters, **the three review probes as fixtures**, a non-assigned repricing probe, and real-data count consistency.
* `backend/tests/test_drift_scenarios.py`: a coverage/reading test for `compare()`.

### A3 — Scenario-package contract (`backend/churn_backend/scenarios.py`)
* `load()` validates the full contract before `ready`:
  * object/list types;
  * scenario ids exactly `no_shock, mild, severe`;
  * all 78 predictor keys;
  * every PSI/KS/missing-share/availability field (finite, bounded, coverage reconciles);
  * count relationships (assigned ≥ eligible ≥ affected, …);
  * `changed_features` consistent with the drift;
  * flagged = saved + into − out;
  * the flagged-only view;
  * the no-shock reference unchanged;
  * gates (parity zero, reproduction ≤ tolerance, 0 flag mismatches);
  * register shape and agreement with the scenarios;
  * `scores.csv` header, coverage (3 × customers, same customers per scenario, no duplicates, values in range) and per-scenario flagged totals.
* `safe_load()` also maps `AttributeError`, `TypeError`, `UnicodeError` and `IndexError` to `invalid`. A manifest of `[]` is now `invalid`, not a 500.
* `NOTE` is the approved sentence.
* **Shared representative fixture:** `backend/tests/make_opr_fixture.py` builds `backend/tests/fixtures/opr_package/` (synthetic, 8 customers, built with the real `drift.compare` and `REGISTER`) and `frontend/tests/fixtures/opr-scenarios.json`. The backend test asserts that `load()` on the package returns **exactly** the frontend fixture.
* `.gitattributes`: the hash-checked fixture files keep exact bytes on every platform.
* `backend/tests/test_drift_scenarios.py`:
  * the old minimal "valid package" (which the review showed was unrenderable) is replaced by the shared fixture;
  * 16 targeted malformed packages, plus malformed JSON text.

### A5 — OPR wording (`frontend/src/pages/ResearchPreview.jsx`)
This is a minimal Phase A update; Phase C redesigns the page.
* `DEPOSIT_ONLY` is the approved three-sentence text.
* New `PASS_THROUGH` (the approved sentence) and `KS_NOTE` (paired copies, no p-values).
* The weighted-rate coverage note is built from the package counts.
* "Customers assigned to exit at maturity" and "Actually affected in the window" are separate columns, plus customers whose score changed, with a sentence explaining the denominators.
* Scope line: "Performance not evaluated: hypothetical outcomes are unavailable."
* The local PSI wording function is removed (the backend supplies `reading`).
* `frontend/tests/opr-scenarios.test.jsx`: new assigned-vs-affected/coverage test; exact performance text; stronger bans.

### A4 — CI portability
* `scripts/local_session.py`: `runtime_paths(root)`:
  * Windows: `.venv\Scripts\python.exe` and the existing Node default, so Windows usage is unchanged;
  * elsewhere: `.venv/bin/python`, with Node from `PATH`;
  * `TXB_NODE_EXE` wins on every platform.
* `tests/test_local_session.py`:
  * the mocked launch test patches the resolver and checks that a missing runtime still stops the launch;
  * new explicit Windows/POSIX/override resolution tests;
  * a test that the default package is m7-opr-2.

### A6 — Documentation
* `docs/ROADMAP.md`:
  * a **current status table** with the columns implemented / automated verification / owner acceptance (quoted from the milestone notes; **nothing newly ticked**) / production readiness;
  * M7 wording corrected;
  * render-7 / m6-evidence-6.
* `PRODUCT.md`, `README.md`: no longer call OPR a "design preview" or "later work". README no longer states stale test counts.
* `docs/LOCAL_DATABASE_WORKFLOW.md`: the runbook states that verified OPR rates end on **10 Jul 2024**, so later assessments show Finance contribution as unavailable (fail-closed), and that `m7-opr-2` is the default package.
* **UI reason:** the existing "Not provided: …" list on the customer Finance tab now shows the backend reason including the end date.

## Every changed assertion and why
1. `backend/tests/test_finance_metrics.py:112`: `'OPR not verified for this cutoff'` → `'OPR not verified for this cutoff (verified rates end 10 Jul 2024)'`. **Why:** A6 requires the end date in the reason. Still exact `assertIn` on the list.
2. `backend/tests/test_ai_render.py:254`: `evidence.VERSION == 'm6-evidence-5'` → `'m6-evidence-6'`. **Why:** the approved terminology change alters the evidence label.
3. `backend/tests/test_ai_render.py` lines 67, 70, 73, 119, 121, 133, 241, 245, 255, 265, 268: the exact expected sentences and labels now say "combined flow" / "Combined flow" instead of "transaction value". **Why:** the approved rename. The sentences are otherwise identical. The 263-word card pin is unchanged: both terms are two words.
4. `backend/tests/test_drift_scenarios.py`:
   * `assertIn('main drivers do not move', body['note'])` → exact equality with the approved sentence plus `assertNotIn('main drivers', …)` on the whole payload;
   * version `'m7-opr-1'` → the shared fixture;
   * the minimal valid-package fixture is replaced by the representative one.

   **Why:** review findings 3 and 5. The replacement assertions are stricter.
5. `tests/test_opr_scenarios.py`:
   * version pin `'m7-opr-1'` → `'m7-opr-2'`;
   * `(fds_maturing_in_window, fds_closed, fds_repriced) == (2, 1, 1)` → `(fds_maturing_in_window, exit_affected_fds, repriced_fds) == (2, 1, 1)` plus the new counters;
   * the no-shock `fds_closed + fds_repriced == 0` → `exit_affected_fds + repriced_fds + cells_changed == 0`.

   **Why:** the approved count semantics. Same values on the original fixture.
6. `tests/test_local_session.py` launch test: it previously depended on the real `.venv\Scripts\python.exe` and Node path, which fail on Linux. It now patches `runtime_paths` and asserts the spawned commands use the resolved paths. **Why:** finding 4. Resolution is tested explicitly in `RuntimePathTests`.
7. `frontend/tests/opr-scenarios.test.jsx`:
   * performance text `toMatch(/^3\. Performance changeNot computed\./)` → exact `toBe(...)` with the approved scope line;
   * `BANNED` extended with `main drivers`, `significant` and `p-value` (except "p-values, because" in the explanation).

   **Why:** A5. Stricter.
8. Test data only (not assertions): the `frontend/tests/ai-drafts.test.jsx` basis string and `frontend/tests/fixtures/briefing.json` now say "Combined flow".

## Commands run and actual outputs

**April check B before/after** (read-only: `file:artifacts/m6-review.sqlite?mode=ro`; old vs new `finance_metrics.py` on the 1,000 April features):

| Cost ratio | 1.0 | 0.75 | 0.5 |
|---|---|---|---|
| Customers flagged, earlier rule (non-policy) | 314 | 275 | 196 |
| Customers flagged, owner rule (non-policy) | **314** | **275** | **195** |
| Uncovered a month, earlier rule | RM828,703.31 | RM462,232.94 | RM164,385.92 |
| Uncovered a month, owner rule | RM826,316.33 | RM459,845.97 | RM161,998.95 |

* Policy-exempt B is unchanged (95; RM3,792,166.15). Check A is unchanged (165). Customers with negative FD earnings: 8.
* Script output: `RaR totals and every sensitivity RaR identical: True`. This covers the total, both bases and every cost and premium sensitivity column.
* Base RaR, unchanged:

  | Group | Base | Cost 0.75 / 0.5 | Premium 0% / 1.0% |
  |---|---|---|---|
  | All customers | −5,964,429.65 | +416,108.56 / +6,796,646.77 | −9,508,639.56 / −2,420,219.74 |
  | Deposit-condition (FD-threshold) | +878,485.68 | | |
  | Policy-exempt | −6,842,915.33 | | |

**m7-opr-2 generation** (`C:\Users\fikri\fyp-model-env\Scripts\python.exe -I -B scripts\opr_scenarios.py --research-root <R> --test-db artifacts\m6-review.sqlite --out artifacts\m7-scenarios\m7-opr-2`, 67 s):
```
Parity gate: exact for 11 account-derived predictors
Reproduction gate: {"max_abs_raw_difference": 0.0, "max_abs_risk_difference": 0.0, "flag_mismatches": 0, "saved_flagged": 206, "tolerance": 1e-12}
```
The research-listing gate passed: the run would stop before writing if the folder changed.

| | No shock | Mild +25 bp | Severe +125 bp |
|---|---:|---:|---:|
| Assigned to exit at maturity (of 398) | 0 | 20 | 80 |
| Eligible: assigned customers with an FD maturing Mar–Apr (FDs) | 0 (0) | 9 (11) | 42 (59) |
| Actually affected customers (FDs closed) | 0 (0) | **8 (10)** | **41 (58)** |
| Repriced FDs / customers | 0 / 0 | 320 / 221 | 272 / 188 |
| In-window FDs with no ACTIVE post-maturity row (baseline closure preserved) | 9 | 9 | 9 |
| FDs with a missing post-maturity snapshot | 0 | 0 | 0 |
| Cells changed | 0 | 495 | 613 |
| Customers whose score changed | 0 | 11 | 49 |
| Flagged (saved 206); into / out of review | 206; 0 / 0 | 206; 0 / 0 | 206; 0 / 0 |
| Mean risk (saved 16.097792%) | 16.097792% | 16.098270% | 16.091526% |
| Score PSI / KS | 0 / 0 | 0.000080 / 0.001 | 0.000180 / 0.007 |
| Predictors changed | 0 | 9 | 9 |
| Largest input PSI (weighted FD offer rate) | 0 (No shift) | 0.0242 (Little shift) | **0.3258 (Large shift)** |
| Weighted FD rate compared on (non-missing) | 384 → 384 | 384 → 376 | 384 → 344 |

* **Old vs new counters:**
  * m7-opr-1 reported "customers with closures" 9 / 42 and "FDs closed" 11 / 59. Those were the *eligible* counts.
  * Actual changes are 8 customers / 10 FDs (mild) and 41 / 58 (severe). The difference is the review's "already closed" case, which occurs in the real data: 9 in-window FDs have no ACTIVE post-maturity row.
* **`scores.csv` is byte-identical to m7-opr-1** (sha256 `1459a492…6b8`). The over-counting affected only the counters, not the transformed cells or the scores.
* **Determinism:** a second run to a scratch folder gave byte-identical `manifest.json`, `drift.json` and `scores.csv`.
* **m7-opr-1 untouched:** `sha256sum -c` gives OK for all 3 files.
* m7-opr-2 sha256: `manifest.json 247281f8…d7d7`, `drift.json 9d03e75b…de41`, `scores.csv 1459a492…e6b8`.
* `scenarios.load()` gives `ready` for m7-opr-2. m7-opr-1 is `invalid` under the stricter contract (it predates the new fields); it stays on disk as prior evidence.

**Generator tests in fyp-model-env** (`TXB_RESEARCH_ROOT=<R> fyp-model-env\Scripts\python.exe -I -B tests\test_opr_scenarios.py -v`): `Ran 13 tests in 93.597s — OK`. This includes RealDataTests, which run the generator twice: gates, byte-identical packages, no-shock reference, count consistency and deposit-only inputs.

**Full check, Windows** (`.\.venv\Scripts\python.exe scripts\check.py`, exit 0):
* backend `Ran 201 tests — OK (skipped=1)`;
* utility `Ran 31 tests — OK (skipped=11)` (the pandas/scipy/real-data generator tests run only in fyp-model-env, above);
* Node `tests 10, pass 10, fail 0`;
* React `Test Files 13 passed, Tests 109 passed`;
* build `✓ built in 409ms`.

**Full check, clean Ubuntu 24.04 container** (`git archive` of `fa40d39` into `mcr.microsoft.com/devcontainers/base:ubuntu-24.04`, Python 3.12.3 from apt over HTTPS, Node v24.22.3 checksum-verified from nodejs.org, `pip install -r requirements.txt`, `npm ci`, `python scripts/check.py`; exit 0):
```
== PRETTY_NAME="Ubuntu 24.04.3 LTS" | Python 3.12.3 | node v24.22.3 | commit fa40d39
Running: /ci/bin/python -m unittest discover -s tests -v   -> Ran 201 tests ... OK (skipped=1)
Running: /ci/bin/python -m unittest discover -s tests -v   -> Ran 31 tests ... OK (skipped=11)
Running: npm test   -> tests 10, pass 10, fail 0; Test Files 13 passed (13), Tests 109 passed (109)
Running: npm run build   -> ✓ built in 293ms
```
* The plain `ubuntu:24.04` image could not be used: its port-80 apt mirrors returned 403 on this network.
* Docker Desktop was started for this run.
* The GitHub workflow itself was not triggered (it runs on PRs and on pushes to `main`).

## What you need to do

1. **Re-run the summary batch live (render-7 + m6-evidence-6 change the cache keys and evidence hashes).** Stored summaries show as changed evidence until you do. In your key-holding terminal, from the repository root:
   ```PowerShell
   .\.venv\Scripts\python.exe scripts\generate_summaries.py --batch-id bf0e828cdd426ae496ff36bd207acfcd02dccd928eebd14eea5027ce45c9204a --dry-run
   .\.venv\Scripts\python.exe scripts\generate_summaries.py --batch-id bf0e828cdd426ae496ff36bd207acfcd02dccd928eebd14eea5027ce45c9204a --limit 5 --keep-rejected
   ```
   Repeat the second command to continue. Phase B builds the demo database only **after** this re-run.
2. Inspect the OPR page with m7-opr-2 (`.\.venv\Scripts\python.exe scripts\local_session.py m6-test --backend-port 5066 --frontend-port 5186`, then Help & previews → OPR). The launcher now defaults to m7-opr-2.
3. To regenerate the shared OPR fixture after a contract change: `.\.venv\Scripts\python.exe -B backend\tests\make_opr_fixture.py`.

## Open questions
* None blocking.

## Known limitations
* The OPR page is updated only for correctness and wording here. Its layout is redesigned in Phase C.
* m7-opr-1 is not displayable under the new contract. It is kept as prior research evidence, not migrated.
* The Ubuntu run used a devcontainer Ubuntu image with HTTPS apt mirrors, because port-80 mirrors are blocked locally. The remote GitHub Actions run on this branch is not yet confirmed.
* Check B remains an assumption-based estimate (cost proxy, OPR as a funding proxy); see `docs/FINANCE_METRICS.md`.
