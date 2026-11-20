# Local Working and Test databases

## Current Milestone 6 branch

Use the isolated **Milestone 6 Test** file `artifacts/m6-review.sqlite` (schema 5), copied once from the confirmed Milestone 5 Test. The original Working and Milestone 5 Test stay at schema 4. Milestone 6 refuses launching/migrating those originals. No new outcomes/scenarios are loaded during preparation.

```PowerShell
# Prepare once; repeating inspects/resumes the same file and never overwrites it:
.\.venv\Scripts\python.exe scripts\prepare_m6.py
# Every ordinary session, resume the same file on explicitly selected free ports:
.\.venv\Scripts\python.exe scripts\local_session.py m6-test --backend-port 5066 --frontend-port 5186
```

Verified frontend: `http://127.0.0.1:5186/`; backend: `http://127.0.0.1:5066`. The helper checks both runtime identities/schema before reporting URLs; the badge identifies Milestone 6 Test. Port 5000 was occupied during implementation and was left untouched. The selected ports still refuse unknown occupants. Business-record counts/hashes before and after migration are in `artifacts/m6-data-verification.json`; all existing business rows survived. The only migration changes are additive cache/reservation storage and schema version 5. See [MILESTONE\_6.md](MILESTONE_6.md) for AI setup, validation and acceptance limits.

The older daily commands below apply when using **milestone-5 code**. They are not Milestone 6 launch commands. Changing Git branch does not isolate a database.

The [read-only database audit](../artifacts/database-audit-20261115T200253Z-213999.json) inventories 23 application SQLite candidates with full paths, integrity results, schema versions, months and table counts. It did not start Flask or choose a copy. Other copies remain preserved; their dates and row counts alone do not make them the Working database.

## Confirmed roles — 16 November 2026

| Role          | Full path                                                                                                      | Schema | Assessments                    | Predictions | Reviews / cases / follow-up events | Observed outcomes |
| ------------- | -------------------------------------------------------------------------------------------------------------- | -----: | ------------------------------ | ----------: | ---------------------------------- | ----------------: |
| Working       | `D:\Degree Life\FYP Full-Stack Development\corporate-attrition-app\backend\instance\churn.sqlite`              |      4 | Feb, Mar, Apr 2024; 1,000 each |       3,000 | 6 / 6 / 3                          |                 0 |
| Reusable Test | `D:\Degree Life\FYP Full-Stack Development\corporate-attrition-app\artifacts\m5-review-20261116-030542.sqlite` |      4 | Feb, Mar, Apr 2024; 1,000 each |       3,000 | 6 / 6 / 3                          |       1,000 April |

Both selected files pass SQLite quick and foreign-key checks. The audit gives them the same immutable scoring fingerprint `f81353414d47df7d667142e0dd9a21f1964b91d5a772bb9c8c0b6e4ed41b33cb`. Their outcome records differ; identical prediction counts do not mean they are the same file. The audit groups other historical copies by scoring fingerprint but their human and outcome records vary. No copy was promoted, merged or deleted.

The current shell has no `CHURN_DB_PATH` or `VITE_API_TARGET` override. Without the helper, Flask defaults to Working and Vite defaults to port 5000. A shell's environment does **not** identify an already-running server. On inspection, port 5000 had Python PID 27192; its launch command and database could not be established from the permitted process inspection, so no link to it is treated as a confirmed Working or Test session.

## Daily commands

Run from the repository root in PowerShell:

```PowerShell
.\.venv\Scripts\python.exe scripts\local_session.py test
```

This resumes the named Test database. For ordinary UI and follow-up work tomorrow, run the same command; it does not create another copy. To use Working deliberately:

```PowerShell
.\.venv\Scripts\python.exe scripts\local_session.py working
```

The helper refuses missing or non-application databases, a Test alias to Working, and occupied ports. It starts Flask on `127.0.0.1:5000` and Vite on `127.0.0.1:5173` with explicit matching environment, verifies both runtime identities, and prints the resolved path, schema, months, URLs and owned PIDs. It reports any migration backup actually created. **Ctrl+C in that terminal stops only its child servers.** Stop an unrelated process yourself before launching; the helper will not kill it or choose another port.

The small badge visible only in the Vite development UI comes from `GET /api/runtime-context` on the running backend. It shows Working/Test and the filename, or Unknown if the mode and resolved path do not agree. It is absent from built production UI and print/PDF output. The endpoint is enabled only for sessions started with the local-session environment and does not expose the full local path.

## A deliberate new copy

Only clean-state or schema-change tests need a new sandbox. Choose the source and a fresh destination; this command refuses overwrite and records source, destination, time and purpose next to the copy:

```PowerShell
.\.venv\Scripts\python.exe scripts\local_session.py new-test --source backend\instance\churn.sqlite --destination artifacts\my-new-test.sqlite --purpose "isolated migration check"
```

The normal Test launcher remains pinned to the confirmed reusable Test file. A new copy is **not** silently selected for the next session. Git commits preserve code, while SQLite state needs its own backups; committing does not save, merge or restore a database.

## Optional Monitoring delivery scenario on Test only

The Test sandbox already has April outcomes. This separately invoked command selects a customer with an open linked case and accepted April outcome, records a planned RM visit, confirms planning did not change delivery coverage, then records an eligible delivered visit dated **2024-05-15** through the normal case API:

```PowerShell
.\.venv\Scripts\python.exe scripts\monitoring_scenario.py --apply
```

It prints the selected case/customer/task ID and actual before/after coverage. A repeat reuses the marked task and does not duplicate a delivered event. It refuses Working and uncertain database paths. It does not import outcomes, rescore, reset or change the accepted prediction. If Test had zero eligible delivered customers before this command and the selected customer had none, expected coverage is one documented customer and 999 without recorded delivery; displayed rates may round to the same value.

Owner acceptance of the Monitoring workflow remains pending.
