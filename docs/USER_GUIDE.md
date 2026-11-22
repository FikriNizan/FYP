# User guide: workspace and monitoring notes

The in-app **Guide** page is a short visual summary: the monthly workflow, four words to know, three reminders, why a lower score never erases a decision, and how to read Monitoring. This file keeps the longer explanations behind it. It is the user manual for the workspace.

The wording in sections 1–4 is the text the in-app Guide and the Monitoring help carried before the final tweaks of 23 November 2026, kept word for word so nothing is lost.

## 1. From evidence to follow-up (the monthly workflow in detail)

The workspace is one shared space for Operations, Finance and relationship managers.

1. **Choose the evidence.** Choose an assessment in Overview. Check its cutoff, forecast and batch; a single-case sample is not the full portfolio.
2. **Understand the customer.** Open a review. Summary holds recorded flows and shared model signals. Operations and Finance show perspectives on the same evidence.
3. **Record the committee judgement.** Prioritise for RM, Monitor or No immediate action. Give a reason and reviewer. Save explicitly; drafts and failed saves do not count as saved decisions.
4. **Resume the case later.** Reviewed Customers keeps original decisions alongside the latest available assessment. Prepare a briefing for a prioritised case, then plan or record follow-up after contact.

## 2. Four different questions

| Question | Meaning |
|---|---|
| Observed activity | What was recorded through the cutoff? |
| Predicted risk | What is the estimated chance of the defined drop over the next three months? |
| Review threshold | Which saved predictions were flagged for review? |
| Outcome rule | Did the future three-month average combined flow fall to at most half of a positive trailing twelve-month average? This concerns transaction volume, not account closure. |

Model signals explain a prediction; they do not prove a cause. Balances show exposure; fees and waivers are historical estimates. Planned work is not a delivered intervention, and a lower later risk does not prove retention effectiveness.

## 3. How a case survives a lower later score (worked example)

Constructed values for explanation only. This example is isolated from saved records.

| | At the time of review · January example | Latest assessment · February example |
|---|---|---|
| Predicted risk | 70.0% | 18.0% |
| Record | Committee: Prioritise for RM. Reason: investigate recorded payment friction. | Case: Open · Follow-up: Attempted |

The January decision stays intact. An RM records the contact attempt separately; the lower risk does not close the case.

## 4. Reading Monitoring

- **Observed outcome.** An observed outcome is a volume drop: the next three-month average combined flow is at or below half of a positive trailing twelve-month average. It does not mean account closure. Unavailable includes outcomes not imported or incomplete source coverage. It is never counted as a zero or a negative outcome.
- **How outcomes arrive.** Outcomes are derived automatically when the monthly package that completes an assessment's three-month window is uploaded, from the uploaded packages' own data. A month that is not yet uploaded leaves the assessment waiting; nothing is guessed. An administrator can also load outcomes from the trusted research file with the command below.
- **Expected vs actual.** Predicted and observed figures use the same customers when compared. Expected drops are the sum of predicted risk. The Brier score (a probability-error score) remains in the API and documentation; it is not shown on screen.
- **Follow-up.** Documented delivery means a completed RM visit, customer contact or service fix dated inside the outcome window. Planned work, attempts and notes are excluded. No recorded delivery does not prove that nothing happened. These groups are selected, not controlled; differences do not prove retention benefit. On screen, "Not halved" is the outcome where activity did not fall to half; a followed-up customer in that group counts as a false alarm, although the RM may have kept them.
- **Input movement.** Input and risk movement compares the selected assessment with an earlier batch under the same frozen protocol. It is descriptive only; no alert threshold or causal explanation is assigned.
- **The three scores.**
  - Precision ("flags that were real drops"): of the flagged customers, how many had an observed volume drop?
  - Recall ("drops the model caught"): of all observed volume drops, how many were flagged?
  - F1: a balanced summary of precision and recall, shown as a 0–1 score.
- **Rate-shock what-if.** It reads a scenario package generated offline; it never changes saved predictions. Monitoring is descriptive.

### Administrator fallback

Outside the browser:

```
python -m flask --app app load-outcomes --batch-id BATCH --observed-through YYYY-MM-DD
```

Then add `--apply` to save. It needs `TXB_RESEARCH_ROOT` (the research folder setting).

## Related documents

- [Finance metrics](FINANCE_METRICS.md): contribution at stake (Revenue at Risk) and fee subsidy leakage formulas and sources.
- [Milestone 5](MILESTONE_5.md): outcome import and monitoring design.
- [Local database workflow](LOCAL_DATABASE_WORKFLOW.md): named database sessions.
