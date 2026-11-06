# Design and build the TxB Retention Studio frontend

Act as a product designer and React frontend engineer. Design and implement a clear decision-support dashboard for a Malaysian bank’s transaction banking team. The dashboard helps Operations, Finance and relationship managers review corporate customers with predicted volume attrition, agree on priorities, and track follow-up. Work on the **frontend and its presentation layer**. Where a feature needs a new backend process, design the screen and its states using clearly labelled previews or unavailable controls.

Use the existing **React + Vite** project and **plain CSS**. Reuse the existing API adapter and Flask endpoints where they support the intended action. Keep the current database, model, thresholds and saved assessments intact. The earlier static HTML is a reference for user journeys, useful information and visual explanations. Treat its illustrative numbers, styling and screen density as design inputs, not authoritative data or layout requirements. If no repository is supplied, create a self-contained React prototype with isolated fixtures. If the tool can only produce designs, provide the corresponding screen mockups and interaction states.

## 1. Organise the product around the work

The primary journey is:

**Choose an assessment → find a customer → understand the evidence → record the committee decision → prepare a briefing if useful → follow up later.**

* **Operations** looks for changes in payment activity, failures and service friction. Its job is to identify issues worth investigating and, where appropriate, coordinate a service fix.
* **Finance** examines balances, estimated fees and waivers to understand exposure and help prioritise the committee’s capacity.
* **The committee** uses both perspectives and the model’s explanation to decide what deserves attention. The saved decision is a human judgement.
* **The relationship manager (RM)** sees the original decision, recent evidence and useful discussion questions, then records what happened after contact.

Build one shared workspace with consistent evidence and terminology. Operations and Finance are perspectives on the same case. View controls switch the information shown; they do not imply authenticated roles or access restrictions unless those are actually provided.

Use restrained navigation: **Overview**, **Reviewed Customers**, **Monthly Assessments**. Open **Customer Review** from a customer row, and **RM Briefing** from a reviewed case or a selection of prioritised cases. Place monitoring and the OPR scenario in a separate secondary area or an explicitly labelled design preview. Keep a short **Guide** within easy reach. Show the selected assessment month and batch where it scopes the data. Preserve that selection, filters and search when returning from a customer page.

## 2. Set the visual and writing rules

* Use a light, neutral workspace: off-white surfaces, graphite text, subtle dividers and one restrained accent for links and primary actions. Reserve status colours for meaningful states such as a review flag, overdue follow-up or error. Pair colour with text or an icon. Avoid a wall of coloured cards, heavy gradients and large decorative banners.
* On each screen, lead with the user’s decision or next action. Use spacing, alignment and typography to group content. Limit the overview to three prominent metrics and one compact visual; give the review queue the most space. Use tables and compact rows for routine information.
* Use a three-layer explanation pattern: **short label and takeaway → accessible “What does this mean?” explanation → expandable technical evidence**. Provide click and keyboard access to explanations; hover is optional. Place help beside the term. Do not repeat the same explanation across every card.
* Use short titles, one-sentence summaries, and labels that make sense without a project briefing. Keep full reasons, notes, definitions, source metadata and methodology available through detail views or expanders.
* Give each chart a specific question, a date range, units, labelled axes, a direct takeaway supported by the data, and an accessible way to read exact values. Use charts for changes or comparisons; use text or tables for precise single values. Avoid decorative gauges, repeated pie charts and invented distributions.
* Design for a meeting-room laptop and a narrower browser. On small screens, prioritise the customer, status and main action; progressively reveal secondary columns or use controlled table scrolling. Support keyboard navigation, visible focus, readable contrast, correctly labelled forms and non-colour status cues.

Use copy such as:

| Concept                 | Default UI wording                     | Explain when asked                                                                                                                                                          |
| ----------------------- | -------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Calibrated probability  | **Predicted risk**                     | The model’s estimated chance of the defined drop in transaction volume in the next three months. Calibration adjusts how the model’s scores map to estimated probabilities. |
| Feature                 | **Model input** or a named measure     | A value used by the model, such as the rate of failed payments.                                                                                                             |
| SHAP attribution        | **Signals to investigate**             | Which inputs pushed this estimate higher or lower. They do not establish why the customer changed behaviour.                                                                |
| Probability threshold   | **Review threshold**                   | The score used to flag customers for the review queue. The backend’s saved flag is authoritative.                                                                           |
| Volume-attrition target | **What counts as a drop in activity?** | The next three months’ average combined transaction flow is at most half of a positive trailing twelve-month average.                                                       |
| Low risk                | **Below review threshold**             | The current score did not trigger a review flag.                                                                                                                            |
| No action               | **No immediate action**                | A recorded committee decision.                                                                                                                                              |

