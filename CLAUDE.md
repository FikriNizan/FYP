# TxB Retention Studio — project rules

Final Year Project: explainable decision support for silent corporate transaction-volume
attrition. React/Vite frontend (`frontend/`), Flask API (`backend/churn_backend/`), SQLite.
The owner is a student: explain decisions plainly. For non-trivial work, read first,
propose a plan, and wait for approval before editing.

## Where things are

* `backend/churn_backend/ai_evidence.py`: typed, cutoff-safe evidence from saved records.
* `backend/churn_backend/ai_drafts.py`: Gemini adapter, validation, fallback, cache/reservations.
* `backend/churn_backend/ai_contract.py`, `ai_output_audit.py`, `ai_diagnostics.py`: output
  contract, validation rules, redacted diagnostics.
* `frontend/src/components/AIBriefingDraft.jsx`: Summary and RM discussion draft UI.
* `scripts/local_session.py`: named database sessions; `scripts/check.py`: all checks.
* `scripts/generate_summaries.py`: batch "What stands out" summaries (owner runs live).
* Milestone docs: `docs/MILESTONE_6.md`, `docs/LOCAL_DATABASE_WORKFLOW.md`, `docs/ROADMAP.md`.

## Daily commands (PowerShell, repository root)

```PowerShell
.\.venv\Scripts\python.exe scripts\check.py
.\.venv\Scripts\python.exe scripts\local_session.py m6-test --backend-port 5066 --frontend-port 5186
```

## Hard rules

1. **Research project is read-only.** Never write, move or regenerate anything in
   `C:\Users\fikri\OneDrive - Asia Pacific University of Technology And Innovation (APU)\Degree\SEM 6\Project Module (FYP)\fyp-data-refinement`.
2. **Frozen champion is immutable.** The CatBoost baseline + sigmoid recalibration, its
   threshold, protocol hash and saved predictions/SHAP must never be retrained, rescored or
   have their policy changed. Use the saved full-precision flag; never recompute it.
   *Exception (Milestone 7, owner-approved): the frozen champion may score shocked copies of saved features in the modelling environment for the OPR stress demonstration; its artifacts load read-only, saved predictions, SHAP and flags are never changed, and scenario scores live only in `artifacts/m7-scenarios/`, never in any predictions table or the Working DB.*
3. **Databases.** Never write to the Working database (`backend/instance/churn.sqlite`).
   Use only the named Test sessions. For Milestone 6 that is `artifacts/m6-review.sqlite` via
   `scripts/local_session.py m6-test`. Never commit `.sqlite` files, keys or `artifacts/`.
4. **API keys.** Never read, print, log, store or commit API keys. Never make live Gemini
   calls; the owner runs every live call. Tests mock the provider and need no network.
5. **Minimal changes.** Reuse existing modules. Do not build new diagnostic frameworks or
   tooling unless asked.
6. **Verify.** Run `scripts/check.py` before finishing and report the actual backend,
   utility, Node and React test counts plus build result. Never remove or weaken an
   assertion to make a test pass.
7. **Handoff.** Finish every task with `docs/handoffs/<YYYY-MM-DD>-<topic>.md` containing:
   branch and commit SHA; what changed and why (per file); commands run with their actual
   outputs (test counts); exactly how the owner runs anything new; open questions; known
   limitations.
8. **Git.** Work on a new branch, commit and push it. Never merge into `main`; never
   force-push.

## Grounding principles (do not weaken)

* Probabilities, money, dates and SHAP arithmetic stay deterministic; Gemini writes only
  bounded narrative/questions using protected placeholders.
* External payloads use the pseudonym "Customer A"; identifiers, names and free-text notes
  stay local.
* Validation failures fall back to deterministic text and are never stored as Gemini drafts.
* SHAP influence is not causation; balances are exposures; fee/waiver figures are estimates.
