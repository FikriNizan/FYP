# Handoff: final tweaks (13 items), 23 November 2026

## Branch and commits

Branch `final-tweaks`, created from `final-refinement @ 2017446`. Pushed; not merged into `main`.

| Commit | What |
|---|---|
| `52763b2` | Approved input: `docs/design/final-tweaks-mockup.html` |
| `3e6fb14` | Phase 1: FD earnings net of SRR, check B "fixed deposits" wording, `render-7` → `render-8` |
| `0a789e4` | Phase 2: UI items 1, 2, 5–13; hermetic backend tests; screenshots |
| (this file) | Handoff |

## What changed, per item

| # | Change | Files |
|---|---|---|
| 1 | The "This assessment decision" dropdown no longer offers "Awaiting review". The "Flagged · awaiting review" tab stays. A URL that still carries `decision=awaiting_review` (or any unlisted value) is treated as "All decisions"; the select and the API query agree, and the page does not break. | `frontend/src/pages/Overview.jsx` |
| 2 | Finance tab breakdown row: "Fixed deposit earnings". | `frontend/src/components/FinancePerspective.jsx` |
| 3 | Check B wording now says fixed deposits everywhere it is shown: card text `fixed deposits don't cover waived transaction cost`; Finance tab "Do fixed deposit earnings cover the waived cost?" with "Fixed deposits don't cover waived transaction cost."; finance picture rows, including the policy text "Waived transaction cost not covered by fixed deposits (policy exemption)". No other backend copy existed: briefings and the PDF use `ai_render`. | `backend/churn_backend/ai_render.py`, `frontend/src/components/FinanceMetrics.jsx`, `FinancePerspective.jsx`, `docs/FINANCE_METRICS.md` |
| 4 | Fixed deposit earnings = `fd × ((1 − SRR) × (OPR + premium) − offer_rate) / 12`, with SRR taken from the dated `SRR_TABLE` (2.0% for all 2024 cutoffs). Missing SRR makes FD earnings unavailable with the reason "SRR not verified for this cutoff". The result is still signed and never clipped, and a zero balance still earns zero. This applies to the base figure and every premium and cost-ratio variant. Check A is untouched. `ai_render.VERSION` goes from `render-7` to `render-8`; the evidence hash and contract `m6-narrative-8` are unchanged. `FINANCE_METRICS.md` has the new formula, rationale, the three SRR sources, the April tables and the card length. | `backend/churn_backend/finance_metrics.py`, `ai_render.py`, `docs/FINANCE_METRICS.md`, `docs/ROADMAP.md` |
| 5 | Monitoring layout: Readiness (full width) → [flags 2×2 \| Follow-up and outcomes] → [Expected vs actual \| Input movement] → Month by month (full width). Panels in a row stretch to equal height (`.row-eq`); one column below 900 px. With no outcomes yet, the callout, Input movement and Month by month each run full width. Data and components are unchanged. | `frontend/src/pages/Monitoring.jsx`, `frontend/src/workspace-architect.css` |
| 6 | The Rate-shock tab opens with a scope note: "Stress test on the April 2024 assessment · 1,000 customers. The month comes from the scenario package, …". `scenarios.load()` now also returns the manifest's `batch_id` and still never touches a database. `/api/scenarios` resolves that batch's month with one read-only `SELECT` (`repo.select_batch`), or returns `assessment: null`, which shows "Stress test on a saved assessment that is not in this database." **N** is `scenarios[0].prediction_change.risk.reference_available`. For the April package (`m7-opr-2`) it is **1,000**, which equals the unique customers in `scores.csv`; `load()` already checks that scores has exactly 3 × N rows. | `backend/churn_backend/scenarios.py`, `api.py`, `frontend/src/components/RateShock.jsx`, `backend/tests/make_opr_fixture.py`, `frontend/tests/fixtures/opr-scenarios.json` |
| 7 | Guide rebuilt to the mockup's "Guide" screen: title and subtitle, the four-step monthly workflow with icons and page badges, four words to know (Contribution at stake ends "Called Revenue at Risk (RaR) in the project report."), three reminders, the two decision example cards with "Example values for explanation only.", and "For data owners: reading Monitoring" (five points, an "Open Monitoring →" link, a closed "Administrator fallback" details element). Four mockup icons (search, message, flag, grid) were added to `Icon.jsx`. `monitoringCopy.js` was deleted; only the Guide imported it. All removed explanatory text (the old steps, "Four different questions", the worked example, every Monitoring note including the Brier note, precision/recall/F1 definitions, and the fallback's `TXB_RESEARCH_ROOT` note) is now in the new **`docs/USER_GUIDE.md`**, linked from the README docs index. **Owner wording change (23 Nov):** the Contribution at stake term reads "An estimate, not a forecast." instead of "…not a forecast loss.", so the existing "never uses the word loss" test stays unchanged. | `frontend/src/pages/Guide.jsx`, `Icon.jsx`, `workspace-architect.css`, `docs/USER_GUIDE.md`, `README.md` |
| 8 | Finance picture subtitle: "Contribution at stake is our Revenue at Risk (RaR): three months of estimated fees, minus assumed transaction cost, plus fixed deposit and operating-balance earnings. An estimate, not audited profit." | `FinanceMetrics.jsx` |
| 9 | "Activity held" → "Not halved" in the matrix header, legend key and follow-up aria-label. The new follow-up hint text is in place. | `Monitoring.jsx` |
| 10 | Follow-up card: title "Follow-up and outcomes"; subtitle "All customers with outcomes · follow-up inside the {window} window"; rows "Follow-up delivered" and "No delivered follow-up recorded". | `Monitoring.jsx` |
| 11 | Operations level word `Usual` → `Typical`. The backend key stays `usual`, and the "Usual (12-month average)" activity row is unchanged. | `OperationsPerspective.jsx` |
| 12 | Signals subtitle gains "Bar length shows relative influence among the signals shown." | `Signals.jsx` |
| 13 | "How to read the lines" is now a closed `<details>` with the same text; the legend and line labels stay visible. | `FlowHistory.jsx`, CSS |
| Added | **Hermetic tests.** `test_unconfigured_environment_still_serves_reads` depended on the caller's shell: with the owner's saved `TXB_RESEARCH_ROOT` and `TXB_MODEL_PYTHON` it actually started the real monthly scorer and got 201 instead of 503. The scorer subprocess reads the research root and writes only to a temp folder; nothing in the research folder changed. The new `backend/tests/hermetic.py` (`unconfigured(self)`) clears every `TXB_*`, `GEMINI_API_KEY`, `GOOGLE_API_KEY` and `CHURN_DB_PATH` for the length of each test, so config falls back to unset. It is called first in every `setUp` that builds an app (13 modules), because GenAI settings are also read from `os.environ` at call time. The named test now also asserts that both settings are `None`. No assertion was removed or loosened. | `backend/tests/hermetic.py`, `backend/tests/test_*.py` |

