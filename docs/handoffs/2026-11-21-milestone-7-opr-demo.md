# Handoff: Milestone 7, OPR shock drift demonstration (21 November 2026)

## Branch and commits
Branch **`milestone-7`**, created from `summary-rejections` at `4455b2f`. Pushed; no force-push, no merge into `main`, and no co-author or session trailers.

| Commit | Content |
|---|---|
| `624750d` | Finance tab headings: "Check A · fee waiver condition" / "Check B · deposits vs waived cost" (separate small change) |
| `cd5beba` | `drift.py`: PSI and KS (stdlib only) with hand-checked tests |
| `4827464` | `scripts/opr_scenarios.py` generator and its tests |
| `5b5a810` | `GET /api/scenarios`, the read-only `/research` view, session wiring, tests |
| docs commit (contains this file) | `CLAUDE.md` rule 2 exception line, `ROADMAP.md`, this handoff. Its SHA is the branch head: `git log -1 milestone-7` |

**What this is:** an assumption-based synthetic stress demonstration. It is **not** a forecast of BNM policy, not evidence of customer behaviour, and not a performance evaluation.

## The finding (narrow, as required)
**This scenario changes deposit-related inputs only. Collections, payments, digital and friction inputs are unchanged by assumption, so the model's main drivers do not move.** Of the 78 predictors, 69 are unchanged by design: 67 that no FD rule can reach, plus `non_fd_balance_myr` and `fd_maturing_30d_count`, which no rule changed in this window.

Under an FD-only hike with these assumptions:
- **Deposit inputs:**
  - `fd_balance_weighted_offer_rate` drifts the most: PSI **0.024** (mild) and **0.326** (severe; above the 0.25 convention); KS 0.114 / 0.404.
  - The other 8 changed deposit inputs have PSI ≤ **0.032** (severe `fd_balance_change_3m_vs_previous_3m`).
- **The score distribution** moves by PSI **0.00008** / **0.00018** and KS **0.001** / **0.007**.
- **Workload:** no customer crosses the frozen review boundary in either direction, so the flagged count stays **206** in every scenario.

Performance change is **not computed**, because no outcomes exist under a hypothetical shock. PSI and KS only show whether the data look different from the reference; they say nothing about model performance either way.

## Final assumption register (`m7-opr-1`, seed 20240430)
| Item | No shock | Mild | Severe | Basis |
|---|---|---|---|---|
| OPR change | 0 | +25 bp | +125 bp | BNM moves in 25 bp steps. +125 bp is the 2022–23 cycle (1.75% → 3.00%) and the size of the 2020 easing (−125 bp; largest single move −50 bp on 5 May 2020). Sources: https://www.bnm.gov.my/monetary-stability/opr-decisions; https://www.bnm.gov.my/-/monetary-policy-statement-05052020; …-11052022; …-03052023 |
| Direction | — | hike | hike | Migration needs only incomplete own pass-through relative to a competitor (Tang, Puah & Liew 2015; Drechsler, Savov & Schnabl 2017; BNM FSR 2H2023 p.30). A cut needs faster or deeper own cuts, against documented downward rigidity |
| Effective date / lag | — | 1 Feb 2024 / 1 month | same | Hypothetical (the real OPR held at 3.00%). Repricing starts 1 Mar 2024 |
| Pass-through | — | own 50%, competitor 100% | same | Rate gap facing customers 12.5 / 62.5 bp |
| Cohort | — | active FD on 31 Jan 2024 (pre-shock): **398** customers | same | |
| Migrating share | 0 | 5% → **20** customers | 20% → **80** customers | Illustrative and fixed before any result. One seeded shuffle, so the mild migrants are a subset of the severe ones |
| Renewal rule | — | **maturity-only** | same | An FD reprices or closes only at its maturity (as shown in the Jan 2024 snapshot) between 1 Mar and 30 Apr 2024. **No early withdrawal is assumed** |
| Migrants | — | each FD maturing in the window is closed from its maturity (status CLOSED, balances 0) | same | Mirrors the generator's own closure |
| Non-migrants | — | each FD maturing in the window renews at its offer rate + 50% × shock | same | |
| Transaction response | off | off | off | Your decision |
| Fees and waivers | unchanged | unchanged | unchanged | |

