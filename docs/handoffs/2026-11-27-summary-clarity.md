# Handoff: Summary card clarity and AI citation rule (27 Nov 2026)

- **Branch:** `m9-summary-clarity`, created from `final-tweaks`. It is pushed, not merged into `main`, and was never force-pushed.
- **Implementation commit:** `2a81f419bfa3897be6c1a1d229b618dd44b74196`. This handoff is in the commit after it.
- **Versions:**
  - `ai_render.VERSION`: `render-8` → `render-9`
  - `CONTRACT_VERSION`: `m6-narrative-8` → `m6-narrative-9`
  - Both are part of the draft cache key, so every stored summary and RM draft is now stale. A stale draft shows standard text until it is regenerated.
- **Not touched:** the frozen champion, saved predictions/SHAP/flags, the Working DB and the research project. No live Gemini calls were made; every test mocks the provider.

## Why

Your supervisor's feedback on customer 689 (April 2024) said:
- "combined flow" was undefined;
- 56.7% against 25.9% had no stated meaning;
- RM 115,794,564.30 was hard to read;
- "service and online banking" was vague;
- the footnote was confusing.

The consistency problem had a specific cause. The card named only the family of the single top driver, while Gemini could cite any fact. The saved link note cited `feature.outbound_flow_ratio_3m_to_12m`, which is a lower-risk driver and is not shown on the card.

## What the card says now (customer-689-like test fixture)

> Estimated chance that average monthly combined flow (Collection + Disbursement) over May–Jul 2024 falls to half or less of its usual level: 56.7%, more likely than not.
> Flagged for committee review: at or above the 25.9% threshold, which was set from past data to balance catching real cases against false alerts.
> Strongest signals raising the estimate: average online session length, payment failure rate and login failure rate (details in Signals to investigate).
> Usual monthly combined flow (12-month average): RM 115.8 million.
> *Prediction for May–Jul 2024, based on data up to 30 Apr 2024. "Usual monthly combined flow" is the monthly average from May 2023 to Apr 2024.*

## What changed, per file

| File | Change and reason |
|---|---|
| `backend/churn_backend/ai_render.py` | **Bottom line rewritten (render-9).** <br>• `likelihood()`: the phrase is chosen from the percentage the card displays, so a displayed 50% always reads "more likely than not" (your amendment 2). The middle band ("below even odds, but high enough to review") uses the saved flag, which is never recomputed. <br>• `short_money()`: billion / million / whole ringgit, rounded half-up; it moves up a unit when rounding crosses a boundary. <br>• `top_higher()` and `joined()`: the top 3 `higher_risk_drivers` by contribution, in the same order and with the same labels (`driver_name`) as Signals to investigate. With none, the line reads "No signal raised the estimate notably." <br>• `in_sentence()`: the first letter is lowercased unless the label starts with an acronym (amendment 3). <br>• `footnote(evidence)` replaces the old fixed `FOOTNOTE`. Its months come from the saved cutoff: the forecast is the next 3 months, and the baseline is `ai_evidence.period(cutoff, 12)`. The usual-flow sentence appears only when line d is on the card. <br>• The not-flagged wording now also explains the threshold. <br>• `driver_family` and `SERVICE_FEATURES` are deleted (nothing else used them). <br>• **`allowed_references()`**: the feature/signal IDs of the top-3 higher-risk drivers, `feature.combined_flow_mean_12m_myr`, `feature.combined_flow_ratio_3m_to_12m` and `prediction.risk/flag/threshold`. **Every ID of a lower-risk driver is removed, and that rule wins over the others.** <br>• `render_summary` adds a deterministic `basis` ("Based on") to every meeting question, built with the existing `basis()`. <br>• `provider_payload` adds `allowed_references` (IDs only, still "Customer A"). <br>• Evidence IDs on each bottom-line item are as before. |
| `backend/churn_backend/ai_output_audit.py` | New rule `citation_scope`, applied to both purposes. Its diagnostic lists the disallowed IDs and which of them are lower-risk drivers. For summaries the failing item is dropped (`LINK_FIT_RULES` / `QUESTION_FIT_RULES`): a template question fills the gap, nothing dropped is stored, and if nothing is left the whole card falls back. For discussion drafts any failure means the whole draft falls back to the standard questions (existing behaviour). |
| `backend/churn_backend/ai_contract.py` | `m6-narrative-9`. The reference instructions for both purposes now tell Gemini to cite only `allowed_references`. |
| `backend/churn_backend/ai_drafts.py` | The prompt's "Good link" example ended "…alongside the change in payments", which taught exactly the 689 failure. It now links allowed facts only. Message→rule map gains `citation_scope`. |
| `scripts/generate_summaries.py` | `--session` with choices exactly `m6-test` and `m8-demo`, default `m6-test`. It is passed to `selected_database()` only (your amendment 1); nothing else changed. |
| `frontend/src/components/CustomerSummary.jsx` | Each meeting question shows `Based on: …`, using the existing `muted client-basis` classes. `AIBriefingDraft.jsx` and `Signals.jsx` are unchanged. |
| `docs/MILESTONE_6.md` | Short policy note for render-9 / m6-narrative-9. |
| Tests | Listed below. |

