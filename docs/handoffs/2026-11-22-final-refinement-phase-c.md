# Handoff — final refinement, Phase C (UI refresh to the approved mockup)

Date: 22 November 2026 (Malaysia time). Branch: `final-refinement`, continuing from Phase B (`6701e3e`). Pushed to
`origin/final-refinement`. Nothing merged into `main`; no force-push; no Co-Authored-By trailers.

**Scope.** Presentation only, plus the backend fields the screens need, so that every number still comes from the server.
* **Applied:** the three owner corrections, the "Ready after <Month YYYY> data" waiting label, and the confirmed decisions (Questions for the meeting; card sections dropped from the Summary tab; screenshots committed here).
* **Not done:**
  * The demo database was **not** built. It waits for your render-7 summary re-run.
  * No live Gemini call was made.
  * The Working database and the research folder were not touched.

## Commits

| SHA | What |
|---|---|
| `930ac39` | Backend fields for the UI refresh. All figures stay server-side. |
| `f21d4d2` | UI refresh: components, pages, CSS and retargeted tests. Also `opr_verified`, `driver_labels` and `feature_labels`. |
| `ae388b8` | Before/after screenshots |
| (this file) | Phase C handoff and roadmap row |

## What changed and why, per file

### Backend (new fields only; no rule or figure changes)

**`repository.py`**
* `service_levels`: the C5 level rule (proposal accepted).
  * A measure is **High** when it is above the nearest-rank 75th percentile of the assessment's customers with a value, and above zero. Otherwise it is **Usual**; a missing value is **Not provided**.
  * The thresholds are cached per saved batch, because saved predictions never change.
* `driver_labels`: plain names for the customer's drivers. These are the same labels the summary card uses (`ai_render.DRIVER_LABELS`).
* Summary payload:
  * `flagged_share`;
  * `flagged_balances` (**fixed deposits plus operating balances** of flagged customers, with the split: correction 1).

**`finance_metrics.py`**
* `fd_threshold_myr`, from TIER_TERMS, for deposit-condition tiers only.
* Portfolio payload:
  * `bases_tiers`, so the UI hard-codes no tier lists;
  * `opr_verified` and `opr_verified_through`, which give the UI its fail-closed OPR reason.

**`outcomes.py`**
* Every performance object gains `expected_positives` (the sum of predicted risk) and `negatives`.
* Trend items gain `positives`, `expected_positives`, `precision` and `recall`.
* Drift gains `previous_flagged` and `current_flagged`.
* `outcome_check` gains `ready_after_month`: the **last** month of the forecast window (owner decision).

**`scenarios.py`**: `feature_labels` (plain input names) in the ready payload. The shared fixture was regenerated with `make_opr_fixture.py`; only the frontend JSON changed, the package files did not.

### Frontend

**Global (`workspace-architect.css`, `Icon.jsx`, `App.jsx`)**
* Panel headings are in sentence case: the uppercase transform on h2 is removed.
* New line icons. The mockup's layout styles are added under the existing tokens.
* Navigation reads Overview, Reviewed Customers, Monthly Assessments, Monitoring.
* "Help" keeps only Guide.
* `/finance` is a new, assessment-scoped route.
* `/research` redirects to `/monitoring?tab=rate-shock`.

**`pages/Overview.jsx` (C1)**
* Four tiles:
  * Customers assessed.
  * Flagged for review, with its share.
  * Flagged, awaiting review.
  * **Deposits held by flagged customers**: the API total of fixed deposits plus operating balances, with the sub-line "Fixed deposits RM X · Operating RM Y". It links to the Finance picture.
* The review queue is unchanged: existing columns, search, filters, ranking and pagination.
* The finance cards, Revenue at Risk section and By tier table are removed from Overview.

**`pages/FinancePicture.jsx` (new) and `components/FinanceMetrics.jsx` (C2)**
* Two cards, "Tiers with a deposit condition" and "Policy-exempt tiers", each showing contribution at stake.
  * The two fee-waiver checks are listed separately in each card and never summed.
