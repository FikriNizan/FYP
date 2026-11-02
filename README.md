# Corporate Attrition App — Full-stack Foundation

A development starting point for the Fikri Nizan FYP: an explainable decision-support dashboard for silent corporate transaction-volume attrition in Malaysian banking.

This project joins the existing Flask/SQLite backend to a modular HTML/CSS/JavaScript frontend. It serves a live monthly portfolio, customer evidence and a committee review form. Decisions are saved through the API into SQLite, not browser storage. The original research project and backend folder can remain where they are.

**Start here:** complete sections 1–4 below before reorganising your research files or adding features. This README describes the new application. [Development roadmap](docs/ROADMAP.md) tracks the remaining work; this is not the complete FYP delivery.

## What the API checks established

Your February 2024 import reports 1,000 assessed customers, 208 flagged, 792 below the threshold, customer names loaded, full feature values loaded, and transaction history loaded. The supplied Customer 944 response contains 78 model inputs and twelve observed monthly flow records. These are imported historical synthetic research results, not newly generated live predictions.

The database contains the data. This ZIP contains application source and the existing one-case demo; it does **not** contain your 1,000-customer database or trained model binaries. Copy your current database in section 3 to retain the full portfolio and any reviews.

## 1. Understand the pieces

| Location                                      | Purpose                                                                   | Edit it when…                                          |
| --------------------------------------------- | ------------------------------------------------------------------------- | ------------------------------------------------------ |
| `frontend/index.html`                         | Browser page shell                                                        | Changing the overall page structure                    |
| `frontend/src/main.js`                        | Portfolio, customer review and interaction behaviour                      | Changing what a user can do                            |
| `frontend/src/styles.css`                     | Layout, colours and responsive presentation                               | Refining the design                                    |
| `frontend/src/api.js`                         | Browser-to-Flask requests                                                 | Adding or changing API calls                           |
| `frontend/src/format.js`                      | Shared plain-language formatting                                          | Changing display rules for percentages, money or dates |
| `backend/app.py`                              | Starts the application                                                    | Changing local startup                                 |
| `backend/churn_backend/api.py`                | HTTP API routes                                                           | Adding a server operation                              |
| `backend/churn_backend/repository.py`         | Database reads and writes                                                 | Changing persistence or queries                        |
| `backend/churn_backend/validation.py`         | Input and evidence validation                                             | Changing what the server accepts                       |
| `backend/churn_backend/importer.py`           | Imports completed research exports                                        | Extending the prepared-batch import                    |
| `backend/churn_backend/schema.sql`            | Current SQLite table definitions                                          | Planning a database migration                          |
| `backend/tests/`, `tests/`, `frontend/tests/` | Automated checks                                                          | Verifying meaningful behaviour                         |
| `scripts/`                                    | Local checks and safe database copying                                    | Automating repeatable developer tasks                  |
| `.github/workflows/ci.yml`                    | Runs checks on GitHub                                                     | Changing continuous integration                        |
| `docs/`                                       | Architecture, workflow and delivery checklist                             | Recording decisions and progress                       |
| `research/`, `data/`, `artifacts/`            | Documented boundaries for research, private inputs and frozen model files | Connecting later pipeline/scoring stages               |

Frontend = what users see and click. Backend = trusted server operations. Database = records that survive restarting. Together these make a full-stack application. Machine learning supplies prediction evidence; it is an additional component, not a substitute for these layers.

A single repository can contain these separate responsibilities. It does not need one universal `src/` folder. There is no frontend build process at this stage: Flask serves the HTML, CSS and JavaScript directly.

## 2. Create a clean development folder

Keep your old folders as the reference and backup. Extract the ZIP so the project root is, for example:

`C:\Projects\corporate-attrition-app`

The root should directly contain `README.md`, `backend`, `frontend`, `scripts` and `requirements.txt`. Avoid accidentally opening an extra parent ZIP folder. A short path outside OneDrive is convenient for source code; the research inputs can stay in their current location.

Open that root in VS Code, open a PowerShell terminal, then run:

```PowerShell
cd C:\Projects\corporate-attrition-app
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Python 3.12 is the application runtime. Node.js 24 is only needed for local JavaScript checks; it is not required to start or use the dashboard. Git is needed when you reach the version-control exercise.

Do not recreate the virtual environment each time you start the app. Create it once per checkout and reinstall requirements when they change.

## 3. Copy your current database

Stop the old Flask server with Ctrl+C. **Do this before starting the new application**, since starting creates an empty destination database if none exists.

The old backend defaults to `instance\churn.sqlite`. If you set `CHURN_DB_PATH`, use that actual source path instead. In the new project root:

```PowerShell
$oldBackend = "C:\Users\fikri\OneDrive - Asia Pacific University of Technology And Innovation (APU)\Degree\SEM 6\Project Module (FYP)\fyp-flask-backend-v1"
Test-Path "$oldBackend\instance\churn.sqlite"
.\.venv\Scripts\python.exe scripts\copy_database.py "$oldBackend\instance\churn.sqlite"
```

`Test-Path` should return `True`. The copy script reports row counts for batches, predictions, reviews, review history and actions. It checks SQLite integrity, preserves the source and refuses an existing destination. Predictions across multiple imports can exceed 1,000; **the selected February batch** should still contain 1,000 customers.

If it refuses because the new destination already exists, inspect what is in that database before replacing anything. To copy to a different new filename:

```PowerShell
.\.venv\Scripts\python.exe scripts\copy_database.py "$oldBackend\instance\churn.sqlite" --destination "C:\Projects\corporate-attrition-app\backend\instance\copied-churn.sqlite"
$env:CHURN_DB_PATH = "C:\Projects\corporate-attrition-app\backend\instance\copied-churn.sqlite"
```

That environment variable applies to this terminal; set it again in a new terminal if you use a custom path. Do not switch back and forth between two independently edited database copies. Once the new setup is checked, use the new copy for ongoing development and keep the original as a backup.

**Only if you have no existing database:** import the single saved case instead. This is an alternative, not the 1,000-customer setup:

```PowerShell
.\.venv\Scripts\python.exe -m flask --app backend/app.py init-demo
```

For a fresh import of a complete monthly export, see [Architecture and data flow](docs/ARCHITECTURE.md). You do not need to reimport after copying the database.

## 4. Run and complete your first full-stack exercise

From the new project root:

```PowerShell
.\.venv\Scripts\python.exe backend\app.py
```

Open `http://127.0.0.1:5000/`. The root now serves the dashboard; the former root JSON index is at `/api`. API endpoints such as `/api/summary` remain available.

