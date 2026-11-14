# Corporate Attrition App — React + Flask Foundation v0.3.0

An explainable decision-support application for silent corporate transaction-volume attrition in Malaysian banking. The frontend is **React + Vite**; Flask provides the API and SQLite stores saved assessments, committee reviews and actions.

This corrects the earlier v0.2.0 plain-JavaScript starter to match Part 1, Section 2.4.7 (React) and Section 2.4.6 (Flask). The existing model policy, import validation and database schema are preserved. Static HTML remains a design/usability artifact.

**Already using v0.2.0 and copied the database? Start with** **[UPGRADE\_TO\_REACT.md](docs/UPGRADE_TO_REACT.md).** Do not repeat the database import or replace your working project wholesale. The supplied updater previews changes, checks for local edits and preserves the database, virtual environment and Git repository.

## Where you are now

Milestone 4 Step 3 adds prepared monthly CSV + manifest upload, fresh frozen-model scoring and atomic publication through the existing Monthly Assessments page. Trusted optional enrichment now attaches names and recorded cutoff-safe history, and later deliberate committee reviews continue one existing case. The April historical replay matched all 1,000 archived results exactly on a separate database copy. See [MILESTONE\_4.md](docs/MILESTONE_4.md) for copyable Windows configuration, safe replay/comparison commands, measured timings and the separate pending Step 4 owner exercise. No milestone-wide sign-off is claimed.

Milestone 2 (Reviewed Customers and follow-up) is implemented. Milestone 3 now completes the existing RM briefing with a direct, read-only PDF download and freshness checks. See [MILESTONE\_3.md](docs/MILESTONE_3.md) for dependency setup, verified behaviour and the owner's pending Windows acceptance walkthrough; [MILESTONE\_2.md](docs/MILESTONE_2.md) retains the earlier workflow context.

Your supplied database-copy log showed three preserved batches and 2,001 prediction records. Those correspond to the one-case demo and two 1,000-customer imports. The selected enriched February batch remains a portfolio of 1,000 customers, with 208 flagged and 792 below threshold. At copying, there were zero reviews/actions; later development decisions will change those workflow counts.

## 1. Understand the stack

| Layer             | Responsibility                                                                                                         |
| ----------------- | ---------------------------------------------------------------------------------------------------------------------- |
| React             | Composes pages/components and handles user interaction, filters and drafts                                             |
| Vite              | Development server, React transformation and frontend build                                                            |
| Flask             | API routes, evidence/input validation and database operations                                                          |
| SQLite            | Persistent batches, immutable prediction evidence, versioned reviews and dated action notes                            |
| Research pipeline | Creates/validates features and produces frozen-model predictions/explanations; training is separate from serving pages |

Frontend = what users see and click. Backend = trusted server operations. Database = records that survive a restart. The first learning exercise is to trace one saved review through all three layers.

## 2. Find the right file

| Location                                                | Purpose                                                         |
| ------------------------------------------------------- | --------------------------------------------------------------- |
| `frontend/src/main.jsx`                                 | Starts React and the hash-based router                          |
| `frontend/src/App.jsx`                                  | Assessment selection, navigation and shared review/draft state  |
| `frontend/src/pages/Overview.jsx`                       | Portfolio counts, searching, filters and pagination             |
| `frontend/src/pages/CustomerReview.jsx`                 | Customer evidence and Ops/Finance layout                        |
| `frontend/src/components/ReviewForm.jsx`                | Editable review and explicit save/conflict handling             |
| `frontend/src/components/Signals.jsx`                   | Shared SHAP signals, plain-language/technical layers            |
| `frontend/src/components/FlowHistory.jsx`               | Recorded monthly flows and accessible exact-value table         |
| `frontend/src/api.js`, `format.js`                      | API requests and consistent display rules                       |
| `frontend/src/workspace.css`, `workspace-architect.css` | Ordered base/Architect styles; screen theme and A4 print rules  |
| `frontend/package-lock.json`                            | Exact resolved frontend dependency versions                     |
| `backend/churn_backend/`                                | Existing Flask API, importer, validation and persistence        |
| `backend/instance/churn.sqlite`                         | Default local database, excluded from source control            |
| `scripts/`                                              | Checks, safe database copying and guarded React source updating |
| `.github/workflows/ci.yml`                              | Backend tests, frontend tests and React build on GitHub         |

## 3. Run your existing project on Windows

Use **Node.js 24.15+ within 24.x** and Python 3.12. The tested Node version is recorded in `.nvmrc` and npm version in `frontend/package.json`. Node/npm are now required for frontend development and building.

After applying the update, install the locked dependencies once:

```PowerShell
cd "D:\Degree Life\FYP Full-Stack Development\corporate-attrition-app\frontend"
npm ci
```

Terminal 1 — Flask:

```PowerShell
cd "D:\Degree Life\FYP Full-Stack Development\corporate-attrition-app"
.\.venv\Scripts\python.exe backend\app.py
```

Terminal 2 — React development:

```PowerShell
cd "D:\Degree Life\FYP Full-Stack Development\corporate-attrition-app\frontend"
npm run dev
```

