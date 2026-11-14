# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

Operations and Finance form the joint committee reviewing corporate customers with predicted transaction-volume attrition in a Malaysian banking context.

* Operations investigates recorded payment activity, failures and service friction, and coordinates service follow-up where appropriate.
* Finance considers balances, estimated fees and waivers to understand exposure and help prioritise committee capacity.
* The committee considers both perspectives and saves a reasoned human judgement.
* Relationship managers (RMs) prepare evidence-linked discussion briefings and return later to plan or record customer contact and follow-up.

These are perspectives and responsibilities in a shared workspace. View switching does not imply authenticated roles or access restrictions.

## Product Purpose

TxB Retention Studio turns saved model predictions, operational signals, financial context and transaction-flow history into an evidence-led customer review and follow-up workflow. Success means the committee can understand an assessment, record its judgement, and let an RM resume the case later with the original evidence and decision intact alongside the latest available assessment.

The target is silent transaction-volume attrition, not account closure. The defined outcome is a next-three-month average combined transaction flow at most half of a positive trailing twelve-month average.

## Positioning

The product combines model evidence with operational, financial, and transaction-flow context in a review workflow while preserving immutable prediction snapshots. Batch and prediction identifiers keep each customer assessment traceable to its imported evidence package.

## Operating Context

The primary journey is: choose an assessment → find a customer → understand the evidence → save the committee decision → prepare a briefing if useful → follow up later. Saving a committee decision does not require immediate outreach or an action log.

Overview is scoped to an exact saved assessment batch. Customer Review presents Summary, Operations and Finance perspectives on that same assessment. Reviewed Customers spans assessments so earlier decisions remain findable after later imports. A case links the original decision to dated follow-up tasks and events, with explicit manual defer, closure and reopening.

Monthly Assessments describes saved evidence coverage and provides the implemented upload, validation, scoring and publication flow for a complete prepared month; scoring requires the trusted local research environment to be configured. RM Briefing prepares a read-only structured discussion preview for explicitly selected prioritised cases, with working browser Print and local PDF download actions. Guide explains the workflow. Monitoring reads explicitly imported mature synthetic outcomes and saved follow-up delivery as descriptive evidence. AI drafting and OPR calculations remain unavailable or clearly labelled isolated design previews until their services exist.

The application is a local research/FYP prototype for a meeting-room laptop and narrower browser windows. It is not established as a production banking service.

## Capabilities and Constraints

* Assessments are selected by `batch_id` and are associated with a cutoff month.
* Customer records and prediction actions are traceable through `batch_id`, `cus_id`, and `prediction_id`.
* Reviews are versioned and stale edits must not overwrite newer decisions.
* Committee choices are Prioritise for RM, Monitor and No immediate action. Reason and reviewer attribution are required; owner, follow-up date and perspective notes are optional.
* Customer history can be examined across imported assessment batches.
* A case remains anchored to its original reviewed prediction. New imports and lower later scores do not rewrite the original decision or automatically close the case.
* Committee decision, case status, follow-up status and observed outcome are separate concepts. Plans and actual events have distinct dates, and linked task events preserve their history.
* Reviewer and event-author names are user-entered attribution, not authenticated identity.
* The workflow uses React/Vite with plain CSS, a Flask API and local SQLite persistence.
* The local saved-evidence workflow is the source of truth for this prototype; it is not live model scoring.
* The frozen CatBoost model policy, saved flagging threshold, assessment identifiers and immutable evidence must be preserved. The frontend formats and visualises saved values; it does not retrain, recalculate flagging from rounded scores or change the policy in the review flow.
* Observed activity ends at the assessment cutoff; predicted risk covers the following three months. Missing observations stay missing, and genuine zero values remain zero.
* Balances are exposures. Fees and waivers are separate historical estimates, not verified profit, invoices or guaranteed retention savings.
* Product explanations must preserve explicit uncertainty and limitations. Model explanations are not causal effects, financial values may be unavailable, and action logging does not establish retention effectiveness.
* Connected saved data, the real prepared-month upload flow, isolated demo previews and unavailable integrations must remain distinguishable. Preview interactions must not create real records, transmit files or announce successful scoring/publication.
* AI generation, live-bank inference, live outcome feeds and OPR scenario calculations are not established capabilities. Historical prepared-month scoring and administrator-loaded mature-outcome monitoring are local, bounded workflows; they do not imply live-bank performance or intervention effectiveness.