## FD maturity counts and migrants (recon, read-only)
- **Maturity dates:** every FD row has one (50,640 FD rows, 0 missing).
- **Active FDs at each snapshot:**

  | Snapshot | Active FDs | Holders |
  |---|---|---|
  | 31 Jan 2024 | 577 | 398 |
  | 29 Feb 2024 | 570 | 393 |
  | 31 Mar 2024 | 563 | 388 |
  | 30 Apr 2024 | 555 | 384 |

- **Maturing in the window (FDs active on 31 Jan):** February 0; March **145** FDs (107 holders); April **194** FDs (127 holders). In total **339 FDs, 234 holders**. That is not "almost none", so the scenario is maturity-only.
- **Synthetic-data property:** FDs roll over about every 3 months whatever the product, and `rate_offer` is redrawn every month.

| Scenario | Migrants (of the 398 cohort) | Of them, April FD holders (of the 384) | Migrants with an FD closed | FDs closed | FDs repriced |
|---|---|---|---|---|---|
| No shock | 0 | 0 | 0 | 0 | 0 |
| Mild | 20 | 18 | 9 | 11 | 328 |
| Severe | 80 | 75 | 42 | 59 | 280 |

Migrants whose FDs mature after April keep them in this window, because no early withdrawal is assumed.

## Gate results
| Gate | Result |
|---|---|
| Parity: the 11 account-derived predictors recomputed from unperturbed snapshots vs the saved April features (1,000 customers, nulls included) | **exact: 0 mismatches for every feature** |
| Reproduction: frozen champion on unshocked April features vs saved scores | max \|Δ raw\| **0.0**, max \|Δ calibrated\| **0.0** (tolerance 1e-12); flag mismatches **0** (saved flagged 206) |
| Research folder listing (12,693 files: path, size, mtime) during each run | unchanged |
| Determinism | two runs give byte-identical `manifest.json`, `scores.csv` and `drift.json`; the real package is identical to both trial runs |

**The parity gate caught a real issue:** the first mirror started its history in May 2023, and the rolling means then differed by up to 1.5e-8 for 54 / 68 customers. pandas rolling means carry floating-point state along the series. Starting at the coverage start (31 Jan 2020), as the pipeline does, gives exact parity.

## Drift tables
**Input drift** (reference: unshocked April features; changed inputs only; all others have PSI 0 and KS 0):

| Input | Mild PSI | Mild KS | Mild customers changed | Severe PSI | Severe KS | Severe customers changed |
|---|---|---|---|---|---|---|
| active_account_count | 0.0001 | 0.003 | 8 | 0.0027 | 0.021 | 40 |
| active_fd_count | 0.0003 | 0.008 | 8 | 0.0070 | 0.040 | 40 |
| closed_fd_count | 0.0005 | 0.008 | 8 | 0.0091 | 0.040 | 40 |
| fd_average_balance_myr | 0.0003 | 0.008 | 8 | 0.0069 | 0.040 | 40 |
| fd_balance_change_3m_vs_previous_3m | 0.0017 | 0.020 | 8 | 0.0322 | 0.098 | 41 |
| fd_balance_mean_12m_myr | 0.0000 | 0.002 | 8 | 0.0003 | 0.004 | 41 |
| fd_balance_mean_3m_myr | 0.0000 | 0.003 | 8 | 0.0007 | 0.008 | 41 |
| fd_balance_myr | 0.0003 | 0.008 | 8 | 0.0070 | 0.040 | 40 |
| fd_balance_weighted_offer_rate | 0.0242 | 0.114 | 226 | **0.3258** | **0.404** | 226 |

The missing share of `fd_balance_weighted_offer_rate` rises from 0.616 to 0.624 (mild) and 0.656 (severe), because closed FDs leave customers without an FD balance.

**Prediction change** (reference: saved April scores):

| Scenario | Score PSI | Score KS | Customers whose score changed | Into review | Out of review | Flagged vs saved 206 | Mean risk |
|---|---|---|---|---|---|---|---|
| No shock | 0.000000 | 0.000 | 0 | 0 | 0 | 206 | 16.10% → 16.10% |
| Mild | 0.000080 | 0.001 | 11 | 0 | 0 | 206 | 16.0978% → 16.0983% |
| Severe | 0.000180 | 0.007 | 49 | 0 | 0 | 206 | 16.0978% → 16.0915% |

**Flagged-only (secondary):** 206 of 206 stay flagged in every scenario; score KS among them is 0.0049 in the mild and severe scenarios.

