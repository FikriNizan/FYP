# Milestone 2: clean February → March test

Use this guide in the current React/Flask project. Keep your latest Milestone 2 implementation. The commands reset only the application's SQLite database by archiving it, then replay existing saved monthly predictions. They do not regenerate research data, retrain CatBoost or rerun SHAP.

This guide uses the verified `import-shap` CLI. If you have added a web-upload feature, test that upload separately with the input format your current backend accepts. The CLI replay does not itself verify a new upload endpoint or manufacture a new package format.

The intended sequence is:

1. Check the existing export contains February and March.
2. Stop the application, take a verified database backup, and archive the old database.
3. Import only enriched February 2024.
4. Save and test February reviews, cases and follow-ups; restart and verify persistence.
5. Import March into the same database and test the cross-month behaviour.

**Reset once at the beginning. Keep February's database records when adding March.**

## 1. Stop the backend and set your paths

Stop Flask with Ctrl+C. Close any SQLite database viewer. You can leave Vite running, but reload the browser after the reset and discard any old unsaved development drafts.

Use the same PowerShell terminal for the variables, reset, imports and Flask startup below. The React development server can run in its own terminal.

```PowerShell
Set-Location "D:\Degree Life\FYP Full-Stack Development\corporate-attrition-app"
$ErrorActionPreference = "Stop"

$projectRoot = (Get-Location).Path
$pythonExe = Join-Path $projectRoot ".venv\Scripts\python.exe"
$researchRoot = "C:\Users\fikri\OneDrive - Asia Pacific University of Technology And Innovation (APU)\Degree\SEM 6\Project Module (FYP)\fyp-data-refinement"
$shapDir = Join-Path $researchRoot "data\models\shap_explainability_v1"
$customerMaster = Join-Path $researchRoot "data\final_v4_0_1\cleaned\company_population_clean.csv"
$flowFile = Join-Path $researchRoot "data\final_v4_0_1\cleaned\monthly_flows.csv"
```

Adjust only `$researchRoot` if that research project has moved. The current application path above is the one you supplied.

## 2. Check the source before resetting

```PowerShell
$requiredFiles = @(
    $pythonExe,
    (Join-Path $projectRoot "scripts\copy_database.py"),
    (Join-Path $shapDir "explainability_manifest.json"),
    (Join-Path $shapDir "dashboard_explanations.jsonl"),
    (Join-Path $shapDir "feature_values.csv"),
    (Join-Path $shapDir "feature_catalog.csv"),
    $customerMaster,
    $flowFile
)

foreach ($filePath in $requiredFiles) {
    if (-not (Test-Path -LiteralPath $filePath -PathType Leaf)) {
        throw "Missing required file: $filePath"
    }
}

$monthCounts = @(Import-Csv -LiteralPath (Join-Path $shapDir "feature_values.csv") -Encoding UTF8 | Group-Object cutoff_month)
foreach ($monthEnd in @("2024-02-29", "2024-03-31")) {
    $monthEntry = $monthCounts | Where-Object { $_.Name -eq $monthEnd }
    if ($null -eq $monthEntry -or $monthEntry.Count -ne 1000) {
        throw "Expected 1,000 feature rows for $monthEnd. Check the export before resetting."
    }
}
$monthCounts | Where-Object { $_.Name -in @("2024-02-29", "2024-03-31") } | Select-Object Name, Count
```

Expected: February and March each have 1,000 rows. This checks availability; the importer subsequently performs its full manifest/schema/explanation validation.

Keep the complete export directory unchanged. Do not manually delete other months from its CSV/JSONL files: the importer verifies the full export against its manifest and selects the requested month itself.

## 3. Back up and archive the active database

The default database is `backend\instance\churn.sqlite`. The commands respect `CHURN_DB_PATH` if you have explicitly configured another location, and retain that location for this terminal's imports and server startup.

