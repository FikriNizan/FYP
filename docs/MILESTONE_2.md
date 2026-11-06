# Milestone 2 — Reviewed Customers and follow-up

## Entry checkpoint

The roadmap calls this Milestone 2. It assumes a working React/Flask foundation. The old v0.2.0 ZIP used plain JavaScript; the corrected v0.3.0 package supplies React + Vite. If you are still using v0.2.0, follow [the React update guide](UPGRADE_TO_REACT.md) first, preserving your existing database.

Your database copy is already complete. The supplied log reported 3 batches, 2,001 stored prediction records, and zero saved reviews/actions at the time of copying. This does not establish whether you have since completed the browser or GitHub checks, so verify those using the guide rather than repeating the import.

## Business behaviour we are implementing next

A committee saves a decision in Customer Review. The customer becomes available on a dedicated Reviewed Customers page. An RM or operations user returns to that page later to record an attempted contact, completed visit or service action. A new monthly assessment changes the latest evidence shown alongside the original decision; it does not rewrite the earlier decision.

A briefing can be generated before outreach. Recording outreach immediately after committee review is optional and only appropriate if it has actually happened. PDF/briefing generation belongs to the following milestone.

## Build in this order

| Step                | Development work                                                                                                       | Acceptance evidence                                                                               |
| ------------------- | ---------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------- |
| 1. Reviewed list    | API and React page listing saved decisions, reason, reviewer, owner and original assessment                            | A saved review appears after reload; no-action and monitor decisions remain distinguishable       |
| 2. Preserve context | Stable reviewed-case identity linked to the original prediction; latest assessment retrieved separately by customer ID | Original and latest month/risk are both visible; a new import does not erase the case             |
| 3. Follow-up        | Linked task/action identity with dated events and manual open/defer/close behaviour                                    | A planned contact can later be completed on the same task; history remains available              |
| 4. Verify           | Database migration and API/React workflow checks                                                                       | Existing reviews survive the upgrade and a lower next-month risk leaves the prior decision intact |

Before Step 1 changes the schema, add a versioned migration and test it against a copy of an existing database. Keep `decision`, `case status`, `follow-up status` and `observed outcome` separate.

## Required information

For a reviewed case: customer identifier, original prediction/batch, original decision month/risk, committee decision, reason, reviewer, owner, next-action date, current case status and timestamps. Latest month/risk is retrieved from its separate saved assessment rather than replacing the original score.

For a follow-up: stable follow-up ID, case link, action type, planned date if applicable, actual event date, attempted/completed/cancelled state, recorded-by attribution and notes. Preserve later status events instead of overwriting the history. A planned contact is not a delivered intervention.

The existing action-note API is useful prior work, but separate append-only notes do not yet link a planned task to its completion. Extend it deliberately rather than presenting that lifecycle as already implemented.

## First exercise after the React checkpoint

Save one labelled development review for Customer 944 and reload it. Record the prediction/batch ID used for that decision. This gives the upcoming Reviewed Customers page a concrete saved case to retrieve.

If Git is already initialised, start a small branch before feature changes:

```PowerShell
git switch -c feature/reviewed-customers
```

If Git is not yet initialised, complete `docs/DEVELOPMENT.md` first. Keep the React conversion checkpoint separate from the Reviewed Customers feature changes when committing.

When only February is imported, the latest available month may still be February. Do not invent another score or claim a risk change. For the cross-month acceptance test, later import a second genuine saved monthly export, or use clearly constructed automated test fixtures.

## Implementation checkpoint — 6 November 2026

The four implementation steps above are now available. The runtime has a Reviewed Customers worklist, case details, original/latest evidence, linked follow-up events and explicit open/deferred/closed case states. The current neutral frontend follows `dashboard-frontend-design-prompt.md`; see [UI_DESIGN.md](UI_DESIGN.md) for the design and integration handoff.

