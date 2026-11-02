# A beginner's development workflow

## The development loop

Choose one small user behaviour. Define what success looks like, change the relevant layer, run checks, test the user journey, inspect the difference and commit the change. Completing one thin journey across frontend, API and database is more useful than building every page with disconnected dummy data.

The first journey is already wired: monthly overview → customer evidence → save committee decision → reload. Start by tracing it, then refine one part. You do not need to learn React, Docker and cloud deployment at the same time.

## What each term means

| Term              | Practical meaning in this project                                               |
| ----------------- | ------------------------------------------------------------------------------- |
| Repository        | One version-controlled application folder                                       |
| Commit            | A named checkpoint of source changes                                            |
| Branch            | A separate line of work for one change                                          |
| Pull request (PR) | A reviewable proposal to merge a branch into `main`                             |
| CI                | GitHub automatically runs the same checks you run locally                       |
| CD                | An automated release/deployment step after agreed checks and a hosting decision |
| Environment       | Separate local/test/deployed configuration and data                             |
| Dependency        | A library the application needs, recorded in requirements                       |
| Migration         | A versioned transformation of the database schema                               |

Source control does not back up the SQLite database because it is deliberately ignored. Use `scripts/copy_database.py` with a new destination for development backups and keep the backup protected separately.

## Your first Git repository

Install Git if necessary. Complete the local application exercise first. From the project root:

```PowerShell
git init -b main
git status --short
```

Review what Git will include. `backend/instance`, databases, local `.env` files, large data and model binaries are ignored. The repository should contain source and documentation. If any old research data was placed in another folder, check it before adding files: exclusions are not a substitute for review.

If this is your first Git installation, set your own Git commit name and email through Git's normal setup. Do not copy another person's identity.

```PowerShell
git add .
git diff --cached --stat
git commit -m "Create full-stack attrition dashboard foundation"
```

In GitHub, create an **empty private repository** with a chosen name, such as `corporate-attrition-app`. Avoid adding an extra README there because this project already has one. Copy the actual URL GitHub gives you; replace the placeholder below:

```PowerShell
git remote add origin https://github.com/YOUR-USERNAME/corporate-attrition-app.git
git push -u origin main
```

Use GitHub's normal sign-in/credential flow. Do not place access tokens in source files. No remote has been created or credentials configured by the starter.

## Make one controlled change

Example: improve a label in the customer review form.

```PowerShell
git switch -c ui/refine-review-label
```

1. Find the form label in `frontend/src/main.js`.
2. Make one wording change.
3. Reload the dashboard and check desktop and narrow widths.
4. Run `scripts/check.py` using the virtual-environment Python.
5. Inspect the change before committing.

```PowerShell
git diff
git add frontend/src/main.js
git commit -m "Clarify committee review label"
git push -u origin ui/refine-review-label
```

Open a pull request on GitHub. Describe the problem and resulting behaviour, then state the checks performed. Wait for the `Application checks` workflow to pass and inspect the changes before merging. On repository plans that support it, make passing CI a branch protection/ruleset requirement; the workflow file alone does not prevent a direct push or merge.

After merging:

```PowerShell
git switch main
git pull --ff-only
```

For later changes, use another small branch. Avoid one long-lived branch containing every unfinished feature.

## Continuous integration in this starter

`.github/workflows/ci.yml` checks out the repository, selects Python 3.12 and Node.js 24, installs pinned requirements and runs `python scripts/check.py`. It runs on pull requests, pushes to `main`, and manual dispatch.

The workflow does not need a customer database or model binary. Tests make temporary fixtures and the one-case demo supplies a deterministic existing evidence sample. Do not add the full dataset or credentials merely to make CI pass.

This follows GitHub's [Python build/test guidance](https://docs.github.com/en/actions/tutorials/build-and-test-code/python): run reproducible application checks in a runner. A local pass is not a GitHub workflow run; inspect the Actions tab after pushing to verify the remote environment.

## Testing without drowning in tests

* Backend changes: exercise input validation, API output and persistence where behaviour changes.
* Frontend changes: check the user action and API/error behaviour. A text or colour change usually only needs direct inspection.
* Schema changes: verify migration of an existing database and preservation of decisions/history.
* Data/model changes: check temporal boundaries, schema/protocol and saved evaluation artifacts separately from page rendering.

The current checks do not establish model quality, usability or deployment throughput. Those are separate evaluations with their own acceptance criteria.

## Debugging by layer

| Symptom                                           | First place to inspect                                                                     |
| ------------------------------------------------- | ------------------------------------------------------------------------------------------ |
| Wrong alignment or crowded wording                | Browser layout, `styles.css`, then view markup                                             |
| Page loads but table stays empty                  | Browser Network tab: `/api/months`, selected `batch_id`, then `/api/customers`             |
| A value appears as missing                        | API JSON first; then the formatter. Do not substitute a guessed value                      |
| Save returns 422                                  | Validation message and request fields                                                      |
| Save returns 409                                  | Another saved version exists. Copy any needed draft notes, then load the latest decision   |
| Saved review disappears after restart             | Confirm `CHURN_DB_PATH`/default database and selected batch are unchanged                  |
| New score seems inconsistent with an older review | Check assessment month and original decision context; do not overwrite historical evidence |
| API returns 500                                   | Flask terminal traceback and a minimal failing request                                     |

Use the browser developer tools Network and Console panels, and the Flask terminal. Start with the layer where the data first becomes wrong.

## Environments and deployment

Local development uses one developer machine, local SQLite and no authenticated identity. Automated tests use disposable databases. A deployed demonstration will need an explicit plan for authentication, configuration/secrets, TLS, persistent database storage, backups and a production server. Record the chosen scope and load-test the actual environment before claiming readiness.

Do not expose the current local development server as a bank-facing service. Flask documents the [deployment boundary](https://flask.palletsprojects.com/en/stable/deploying/). Selecting a hosting platform comes later; it does not need to delay the local full-stack workflow.

Do not add deployment YAML merely because the acronym is CI/CD. First make the application and data lifecycle reliable, choose a host, and decide how releases preserve database state.