```PowerShell
if ([string]::IsNullOrWhiteSpace($env:CHURN_DB_PATH)) {
    $dbPath = Join-Path $projectRoot "backend\instance\churn.sqlite"
} else {
    $dbPath = [System.IO.Path]::GetFullPath($env:CHURN_DB_PATH)
}

if (-not (Test-Path -LiteralPath $dbPath -PathType Leaf)) {
    throw "Existing database not found: $dbPath. Check the active database path before resetting."
}

Write-Host "Active database: $dbPath"
$env:CHURN_DB_PATH = $dbPath
$testStamp = Get-Date -Format "yyyyMMdd-HHmmss-fff"
$backupDir = Join-Path $projectRoot ".upgrade-backups\milestone2-$testStamp"
New-Item -ItemType Directory -Path $backupDir | Out-Null

& $pythonExe scripts\copy_database.py $dbPath --destination (Join-Path $backupDir "verified-snapshot.sqlite")
if ($LASTEXITCODE -ne 0) {
    throw "Backup failed. The active database has not been archived."
}

$originalName = Split-Path -Path $dbPath -Leaf
Move-Item -LiteralPath $dbPath -Destination (Join-Path $backupDir $originalName)
foreach ($suffix in @("-wal", "-shm", "-journal")) {
    $companion = "$dbPath$suffix"
    if (Test-Path -LiteralPath $companion) {
        Move-Item -LiteralPath $companion -Destination (Join-Path $backupDir "$originalName$suffix")
    }
}
Write-Host "Archived old database and saved verified snapshot in: $backupDir"
```

This gives the application an empty starting point at the original database path, with a recoverable copy of the old batches, reviews, action history and any additional tables inside that SQLite database. The provided backup utility uses SQLite's backup API and integrity checks. Its printed counts cover the original core tables; the backup itself copies the whole database.

Application source, the virtual environment, frontend dependencies, research CSVs and model/export artifacts stay in place. If the project has adopted a different database configuration beyond `CHURN_DB_PATH`, reconcile that path before applying this reset.

## 4. Import February as the only starting assessment

Still in the same project-root terminal:

```PowerShell
& $pythonExe -m flask --app backend/app.py import-shap --directory $shapDir --month 2024-02 --customer-master $customerMaster --flows $flowFile
if ($LASTEXITCODE -ne 0) {
    throw "February import failed. Keep the backup and resolve the reported error before continuing."
}
```

The supplied starter initialises an absent database when Flask creates the app. If your newer Milestone 2 code has an explicit fresh-database migration/setup command, apply that version's documented setup as well before entering case data. Keep your current implementation; do not replace it with the older starter schema.

The import should report `records: 1000` and `already_imported: false`. It includes names and observed flow history from the first import, so there is no need for a second February enrichment batch. Skip `init-demo`.

Start Flask:

```PowerShell
& $pythonExe backend\app.py
```

Keep/restart React in its separate terminal if needed:

```PowerShell
cd "D:\Degree Life\FYP Full-Stack Development\corporate-attrition-app\frontend"
npm run dev
```

Reload `http://127.0.0.1:5173/` in connected-data mode. Check `/api/months` at `http://127.0.0.1:5000/api/months` if you want to verify the batch inventory directly.

Expected immediately after import, before saving reviews:

| Item                           |                                 Expected |
| ------------------------------ | ---------------------------------------: |
| Imported batches               |                                        1 |
| February customers             |                                    1,000 |
| February flagged               |                                      208 |
| February below threshold       |                                      792 |
| Saved reviews/cases/follow-ups | Empty before you create new test records |

A single February assessment can still include twelve months of observed flow history: the importer reads that history from the unchanged source flow file. You do not need to import January as a separate assessment just to display those earlier observations.

The February forecast covers March–May 2024. Customer 944 should show approximately 84.4% risk, MYR 2,016,997.13 non-FD balances, MYR 0 FD balance and observed flows through February. Use the enriched batch returned by this import.

## 5. Test February before adding March

Create a small, documented set of development cases rather than reviewing every customer. For example:

| Test | Example action                                                           | What to verify                                                           |
| ---- | ------------------------------------------------------------------------ | ------------------------------------------------------------------------ |
| M2-A | Prioritise one customer; enter reason, reviewer, owner and optional date | Decision is saved and the customer appears in Reviewed Customers         |
| M2-B | Put another customer on Monitor                                          | Decision is distinct from prioritisation and remains retrievable         |
| M2-C | Record No immediate action for a third customer                          | The saved rationale remains visible; this does not change its model flag |
| M2-D | Plan and then record a completed/attempted follow-up using a linked task | Owner, dates, actor and task/event history remain traceable              |
| M2-E | Manually defer/close a case, if implemented                              | Change and reason are retained without modifying the prediction          |

Use clearly labelled notes such as “Development test M2-A”. No real customer contact is being asserted. Logging an action immediately on committee save is optional; the follow-up page is used when that later event is recorded.

For each chosen customer, record its ID, February prediction/batch ID, original risk, decision and case/task ID if available. Capture a screenshot of the original decision context.

Then:

* Reload the browser and verify saved decisions and history.
* Stop and restart Flask and verify again.
* Check that saving a decision did not change the risk, threshold, SHAP or recorded flow values.
* Check the draft, validation and conflicting-edit behaviour if these are part of your milestone acceptance.

Do not reset the database after these tests: these records are exactly what the March test needs.

## 6. Import March into the same database

Stop Flask with Ctrl+C in its terminal. Reuse the variables in that same terminal:

```PowerShell
& $pythonExe -m flask --app backend/app.py import-shap --directory $shapDir --month 2024-03 --customer-master $customerMaster --flows $flowFile
if ($LASTEXITCODE -ne 0) {
    throw "March import failed. February should remain published; inspect the error before continuing."
}
& $pythonExe backend\app.py
```

This imports March's existing frozen-model outputs. It does not export new predictions, upload raw source tables or test a new live-scoring service. You already have both months in the completed research export; `--month` selects which one enters the application.

Reload React and select March where appropriate. Expected: two assessment batches, February and March, each containing 1,000 customers. The database now has 2,000 customer-assessment records; those are not 2,000 different customers.

March's forecast covers April–June 2024. Its observed history must end in March. March's risk, flagged count, fees and waivers may differ from February; do not hardcode February's totals or require Customer 944's score to fall.

## 7. Cross-month acceptance for Milestone 2

| Check                                | Expected result                                                                                                            |
| ------------------------------------ | -------------------------------------------------------------------------------------------------------------------------- |
| Open the earlier prioritised case    | Same original February decision, reason, owner and context remain available                                                |
| Original assessment                  | February risk and evidence are preserved                                                                                   |
| Latest available assessment          | March month/risk is shown separately, with a way to open March flows and SHAP                                              |
| New risk is lower or below threshold | Earlier case is not automatically deleted, closed or relabelled                                                            |
| Existing follow-up                   | February-created tasks and event history remain attached to their original case                                            |
| New follow-up after March import     | Can be recorded against the same ongoing case where intended                                                               |
| Monthly review versus ongoing case   | A new March prediction may initially be awaiting its own review; that does not erase the February decision or ongoing case |
| Historical navigation                | Switching back to February shows that saved snapshot, without silently substituting March evidence                         |
| Restart                              | Both months, original reviews and follow-up history remain present                                                         |

If all of these work, and the same-month review/follow-up checks pass, you have good functional evidence for Milestone 2. Next is Milestone 3: RM briefing and PDF generation.

This historical replay tests the application workflow. It does not establish intervention effectiveness or validate a new monthly ETL/inference pipeline. A score change is a new model estimate, not proof that outreach retained a customer.

## Recovery if needed

Stop Flask. Keep the new test database and any sidecars together in a different archive folder if you want to retain this test run. Copy `verified-snapshot.sqlite` from the backup folder back to the active path printed in Step 3, with the backend stopped and no files left over from the newer database under that filename. Restart using the same database configuration.

Do not overwrite a running or open database. No recovery step needs to touch the research export or model files.

## Verification scope of this guide

The reset/import sequence was checked against the supplied starter using constructed two-customer February/March export fixtures: backup, archive, fresh February import, save/restart, then March import preserving the February review/action and imported history. The user's full dataset and latest Milestone 2 case implementation remain on the user's computer. Windows PowerShell commands have been written for that environment; they were not executed against the user's machine here.
