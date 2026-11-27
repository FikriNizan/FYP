# Handoff: Summary card layout tidy-up (27 Nov 2026)

- **Branch:** `m9-summary-clarity`. Pushed, not merged into `main`, never force-pushed.
- **Commits:** the layout change is `80ad8c55d1db9adfb3029dc1971bbab81c79ede1`; this handoff is in the commit after it.
- **Scope:** frontend only. There are no backend changes, `RENDER_VERSION` and `CONTRACT_VERSION` are unchanged (render-9 / m6-narrative-11), and no Gemini calls were made. The saved m6-narrative-11 drafts in m8-demo stay valid: the server's text and evidence IDs are rendered differently, not changed.

## What changed, per file

| File | Change and reason |
|---|---|
| `frontend/src/components/CustomerSummary.jsx` | **Bottom line as a fact grid.** <br>• `splitFact(text)` splits at the first `": "` into a label and a value. <br>• `factCells(items)` places cells by `evidence_ids`, not by position: <br>&nbsp;&nbsp;– the item citing `prediction.risk` → `fact hero`; <br>&nbsp;&nbsp;– the items citing `prediction.flag` and `feature.combined_flow_mean_12m_myr` → `fact pair`, or `fact wide` if only one of them is present; <br>&nbsp;&nbsp;– everything else → `fact wide`. <br>• **Visual order:** hero, the pair, then the other cells in server order. This was approved; it puts "Strongest signals" below the flag/usual-flow row. <br>• **Markup:** a labelled sentence is its own `<dl class="fact …">` with `<dt>` (label) and `<dd>` (value). A sentence with no `": "` is a `<p class="fact wide">`. One `<dl>` per cell keeps the HTML valid. <br>• The AI link note is unchanged (`<p class="ai-link-note">` with the "AI note" badge) but now sits inside a new `<div class="ai-link-box">` below the grid. <br>• The footnote stays last and gains the class `summary-footnote`. <br>• The wording, the meeting-question markup and the `client-basis` class are unchanged. |
| `frontend/src/workspace-architect.css` | New rules inside the existing `@media screen` block, next to `.callout`: <br>• `.fact-grid`: 2 columns; a 1px gap over the `--line` background draws the borders between cells; 6px radius. Hero and wide cells span both columns. <br>• `dt`: 12px, muted. `dd`: 15px, semibold. `dd::first-letter` is uppercased (CSS only). <br>• Hero `dd`: 22px, bold, `var(--danger)`. <br>• `.ai-link-box`: `#f6f8fc` background, 6px radius, `12px 14px` padding. The old divider line on the note is reset inside the box. <br>• `.summary-footnote`: 12px. <br>• `.meeting-questions .client-basis`: `display:block`, 12px, muted, 3px top margin. It's scoped to the summary list, so RM markup is unaffected. <br>• Below 640px (`max-width:639px`) the grid is a single column. <br>• `.ai-summary .callout>div` fills the space beside the info icon. |
| `frontend/tests/ai-drafts.test.jsx` | One expectation updated and five tests added (below). |

**RM discussion draft:** unchanged. It doesn't have the inline problem, because `workspace.css:305` already sets `.client-questions .client-basis { display: block; }`.

## Tests

**New (React):**
1. `splits each bottom-line sentence at its first ": " into a label and a value without changing the text`. It checks the `dt` and `dd` text of the risk cell, that only the first `": "` splits, and that `label + ": " + value` equals the original text for every labelled cell. A sentence without `": "` is a full-width `<p class="fact wide">`.
2. `places bottom-line cells by evidence_ids: hero, the flag and usual-flow pair, then the rest`. The fixture is deliberately out of server order, so placement can only come from `evidence_ids`.
3. `gives the flag or usual-flow cell the full width when its partner is missing`. Covers flag only and usual flow only.
4. `shows the AI note in its own box below the fact grid and keeps the footnote last`. The children are exactly grid → AI note box → footnote, and with no link note there is no box.
5. `renders "Based on" as its own element after the meeting question text`. It is a `<small>`, the last child of the `li`, preceded by the question's text node, inside `ol.meeting-questions` (the list the block-line CSS targets).

