# UI direction and layout

Current direction: the approved Architect theme brief, applied to the existing workflow-based dashboard. Navy navigation, a white header, gradient KPI tiles, uppercase panel headings and coloured finance-card top borders are confirmed decisions. The product/evidence constraints in [dashboard-frontend-design-prompt.md](dashboard-frontend-design-prompt.md) still apply; its older presentation guidance is superseded by this approved brief. Changes are frontend-only: no Flask routes, API contracts, model calls or saved-data semantics change.

## Visual foundation

- Navy navigation (`#132742`), cool light workspace (`#F1F4F6`) and white work surfaces.
- Cobalt (`#3F6AD8`) identifies primary actions and selection. Semantic colours are reserved for flags, plans, attempts, completion and overdue work, always accompanied by text.
- Three separate gradient KPI tiles use navy for assessed customers, rose for flagged customers and cyan for awaiting review; green is not a pending-count colour. Standard controls, aligned data, readable supporting text and generous separation between jobs establish hierarchy.
- Open Sans Variable self-hosted by `@fontsource-variable/open-sans`, with Open Sans/Segoe UI/Arial/sans-serif fallbacks, tabular values and authored SVG icons. No remote fonts, decorative images or styling CDN. Chart SVG text uses the same font; print retains its previous system font.
- Visible keyboard focus, labelled forms, error/status announcements, single-column narrow layouts and table scrolling within panels.

The active stylesheets are `frontend/src/workspace.css` followed immediately by `frontend/src/workspace-architect.css`; all theme rules are inside screen media queries, preserving A4 briefing print rules. `styles.css` and `architect.css` are unimported historical references. The durable system is recorded at the root in `DESIGN.md` and `.impeccable/design.json` through the Impeccable `document` scan-and-merge workflow from the final active code.

## Navigation and business flow

Primary navigation: **Overview · Reviewed Customers · Monthly Assessments · Monitoring**. Desktop uses a persistent navy rail; narrow screens use horizontal navigation. Guide and the OPR preview live under Help & previews. The exact assessment selector appears on the Overview/Customer Review and Monitoring workspaces where data is batch-scoped.

Overview is scoped to an exact batch. Search, decision filter, flag filter and pagination live in its URL; customer links retain a return URL so Back to review queue and workspace navigation restore the selected context. The three metrics and progress bar use complete API summary counts, never page totals. A visible Financial context for flagged customers section sits between review progress and the queue. Its four cards show operating balances, fixed deposits, estimated fees and estimated waivers, with Exposure/Historical estimate tags, formatted MYR totals and explicit record coverage. Coverage bars are decorative; counts remain text. The grid uses four columns, two at 1250px and one at 760px. Its interpretation footnote stays visible. Sample assessments are labelled explicitly.

Customer Review has Summary, Operations and Finance tabs with click/arrow/Home/End keyboard access. Customer, assessment, forecast and decision context stay visible while switching. Summary shares model signals and one observed monthly flow chart; Operations and Finance show grouped saved values, labelled comparison bars and visible interpretation callouts. Record decision focuses the persistent committee form. Drafts survive perspective changes and in-tab navigation; validation/conflict failures retain them.

The chart supports combined, incoming and successful outgoing flow. It sorts and limits observations to twelve calendar months through cutoff, includes missing months as gaps, preserves true zeros, labels MYR/date range/axes and exposes an exact-value table. Only combined flow with a positive trailing twelve-month average gets two reference lines: a dotted navy average and dashed crimson half-average attrition reference, with direct labels and matching legend swatches. The reference concerns the next three unobserved months, never observed success or failure. Pointer/touch tooltips show exact values and, when applicable, change from the average; their width and anchor keep text inside narrow viewports; the exact-value table remains available to keyboard users. Missing/non-positive averages and other measures have no reference lines.

Operations pairs two activity bar rows with adjacent MYR values and a dashed half-average marker only for a positive twelve-month average. Service experience shows four saved aggregate rates using `percent()` on fractions and neutral-blue 0?100% bars; no monthly trend or service verdict is inferred. The old definition list and disclosure are replaced by panel subtitles and the callout. Container widths govern activity stacking below 560px and service columns (four at 620px and above, two below, one at 340px or less).