**PDFs:** `briefings.py` and `briefing_pdf.py` do not reuse the bottom line, so the PDF is unchanged. It already prints "Based on" for RM drafts.

**Label parity:** Signals to investigate gets its labels from `customer.driver_labels`, which comes from `repository.driver_labels` → `ai_render.driver_name`. Both read the same backend table, so no second mapping was needed. A new test checks that line c matches those labels in the same order.

## Tests

### New tests

**`test_ai_render.py`**
- Exact strings a–e for the customer-689-like fixture.
- Likelihood bands: 0.567, 0.5, **0.4996** (displays 50%, so "more likely than not"), 0.4994, exactly the threshold, below the threshold; plus a check that the saved flag is used and not recomputed.
- Rounding: billion, million and below a million, including the boundary cases.
- Top-3 with 0, 1, 2, 3 and 4 drivers, label parity with `repository.driver_labels`, and a check that a lower driver never appears.
- Acronym lowercasing.
- Footnote months for three cutoffs, including year boundaries.
- "Based on" for template and AI questions.
- Contents of `allowed_references`, including lower-driver precedence and the payload.
- **The 689 reproduction:** a link citing the lower-risk `outbound_flow_ratio_3m_to_12m` → `citation_scope` → link dropped; an out-of-set question dropped; allowed citations accepted.

**`test_ai_drafts.py`** (through `generate()` and the database)
- A lower-driver citation drops the link and is never stored.
- An out-of-scope citation alone means a full fallback with nothing stored.
- RM client questions citing outside the set fall back to the standard questions, with nothing stored.
- **A draft stored under render-8 / m6-narrative-8 is not served after the bump.**

**`test_ai_batch.py`:** `--session` default and choices; `working`, `test`, `m5-test`, unknown names and paths are refused before any database is opened.

**`tests/test_local_session.py` (utility):** the m8-demo session refuses a file that is the Working DB.

**React (`ai-drafts.test.jsx`):** "Based on" appears under summary questions.

### Expected strings changed (wording changed on purpose)

**`test_ai_render.py`**
- `test_plain_sentences_match_saved_values`: bottom lines 0, 1 and 3, and the not-flagged sentence, now use the new wording. Usual flow is now "RM 1.3 million". I added an assertion that the evidence display stays exact.
- `test_friction_led_and_flow_led_customers_get_different_emphasis`: the two "Strongest signals" strings.
- `test_sections_order_titles_and_closing` and `test_footnote_appears_once_on_every_card`: `render.FOOTNOTE` → `render.footnote(...)`. The second also gains a new check that the usual-flow sentence is absent when line d is.

**`test_ai_drafts.py`**
- `CONTRACT_VERSION` assertion `m6-narrative-8` → `m6-narrative-9`.
- `test_case_eligibility_external_privacy_and_pdf_exact_draft`: the second basis is now "Combined flow vs 12-month average", because the helper's citation changed (see below).