Open **<http://127.0.0.1:5173/>**. Vite forwards `/api` to Flask at port 5000. Keep both terminals running. React changes update in the browser as you edit.

For a single Flask address, run `npm run build` in `frontend` and open **<http://127.0.0.1:5000/>**. Flask serves the generated `frontend/dist` files. Rebuild after frontend changes when using this address. An unbuilt Flask root returns a useful 503 setup response while API endpoints remain available.

## 4. New checkout only

If you have no virtual environment in this checkout:

```PowerShell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Before first starting Flask, copy your existing database using `scripts/copy_database.py` and its actual source path:

```PowerShell
.\.venv\Scripts\python.exe scripts\copy_database.py "C:\path-to-your-existing-backend\instance\churn.sqlite"
```

Replace the example path with the real one. The script checks integrity, preserves the source and refuses an existing destination. It uses SQLite's backup API. If you set `CHURN_DB_PATH`, use that actual source/destination deliberately and keep the same environment configuration between restarts.

Only when no database is available, import the bundled single saved case:

```PowerShell
.\.venv\Scripts\python.exe -m flask --app backend/app.py init-demo
```

This supplies one customer with partial context. It is not the full 1,000-customer portfolio. For completed export imports see [Architecture](docs/ARCHITECTURE.md).

## 5. Verify the React foundation

1. Select the enriched February assessment beginning `5f30af…`, showing names + trends.
2. Confirm 1,000 assessed, 208 flagged and 792 below threshold (before changing its reviews).
3. Search for `944`; confirm PERKASA MULIA TRADING SDN BHD, about 84.4% risk, MYR 2,016,997.13 operating account balances and MYR 0 FD balance.
4. Check twelve observed flow months through February 2024. Forecast: March–May 2024.
5. Save a review with a clear reason such as “Development acceptance test”, then reload/restart and confirm it remains with the same batch.
6. In two tabs, confirm a stale save produces a conflict and preserves the unsaved notes until you explicitly load the latest decision.

These are API-derived values, not hardcoded display totals. The ZIP contains code and the existing one-case demo; the full portfolio comes from your preserved database.

From the project root:

```PowerShell
.\.venv\Scripts\python.exe scripts\check.py
```

Backend-only checks:

```PowerShell
.\.venv\Scripts\python.exe scripts\check.py --backend-only
```

The complete checks run 42 backend/API/PDF/migration tests, 8 database-copy/source-update tests, 8 JavaScript client/API tests, 58 React interaction/rendering tests, and a Vite build. Tests use temporary databases and constructed fixtures. See [Verification](docs/VERIFICATION.md) for scope and remaining user acceptance checks.

## 6. Current feature boundary

Implemented: API-backed assessment selection, portfolio, customer review, saved SHAP/flow/financial evidence, in-tab drafts and versioned saved decisions. React preserves the original evidence and uses the saved flag without recalculating it from rounded percentages. SHAP is shared across Operations and Finance. Financial zeros remain distinct from missing values.

Retained: completed-export CLI import, review history and dated action-note APIs. Reviewer names are user-entered attribution; authenticated identity is not implemented.

Milestone 2 implementation: Reviewed Customers, original/latest assessment comparison, persistent cases, linked follow-up tasks and events, explicit closure/defer/reopen decisions, audit history and version conflicts. Existing databases receive a timestamped SQLite backup before automatic migration on Flask startup; existing reviews are backfilled as cases. See [Milestone 2](docs/MILESTONE_2.md) for the acceptance walkthrough and [UI design](docs/UI_DESIGN.md) for the current frontend direction, connected features and preview boundaries. Browser acceptance with your portfolio remains to be completed.

Briefing/PDF is implemented in Milestone 3. Later milestones cover automated new-month inference, intervention-aware outcomes, grounded GenAI and an OPR scenario. See [Roadmap](docs/ROADMAP.md).

## 7. Learn through one working change

Start with a label in `ReviewForm.jsx`, test the page and commit it. Then trace `api.saveReview()` → Flask review route → `repository.save_review()` → SQLite. Learn React components, props and state through those files rather than introducing more tools at once.

Follow [Development](docs/DEVELOPMENT.md) for Git branches, commits, pull requests and CI. The included workflow runs `npm ci`, tests and a build. It is prepared; a remote GitHub run must still be confirmed after pushing. Deployment/CD follows a hosting and persistent-storage decision.

## Documentation

* [React update guide](docs/UPGRADE_TO_REACT.md) — preserve the project you already set up.
* [Milestone 2](docs/MILESTONE_2.md) — immediate next feature and acceptance criteria.
* [Architecture](docs/ARCHITECTURE.md) — research versus monthly processing versus runtime.
* [Development](docs/DEVELOPMENT.md) — daily developer workflow.
* [Roadmap](docs/ROADMAP.md) — overall progression.
* [Verification](docs/VERIFICATION.md) — evidence and test limits.
* [UI design](docs/UI_DESIGN.md) — Architect theme and workflow layout decisions.
* [API contract](backend/API_CONTRACT.md) — retained request/response contracts.

`docs/backend-v1-reference.md` is an archived original backend reference. Follow this README for current paths and frontend startup.
