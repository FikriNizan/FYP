# Codex task: Make local working/test database selection explicit and repeatable

I am losing track of which SQLite database my dashboard uses. Diagnose the state without changing records, then implement a small local development workflow so I can test without repeating ad hoc environment/copy/port instructions.

Work in my current FYP / TxB Retention Studio worktree:
D:\Degree Life\FYP Full-Stack Development\corporate-attrition-app

Preserve all existing edits and Milestone 5 fixes. Read repository instructions, current configuration, migrations, copy\_database.py, check.py and frontend/vite.config.js. Do not commit, push, reset, delete data, create a new branch or overwrite any database.

## First establish facts

Read the database-audit JSON report I supplied, or run the supplied inspect\_databases.py from the project root. It opens SQLite read-only and does not import the application. Validate its findings against the actual files. Do not start/import Flask merely to inspect candidates: startup may migrate or create a database.

Inventory only app-related candidates and report:

* Full paths, schema versions, integrity checks, batches/months, predictions, reviews, reviewed cases, follow-up events and observed outcomes.
* Which copies have identical immutable scoring data but different human/outcome records.
* The default backend/instance/churn.sqlite and shell CHURN\_DB\_PATH/VITE\_API\_TARGET values.
* App-related server PIDs/listening ports you can identify, and their launch commands. A different shell's environment is not proof of an existing server's database.
* What can and cannot be established from process/configuration evidence. Identical row counts do not prove two paths are the same file.

Do not silently select the newest/largest copy, restore a backup, merge changes or promote demonstration actions. If there is a real ambiguity about which human records I want to keep, report the candidates and ask me that specific data-choice question before any restoration. You can build the launch helpers while that choice is pending; do not run an ambiguous working session.

## Implement two explicit local modes

Keep one user-facing launcher for a normal session and one for a test session, using the existing Python environment and Windows/PowerShell. A standard-library Python launcher with simple commands is acceptable. Choose a small implementation, document the exact commands and avoid requiring me to set environment variables manually every run.

* Working mode targets the confirmed working path, normally backend/instance/churn.sqlite.
* Test mode targets an explicitly identified reusable sandbox under artifacts. Existing test state is resumed by default.
* A separate deliberate command creates a NEW sandbox from a chosen source using the existing SQLite online-backup helper. Record source, destination, timestamp and purpose. Refuse overwrite. Preserve older copies; do not introduce automatic cleanup.
* Selecting a mode must be explicit. Do not silently initialise an empty database because of a misspelled path. Validate file existence and its application identity before launching. Use absolute resolved paths.
* Never load demonstration actions, outcomes or resets automatically in working mode. Test setup is explicit and repeatable.
* Use existing migration/backup behavior for the selected database; print the schema state and any upgrade/backup that actually occurs. Test schema-changing code on a copy before exercising it against working records.
* For now, run only one local mode at a time. Use the familiar backend 5000 / frontend 5173 pair for both modes; do not silently select a random alternative port when one is occupied.
* Start the child backend with an explicit CHURN\_DB\_PATH and the frontend with an explicit matching VITE\_API\_TARGET. Do not inherit stale routing or database selection. Keep existing scoring settings configurable; do not hardcode secret values or set persistent Windows user/system environment variables.
* Do not run an unrelated server behind the link. Check readiness and runtime identity before reporting success. Never terminate arbitrary Python/Node processes; only stop processes the helper owns, with normal cleanup on Ctrl+C.

The existing frontend normally proxies to 5000. Starting an independent server at 5085 does not redirect 5173; the helper must prevent this mismatch.

## Make the selected environment visible

At startup print a concise session card: Working/Test, full resolved database path, schema version, assessment months/counts, backend URL, frontend URL and owned process IDs.

Add a small development-only indicator to the dashboard saying which mode and database filename are in use. It must come from the running backend's actual configured DATABASE, not browser localStorage, a static label or a guessed port. A development-only read-only runtime-context endpoint is acceptable; it must not import data, mutate records or expose the full local path in a normal end-user UI. Validate the declared mode against the actual resolved path. An unknown/mismatched context must be displayed honestly.

Keep this indicator out of RM PDFs/print and the polished normal end-user layout. Preserve the Architect design except this unobtrusive local development aid. Do not implement role authentication or a deployment system in this task.

A bare link is not a sufficient agent handoff. Every agent launch report should state the mode, database, routing and scenario it actually started.

## Make the pending Monitoring delivery test repeatable

Provide exact steps or a small explicitly invoked sandbox-only scenario helper for the existing Monitoring test:

* Use an April customer with an open linked case and loaded May–July outcomes.
* A planned action does not count as delivered.
* One eligible delivered RM visit/customer contact dated 2024-05-15 counts for April.
* If the baseline has zero eligible deliveries, expect one documented customer and 999 without recorded delivery; metric percentages may look unchanged after rounding.
* Repeating scenario setup must not create duplicate deliveries/cases. Use the normal service/API validation and identify created test records.
* Refuse scenario writes when the resolved database is the working file, its alias, or a path of uncertain role. Do not change the original source outcomes or predictions.
* Report the actual baseline and resulting counts rather than assuming every reused sandbox starts at zero.

No automatic replay of raw data generation, training, April scoring or manual source-manifest changes is needed. This task fixes development environment control.

## Verify and document

Add meaningful tests for path resolution, missing-file refusal, no-overwrite copying, test-mode safeguards, child environment/proxy agreement, session identity and owned-process cleanup. Reuse existing tests rather than adding mirror-only tests. Use temporary databases/process stubs where appropriate; do not launch a test against my working data.

Test the launch flow on a disposable sandbox, and browser-check the development-only indicator against the runtime report. Verify monitoring and existing app flows are unaffected. Run scripts/check.py and the normal frontend build as appropriate; report what actually ran.

Document:

* The read-only inventory and the confirmed database roles, with any unresolved data-choice question.
* The small set of commands for Working, Test, New test copy and Stop.
* That UI/content editing normally reuses a sandbox; only specific clean-state tests need new copies.
* That Git commits preserve code, while SQLite state needs separate backups.
* How to resume a test tomorrow and how to identify it before writing.
* Any manual acceptance still pending.

Do not assume my existing data are damaged. Preserve all candidates until their role is established. Leave source changes uncommitted and do not perform a working-database restore or promotion without my explicit data choice.
