# Milestone 3 — RM briefing and PDF

Implemented and verified on 9 November 2026 against the local `architect-theme` worktree, starting at `1b1c036893f5ea58e0af1723c9f12909510875ce`. Owner acceptance is a separate, pending step below. No commit, merge or deployment is implied.

## What is connected

Use **Reviewed Customers → select case(s) → Prepare RM briefing → Download PDF**. Case Details retains its single-case Prepare RM briefing link. Only explicitly selected case IDs are used, in their chosen order, with duplicates removed and a maximum of ten unique cases. Eligibility uses the currently saved originating prediction's committee decision, **Prioritise for RM**; an open/deferred/closed lifecycle status is separate. No follow-up is required.

The existing briefing page and the PDF consume one deterministic, server-built representation. It separates:

* The original assessed snapshot and immutable opening judgement (`original`, `original_review`), with original reason/reviewer and the accurately labelled case-opened date.
* The currently saved review (`original.review`), with current rationale/reviewer/review-saved date, case owner, due date/status and saved follow-up summaries. A plan is not contact delivery.
* The latest backend-resolved assessment (`latest`), with its own cutoff, forecast and risk. A different batch at the same cutoff is identified without calling it a newer month.

Activity uses the latest saved three- and twelve-month flow averages. Missing or non-positive references have an explicit fallback; missing cutoff-safe monthly history is stated without fabricated observations. Selected model signals include readable labels, recorded values and influence direction, separate from measured activity and causal conclusions. The briefing contains Operations rates/notes and separate balance exposures and historical three-month monthly fee/waiver estimates. It does not calculate profit, invoices, savings, outcomes or intervention effectiveness.

Questions retain the existing bounded evidence criteria, tightened to omit unsupported filler and duplicate payment questions. At most three neutral questions identify their evidence and assessment month. Insufficient evidence gets an explicit message. Amounts use MYR/en-MY conventions, including genuine zeros versus `Not provided`, negative amounts and decimal rounding.

Both original/latest batch and prediction IDs, case ID/version and available original/current review versions are present in the PDF and browser print, regardless of whether the on-screen source disclosure is expanded. Single-case sample provenance is resolved from the saved batch registry. No fixture is used as live evidence.

## Local PDF implementation and setup