* "All customers combined" is a secondary line.
* Two `SensitivityTable`s:
  * same component, same h2 level, side by side, always visible;
  * identical rows: Deposit-condition tiers, Policy-exempt tiers, All customers (secondary).
* The caption is exactly "The sign of these totals depends on both assumptions; both matter equally."
* There is a one-line definition of contribution at stake.

**`pages/CustomerReview.jsx`, `components/Workspace.jsx` (C3)**
* Header:
  * name, CIF, tier, decision badge and workflow badge;
  * predicted risk with the review threshold;
  * recent vs usual flow, with a lower/higher chip.
* The tabs have icons.
* `ReviewForm.jsx` is **unchanged** and sits beside every tab.

**`components/CustomerSummary.jsx` (new), `components/Signals.jsx` (C4)**
* Summary panel:
  * Header "Summary · AI-assisted" with "Facts are from saved records. Items marked AI were drafted by Gemini for review." It shows "Summary" when there is no stored draft.
  * The server's bottom line and 12-month footnote.
  * The AI note, below a divider, **only** when a validated link note exists.
* Chart unchanged.
* Signals:
  * plain labels, an up/down icon and the customer's own value;
  * a relative-strength bar with no number;
  * no log-odds toggle.
* **Questions for the meeting** (your decision), each badged AI or Standard.
* The Operations, Finance, "What the model weighed" and Decision sections of the card are no longer on this tab; the briefing and PDF still render them.
* `AIBriefingDraft.jsx` is now the RM-briefing discussion draft only. The old summary labels "AI-generated summary (stored)" and "AI draft · review before use" are gone.

**`components/OperationsPerspective.jsx` (C5)**
* Service experience comes first. Each of the four columns shows a value, the backend level word and a 0–100 track.
* A one-line hint appears only for a High measure.
* The rule line reads "High = higher than 3 in 4 customers in this assessment."
* Activity level follows: usual vs recent bars, the red dashed half-of-usual reference and one sentence.

**`components/FinancePerspective.jsx` (C6)**
* Contribution card:
  * contribution at stake for 3 months, plus the monthly figure;
  * "Shown beside the risk, never multiplied by it.";
  * the negative sentence, exactly as specified;
  * any unavailable reasons.
* "Fee waiver deal kept?": the A text appears only when A is true.
* "Do deposits pay for the waived fees?":
  * exactly "Deposits don't cover waived transaction cost." plus "Uncovered: RM X a month.", only when B is true;
  * policy-exempt customers are shown as a policy exemption.
* Where the money sits: an allocation bar, two account rows, and the fee-waiver condition bar against `fd_threshold_myr`. A policy exemption shows "Fee waiver by policy exemption" with no bar.
* Monthly breakdown bars.
* A link to the Finance picture. There are no sensitivity tables on this tab.

**`pages/Monitoring.jsx`, `components/RateShock.jsx` (new) (C7)**
* Two tabs.
* **Outcomes:**
  * Readiness cards: "Ready", or **"Ready after <Month YYYY> data"**, or "Not checked". There is an empty state when nothing can be checked.
  * The 2×2, with headers exactly "Activity halved" / "Activity held" and rows "Flagged" / "Not flagged". The cells are Caught / False alarm ("May include customers an RM kept") / Missed / Correctly quiet (correction 2).
  * Two plain sentences, and F1 in small type.
  * Expected vs actual drops.
  * Follow-up split, with the "No record does not prove no contact." hint.
  * Month by month, and input movement.
  * Brier is off screen; it remains in the API and the docs.
* **Rate-shock what-if:**
  * What was assumed: three scenario cards and three assumption lines.
  * What changed in deposits: grouped bars of assigned vs actually affected customers, with the denominator sentence.
  * What changed in model output and workload: flagged bars start at zero and run to all customers.
  * Which inputs moved: shift words No / Little / Moderate / Large.
  * A single "Technical detail" disclosure: PSI/KS values, the paired no-p-value reason and coverage.
  * Scope note: "Performance not evaluated: hypothetical outcomes are unavailable.", plus the A5 sentences.
  * No verdict colour.

