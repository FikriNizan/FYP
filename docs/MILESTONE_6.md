# Milestone 6: Gemini decision support

Implemented on `milestone-6`, based on `milestone-5` at **7ef19cbb862108aa276fd8789381fd6b31f9626b**, and committed as `8e99d78` ("Milestone 6 - Phase 1"). The batch-summary change below is on `milestone-6-batch`. Owner acceptance remains pending. Monitoring's visual redesign remains deferred.

## Behaviour and architecture

Customer Review no longer displays the realised forecast outcome, whether loaded or missing. Its observed activity, history, shared model signals, Operations/Finance views and committee workflow remain. Outcomes and Monitoring APIs/calculations remain intact.

Summary has one **What stands out** section, which only reads summaries stored by the offline batch command (see "Batch summaries vs on-demand discussion" below) and otherwise shows deterministic text. RM Briefing has a per-case **Discussion draft** action for currently prioritised selections, alongside the existing deterministic briefing and questions. Loading, GET, refresh, print and PDF never generate. Each explicit discussion POST makes at most two bounded Gemini calls (one retry on provider unavailability, within the configured timeout). Drafts survive refresh/restart. Regeneration creates a fresh immutable UUID and clears review acknowledgement. Failed regeneration returns an honest deterministic fallback and retains an older matching saved version in storage; a later GET may retrieve it. Invalid IDs and stale fingerprints return errors, not fake successful fallbacks. An evidence-validation error leaves the surrounding deterministic customer UI available.

`ai_evidence.py` builds typed facts from saved server records. `ai_drafts.py` owns the SDK adapter, response validation, fallback, SQLite reservations/cache and export resolution. The shared React component suppresses responses after record changes/unmount, presents source details and review acknowledgement. All prose is plain text in React and escaped by the existing ReportLab helper.

The framework combines numerically verified SHAP explanations with evidence-grounded Gemini narratives, output validation and human review to reduce unsupported interpretations and support stakeholder understanding. Improved comprehension has **not** yet been measured.

## Evidence and mathematical hierarchy

1. **Prediction:** preserve saved calibrated probability, full-precision flag, threshold, identifiers and frozen policy. No rescoring/retraining.
2. **Explanation:** call the existing `validate_record`. Sum `base_logodds`, every higher/lower `contribution_logodds`, `other_features_contribution_logodds` and `probability_clip_adjustment_logodds`. Apply stable sigmoid. Reconstruction, reference probability and raw-to-sigmoid calibration residuals must each be at most **2e-10**. Feature/driver matching retains the importer's tolerance `1e-8 * max(1, abs(driver_value))`. Contributions are calibrated log-odds, not probability points. Displayed drivers alone are not the entire score.
3. **Business evidence:** a versioned allowlist supplies labels, group, units, date/window, allowed meaning, source and statement/question eligibility. Historical comparison uses `recent / trailing`, reports both percentage of baseline and `(1 - ratio)` reduction when appropriate. Missing facts are omitted; zero is retained. A ratio of 0.0087 is 0.87% **of** baseline and 99.13% lower, never a 0.87% reduction.
4. **Narrative:** Gemini writes original short blocks and verification questions, with statement kinds and evidence IDs. Complete server-formatted fact clauses are protected placeholders. Free wording can connect/emphasise facts; it cannot introduce literal quantities/dates or rewrite protected arithmetic. The server substitutes normal text only after checks.
5. **Human review:** inspect meaning, uncertainty, usefulness and unsupported interpretations. Numerical reconstruction is neither a confidence interval nor a semantic error bound.

Dictionary `m6-evidence-1` intentionally covers 15 verified existing concepts, rather than guessing all 78 predictor meanings. It covers combined monthly/recent/trailing flow, combined/incoming/outgoing baseline ratios, login/payment/bank-attributed failures, passive sessions, deposits scheduled within thirty days, operating/fixed-deposit balances, and historical monthly fee/waiver estimates. Definitions reuse the saved export conventions and the existing Operations, Finance and deterministic briefing definitions (`feature_schema.json`, `constants.py`, `OperationsPerspective.jsx`, `briefings.py`). Unknown definitions are excluded from narrative, while the original model display remains available. Dictionary coverage is deliberately partial.

Facts include exact saved assessment identity, protocol/model/feature versions, calibrated risk/threshold/flag, cutoff-safe recorded flow fields and relevant available signals of both directions. Periods distinguish snapshot exposures, historical means, baseline comparisons and forecasts. Summary builds no outcome/review/latest-assessment evidence; importing outcomes or a later assessment leaves its hash unchanged. RM uses one explicitly identified latest assessment, with separate original-assessment and current-review dates and locally resolved human context. Workflow dates are later human records, not inputs to an earlier prediction. There are no future outcome labels or future recorded flows in either provider payload.

External payloads use `Customer A`; customer/batch/prediction/case identifiers, names, paths, attribution and free-text notes stay local. **Conservative departure:** committee rationale/notes are represented externally by opaque typed references, then resolved locally as attributed human context. Gemini cannot interpret unsent note contents. This avoids transmitting personal names or prompt instructions embedded in those notes. It also limits how deeply Gemini can tailor discussion to free-text committee rationale.

## Validation boundaries

Checks enforce strict duplicate-free JSON, block/question counts, text/output bounds, known evidence references, correct declared kinds, standalone typed placeholders, no unresolved tokens, quantity/date/markup rules, restricted comparative language and specific causal/motive/profitability/complaint/instruction patterns. Questions must invite verification and tested operational/financial topic words must have relevant references. SHAP direction and observation period are preserved inside complete protected clauses; free-text comparisons are deliberately conservative. Valid free paraphrases are accepted; this is not a fixed sentence selector.

These rules cover specific errors, **not arbitrary semantic entailment**. A valid reference or absence of a prohibited phrase does not establish truth. Relevant nuance can be rejected, and unsupported wording outside the tested rules can still pass. No LLM judge is used. Fallback is deterministic and never stored as successful Gemini generation. Balances are exposures; separate fees/waivers are historical estimates, not profit or savings. Scheduled maturity is not evidence of withdrawal. Logged follow-up does not establish effectiveness.

## Provider and local configuration

Official Google GenAI Python SDK **google-genai==3.6.1**, installed/tested in the application `.venv`; the training environment was not changed. Adapter uses `Client(..., vertexai=False)`, explicit backend `GEMINI_API_KEY`, `models.generate_content`, `v1beta`, JSON MIME type and `response_json_schema`. Default configurable model: **gemini-3.5-flash-lite**, documented by the current SDK/model guides. Account access and live structured output remain subject to the live smoke test. No provider fallback, search, tools, execution, retrieval or background work.

From the repository root, in PowerShell:

