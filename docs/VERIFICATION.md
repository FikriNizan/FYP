# Verification record — React correction, 3 November 2026

## Impeccable redesign and five-issue refinement — 7 November 2026

The work-centred redesign passes **73 automated tests** (32 backend/migration, 8 copy/update, 6 JavaScript utility/API and 27 React interaction tests), plus the production build. Seven added React checks cover independent per-task drafts, deliberate task outcomes, scoped discard, worklist filters/page/selection restoration, version advancement after the same session's accepted write, keyboard action switching and normal committee-draft discard.

All five critique findings are addressed: switching tasks preserves drafts; model values have separate readable rows on narrow screens; Reviewed Customers retains URL context on return; each form exposes unsaved state and discard; and Manage case is reachable from action tabs near the customer context. The visual system now uses navy navigation, cobalt selection and a compact queue-first layout, documented in the root design-system files.

Chrome checks used a read-only SQLite backup of the working portfolio in a disposable server. All eight routes were captured at 1440px and 390px, with additional Overview checks at 320px, 768px and 1366×768. The first queue row ends around 672px on the laptop viewport. No page-wide overflow or JavaScript exceptions were observed. Real browser forms confirmed task-draft restoration, explicit task outcomes and scoped discard; the original prediction explanation remained identical. All writes were to the disposable copy, which included the genuine enriched February evidence and saved cases.

The independent finish review confirmed the five requested fixes, then identified desktop Guide definition overlap and print-preview clipping. Both were corrected. The final reviewer verdict is `ship` for those scored finishing fixes. Actual Chrome PDF page renderings verified complete monetary values on page 1 and complete original/latest batch and prediction identifiers on page 2. Review screenshots, browser results and verdicts are local, ignored artifacts under `.impeccable/review/`.

The detector ran once for this refinement and reported only two font warnings in unimported historical stylesheets. They do not describe the active `workspace.css` system. Representative-user acceptance, comprehensive accessibility, physical touch devices and other browser engines remain outside these checks. The temporary preview server was stopped after review.

## Frontend design-prompt refinement — 6 November 2026

All **66 tests** and the production build pass: 32 backend/migration tests, 8 database-copy/update tests, 6 JavaScript utility/API tests and 20 React interaction tests. This refinement changed frontend/presentation and documentation only; it adds no backend route, migration or model service.

Added frontend coverage verifies queue URL/filter/page restoration, bounded observed-month charts with gaps/zeros/cutoff, isolated failed-upload and hypothetical OPR states, selected saved-case briefings, disabled AI/PDF generation, browser-print invocation, deterministic questions and rejection when a selected committee decision changes.

Chrome checks rendered all eight screens at 1440px and 390px, plus failed-upload, modified OPR assumptions and print layouts. Screenshots were inspected and a fixture briefing was printed to a local PDF using Chrome. No page-wide overflow or runtime exceptions were observed; preview interactions left the saved case API response unchanged. These are local browser checks with disposable data, not representative-user acceptance or a complete accessibility audit.

A read-only snapshot of the working database also confirmed the enriched batch's 1,000 assessed / 208 flagged / 792 below threshold and Customer 944's saved risk of 0.8440919498232807. All legacy rows and the source database bytes remained unchanged. The handoff, connected interactions and future backend requirements are documented in [UI\_DESIGN.md](UI_DESIGN.md).

## Milestone 2 update — 6 November 2026

Windows local checks now pass **59 tests**: 32 backend/migration/API tests, 8 copy/update tests, 6 JavaScript utility/API tests and 13 React interaction tests, plus the Vite production build. The database-copy tests now explicitly close SQLite connections, fixing Windows cleanup locks.

New checks cover legacy migration/backfill/backup/idempotence, atomic rollback and future-schema refusal; preserved original decisions under lower next-month risk; manual case state changes; linked plans/attempts/completions; retrospective events and date validation; stale case/task conflicts; attribution, filters, same-origin writes and retained React drafts.