**Metric definitions:**
- **PSI:** 10 reference-quantile bins (nearest-rank deciles, duplicate edges merged); one bin per value when there are ≤ 10 distinct values and one per category; a missing-value bin; ε = 1e-4 for empty bins.
- **PSI reading (conventions, not tests):** 0.10 / 0.25. Sources: Siddiqi (2006), *Credit Risk Scorecards*, Wiley; Yurdakul (2018), *Statistical Properties of Population Stability Index*, PhD dissertation, Western Michigan University, https://scholarworks.wmich.edu/dissertations/3208. Its abstract calls these "rules of thumb" used "without reference to Type I or Type II error rates".
- **KS:** the two-sample statistic only, with no p-value, because n = 1,000 makes tiny shifts look "significant" and ties make p-values unreliable.
- **Limitation:** univariate checks miss changes in how features move together.

## What changed and why
| File | Change |
|---|---|
| `frontend/src/components/FinanceMetrics.jsx`, `frontend/tests/finance-metrics.test.jsx` | Headings, `aria-label`s and portfolio rows renamed. The three lookups use the new names, and two exact-heading assertions were added. "Deposits don't cover waived transaction cost" is unchanged. Docs keep "deal broken" / "deal not paying" |
| `backend/churn_backend/drift.py` (new) | Shared PSI/KS module (stdlib only, so the app and the generator use one implementation) |
| `scripts/opr_scenarios.py` (new) | Offline generator (see below) |
| `backend/churn_backend/scenarios.py` (new), `api.py`, `__init__.py` | `GET /api/scenarios` reads the package from `TXB_SCENARIO_DIR`. It checks manifest file hashes and gates, returns `not_generated` / `invalid` / `ready`, and never writes |
| `scripts/local_session.py` | The m6-test session sets `TXB_SCENARIO_DIR=artifacts/m7-scenarios/m7-opr-1` (unless already set) |
| `frontend/src/pages/ResearchPreview.jsx`, `api.js`, `App.jsx`, `Guide.jsx` | `/research` becomes "OPR stress demonstration" (see below) |
| `CLAUDE.md` | Rule 2 exception line, exactly as approved |
| `docs/ROADMAP.md` | First three Milestone 7 items marked done |

**What the generator does:**
1. Reads the April features, the account snapshots and the saved scores, with the Test DB opened `mode=ro`.
2. Runs the parity gate and the reproduction gate.
3. Applies the register to an in-memory copy of the snapshots.
4. Recomputes the 11 predictors with an exact mirror of `feature_engineering_v1.py` (L231-246, L252-258, L351-365, L391).
5. Scores with `load_context` → `model.raw_probability` / `predict_proba`, with no SHAP.
6. Writes `manifest.json`, `scores.csv` (scenario output only) and `drift.json` to a new folder outside any database.

It refuses an existing output folder, and refuses any output inside the research folder.

**What the page shows:**
- the assumption register;
- the three outputs as separate sections;
- the deposit-only statement;
- the caption "PSI and KS show whether the customer data look different from the reference. They do not show whether the model has become less accurate."

The page reuses `featureMeta` labels and the Monitoring table pattern, and nothing is calculated in the browser.

## Tests
**`.\.venv\Scripts\python.exe scripts\check.py`** (exit 0):

| Suite | Before | After |
|---|---|---|
| Backend | 182 | **194** (`OK (skipped=1)`; the skip is the scipy comparison) |
| Utility | 14 | **22** (`OK (skipped=6)`; pandas, real-data and scipy tests need the modelling environment) |
| Node | 10 | **10** |
| React | 104 | **108** (13 files) |
| Build | passed | **passed** (`✓ built in 256ms`) |

**Generator tests in `fyp-model-env`:**
- Command: `& C:\Users\fikri\fyp-model-env\Scripts\python.exe -B -m unittest tests.test_opr_scenarios -v`.
- Result: **Ran 8 tests in 56.969s, OK**, no skips.
- They cover:
  - the register is pinned;
  - seeded nested migrants;
  - the maturity-only rule on a small fixture (no early withdrawal; repricing only from maturity);
  - KS equals `scipy.stats.ks_2samp(...).statistic` on fixtures and random samples;
  - exact gates on real data;
  - byte-identical packages;
  - no shock → PSI 0, KS 0 and the saved scores reproduced;
  - only the 11 deposit inputs can change.