**Other pages and modules**
* `pages/MonthlyAssessments.jsx` (B4, C8): the "Outcome check" column uses "Ready after <Month YYYY> data". Otherwise it is restyled only; every column is kept, and there is no reset control.
* `pages/Guide.jsx`, `monitoringCopy.js`: the Guide now carries the Monitoring reading notes, including a corrected note on outcomes derived from uploads, and the administrator `load-outcomes` fallback. That hint is no longer on the Monitoring screen.
* Removed: `pages/ResearchPreview.jsx` (replaced by `RateShock.jsx`) and `components/MonitoringCharts.jsx` (the Brier and trend charts are no longer on screen).

## Every changed assertion and why

Backend: **no backend assertion changed** in Phase C. Only additions were made: `test_finance_metrics` (bases, balances, threshold) and `test_outcomes` (P75 levels, expected drops, ready-after month, plain labels).

Frontend: tests targeting the old layout were retargeted to the approved design. Every protective rule was kept, and several were strengthened.

**1. `finance-metrics.test.jsx`** (rewritten for `FinancePerspective` and the Finance picture)
* Kept or strengthened:
  * wording bans, now also /robust/ and /resilient/;
  * never summed (no 43.87; no 479 customers);
  * B text inside the contribution card;
  * the A text only when A is true;
  * the exact negative sentence;
  * no B text for policy-exempt customers;
  * "Not provided" with the backend reason;
  * sensitivity tables share a parent, are never inside `<details>`, have 4 columns and a secondary last row, and show exact backend values;
  * a new check that both tables have **identical row labels**;
  * the hard-coded-figure scan, extended to 18.23 and 100,000.
* Changed because the design changed:
  * Customer-tab sensitivity tests became "no tables on the customer tab, link to the Finance picture" (C6).
  * "Check A/B" article headings became the two yes/no questions (C6).
  * The risk "78.9%" inside the stake group became "the risk is not in the card" (it moved to the header, C3).
  * Table headings went from h3 to h2, because the tables are now top-level panels with the same heading level (C2).
  * Row labels went from "FD-threshold tiers" / "All customers combined" to "Deposit-condition tiers" / "All customers", and the row header from "Group" to "Cost ratio" / "Liquidity premium" (C2 wording).

**2. `finance-perspective.test.jsx`** (customer 944)
* The fee "Not provided" count and the "0.00 ×2" count became explicit checks: zero FD stays RM0.00, zero waivers stay RM0.00 a month, and a missing fee is never shown as zero.
* The old split panel and missing-card caption became the allocation bar.

**3. `operations.test.jsx`**
* Track indexes follow the new column order (sign-in, sessions, outgoing, our side).
* The "Not provided ×2" check became "2 unavailable values", the same meaning.
* A new test covers levels and hints.

**4. `overview-finance.test.jsx`**
* Both old tests (flagged finance cards; RaR placed before the queue) were replaced by: four API tiles including **FD plus operating**, no RaR / By tier / sensitivity on Overview, and missing balances shown as not provided.
* New Finance picture page tests, including the fail-closed OPR reason.

**5. `ai-drafts.test.jsx`**
* The six summary-card tests were replaced by five `CustomerSummary` tests:
  * the new header and sentence (C4);
  * bottom line only, with the card sections absent;
  * the AI note badge only with a link section;
  * Questions for the meeting with AI / Standard badges;
  * the standard fallback with no AI labels, and the stale-evidence sentence.
* The discussion-draft tests are unchanged.

**6. `app.test.jsx`**
* "792 below the review threshold" became "20.8% of customers" (C1 tile).
* "Observed activity" heading became "Recent activity vs usual" (C3).
* "What stands out" became "Summary" (C4).
* The finance missing/zero checks became explicit, as in item 2.
* New tests:
  * the decision panel (all fields, save/discard state) is present beside every tab;
  * signals show no numbers or percentage weights.

**7. `monitoring.test.jsx`** (rewritten for C7)
* Removed the old state labels (Not loaded / Window open / Partly loaded), the population selector, the Brier tiles, the 78-feature expander and the "How to read this page" details (moved to the Guide).
* Kept:
  * no invented outcomes;
  * unavailable outcomes excluded and never counted as zero;
  * the follow-up caveat;
  * the honest error state.
