# Update your existing project to React — start here

You have already copied the database into:

`D:\Degree Life\FYP Full-Stack Development\corporate-attrition-app\backend\instance\churn.sqlite`

That copy reported 3 batches and 2,001 prediction rows, matching the one-case demo, original full import and enriched full import. The React update changes source code; it does not convert, reimport or reset the database. The selected enriched February assessment should still show 1,000 customers, 208 flagged and 792 below threshold.

## 1. Prepare

Stop Flask and any frontend development server with Ctrl+C. Keep your existing project folder and `.venv`.

Extract the new ZIP separately. For the commands below, extract so the new package root is:

`D:\Degree Life\FYP React Update\corporate-attrition-app`

It should contain `README.md`, `backend`, `frontend` and `scripts`. Adjust `$update` if your extraction path differs. Do not extract over the existing folder.

## 2. Preview and apply the source update

In PowerShell:

```PowerShell
$project = "D:\Degree Life\FYP Full-Stack Development\corporate-attrition-app"
$update = "D:\Degree Life\FYP React Update\corporate-attrition-app"
& "$project\.venv\Scripts\python.exe" "$update\scripts\apply_react_update.py" "$project"
```

The first command is a preview. It checks supplied file hashes and compares existing files with the original v0.2.0 starter before writing anything. If it reports local edits, keep those files and review the listed differences before merging. A conflict stops the entire update; do not force-copy over your work.

If the preview succeeds:

```PowerShell
& "$project\.venv\Scripts\python.exe" "$update\scripts\apply_react_update.py" "$project" --apply
```

Changed source files are backed up under `.upgrade-backups`. The script preserves `backend\instance`, `.venv`, `.git` and files outside the update manifest. It removes the old `frontend/src/main.js` only when its contents match the original starter. No database schema migration is required for this React-only correction.

Do not run `copy_database.py` again: the correct working database is already in this project. Continue using the existing copied database.

## 3. Install the React dependencies

Check your terminal:

```PowerShell
node --version
npm --version
```

This package targets **Node.js 24.15 or later within 24.x**, recorded with the tested Node version in `.nvmrc`. If Node is missing or outside that range, install an appropriate Node 24 release from [Node.js](https://nodejs.org/en/download), then reopen PowerShell. npm comes with Node.

```PowerShell
Set-Location "$project\frontend"
npm ci
```

`npm ci` installs exactly the versions recorded in `package-lock.json`. It does not replace your database. Node is now a required frontend development/build tool, unlike the earlier plain-JavaScript starter.

## 4. Start both development servers

Terminal 1:

```PowerShell
cd "D:\Degree Life\FYP Full-Stack Development\corporate-attrition-app"
.\.venv\Scripts\python.exe backend\app.py
```

Terminal 2:

```PowerShell
cd "D:\Degree Life\FYP Full-Stack Development\corporate-attrition-app\frontend"
npm run dev
```

Open **<http://127.0.0.1:5173/>** for React development. The browser sends `/api` requests to Vite; Vite forwards them to Flask on port 5000. The development proxy preserves the Host header so the existing same-origin write protection continues to work. Do not add a broad CORS exception to solve local setup issues.

For one-address operation instead, run `npm run build` inside `frontend`, keep Flask running, and open **<http://127.0.0.1:5000/>**. Flask serves the generated `frontend/dist` files. After frontend source changes, rebuild if using this address. The development address at 5173 updates as you edit.

If Flask's root returns `frontend_not_built`, the API is running but the React build has not been generated. Use the Vite address or build first.

## 5. Complete the React checkpoint

* [ ] Enriched February batch `5f30af…`: 1,000 customers, 208 flagged and 792 below threshold.
* [ ] All three imported batches remain selectable.
* [ ] Search Customer 944 and confirm approximately 84.4% risk, MYR 2,016,997.13 operating account balances, MYR 0 FD balance and the twelve-month observed flow trend.
* [ ] Save a clearly labelled development review, refresh and confirm it remains.
* [ ] Restart Flask and confirm the saved review remains with the same batch.
* [ ] Run the checks below.

From the project root:

```PowerShell
.\.venv\Scripts\python.exe scripts\check.py
```

This runs backend/update checks, JavaScript utilities, React interaction tests and the frontend build. It uses temporary test databases; it does not open your working customer database.

Once this checkpoint passes, continue with [Milestone 2](MILESTONE_2.md): Reviewed Customers and follow-up. That feature is the next implementation milestone; converting to React does not itself complete it.
