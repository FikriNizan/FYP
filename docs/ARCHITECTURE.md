# Architecture and data flow

## 1. Separate three kinds of work

| Kind                  | Responsibility                                                                                                                                                  | When it runs                                             | Current status                                                                                     |
| --------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------- | -------------------------------------------------------------------------------------------------- |
| Research and training | Generate/clean research data, examine features, compare models, select and evaluate a champion                                                                  | During investigation or a controlled future model update | Existing research project; retained as evidence                                                    |
| Monthly processing    | Validate a prepared batch, calculate features as of the cutoff if needed, use the frozen model and calibrator, generate explanations, publish an accepted batch | Once per new monthly package                             | Existing importer consumes completed exports; an online scoring pipeline is still to be integrated |
| Application runtime   | Read published evidence, show it to users, save committee decisions and follow-up records                                                                       | Whenever a user uses the dashboard                       | Flask + SQLite + browser UI in this repository                                                     |

Notebooks can be research records **and** contain useful pipeline logic. They are not all disposable. Code for cleaning, feature engineering and inference may need to become reusable modules. Inspect its input/output and temporal rules before moving it. The dashboard must not retrain the model when a page opens or a monthly batch arrives.

## 2. Current runtime

The browser requests HTML/CSS/JavaScript from Flask. Its JavaScript requests `/api` JSON from that same Flask address. Flask reads saved evidence and human reviews from SQLite. The frontend sends a committee decision by `PUT`; the backend validates it and saves both the current review and a historical version.

One process is deliberate for this stage: no separate frontend development server, CORS configuration or frontend build tool is required. Separate folders preserve responsibilities without requiring separate deployed services.

Current serving matches Flask's documented [single-page application pattern](https://flask.palletsprojects.com/en/stable/patterns/singlepageapplications/). [Application factory](https://flask.palletsprojects.com/en/stable/tutorial/factory/) and [project layout](https://flask.palletsprojects.com/en/stable/tutorial/layout/) references explain the backend structure.

## 3. Current import boundary

The existing `import-shap` command reads:

* `dashboard_explanations.jsonl`: saved per-customer predictions, model policy and explanations.
* `feature_values.csv`: saved model inputs, joined by customer identifier and cutoff.
* `feature_catalog.csv`: feature definitions/catalogue used to verify the export.
* The export manifest and expected hashes.
* Optional customer master: names joined by identifier.
* Optional monthly flows: only history through the selected cutoff.

The importer checks the completed export, feature schema, protocol identity and mathematical reconstruction of the prediction before committing a new batch. It imports **saved model outputs**; Flask is not currently loading a CatBoost binary or scoring new arbitrary feature rows.

Example from the new root, if a complete research import is needed instead of database copying:

```PowerShell
$fypData = "C:\Users\fikri\OneDrive - Asia Pacific University of Technology And Innovation (APU)\Degree\SEM 6\Project Module (FYP)\fyp-data-refinement"
.\.venv\Scripts\python.exe -m flask --app backend/app.py import-shap --directory "$fypData\data\models\shap_explainability_v1" --month 2024-02 --customer-master "$fypData\data\final_v4_0_1\cleaned\company_population_clean.csv" --flows "$fypData\data\final_v4_0_1\cleaned\monthly_flows.csv"
```

Keep existing data paths until the inventory is complete. A shorter code path does not require moving the research dataset.

## 4. Snapshot identity and review identity

* A **batch** is one imported assessment with a cutoff, protocol, source provenance and record count.
* A **prediction** identifies one customer within one batch.
* A **review** is a versioned human decision linked to that prediction.
* An **action** is a separately dated follow-up note linked to the original prediction.

The frontend sends an explicit `batch_id` with reads. It does not silently choose another import because two batches have the same cutoff month. Enriching an import with names/history can create a distinct batch. Earlier reviews remain with their original predictions; they are not automatically transferred to a new import.

New monthly assessments can change risk substantially. They do not overwrite January evidence or cancel January committee decisions. The next milestone will create a Reviewed Customers worklist that shows original decision context alongside the latest available assessment.

`expected_version` on a review write prevents a user from silently overwriting a decision saved by another session. The current PUT contract replaces the editable fields; the frontend therefore sends all of them.

## 5. Keep four concepts separate

