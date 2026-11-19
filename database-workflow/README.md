# Establish the database state, then simplify development

Your usual Flask + React/Vite setup is valid. The uncertainty comes from process-specific configuration and many similarly named database copies.

## What the current app actually does

* Flask uses CHURN\_DB\_PATH from the environment of the process that starts it. If absent, it uses backend/instance/churn.sqlite.
* React at <http://127.0.0.1:5173> forwards /api to VITE\_API\_TARGET, or to Flask at <http://127.0.0.1:5000> by default.
* Starting a test Flask at 5085 does not redirect an already running Vite server to 5085.
* Two separate PowerShell windows do not automatically share variables you set in one of them. Changing a variable after starting a process does not reconfigure that process.
* Activating .venv chooses Python dependencies, not the database.
* Flask startup can apply existing schema migrations. Inspecting the databases should therefore avoid starting/importing the app just to find their contents.
* SQLite files and test artifacts are excluded from Git in this repository. A code commit is not a database backup.

| Item             | Purpose                                                                           |
| ---------------- | --------------------------------------------------------------------------------- |
| Working database | Your chosen continuing project records and intended demonstration data            |
| Test database    | A reusable sandbox copy where demonstration actions and failure tests are allowed |
| Backup           | A preserved recovery snapshot; not an everyday development target                 |

A backup can be made from either a working or test database. Its filename alone does not establish which source it came from.

## Do this first: read-only inventory

1. Stop Flask and Vite with Ctrl+C in their own terminals. Ask an agent to identify any servers it launched separately. Preserve every database and backup. There is no evidence yet that you need to reset anything.
2. Extract this ZIP so its files are here:
   D:\Degree Life\FYP Full-Stack Development\database-workflow\
   It is a sibling of corporate-attrition-app, not a replacement for it.
3. From PowerShell run:

```PowerShell
Set-Location 'D:\Degree Life\FYP Full-Stack Development\corporate-attrition-app'
.\.venv\Scripts\python.exe '..\database-workflow\inspect_databases.py' --project-root .
```

The script uses only Python's standard library. It reads candidate databases in backend/instance, artifacts, the project root, and the current shell's CHURN\_DB\_PATH. Pre-migration backups are included; journal/WAL sidecars are not treated as independent databases. To include another known database elsewhere, add --database followed by its quoted path.

The script:

* Opens SQLite connections read-only, without importing Flask or applying migrations.
* Reports each full path, schema version, integrity checks, table counts and assessment/outcome coverage.
* Fingerprints accepted scoring evidence and the human/workflow tables, making differences between copies visible.
* Does not create a missing database, choose a winner, merge, restore, seed, reset, or delete anything.
* Writes only a new JSON audit report in artifacts and prints its exact path. It contains paths, IDs, counts and hashes, not customer names, notes or exported data rows.

Send the printed summary or the generated JSON report for review. Modified dates and larger counts alone are not reasons to replace your working database. Your last shared working-database copy log had three batches, 3,000 predictions and six reviews; that is a reference point, not proof of its current contents.

If another server remains active, this optional read-only command lists relevant listening ports:

```PowerShell
Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue |
    Where-Object { $_.LocalPort -in @(5000, 5173, 5085, 5075, 5074) } |
    Select-Object LocalAddress, LocalPort, OwningProcess
```

A listening PID does not by itself identify a database. The audit's environment fields describe the current shell's next launch, not the environment of a server an agent already started. Do not stop all Python or Node processes indiscriminately.

## After the inventory: one working mode and one test mode

Give codex-database-workflow-prompt.md to the local agent, together with the audit report. It asks for explicit startup modes, coordinated frontend/backend routing and a small development-only database identity indicator. That prevents relying on a bare browser link or a remembered port.

Until those helpers exist, use an explicit absolute CHURN\_DB\_PATH in the same terminal that starts Flask, and explicitly set VITE\_API\_TARGET in the terminal that starts Vite. Check the selected database first. Do not switch to a different candidate merely because it has a later timestamp.

You do not need a fresh database for every UI edit:

* Spacing, wording and visual changes: reuse your test sandbox.
* Browser tests that create reviews or actions: use the sandbox and label the demonstration records.
* A clean import, migration or reset scenario: create a new copy using scripts/copy\_database.py and record its source/purpose.
* scripts/check.py: its isolated tests manage their own temporary databases; it does not need your manual copy procedure.
* Ongoing genuine project records: use the confirmed working database intentionally.

Keep only one local mode running at a time initially. After implementation, an agent handing you a link should identify the mode, database, frontend URL, backend URL and scenario. Never promote test edits into the working database automatically.

The audit tool passed six isolated checks, including missing-file refusal, no migration, unchanged source bytes and visibility of committed WAL records. Your actual Windows database state must still be inspected with the command above.