**React fixture text:** "Strongest signals: …" and the old footnote were replaced with render-9-style text in the fixture and its two assertions.

### Assertions removed (approved)

`test_bottom_line_family_names_only_the_top_positive_driver` was deleted along with `driver_family`. Its 9 family checks and its "customer profile" predictor set check went with it. The new top-3 test replaces it.

### Word limits raised (approved: re-measured, same headroom)

| Check | Before | After | Measured |
|---|---|---|---|
| Demo/fixture card limit (`test_ai_render`) | 240 | **300** | demo max 228 → 288 (12-word headroom kept) |
| Finance card limit (`test_finance_metrics`) | 240 | **300** | 269 |
| Longest theoretical card, pinned | 264 | **325** | 325 |
| Longest theoretical card, ceiling | 270 | **331** | pin + 6, as before |

### Test inputs changed (approved: cite allowed IDs; each test still checks the same rule)

For the demo customer the allowed IDs are:
- combined flow vs usual (`FLOW`) and collections vs usual (`COLLECT`), both in the Finance section;
- payment failure rate (`PAYMENTS`), in the Operations section;
- usual flow and `prediction.*`.

Login failure and sessions without transactions are its 4th and 5th drivers. Operating balance is a lower-risk driver.

- `test_ai_drafts.py`:
  - `notes()` second fact: login → payment failure.
  - `client_questions()` default second citation: login → combined flow ratio.
  - `test_client_questions_reject_unsupported_…` `raw()` default: login → payment failure.
  - `test_question_empty_boundary_…`: operations login → payment failure; finance balance → combined flow ratio.
  - `test_client_question_contract_schema_and_prompt` count loop: login → payment failure.
  - `test_client_questions_reject_offers_…` `login` variable: now payment failure.
  - `test_validator_enforces_reference_count_…` IDs: payment failure, combined flow ratio, collections ratio, risk.
  - `test_summary_link_note_rejects_lists_…`: the accepted `good` and `connected` links now cite PAYMENTS, COLLECT and FLOW, with new wording. `good` still contains "the change in", so the comparison-rule check still applies.
  - `test_summary_questions_open_…` accepted questions: cite PAYMENTS or COLLECT.
  - `test_summary_has_exactly_one_question_per_audience`: ops text "…completing payments online?" + PAYMENTS; fin + FLOW.
  - Class `OPS`/`FIN`: same swaps.
  - `same_section_link()`: COLLECT and FLOW (both Finance), so it still fails only `link_sections`.
  - `unfit_finance_question()`: now asks about deposit plans and cites FLOW, so it still fails only `question_relevance`.
  - `test_relevance_failure_with_a_prohibited_claim_…`: "deposits ended" + FLOW.
- `test_ai_batch.py`:
  - `output()` default: combined flow ratio.
  - `notes()` second fact: payment failure.
  - `test_outcome_line_counts_…`: an unfit same-section link (COLLECT + FLOW) and a payments question.
- `test_ai_render.py` `test_ai_text_within_its_own_limits_…`: payment failure + combined flow ratio, replacing login + balance. The word counts are unchanged.
- `scripts/evaluate_m6.py`: no change needed. Its notes cite `prediction.risk` and `signal.combined_flow_ratio_3m_to_12m`, which are allowed in all six fixtures.

## Commands run and actual outputs

```PowerShell
.\.venv\Scripts\python.exe scripts\check.py
```

| Suite | Result | Previously |
|---|---|---|
| Backend | `Ran 230 tests — OK (skipped=1)` | 217 |
| Utility | `Ran 36 tests — OK (skipped=11)` | 35 |
| Node | `tests 10 · pass 10 · fail 0` | 10 |
| React | `Test Files 15 passed · Tests 136 passed (136)` | 135 |
| Build | `vite build … ✓ built in 420ms` | OK |

Backend +13: render +8 net (9 new, 1 deleted), drafts +4, batch +1. Utility +1. React +1.

## How you re-generate for the demo (m8-demo, live, owner only)