**Dependency audit.** Before the fix I ran both Python suites with network connections blocked and logged, using a fake key, `TXB_GENAI_ENABLED=1`, and `TXB_*` paths that existed and did not exist. Results: 216 / 216 backend and 35 / 35 utility tests passed, with **zero connection attempts**. The monthly test was the only one whose result changed, and only with a real research root plus model Python.

## Item 4: before and after (April 2024, M6 Test, read-only)

Computed on a scratchpad **copy** of `artifacts/m6-review.sqlite` (batch `bf0e828c…`, 1,000 customers) using `finance_metrics.customer_metrics` and its own `_group` / `_add` aggregation. "Before" is the code at `2017446`; "after" is `3e6fb14`. The before figures reproduce the documented April table exactly.

Owner's estimates: threshold tiers +RM0.88m → about +RM0.63m is **confirmed** (+RM626,596.11). Policy-exempt −RM6.84m → about −RM7.08m is **−RM7,087,215.15**, which rounds to −RM7.09m. The owner's independent deltas (threshold −RM251,890, exempt −RM244,300) agree.

**Revenue at Risk (3 months), base case: cost ratio 1.0, premium 0.5%**

| | Before | After |
|---|---|---|
| Deposit-condition tiers (SME_S, SME_M, CORP_L) | +RM878,485.68 | **+RM626,596.11** |
| Policy-exempt tiers (CORP_XL, GOV) | −RM6,842,915.33 | **−RM7,087,215.15** |
| All customers | −RM5,964,429.65 | −RM6,460,619.04 |

**Cost-ratio sensitivity (premium 0.5%), 1.0 / 0.75 / 0.5**

