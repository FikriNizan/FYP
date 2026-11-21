# Handoff — demo build and small polish

Date: 22 November 2026 (Malaysia time). Branch `final-refinement`, pushed to `origin/final-refinement`. Nothing merged into
`main`; no force-push; no trailers.

Requested after the owner's render-7 summary re-run was complete (206/206 current). No live Gemini call. The Working
database and the research folder were not touched.

| SHA | What |
|---|---|
| `e97c7b5` | Polish: unit-aware signal values, header note, chart lead sentence |
| (this file) | Handoff |

## 1. Demo build (`scripts/demo_session.py build`)

Command:

```PowerShell
.\.venv\Scripts\python.exe scripts\demo_session.py build --research-root $R
```

What the run did:
* copied `artifacts\m6-review.sqlite` (SQLite backup API) to `artifacts\m8-demo.sqlite`, with its origin record marked as the demo;
* checked that the copy holds exactly February, March and April 2024;
* removed the outcomes **in the copy only**;
* reused the May 2024 package, which already existed and validated, so nothing was prepared from the research folder.

Counts were then read through the app on the demo copy (GET only):

| Measure | Value |
|---|---|
| Batches | 3 (Feb, Mar, Apr 2024) |
| Predictions | 3,000 |
| Reviews / review history | 9 / 9 |
| Stored summary drafts (all render versions) | 419; plus 1 discussion draft |
| Flagged April customers with a **current render-7** summary (`saved` state) | **206 of 206** (render-7, m6-evidence-6) |
| Outcomes | **0** (3,000 removed in the copy; source unchanged) |
| Outcome check (`/api/months`) | Feb, Mar and Apr: all `waiting` |
| Schema | 6 (the source had already been migrated, so no new migration or backup) |

Launch the demo on separate ports. The scoring settings are needed so the May upload can be scored:

```PowerShell
$env:TXB_RESEARCH_ROOT = $R; $env:TXB_MODEL_PYTHON = 'C:\Users\fikri\fyp-model-env\Scripts\python.exe'
.\.venv\Scripts\python.exe scripts\local_session.py m8-demo --backend-port 5086 --frontend-port 5196
```

Then open Monthly Assessments and upload `artifacts\m8-packages\prepared-2024-05\features.csv` and `manifest.json`. Expect:
* "February 2024 is now ready to check. Outcomes derived from Mar–May 2024 activity for 1,000 of 1,000 customers."
* March: "Ready after May 2024 data" before the upload, then "Ready after June 2024 data" after it.
* April: "Ready after July 2024 data".

These labels name the last month of each assessment's forecast window.

To rebuild after another summary run (`--rebuild` replaces only `artifacts\m8-demo.sqlite`):

```PowerShell
.\.venv\Scripts\python.exe scripts\demo_session.py build --research-root $R --rebuild
```

## 2. Polish (presentation only)

**a. Signals: unit-aware values** (`frontend/src/format.js`, `driverValue`):
* Counts are whole numbers with a unit: "1,007 collections a month", "0 per session", "2 active fixed deposits", "1 of the last 3 months with none".
* Rates and shares are %. Money is RM, with "a month" added for flow, fee and waiver means.
* Changes read as "42.0% lower than the previous 3 months". Recency reads as "27 days ago" or "1 month ago". The tier shows its plain name.
* All values remain the saved feature values.

**b. Customer header** (`pages/CustomerReview.jsx`): "a month, last 3 months" sits under the recent-activity amount.

**c. Chart takeaway** (`components/FlowHistory.jsx`):
* For combined flow, the chart now leads with "Last 3 months averaged RM X a month, Y% below the 12-month average."
* The sentence is built from the saved `combined_flow_mean_3m_myr` and `combined_flow_ratio_3m_to_12m`, passed in from the customer and case APIs. Nothing is recomputed from the bars.
* The month-on-month sentence stays as secondary (muted) text.
* Other measures, or a missing value, keep the monthly takeaway as the lead.

Tests:
* `frontend/tests/polish.test.jsx` (new, 3 tests): unit-aware values, the lead sentence plus the secondary line plus behaviour on measure switch, and the fallback when the API values are missing.
* `app.test.jsx`: one added assertion, that the header note sits next to the API amount.

**No assertion was changed or removed.**

## Commands and actual outputs

`.\.venv\Scripts\python.exe scripts\check.py`, exit 0:
* backend `Ran 215 tests — OK (skipped=1)`;
* utility `Ran 35 tests — OK (skipped=11)`;
* Node `tests 10, pass 10, fail 0`;
* React `Test Files 14 passed, Tests 118 passed`;
* build `✓ built in 361ms`.

## Open questions / limitations

* Count units are a display mapping by predictor family in `format.js`. A predictor without a mapped unit shows a whole number with no unit.
* The demo copy carries 419 stored summary drafts, including older render versions. Only the 206 current render-7 drafts are served.