Database startup applies explicit schema versions 1 (existing foundation) and 2 (`backend/churn_backend/migrations/002_reviewed_cases.sql`). An existing database receives a timestamped SQLite backup beside it before migration. Schema changes and version records commit together; failed migrations roll back. Starting the app again does not repeat the migration or backfill. A database from a newer application schema is refused.

One case is anchored to one reviewed prediction, using that prediction's stable ID. A monthly import never deletes, moves or automatically closes it. Reviewing a different monthly prediction creates a separate case; cases are not silently merged by customer ID. Existing reviews are backfilled once, preserving the earliest available committee review as the original decision, while current owner/date are initialised from the current review. Later committee revisions remain in review history; case owner/date/status are managed independently on the case page.

Latest evidence means the newest imported cutoff for that customer, with full exports preferred over samples, then name/flow enrichment, import time and batch ID breaking same-month ties. This is independent of the overview assessment selector. Original evidence links always retain the exact original batch. If no newer month exists, the UI explicitly shows the same assessment; it does not invent a risk change.

Follow-ups support planned → attempted → completed/cancelled, including repeated attempts, direct completion of a plan, and retrospective attempted/completed events without a prior plan. The API stores completion as `delivered`, matching the existing action vocabulary. Each event preserves action type, date, notes, attribution and recording timestamp; the initial planned date remains separate from actual event dates. Completed/cancelled tasks are terminal. New actual events cannot be future-dated. Closing a case preserves any unfinished tasks; reopen it before adding events. Planned work is not intervention delivery, and delivery does not establish effectiveness.

All case/task writes carry the case's `expected_version`. Successful writes increment that version, so concurrent case and task edits cannot silently overwrite each other. Conflicted drafts remain available until explicit discard/reload. In-tab case drafts also survive navigation. Legacy action notes remain visible in audit history without inferring links between unrelated notes.

## Acceptance walkthrough with your portfolio

1. Restart Flask, then use Vite or rebuild the frontend. Startup creates a pre-migration backup automatically; do not reimport or replace your working database.
2. Open Reviewed Customers. Your three existing saved reviews should appear as three cases, across assessments. Verify monitor/no-immediate-action decisions using the original-decision filter where available.
3. Open a case and check original decision/risk/month, reviewer and rationale beside the latest available assessment. Open both evidence links and verify their selected batches.
4. Create a clearly labelled development follow-up plan. Select that same task and record an actual attempt/completion with its actual date. Check that the plan date and every event remain visible.
5. Alternatively record an actual follow-up with no prior plan. It must not acquire an invented planned date.
6. Defer, close and reopen a case with explicit reasons. Reload/restart and check its status/history. The original prediction and decision must remain available.
7. Open the same case in two tabs. Save in one, then try saving the older version in the other. Verify an explicit conflict and preserved draft until you discard and load the latest case.
8. Check keyboard operation and narrow layouts with realistic company names, notes and multiple tasks. Review tables scroll within their panels on narrow screens.

Automated fixtures demonstrate January prioritisation followed by lower February risk, leaving the case open. A real-data cross-month demonstration still requires a genuinely newer saved assessment; your current portfolio only contains February assessments.

Verification: 59 tests and the Vite production build pass. Chrome fixture screenshots cover Overview, Reviewed Customers and Case Details at desktop/narrow widths; real React forms also completed plan → delivery → manual case closure through Flask while retaining the original explanation. A read-only backup of the working database was migrated in a temporary directory: 3 batches, 2,001 predictions, 3 reviews, 5 review-history entries and 0 legacy actions were preserved exactly; 3 cases were backfilled and SQLite integrity/foreign-key checks passed. This rehearsal did not migrate the working database or complete the user's acceptance walkthrough.

## Scope boundary

Milestone 2 implementation and automated verification are complete; user acceptance remains open until the walkthrough above is demonstrated. GenAI, PDF, new-month inference, OPR and outcome monitoring remain later milestones. Reviewer and event attribution are user-entered, not authenticated identity.