```PowerShell
.\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
$env:TXB_GENAI_ENABLED = '0' # default; deterministic operation needs no key
$env:TXB_GENAI_PROVIDER = 'gemini'
$env:TXB_GENAI_MODEL = 'gemini-3.5-flash-lite'
$env:TXB_GENAI_TIMEOUT_SECONDS = '30'
$env:TXB_GENAI_MAX_OUTPUT_TOKENS = '2048'
# Only when ready for explicit synthetic live requests, set locally:
$env:GEMINI_API_KEY = '<your locally supplied Gemini API key>'
$env:TXB_GENAI_ENABLED = '1'
```

Never put the key in `VITE_*`, browser storage, fixtures, URLs, Git or chat. The adapter does not implicitly select `GOOGLE_API_KEY`. Restart the named session after changing its environment. Timeout is bounded to 1–60 seconds; output to 256–4096 tokens; provider evidence to 32,000 UTF-8 bytes; raw output to 16,000 bytes. The SDK always makes one attempt (attempts=1); any retry is the application's own bounded loop described in the batch section below. Summary allows 1–4 blocks and at most three questions; discussion 1–6 blocks and at most five questions. Resolved hard word ceilings are 220/340 including questions, allowing protected values/periods; prompts aim for shorter 80–130 / 120–200 narrative words. The finite SDK timeout bounds a request; it is not a guarantee of total wall-clock latency under every OS/network condition.

Missing configuration, safety/refusal, incomplete/empty/malformed output, provider errors and invalid narrative return safe fallback codes. Provider exception text and full responses are not exposed or logged. Structured SDK failures now use specific safe fallback codes; unknown failures retain `provider_request_failed` (see the 20 November diagnosis below). No live request was performed during implementation.