| Concept           | Meaning                                                                                | UI treatment                                             |
| ----------------- | -------------------------------------------------------------------------------------- | -------------------------------------------------------- |
| Cutoff            | Latest month of information available for this prediction                              | Assessment selector and customer header                  |
| Observed activity | Recorded transactions through the cutoff                                               | Trend and recent-versus-usual comparison                 |
| Predicted risk    | Calibrated estimated probability of the defined next-three-month outcome               | Main percentage                                          |
| Review threshold  | Probability boundary for flagging a prediction                                         | Optional explanation; saved policy used without rounding |
| Outcome rule      | Future three-month mean combined flow at most 50% of a positive past twelve-month mean | Plain-language optional explanation                      |

February 2024 has observed history through February and forecasts March–May 2024. The next three-month outcome is not already observed in the displayed history. A lower next-month risk is a new prediction; it does not itself establish that an intervention worked.

## 6. Frozen champion contract

This starter preserves the model policy already agreed and exported. It does not refit or select another champion.

* Model: CatBoost baseline, followed by sigmoid recalibration.
* Model input count: **78**. The earlier 81-column model table includes identifiers/target; 81 is not the predictor count.
* Calibrated review threshold: `0.2586013233784648` (about 25.86%).
* Calibration slope: `0.9588242871048336`; intercept: `-0.23690175755868847`.
* Protocol SHA-256: `6ae6d17ef0dcb7c3b0b7e090bed0dbae475024f5c0606f71ad100411adb5a4dc`.
* SHAP contributions are in calibrated log-odds. The supplied higher/lower contributions, base value, remaining-feature contribution and clipping adjustment reconstruct the saved risk within importer tolerances.

Sigmoid recalibration transforms the fitted model's output; it is not an activation layer inserted into CatBoost's trees. Threshold changes affect flagging, while changes to the target definition require a new labelled/model evaluation protocol. Future flexibility must preserve versioned policy and comparable evidence.

The provisional champion remains a research decision supported by offline comparison. A working web application does not establish real-bank effectiveness or deployment readiness.

## 7. Preserve evidence and business judgement

SHAP appears in a shared section, because a risk driver can relate to flows, service, deposits or pricing. Operations and Finance then review their own evidence and enter a joint decision. SHAP explains the model prediction; it does not establish the cause or prescribe a guaranteed solution.

Balances are exposures. Fees and waivers are separate historical monthly estimates, not confirmed net profit or retention savings. Unknown values remain missing; an actual zero remains zero.

Human review records do not write back into the frozen risk or relabel the target. Follow-up and outcomes need separate records. Later intervention monitoring must distinguish predictive evaluation from treatment effectiveness; excluding intervened cases gives a selected non-intervened subset, not an unbiased estimate for the original portfolio.

## 8. Inventory the old research project before reorganising it

Create one inventory row per existing notebook/script. Do not rename or delete files first.

| Record           | What to write                                                                                               |
| ---------------- | ----------------------------------------------------------------------------------------------------------- |
| Path             | Exact current filename and directory                                                                        |
| Purpose          | One sentence: generation, cleaning, feature calculation, splitting, training, calibration, SHAP or analysis |
| Inputs           | Files/tables and required cutoff                                                                            |
| Outputs          | Exact output paths and manifest/version                                                                     |
| Dependencies     | Prior script or artifact required                                                                           |
| Leakage boundary | Latest observed month and whether future labels are used                                                    |
| Execution        | Exact command, or notebook cells required in order                                                          |
| Disposition      | Research-only, reusable processing logic, frozen artifact producer, or superseded with evidence             |

Known conceptual sequence: synthetic generation → cleaning/harmonisation → historical features and future labels → temporal validation/splits → model comparison and champion selection → calibration and threshold selection → final evaluation → SHAP export → application import.

This sequence is a map of responsibilities, not a claim that every raw-source temporal check has already been audited. The complete notebooks/pipelines are not bundled here. Their exact filenames and relationships still need the inventory.

## 9. Database changes from here

The v0.2.0 starter uses the existing v1 table layout; copying the database requires no schema conversion. `CREATE TABLE IF NOT EXISTS` only initialises the present schema. It is not a general migration system.

Before adding follow-up tables or changing columns, introduce explicit versioned migrations, take a backup and test upgrading an existing database. Alembic is one possible later choice; it is not required just to use this unchanged schema. Keep migrations in Git and customer databases outside Git.