| | Before | After |
|---|---|---|
| Deposit-condition tiers | +0.88m / +2.84m / +4.79m | +0.63m / +2.59m / +4.54m |
| Policy-exempt tiers | −6.84m / −2.42m / +2.00m | −7.09m / −2.67m / +1.76m |
| All customers | −5.96m / +0.42m / +6.80m | −6.46m / −0.08m / +6.30m |
| Customers with negative RaR | 242 / 160 / 65 | 259 / 173 / 68 |

**Liquidity-premium sensitivity (cost ratio 1.0), 0% / 0.5% / 1.0%**

| | Before | After |
|---|---|---|
| Deposit-condition tiers | −0.92m / +0.88m / +2.68m | −1.14m / +0.63m / +2.39m |
| Policy-exempt tiers | −8.59m / −6.84m / −5.10m | −8.80m / −7.09m / −5.38m |
| All customers | −9.51m / −5.96m / −2.42m | −9.93m / −6.46m / −2.99m |

**Fee subsidy checks**

| | Before | After |
|---|---|---|
| Check B, non-policy, customers (cost 1.0 / 0.75 / 0.5) | 314 / 275 / 195 | 329 / 291 / 205 |
| Check B, uncovered a month (cost 1.0) | RM826,316.33 | RM869,318.19 |
| Check B, uncovered a month (cost 0.75) | RM459,845.97 | RM491,368.43 |
| Check B, uncovered a month (cost 0.5) | RM161,998.95 | RM177,050.03 |
| Check B, policy-exempt (base) | 95 · RM3,792,166.15 | 96 · RM3,865,735.39 |
| **Check A** | 165 · RM335,436.84 | **165 · RM335,436.84 (unchanged)** |
| A and B both (non-policy) | 164 | 164 |
| Customers with negative FD earnings | 8 | 15 |

## Summary batch dry run (zero API calls)

```
Batch bf0e828cdd426ae496ff36bd207acfcd02dccd928eebd14eea5027ce45c9204a | eligible (flagged): 206 | already cached: 0 | to generate: 206 | invalid evidence: 0
Dry run: zero API calls; nothing written.
```

206 to generate, as expected: the render version is part of the cache key.

## Summary card word count

| Cards (April 2024, M6 Test copy) | render-7 min / median / max | render-8 min / median / max |
|---|---|---|
| 206 flagged | 203 / 217 / 240 | 203 / 217 / **241** |
| All 1,000 | 195 / 214 / 240 | 195 / 214 / **241** |

- The new real maximum is **241** words, on customer 72 (the only card at 241). It is one word over the 240 design target; 240 is a target, not a rule. The owner accepted this on 23 Nov 2026, and nothing was shortened.
- The theoretical worst case is **264** words (was 263). The exact pin in `test_longest_theoretical_card_stays_under_its_ceiling_guard` is now 264, and the ≤ 270 ceiling guard is unchanged and passes.

## Tests added or updated

**Backend**
- `test_finance_metrics.test_fd_earnings_formula_nets_srr` (new): exact value, a negative result not clipped, SRR unavailable (reason shown, contribution unavailable), zero balance earns zero, and every premium variant uses the new formula.
- Older tests that used the old formula keep the case they test (zero, −20, covered at 60, partly covered at 8). Their offer-rate inputs were re-derived, and the premium spread expectations are now [−60, 430, 920] and 980.
- `test_drift_scenarios.test_stressed_assessment_month_is_resolved_read_only_from_the_package_batch` (new): `assessment` is null when the batch is absent and its month when present, the database bytes are unchanged, and an empty `batch_id` is invalid.

**React**
- `guide.test.jsx` (new, 6 tests).
- Rate-shock scope note (3 tests).
- Review-queue decision filter (3 tests).
- Signals subtitle and the flow-chart reading note (2 tests).
- Monitoring layout (2 tests).

**Changed labels**
- Monitoring: "Not halved"; the follow-up card title, subtitle, rows, legend and hint.
- Operations: "Typical".
- Finance tab: "Fixed deposit earnings" and the check B question and text.
- Finance picture: the new definition.
- Workspace: the Guide example is now labelled "Example values for explanation only." instead of "Demo preview".

## Commands run and actual outputs

`.\.venv\Scripts\python.exe scripts\check.py`, final run in a normal terminal **with the owner's saved variables present** (`GEMINI_API_KEY`, `TXB_RESEARCH_ROOT`, `TXB_MODEL_PYTHON`, `TXB_GENAI_MODEL`, `TXB_GENAI_ENABLED`, `TXB_GENAI_PROVIDER`):

