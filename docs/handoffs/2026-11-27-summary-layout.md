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
