# Development roadmap and acceptance checklist

Use one current milestone at a time. Check a milestone only after its behaviour has been demonstrated; source code alone is not completion.

## Existing foundation

* [x] CatBoost champion policy and sigmoid recalibration exported from research.
* [x] Offline model assessment completed previously; real-bank effectiveness remains unestablished.
* [x] Existing backend imports verified saved exports with feature/protocol/explanation checks.
* [x] Existing backend stores immutable evidence separately from review decisions and action notes.
* [x] User imported the February 2024 full portfolio with names and historical flows.
* [x] User's original backend passed its 20 tests.
* [x] Static UI used for design/usability exploration; not treated as the runtime data source.

## Milestone 1 — React full-stack foundation (checkpoint)

Deliverable: one repository, one locally running app, one persistent committee-review journey.

* [x] Separate frontend, backend, scripts and documentation.
* [x] Correct the starter to React + Vite, preserving the existing Flask API and database schema.
* [x] Add a guarded source updater for the existing Windows project; preserve its database and Git setup.
* [x] Serve frontend and API together from Flask.
* [x] Read actual API summaries, customer lists, features, SHAP and flow history.
* [x] Save reviews with backend validation and version checks.
* [x] Keep an unsaved in-tab draft separate from a saved decision.
* [x] Distinguish missing money from zero; observed values from predictions.
* [x] Shared model signals above separate Operations and Finance perspectives.
* [x] Safe database-copy script preserving the old source and refusing overwrite.
* [x] Local checks and a prepared GitHub CI workflow.
* [x] User copied the existing database (provided log: 3 batches, 2,001 prediction rows).
* [x] User applies the React source update and completes the browser exercise on Windows.
* [x] User confirms 1,000/208/792 and the verified Customer 944 values in the new app.
* [x] User confirms save/reload/restart behaviour in the copied database.
* [x] Create the private GitHub repository, push and verify the first remote CI run.
* [x] Usability pass at desktop/mobile widths with representative users.

Acceptance: a user can review one actual imported customer and retrieve the same saved decision after restarting, with the original evidence preserved.

## Milestone 2 — Reviewed Customers and follow-up