Finance is one section containing its heading, balance cards, conditional split panel, estimate cards and callout. The split requires two numeric non-negative balances and a positive sum; rounded shares total 100.0%. A zero balance remains a visible zero and zero-width segment. Missing cards use dashed borders, no shadow and an explicit missing caption. Estimates compare only against the larger of the two recorded historical estimates when both exist and the larger is positive. Finance cards use two columns at container widths of 520px and above and one below. The shared `FinanceCard` component also serves Overview. All decorative bars have adjacent values and are hidden from assistive technology.


Reviewed Customers spans all imported assessments. Its concise list shows customer, current decision, reviewed assessment, owner, next follow-up and case state. The decision filter uses the latest deliberate committee review linked to each case; the opening judgement remains visible on Case Detail. Submitted filters, page and briefing selection live in the URL, and case links retain that return context. Clear filters leaves explicit briefing selections intact. Overdue labels use the Malaysian date and exclude closed cases; unsupported due-status filtering is not offered. Select up to ten currently prioritised cases for a briefing; selections are rechecked on load.

Case Details puts current owner, next follow-up and the current saved committee decision near the title, with Record follow-up / Manage case action tabs. Original/latest assessment comparison stays distinct. The selected editor sits beside activity on desktop and precedes the timeline on narrow screens. There is one active editing task at a time. If no newer assessment month exists, it says so.

Follow-up drafts are stored separately per task within the tab, including a separate new-task draft. Switching tasks or action views preserves them. Existing tasks require an explicit attempted/completed/cancelled choice; selecting a task never defaults to a delivered intervention. Each form shows its local unsaved state and has an ordinary discard action. Discard affects only that form/task. Case/task conflicts preserve drafts until explicit discard/reload. Known writes from the same session advance matching draft versions, while older potentially stale drafts retain their conflict protection.

Linked task events, manual defer/close/reopen and audit notes remain connected to Milestone 2 APIs. Timelines distinguish planned, attempted, completed and cancelled events. The UI labels the current case owner rather than inventing a separate historical task owner.

Committee decision, case status, task state and observed outcome are distinct. A lower risk never closes a case. A planned contact never counts as a delivered intervention. No realised outcome is inferred from a task or risk change.

## Connected features, previews and unavailable actions

| Interaction | State | Source or required integration |
|---|---|---|
| Assessments, portfolio counts, queue, customer evidence | Connected to saved data | Existing months/summary/customers APIs |
| Explicit committee save, drafts and conflicts | Connected | Existing versioned review API; no automatic outreach write |
| Reviewed cases, case status and task timeline | Connected | Existing Milestone 2 case/follow-up APIs |
| RM briefing | Read-only deterministic preview and PDF from saved cases | Shared server-built sections resolved through the existing case service; up to ten explicit current-prioritise case IDs; no AI service |
| Print briefing | Working browser action | `window.print()` after freshness validation, with dedicated print CSS and exact source IDs; AI/demo controls are excluded |
| Download PDF | Connected local download | Server revalidates eligibility and preview snapshots; changed evidence requires review before retry; no database writes or external renderer |
| AI drafting | Unavailable, with optional labelled state examples | Grounded generation service, evidence validation and human-review flow required; Generate stays disabled |
| Monthly package upload | Connected prepared CSV + manifest workflow | Server validation, trusted saved-model scoring, evidence verification and atomic publication; configuration required |
| Monitoring | Connected to saved outcomes when explicitly loaded | Outcome coverage, descriptive delivered-follow-up groups, saved-risk metrics and previous-batch input movement; no causal or real-bank claim |
| OPR assumptions | Hypothetical local inputs only | Sourced assumptions and scenario engine required; baseline/scenario outputs remain uncalculated |
| Lower next-month risk demonstration | Demo preview in Guide | Constructed 70% January / 18% February example, never mixed into saved cases or totals |

Monthly Assessments accepts a prepared features CSV and matching JSON manifest. It keeps saved assessments visible during an honest indeterminate processing state; errors allow resubmission, and success refreshes the list and links to the exact published batch. Repeat submissions are distinguished from new publication. No intermediate stage is presented as complete before the bounded server request returns. AI state previews illustrate generating, ready, error and unavailable layouts without a request; the ready example uses deterministic saved facts and is labelled as an example.

