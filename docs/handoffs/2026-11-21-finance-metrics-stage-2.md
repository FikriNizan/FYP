# Handoff: Revenue at Risk and Fee Subsidy Leakage, stage 2 (UI) (21 November 2026)

## Branch and commits
Branch **`finance-metrics`**. Pushed; no force-push, no merge into `main`, and no co-author or session trailers.

| Commit | Content |
|---|---|
| `d6d38b2` | Backend wording: flag-driven card sentence (render-6), "loss" removed, driver labels Transaction value / Collections / Payments (m6-evidence-5) |
| `d44dc99` | Card-only check A text "waiver condition not met"; ceiling guard for the longest theoretical card |
| `a0a2310` | Frontend: Finance tab and Overview sections, `millions()`, CSS, React tests |
| docs commit (contains this file) | `FINANCE_METRICS.md`, `ROADMAP.md`, this handoff. Its SHA is the branch head: `git log -1 finance-metrics` |

At the start of stage 2, recon found no partial stage-2 work: the tree was clean, there was no stash, and HEAD = origin = `fec6731`.

## What changed and why

### Backend
| File | Change | Why |
|---|---|---|
| `backend/churn_backend/ai_render.py` | `stake_line` rebuilt from the flags. Constants `FSL_A_TEXT` ("waiver condition not met", card only), `FSL_B_TEXT` ("deposits don't cover waived transaction cost") and `NEGATIVE_TEXT`. `VERSION = 'render-6'` | Approved wording. A/B text follows each flag only. "loss" banned. Word budget (see Card length) |
| `backend/churn_backend/finance_metrics.py` | Portfolio `note` reworded without "loss". **Formulas unchanged** | The note can be shown in the UI |
| `backend/churn_backend/briefings.py` | Ratio driver labels: Transaction value / Collections / Payments | App-wide terminology (your decision) |
| `backend/churn_backend/ai_evidence.py` | `combined_flow_ratio_3m_to_12m` label is "Transaction value"; `VERSION = 'm6-evidence-5'` | The label reached people (evidence below) |
| `backend/tests/test_finance_metrics.py`, `backend/tests/test_ai_render.py` | Wording tests and the ceiling guard (assertions listed below) | |

### Frontend
| File | Change |
|---|---|
| `frontend/src/components/FinanceMetrics.jsx` (new) | See the three components below |
| `frontend/src/components/FinancePerspective.jsx` | Renders the customer view (new `metrics` and `risk` props). Existing sections unchanged |
| `frontend/src/pages/CustomerReview.jsx` | Passes `c.finance_metrics` and `c.calibrated_risk` |
| `frontend/src/pages/Overview.jsx` | New section "Revenue at Risk and fee subsidy leakage" between the flagged financial context and the queue. Hidden when the API has no `finance_metrics` |
| `frontend/src/format.js` | `millions()` (e.g. −RM1.23m, U+2212 minus); driver labels Transaction value / Collections / Payments |
| `frontend/src/workspace-architect.css` | Layout for the new blocks. Sensitivity tables fit without horizontal scrolling |
| `frontend/tests/finance-metrics.test.jsx` (new), `frontend/tests/fixtures/finance-april.json` (new) | React tests. The fixture is the live April `/api/summary` `finance_metrics` plus customer 604's `finance_metrics`: aggregates and numbers only, no names or notes |
| `frontend/tests/overview-finance.test.jsx`, `frontend/tests/fixtures/briefing.json` | New section-order test; fixture labels renamed |

**What `FinanceMetrics.jsx` contains:**
- **`SensitivityTable`:** one component for both sensitivities. Both are always open and sit side by side, with the same heading level. Column order comes from the backend's `cost_ratios` / `liquidity_premiums` lists, because the JSON keys arrive sorted.
- **`CustomerFinanceMetrics`:**
  - predicted risk next to contribution at stake, never multiplied;
  - the monthly contribution, with the A/B labels beside it only when each check is true;
  - the exact negative sentence;
  - the components;
  - separate A and B cards, with policy labels;
  - both sensitivities;
  - unavailable reasons shown as "Not provided: …".
- **`PortfolioFinanceMetrics`:**
  - FD-threshold and policy-exempt panels shown separately;
  - "The sign of these totals depends on both assumptions; both matter equally.";
  - both sensitivity tables, with "All customers combined" as a secondary last row;
  - a secondary combined line;
  - a collapsed by-tier table.

**All numbers come from the backend.** A static test fails if any scope figure appears in `frontend/src`.

## Card length: the 241-word finding and your decision
- **Count scope:** the word count (`ai_render.card_words`) covers the **deterministic card sections plus the template questions only**. AI link text and AI questions are **excluded**; they have their own limits.
- **Finding:** with the first stage-2 wording, one flagged April card was **241** words (max). It had a negative contribution, A and B both true, and all 6 finance lines in use.
- **Decision 1 (card only):** check A reads "waiver condition not met" (−1 word). The UI keeps "Fee waiver condition not met".
- **Worst case:** a search for the longest theoretical card found **263** words. It is broken down below.
- **Decision 2:** accept 263. 240 stays a design target. Lines, approved wording and template questions are unchanged. A **ceiling guard at 270** pins the worst case (`test_longest_theoretical_card_stays_under_its_ceiling_guard`; it also pins the exact 263).

