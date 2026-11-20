# Handoff: Revenue at Risk and Fee Subsidy Leakage, stage 1 (21 November 2026)

## Branch and commits
Branch **`finance-metrics`**, created from `milestone-6-batch` at `6487f8b`; pushed, with no force-push and no co-author line.

| Commit | Content |
|---|---|
| `20f08a9` | `finance_metrics.py`, API fields, card sentence, tests |
| next commit | `docs/FINANCE_METRICS.md`, roadmap, this handoff |

The plan listed separate commits for the module and the wiring. They share one test file, so they went in as one commit.

## What changed and why
| File | Change |
|---|---|
| `backend/churn_backend/finance_metrics.py` (new) | `TIER_TERMS` (5 rows, with source hashes); verified BNM `OPR_TABLE`/`SRR_TABLE`; `customer_metrics` (components, contribution, RaR, FSL A/B, sensitivity 0/0.5/1.0%, unavailable reasons); `portfolio` (totals by tier and by flag, coverage, policy bucket) |
| `backend/churn_backend/repository.py` | The customer detail record has `finance_metrics`; `summary()` has portfolio `finance_metrics` |
| `backend/churn_backend/ai_evidence.py` | Attaches `finance_metrics` to the evidence **after** the hash (derived from the saved features; the evidence hash is unchanged) |
| `backend/churn_backend/ai_render.py` | `stake_line`: one Finance sentence after the trend line, inside the 6-line cap; `external=False` keeps it **out of the Gemini payload**; `render-5` |
| `backend/tests/test_finance_metrics.py` (new) | 12 tests |
| `docs/FINANCE_METRICS.md` (new), `docs/ROADMAP.md` | Formulas, parameters, verification, sources with their status, limitations; IR Objective 3 entry |

**No import was built,** by your approval: per-customer inputs are already in the saved features.

**Signed FD earnings:** these are **shown signed and never clipped**, as you decided; check B uses the signed value.

## Verification results (read-only; nothing was written to the research folder)
- **Fee features:** fee = effective × count and waiver = (standard − effective) × count, so fee income is after waivers and fee + waiver = standard × count.
- **Fee matrix:** `standard = base × (1 + markup)` and `effective = standard × (1 − waiver_pct)` each hold for 14,000 / 14,000 contracts. Cost = (fee + waiver) / (1 + markup) exactly.
- **Waiver basis:** uniform per customer and determined by tier. FD_THRESHOLD: SME_S, SME_M, CORP_L (900 customers). POLICY_EXEMPT: CORP_XL, GOV (100).
- **Active waiver:** `waiver_flag ⇔ waiver_pct > 0`, so active waiver = `catalog_waiver_mean_pct > 0`. The FD_THRESHOLD flag equals onboarding FD ≥ threshold (463 / 437).
- **Rates:** OPR 3.00% (MPS 3 May 2023, held 24 Jan / 7 Mar / 9 May 2024). SRR 2.00% effective **20 March 2020** (BNM's text; not 16 March) until 16 May 2025.
- **Worked example** (`36d5187951d9…`, SME_S): fee +0.29, cost −18.52, FD 0.00, operating +44.87, so **contribution +RM26.64 a month and RaR RM79.92**. FSL A RM25.64 a month; FSL B RM18.23 a month. Matches your +20 to +27 range.

**Citation status:**
- **Verified:** BNM OPR/SRR. Also Bank Islam business **IBG RM0.10 / RENTAS RM2.00**, from BNM's *Comparative Tables — Businesses* spreadsheet, read locally as data.
- **Marked "not independently verified":** the AFP earnings-credit formula, FTP/liquidity premium, the FCA cash savings study and the BNM 2013 IBG reform. The fetch agent had no search tool, and the pages it could reach didn't contain them.

## April 2024 results (M6 Test, read-only; snapshots identical before and after)
**Coverage:** 1,000 / 1,000 customers available. **Card length:** 207 / 221 / **239** words (min / median / max), ≤ 240.

**Your requested counts, by tier:**

| Tier | Customers | Negative FD earnings | A only | B only | Both A and B | B (policy) |
|---|---|---|---|---|---|---|
| SME_S | 300 | 2 | 1 | 6 | 34 | — |
| SME_M | 350 | 4 | 0 | 54 | 62 | — |
| CORP_L | 250 | 2 | 0 | 90 | 68 | — |
| CORP_XL | 60 | 0 | 0 | — | 0 | 56 |
| GOV | 40 | 0 | 0 | — | 0 | 39 |
| **Total** | **1,000** | **8** | **1** | **150** | **164** | **95** |

**Portfolio totals** (base premium 0.5%):

| Group | RaR (3 months) | FSL A (customers / RM a month) | FSL B, non-policy (customers / RM a month) | B, policy (customers / RM a month) |
|---|---|---|---|---|
| SME_S | RM67,349 | 35 / RM993 | 40 / RM762 | — |
| SME_M | RM544,168 | 62 / RM21,702 | 116 / RM41,829 | — |
| CORP_L | RM266,968 | 68 / RM312,742 | 158 / RM786,112 | — |
| CORP_XL | −RM5,203,596 | — | — | 56 / RM2,869,313 |
| GOV | −RM1,639,319 | — | — | 39 / RM922,854 |
| Flagged (206) | RM427,977 | 61 / RM12,475 | 63 / RM13,223 | 6 / RM19,345 |
| Not flagged (794) | −RM6,392,407 | 104 / RM322,962 | 251 / RM815,480 | 89 / RM3,772,821 |

**Finding:**
- **Negative total:** total contribution at stake is negative (−RM5.96m over 3 months), driven entirely by the **POLICY_EXEMPT** tiers, CORP_XL and GOV, whose waived transaction costs exceed what their balances earn.
- **FD_THRESHOLD tiers:** all three are positive in total, but CORP_L carries most of the A and B leakage.
- **Cost proxy caveat:** the cost proxy likely overstates cost (see Limitations), so these are conservative.

## Tests
**`scripts/check.py`** (exit 0):

| Suite | Before | After |
|---|---|---|
| Backend | 159 | **171** (+12) |
| Utility | 14 | 14 |
| Node | 10 | 10 |
| React | 90 | 90 |

The build passed, `pip check` was clean and `git diff --check` was clean. **No existing assertion changed.**

**New tests:**
- the worked example to the cent;
- missing vs zero;
- signed FD earnings;
- sensitivity;
- check A strict `<` and equality;
- POLICY_EXEMPT exclusion and label;
- check B boundary (0 > 0 not flagged);
- unknown tier and unverified cutoff;
- `TIER_TERMS` pinned;
- portfolio totals, coverage and API fields;
- card wording (flags, negative, policy) and that the sentence is not in the provider payload.

**Your import tests:** the "import hash/refusal" tests you listed are replaced by the `TIER_TERMS` pinning and unknown-tier tests, because no import was built (approved route).

## Open questions and limitations
- **Check B ignores operating-balance earnings by design.** A customer can have a positive contribution and still be flagged B (as in the worked example, where the operating balance pays). The card says "waiver cost exceeds deposit earnings" to stay precise.
- **Policy-exempt totals:** the POLICY_EXEMPT negative contribution dominates the portfolio total. Should the Overview show FD_THRESHOLD and POLICY_EXEMPT totals separately by default? This is a stage-2 decision.
- **Card length:** cards are at most 239 words, leaving almost no margin under 240.
- **Owner-cited references:** these still need primary sources (see `FINANCE_METRICS.md`).
- **Stage 2 next:** the Finance tab breakdown with sensitivity, and the Overview table. The full summary batch stays on hold.
