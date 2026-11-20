# Finance metrics: Revenue at Risk and Fee Subsidy Leakage (IR Objective 3)

Implemented in `backend/churn_backend/finance_metrics.py`. All values are **deterministic monthly MYR estimates at the assessment cutoff**, computed from each prediction's saved features. They are estimates of **relationship contribution**, not audited profit and not expected loss. There is no GenAI involvement: the card sentence is server-written and is never sent to the provider.

## Business logic

The "gentleman's agreement": the bank waives a corporate customer's transaction fees, and bears the per-transaction payment-network cost, in return for the customer keeping large fixed deposits (FDs). This mirrors US *account analysis / earnings credit* practice, where balances earn credits that offset service fees. The loophole is that transaction volume can grow until the bank's cost exceeds what the deposits earn.

## Formulas (per customer, per month, at the cutoff)

| Measure | Formula | Notes |
|---|---|---|
| Fee income | `estimated_fee_mean_3m_myr` | What the customer pays **after** waivers (verified, below) |
| Transaction cost | `(estimated_fee + estimated_waiver) / (1 + tier standard_markup_pct)` | Equals Σ `bnm_base_fee × count` exactly (verified, below); `bnm_base_fee` is the cost proxy |
| FD earnings | `fd_balance_myr × (OPR + liquidity_premium − fd_balance_weighted_offer_rate) / 12` | **Signed**: negative when the rate paid exceeds OPR + premium (never clipped). A genuine zero balance earns zero |
| Operating-balance earnings | `non_fd_balance_myr × (1 − SRR) × OPR / 12` | No liquidity premium |
| Relationship contribution | fee income − transaction cost + FD earnings + operating-balance earnings | |
| **Revenue at Risk (RaR)** | `3 × monthly contribution` | The 3-month forecast window. Shown **next to** the risk %, never multiplied by it. Label: "contribution at stake" |
| **FSL check A ("deal broken")** | active FD_THRESHOLD waiver **and** `fd_balance_myr < tier fd_waiver_threshold_myr` (strictly less) | Leakage A = monthly estimated waiver. POLICY_EXEMPT customers are excluded and labelled "policy exemption" |
| **FSL check B ("deal not paying")** | active waiver **and** `max(0, cost − fee income) > FD earnings` | Leakage B = shortfall − FD earnings. POLICY_EXEMPT customers are shown, labelled "policy", and totalled separately. Operating-balance earnings are deliberately ignored here: the agreement is fees-for-deposits |

**Rules that apply across the formulas:**
- **Active waiver** = `catalog_waiver_mean_pct > 0`.
- **A and B overlap.** Their totals are reported side by side and **never added**.
- **Missing is not zero.** A missing input makes the dependent measure unavailable, with the reason listed. A cutoff outside the verified rate tables makes all measures unavailable rather than guessed. An unknown tier does too.

## Parameters