**April 2024 after the change** (M6 Test, deterministic renderer on a scratchpad copy of the database, no provider):

| Cards | Min | Median | Max | At exactly 240 | Over 240 |
|---|---|---|---|---|---|
| 206 flagged | 203 | 217 | **240** | customer **72** | none |
| All 1,000 | 195 | 214 | **240** | customer **72** | none |

Before the A change the same runs gave 203 / 217 / **241** (flagged) and 195 / 214 / 241 (all). No rendered April card contains `/\bloss/i`.

**Negative cards in April:**
- 13 of the 206 flagged cards; all 13 have check B true.
- 242 of all 1,000 cards: 171 with B true and **71 with B false**. Those 71 show the figure without the B label.

### The 263-word worst case
**Conditions:**
- demo cutoff 29 Feb 2024, so every 3-month period spans a year and costs one extra word;
- flagged;
- every Operations/Finance fact present and notable;
- negative contribution with A and B true;
- the three longest driver labels ranked first;
- a friction driver, which adds the service closing and the friction question.

| Section | Words | Lines |
|---|---|---|
| Bottom line | 44 | risk sentence 20; flagged 10; strongest signals (service and online banking) 6; usual value 8 |
| Operations | 39 | successful payments pair 14; successful logins pair 14; sessions without transactions 11 |
| Finance | 94 | trend 12; **negative sentence with A and B, 26**; fees and waivers 19; fixed deposits with maturities 15; Collections 11; Payments 11 |
| Weighed | 34 | "Payments in processing per month", "Share of payments in processing", "Online sessions started, 3 months" (9 each); note 7 |
| Footnote + closing | 24 | footnote 7; closing 5; service closing 12 |
| Template questions | 28 | Operations friction question 15; Finance question 13 |
| **Total** | **263** | Same card with the stage-1 negative sentence: 262. With no stake sentence: 237 |

## Driver label "Transaction value" in `ai_evidence.py` (m6-evidence-5): grep evidence
**People see it:**
- `ai_evidence.py:16`: the `DICTIONARY` label for `combined_flow_ratio_3m_to_12m`.
- `ai_evidence.py:99`: `add()` stores it as `facts[key]['label']`.
- `ai_drafts.py:331`: the summary API returns `evidence=list(evidence['facts'].values())`.
- `frontend/src/components/AIBriefingDraft.jsx:90`: renders `<dt>{f.label}</dt>` in the supporting-evidence panel. So "Transaction activity" was **shown to people**.

**The provider never received it:**
- `ai_evidence.external` → `ai_render.provider_payload` names facts through `ai_render.name()` (`ai_render.py:137-142`).
- `name()` prefers `DRIVER_LABELS`, which already says "Transaction value vs 12-month average" (`ai_render.py:58`; asserted in `test_weighed_section_and_provider_payload_use_the_same_plain_labels`).

**Result:** the label changed and `VERSION` became `m6-evidence-5`, so every evidence hash changes. You accepted this; render-6 already changed the draft cache key.

## Every changed test assertion
| Commit | Test | Change |
|---|---|---|
| `d6d38b2` | `test_finance_metrics.test_card_states_contribution_at_stake_…` | Expected sentence: removed "not a loss forecast"; B text "waiver cost exceeds deposit earnings" → "deposits don't cover waived transaction cost". Added: no `\bloss` in any card line |
| `d6d38b2` | `test_finance_metrics.test_card_wording_for_negative_contribution_and_policy_exemption` | The single old negative assertion ("…is negative: -RM 12.50 a month (an estimate, not a loss forecast).") was replaced by six exact assertions: negative + B false (no label), negative + B true, negative + policy B (no label), positive A only, positive B only, positive neither. Each also checks `external=False` and no "loss". The `contribution_monthly=None → []` assertion is unchanged |
| `d6d38b2` | `test_finance_metrics.test_portfolio_totals_coverage_and_groups` | Added: the note contains no "loss" (the existing "must not be added" assertion is kept) |
| `d6d38b2` | `test_ai_render.test_card_uses_collections_and_payments_terminology` | `evidence.VERSION` 'm6-evidence-4' → 'm6-evidence-5'; added: label 'Transaction value' |
| `d44dc99` | the two `test_finance_metrics` card tests above | "fee waiver condition not met" → "waiver condition not met" (card-only text, your decision) |
| `d44dc99` | `test_ai_render.test_longest_theoretical_card_stays_under_its_ceiling_guard` (new) | Pins 263 and asserts ≤ 270. The existing representative test `test_server_card_length_is_bounded_for_demo_and_every_fixture` (≤ 240) is unchanged |
| `a0a2310` | `overview-finance.test.jsx` | **Section-order update (a layout change, not a weakened assertion).** New test: financial context → "Revenue at Risk and fee subsidy leakage" → queue, with both sensitivity regions present. The original test's "financial context → queue" assertion is **unchanged** and still passes, because its fixture has no `finance_metrics` and so the section is hidden |
| `a0a2310` | `fixtures/briefing.json` | Fixture text only ("Transaction activity" → "Transaction value", "Incoming payments" → "Collections"); no assertion changed |