Your demo database is `artifacts\m8-demo.sqlite`. April 2024 there is batch `bf0e828cdd426ae496ff36bd207acfcd02dccd928eebd14eea5027ce45c9204a`, with 206 flagged customers (read-only check today).

**Safety:** `--session m8-demo` goes through `local_session.selected_database('m8-demo')`. That refuses to run if the file is the Working DB, the M5 Test file or `m6-review.sqlite`, under any name (tested). `working`, unknown names and paths are not accepted as `--session` values.

1. **Dry run.** Zero API calls, no key needed, nothing written. Expect `to generate: 206`, because the version bump makes every old draft stale.
   ```PowerShell
   .\.venv\Scripts\python.exe scripts\generate_summaries.py --session m8-demo --batch-id bf0e828cdd426ae496ff36bd207acfcd02dccd928eebd14eea5027ce45c9204a --dry-run
   ```
2. **Small live run.** Use your own terminal, where you set `TXB_GENAI_ENABLED=1` and `GEMINI_API_KEY` yourself.
   ```PowerShell
   .\.venv\Scripts\python.exe scripts\generate_summaries.py --session m8-demo --batch-id bf0e828cdd426ae496ff36bd207acfcd02dccd928eebd14eea5027ce45c9204a --limit 5 --keep-rejected
   ```
3. **Full April batch.** Resumable: customers already stored are skipped.
   ```PowerShell
   .\.venv\Scripts\python.exe scripts\generate_summaries.py --session m8-demo --batch-id bf0e828cdd426ae496ff36bd207acfcd02dccd928eebd14eea5027ce45c9204a --limit 206 --keep-rejected
   ```

**Reading the results.** The last line of each run looks like this:

`Outcomes: accepted N (link dropped L | question dropped Q) | fallback F`

- **F** = customers that fell back to the deterministic card. The line above it gives the reasons: `Fallback by reason: {"output_validation_failed": …}`.
- **L / Q** = accepted drafts that lost the link note or a question (`citation_scope` and the other fit rules).
- `--keep-rejected` writes each rejected output and its rule IDs to `artifacts\m6-rejected-<time>.jsonl`. That folder is ignored by git and never committed.
- Re-running the dry run afterwards shows how many still have no current draft (`to generate:`).

**RM drafts (on demand):**
1. Start `.\.venv\Scripts\python.exe scripts\local_session.py m8-demo --backend-port 5086 --frontend-port 5196`.
2. Open a prioritised case's briefing and press **Suggest client questions**.
3. A citation failure shows **Deterministic fallback** with "output validation failed".

## Open questions

1. **Session label.** `generate_summaries.py` still passes `TXB_LOCAL_MODE='m6-test'` to `create_app`. I left it as you instructed (only `selected_database` changes), so an m8-demo run is labelled m6-test in local diagnostics only. Do you want that label to follow `--session`?
2. **Wording.** The risk sentence uses "Collection + Disbursement" (singular, as specified), while the rest of the card says "Collections" and "Payments". Keep it, or say "Collections + Payments"?
3. **Card length.** Cards are about 60 words longer (demo 228 → 288). The bottom line is clearer but the card is longer. Is that acceptable to your supervisor?

## Known limitations

- **Stricter citations mean more fallbacks.** Summaries will show more dropped link notes and template questions, and RM drafts will fall back more often. Gemini is told the allowed IDs, which should reduce this.
- **Some top drivers cannot be cited.** A top-3 driver without a DICTIONARY fact cannot be cited by the AI, because no fact for it exists in the payload. Example: `session_duration_mean_3m_sec`, customer 689's #1 signal. It is named on the card but is never citable. As you asked, these were not added to the dictionary.
- **Few-fact customers.** An Operations question needs an allowed Operations fact. If none of a customer's top-3 drivers is an Operations fact, an AI Operations question is always dropped and the template is used.
- **The 50% boundary.** At a displayed 50% the card says "more likely than not" even when the risk is just below 0.5 (e.g. 0.4996). This is deliberate, so the phrase matches the number shown.
- **Still deferred.** The "Good finance question" prompt example (moving payments to another bank) is unchanged.
