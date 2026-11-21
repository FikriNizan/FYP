# Handoff: summary draft rejections and item-level acceptance (21 November 2026)

## Branch and commits
Branch **`summary-rejections`**, created from `finance-metrics` at `f2053bf`. Pushed; no force-push, no merge into `main`, and no co-author or session trailers.

| Commit | Content |
|---|---|
| `94ab0e7` | Item-level acceptance (validator, storage, responses, batch outcome line) and tests |
| docs commit (contains this file) | `docs/MILESTONE_6.md` policy note and this handoff. Its SHA is the branch head: `git log -1 summary-rejections` |

## The honest starting numbers
The live April batch (`bf0e828c…c9204a`, 206 flagged customers, render-6, m6-narrative-8) ran **before this change**:
- **120 / 206 accepted whole (58%)**;
- **86 / 206 fell back (42%)**, all `output_validation_failed`.

An earlier 5-row pass also rejected 5 other customers. All 5 were accepted on retry.

## Diagnosis (counts and structure only; no customer or model text)
- **Rule sets in the 86 rejections:**
  - `link_sections` only: 54
  - `question_relevance` only: 21
  - both: 8
  - `link_sections` + `prohibited_claim`: 1
  - `question_audience` + `question_relevance`: 1
  - `evidence_references` + `link_sections` + `question_relevance`: 1
- **The link:**
  - all 86 rejected drafts wrote the optional link; all 120 accepted drafts left it empty;
  - 64 of the 66 failing links (both files) cited **only Operations facts** (mostly login failure + sessions without transactions); the other 2 cited a single ID.
- **The Finance question:**
  - 34 of the 35 `question_relevance` failures are the Finance question;
  - each mentions **payments** but cites only balance, deposit or fee facts;
  - a payments fact was in the Finance section in 35 of 35 cases.
- **Spread:** even across driver family, tier and fee-line presence. There is a mild gradient with the number of supplied facts (14 → 35%, 16 → 58%).
- **Code since before the finance branch (`6487f8b`):**
  - `ai_contract.py`, `ai_output_audit.py`, `ai_drafts.py` and the prompt were unchanged;
  - a payload comparison over all 206 customers found one difference: the stage-1 stake line takes one Finance slot, so the fees line was dropped for 172 customers and the deposit line for 34;
  - no ID moved section and no payload name changed. Stage 2 (render-6, m6-evidence-5) changed nothing in the payload.
- **Classification:**
  - `link_sections`: model non-compliance with a stated rule, primed by an ambiguous prompt example;
  - `question_relevance`: a rule not disclosed to the model, plus a priming example;
  - the validator mapping is correct.

## What changed and why
| File | Change |
|---|---|
| `backend/churn_backend/ai_output_audit.py` | `drop_unfit_items` (see below) |
| `backend/churn_backend/ai_drafts.py` | `_validate` accepts the kept items; `card['dropped']` keeps rule IDs only; local sessions log an INFO line with counts and rule IDs and set `g.genai_item_drops`. `item_drops()` returns counts only. `load()` removes `dropped` from responses and returns `item_drops` counts |
| `scripts/generate_summaries.py` | New line after the existing summary: `Outcomes: accepted N (link dropped L \| question dropped Q) \| fallback F`. The existing line is unchanged |
| `backend/tests/test_ai_drafts.py` | 8 new tests (below) |
| `backend/tests/test_ai_batch.py` | 1 new test for the Outcomes line |
| `docs/MILESTONE_6.md` | Policy note: what is dropped vs rejected, why the version stays m6-narrative-8, and the deferred prompt problems |

**What `drop_unfit_items` does:**
- It accepts a draft only when **every** failure is either:
  - a link fit rule (`link_sections`, `link_list_only`, `link_length`) on `link.*`; or
  - `question_relevance` on `questions[i].evidence_ids`.
- The link becomes `{"text": "", "evidence_ids": []}`. Failing questions are removed, and the template question fills that audience.
- `dropped = [{"item": "link" | "question:<index>/<audience>", "rules": [...]}]`.
- If nothing valid remains, the result is `None`: a full fallback.

**Unchanged:**
- **Whole-draft rejection** for `prohibited_claim`, `protected_content`, `unprotected_comparison`, `evidence_references`, `placeholder_reference`, `unresolved_placeholder`, `question_audience`, schema and `model_word_limit` (counted on the full output, link included), on any item.
- **No prompt change; `CONTRACT_VERSION` stays `m6-narrative-8`.** The 120 accepted drafts remain valid: they had no link and no dropped item, so they satisfy the policy.

**Consistency with "validation failures fall back to deterministic text and are never stored as Gemini drafts":**
- a failing item's text is discarded inside `_validate`, so it is never stored, shown or logged;
- the card shows the deterministic equivalent: no link section, or the template question;
- a draft with nothing valid left is a full fallback and is not stored.

## Tests
**New tests in `test_ai_drafts.py`:**

| Test | Checks |
|---|---|
| `test_unfit_link_alone_is_dropped_and_validated_questions_are_kept` | saved, link empty, questions kept, `dropped` recorded, marker text absent from the DB and the response, rule ID absent from the response |
| `test_unfit_link_with_a_prohibited_claim_rejects_the_whole_draft` | two cases, including a same-section link with a prohibited claim |
| `test_unfit_link_with_a_question_audience_failure_rejects_the_whole_draft` | |
| `test_question_failing_only_relevance_is_dropped_and_the_template_fills_its_audience` | Finance question dropped, template fills the audience, text absent from the DB |
| `test_relevance_failure_with_a_prohibited_claim_on_the_same_question_rejects_the_whole_draft` | |
| `test_link_reference_failure_rejects_the_whole_draft` | `evidence_references` on the link |
| `test_nothing_left_after_dropping_is_a_full_fallback` | link and both questions dropped: fallback, nothing stored |
| `test_item_drop_diagnostic_counts_without_text` | `g.genai_item_drops` counts; the log has rule IDs but no text |