**New React tests** (`finance-metrics.test.jsx`, 14):
- worked example: risk 78.9% beside RM79.92; A and B labels in the contribution block; A RM25.64 and B RM18.23 kept separate, with no summed figure;
- both sensitivity tables: 4 columns, not in `<details>`, same parent;
- negative with B false (no label) and negative with B true;
- positive with A only and with B only;
- policy labels;
- unavailable reasons;
- Finance perspective wiring;
- `millions()`;
- portfolio panels, with the combined row secondary;
- both portfolio tables with the exact April figures;
- source rules: no `\bloss`, no hard-coded figures.

**Banned in rendered text:** `/loss/i`, `/minor/i` and `/positive under all|always positive/i`.

## Commands and actual outputs
**`.\.venv\Scripts\python.exe scripts\check.py` (exit 0):**

| Suite | Before (stage 1) | After |
|---|---|---|
| Backend | 172 | **173** — `Ran 173 tests … OK` |
| Utility | 14 | **14** — `Ran 14 tests … OK` |
| Node | 10 | **10** — `ℹ tests 10, ℹ pass 10, ℹ fail 0` |
| React | 90 | **104** — `Test Files 12 passed (12), Tests 104 passed (104)` |
| Build | passed | **passed** — `✓ built in 324ms` |

**Other checks:**
- `git check-ignore -v frontend/dist` → `.gitignore:9:frontend/dist/`. `git ls-files frontend/dist` → 0 files, so `dist/` is not committed.
- `grep -rniE '\bloss' frontend/src` → 0 matches. Rendered April cards: 0 of 1,000 contain `\bloss`.

**Live check, read-only on M6 Test only:**
- **Session:** `scripts/local_session.py m6-test --backend-port 5066 --frontend-port 5186`.
- **Fetched:** `GET /api/summary?batch_id=bf0e828c…` (April) and `GET /api/customers/604`. AI endpoints were not called.
- **Values, exact:**
  - cost ratio, FD-threshold: +RM0.88m / +RM2.84m / +RM4.79m;
  - cost ratio, policy-exempt: −RM6.84m / −RM2.42m / +RM2.00m;
  - premium, all customers: −RM9.51m / −RM5.96m / −RM2.42m;
  - premium, FD-threshold: −RM0.92m / +RM0.88m / +RM2.68m.
- **Raw values:** FD-threshold premium −920,726 / 878,486 / 2,677,697; totals −9,508,640 / −5,964,430 / −2,420,220.
- **Headless Chrome screenshots** of the Overview and customer 604's Finance tab: layout as described, both sensitivities fully visible side by side, no "loss" in the tab text.

**M6 Test database sha256:**
- before: `f5fd067668aa60e1982fd3f9829430fd77113e6046899c7a0952f4f1e639d849`
- after: `f5fd067668aa60e1982fd3f9829430fd77113e6046899c7a0952f4f1e639d849` (identical)

The card word counts ran on a scratchpad copy. The Working database, the research folder, the champion and API keys were not touched, and no Gemini call was made.

## How you run it
```PowerShell
.\.venv\Scripts\python.exe scripts\check.py
.\.venv\Scripts\python.exe scripts\local_session.py m6-test --backend-port 5066 --frontend-port 5186
```
- **Overview:** the new section sits under "Financial context for flagged customers".
- **Customer view:** open a customer, then the **Finance** tab, then "Relationship contribution (estimate)".

**Reminder:** render-6 and m6-evidence-5 change the draft cache keys and evidence hashes. **Re-run the summary batch (live, yourself)** with `scripts/generate_summaries.py` afterwards. Existing saved summaries will show as changed evidence until then.

## Open questions
- **Other "Incoming"/"Outgoing" text was left as is:** it consists of flow and operations labels, not driver labels. It appears in `FlowHistory.jsx` ("Incoming flow", "Successful outgoing flow", table headers), `OperationsPerspective.jsx` and `monitoringFeatures.js` ("Outgoing payment failure rate"), and in the legacy `main.js`. Should these also move to Collections / Payments?
- **The A wording differs by surface:** the card says "waiver condition not met" and the UI says "Fee waiver condition not met". Is that acceptable long-term?
- **PayNet business IBG charges** remain unverified (HTTP 403).

## Known limitations
- 240 words is a design target, not a guarantee: theoretical cards reach 263 (guarded at 270). Customer 72 is exactly at 240.
- The worst-case search covers the labels in `DRIVER_LABELS`. A saved driver outside that table would fall back to `briefings.driver_label` and could be longer.
- The cost proxy, synthetic fees, OPR-as-funding proxy and costs left out are unchanged from stage 1 (see `FINANCE_METRICS.md`).
- The visual check was by headless screenshot at 1440 px width only; narrow widths are covered by CSS rules but were not screenshotted.
