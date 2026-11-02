# Verification record — 2 November 2026

## Checks performed for this starter

Environment: Python 3.12, Flask 3.1.3 and Node.js 24.22.1 in the build environment. Requirements are pinned to the dependency versions used for this run.

| Check                                     | Result    | Scope                                                                                                                                                                                            |
| ----------------------------------------- | --------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Existing backend suite                    | 20 passed | Saved export validation, leakage/protocol rejection, month isolation, joined context, persistent/versioned reviews and dated actions                                                             |
| Frontend-serving tests                    | 2 passed  | Flask serves the HTML/module assets and API index; empty database handled at the API boundary                                                                                                    |
| Database-copy tests                       | 4 passed  | Data/history preserved, original untouched, overwrite refused, missing/same/unrelated source rejected                                                                                            |
| JavaScript tests                          | 6 passed  | Missing versus zero, percentage scale, forecast/observed definitions, escaping, scoped URLs, API errors and no automatic conflict retry                                                          |
| JavaScript syntax                         | Passed    | All three frontend JavaScript modules                                                                                                                                                            |
| Customer 944 rendering/request simulation | Passed    | Supplied 78-feature response produces 84.4% risk, 99.1% lower observed activity, actual balances, shared SHAP and twelve flow months; save carries expected version and complete editable fields |

The rendering simulation used a minimal DOM adapter and supplied API JSON. It is a code-level check of rendering and request wiring, **not** a real browser layout/accessibility test. No desktop/mobile visual acceptance or Windows test of this new application has been completed here.

No database from the user's machine was available in this build environment. The safe-copy function was exercised on a constructed database containing the same table relationships. The user's 1,000-customer import and original backend tests were evidenced by the supplied logs/API output, not independently rerun against that full database here.

The source starter retains the existing schema and model protocol. The original backend source folder was preserved; the new app is a separate copy. Backend changes are frontend static serving, a separate `/api` index, application version 0.2.0 and new serving tests. Existing model/evidence validation, import, review and action logic were retained.

## Required local acceptance

Use README section 4 after copying your database:

* [ ] February selected batch shows 1,000 customers, 208 flagged and 792 below threshold.
* [ ] Customer 944 is PERKASA MULIA TRADING SDN BHD, risk approximately 84.4%, operating account balances MYR 2,016,997.13 and FD balance MYR 0.
* [ ] Twelve observed flow months end at February 2024; no future chart values are shown as observations.
* [ ] Search, filters, pagination and assessment changes behave correctly.
* [ ] Opening another customer and returning retains an unsaved draft within the tab; it does not change the saved status/count.
* [ ] Saving then reloading/restarting preserves the decision and evidence.
* [ ] Two tabs editing the same review produce a visible conflict for the stale version rather than a silent overwrite.
* [ ] Empty/missing data states remain understandable.
* [ ] Keyboard navigation, readable focus, desktop and narrow-width layouts are usable.
* [ ] Remote GitHub CI completes after the first push.

These are the next developer acceptance tasks, not already-completed milestones. Real-bank usefulness, causal intervention effectiveness, new-month scoring, throughput targets and deployment readiness require their own evaluation.
