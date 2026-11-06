# UI direction and layout

Current direction: the user's Impeccable request to address all five critique findings and freely refine layout, design and theme around the work. The product and evidence rules in [dashboard-frontend-design-prompt.md](dashboard-frontend-design-prompt.md) remain binding; this request permits a new visual treatment. The static HTML remains journey context. This refinement changes React and presentation only; it adds no Flask routes, schema changes, model calls or file transmission.

## Visual foundation

- Navy navigation (`#132742`), cool light workspace (`#F1F5FB`) and white work surfaces.
- Cobalt (`#285ED1`) identifies primary actions and selection. Semantic colours are reserved for flags, plans, attempts, completion and overdue work, always accompanied by text.
- Three concise portfolio measures share a row above the queue. Standard controls, aligned data, readable supporting text and generous separation between jobs establish hierarchy.
- Segoe UI/Arial workhorse typography, tabular values and authored SVG navigation icons. No remote fonts, decorative images, styling CDN or new dependencies.
- Visible keyboard focus, labelled forms, error/status announcements, single-column narrow layouts and table scrolling within panels.

The single active presentation layer is `frontend/src/workspace.css`. `styles.css` and `architect.css` are unimported historical references. The durable system is recorded at the root in `DESIGN.md` and `.impeccable/design.json` after the finish review.

## Navigation and business flow

Primary navigation: **Overview · Reviewed Customers · Monthly Assessments**. Desktop uses a persistent navy rail; narrow screens use horizontal navigation. Guide and Monitoring/OPR previews live under Help & previews. The exact assessment selector appears only where data is batch-scoped.

Overview is scoped to an exact batch. Search, decision filter, flag filter and pagination live in its URL; customer links retain a return URL so Back to review queue and workspace navigation restore the selected context. The three metrics and progress bar use complete API summary counts, never page totals. Finance exposures expand separately with coverage counts. Sample assessments are labelled explicitly.

Customer Review has Summary, Operations and Finance tabs with click/arrow/Home/End keyboard access. Customer, assessment, forecast and decision context stay visible while switching. Summary shares model signals and one observed monthly flow chart; Operations/Finance show saved values and interpretation help. Record decision focuses the persistent committee form. Drafts survive perspective changes and in-tab navigation; validation/conflict failures retain them.

The chart supports combined, incoming and successful outgoing flow. It sorts and limits observations to twelve calendar months through cutoff, includes missing months as gaps, preserves true zeros, labels MYR/date range/axes and exposes an exact-value table. The combined-flow reference average is not shown on unrelated measures.

Reviewed Customers spans all imported assessments. Its concise list shows customer, current decision, reviewed assessment, owner, next follow-up and case state. The Original decision filter explicitly refers to the judgement at case opening; the table labels the current decision separately. Submitted filters, page and briefing selection live in the URL, and case links retain that return context. Clear filters leaves explicit briefing selections intact. Overdue labels use the Malaysian date and exclude closed cases; unsupported due-status filtering is not offered. Select up to ten currently prioritised cases for a briefing; selections are rechecked on load.

Case Details puts current owner, next follow-up and committee decision near the title, with Record follow-up / Manage case action tabs. Original/latest assessment comparison stays distinct. The selected editor sits beside activity on desktop and precedes the timeline on narrow screens. There is one active editing task at a time. If no newer assessment month exists, it says so.

Follow-up drafts are stored separately per task within the tab, including a separate new-task draft. Switching tasks or action views preserves them. Existing tasks require an explicit attempted/completed/cancelled choice; selecting a task never defaults to a delivered intervention. Each form shows its local unsaved state and has an ordinary discard action. Discard affects only that form/task. Case/task conflicts preserve drafts until explicit discard/reload. Known writes from the same session advance matching draft versions, while older potentially stale drafts retain their conflict protection.

Linked task events, manual defer/close/reopen and audit notes remain connected to Milestone 2 APIs. Timelines distinguish planned, attempted, completed and cancelled events. The UI labels the current case owner rather than inventing a separate historical task owner.

Committee decision, case status, task state and observed outcome are distinct. A lower risk never closes a case. A planned contact never counts as a delivered intervention. No realised outcome is inferred from a task or risk change.

## Connected features, previews and unavailable actions

| Interaction | State | Source or required integration |
|---|---|---|
| Assessments, portfolio counts, queue, customer evidence | Connected to saved data | Existing months/summary/customers APIs |
| Explicit committee save, drafts and conflicts | Connected | Existing versioned review API; no automatic outreach write |
| Reviewed cases, case status and task timeline | Connected | Existing Milestone 2 case/follow-up APIs |
| RM briefing | Read-only structured preview from saved cases | Existing case details; deterministic evidence and bounded questions; no AI service |
| Print briefing | Working browser action | `window.print()` with dedicated print CSS and exact source IDs; server PDF export stays unavailable |
| AI drafting | Unavailable, with optional labelled state examples | Grounded generation service, evidence validation and human-review flow required; Generate stays disabled |
| Monthly package upload | Unavailable; isolated state preview | Agreed package contract, file validation, job/scoring status and atomic publication services required |
| Monitoring | Unavailable | Data-quality/drift results, mature outcomes, periods/counts and intervention-window integration required |
| OPR assumptions | Hypothetical local inputs only | Sourced assumptions and scenario engine required; baseline/scenario outputs remain uncalculated |
| Lower next-month risk demonstration | Demo preview in Guide | Constructed 70% January / 18% February example, never mixed into saved cases or totals |

Upload state previews cover pending, processing, validated, failed and published states. The file input and real upload/scoring buttons are disabled. Failed previews preserve the saved assessment list and offer a local correction/resubmission example. AI state previews illustrate generating, ready, error and unavailable layouts without a request; the ready example uses deterministic saved facts and is labelled as an example.

No scenario, upload or AI preview writes to saved records. Fees/waivers remain historical estimates, balances remain exposures and task delivery never creates a realised outcome.

## Validation and next review

The complete check now passes 73 tests (32 backend/migration, 8 copy/update, 6 JavaScript and 27 React) plus a production build. New regressions cover independent task drafts, deliberate outcome choice, scoped discard, worklist URL/selection restoration, own-session version advancement, case action keyboard controls and ordinary review-draft discard.

Browser verification uses a read-only SQLite backup of the working portfolio in a disposable server. All eight screens were captured at 1440px and 390px, with additional Overview checks at 1366×768, 768px and 320px. The first queue record is visible on the laptop viewport. Real browser forms verified task switching, draft restoration, explicit outcomes and discard; prediction explanation bytes stayed identical. The checked screens have no page-wide overflow or JavaScript exceptions. Screenshots and a browser-printed PDF live under ignored `.impeccable/review/`. Physical touch devices and other browser engines were not exercised.

The browser copy includes the actual enriched February batch, long company names, recorded flows and saved reviews. Its reference totals remain 1,000 assessed / 208 flagged / 792 below threshold, and Customer 944 remains about 84.4%; these values are never hardcoded in the UI. All browser writes target the disposable copy. Representative-user usability and comprehensive accessibility remain separate acceptance work.
