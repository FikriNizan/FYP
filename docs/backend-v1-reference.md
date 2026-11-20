> Archived backend v1 reference. Use the root README for current folder commands and frontend startup. The original root JSON index is now at `/api`.

# Corporate attrition Flask backend — milestone 1

This backend serves saved prediction evidence and stores human review decisions and dated action notes. It is the foundation for the frontend. The champion, sigmoid calibration, target and research threshold are unchanged.

## Start here: Windows PowerShell

Extract the ZIP, open the `fyp-flask-backend-v1` folder in VS Code, and open its terminal. Run these commands from that folder:

```PowerShell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m flask --app app init-demo
.\.venv\Scripts\python.exe app.py
```

No activation or PowerShell execution-policy change is required. Keep the final command running while using the API. Stop it with Ctrl+C.

Open these addresses:

* <http://127.0.0.1:5000/api/health>
* <http://127.0.0.1:5000/api/summary>
* <http://127.0.0.1:5000/api/customers/944>

JSON in the browser is the expected result at this stage. UI design and frontend implementation come separately.

The bundled example is **one exact customer case from your executed full-data SHAP notebook**: customer 944, February 2024, risk 84.4091949823%, frozen cutoff 25.8601323378%. Its source notebook checksum is recorded. It is **not the whole February population**. Only the ten feature values printed with that explanation are available. Missing names, fee estimates, FD balances and transaction histories remain null or empty; the observed non-FD balance is retained. No additional customers or financial values have been invented.

SQLite creates `instance/churn.sqlite` automatically. Stopping and restarting the server preserves decisions and notes. Running `init-demo` again is safe and does not reset existing reviews.

## Load your full monthly results

Your completed SHAP notebook already produced the required files on your computer. This backend does not need CatBoost installed and does not load model pickles: it serves that saved evidence.

1. Stop the server.
2. Replace the placeholder project path below with the folder containing your existing modeling project.
3. Run the import command and restart the server.

```PowerShell
$fypProject = "C:\path\to\fyp-data-refinement"
.\.venv\Scripts\python.exe -m flask --app app import-shap --directory "$fypProject\data\models\shap_explainability_v1" --month 2024-02 --customer-master "$fypProject\data\cleaned\company_population_clean.csv" --flows "$fypProject\data\cleaned\monthly_flows.csv"
.\.venv\Scripts\python.exe app.py
```

`data/cleaned` is the existing ETL output folder; adjust these two paths if your folders differ. The customer master and flows arguments are optional. Without them, names and flow histories stay unavailable. Financial indicators come from `feature_values.csv`, not customer names or fabricated defaults.

The required files in the explanation directory are:

| File                           | Used for                                                     |
| ------------------------------ | ------------------------------------------------------------ |
| `explainability_manifest.json` | Successful run, frozen calibration/policy and file checksums |
| `dashboard_explanations.jsonl` | Saved probabilities, flags and compact SHAP explanations     |
| `feature_values.csv`           | The two keys and all 78 original predictor values            |
| `feature_catalog.csv`          | Feature labels, groups and numeric/categorical kinds         |

The importer validates the complete explanation export before importing the selected month. It checks matching customer-month keys, exact predictor schema, file hashes and sizes, the accepted experiment identity, saved calibration, flags and probability reconstruction. Outcome labels are not accepted as model evidence. The earlier 20-customer technical fixture has a different policy and is rejected.

For the completed full run, February contains 1,000 customer records. That full export is not bundled here. Exact monthly records are imported only when you run this command against your local outputs.

Reimporting an identical month is a no-op. A genuinely different context/export becomes a new batch instead of overwriting old evidence or reviews. Full export batches are preferred to the single sample when selecting a month. `/api/months` lists batch identifiers, and `?batch_id=...` explicitly selects any preserved version.

Import another existing month by changing `--month`, for example to `2024-03`. Historical flow charts contain only observations through the selected cutoff and retain up to twelve months. Snapshot history shows only imported prediction months; the backend does not invent missing scores.

## Save a review