Chrome headless checks with a disposable demo database rendered Overview and Reviewed Customers at desktop widths, Reviewed Customers at 390px and Case Details at 1440px/390px. The real React forms successfully planned a contact, completed the same task and manually closed its case through Flask; the original prediction explanation remained identical. No page-wide overflow or JavaScript exceptions were observed; screenshots were inspected. This does not establish representative-user usability or comprehensive accessibility.

Migration was also rehearsed on a SQLite backup of the local working database, exclusively in a temporary directory. All rows in the five existing tables were compared before/after and remained identical: 3 batches, 2,001 predictions, 3 reviews, 5 review-history entries and 0 actions. Three cases were backfilled, integrity and foreign-key checks passed, and source database bytes remained unchanged. The working database will migrate on the next Flask startup.

The acceptance walkthrough in [MILESTONE\_2.md](MILESTONE_2.md) remains pending. A genuine cross-month portfolio demonstration, representative-user testing and a remote CI run for these changes have not been established. The rest of this document is the historical React-foundation verification record.

Environment: Python 3.12, Flask 3.1.3, Node.js 24.22.1 and npm 11.9.0 in the build environment. Frontend dependency versions are exact in `package.json`/`package-lock.json`; Python dependencies remain pinned.

| Check                                   | Result    | Scope                                                                                                                                                                                                      |
| --------------------------------------- | --------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Existing backend suite                  | 20 passed | Export verification, leakage/protocol rejection, month isolation, persistence, review conflicts and action notes                                                                                           |
| React-serving/backend integration tests | 4 passed  | Built assets, explicit unbuilt response, retained API, and same-origin write under the development Host header                                                                                             |
| Database copying                        | 4 passed  | Records/history preserved, original untouched, overwrite and invalid source refused                                                                                                                        |
| Guarded source update                   | 4 passed  | Database/Git preserved, source backup, idempotence, local-edit conflicts and preview/tampering/protected-path handling                                                                                     |
| JavaScript utility/API tests            | 6 passed  | Missing versus zero, probability scale, dates, escaping, scoped URLs and request errors                                                                                                                    |
| React interaction/rendering tests       | 8 passed  | API-driven portfolio/search, shared signals, actual-vs-missing money, saving/version payload, draft navigation, explicit conflict resolution, unknown batch, zero-flow chart and preferred batch selection |
| Frontend build                          | Passed    | Vite successfully builds the React application and dependencies                                                                                                                                            |

Total: **46 automated tests** plus the frontend build. React tests use jsdom with mocked API responses; test fixtures are software checks rather than research findings. No real browser visual/accessibility test or Windows execution of this new React version was completed here.

Additional package checks verify that a full v0.2.0 source copy can receive the update while preserving existing database bytes; local edits stop the update. Built HTML/assets are checked through Flask's test client. The development proxy is checked with a real HTTP request to confirm a review save can pass the retained Origin protection.

The complete 1,000-customer database remains on the user's machine. The user's supplied import/API logs establish the reported counts and available context. Tests here use temporary databases and the existing saved demo; they do not independently re-evaluate the complete bank portfolio or run new CatBoost inference.

The frozen model policy, database schema, importer, validation and repository logic are retained. This release changes the frontend implementation and serving/build/development setup. It does not add Reviewed Customers/case migrations, GenAI, OPR, online inference or authenticated identities.

## Local checkpoint after applying the update

* [x] Both development servers start and the React page opens at port 5173.
* [x] Existing three batches remain selectable; enriched February shows 1,000 / 208 / 792.
* [x] Customer 944 shows the verified values and twelve observed monthly flows through February 2024.
* [x] Search, filters and pagination use the selected batch.
* [x] Unsaved drafts survive navigation within the tab but do not change saved counts.
* [x] Save, browser reload and Flask restart preserve the decision and original evidence.
* [x] Two tabs trigger an explicit conflict for a stale save.
* [x] Keyboard, desktop/narrow layouts, chart readability and error states are usable.
* [x] Remote GitHub CI completes after the code is pushed.

Use [UPGRADE\_TO\_REACT.md](UPGRADE_TO_REACT.md), then [MILESTONE\_2.md](MILESTONE_2.md). These unchecked items remain user acceptance work, not completed claims.