| Suite | Result |
|---|---|
| Backend | `Ran 217 tests — OK (skipped=1)` |
| Utility | `Ran 35 tests — OK (skipped=11)` |
| Node | `tests 10, pass 10, fail 0` |
| React | `Test Files 15 passed (15), Tests 134 passed (134)` |
| Build | `✓ built in 250ms` |

**check.py no longer needs a cleared environment.** It passes in a normal terminal with the owner's saved TXB_* and Gemini variables present.

Phase 1, for the record: in a cleared environment the counts were 216 / 35 / 10 / 118 (14 files) and the build passed. In the normal terminal at that point, `test_unconfigured_environment_still_serves_reads` failed (201 != 503), and it failed the same way at `2017446`. That is fixed above.

## Screenshots

Folder: `docs/handoffs/screenshots/final-tweaks/`.

**How they were taken**
- Session: m6-test, launched from a PowerShell terminal with `$env:TXB_GENAI_ENABLED = '0'` set before `scripts\local_session.py m6-test --backend-port 5066 --frontend-port 5186`.
- Browser: headless Chrome over the DevTools protocol, full page, 1440 px wide, and 760 px for Monitoring and Guide.
- Data: customer 323 for April 2024; Monitoring on February 2024.

| File | Screen |
|---|---|
| `overview-queue.png` | Overview, review queue (item 1) |
| `customer-summary.png` | Summary: Signals subtitle and closed "How to read the lines" (items 12, 13) |
| `customer-operations.png` | Operations, "Typical" (item 11) |
| `customer-finance-tab.png` | Finance tab: "Fixed deposit earnings" and check B wording (items 2, 3) |
| `finance-picture.png` | Finance picture: new subtitle, new April figures and check B rows (items 3, 4, 8) |
| `monitoring-outcomes.png`, `monitoring-outcomes-narrow.png` | Monitoring outcomes (items 5, 9, 10) |
| `monitoring-rate-shock.png` | Rate-shock scope note (item 6) |
| `guide.png`, `guide-narrow.png` | Guide (item 7) |

**No live Gemini call was made.**
- The script intercepted every request and blocked any non-GET request. It blocked none, because none was attempted.
- Every `/api/` request was a GET. The only AI-related ones were GETs of the stored summary (`/ai-summary`). Nothing was sent to `/ai-discussion`, and "Suggest client questions" was never clicked.
- No page errors.

Because of `render-8`, the Summary tab shows the standard summary text until the owner re-runs the batch.

## Owner's next steps

(1) relaunch with the Gemini key and re-run `generate_summaries.py --batch-id bf0e828c… --limit 206 --keep-rejected`;
(2) `scripts\demo_session.py build --research-root $R --rebuild`;
(3) confirm 206/206 current in m8-demo.

## How to run anything new

- **No new commands.** `scripts\check.py` now works in a normal terminal.
- **Single backend test modules:** both `python -m unittest tests.test_x` (from `backend/`) and `discover` still work.
- **Regenerating the OPR fixture:** if you ever regenerate it (`python backend/tests/make_opr_fixture.py`), it now records exactly what `/api/scenarios` serves, including `batch_id` and `assessment`.

## Open questions

- **Narrow-width rail.** At 760 px, the rail's "Guide" item floats over the top navigation (visible in both narrow screenshots). This was not caused by this work: no rail markup or CSS changed. Fix it as a separate polish item if wanted.

## Known limitations

- **SRR approximation.** SRR is applied to each customer's whole FD balance at the cutoff rate. BNM computes it on an averaged eligible-liabilities base, net of interbank assets, so the per-customer share is an approximation (recorded in `FINANCE_METRICS.md`).
- **SRR sources.** The three sources were cited as the owner supplied them; the PDF was not fetched in this session.
- **Card length.** The April maximum is 241 words, over the 240 design target (accepted).
- **Frontend finance fixture.** `frontend/tests/fixtures/finance-april.json` is a static test fixture and still holds the older April figures. The tests only check that the UI renders what the API sends, so the screenshots, not the fixture, show the new figures.
- **Rate-shock month.** If a future package names a batch that is not loaded, the tab shows the "not in this database" note and everything else still works.