## Brand Commitments

The product name is TxB Retention Studio. Use clear banking-workflow language, neutral discussion questions and evidence-linked statements. Preserve uncertainty and avoid claims about customer motives, causal explanations or intervention effectiveness that the saved evidence cannot establish.

## Evidence on Hand

* Frontend application and routes: [`frontend/src/App.jsx`](./frontend/src/App.jsx)
* Customer review workflow: [`frontend/src/pages/CustomerReview.jsx`](./frontend/src/pages/CustomerReview.jsx)
* Reviewed cases and follow-up: [`frontend/src/pages/ReviewedCustomers.jsx`](./frontend/src/pages/ReviewedCustomers.jsx), [`frontend/src/pages/CaseDetail.jsx`](./frontend/src/pages/CaseDetail.jsx)
* Structured RM briefing: [`frontend/src/pages/Briefing.jsx`](./frontend/src/pages/Briefing.jsx)
* Portfolio overview and review queue: [`frontend/src/pages/Overview.jsx`](./frontend/src/pages/Overview.jsx)
* Backend API routes: [`backend/churn_backend/api.py`](./backend/churn_backend/api.py)
* Evidence snapshot and prediction relationships: [`backend/churn_backend/repository.py`](./backend/churn_backend/repository.py)
* Persistence schema: [`backend/churn_backend/schema.sql`](./backend/churn_backend/schema.sql)
* Case migration and lifecycle: [`backend/churn_backend/migrations/002_reviewed_cases.sql`](./backend/churn_backend/migrations/002_reviewed_cases.sql), [`backend/churn_backend/cases.py`](./backend/churn_backend/cases.py)
* Backend behavior tests, including customer `944`: [`backend/tests/test_backend.py`](./backend/tests/test_backend.py)
* Local prototype database: [`backend/instance/churn.sqlite`](./backend/instance/churn.sqlite)
* Current frontend brief and integration handoff: [`docs/dashboard-frontend-design-prompt.md`](./docs/dashboard-frontend-design-prompt.md), [`docs/UI_DESIGN.md`](./docs/UI_DESIGN.md)
* Milestone scope and verification limits: [`docs/MILESTONE_2.md`](./docs/MILESTONE_2.md), [`docs/ROADMAP.md`](./docs/ROADMAP.md), [`docs/VERIFICATION.md`](./docs/VERIFICATION.md)

No external customer testimonials, production outcome monitoring, or verified retention-effectiveness evidence is established in the product record.

## Product Principles

1. Make review decisions evidence-led rather than prediction-led.
2. Keep every assessment and decision traceable to its saved evidence snapshot.
3. Preserve uncertainty and distinguish signals from causal conclusions.
4. Support practical relationship-manager follow-up without relabeling model outcomes.
5. Make integration boundaries explicit and keep previews separate from operational records.

## Accessibility & Inclusion

Support keyboard navigation, visible focus, labelled forms, readable contrast and status cues that do not rely on colour alone. Provide exact values alongside charts and adapt the workspace for narrower browsers. Display money in MYR and human-facing dates in Malaysian context. These are design requirements, not a claim of audited accessibility compliance.

## Open Decisions

Production hosting, authentication/access control and a final deployment scope remain later decisions. Production hardening of monthly upload/scoring and outcome monitoring, grounded AI generation, and a justified OPR calculation contract require further integration work. Milestone acceptance and representative-user evaluation remain governed by the project roadmap; implemented screens alone do not establish sign-off.
