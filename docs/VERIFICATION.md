# Verification record — React correction, 3 November 2026

Environment: Python 3.12, Flask 3.1.3, Node.js 24.22.1 and npm 11.9.0 in the build environment. Frontend dependency versions are exact in `package.json`/`package-lock.json`; Python dependencies remain pinned.

| Check | Result | Scope |
|---|---|---|
| Existing backend suite | 20 passed | Export verification, leakage/protocol rejection, month isolation, persistence, review conflicts and action notes |
| React-serving/backend integration tests | 4 passed | Built assets, explicit unbuilt response, retained API, and same-origin write under the development Host header |
| Database copying | 4 passed | Records/history preserved, original untouched, overwrite and invalid source refused |
| Guarded source update | 4 passed | Database/Git preserved, source backup, idempotence, local-edit conflicts and preview/tampering/protected-path handling |
| JavaScript utility/API tests | 6 passed | Missing versus zero, probability scale, dates, escaping, scoped URLs and request errors |
| React interaction/rendering tests | 8 passed | API-driven portfolio/search, shared signals, actual-vs-missing money, saving/version payload, draft navigation, explicit conflict resolution, unknown batch, zero-flow chart and preferred batch selection |
| Frontend build | Passed | Vite successfully builds the React application and dependencies |

Total: **46 automated tests** plus the frontend build. React tests use jsdom with mocked API responses; test fixtures are software checks rather than research findings. No real browser visual/accessibility test or Windows execution of this new React version was completed here.

Additional package checks verify that a full v0.2.0 source copy can receive the update while preserving existing database bytes; local edits stop the update. Built HTML/assets are checked through Flask's test client. The development proxy is checked with a real HTTP request to confirm a review save can pass the retained Origin protection.

The complete 1,000-customer database remains on the user's machine. The user's supplied import/API logs establish the reported counts and available context. Tests here use temporary databases and the existing saved demo; they do not independently re-evaluate the complete bank portfolio or run new CatBoost inference.

The frozen model policy, database schema, importer, validation and repository logic are retained. This release changes the frontend implementation and serving/build/development setup. It does not add Reviewed Customers/case migrations, GenAI, OPR, online inference or authenticated identities.

## Local checkpoint after applying the update

- [ ] Both development servers start and the React page opens at port 5173.
- [ ] Existing three batches remain selectable; enriched February shows 1,000 / 208 / 792.
- [ ] Customer 944 shows the verified values and twelve observed monthly flows through February 2024.
- [ ] Search, filters and pagination use the selected batch.
- [ ] Unsaved drafts survive navigation within the tab but do not change saved counts.
- [ ] Save, browser reload and Flask restart preserve the decision and original evidence.
- [ ] Two tabs trigger an explicit conflict for a stale save.
- [ ] Keyboard, desktop/narrow layouts, chart readability and error states are usable.
- [ ] Remote GitHub CI completes after the code is pushed.

Use [UPGRADE_TO_REACT.md](UPGRADE_TO_REACT.md), then [MILESTONE_2.md](MILESTONE_2.md). These unchecked items remain user acceptance work, not completed claims.
