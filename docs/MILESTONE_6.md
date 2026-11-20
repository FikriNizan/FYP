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

Contract version was then **m6-narrative-2** (current code: `m6-narrative-3`), included in existing cache identity; earlier draft records are preserved but cannot silently bypass the corrected prompt/schema version. Rejected output/evidence can be retained only in the explicitly opted-in CLI process. Offline Enter reloads contract/validator against the same in-memory response and never calls the provider, writes a draft or prints its text. Normal browser responses contain only the established fallback/error fields.

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