Keep **observed activity**, **predicted risk**, **review threshold**, and the **outcome rule** visually distinct. For a February 2024 cutoff, the observed data end in February and the forecast covers March–May 2024. A past change in transaction volume, a future risk percentage, and a later recorded outcome answer different questions. The target concerns transaction volume, not account closure. Keep the policy read-only in the review flow; any future change to the flagging policy belongs to a separate business and model decision.

## 3. Design each screen

### Overview — decide who needs a review

* Put assessment selection, information cutoff and forecast period in a compact header. If the same month has multiple saved batches, distinguish them by version or coverage. Show only totals for the selected batch.
* Lead with **Customers assessed**, **Flagged for review**, and **Flagged and awaiting review**. Use at most one small portfolio visual, such as a directly labelled review-progress bar from complete batch counts. Do not build a distribution or a portfolio total from one paginated list.
* Make the **customer review queue** the main content. Default to flagged customers ranked by predicted risk. Include company/ID search, All customers, Flagged, and Awaiting review controls, review decision filtering where supported, result count and pagination. Useful columns: customer, predicted risk, review flag, committee decision and **Open review**. Show business context in a detail panel or optional column only when the data support it.
* Place exposure totals and coverage in an expandable Finance section. Fees, waivers and balances are separate measures. Display “208 of 208 records available” or the applicable coverage when relevant. Do not infer portfolio-wide service issues from the visible page of customers.

### Customer Review — understand the case and record the decision

* Keep a compact header with company/ID, selected assessment, forecast window, model review flag and current saved decision. Give **Predicted risk** and **Observed activity** separate prominent positions. Describe observed activity as the latest three-month average compared with the trailing twelve-month average, when both are available and the reference average is positive. Place the threshold and target definition behind nearby explanation controls.
* Split the view into **Summary**, **Operations**, and **Finance**, using tabs or a similarly clear layout. Use a visible **Record decision** action that opens the decision section or drawer. Keep the customer and assessment context visible when switching perspectives.
* In Summary, show one observed transaction history chart of up to twelve available months, ending at the cutoff. Use monthly combined flow as the default; make incoming and successful outgoing flow available when supported. Label MYR and date ranges. Show missing months as gaps and actual zero as zero. Keep any reference average clearly labelled. Never draw future estimates as observations.
* Put **Signals to investigate** in shared evidence. Start with two or three concise signals, with the observed measure and whether it pushed the estimate up or down. Expand to see other signals and the technical SHAP view. If using signed bars there, label the measure as model contribution in log-odds. Do not display SHAP as probability percentage points, add top contributions as if they were the whole prediction, or present suggested causes as confirmed facts.
* Operations shows relevant trends and actual values for payment activity, payment failures, login difficulties and related measures. Use a short comparison or sparklines only when a real time series exists. Show a compact metric or “Not provided” otherwise.
* Finance shows operating account and fixed-deposit balances, estimated monthly fees, and estimated monthly waivers. Label historical estimates and exposure. Do not call these verified profitability, actual invoices or guaranteed retention savings. Avoid charts that sum or compare balances with fees as though they had the same meaning.
* In the decision form, include **Prioritise for RM**, **Monitor**, and **No immediate action**, with reason and reviewer required, plus optional owner, next follow-up date and notes from each perspective. Use an explicit **Save decision**. Make unsaved, saving, saved, validation error and conflicting edit states distinguishable. Preserve the draft on failure; show a clear way to load the latest saved decision on conflict. A successful save may link to Reviewed Customers when available. No outreach log is required to save the review.

### Reviewed Customers — resume a case after the meeting

* Show saved cases, including monitor and no-immediate-action decisions. Support search and filters for decision, owner and due status when supported. Keep the list concise: customer, decision, reviewed assessment, owner, next follow-up, and case status. Put full notes and history on the case view.
* In case detail, show **At the time of review** and **Latest available assessment** side by side. Each has its own month and risk; the original also shows the committee rationale. Link to the appropriate month’s flow and model signals. If there is no newer assessment, say so. A lower new score does not overwrite or close the earlier decision.
* Use a dated timeline for follow-up. A planned contact, attempted contact, completed visit, service fix and cancellation must be distinguishable. Design a linked task history with owner, planned date, actual date, recorded by and notes. Keep **committee decision**, **case status**, **follow-up status** and **observed outcome** separate. An actual intervention is recorded after it happens; do not infer it from a plan.
* Preserve existing dated action notes where available. Use preview states for cross-month cases, linked task updates, and manual defer or close actions until the corresponding backend functions exist.