| Parameter | Value | Source |
|---|---|---|
| Tier markup, FD waiver threshold | SME_S 0.40 / RM100,000; SME_M 0.30 / RM500,000; CORP_L 0.15 / RM2,000,000; CORP_XL 0.05 / RM5,000,000; GOV 0.05 / RM3,000,000 | Research `data/final_v4_0_1/cleaned/ref_corporate_tier.csv`, sha256 `0fa6e1c72c7f183ec0d1255c2a6dc02dfaa10c3dcadfdb194b72c288d2817f98` |
| Waiver basis by tier | FD_THRESHOLD for SME_S, SME_M, CORP_L; POLICY_EXEMPT for CORP_XL, GOV | Observed in `fee_matrix_clean.csv`, sha256 `2df2b489b18cc6ada3a60df99c7a1564fd6b9a0c8b1427142ffac96ab8b7041f`: uniform per customer, determined by tier for 1000/1000 customers |
| OPR | **3.00%** from 2023-05-03; table verified through 2024-07-10 | BNM Monetary Policy Statement, 3 May 2023 (https://www.bnm.gov.my/-/monetary-policy-statement-03052023). Held at the 24 Jan 2024, 7 Mar 2024 and 9 May 2024 meetings (…-24012024, …-07032024, …-09052024); OPR decisions index https://www.bnm.gov.my/monetary-stability/opr-decisions |
| SRR | **2.00%** from 20 Mar 2020 to 15 May 2025; 1.00% from 16 May 2025 | BNM, 19 Mar 2020: "lowered … from 3.00% to 2.00% effective 20 March 2020" (https://www.bnm.gov.my/-/additional-measures-to-further-support-smes-and-individuals-affected-by-the-covid-19-outbre-1); BNM, 8 May 2025 (https://www.bnm.gov.my/-/srr-0525) |
| Liquidity premium | **0.5%** base; sensitivity **0%** and **1.0%** | Design choice, described below |

All three assessment cutoffs (29 Feb, 31 Mar and 30 Apr 2024) use OPR 3.00% and SRR 2.00%.

## Verification against the research data (read-only)

**Fee features** (`feature_engineering_v1.py`, lines 125–136 and 382–385):
- `estimated_fee_units = effective_fee × count` and `estimated_waiver_units = (bank_standard_fee − effective_fee) × count`, per customer and product.
- `count` is inbound transactions plus **successful** outbound payments.
- The features are trailing 3-month means.

So fee income is after waivers, and fee + waiver = standard fee × count.

**Fee matrix** (14,000 contracts):
- `standard = base × (1 + tier markup)` holds for 14,000 / 14,000 contracts.
- `effective = standard × (1 − waiver_pct)` holds for 14,000 / 14,000.
- All of a customer's products share the tier markup, so (fee + waiver) / (1 + markup) = Σ base × count exactly.

**Waiver flag:**
- `waiver_flag ⇔ waiver_pct > 0` for 14,000 / 14,000 contracts, and the flag is uniform per customer.
- FD_THRESHOLD customers have the flag exactly when their onboarding FD is ≥ the tier threshold (463 / 437, no exceptions). That supports "≥ threshold = deal kept".
- All 100 POLICY_EXEMPT customers have it.

**Coverage on the M6 Test database:** `fd_balance_weighted_offer_rate` is missing in 1,835 / 3,000 predictions, all with `fd_balance_myr = 0`. Coverage is therefore 100%.

## Worked example (April 2024, prediction `36d5187951d9…`, customer 604, tier SME_S)

**Inputs:** fees RM0.2878 a month, waivers RM25.6356, operating balance RM18,313.53, FD RM0, active FD_THRESHOLD waiver.

| Component | Calculation | RM / month |
|---|---|---|
| Fee income | | +0.29 |
| Transaction cost | (0.2878 + 25.6356) / 1.40 | −18.52 |
| FD earnings | FD 0 | 0.00 |
| Operating-balance earnings | 18,313.53 × 0.98 × 0.03 / 12 | +44.87 |
| **Contribution** | | **+26.64** |
| **RaR** (3 months) | 3 × 26.64 | **RM79.92** |

- **FSL A:** flagged (FD 0 < RM100,000) at **RM25.64** a month.
- **FSL B:** flagged (shortfall 18.23 > FD earnings 0) at **RM18.23** a month.
- **Reading:** the relationship still contributes, but because of the operating balance, not the deposit the waiver was granted for.

## Sensitivity design

The liquidity premium represents the extra value of term funding over overnight money. It is uncertain, so the customer view shows FD earnings, contribution, RaR and the B flag at **0%, 0.5% (base) and 1.0%**. Only FD earnings depend on it. A customer with no FD is unaffected.

## Sources and citation status

| Topic | Status |
|---|---|
| BNM OPR and SRR | **Verified** by fetching the BNM pages above |
| Payment fees: Bank Islam Malaysia Berhad business IBG **RM0.10**, RENTAS **RM2.00** | **Verified** from BNM's *Comparative Tables — Businesses* (https://www.bnm.gov.my/documents/20124/57659/Comparative_Tables_Businesses_v7.xlsx, linked from https://www.bnm.gov.my/e-payment-services-and-fees). The table is a current comparison, not dated to 2024 |
| AFP account-analysis earnings credit formula EC = CB × (1 − RR) × ECR × (D/365) | Cited by the project owner; **not independently verified in this work** (AFP material is subscription-only) |
| Funds transfer pricing (deposit value = term funding credit minus rate paid; liquidity premium for term deposits) | Cited by the project owner; **not independently verified in this work** |
| FCA cash savings profitability analysis | Cited by the project owner; **not independently verified in this work** |
| BNM 2013 payment pricing reform (online IBG at 10 sen) | Cited by the project owner; **not independently verified in this work**. The current BNM table above shows IBG RM0.10 |

Before submission, the unverified items need a primary source with a URL or reference.

## Limitations

- **Cost proxy:** `bnm_base_fee` stands in for the bank's per-transaction cost. Actual PayNet charges to banks are not public, and the real-world BNM figure is a **customer price cap**, so cost is likely **overstated** and leakage conservative (more likely flagged than missed).
- **Synthetic standard fees:** the synthetic standard fee (base × 1.05 to 1.40) can exceed real price caps, e.g. online IBG RM0.10. This is a known simplification of the synthetic data.
- **Failed payments:** these carry no cost in the source counts (only inbound plus successful outbound are counted).
- **OPR as a funding proxy:** OPR is an **overnight** rate, used as a simplified proxy for term funding value. The liquidity premium sensitivity partly addresses this.
- **Costs left out:** no operating, staff, credit or capital costs.
- **Basis by tier:** this is an observed property of the synthetic source, not a documented generator rule. Re-verify the hashes and `TIER_TERMS` if the source changes.
- **OPR table range:** the table is deliberately limited to verified dates. Later cutoffs show as unavailable until a verified row is added.
- **What the numbers are not:** an estimate of relationship contribution, not audited profit, expected loss or a retention saving.

## Where it appears (stage 1)

- **API:** the customer detail record has `finance_metrics` (components, contribution, RaR, FSL A/B, sensitivity, unavailable reasons, sources). `/api/summary` has `finance_metrics` portfolio totals by tier and by flagged / not flagged, with coverage, plus a separate policy bucket.
- **Summary card (Finance section):**
  - one server-written sentence, e.g. "Contribution at stake over May–Jul 2024: RM79.92 (estimated relationship contribution; not a loss forecast; fee waiver condition not met; waiver cost exceeds deposit earnings).";
  - a negative contribution reads "Estimated relationship contribution is negative: −RM X a month (an estimate, not a loss forecast).";
  - POLICY_EXEMPT check-B results are not flagged on the card.
- **Not yet in the UI:** the Finance tab and the portfolio table are stage 2.