Implementation checkpoint (6 November 2026): the listed behaviours are implemented and covered by local automated checks. The [Milestone 2 acceptance walkthrough](MILESTONE_2.md#acceptance-walkthrough-with-your-portfolio) remains pending; this milestone is not yet signed off. The checkboxes below remain open until that walkthrough is demonstrated.

Do this after the React checkpoint and before GenAI or OPR. Follow [MILESTONE\_2.md](MILESTONE_2.md) for the first implementation slice.

* [x] Introduce tested, versioned database migrations before schema changes.
* [x] Define a stable reviewed-case/follow-up identity so a case survives a new monthly batch.
* [x] List reviewed customers with original decision month/risk, reviewer, reason, owner and follow-up state.
* [x] Show latest available assessment month/risk and latest historical flow/SHAP alongside the original decision context.
* [x] Never auto-cancel a decision solely because a new monthly risk falls.
* [x] Add a linked follow-up lifecycle, rather than unrelated planned/completed notes with no task identity.
* [x] Allow a completed RM contact, service action or unsuccessful attempt to be recorded after the event; no immediate action log required on committee save.
* [x] Record who/when/what, intervention delivery date/type and notes. Treat a planned action separately from an actual intervention.
* [x] Show explicit manual case closure/defer decisions and their reasons; preserve audit history.
* [x] Test a January prioritisation followed by a lower February score.

Acceptance: a reviewer can find a previously prioritised customer after a new import, see both contexts and record a later follow-up without altering the earlier prediction.

The existing `/actions` endpoints support dated notes but do not implement the complete linked task lifecycle. They are retained, not presented as a completed Reviewed Customers feature.

## Milestone 3 — RM briefing and PDF

* [x] Generate a deterministic briefing from selected prioritised customers.
* [x] Include customer/assessment identity, forecast and risk, recorded flow trend, top signals, Ops/Finance findings, committee rationale, owner and next step.
* [x] Include questions for a relationship discussion, phrased as hypotheses to verify.
* [x] Keep figures traceable to the saved assessment and label unavailable data.
* [x] Add a readable print/PDF export; a briefing can be generated before any outreach.
* [x] Include original review and latest assessment dates where they differ.

Acceptance: an RM receives a reproducible briefing that does not confuse model evidence with confirmed customer complaints.

Implementation and software/PDF verification completed on 9 November 2026; see [MILESTONE_3.md](MILESTONE_3.md) for the direct-download contract, dependencies, evidence and Windows acceptance steps. The owner's own acceptance walkthrough remains pending. Live GenAI remains in the later AI milestone.

## Milestone 4 — Monthly package and automated processing

Start by choosing and documenting one input contract. Recommended first integration: a **new month's complete prepared feature table**, with required metadata/provenance, plus optional names/observed history. Do not require the user to re-upload the entire past feature table every month. Historical rows are preserved by the application. Rolling features still require the upstream pipeline to use adequate history.

* [ ] Inventory the existing generation/cleaning/features/training/export files and their dependencies.
* [ ] Extract reusable feature/scoring logic from notebooks where necessary, without changing research results silently.
* [ ] Formalise required keys, feature names/order/types, categorical values, units, cutoff, completeness, missing values and protocol version.
* [ ] Verify outstanding raw/source-level temporal boundaries and label maturity checks; do not assume application tests complete that audit.
* [ ] Decide whether a supplied package contains ready features or raw source tables. Ready features are the smaller first application scope.
* [ ] Load the frozen model, calibrator and saved threshold; do not retrain on upload.
* [ ] Add validate → process → verify → publish states. Failed validation must leave the last published batch unchanged and return useful errors.
* [ ] Use a separate upload limit and deliberate background-job design if processing is too slow for a request. The existing 64 KiB human-note limit is not a monthly-file upload limit.
* [ ] Prevent duplicate/replaced imports from silently moving prior reviews.
* [ ] Benchmark validation/ETL, feature calculation, model inference, SHAP, import and API latency separately at the 1,000-customer scale.
* [ ] Set SMART latency/throughput targets from measured baselines and project requirements; record hardware and coverage.

Acceptance: a genuinely new prepared monthly package is validated, scored and published reproducibly, while failure preserves prior data and scores/history remain traceable.

## Milestone 5 — Outcomes and intervention-aware monitoring

* [ ] Load observed outcomes only when the three-month horizon is fully available.
* [ ] Retain prediction, committee decision, action delivery and realised outcome as distinct records.
* [ ] Derive intervention exposure from actual action type/date and the assessment window; do not treat every note or planned contact as an intervention.
* [ ] Report outcome maturity and intervention coverage counts.
* [ ] Report descriptive outcomes for intervened customers separately. Non-intervened metrics are for a selected subset, not an unbiased portfolio estimate.
* [ ] Document that no counterfactual/control design means no proven intervention effectiveness.
* [ ] Monitor drift and predictive performance over time without inventing labels for unmatured cases.

Acceptance: the report can explain why a delivered intervention and a non-attrition outcome do not prove either a model error or successful retention.

## Milestone 6 — Grounded GenAI

* [ ] Define a structured evidence payload with allowed fields and traceable numeric values.
* [ ] Keep model probabilities, money, dates and SHAP math deterministic; the LLM writes only bounded narrative/questions.
* [ ] Use non-causal language and require evidence-linked claims.
* [ ] Validate output schema, unsupported claims and numeric consistency; provide a deterministic fallback.
* [ ] Require human review before using the briefing with a customer.
* [ ] Evaluate faithfulness and usefulness with examples; do not claim a mathematical guarantee of hallucination-free narrative.

Acceptance: generated questions help the RM investigate evidence without inventing customer motives or financial facts.

## Milestone 7 — OPR demonstration, evaluation and release

* [ ] Define OPR as a separate assumptions-based scenario rather than observed portfolio truth.
* [ ] Source/justify pass-through, renewal/exit and competitor-response assumptions; expose adjustable assumptions clearly.
* [ ] Show scenario changes and their limits without hardcoding a claimed loss of model accuracy.
* [ ] Complete user testing and the final evidence-linked report, including accepted/rejected supervisor suggestions and their justification.
* [ ] Select a deployment environment; add authentication, persistent storage, backups and production serving appropriate to the chosen scope.
* [ ] Run actual deployment tests and only then add a release/CD workflow.

Acceptance: scenario results, model evaluation, user decisions and observed outcomes remain clearly distinguishable.