**Changed expectation (DOM structure, intentional):** in `shows the server bottom line and footnote only; …`, the assertion `getByText('Strongest signals raising the estimate: payment failure rate (details in Signals to investigate).')` became:
- the label `Strongest signals raising the estimate` is a `<dt>`;
- its `<dd>` reads `payment failure rate (details in Signals to investigate).`

The sentence is now split across two elements; its text is the same.

**Unchanged and still passing:**
- the `closest('p')` assertions on the plain risk sentence and the `ai-link-note` paragraph;
- the exact `li` textContent assertions;
- the `className` `muted client-basis` assertion;
- every RM client-question assertion.

## Commands run and actual outputs

`.\.venv\Scripts\python.exe scripts\check.py`

| Suite | Result | Previously |
|---|---|---|
| Backend | `Ran 242 tests — OK (skipped=1)` | 242 (unchanged, as expected) |
| Utility | `Ran 36 tests — OK (skipped=11)` | 36 |
| Node | `tests 10 · fail 0` | 10 |
| React | `Test Files 15 passed (15) · Tests 141 passed (141)` | 136 (+5) |
| Build | `✓ built in 254ms` | OK |

## How you check it visually

1. Start the demo session:
   ```PowerShell
   .\.venv\Scripts\python.exe scripts\local_session.py m8-demo --backend-port 5086 --frontend-port 5196
   ```
2. Open the frontend at `http://127.0.0.1:5196`. Select the **April 2024** assessment, open customer **689**, and stay on the **Summary** tab.
3. Check:
   - **Hero:** "Estimated chance …" is the full-width top cell, with "56.7%, more likely than not." in large red bold.
   - **Pair:** the "Flagged for committee review" and "Usual monthly combined flow (12-month average)" cells sit side by side.
   - **Signals:** "Strongest signals raising the estimate" is full width below them.
   - **Text:** labels are small and grey, values semibold, and the first letter of each value is capitalised (e.g. "Average online session length, …").
   - **AI note:** if this customer's stored draft has a link note, it sits in a light blue-grey box below the grid with its "AI note" badge.
   - **Footnote:** it is last, small and grey.
   - **Questions:** under "Questions for the meeting", each "Based on: …" sits on its own line beneath the question.
4. Narrow the window below 640px. The grid becomes one column.

## Open questions

1. **Info icon.** The round icon still sits to the left of the grid, inside the existing `callout`. Keep it, or drop it now that the grid is framed?
2. **Visual order.** On screen, "Strongest signals" now comes after "Usual monthly combined flow", but the server and any PDF/print text list it before. Is that difference acceptable?

## Known limitations

- **Styles aren't tested.** jsdom doesn't apply the CSS files, so the tests cover structure and class names only. Sizes, colours, borders, `::first-letter` and the 640px switch need your visual check.
- **Splitting depends on the first `": "`.** A future server sentence with an earlier `": "` would split there. All current bottom-line sentences have exactly one, at the intended place.
- **`::first-letter` and leading punctuation.** It uppercases the first letter only. A value starting with a digit (e.g. "56.7%") or the currency "RM" is unaffected.
- **Pair order.** Within the pair, cells keep the server's item order. For real cards that is flag (left, or first when stacked at ≤639px), then usual flow. The test fixture deliberately lists usual flow first, to prove placement comes from `evidence_ids`.

## Follow-up: visual-check fixes (render-10)

Your m8-demo screenshot showed three problems: the CSS leak, the trailing full stops and the ambiguous comma list.

### Is the bottom-line text stored or re-rendered?

**Stored.** When a draft is accepted, `generate()` stores the whole rendered card (`render_summary()` output, bottom line included) in `ai_drafts.content_json`. On view, `_load()` serves that stored card; only the deterministic fallback is re-rendered.