### RM Briefing and GenAI — prepare for the discussion

* Provide a clean, print-friendly briefing preview for one or more explicitly selected prioritised customers. Include customer and assessment identifiers, dated risk estimate and forecast, observed trend, top signals, Ops/Finance context, committee rationale, owner and next step. If original and latest assessments differ, label both.
* Include two or three neutral **Questions for the customer** linked to evidence. Example: “We noticed more failed payments in recent months. Did you experience any difficulties completing payments?” Use only evidence supported by the selected case. The briefing can be prepared before outreach.
* Retain or add a compact **AI briefing draft** section. Default to “AI draft not available yet” when disconnected. A labelled example can demonstrate what an evidence-linked draft will look like. Provide space for generating, ready, unavailable and error states; only activate generation when a real service exists. Keep the structured evidence and a deterministic briefing usable without AI.
* Keep numeric facts sourced from saved records. An AI draft may help phrase evidence and questions; it must be clearly identified for human review. Do not invent motives, causes or figures. Show a PDF action as unavailable until export works, or provide a clearly named browser **Print** action if actually implemented.

### Monthly Assessments — manage evidence coverage and preview future uploads

* Show saved month, batch version, customer count and available evidence such as names and flow history. Distinguish a single-case sample from a complete portfolio. Allow an assessment to be opened in the overview.
* Design the future **Upload monthly package** flow around **Select → Validate → Score → Publish**. Provide layouts for pending, processing, validated, failed and published states, useful validation issues and a way to correct/resubmit. The previous published assessment stays visible on failure.
* Leave the package schema to the agreed data contract. No automatic dataset regeneration or retraining belongs in this screen. Until upload/scoring services exist, use an inert entry point or explicitly labelled interactive preview; do not announce a real upload, validation, model run or publication.

### Monitoring and OPR — keep scenario evidence separate

* Reserve a secondary view for future data-quality, drift and observed outcomes. Show periods and record counts, and distinguish pending outcomes from mature observations and intervention exposure. No implied causal retention benefit or performance estimate without supporting data.
* Put **OPR scenario** in a separate, clearly named hypothetical workspace. Prepare layout for rate change, deposit renewal/exit, competitor movement and pass-through assumptions, with a side-by-side baseline/scenario comparison when outputs exist. Keep it out of the main customer-review flow. Scenario controls must never change saved predictions or show fabricated accuracy changes as observed results.

## 4. Implement honest states and a clean handoff

Use three distinguishable states where relevant: **Connected to saved data**, **Demo preview**, and **Unavailable pending integration**. A small contextual label is sufficient for fixtures; avoid repeating a prototype banner on every screen. Keep fixtures out of live totals and saved records. Show useful loading, empty, missing-data, error, unsaved and retry states. Display genuine zero values. Use consistent Malaysia-local dates and MYR formatting.

Inspect the supplied API contract. The existing foundation supports assessment selection, batch summaries, customer search/detail/history, saving a versioned review, and dated action notes. Use relative API calls through the existing development proxy. Build additional views with isolated fixture data or clearly unavailable actions until supported. Do not add Flask routes, change schemas, call an LLM, transmit files, or silently simulate successful writes. Preserve batch and prediction IDs across navigation and saves. The backend owns probability, flags and historical evidence; the frontend formats values and visualises the data it receives.

Deliver a cohesive set of navigable React screens or corresponding high-fidelity mockups. Use reusable table, filter, chart, explanation, status and form components, with consistent responsive CSS. Include a short handoff identifying which interactions are connected, which use fixtures, and the backend capability each unavailable action needs.

Validate the design with these walkthroughs:

1. Select the enriched February assessment. If the supplied dataset is connected, check **1,000 assessed, 208 flagged, 792 below threshold** and Customer **944 at about 84.4% predicted risk**. These are reference checks, never hardcoded totals. In a sample view, clearly show sample scope.
2. Open a customer and distinguish past activity, future risk, the review threshold and the outcome rule without reading a long methodology section.
3. Review both perspectives, save a decision, and confirm it appears after reload when connected. Simulate a save failure or conflicting edit without losing the draft.
4. Show an earlier prioritisation beside a lower later score in a labelled fixture. Confirm the original decision stays intact and the later follow-up has its own status.
5. Open an RM briefing preview with AI unavailable. Confirm there is enough structured evidence to prepare for the discussion.
6. Show a failed upload preview and an OPR assumption change. Confirm neither changes the published assessment or appears as an observed result.