1. Choose the February assessment showing **1,000 customers, names + trends**. The selector includes a short batch ID so previous versions of the same month remain distinguishable.
2. Confirm 1,000 assessed, 208 flagged and 792 below the threshold for your latest February batch. These are data checks, not hardcoded page values.
3. Search for customer `944` and open its review.
4. Confirm about **84.4% predicted risk**, **MYR 2,016,997.13 operating account balances**, **MYR 0 fixed deposits**, and the observed monthly trend. An older partial demo batch has missing values; select the enriched batch explicitly.
5. Save a test committee decision with a clear reason and your reviewer name. This is a real write to the copied development database. Use a reason such as “Development acceptance test” so it is distinguishable from an actual committee decision.
6. Reload the page, then restart Flask and revisit the same assessment. Confirm the saved decision remains and the model score has not changed.
7. Return to the overview and confirm the relevant review count changed.

This connects the whole stack: browser form → HTTP request → server validation → database transaction → refreshed browser data. Read `api.js`, `api.py`, then `save_review()` in `repository.py` to trace that one operation.

No post-review action entry is required to save a committee decision. The dedicated cross-month Reviewed Customers workflow is the next feature milestone.

## 5. Run checks before changing code

Backend and database-copy checks require only Python:

```PowerShell
.\.venv\Scripts\python.exe scripts\check.py --backend-only
```

With Node.js 24 installed, run everything:

```PowerShell
.\.venv\Scripts\python.exe scripts\check.py
```

The starter has 22 backend checks, 4 database-copy checks and 6 JavaScript checks. Tests use temporary databases. They do not open your copied development database. The test runner also checks JavaScript syntax.

Automated coverage includes the existing evidence/import protections, review persistence and conflict handling, frontend asset serving, copying without overwrite, and display rules such as missing versus zero. This is not a substitute for the browser exercise above or user testing.

## 6. Put the application under version control

Follow [Developer workflow](docs/DEVELOPMENT.md) after the local exercise works. It explains Git, branches, commits, pull requests and CI in beginner terms, with exact commands.

The included workflow runs checks on pull requests and pushes to `main`. It has been prepared and the same checks run locally; no remote GitHub repository or workflow run has been created for you. There is no deployment workflow yet. Choose a hosting target and address authentication/persistent storage before adding CD.

## Current capability and scope

Implemented in this starter:

* Live API-backed assessment selection, summary, searching, filtering and pagination.
* Customer detail using saved risk, supplied SHAP signals, observed flow history, Operations and Finance evidence.
* Shared SHAP section across both business perspectives, with plain-language labels and optional technical details.
* Review decisions saved in SQLite, version checked to prevent silent overwrites. A conflict keeps the draft visible and requires explicitly loading the latest saved version.
* In-tab draft preservation while navigating; draft changes are not saved to the server until **Save decision**. Closing the tab can lose unsaved drafts.
* Original backend import, review history and action APIs retained.
* Safe database-copy script, Git exclusions, checks and a GitHub CI workflow.

Remaining milestones: cross-month Reviewed Customers and linked follow-up tracking; briefing/PDF; a defined monthly input package and automated scoring; outcome/intervention monitoring; grounded GenAI; OPR scenario demonstration. See [Roadmap](docs/ROADMAP.md).

This local foundation has no authenticated users, background job queue or deployed hosting. Reviewer names are user-entered attribution. Keep those distinctions in the final report when describing what was implemented versus planned.

## Documentation order

1. This README — get the application running and understand the folders.
2. [Architecture](docs/ARCHITECTURE.md) — research versus monthly processing versus runtime.
3. [Development](docs/DEVELOPMENT.md) — make one small change, test and commit it.
4. [Roadmap](docs/ROADMAP.md) — finish one milestone at a time.
5. [Verification](docs/VERIFICATION.md) — checks performed and remaining local acceptance tests.
6. [API contract](backend/API_CONTRACT.md) — request/response details.

`docs/backend-v1-reference.md` preserves the original backend instructions as an archived reference. Its old folder commands and root JSON description do not replace this README.