Google's [SDK documentation](https://googleapis.github.io/python-genai/), [structured outputs](https://ai.google.dev/gemini-api/docs/structured-output), [API keys](https://ai.google.dev/gemini-api/docs/api-key), [model guide](https://ai.google.dev/gemini-api/docs/models) and [service terms](https://ai.google.dev/gemini-api/terms) were consulted (official redirects followed). Current terms distinguish unpaid-service data use/human review from paid-service processing; paid requests may still be logged for abuse prevention/legal obligations. This configuration does not establish zero retention or banking compliance. Use synthetic Test data for verification. SHAP's [TreeExplainer documentation](https://shap.readthedocs.io/en/latest/generated/shap.TreeExplainer.html) distinguishes the explained model-output units; the app uses its verified saved calibrated export contract, not a new explainer.

## Cache, concurrency and export

Migration 005 adds only `ai_drafts`, its lookup index and `ai_reservations`, plus schema migration version 5. Drafts are separate from immutable prediction and human decision records. Cache keys hash allowed semantic evidence, assessment/customer/case versions, original/current/latest context, dictionary and prompt/schema version, provider and configured model. Request timestamps and `prepared_on` are excluded. Each successful generation stores a new immutable draft identity, generation time, provider/model, validation version, evidence references and actual checks. Content has immutable version 1 per UUID; regeneration creates a new UUID.

Reservations prevent concurrent identical requests across processes, with expiry bounded by request timeout plus thirty seconds. SQLite write transactions are released before network calls. Publishing re-resolves evidence under a write lock and checks reservation ownership/expiry, preventing a committee edit during generation from publishing a current-looking stale draft. Failed/expired reservations recover safely. GET reads a consistent snapshot without writes.

The **Include reviewed AI discussion draft** control is off by default. Review the exact draft and evidence checkbox for each case to include. Print and PDF freshly check selection, snapshots, cache identity and acknowledgement, with another snapshot check after draft resolution. Browser print displays the same server-returned draft as PDF; PDF never trusts browser-supplied prose. Acknowledgement is a local user assertion, not authenticated sign-off. Standard deterministic export remains available. Native browser printing outside the app's checked Print action cannot provide a fresh server validation; use the app action for reviewed AI inclusion.

## Reusable Test session and data protection

One-time preparation (safe to repeat; it resumes rather than overwrites):

```PowerShell
.\.venv\Scripts\python.exe scripts\prepare_m6.py
```

This uses the existing SQLite backup/copy mechanism on the verified `artifacts/m5-review-20261116-030542.sqlite`, refuses aliases/overwrite, then migrates **only** **`artifacts/m6-review.sqlite`**. Initial before/after business-table counts and hashes are recorded in `artifacts/m6-data-verification.json`. Schema changed 4 → 5, adding empty cache/reservation tables. Business rows are unchanged: three batches, 3,000 predictions, 3,000 outcomes; other exact counts are in the audit. Original Working/M5 Test remain at schema 4. Migration alters the M6 file; no claim of unchanged database bytes is made.

Ordinary repeat launch (same file every time):

```PowerShell
.\.venv\Scripts\python.exe scripts\local_session.py m6-test --backend-port 5066 --frontend-port 5186
```

Verified URL: **<http://127.0.0.1:5186/>**, backend **<http://127.0.0.1:5066>**. The launcher verifies backend and Vite proxy identities and schema 5 before printing URLs; the development badge says **Milestone 6 Test database · m6-review\.sqlite**. Port 5000 was occupied by an unverified process and was left untouched. The explicit port options isolate this session; occupied selected ports still fail. Ctrl+C stops only this launcher's children.

Use `milestone-5` code for its existing `working`/`test` commands. Milestone 6's launcher refuses those launch modes, and its migration code refuses the original confirmed files or aliases to them. Git branches do not isolate SQLite. Do not run Milestone 6 against M5's file through an old command. Runtime files, keys and local evidence artifacts remain ignored by Git.

## Verification and finite evaluation

```PowerShell
.\.venv\Scripts\python.exe scripts\check.py
.\.venv\Scripts\python.exe scripts\evaluate_m6.py
.\.venv\Scripts\python.exe -m pip check
# Optional: only after offline checks, configured key and synthetic Test inspection:
.\.venv\Scripts\python.exe scripts\gemini_smoke.py --prediction-id '<saved Test prediction ID>' --apply
```

The smoke command performs at most one external request, uses only the pinned M6 Test database and fails without explicit `--apply` and local configuration. It can store a validated draft; it does not alter business records. Inspect its evidence and output before enabling routine use.

Baseline actually passed: 78 backend, 14 utility, 10 Node and 71 React tests plus build. Final results and browser evidence are recorded below after verification. Offline test discovery uses mocks/fakes and requires no credentials/network.

Final checks on 19 November 2026 passed: **94 backend, 14 utility, 10 Node and 80 React tests**, production build, `pip check` and `git diff --check`. No assertions were removed to bypass a failure; the obsolete unavailable-preview expectations were replaced with operational drafting expectations, and migration tests now expect schema 5. The SDK boundary tests use the installed pinned Google types and mock only the client/network boundary.

Headless Chrome against the named M6 Test session passed Summary and RM fallback checks at **1440/760/380px**, badge/schema identity, unchanged review controls, expanded evidence, keyboard button focus, refresh, checked deterministic browser-print invocation and actual server PDF download. No page overflow or console exceptions were observed. Mobile evidence layout was visually inspected and corrected. Screenshots/results and PDF are in ignored `artifacts/m6-browser/`; full automated log is `artifacts/m6-check.log`. Browser checks did not exercise live Gemini or a live saved AI export; cache/restart/staleness and reviewed AI print/PDF resolution are covered by offline integration/component tests. An actual local server restart was also verified against the same schema-5 file.

Final data audit `artifacts/m6-final-data-check.json` confirms every business-table hash matches the initial copy and both originals match the initial read-only audit. M6 retains **3 batches, 3,000 predictions, 3,000 outcomes, 9 reviews, 9 cases, 7 follow-ups and 9 follow-up events**. AI cache and reservations remain empty after disabled-provider browser checks. The four currently prioritised cases have bounded provider payloads of **21,584–22,898 bytes**; redundant channel-level monthly flow rows remain local while combined monthly totals and channel ratios are supplied externally. No new scenario or outcome import was run.

Eight reproducible synthetic cases are checked in under `backend/tests/fixtures/m6_evaluation.json`: high/low risk, operational friction, Finance/deposits, falling/rising activity, partial/zero data, a continuing case and revised decision. `evaluate_m6.py` creates disposable records, compares mocked prose to fallback, checks protected values/references and reports numerical residuals separately. Initial run: eight examples, maximum reconstruction residual **0.0**, **zero external calls**, **zero human quality reviews**. These constructed residuals test arithmetic, not model fidelity or semantic quality. Mock latency is local fixture/validation latency, not Gemini latency. No Gemini-generated example has yet been accepted or rated.

Manual held-out rubric (owner or named Operations/Finance/RM reviewer, record example ID/date/reviewer, source type, pass/fail and observed errors):

* Factual support: compare every claim with supporting evidence and fallback.
* Attribution: higher/lower influence on saved estimate, no causal or trend inference from sign.
* Periods/values: cutoff observations, future prediction window, original/latest review separation, correct ratio/money meaning.
* Restraint/uncertainty: no invented motives, complaints, profitability or effectiveness; useful unknowns to verify.
* Readability/usefulness: concise plain wording and relevant Operations/Finance questions without padding.

Owner acceptance remains open until a reader can explain what was recorded through cutoff, what the following forecast predicts, which operational/financial signals deserve investigation, what remains unknown and what to ask before deciding. Record the number reviewed and errors, comparing Gemini output with evidence and fallback. Finite results do not establish universal hallucination-free text, improved understanding, real-bank compliance or intervention effectiveness.

### Acceptance still pending

* Live Gemini SDK/model/account smoke and observed provider latency.
* Human review of held-out Gemini-generated summaries and discussion drafts, including free-text tailoring limitations.
* Owner review of screen, reviewed AI export and continuing/revised cases.
* Production authentication, bank data governance and real-source point-in-time assurance.

## Live-failure diagnosis — 20 November 2026

The owner ran exactly one explicit smoke request for prediction `6eacc4bd0811472ff911b9243ae6576ee81c2f45232eaff316321a850e3ab5a0` in the PowerShell session holding the key. Sanitised result: **stage=request, exception\_class=ServerError, HTTP=503, provider\_status=UNAVAILABLE, provider\_reason=null, elapsed\_seconds=7.0**. The provider request failed before narrative validation. This demonstrates a Gemini service-unavailability response; it does not demonstrate an invalid key, depleted quota or faulty grounding. No second live request, model switch or billing change was made. Successful live generation remains pending.

The adapter now emits separate **server-terminal-only** diagnostics in local sessions: failure stage, allowlisted exception class, numeric HTTP status, allowlisted provider status/reason and elapsed time. It never logs exception strings, stack traces, prompts, evidence, API keys or full error responses. Non-local sessions do not emit/store them. Browser responses contain no diagnostic object or exception/status details. The existing smoke command enables local diagnostics and prints the same sanitised record:

```PowerShell
# In the already activated (.venv) terminal that holds the key:
python scripts/gemini_smoke.py --prediction-id 6eacc4bd0811472ff911b9243ae6576ee81c2f45232eaff316321a850e3ab5a0 --apply
```

The one authorised live request above is already consumed; this command is recorded for a later explicitly authorised acceptance check, not an instruction to keep retrying now. A coding-tool shell does not inherit variables set later in the owner's PowerShell. Do not copy keys into chat or recover another process's environment.

HTTP 503 now returns the safe code `provider_unavailable` with deterministic fallback and elapsed time, and the UI explains that no automatic retry was made. Structured SDK errors also distinguish authentication, access, model availability, rate limits, request rejection and timeouts without parsing private messages. Unknown failures retain `provider_request_failed`. Existing grounding, cache, business-data protections and single-attempt policy remain intact. The old custom temperature was removed because current Google guidance deprecates/ignores it for this model generation; that compatibility cleanup is **not claimed as the cause of this 503**.

Offline checks verified SDK 3.6.1, millisecond timeout, attempts=1, supported JSON-schema fields, and actual SDK request serialisation against a mocked transport. The target's evidence passed existing numerical checks and its provider payload was 19,756 bytes, within the existing bound. Google's [model capability page](https://ai.google.dev/gemini-api/docs/models/gemini-3.8-flash) and [troubleshooting guidance](https://ai.google.dev/gemini-api/docs/troubleshooting) were rechecked.

No key replacement or billing action is indicated by the observed 503. Leave the configured model/key intact, restart the local session to load the changed adapter, and perform a later single explicit acceptance request when the provider is available. If unavailability persists, check Google's service status/support for the existing Gemini model/project and provide only sanitised metadata. Do not automatically increase quota, change billing, weaken validation or substitute another model.

Diagnosis verification on 20 November 2026: 98 backend, 14 utility, 10 Node and 81 React tests passed, with production build, pip dependency checks and whitespace checks. Regression cases cover the demonstrated structured 503, one request/no retries, local-only redacted diagnostics, private browser responses, actual SDK serialisation through a mocked transport, and unchanged business records. Read-only before/after snapshots of Working, M5 Test and M6 Test business tables/schema match; records were not migrated or changed by this diagnosis. Logs are in ignored `artifacts/m6-live-diagnosis-check.log`; only the owner-run smoke above contacted Gemini.

On 20 November 2026 the owner explicitly selected Gemini 3.5 Flash-Lite for the next trial. The default and setup example now use `gemini-3.5-flash-lite`; an existing PowerShell model override must also be updated before restart. Google documents structured outputs for this exact stable ID: <https://ai.google.dev/gemini-api/docs/models/gemini-3.5-flash-lite> . The SDK-boundary regression covers the selected model. Grounding, timeouts, output bounds, one-attempt behaviour and model-specific cache identity remain intact. No live request was made for this configuration change; availability and narrative acceptance remain pending.

### Flash-Lite output validation diagnosis

The owner's first explicit Flash-Lite smoke completed the provider request and returned `output_validation_failed` after 4.375 seconds. No raw generated output was retained, so its exact failed rule cannot be reconstructed. Added local-only `validate_output` diagnostics with an allowlisted rule ID and validation elapsed time; no generated text, unknown references or JSON keys enter diagnostics/browser responses. Rule IDs distinguish schema, references, statement kind, protected content, placeholder boundaries, questions and resolved length.

Offline investigation identified and corrected a false positive: the comparison regex `ris\w*` also matched the ordinary noun “risk.” It now matches explicit rise/rising/riskier forms, allowing non-numerical discussion of risk while retaining the ban on unsupported trend/comparison claims. This confirmed lexical bug is not claimed as the established cause of the earlier unrecorded output rejection. Regression checks cover both accepted “saved risk estimate” wording and rejected invented rising/falling claims. Full checks passed: 100 backend, 14 utility, 10 Node and 81 React tests plus build; log: `artifacts/m6-validation-diagnosis-check.log`. A single further owner-run diagnostic smoke was requested to establish live acceptance or obtain the exact remaining rule; no live call was made by the coding-tool shell.

The owner-run follow-up Flash-Lite smoke at 02:02 MYT on 20 November returned stage=request, ServerError, HTTP 503, UNAVAILABLE, provider\_reason=null in 3.469 seconds, with the corrected `provider_unavailable` fallback and elapsed time. No output reached validation in that attempt, so live acceptance of the risk-word fix remains pending. No further retry was requested or performed. Both the earlier successful provider response/rejected narrative and this later provider outage are recorded distinctly; account/billing changes are not indicated by this 503.

### Flash-Lite HTTP 400 isolation — 20 November 2026

The owner reported an application HTTP 400 ClientError (2.265 seconds) with no captured status/reason. This is classified as request rejection, not provider unavailability. The SDK keeps structured data in `APIError.details`, with `status`/`message` shortcuts that can be absent for other envelope shapes. Local-only diagnostics now support direct/wrapped/list/string/JSON-string errors, detail/description variants, structured ErrorInfo and BadRequest field violations, and allowlisted alternative status/type/code values. Descriptions use fixed classifications for recognised key/prerequisite/parameter errors; otherwise only fixed protocol/error vocabulary survives, with unknown runs redacted and output bounded to 220 characters. Field paths must match known application configuration/schema paths. Keys, URLs, request bodies, customer evidence, unknown JSON fields and raw exception strings are not printed or returned to the browser.

Current request inspection against official model/GenerateContent/schema documentation: `gemini-3.5-flash-lite`, `v1beta models.generateContent`, response MIME JSON and `responseJsonSchema` are documented. The application schema uses object/array/string, properties/items/required/enum/additionalProperties only. Actual installed-SDK serialisation was tested against an intercepted transport: generated fields are maxOutputTokens, responseJsonSchema and responseMimeType; tools is an empty array, automatic function calling remains an SDK-only disabled option, and the system instruction is separate. Timeout remains milliseconds; attempts=1 remains no retry. Local serialisation success is not asserted as proof of remote account acceptance.

The new `--isolate` smoke mode uses the same explicit key/model/API and performs at most two requests: a synthetic minimal text request without evidence/schema/tools, then one application request only after minimal success. Regression checks exercise both branches and assert no application call after failure. The coding-tool shell has no key; the owner ran the bounded isolation command once. **Observed result: stage=minimal\_request, ClientError, HTTP 400, elapsed=1.063 seconds, status/reason/description unrecognised by the then-current extractor; application request skipped.** This proves that the application's evidence/system instruction/schema is not necessary to reproduce this particular rejection. It does not identify the exact credential, prerequisite, minimal-parameter or account cause.

After that result, extraction was extended for previously missed string/detail/JSON envelopes and generic vocabulary-redacted descriptions. The earlier provider body was not retained and the owner process exited, so the actual rejection wording cannot be recovered offline. No further live request was made or requested in this diagnostic run; the failed minimal gate prevents the second application request. **Root cause remains unconfirmed.** No speculative credential rotation, billing change, model switch, request-parameter change or weakening of grounding was performed. A future explicitly authorised diagnostic run would be required to capture the remaining rejection with the updated extractor.

Checks passed: **102 backend, 14 utility, 10 Node and 81 React tests**, production build, dependency/whitespace checks. Logs: ignored `artifacts/m6-400-check.log`. Read-only before/after business/schema snapshots for Working, M5 Test and M6 Test match (`artifacts/m6-400-data-after.json`). Only the diagnostic and smoke tooling changed for this HTTP-400 investigation.


### In-memory bounded diagnostic capture

`gemini_smoke.py --apply --isolate --hold-error` retains a failed provider exception only in the running CLI process. This is an explicit CLI opt-in (`TXB_GENAI_CAPTURE_ERROR` app setting), inactive in ordinary API sessions. The console prints safe diagnostics and a bounded shape view (allowlisted names and value types, unknown-field counts, no scalar values). If extraction needs repair, keep the process open: Enter reloads only the extractor against the same exception; q/EOF discards it and exits. The loop has no network/provider call path. A failed minimal gate still prevents the application call. Application provider failures can also be held for offline re-extraction. Raw exceptions, headers, URLs and response bodies are never written to disk or exposed to the browser.

Offline verification passed: 103 backend, 14 utility, 10 Node and 81 React tests, production build, dependency and whitespace checks (`artifacts/m6-bounded-capture-check.log`). A dedicated regression performs one mocked failing request, reloads/extracts the same retained exception offline, and asserts the SDK request count remains exactly one and private data is absent from console output. The original exception is retained only when explicitly enabled; no new generation is triggered by an offline reload.


### Demonstrated malformed credential formatting — 20 November 2026

The newly authorised bounded run made **one** minimal live request, returning HTTP 400 after **0.984 seconds**; the application gate stopped and no application request was made. The owner kept the CLI exception in memory. Several Enter presses re-extracted that same object offline; these were zero additional live requests. Shape inspection showed an SDK error with only `message` and HTTP reason `Bad Request`, containing an HTML error page rather than a structured Gemini JSON rejection. Accordingly RPC status and reason remain null; no quota/billing error is asserted.

The offline extractor repair added HTML-safe message handling and **derived categories/booleans only** from the attached failed request: official Gemini destination, HTTPS, expected v1beta generateContent route, POST, valid JSON object containing only contents/generationConfig, and the actual credential header matching the local environment key. Crucially, **key_has_control_characters=true**, with surrounding-whitespace=false and non-ASCII=false. The locally configured credential sent with the rejected request therefore contains an embedded non-printing ASCII control character. This is a demonstrated local credential-format fault consistent with an HTTP-layer HTML 400; the provider supplied no finer structured rejection. The eventual validity/quota of the intended clean token remains untested.

Smallest fix: re-enter the **same existing key token cleanly**, using the provider's copy button, rather than rotating it, editing the model, changing billing or stripping characters automatically. Exit the retained-error loop with q, then in the same activated PowerShell terminal enter it without echo/history exposure:

```powershell
$geminiKeyInput = Read-Host 'Paste your existing Gemini API key' -AsSecureString
$env:GEMINI_API_KEY = [System.Net.NetworkCredential]::new('', $geminiKeyInput).Password
Remove-Variable geminiKeyInput
```

Do not paste it into chat. Restart the usual named UI session to inherit the corrected environment. A later live acceptance attempt is a separate explicit operation; no further live request was made or requested in this diagnostic run after the failed minimal gate.

The new shared `genai_credentials.key_format_issue` check rejects control characters and surrounding whitespace locally in both application generation and minimal smoke, returns the safe `invalid_key_format` fallback and makes **zero SDK/network calls**. It never transforms the token. The UI explains the required local correction. The extractor can now identify this captured case with `description_code=credential_header_control_characters` and `diagnosis_source=local_request_check`, without pretending it is a Google RPC status or reason. Only credential-format booleans/categories are logged, never header contents, URLs, bodies, names, key characters or positions.

Final verification: **106 backend, 14 utility, 10 Node and 82 React tests**, production build, dependency/whitespace checks. Regressions cover HTML/structured errors, same-object offline re-extraction without extra calls, malformed key rejection before client creation, deterministic fallback/clear UI state, no credential disclosure and unchanged business snapshots. All Working/M5 Test/M6 Test business/schema snapshots match this run's read-only baseline (`artifacts/m6-bounded-data-after.json`). Successful clean-key live generation and narrative acceptance are still pending; no claim is made that the credential token itself has been authenticated.


### Purpose-specific question contract — 20 November 2026

The owner reported `validate_output/question_count` after fixing key formatting. Source inspection demonstrated a contract mismatch: the backend allowed at most three Summary questions or five RM questions, but the provider JSON schema had no `minItems`/`maxItems`, and the shared prompt mentioned the RM five-question rule without explicitly giving Summary its own three-question rule. The earlier failed UI response had not been retained, so its exact type/count cannot be reconstructed or claimed.

A memory-only response capture and privacy-safe question-contract metadata report were added to the existing CLI `--hold-error` option. Exactly one additional authorised application request was attempted by the owner: it returned HTTP 503 UNAVAILABLE after 5.61 seconds before producing output. No retry or second call was requested/performed. Therefore this run's honest metadata is: **purpose=summary; questions field type=unavailable; actual count=unavailable; permitted minimum=0; permitted maximum=3**. No generated text/questions or customer evidence was exposed. The previous rejection's actual count remains unknown; live acceptance of the corrected contract remains pending.

`ai_contract.py` now owns purpose limits. `schema_for(purpose)` and `purpose_instruction(purpose)` are used for every SDK call, and the backend validator reads the same bounds. Summary questions are an array with minItems=0/maxItems=3; RM discussion minItems=0/maxItems=5. The prompt explicitly permits [] for insufficient evidence and forbids padding. Existing block limits (1–4 Summary, 1–6 discussion) and resolved hard word limits (220/340 including questions) are shared and unchanged. All existing evidence, placeholder, direction and narrative validation remains in force. Over-limit/wrong-type output is rejected in full, never trimmed or coerced.

Contract version was then **m6-narrative-2** (superseded by `m6-narrative-4`, see "Schema simplified" below), included in existing cache identity; earlier draft records are preserved but cannot silently bypass the corrected prompt/schema version. Rejected output/evidence can be retained only in the explicitly opted-in CLI process. Offline Enter reloads contract/validator against the same in-memory response and never calls the provider, writes a draft or prints its text. Normal browser responses contain only the established fallback/error fields.

Regressions cover zero, one, exact maximum, maximum+one, null/object/string/boolean/number questions for both purposes; fresh schema instances; exact purpose-specific SDK schema/prompt; no private question text in logs or API responses; and existing grounding checks. A diagnostic false positive was also corrected: a generic 503 message mentioning “model” no longer reports model as an invalid field path. Field paths require structured field metadata or explicit parameter/field syntax.

Actual final checks: **111 backend, 14 utility, 10 Node and 82 React tests**, production build, dependency/whitespace checks. Logs: ignored `artifacts/m6-question-contract-check.log`. All Working/M5 Test/M6 Test business/schema snapshots match the read-only baseline (`artifacts/m6-question-data-after.json`). No model/key/billing/business record change was made. The provider outage prevented a live generated-example check, not offline implementation and regression verification.


## Batch summaries vs on-demand discussion — 21 November 2026

**Decision (owner):** "What stands out" summaries are generated in a **batch**, after a monthly assessment is published, for **flagged customers only** (saved `review_alert`, never recomputed). The Customer Review page only reads stored summaries and otherwise shows the existing deterministic text; it never generates on page load. RM **discussion drafts stay on demand** for currently prioritised cases.

**Why:** live trials hit 503 UNAVAILABLE and rate limits one click at a time. A batch protects the per-minute and daily quota, removes network waits from page loads, and can be retried and resumed offline. Discussion drafts depend on later human committee context, so they remain an explicit user action.

**Server enforcement:** `GET /api/predictions/<id>/ai-summary` is read-only; POST returns 405. Summaries are written only through `ai_drafts.generate`, called by the batch command (and the existing single-request smoke script).

**Retry policies** (application loop; the SDK still makes one attempt per call):

| Path | Attempts | Retries on | Backoff | Total wait |
|---|---|---|---|---|
| Smoke script (default) | 1 | none | — | one timeout |
| Discussion (on demand) | 2 | 503/500/502 (`provider_unavailable`) | 1.5 s × jitter 0.5–1 | within configured timeout; second attempt gets the remaining budget, skipped if under 10 s |
| Batch | 4 | unavailable, per-minute 429, timeout | exponential from max(2 s, 2 × min-interval), capped at 30 s, jitter 0.5–1 | bounded; reservation expiry covers the worst case |

429 responses whose structured `QuotaFailure.quotaId` contains `PerDay` become `provider_quota_exhausted`: no retry, and the batch stops. Validation failures are never retried, so the validator's behaviour is not hidden by repeated attempts.

**Command** (repository root, PowerShell; always uses `artifacts/m6-review.sqlite`, with no option to choose another database):

```PowerShell
# Counts only; zero API calls, no key needed, nothing written:
.\.venv\Scripts\python.exe scripts\generate_summaries.py --batch-id <batch_id> --dry-run
# Live (owner only, in the terminal holding the key):
.\.venv\Scripts\python.exe scripts\generate_summaries.py --batch-id <batch_id> --limit 5 [--min-interval 6] [--keep-rejected]
```

The command is resumable: customers with a stored draft matching the current evidence, contract and model are skipped. It prints generated / fallback-by-reason / skipped / remaining and the elapsed time, and never prints generated text. It stops cleanly (exit code 2) when the daily quota is exhausted or a per-minute limit persists through every retry, and reports how many flagged customers remain. `--keep-rejected` appends each rejected output, with its validation rule IDs and paths, to an ignored `artifacts/m6-rejected-<UTC>.jsonl` so the owner can judge whether Gemini or the validator is wrong. Payloads already use "Customer A" and the data are synthetic.

### Schema simplified and batch stop rules — 21 November 2026

The owner's first live batch request returned **HTTP 400 INVALID_ARGUMENT** before any generation. The redacted description matched Gemini's documented error "The specified schema produces a constraint that has too many states for serving", whose documented causes include long enum values and nested array length limits. The provider schema had both: an enum of every payload fact ID (long dotted IDs) on each `evidence_ids` item, and `minItems`/`maxItems` on those nested arrays.

`schema_for(purpose)` now describes shape only. `evidence_ids` is a plain string array. The top-level shape, required fields, `additionalProperties: false`, the three-value `kind` enum and the top-level block/question limits are unchanged. **The validator (`ai_output_audit.inspect_output`) is the enforcement layer, and its rules are unchanged:** unknown IDs, reference counts outside 1–4, duplicate references, block counts and question counts are still rejected in full, never repaired. Offline tests cover each rule, and a serialisation test asserts that the schema contains no fact IDs and no nested array bounds. The prompt still states the 1–4 exact-ID rule. Contract version is now **`m6-narrative-4`**, which is part of cache identity. No drafts were stored under earlier versions in M6 Test.

The batch command now also stops (exit code 2) on errors that would repeat for every customer: `not_configured`, `invalid_key_format`, `provider_authentication_failed`, `provider_access_denied`, `provider_model_unavailable` and `provider_request_rejected`. It also stops after **three consecutive customers** end in `provider_unavailable` (a likely outage). It reports how many flagged customers remain in each case.

Possible effect: without the enum, Gemini may cite unknown IDs or the wrong number of IDs more often. Those outputs fall back to deterministic text. `--keep-rejected` records them for owner review. Whether the 400 is resolved can only be confirmed by a live run.

### Summary card redesign (m6-narrative-5, stage 1) — 21 November 2026

**Evidence.** The owner's live Flash-Lite batch (`artifacts/m6-rejected-20261120T175116Z.jsonl`, synthetic, "Customer A") rejected **5 of 6** summaries, and every rejection included `placeholder_boundary`: the model kept embedding full-sentence fact placeholders mid-sentence (one also wrote "because"). Retry and backoff behaved correctly. The single accepted summary was judged by the owner, reading as the target user, to be hard to understand. It listed metrics without saying what happened, repeated itself, used system jargon, omitted the transaction trend and asked off-target questions.

**Design.** The summary is a shared card for the monthly retention meeting, so that non-technical Operations and Finance staff can each justify a decision. The **server** now owns structure and every fact sentence, in fixed sections:

1. **Bottom line:** risk and forecast window, saved flag versus threshold, main driver family, usual monthly value.
2. **Operations:** what is happening.
3. **Finance:** what is at stake; transaction-value trend first.
4. **What the model weighed:** the top three saved drivers with their direction.
5. **Questions:** at least one Operations and one Finance question when evidence allows.
6. **Decision:** a deterministic closing; plus a "service issues can be fixed independently" line only when a friction driver raised the estimate.

Gemini writes only one optional short note per section and audience-tagged questions. A `{{fact}}` placeholder in its text resolves to the fact's **name, never its value**. The deterministic fallback is the same card without AI notes, with template questions. On screen, AI sentences carry an "AI note" label. The Operations and Finance tabs are unchanged.

**Facts and wording.** The risk sentence states the target exactly: "Estimated chance that average monthly transaction value over {forecast window} falls to half or less of its 12-month average." Ratio sentences say "{r} of its 12-month average (which includes these 3 months)". Dates read "29 Feb 2024"; the jargon "saved model estimate" is gone. Values come from the saved evidence through the existing formatters, and the exact value, ID and units remain under "View supporting evidence".

The evidence dictionary is now `m6-evidence-2`, adding six recency/frequency concepts:
- successful outgoing payments per month (3 and 12 months);
- successful logins per month (3 and 12 months);
- days since the last successful outgoing payment;
- days since the last successful login.

Their definitions are copied from the research project's `data/features_v1/feature_dictionary.csv` (read-only) and cited in code. A null value means no event yet or an incomplete window, and is omitted.

**Ranking without thresholds.** A fact is *notable* only if its feature is among this customer's saved top-5 higher- or lower-risk SHAP drivers. Within a section, notable facts come first, ordered by |saved contribution|, then other facts in fixed order. If no service or online-banking measure is notable, the card says so ("None of the service or online-banking measures are among the main signals for this estimate."). It does not claim that anything is "usual".

**Validation.** Model text keeps the following rules:
- the prohibited/causal, comparison, quantity/date and markup rules;
- known, unique 1–4 references, with every placeholder cited;
- question form and relevance, and the 0–3 question count.

New rules:
- notes cite only their own section's facts;
- questions cite their audience's section;
- notes and questions are at most 25 words each;
- model text totals at most 100 words;
- (the earlier rendered-card limit of 320 words was removed on 21 November; see "Card length" below).

`placeholder_boundary`, `missing_protected_clause`, `statement_kind`, `block_count` and the old resolved-length rule do not apply to summaries (obsolete by construction). They still apply to the discussion purpose until stage 2. Contract version is **`m6-narrative-5`**. The renderer version is part of cache identity, so drafts stored under earlier versions are not shown as current.

**Card length (owner decision, 21 November).** A card's length comes from the server's own sentences, so rejecting an AI note would only fall back to a card that is just as long. The post-render word limit was therefore **removed as a rejection rule**. AI text stays bounded by its own limits: 25 words per note, 25 per question, 100 in total.

The server sentences were shortened instead:
- the trend reads "Transaction value in {period} averaged X% below (above) its 12-month average", while the exact ratio stays in "View supporting evidence";
- whole-number percentages drop ".0";
- the flag, signal-family, deposit, fee and frequency lines and the template questions are more compact;
- "12-month averages include the latest 3 months." appears **once**, as a footnote just before Decision, whenever any recorded sentence uses a 12-month average (Finance ratios, the Operations frequency sentences, or the usual monthly value).

**Correction (owner review):** the risk sentence's target baseline is also the 12 months ending at the cutoff (`outcomes.py`, `range(-11, 1)`), so it includes the latest 3 months like the features. The footnote therefore appears on **every** card.

Card length is now a **test on server output**: every fixture fallback card must be at most 240 words.

**Measured length.**
- Before shortening: fixture fallback cards 207–226 words; April 2024 flagged cards 257–305 (median 269).
- After shortening: fixture fallback cards 175–190 words; the demo customer with full synthetic features 225; **the 206 flagged April 2024 cards in M6 Test (read-only): 212–240 words, median 222.**

Stage 2 (separate approval) moves the discussion purpose, the Briefing screen and print/PDF to the same contract. Comprehension improvement has not been measured.

**Plain driver labels and terminology (21 November).** "What the model weighed" previously showed raw export labels for drivers outside the evidence dictionary, for example "Session duration mean 3m sec".

`ai_render.DRIVER_LABELS` now gives every one of the 78 predictors a plain 2–5-word label:
- **Source:** the research project's `data/features_v1/feature_dictionary.csv` (read-only).
- **Generic definitions:** where the dictionary shares template text across several features, the label was checked against the actual computation in `feature_engineering_v1.py`. Corrections made that way:
  - `closed_fd_count` = fixed deposits whose status is not active → "Inactive fixed deposits";
  - `fd_average_balance_myr` = the sum of each active deposit's reported average balance → "Fixed deposit average-balance total";
  - `session_forced_drop_rate_3m` = sessions with termination type FORCED_DROP → "Sessions ended by forced drop";
  - `outbound_processing_rate_3m` → "Share of payments in processing".
- **Where they are used:** the weighed section, placeholder names in AI notes and questions, and the provider payload. Gemini therefore sees the same vocabulary as the reader.

Card sentences and labels use **collections** for inbound flows and **payments** for outbound flows; combined flow stays "transaction value". The evidence panel's fact labels and the discussion purpose are unchanged. The renderer version is `render-2`, which is part of cache identity; the evidence hash is unchanged. After this change, April 2024 flagged cards measure 208–234 words (median 221).

### Evaluation finding: live summary run (m6-narrative-5), 21 November 2026

**Run:** the owner ran the batch on 5 flagged April 2024 customers (synthetic M6 Test data, "Customer A" payloads) under `m6-narrative-5`. **4 outputs were accepted and 1 was rejected.** Retry and backoff behaved as designed.

**What the model wrote:**
- **The rejected output:** a Finance note that cited **8 facts in 52 words** (over the note limits). Its notes only **listed fact names the card already shows**, for example "Exposures include {{a}}, {{b}}, …".
- **One accepted card had no AI notes at all** (every note empty). Its AI questions asked for values already on the card or for raw data:
  - "What are the current operating account balances?"
  - "How many login attempts were recorded during the period?"

**Owner judgement (reading as the target user):**
- These AI questions were **worse than the deterministic template questions**.
- **The server-rendered card alone is understandable and is the main comprehension layer.**

This is a small, single-reviewer qualitative finding. It is not a measured comprehension result.

**Design change (`m6-narrative-6`).** The summary AI role is narrowed to:
- **one optional link note,** shown as "What links these signals" after the Bottom line;
- **exactly one Operations and one Finance question.** A missing audience is filled with the template question.

**Link note rules:**
- at most 25 words;
- 2–3 cited facts from at least two different card sections;
- rejected as **list-only** if it has more than 3 placeholders, or if it has 2 or more placeholders with fewer than 4 connecting words outside them.

**Question rules:**
- at most one per audience;
- must open with Has/Have/Is/Are/Could/Did/Does/Do/Can, so "What is/are…" and "How many/much…" value requests are rejected;
- the existing audience, relevance and reference rules still apply.

All existing safety rules are unchanged: prohibited/causal, comparison, quantity/date, markup and references.

The prompt now carries two good and two bad examples for the link note and for each question audience. One of the owner's good link examples ("…alongside the fall in payments") had to use "…the change in payments", because the comparison rule rejects model-written directions; the card states the direction from the exact saved ratio. The Finance example "Is the customer moving part of its payments to another bank?" is kept by owner decision. It is the core silent-churn hypothesis, framed as an internal verification question, and asserting switching remains forbidden. If later runs show it repeated on most cards, it will be revisited.

The deterministic card is unchanged: April 2024 flagged cards are 207–236 words. The next live run will show whether the narrowed role adds useful links and questions.

### Final evaluation: live summary run (m6-narrative-6), 21 November 2026

**Run:** the owner ran the batch on 5 flagged April 2024 customers (synthetic M6 Test data) under `m6-narrative-6`. **5 of 5 outputs were accepted, 0 rejected**, and the retry/backoff path was not needed.

**Owner quality judgement (reading as the target user):**
- **Operations questions: good.** They were natural, relevant verification questions, better than the template.
- **Finance questions: weak and repetitive.** Three were near-identical "Is the customer maintaining its operating account balances…" variants that did not engage the card's Finance facts. The template is arguably better.
- **Link notes: mostly filler.** They followed an "X and Y both relate to Z" pattern copied from the prompt example. Nothing was false, but there was little insight.
- **The switching example** ("moving part of its payments to another bank") was not over-used; in fact it was not used at all.

**Finding.** Strict grounding made the LLM safe: across the evaluated runs, no accepted output contained an unsupported value, date, cause or recommendation. The **deterministic server card is the main comprehension layer**. The LLM's measurable added value is narrow: **tailored Operations questions**. This is a small, single-reviewer qualitative judgement, not a measured comprehension result.

**Decision.** The full 206-customer summary batch is **deliberately on hold** until the planned Revenue at Risk and Fee Subsidy Leakage work changes the Finance section. Generating summaries now would bake in a Finance section that is about to change. The closing work instead focuses the LLM where it helped, on questions (see "Client questions" below).

### Client questions: RM cheat sheet (closing work, m6-narrative-7), 21 November 2026

**Purpose.** The final evaluation showed that the LLM's strength is questions, not narrative. The closing work therefore turns questions into an **RM cheat sheet**: questions the relationship manager can say directly to the client in a meeting or call.

**C1. Deterministic, client-safe question bank** (`briefings.discussion_questions`, shown on the RM Briefing and in print/PDF):
- **Triggers:** only the customer's saved higher-risk drivers, strongest first, with no thresholds.
- **Limits:** at most one question per family and three in total.
- **Families:** all 78 predictors map to one of ten families or to "no client question". The families are collections, payments, overall transaction value, login problems, online banking usage, payment failures and processing, service friction, fixed deposits, fees and waivers, and accounts and balances. The static attributes and device-security monitoring are "no client question".
- **Fixed deposits:** a presence check chooses between "plans for your fixed deposits" and "surplus funds to place".
- **Fallback:** a general relationship check-in.
- **Wording:** approved by the owner. Questions never mention the model, estimates, risk, scores, flags, thresholds, churn, attrition, predictions, records or data, never mention other banks, and contain no numbers or dates.
- **RM-only source:** the plain driver label and value appear in a separate "Evidence" line for the RM, never in the question.

**C2. Optional on-demand AI client questions.** These replace the AI discussion draft. The same route, cache, reservations, `ON_DEMAND` retry, acknowledgement and Briefing print/PDF inclusion are reused.
- **Output:** Gemini returns 2–3 questions, each citing 1–3 facts.
- **Payload:** the customer's card sentences and drivers only. The committee rationale, notes and follow-ups are no longer added to the evidence and never leave the server.
- **Validation:** the existing prohibited/causal, comparison, quantity/date, markup and reference rules, plus:
  - `client_language`: the C1 banned terms, other banks or competitors, and placeholders, which would expose internal metric names;
  - `client_data_request`: "how many/much…" and "what is/are … rate/number/amount/balance…".
- **Openings:** open What/How questions are allowed for clients, unlike internal summary questions.
- **Fallback:** the C1 questions, labelled **Standard**; AI questions are labelled **AI-suggested**. Each shows a "Based on" line for the RM, on screen, in print and in the PDF.

The old block/clause discussion contract and its rules were removed once nothing used them.

**Not yet established:** no live client-question run has been made, and no client or RM has reviewed the questions. The banned-term rules prevent internal language from reaching the client; they cannot guarantee that a question is well judged for a particular relationship. The RM's review, through the existing acknowledgement, remains the control.

### Live evaluation: AI client questions (m6-narrative-7), 21 November 2026

**Run:** the owner generated AI client questions on demand for one prioritised case (`08a3f19a…`, synthetic M6 Test data, Gemini 3.5 Flash-Lite). **All 3 questions were accepted** by the validator; all were client-safe and evidence-linked.

| # | Question (as generated) | RM-only basis | Owner judgement |
|---|---|---|---|
| Q1 | "How have you been managing your incoming collections and outgoing payments recently?" | Collections vs 12-month average; Payments vs 12-month average | Good: combines collections and payments into one natural question |
| Q2 | "Have you experienced any technical difficulties when signing in to use online banking lately?" | Login failure rate; Days since last successful login | Good |
| Q3 | "Would you like to review the account fees and any applicable waivers on your profile?" | Estimated monthly fees; Estimated monthly waivers | **Not acceptable:** an **offer**, not a question about the client's situation. It commits the bank to a pricing conversation, which is a committee decision |

**Change (`m6-narrative-8`):**
- **New validator rule `client_offer`:** rejects client questions that offer or propose bank actions on pricing or terms, i.e. "Would you like (us) to / Do you want / Can we / Could we / Shall we … review, reduce, waive, discount, lower, change, adjust, revise, renegotiate, reprice or match", and the words discount, rebate, waive, "reduce/lower your fees" and "fee reduction".
- **Prompt:** now says "Ask about the client's situation and experience; never offer reviews, discounts, waivers or changes to fees or terms.", with Q3 as a bad example.
- **Tests:**
  - Q3 and similar offers are rejected;
  - Q1, Q2 and every standard question in the client question bank, including "Are the fees and charges on your accounts clear and in line with what you expected?", still pass all client rules.
- **Cache identity:** the contract-version bump makes the stored draft containing Q3 stale, so it is no longer served as current.

**Milestone 6 is closed.** The deterministic card is the comprehension layer. The LLM's role is narrowed to optional internal summary questions and on-demand client questions, under strict grounding and client-safe rules, with RM review. The full 206-customer summary batch remains on hold until Revenue at Risk / Fee Subsidy Leakage revise the Finance section.

### Policy change: item-level acceptance for summary drafts (21 November 2026, commit `94ab0e7`, branch `summary-rejections`)
**Why:** the full April summary batch (206 flagged customers; render-6, m6-narrative-8) accepted 120 drafts whole (58%) and fell back for 86 (42%).
- **The link:** all 86 had written the optional link. 64 links cited only facts from one card section (`link_sections`), almost always two Operations facts.
- **The Finance question:** 34 Finance questions mentioned payments without citing a payments fact (`question_relevance`).
- **Rules and mapping were correct:** the fact-to-section map and the rules were correct for the facts supplied. Since before the finance branch, the only payload difference is the stake line taking one Finance slot.

**What is dropped:** only the failing optional item, and its text is never stored, shown or logged.
- **A link failing only fit rules** (`link_sections`, `link_list_only`, `link_length`) is replaced by an empty link. The card then has no link section, exactly as the deterministic card.
- **A question failing only `question_relevance`** is removed. `render_summary` fills that audience with the deterministic template question.
- **Recorded:** stored content keeps `dropped` with rule IDs only. API responses carry counts only (`item_drops`).

**What still rejects the whole draft:**
- any `prohibited_claim`, `protected_content`, `unprotected_comparison`, `evidence_references`, `placeholder_reference`, `unresolved_placeholder`, `question_audience`, schema or `model_word_limit` failure, on any item. The word limit counts the full output, link included;
- a draft with nothing valid left after dropping.

These fall back to the deterministic card and are never stored as Gemini drafts.

**The contract version was deliberately not bumped** (it stays m6-narrative-8):
- the prompt and the rules are unchanged; only the unit of fallback changed;
- the 120 accepted drafts already satisfy the policy (none had a link or a dropped item), so they stay valid;
- a re-run calls only the 86 customers without a stored draft.

**Offline replay** of the stored rejected outputs (86-row pass): 54 accepted with the link dropped, 21 with a question dropped, 8 with both, and 3 still fall back.

**Known and deferred (a future m6-narrative-9, not started):** two prompt problems found in the diagnosis.
- **The "Good link" example is ambiguous:** failed logins and sessions without transactions are both Operations facts, and "payments" exists in both Operations and Finance.
- **The "Good finance question" example conflicts with the competitor ban:** it asks about moving payments to another bank.

Also undisclosed: the question-topic rule (a question that mentions payments, deposits, fees, balances or logins must cite a fact on that topic) is not stated to the model.