Keep the server running. Open a second PowerShell terminal in this folder:

```PowerShell
$evidence = Invoke-RestMethod "http://127.0.0.1:5000/api/customers/944?month=2024-02"
$predictionId = $evidence.customer.prediction_id
$reviewBody = @{
    decision = "prioritise"
    reason = "Demo review: investigate the recorded friction and lower usage."
    operations_notes = "Ask whether the recorded failures reflect an actual service issue."
    finance_notes = "Assess the available fee and balance indicators."
    owner = "Example RM"
    next_action_date = (Get-Date).AddDays(7).ToString("yyyy-MM-dd")
    reviewer = "Example reviewer"
    expected_version = $evidence.customer.review.version
} | ConvertTo-Json
Invoke-RestMethod -Method Put -Uri "http://127.0.0.1:5000/api/predictions/$predictionId/review" -ContentType "application/json" -Body $reviewBody
```

The choices are `prioritise`, `monitor` and `no_immediate_action`. Customers without a decision are `awaiting_review`. A reason and reviewer attribution are required. Owner and next-action date are optional in this milestone.

`expected_version` is copied from the retrieved review. If two people save the same version, the second save receives HTTP 409; reload before saving. This preserves the other person's decision. Every successful change has a saved version in review history. `PUT` replaces the editable review fields; omitted optional text fields become empty.

The saved prediction, threshold and explanation stay unchanged. Financial and operational assessment fields are notes, not new model predictors.

## Record a dated action note

Use the same `$predictionId` in that second terminal:

```PowerShell
$actionBody = @{
    action_type = "rm_visit"
    action_status = "planned"
    action_date = (Get-Date).AddDays(7).ToString("yyyy-MM-dd")
    notes = "Demo plan only: prepare questions about usage and service friction."
    recorded_by = "Example RM"
} | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:5000/api/predictions/$predictionId/actions" -ContentType "application/json" -Body $actionBody
```

Types: `rm_visit`, `customer_contact`, `service_fix`, `other`. Statuses: `planned`, `attempted`, `delivered`, `cancelled`. Actual attempted/delivered actions cannot have future dates. Notes are append-only in this milestone. Planned activity does not imply an intervention occurred. These entries are user-recorded activity, not verified intervention effectiveness or a new training feature.

## What is complete and what follows

Complete: local API, successful export imports, customer risk/SHAP/feature evidence, available financial indicators, optional historical flows, monthly snapshot selection, saved decisions, review history and dated notes.

Next: UI design and frontend implementation connected to this backend. Then extend the working baseline with prepared monthly ZIP upload and new scoring, the consolidated RM PDF, OPR scenarios and grounded GenAI narratives.

This package does **not** provide a raw ETL interface, automatic retraining, future-outcome monitoring, causal retention estimates, PDF generation or GenAI. In particular, actions do not modify transaction data or relabel a customer. `actual_attrition` remains null and `outcome_status` is `not_loaded` until a later outcome module supplies mature observations. Missing outcomes are not treated as non-attrition.

This is a local research prototype. The server binds to 127.0.0.1; reviewer names are user-entered attribution, not authenticated identities. A frontend should use a same-origin API or Vite development proxy to `/api`; unrestricted cross-origin writes are not enabled. Authentication and bank deployment controls belong to a later deployment scope.

## Verify the backend

```PowerShell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

The tests cover imports, immutable evidence, persistent decisions, concurrent edits, action notes, rejection of invalid data, joined feature values and exclusion of future flows. Constructed test fixtures verify software behavior; their probabilities and financial values are not research findings.

See `API_CONTRACT.md` for the frontend integration contract and `validation/verification_summary.json` for checks run on this package.

## References

* Flask application factories: <https://flask.palletsprojects.com/en/stable/patterns/appfactories/>
* Flask SQLite pattern: <https://flask.palletsprojects.com/en/stable/tutorial/database/>
* Flask testing: <https://flask.palletsprojects.com/en/stable/testing/>

The prediction and SHAP interpretation remains the one documented in your earlier model/explainability packages.