* New:
  * readiness cards and the empty state;
  * the exact 2×2 labels (correction 2);
  * sentences, F1, expected vs actual, month by month and movement;
  * exactly two tabs.

**8. `opr-scenarios.test.jsx`** (now `RateShock`)
* Section headings follow C7, and the performance region became the scope note.
* The KS note is now inside Technical detail.
* Bans extended (/minor/, /healthy/).
* New:
  * assigned vs affected;
  * zero-based flagged bars;
  * plain input labels;
  * one disclosure only.

**9. `workspace.test.jsx`**
* The back link is named "Review queue" (was "← Back to review queue").
* The `/research` test now asserts the redirect to the Rate-shock tab and that OPR is no longer under Help.

**10. `monthly-upload.test.jsx`**: "Waiting for June 2024 data" became **"Ready after July 2024 data"** (your waiting-label decision).

## Commands run and actual outputs

`.\.venv\Scripts\python.exe scripts\check.py`, exit 0:
* backend `Ran 215 tests — OK (skipped=1)`;
* utility `Ran 35 tests — OK (skipped=11)`;
* Node `tests 10, pass 10, fail 0`;
* React `Test Files 13 passed, Tests 115 passed`;
* build `✓ built in 323ms`.

**Screenshots**
* Captured on the **m6-test** session with headless Chrome, full page at 1440 px wide.
* Customer **323** (flagged April customer, risk 69.1%) has a stored render-7 summary with an AI link note.
* At capture time the API reported, for the 206 flagged April customers: 136 current (`saved`), 69 `evidence_changed` and 1 `not_generated`. That is your summary re-run, partly done.
* No captured screen shows "evidence changed". Customers still awaiting the re-run show the standard summary with the line "The stored summary was written for earlier evidence, so standard text is shown until the summary batch is re-run."
* Page errors: none.

Files in `docs/handoffs/screenshots/final-refinement-phase-c/`:

| Before (current code before Phase C) | After |
|---|---|
| `before-overview.png` | `after-overview.png` |
| (Finance picture did not exist) | `after-finance-picture.png` |
| `before-customer-summary.png` | `after-customer-summary.png` |
| `before-customer-operations.png` | `after-customer-operations.png` |
| `before-customer-finance.png` | `after-customer-finance.png` |
| `before-monitoring-outcomes.png` | `after-monitoring-outcomes.png` |
| `before-opr-page.png` (Help & previews → OPR) | `after-monitoring-rate-shock.png` |
| `before-monthly-assessments.png` | `after-monthly-assessments.png` |
| `before-reviewed-customers.png` | `after-reviewed-customers.png` |

**Database note.** Launching the m6-test session on this branch migrated `artifacts\m6-review.sqlite` from schema 5 to 6 (migration 006 from Phase B). The automatic backup is `artifacts\m6-review.sqlite-pre-migration-20261121T200445521962Z`. All rows are unchanged; the migration only adds two nullable columns. Your summary script works on schema 6.

## How you run it

```PowerShell
.\.venv\Scripts\python.exe scripts\local_session.py m6-test --backend-port 5066 --frontend-port 5186
```

Then visit Overview, open the fourth tile (Finance picture), open customer 323 and use all three tabs, and check both Monitoring tabs. `/research` still works as a redirect.

## Open questions

* **The Monitoring "Expected vs actual" sentence** compares counts in words only ("More drops than the predicted risk expected."). If you want the difference as a number, it can be added from a backend field.
* **The rate-shock scenario cards** default to Severe, as in the mockup.

## Known limitations

* **Dev-only badge in screenshots.** The local-database badge is fixed in the bottom-right corner in development builds, so it overlaps some content in the full-page screenshots (for example part of the follow-up bar). It is not part of the production layout.
* **Screenshot data is a test copy.** The screenshots use the M6 Test database (synthetic data), with outcomes already loaded, so every assessment shows "Ready". The waiting and empty states are covered by tests and will appear in the demo session.
* **Demo not built.** After your re-run completes, I run `scripts\demo_session.py build` and report its counts.
