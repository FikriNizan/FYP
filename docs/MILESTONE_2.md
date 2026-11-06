# Milestone 2 — Reviewed Customers and follow-up

## Entry checkpoint

The roadmap calls this Milestone 2. It assumes a working React/Flask foundation. The old v0.2.0 ZIP used plain JavaScript; the corrected v0.3.0 package supplies React + Vite. If you are still using v0.2.0, follow [the React update guide](UPGRADE_TO_REACT.md) first, preserving your existing database.

Your database copy is already complete. The supplied log reported 3 batches, 2,001 stored prediction records, and zero saved reviews/actions at the time of copying. This does not establish whether you have since completed the browser or GitHub checks, so verify those using the guide rather than repeating the import.

## Business behaviour we are implementing next

A committee saves a decision in Customer Review. The customer becomes available on a dedicated Reviewed Customers page. An RM or operations user returns to that page later to record an attempted contact, completed visit or service action. A new monthly assessment changes the latest evidence shown alongside the original decision; it does not rewrite the earlier decision.

A briefing can be generated before outreach. Recording outreach immediately after committee review is optional and only appropriate if it has actually happened. PDF/briefing generation belongs to the following milestone.

## Build in this order

| Step | Development work | Acceptance evidence |
|---|---|---|
| 1. Reviewed list | API and React page listing saved decisions, reason, reviewer, owner and original assessment | A saved review appears after reload; no-action and monitor decisions remain distinguishable |
| 2. Preserve context | Stable reviewed-case identity linked to the original prediction; latest assessment retrieved separately by customer ID | Original and latest month/risk are both visible; a new import does not erase the case |
| 3. Follow-up | Linked task/action identity with dated events and manual open/defer/close behaviour | A planned contact can later be completed on the same task; history remains available |
| 4. Verify | Database migration and API/React workflow checks | Existing reviews survive the upgrade and a lower next-month risk leaves the prior decision intact |

Before Step 1 changes the schema, add a versioned migration and test it against a copy of an existing database. Keep `decision`, `case status`, `follow-up status` and `observed outcome` separate.

## Required information

For a reviewed case: customer identifier, original prediction/batch, original decision month/risk, committee decision, reason, reviewer, owner, next-action date, current case status and timestamps. Latest month/risk is retrieved from its separate saved assessment rather than replacing the original score.

For a follow-up: stable follow-up ID, case link, action type, planned date if applicable, actual event date, attempted/completed/cancelled state, recorded-by attribution and notes. Preserve later status events instead of overwriting the history. A planned contact is not a delivered intervention.

The existing action-note API is useful prior work, but separate append-only notes do not yet link a planned task to its completion. Extend it deliberately rather than presenting that lifecycle as already implemented.

## First exercise after the React checkpoint

Save one labelled development review for Customer 944 and reload it. Record the prediction/batch ID used for that decision. This gives the upcoming Reviewed Customers page a concrete saved case to retrieve.

If Git is already initialised, start a small branch before feature changes:

```powershell
git switch -c feature/reviewed-customers
```

If Git is not yet initialised, complete `docs/DEVELOPMENT.md` first. Keep the React conversion checkpoint separate from the Reviewed Customers feature changes when committing.

When only February is imported, the latest available month may still be February. Do not invent another score or claim a risk change. For the cross-month acceptance test, later import a second genuine saved monthly export, or use clearly constructed automated test fixtures.

## Scope boundary

This v0.3.0 package corrects the frontend framework and supplies the guide/checks. The Reviewed Customers page, cross-month case tables and linked follow-up lifecycle are **not implemented by this package**. They are the next work items. GenAI, PDF, new-month inference, OPR and outcome monitoring remain later milestones.