ReportLab **5.1.0** produces a real A4 PDF in Flask memory. Its tested runtime dependencies are pinned in `backend/requirements.txt`: Pillow **13.0.0** and charset-normalizer **3.5.2**. Root `requirements.txt` includes that file. Bundled static Open Sans Regular (400) and Bold (700), licensed under SIL OFL 1.1, are embedded as of the 11 November refinement below (the initial 9 November export used ReportLab's packaged Bitstream Vera fonts); no OS font installation, browser rendering executable, remote font, API key or external customer-data service is required. The approved dashboard continues using its existing Open Sans/Architect styles. The PDF uses fixed readable type sizes, natural paragraph splitting, a new page for each case and page-numbered footers; it contains no dashboard chrome, controls or AI demo text.

From the project root in PowerShell:

```PowerShell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
npm ci --prefix frontend
npm run build --prefix frontend
.\.venv\Scripts\python.exe scripts\check.py
```

Start Flask using the normal instructions in [DEVELOPMENT.md](DEVELOPMENT.md) or the README. Restart an already-running Flask process after installing/updating this code. Use the browser at the existing app URL. **Download PDF** directly downloads `txb-rm-briefing-<customer-id>.pdf` or `txb-rm-briefing-<count>-cases.pdf`. Filenames are sanitised. **Print briefing** remains a real print-dialog action with browser Save as PDF available.

If saved text contains a glyph outside the embedded font's coverage (for example, emoji or some non-Latin scripts), direct download reports an explicit font error instead of silently substituting unreadable glyphs. The preview and **Print briefing / Save as PDF** remain usable. The browser/OS determines font coverage on that path.

## Read-only API and freshness contract

Existing case endpoints and schemas are unchanged. Two focused endpoints reuse the existing case service:

| Endpoint                                 | Contract                                                                                                                                                                                                                    |
| ---------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `GET /api/briefings?case_id=A&case_id=B` | Validate/deduplicate one to ten IDs; read all records and batch provenance in one SQLite read snapshot; return `items` plus ordered `snapshots`.                                                                            |
| `POST /api/briefings/pdf`                | Accept only `{case_ids, snapshots}`; load and validate all selected cases again; compare snapshots before rendering; return an attachment with `Content-Type: application/pdf`. Client HTML and amounts are never accepted. |

Each preview snapshot includes case ID/version, current review version, original/latest prediction IDs and an SHA-256 fingerprint over the server-resolved case evidence and source provenance. A changed snapshot returns **409** **`briefing_changed`** and refreshed preview content, without any PDF. The page shows the updated briefing, disables print/download and requires **I have reviewed the updated briefing** before retrying. Print also fetches fresh evidence and compares snapshots before opening its dialog. Every retry validates again.

Missing/ineligible cases block the entire selection, never a partial file. Empty/oversized selections, loading, download progress, service failures and unsupported-font errors are explicit. Failures retain selected IDs and the return-worklist query. A new selection immediately hides the old preview and disables export; in-flight downloads are aborted, and late responses cannot download or replace another selection. Responses are `no-store`.

No preview/export endpoint writes reviews, cases, tasks, actions, assessments, predictions or outcomes. PDFs are not saved to SQLite or an application-side archive. AI remains explicitly unavailable; upload/scoring, OPR and outcome monitoring are outside this milestone.

## Verification completed

* Baseline: **92 existing tests** and production build passed before implementation.
* Final automated checks: **115 tests** (41 backend/API/migration/PDF, 8 copy/update, 8 JavaScript client/API, 58 React) and Vite build. Tests use temporary databases and constructed fixtures.
* New coverage: ordered/deduplicated selection and ten-case limit; February origin/March lower-risk context; same-month distinct batches; zero/missing estimates; no follow-up; insufficient/duplicate questions; sample provenance; stale case/review/latest assessment; whole-selection failures; long notes/names; real PDF bytes/A4 pages; read-only database dumps; client selection races, error recovery and review-before-retry.
* The existing React briefing test was updated for the intended change from disabled Export PDF to enabled Download PDF, the new shared-payload endpoint and asynchronous print freshness validation. Other Milestone 2 assertions remain intact.
* Real Chrome downloads: a **two-page A4 single-case PDF** from a read-only backup of the local February/March portfolio, and an **eight-page A4 two-case stress document** from separate constructed fixtures with long names and multiline notes. The files were opened in Chrome's PDF viewer and inspected. Independent parsing with verification-only `pypdf==6.12.0` checked every page's A4 media box, non-blank content, exact source IDs and exclusion of controls/AI text. pypdf is not a runtime dependency.
* Browser flow: Reviewed Customers selection, retained worklist query, direct Download PDF, desktop **1440px** and narrow **380px** preview, browser Print path, and actual server-conflict refresh/review/retry. The copied real case retains February **84.4%** versus March **74.3%** and its manually closed lifecycle; export does not reinterpret that status. A deliberate stale-review mutation was made only in the separate constructed fixture server.
* The copied real case's complete JSON (including original/latest evidence, review history, follow-ups and actions) was identical before/after preparation/download. The working SQLite file's SHA-256 was unchanged. No working February/March records were modified. This was selected-case acceptance using a copied portfolio, not a full-portfolio import/scoring replay.
* Ignored local evidence: `.impeccable/review/milestone3/` contains browser screenshots/checks, actual downloaded PDFs, extracted text and PDF inspection records. None is committed. Temporary acceptance servers are stopped after verification.

## Owner acceptance — pending

1. Install the pinned Python dependencies, build the frontend and restart your normal Flask process.
2. Open **Reviewed Customers**, set any desired filters and select a currently prioritised case. A manually closed case can still qualify when its current committee decision remains Prioritise for RM.
3. Choose **Prepare RM briefing**. Check original judgement/date, latest assessment, financial missing/zero values, current rationale/owner/status and source IDs.
4. Choose **Download PDF**, open the file, check both pages and the complete identifiers. Also try **Print briefing → Save as PDF**.
5. Select two or more currently prioritised cases if available and verify the exported order and case boundaries. Do not change real decisions solely to manufacture a multi-case acceptance selection.
6. If another window updates the selected review/case, retry Download PDF: review the refreshed evidence and explicitly confirm before downloading.

Your acceptance walkthrough, representative-RM evaluation, physical touch devices and other browser engines have not been claimed as completed. Live GenAI remains a later milestone.

## Briefing refinement ? 11 November 2026

The reviewed refinement preserves the read-only endpoints, `{case_ids, snapshots}` request, snapshot fields, SHA-256 evidence hash and 409 `briefing_changed` review-before-retry flow. Discussion-question wording is unchanged; AI remains unavailable, receives only `ai_context` and stays outside print/export. Owner acceptance remains pending.

* A four-cell **At a glance** strip shows committee decision/case state, latest risk with original-risk context, activity versus usual, and **Case due date** with owner and a separate planned-contact note when present. The case due date is not relabelled as the date a contact occurred.
* Original/latest context, activity, model signals, Operations/Finance and current decision use labelled rows. Generic filler is removed; unchanged rationale is identified without repeating the saved reason; all-missing Operations rates collapse to one explicit missing-data statement. Genuine zeros and missing MYR values remain distinct.
* Existing item keys remain. Added fields are `glance`, `risk_definition`, `prepared_on` and nullable `followups`. Signal data now uses `signals.rows` instead of `signals.items`; saved follow-up rows move out of `decision.rows` into `followups.rows`. Current reviewer/date/owner/due/status remain in `decision.rows`. See [API_CONTRACT.md](../backend/API_CONTRACT.md).
* Screen, browser print and direct PDF share the same section order and financial-schedule presentation: header, glance/definition, original/latest context, activity, signals, Operations/Finance, current rationale/next step, recorded follow-ups when supplied, questions and complete identifiers. Browser print uses the browser's header/footer; direct PDF retains the TxB footer and page numbers. Print sizes mirror the PDF. Only briefing-local CSS changed; the approved workspace styles remain untouched.
* PDF fonts are now bundled **static Open Sans 3.003**, 400/700 at width 100, instantiated with preparation-only fontTools 4.68.0 from the official Google Fonts repository. Both static TTFs and the upstream SIL OFL 1.1 licence ship under `backend/churn_backend/fonts/`; no OS fonts, runtime network call or runtime fontTools dependency is introduced. The module-relative paths work independently of the current working directory. [Font provenance and preparation](../backend/churn_backend/fonts/README.md) records the pinned revision and SHA-256 values.
* Both faces cover U+2212 minus, en dash, middle dot, bullet, greater-than-or-equal, curly quotes and normal Malay/English text. Tests verify both embedded faces and retain the existing explicit unsupported-glyph error/message, including emoji rejection.
* Baseline before changes: **115 tests** (41 backend/API/PDF, 8 copy/update, 8 JavaScript client, 58 React), plus Vite build. After the reviewed refinement and font change: **116 tests** (42 backend/API/PDF, 8 copy/update, 8 JavaScript client, 58 React), plus Vite build. The one new backend test comes from the reviewed refinement; font embedding/coverage assertions extend an existing test. No existing React freshness tests were weakened.
* Generated fixture PDFs retain a **two-page single-case** document. The long-name/multiline-note two-case stress document renders across **seven non-blank pages**. Browser comparison and database-integrity verification are recorded separately once completed; these fixture checks do not establish owner or representative-RM acceptance.
