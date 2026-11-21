# Milestone 7 review — OPR stress demonstration

Reviewed branch: [FikriNizan/FYP, milestone-7](https://github.com/FikriNizan/FYP/tree/milestone-7)  
Reviewed commit: `4bdc69408173cb16f538d73c4270a0142adf8431`  
Review date: 21 November 2026, Malaysia time  
Scope: read-only source, documentation, automated checks and independent small-fixture probes. No application source edits, commits, pushes, real database changes or live Gemini requests.

## Recommendation

Freeze **new feature scope** now. Complete a short correctness and wording pass before treating the implementation as frozen, then proceed to UI refinement.

The OPR architecture is appropriate for a bounded research demonstration: assumptions are explicit; hypothetical scenarios are separated from saved assessments; the frozen model is reused; and performance is not claimed without scenario outcomes. The remaining issues concern the maturity rules, the meaning of counts, package validation, CI portability and the strength of some explanations. They do not require a new model or a large redesign.

This review is not a production-readiness certification. The repository itself describes a local research application, and the roadmap still leaves deployment-specific work open.

## Findings to resolve before implementation freeze

### 1. Maturity transformations and counters do not fully implement the stated renewal rule

**Location:** [scripts/opr_scenarios.py, apply_scenario](https://github.com/FikriNizan/FYP/blob/4bdc69408173cb16f538d73c4270a0142adf8431/scripts/opr_scenarios.py#L243), assumption register at line 49.

The register says an eligible non-migrant FD renews at maturity. The implementation only adds a rate increment to each matching monthly row. It does not require those rows to be ACTIVE, and it does not implement a renewal state transition.

The exit branch increments `fds_closed` and adds the customer to `migrants_with_closures` even when no post-maturity rows exist or when those rows were already CLOSED with zero balances.

Independent probes used an FD active in January, with a January-recorded maturity of 15 March:

| Probe | Observed result |
|---|---|
| Baseline March/April rows already CLOSED and zero; customer assigned to exit group | Reports 1 FD closed and 1 customer with closure, but changes **zero cells** |
| Same baseline; customer not assigned to exit group | Reports 1 FD repriced; April remains CLOSED and zero, with only the rate changed |
| January/February rows only; no post-maturity rows | Reports 1 FD closed and 1 customer with closure, but changes **zero cells** |

These establish edge-case defects and a register/code mismatch. The original account snapshots are absent from the repository, so this review cannot quantify how often these cases occur in the real scenario run.

**Required refinement:**

- Define whether the scenario preserves baseline closures or explicitly overrides them with renewal.
- A conservative, small change is to preserve baseline closure history, reprice surviving eligible active FDs, and update the register to describe that conditional rule.
- If automatic renewal is intended instead, define its principal, renewed status, rate and subsequent maturity explicitly. Do not silently resurrect closed accounts.
- Distinguish eligibility, assigned behaviour, actual transformed records and incremental changes relative to the baseline.
- Count distinct accounts/customers only when the defined event really occurs. Missing required snapshots should have an explicit treatment.
- Add fixtures for already-closed accounts, absent post-maturity rows and non-migrant renewal.

Version and regenerate the scenario package after a change to transformation or count semantics. Preserve the existing package as prior research evidence; do not overwrite saved predictions or the Working database.

### 2. “Customers who move deposits” displays assigned customers, not demonstrated movements

**Location:** [ResearchPreview.jsx, PredictionChange](https://github.com/FikriNizan/FYP/blob/4bdc69408173cb16f538d73c4270a0142adf8431/frontend/src/pages/ResearchPreview.jsx#L53); generator result fields at line 332.

The page displays `migrants`: the seeded selection from the 398-customer January cohort. Maturity restrictions mean some selected customers cannot exit during the March–April simulation window.

The committed fixture contains:

| Scenario | Assigned exit group | Reported customers with eligible closures | Reported FDs closed |
|---|---:|---:|---:|
| Mild | 20 | 9 | 11 |
| Severe | 80 | 42 | 59 |

The closure columns above are the **current package’s counters**, not independently verified incremental withdrawals; finding 1 means those counters also need reconciliation.

**Required refinement:** Label 20/80 as “Customers assigned to exit at maturity”. Display separately the customers and FDs actually affected within the window, using corrected counters. Explain the different denominators. Do not simply replace one ambiguous count with another.

### 3. Scenario-package validation can accept an unusable package or raise an uncaught exception

**Location:** [backend/churn_backend/scenarios.py](https://github.com/FikriNizan/FYP/blob/4bdc69408173cb16f538d73c4270a0142adf8431/backend/churn_backend/scenarios.py#L28), existing package tests in `backend/tests/test_drift_scenarios.py`.

File hashes and recorded gates are useful, but they do not establish the required shape of the payload.

Independent probes showed:

- A manifest containing JSON `[]` raises an uncaught `AttributeError`, rather than returning the intended `invalid` state.
- A hash-consistent package with one incomplete no-shock scenario, no `register.scenarios`, and a header-only scores CSV is returned as `ready`. The frontend then assumes the missing register scenarios and prediction-change objects exist.
- The existing “valid package” backend test uses this incomplete structure, so backend and frontend tests do not jointly enforce a renderable contract.

**Required refinement:** Validate the full supported package contract before returning `ready`: object/list types, required scenario IDs, required predictor keys and metrics, finite numbers, sensible bounds, consistent counts and gate fields. Validate the scores CSV coverage and scenario/customer keys as part of package validation, and reconcile summaries where practical. Handle malformed nested types as `invalid`. Use a shared representative valid fixture and targeted malformed-package tests.

This is a local package reliability issue. It does not require a new authentication system or cryptographic signing infrastructure.

### 4. The current full check is not portable to its configured CI runner

**Location:** [scripts/local_session.py, launch](https://github.com/FikriNizan/FYP/blob/4bdc69408173cb16f538d73c4270a0142adf8431/scripts/local_session.py#L125), `tests/test_local_session.py` line 84, [.github/workflows/ci.yml](https://github.com/FikriNizan/FYP/blob/4bdc69408173cb16f538d73c4270a0142adf8431/.github/workflows/ci.yml).

The launcher requires `.venv/Scripts/python.exe` and defaults to a Windows Node path. The launcher unit test checks those real paths before its mocked subprocess calls. GitHub CI uses Ubuntu, installs Python globally and does not create that Windows environment.

The independent Linux run reached this exact failure:

```text
test_launch_routes_both_children_to_one_test_database_and_stops_them
ValueError: Local Python, Node or Vite is missing; install the existing project dependencies
```

**Required refinement:** Make runtime resolution portable, or isolate Windows-specific launch-path checks from the mocked unit test while testing them explicitly. Preserve Windows usage. Then obtain a green full check on a clean Ubuntu checkout.

The workflow runs for pushes to `main`, pull requests and manual dispatch; a push to `milestone-7` alone does not trigger it. This issue predates the OPR changes but matters before declaring the project checks complete.

### 5. Replace claims about unchanged model drivers with claims about unchanged input values

**Locations:** `ResearchPreview.jsx` line 10, `scenarios.py` line 17, the M7 handoff and roadmap.

Current copy says that transaction/digital/friction inputs are unchanged, “so the model’s main drivers do not move”.

Unchanged feature values do not guarantee unchanged SHAP contributions in an interacting model. The generator explicitly scores without recalculating SHAP. The experiment also does not establish that these inputs are always the main drivers for every customer.

**Suggested replacement:**

> This scenario changes deposit-related inputs only. Transaction activity, digital engagement and service-friction input values are held constant. Scenario-specific SHAP explanations are not computed.

This corrects the claim without adding scenario SHAP as a new feature.

### 6. Clarify what competitor pass-through does

**Location:** assumption register and `apply_scenario`.

The displayed 100% competitor pass-through is metadata; it is not used by the transformation. Own-bank pass-through changes FD rates. Customer exit shares are independently imposed at 5% and 20%.

That is acceptable as an illustrative scenario, but users could otherwise infer a calculated customer-response model.

**Required clarification:**

> Own-bank pass-through affects the simulated FD offer rate. Competitor pass-through provides scenario context. Exit shares are separate illustrative assumptions, not estimated responses to the rate gap.

There is no need to invent a migration formula to finish this milestone.

## What the current results establish

The checked-in frontend fixture and handoff report these figures. They are internally inspectable evidence, not a new independent full-data scoring replay:

| Measure | No shock | Mild: +25 bp | Severe: +125 bp |
|---|---:|---:|---:|
| Mean model output, probability scale | 16.097792% | 16.098270% | 16.091526% |
| Customers whose score changed | 0 | 11 | 49 |
| Customers flagged | 206 | 206 | 206 |
| Customers crossing into/out of review | 0 / 0 | 0 / 0 | 0 / 0 |
| Score-distribution KS | 0 | 0.001 | 0.007 |

Nine of 78 predictors change in the reported run. The largest input PSI is about 0.326 for the severe FD weighted-offer-rate scenario. Transaction-flow, digital and friction inputs are held fixed.

A defensible finding is:

> Under the specified maturity-constrained deposit scenario, some deposit inputs shift substantially, while the frozen model’s score distribution changes little and no customer crosses the saved review boundary.

It does **not** establish that:

- OPR causes the assumed customer movements;
- deposit exit causes the project’s transaction-volume attrition target;
- model accuracy improves or deteriorates under the shock;
- the model is robust to all OPR changes or economic disruption;
- the frozen calibration remains valid under the hypothetical shifted distribution.

The severe mean score decreasing slightly is not, by itself, a bug. A fitted predictive association need not be a monotonic causal response to an economic shock. Keep the result and explain its scope; do not alter assumptions simply to produce a larger adverse effect.

The project target is a drop in combined transaction flow. FD balances and payment activity are related business contexts, but they are not the same outcome. Keeping payment activity fixed makes this a deliberately narrow **deposit-input sensitivity demonstration**, rather than a full macroeconomic or customer-behaviour simulation.

## Research justification

Your original motivation has relevant support beyond internship experience:

- **BNM Financial Stability Review, second half 2023, printed page 30:** discusses deposit competition and corporate rate-hunting in relation to expectations that OPR increases had peaked. This supports the plausibility of a competition/deposit-response channel. [Primary report](https://www.investmalaysia.gov.my/media/533dzt0l/bnm-financial-stability-review-2h2023.pdf)
- **Tang, Puah and Liew (2015), “The Interest Rate Pass-Through in Malaysia: An Analysis on Asymmetric Adjustment”:** finds incomplete pass-through and asymmetric adjustment using Malaysian data from January 1987 to December 2014. This supports considering incomplete adjustment. It does not calibrate this application’s corporate exit shares. [Author institutional repository and abstract](https://ir.unimas.my/id/eprint/18008/)
- **BNM, 24 January 2024:** maintained OPR at 3.00%, supporting the application’s treatment of the February hike as hypothetical rather than a historical event. [Statement](https://www.bnm.gov.my/-/monetary-policy-statement-24012024)

These sources do not establish the particular 50%/100% pass-through rates, one-month lag or 5%/20% exit assumptions. Keep those explicitly illustrative. The +125 bp severe case compresses a cumulative-cycle-sized change into the chosen hypothetical shock; it is not a claim that BNM made a single +125 bp hike in February 2024.

## Metric wording and coverage

Keep the separation between input shift, score change and performance. That is one of the implementation’s strongest choices.

Two explanations need adjustment:

1. The statement that 1,000 observations makes even tiny changes statistically significant is too broad. These are paired baseline/counterfactual observations, not independent samples. Reporting descriptive KS distances without p-values is reasonable; explain that choice directly. [SciPy’s standard two-sample test assumptions](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.ks_2samp.html)
2. PSI 0.10/0.25 readings are conventions, not validated pass/fail limits for this scenario. This is already acknowledged and should remain so. [Yurdakul (2018)](https://scholarworks.wmich.edu/dissertations/3208/)

PSI includes a missing-value bin, while numeric KS excludes missing values. For the weighted FD rate, missingness rises from 61.6% to 62.4%/65.6%; the KS comparisons therefore concern 384 baseline non-missing customers versus 376/344 scenario customers. Explain this coverage in expandable details. A customer losing all FD balances can make its weighted rate legitimately undefined; it is not automatically a data defect.

## Wider-project issues to carry into the content pass

### Finance numbers are assumption-based contribution measures

The deterministic Finance layer documents its assumptions and exposes sensitivity, which is useful. However:

- `bnm_base_fee` is used as a transaction-cost proxy, not verified bank wholesale cost.
- OPR plus a liquidity premium is used as a funding-value proxy.
- Three times monthly estimated relationship contribution is called Revenue at Risk; it is not expected monetary loss or a causal estimate of retention savings.
- The documentation itself reports that the April aggregate’s sign changes across the selected cost assumptions.

Use visible labels such as “Assumed transaction cost” and “Estimated funding contribution”. Keep the assumptions and sensitivity accessible where the prioritisation decision is made. A documented customer price cap does not, by itself, prove the proxy overstates real cost; describe the direction of bias as uncertain without actual cost data.

Finance check B also deserves a wording/policy check: because it uses `max(0, cost − fee)`, a negative FD contribution can trigger the check even when fee income already covers transaction cost. An independent probe with RM100 fee income, RM72.14 assumed transaction cost and −RM20 FD contribution still reported RM20 under check B, despite a positive total monthly contribution of RM7.86 and zero transaction shortfall. Decide whether this means “negative FD funding contribution” or an uncovered transaction subsidy; the present label does not distinguish these cases. Do not silently redefine the business rule during aesthetic work.

The verified OPR lookup currently ends on 10 July 2024. Later uploaded assessments can therefore have unavailable Finance contribution measures until verified rate coverage is extended. This is deliberate fail-closed behaviour, but should be clear in the runbook and UI.

### Documentation needs one current status

`PRODUCT.md` still describes OPR calculations as design previews/unestablished and says live-provider acceptance is pending, while newer handoffs and the roadmap describe later implementation and M6 closure. Reconcile these statements against actual owner acceptance records. Distinguish implementation, automated verification, owner acceptance and production readiness.

Do not mark earlier milestone acceptance items complete merely because a later feature was added.

## UI refinement after the corrections

Keep the current visual system. Reorganise the OPR page around:

1. **What was assumed?** A compact scenario comparison; the full register behind disclosure.
2. **What changed in deposits?** Assigned customers, eligible/affected customers and deposit changes with clearly stated denominators.
3. **What changed in model output and workload?** Scores, directional changes and boundary crossings; technical PSI/KS tables behind disclosure.

Suitable visual aids:

- grouped bars for assigned versus affected customers;
- a baseline-relative score-change plot with units and sufficient precision;
- compact bars for flagged totals, showing the honest unchanged count of 206.

Do not use a green “healthy/robust” verdict. Do not exaggerate tiny score changes with an unexplained axis. Present “Performance not evaluated: hypothetical outcomes unavailable” as a short scope note, rather than a large empty result section.

These changes can improve understanding without introducing new business features.

## Independent verification

| Check | Result |
|---|---|
| Backend unit tests | 194 run; passed |
| Utility tests | 22 run: 17 passed, 1 failed, 4 skipped |
| Utility failure | Launcher test requires Windows executable paths on Linux |
| Utility skips | Four full-data scenario tests require external research data, frozen champion and Test database |
| Node tests | 10 passed |
| React tests | 108 passed |
| Production build | Passed |
| Targeted independent probes | Reproduced maturity/counter and package-contract issues above |
| Source worktree | No tracked changes |
| Live Gemini requests | None |
| User databases | Not available here; none changed |

The first backend attempt encountered a review-environment SOCKS-proxy dependency issue during a mocked SDK test. Clearing proxy variables for the offline test process resolved it; all 194 backend tests then passed. The remaining full-check failure is the repository’s launcher-path test described above.

The repository omits the original research tables, champion artifact, named Test database and generated scenario package. Consequently, this review did not independently rerun the reported exact 1,000-customer parity/scoring/determinism gates. Those are documented owner-side results. Re-run them after correcting and versioning the scenario logic.

## Completion checklist

- [ ] Align maturity transformations, renewal wording and event counts.
- [ ] Separate assigned exit group from customers actually affected within the horizon.
- [ ] Enforce a renderable scenario-package contract and clean invalid state.
- [ ] Restore a green full check on the Ubuntu CI configuration.
- [ ] Correct unchanged-driver, competitor-response and KS wording.
- [ ] Resolve Finance check B interpretation and proxy labels.
- [ ] Reconcile product documentation with accepted implementation status.
- [ ] Generate a new versioned scenario package and repeat owner-side parity, reproduction and determinism checks.
- [ ] Inspect the resulting OPR page manually using that package.
- [ ] Freeze implementation, then proceed with UI/content refinement.

