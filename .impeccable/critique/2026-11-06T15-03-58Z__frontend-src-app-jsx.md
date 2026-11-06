---
target: the dashboard
total_score: 27
max_score: 40
na_heuristics: 
p0_count: 0
p1_count: 2
target_identity: "file:D:\\Degree Life\\FYP Full-Stack Development\\corporate-attrition-app\\frontend\\src\\App.jsx"
target_fingerprint: "sha256:9a0582f64ed88b21a3be269d6a35fd60e3344ab33cfd2687c1847f8d102a4796"
target_path: "D:\\Degree Life\\FYP Full-Stack Development\\corporate-attrition-app\\frontend\\src\\App.jsx"
timestamp: 2026-11-06T15-03-58Z
slug: frontend-src-app-jsx
closed: true
---
Method: dual-agent (A: /root/design_review · B: /root/detector_review)

The dashboard scores **27/40 — Acceptable**. Its restrained visual direction fits committee work. The strongest next step is improving follow-up safety, narrow-screen readability and continuity when returning to the worklist.

| Heuristic | Score /4 | Main finding |
|---|---:|---|
| System status | 3 | Clear save/version feedback; case drafts lack visible unsaved status. |
| Real-world language | 3 | Strong domain language; original/current decision filtering needs clarification. |
| User control | 2 | Ordinary discard/reset actions are missing. |
| Consistency | 3 | Cohesive UI; the two worklists preserve context differently. |
| Error prevention | 2 | Task switching resets input and defaults existing tasks to Completed. |
| Recognition over recall | 3 | Original/latest context helps; lost list filters add memory work. |
| Efficiency | 2 | Briefing selection helps; repeated case work requires extra navigation. |
| Minimalist design | 3 | Restrained presentation; two case forms compete for attention. |
| Error recovery | 3 | Failed saves retain drafts; normal draft recovery needs work. |
| Help and documentation | 3 | Guide and contextual explanations are useful. |
| **Total** | **27/40** | **Interaction refinement needed before sign-off.** |

## Design specificity and overall impression

The interface is grounded in this product: assessment identity, forecast dates, separate observed activity and predicted risk, and original/latest committee context are all meaningful. Familiar enterprise styling is appropriate for this operational workspace.

The journey starts calmly and explains uncertainty well. Confidence weakens during follow-up: list context can disappear and changing a task can replace a draft. The end of the journey needs the same care as the review itself.

## What is working

- Three quiet portfolio metrics and one honest progress visual keep the queue central.
- Predicted risk, observed activity, committee judgement and follow-up remain distinct.
- Original/latest case panels, explicit save/conflict states and nearby help support traceable decisions.

## Priority issues

1. **[P1] Changing a follow-up task replaces the draft and defaults to Completed.** `frontend/src/pages/CaseDetail.jsx:68–71` resets event notes, date and attribution when Task changes. Existing tasks start at `delivered`. This is source-confirmed; the fixture did not contain an existing task for live reproduction. Users can lose work or record the wrong outcome. Preserve drafts by task, provide an explicit discard path and require an intentional outcome choice. **Command:** `/impeccable harden`.

2. **[P1] Narrow-screen model signals merge explanation and value.** Both independent browser reviews saw strings such as “Pushed the estimate higher0.87%” at 390px. `Signals.jsx:5`, `workspace.css:108–109` and the base mobile `.signal` rule leave inline children adjacent after stacking. Functional badges/metadata also fall to 10–11px. Give label, direction and value separate rows with guaranteed spacing; increase important supporting text to readable sizes. **Commands:** `/impeccable adapt`, `/impeccable typeset`.

3. **[P2] Reviewed Customers forgets the working list on return.** `ReviewedCustomers.jsx:9–11` stores filters/page only in component state, and `CaseDetail.jsx:74` returns to bare `/reviewed`. An RM reconstructs owner/status filters after each case. Preserve submitted filters and pagination in the URL, retain return context and add Clear filters. **Command:** `/impeccable harden`.

4. **[P2] Users cannot normally discard changes.** ReviewForm shows Unsaved changes but only exposes disposal after a conflict; case/task forms lack a visible dirty-state label. Add a local unsaved indicator and Discard changes action for each form, restoring its saved baseline. Keep conflict resolution explicit. **Command:** `/impeccable harden`.

5. **[P2] Manage this case is buried on narrow screens.** The sidebar stacks after the full follow-up form, evidence and audit sections, around 2,000px down the sample case capture. Add Record follow-up / Manage case shortcuts near the title, with current owner and next date visible in the summary. **Command:** `/impeccable adapt`.

## Cognitive load and persona red flags

**Moderate cognitive load: 2 of 8 checklist items fail.** Case detail divides attention between task entry and case management; returning to an unfiltered list adds recall. Grouping, hierarchy and progressive disclosure otherwise work. Necessary classification dropdowns exceeding four choices are not automatically defects.

- **Alex, experienced RM:** owner/status filters disappear after opening a case, slowing repeated reviews.
- **Riley, stress tester:** task switching replaces entered fields; the default Completed outcome needs an intentional choice.
- **Sam, low-vision/narrow-window user:** small labels and merged signal text impair scanning even when colour contrast is sufficient.

## Detector and browser evidence

The source scan emitted **3 warnings**: `overused-font` in inactive `architect.css:2` and overridden `styles.css:1`, and `side-tab` for the sample-scope disclaimer in `workspace.css:58`. These are contextual style flags, not grounds to replace system typography or remove a useful disclaimer.

Browser detector headlines totalled **29 route findings across four views**, including repeated small-text warnings, kicker labels, a rounded-card accent and cosmetic line wrapping. These are not 29 unique UX defects. Small functional typography is actionable; the remaining style warnings need contextual judgement. The signal concatenation was confirmed visually by both reviews.

Fresh browser inspection covered 1440×1000 and 390×844. No runtime exceptions or page-wide overflow were observed. Reviewed Customers intentionally scrolls its table internally. Representative muted/badge contrast pairs passed ordinary AA text contrast; this was not a complete accessibility audit. Overlay injection ran in a disposable headless browser, which was then closed; no user-visible overlay remains.

## Minor observations and limits

- The Original decision filter uses the opening decision while the table shows the current committee decision. Explain that distinction clearly.
- Fix singular/plural labels such as “1 customers” and “1 cases”.
- Use a quieter unavailable-value treatment for the prominent Not provided activity state.
- Browser inspection used one disposable sample customer/case. Full-portfolio density, real monthly charts, long names and many-task histories remain to be reviewed with representative data.
- No application source or working database was changed. Only critique artifacts were written; the frontend was rebuilt for current-source inspection. Temporary critique services were stopped.

## Questions to consider

Which improvement should lead: safer follow-up editing, narrow-screen readability or worklist continuity? Should the next pass address the top three issues or all five?