So the `joined()` wording fix needs **`render-10`**:
- The render version is part of the cache key, so the 205 stored m6-narrative-11 / render-9 April drafts in m8-demo are superseded.
- Until you re-run, the Summary tab shows the live fallback, which already uses the new wording.
- `CONTRACT_VERSION` stays `m6-narrative-11`.

### Changes

| File | Change |
|---|---|
| `frontend/src/workspace-architect.css` | `.fact-grid dl.fact { display:block }` and `.fact-grid dd { text-align:left }`. The global `dl`/`dd` rules (two-column grid, right-aligned `dd`) in `workspace.css:146–148`, and the same rules in `styles.css`, were reaching the grid; the scoped class selectors override them. The global rules are unchanged. |
| `frontend/src/components/CustomerSummary.jsx` | Display only: one trailing `.` is dropped from a fact value ("RM 137,601." → "RM 137,601"). Stored text and plain-text cells are unchanged. |
| `backend/churn_backend/ai_render.py` | `joined()`: if any label contains a comma, items are separated by semicolons: `a; b, c; and d`, and for two items `a, b; and c`. Otherwise the style is unchanged: `a, b and c`. `VERSION = 'render-10'`. Word counts don't change. |

### Tests

**New (backend, `test_ai_render.py`)**
- `test_signal_list_uses_commas_without_comma_labels_and_semicolons_with_them`: 1, 2 and 3 items with and without comma labels.
- `test_bottom_line_signal_list_with_a_comma_label_reads_as_three_items`: your example becomes "payments submitted per month; successful payments, 3 months; and estimated monthly fees". A list without comma labels is unchanged.

**New (React):** `drops one trailing full stop from fact values for display only, leaving the stored text unchanged`. It checks:
- "RM 137,601." shows as "RM 137,601";
- a value without a full stop is unchanged;
- only one full stop is dropped ("..." → "..");
- plain cells keep their text;
- the stored item text still ends with ".".

**Changed expectations (intentional; display now drops the trailing full stop)**
- `shows the server bottom line and footnote only; …`: the signals `dd` is now `payment failure rate (details in Signals to investigate)`, without the trailing `.`.
- `splits each bottom-line sentence …`:
  - the risk `dd` is now `56.7%, more likely than not`;
  - the signals `dd` is now without the `.`;
  - the text-unchanged check is now `label + ': ' + value + '.'` equals the stored sentence.
- `test_ai_drafts.py` old-cache test: `('m6-narrative-11','render-9')` is added as a superseded key, and the current-version assertion is now `('m6-narrative-11','render-10')`.

### Commands run

`.\.venv\Scripts\python.exe scripts\check.py`

| Suite | Result | Previously |
|---|---|---|
| Backend | `Ran 244 tests — OK (skipped=1)` | 242 (+2) |
| Utility | `Ran 36 tests — OK (skipped=11)` | 36 |
| Node | `tests 10 · fail 0` | 10 |
| React | `Test Files 15 passed (15) · Tests 142 passed (142)` | 141 (+1) |
| Build | `✓ built in 278ms` | OK |

### Re-run for the demo (owner, live)

1. Dry run; expect `to generate: 206`:
   ```PowerShell
   .\.venv\Scripts\python.exe scripts\generate_summaries.py --session m8-demo --batch-id bf0e828cdd426ae496ff36bd207acfcd02dccd928eebd14eea5027ce45c9204a --dry-run
   ```
2. Live, in your own terminal with the variables set:
   ```PowerShell
   .\.venv\Scripts\python.exe scripts\generate_summaries.py --session m8-demo --batch-id bf0e828cdd426ae496ff36bd207acfcd02dccd928eebd14eea5027ce45c9204a --limit 206 --keep-rejected
   ```
- Read the final `Outcomes: … | fallback F` line for fallbacks.
- If it prints `Stopped: daily quota exhausted`, run the same command the next day; stored customers are skipped.