No scenario or AI preview writes to saved records. The connected upload publishes only fully verified monthly evidence. Fees/waivers remain historical estimates, balances remain exposures and task delivery never creates a realised outcome.

## Validation and next review

The Architect pass builds successfully and passes 46 React/Vitest tests, including all 27 original tests unchanged, plus all six JavaScript client tests. New checks cover Overview coverage/missing totals, FlowHistory line geometry and pointer tooltips without extra rectangles, Operations clamping and missing rates, and Finance complementary shares, conditional splits and historical-estimate bars. Backend tests are outside this frontend-only pass; earlier backend verification is recorded in the project verification documents.

Chrome verification uses a read-only SQLite backup in a disposable server. Overview and all three Customer Review perspectives were captured at 1440, 1250, 1050, 760 and 380px, with no page-wide overflow or JavaScript exceptions. Native keyboard arrow switching and forward Tab order through the evidence panel and decision fields retain 3px focus outlines. Browser requests show locally served Open Sans assets and no Google Fonts hosts. The browser-printed RM briefing retains A4 output, full amounts and source identifiers; the base print stylesheet is unchanged. A 103-element computed-style and geometry comparison was identical with all seven screen-rule groups disabled, including the original Segoe UI/Arial print font. Screenshots, the PDF and verification evidence are under ignored `.impeccable/review/`. Physical touch devices, other browser engines, representative-user usability and a comprehensive accessibility audit were not exercised.


The browser copy includes the actual enriched February batch, long company names, recorded flows and saved reviews. Its reference totals remain 1,000 assessed / 208 flagged / 792 below threshold, and Customer 944 remains about 84.4%; these values are never hardcoded in the UI. This Architect verification does not write reviews or follow-up records. The browser copy can contain different saved finance values from the deliberately constructed customer 944 test fixture; neither is substituted for the other. Representative-user usability and comprehensive accessibility remain separate acceptance work.

## Milestone 3 briefing completion ? 9 November 2026

The existing briefing page now consumes one deterministic server payload for preview and PDF. It distinguishes original/current review and latest assessment context, preserves MYR zero/missing states, labels saved dates accurately and retains trace identifiers. The Architect shell and other screens are unchanged; new wrapping/export CSS is scoped to briefing or print. See [MILESTONE_3.md](MILESTONE_3.md) for implementation, full-check results and PDF/browser inspection, separate from the owner's pending acceptance walkthrough.

## RM briefing refinement ? 11 November 2026

The reviewed briefing adds an At-a-glance strip and labelled financial-schedule rows, separates case due dates from planned contact, deduplicates unchanged rationale and groups saved follow-ups separately. Screen, browser print and PDF share this structure and the existing ink/muted/nav/line/canvas/warning palette. Browser print and PDF use local Open Sans; the PDF embeds static 400/700 TTFs under SIL OFL 1.1. Only briefing-local styles changed. See [MILESTONE_3.md](MILESTONE_3.md#briefing-refinement--11-november-2026) for verified checks and the still-pending owner acceptance.

## Monthly supporting evidence and case continuity

The required monthly upload remains the two prepared files. A trusted server-side customer master and recorded-flow source can attach separately versioned names and up to twelve cutoff-safe observations after the scores are published. Monthly Assessments shows actual name/history coverage per batch. A missing source leaves an honest unavailable or partial state; a changed source requires explicit preview and apply. Older embedded evidence remains stored and available. No predictor, risk, model explanation or print stylesheet changes.

Overview separates the model flag, this prediction's saved review, and server-derived workflow state. Needs committee review counts only flagged first-review/reassessment work. Existing open or deferred cases stay visible in the queue and Reviewed Customers without forcing a duplicate monthly decision. Customer Review shows the original case month, decision and status alongside the current risk, and links to the ongoing case. A deliberate new committee review uses the case version and is linked to that case. Multiple legacy active cases require choosing one. Case Detail, Reviewed Customers and RM briefing use the current linked committee decision while still showing the immutable opening judgement and latest machine assessment separately.