**New test in `test_ai_batch.py`:** `test_outcome_line_counts_accepted_drops_and_fallbacks`.

**No existing assertion changed.** The existing single-item rejection tests (single-section link, list-only link, over-long link, relevance-only question) still raise `ValidationError`. Dropping their only item leaves nothing valid, so the guard falls back.

## Commands and actual outputs
**`.\.venv\Scripts\python.exe scripts\check.py`** (exit 0):

| Suite | Result |
|---|---|
| Backend | **182** — `Ran 182 tests … OK` (was 173; +9) |
| Utility | **14** — `Ran 14 tests … OK` |
| Node | **10** — `ℹ tests 10, ℹ pass 10, ℹ fail 0` |
| React | **104** — `Test Files 12 passed (12), Tests 104 passed (104)` |
| Build | **passed** — `✓ built in 265ms` |

`git diff --check` was clean.

### Offline replay
Both rejected files were replayed through the new validator on a scratchpad copy of `artifacts/m6-review.sqlite`. There was no network access and no writes; the output is structure only.

| File | Rows | Accepted whole | Link dropped | Question dropped | Both dropped | Still fall back |
|---|---|---|---|---|---|---|
| `…T094902Z` (main pass) | 86 | 0 | **54** | **21** | **8** | **3** |
| `…T094449Z` (earlier pass) | 5 | 0 | 0 | 3 | 1 | 1 |

**The 3 that still fall back** (matches the expected 3 of 86):
- `evidence_references` + `link_sections` + `question_relevance`;
- `link_sections` + `prohibited_claim`;
- `question_audience` + `question_relevance`.

**What this means:**
- **No dropped item left an empty draft:** every rescued row kept at least one validated question, so the guard did not fire.
- **Applied to the batch,** the same outputs would give 203 / 206 stored drafts. 120 + 83 = 203, and 3 fall back (1.5%). Of those 203, 120 are whole and 83 have a dropped item.
- **This is a replay of old outputs, not a prediction.** A live re-run produces new outputs.

## Your live check
```PowerShell
.\.venv\Scripts\python.exe scripts\generate_summaries.py --batch-id bf0e828cdd426ae496ff36bd207acfcd02dccd928eebd14eea5027ce45c9204a --limit 20 --keep-rejected
```
**Which customers it runs:**
- the version is unchanged, so the 120 stored drafts are skipped as cached;
- `--dry-run` first should print `eligible (flagged): 206 | already cached: 120 | to generate: 86`;
- the 20 customers are the first 20 of the 86 pending, in fixed order (risk DESC, then prediction_id), and **all were rejected before**.

**For reference only, their old outputs would replay as:** link dropped 13; question dropped 3; both dropped 3; still fall back 1. A new live sample will differ.

**How to read the last two lines:**
- `Generated: N | Fallback by reason: {…} | Skipped (cached): 120 | Remaining: R | Elapsed: …` is the existing line.
- `Outcomes: accepted N (link dropped L | question dropped Q) | fallback F` is the new line:
  - **accepted N:** drafts stored, whole or with a dropped item;
  - **link dropped L:** stored drafts whose link was dropped;
  - **question dropped Q:** stored drafts with at least one question dropped. A draft with both is counted in L and in Q;
  - **fallback F:** all fallbacks, whatever the reason (validation, provider and conflicts). Validation fallbacks are `output_validation_failed` in the existing line.
  - **accepted whole:** at least N − L − Q. It is exactly that unless some drafts dropped both items, which the line counts in both L and Q.
- `Rejected outputs kept: K -> artifacts/m6-rejected-….jsonl` appears only for whole-draft rejections. Dropped items are never written there.

**Then the full run:** repeat without `--limit 20` (or with `--limit 86`) to finish the batch.

**Acceptance against your ≤ 10% bar:** count fallbacks / 206. The 120 cached drafts are already accepted whole.

## Open questions
- **Deferred prompt fixes (m6-narrative-9, not started):**
  - the ambiguous "Good link" example;
  - the "Good finance question" example about moving payments to another bank, which conflicts with the competitor ban;
  - the undisclosed question-topic rule.

  Fixing them would bump the contract and invalidate the stored drafts. Do you want it after the live check?
- **Links still rarely survive:** no stored draft has ever kept a link, so in practice the link stays empty. Keep the optional link, or remove it in a future version?
- **Item-level drops in the UI:** these are invisible to reviewers; only the counts are available in the API. Should the card say when a Gemini item was dropped?

## Known limitations
- **Counts are from replayed old outputs,** not from a new live sample.
- **`question_relevance` is a keyword rule.** Dropping a question it rejects is safe (the template replaces it), but the rule can still reject questions a person would accept.
- **The Outcomes line counts drafts, not items.** `question dropped` counts drafts with at least one dropped question.
- **The M6 Test database was not written by this work.** Its sha256 is `d542e3a0bc22fb54680f0c0c0c851951ca5fa53ee62985e9a9e203bc74217abc` at both the start of the diagnosis and the end of this work (after your batch wrote its drafts). All replay and diagnosis ran on scratchpad copies.