Then repeat the visual check above. Labels should sit above their values, values should be left-aligned with no trailing full stop, and lists containing a comma label should use semicolons.

## Follow-up: "Based on" duplicates and the RM heading (no version bump)

Your RM briefing check on m8-demo found:
1. "Based on" repeated a label when the AI cited the same fact as both `feature.X` and `signal.X` (e.g. "Collections vs 12-month average; Collections vs 12-month average"). Both IDs map to one plain name.
2. The heading should read "AI-suggested alternative wording".

**No Gemini calls and no version bump.** Stored drafts keep their basis text but are de-duplicated wherever "Based on" is shown, so no regeneration is needed. New renders are de-duplicated in `basis()`. The displayed result is the same either way, so the cache keys didn't need to change.

### Changes

| File | Change |
|---|---|
| `backend/churn_backend/ai_render.py` | `basis()` keeps each label once, in order of first appearance. New `unique_basis(text)` de-duplicates a stored basis at `"; "`. A standard-question basis ("Label: value") is unchanged. |
| `backend/churn_backend/briefing_pdf.py` | "Based on" lines use `unique_basis()`. The heading is now "AI-suggested alternative wording · reviewed". |
| `frontend/src/components/AIBriefingDraft.jsx` | New `uniqueBasis(text)`, used in `ClientQuestions`, which covers the dashboard draft and the print section. The `<h3>` is now "AI-suggested alternative wording". |
| `frontend/src/components/CustomerSummary.jsx` | The meeting-question "Based on" uses `uniqueBasis()`. |
| `frontend/src/pages/Briefing.jsx` | The print-section heading is now "AI-suggested alternative wording · reviewed". |

Nothing else in the section changed: the "Suggest/Regenerate questions" buttons, the per-item "AI-suggested" tag and the acknowledgement checkbox are as before.

### Tests

**New**
- **Backend:** `test_based_on_lists_each_label_once_in_order_of_first_appearance` (`basis()` with `feature.X` + `signal.X`; `unique_basis()` with duplicates, one label and a standard basis).
- **PDF:** `test_pdf_shows_a_stored_duplicated_based_on_once_under_the_renamed_heading`. A new draft's basis is already de-duplicated. The test then rewrites the stored basis, in the temporary test database only, as a duplicated string, to imitate an existing stored draft. It records the PDF paragraph texts and checks that "Based on: Collections vs 12-month average" appears exactly once, the duplicated text never appears, and the heading reads "AI-suggested alternative wording · reviewed".
- **React:** `shows a stored duplicated Based on text once, for RM client questions and Summary meeting questions`.

**Changed expectations (heading rename)**
- `frontend/tests/ai-drafts.test.jsx`, `shows AI-suggested and standard client questions with an RM-only basis line`: heading `'AI-suggested client questions'` → `'AI-suggested alternative wording'`.
- `frontend/tests/workspace.test.jsx`, line 148: same change.

### Commands run

`.\.venv\Scripts\python.exe scripts\check.py`

| Suite | Result | Previously |
|---|---|---|
| Backend | `Ran 246 tests — OK (skipped=1)` | 244 (+2) |
| Utility | `Ran 36 tests — OK (skipped=11)` | 36 |
| Node | `tests 10 · fail 0` | 10 |
| React | `Test Files 15 passed (15) · Tests 143 passed (143)` | 142 (+1) |
| Build | `✓ built in 292ms` | OK |

### Visual check

1. Run `.\.venv\Scripts\python.exe scripts\local_session.py m8-demo --backend-port 5086 --frontend-port 5196`.
2. Open a prioritised case's RM briefing. The section heading reads "AI-suggested alternative wording", and each "Based on: …" lists every label once. That includes a draft that was showing the repeat before.
3. Print the briefing and download the PDF. Both show "AI-suggested alternative wording · reviewed" with no repeated labels.