**Changed test assertions:**
- **`workspace.test.jsx`:** "changes only hypothetical OPR inputs and never invents a calculated output" (the disabled assumption form) is **replaced**, because the approved decision removed that form. The new test, "opens the OPR stress demonstration read-only and never invents a calculated output", asserts:
  - the heading and "Not calculated." without a package;
  - one API read and no direct fetch;
  - no number inputs, no "Calculate scenario" button and no table.
- **`finance-metrics.test.jsx`:** the three heading lookups use the new names, and two exact-heading assertions were added.
- No other assertion changed.

**Text guard** (`opr-scenarios.test.jsx`, rendered page and source): no "accuracy", F1, AP, recall, precision, "will fail", "robust", "resilient", "stable to OPR" or "loss". The command `grep -rniE '\bloss' frontend/src` → 0.

## Integrity (before and after; all identical)
| Item | sha256 |
|---|---|
| `artifacts/m6-review.sqlite` | `82b475612b3ae76827c6d81c3e73b97aee5a8fe95b4681dbdd2b4f565ee53daf` (both) |
| `predictions` table dump | `30ab0bb57375defedf99ca968b997740608488d2df7e0d388a91ad0061a598b6` (both) |
| `catboost_baseline_final.joblib` | `3d31eb0cfc36c2a8bb7fb072f9a63664ae2c3a940552c53c0f58ba94394346ec` (both) |
| `frozen_protocol.json` | `6ae6d17ef0dcb7c3b0b7e090bed0dbae475024f5c0606f71ad100411adb5a4dc` (both) |
| `final_policy_parameters.csv` | `121e7223847fa7d79672ccbd298e03481c37f156eec2cadec10fc28c6f0ee56a` (both) |
| Research-folder listing (12,693 files) | `c2de299d8d52607416ab385e41c89b16c3601cf6870c0182ecb3d82fd472887f` (both) |

- The M6 DB hash differs from the earlier `d542…` because of your live summary run before this work started.
- **Package files:** `manifest.json` `b73c2b51…6c86`, `scores.csv` `1459a492…b6b8`, `drift.json` `48240579…33e8`. They are ignored by git and not committed.
- **Untouched:** the Working DB, saved predictions, SHAP and flags. No scenario table exists in any database.

## How you run it
```PowerShell
$R = "C:\Users\fikri\OneDrive - Asia Pacific University of Technology And Innovation (APU)\Degree\SEM 6\Project Module (FYP)\fyp-data-refinement"
$env:PYTHONDONTWRITEBYTECODE = "1"
& C:\Users\fikri\fyp-model-env\Scripts\python.exe -I -B scripts\opr_scenarios.py --research-root $R --test-db artifacts\m6-review.sqlite --out artifacts\m7-scenarios\m7-opr-1
.\.venv\Scripts\python.exe scripts\local_session.py m6-test --backend-port 5066 --frontend-port 5186
```
- **The output folder must be new.** `artifacts\m7-scenarios\m7-opr-1` already exists, so to regenerate, delete it yourself or use another name and set `TXB_SCENARIO_DIR`.
- **Opening the page:** after starting the session, open **Help & previews → OPR · Stress demonstration** (`/research`).

## Open questions
- Should the docs' internal names "deal broken" / "deal not paying" eventually follow the new UI headings?
- **The transaction-response assumption is off.** Turning it on would need its own coefficient and a mirror of the flow features (L272-289). It would change the label path, so it belongs in a new register version.
- Should a February/March reference month also be shown? Scope is currently April only.

## Known limitations
- **Assumptions:** migrating shares and pass-through rates are illustrative assumptions, not estimates. No Malaysian corporate migration coefficient is used.
- **Synthetic data properties:** FDs roll over about every 3 months, and `rate_offer` is redrawn every month. "FDs not maturing keep their rate" therefore means the synthetic monthly rate is left as generated. Interest accrual on renewed FDs is ignored.
- **The mirror covers only the 11 account-derived predictors.** Exact parity proves it matches the pipeline on unperturbed data. The full pipeline was not re-run because it cannot read perturbed copies without breaking its hash checks or writing into the research folder.
- **Univariate PSI/KS** do not capture joint changes. The PSI cut-offs are conventions.
- **Population:** the April 2024 population only. Scenario scores are hypothetical and are not saved predictions.
