# Finance metrics: Revenue at Risk and Fee Subsidy Leakage (IR Objective 3)

Implemented in `backend/churn_backend/finance_metrics.py`. All values are **deterministic monthly MYR estimates at the assessment cutoff**, computed from each prediction's saved features. They are estimates of **relationship contribution**, not audited profit and not a forecast of money the bank will give up. There is no GenAI involvement: the card sentence is server-written and is never sent to the provider.

## Business logic

The "gentleman's agreement": the bank waives a corporate customer's transaction fees, and bears the per-transaction payment-network cost, in return for the customer keeping large fixed deposits (FDs). This mirrors US *account analysis / earnings credit* practice, where balances earn credits that offset service fees. The loophole is that transaction volume can grow until the bank's cost exceeds what the deposits earn.

## Formulas (per customer, per month, at the cutoff)

| Measure | Formula | Notes |
|---|---|---|
| Fee income | `estimated_fee_mean_3m_myr` | What the customer pays **after** waivers (verified, below) |
| Assumed transaction cost | `(estimated_fee + estimated_waiver) / (1 + tier standard_markup_pct) × cost_ratio` | At cost_ratio 1.0, equals Σ `bnm_base_fee × count` exactly (verified, below). `bnm_base_fee` is the cost proxy |
| Fixed deposit earnings (estimate) | `fd_balance_myr × ((1 − SRR) × (OPR + liquidity_premium) − fd_balance_weighted_offer_rate) / 12` | **Signed**: negative when the rate paid exceeds the funding value (never clipped). A genuine zero balance earns zero. Unavailable, with a reason, when OPR or SRR is not verified for the cutoff. Owner formula of 23 Nov 2026 (render-8); earlier: `fd × (OPR + premium − offer_rate) / 12` |
| Operating-balance earnings | `non_fd_balance_myr × (1 − SRR) × OPR / 12` | No liquidity premium |
| Relationship contribution | fee income − transaction cost + FD earnings + operating-balance earnings | |
| **Revenue at Risk (RaR)** | `3 × monthly contribution` | The 3-month forecast window. Shown **next to** the risk %, never multiplied by it. Label: "contribution at stake" |
| **FSL check A ("deal broken")** | active FD_THRESHOLD waiver **and** `fd_balance_myr < tier fd_waiver_threshold_myr` (strictly less) | Leakage A = monthly estimated waiver. POLICY_EXEMPT customers are excluded and labelled "policy exemption" |
| **FSL check B ("deal not paying")** | active waiver **and** shortfall = assumed transaction cost − fee income **> 0** **and** `max(fixed deposit earnings, 0) < shortfall` | Uncovered (leakage B) = shortfall − max(fixed deposit earnings, 0). Owner rule of 22 Nov 2026: negative fixed deposit earnings are **not** folded into check B; they stay visible as their own component. POLICY_EXEMPT customers are shown, labelled "policy", and totalled separately. Operating-balance earnings are deliberately ignored here. |

**Why fixed deposit earnings are net of SRR.** A ringgit fixed deposit is part of the bank's eligible liabilities, so the bank must hold the statutory reserve share (SRR, 2.0% for every 2024 cutoff) at Bank Negara Malaysia in a non-interest-bearing account. Only the remaining (1 − SRR) of the balance can be deployed at the funding value (OPR + liquidity premium), but the bank pays the offered rate on the **whole** balance. Operating-balance earnings already used (1 − SRR); fixed deposits now do the same. Sources are listed under Parameters and in the sources table.

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
| SRR | **2.00%** from 20 Mar 2020 to 15 May 2025; 1.00% from 16 May 2025. Applied to fixed deposits and operating balances | BNM, *Policy Document on Statutory Reserve Requirement*, BNM/RH/PD 029-41, issued 15 May 2025 (https://www.bnm.gov.my/documents/20124/938039/pd_SRR_15May2025.pdf): para 6.1 defines the eligible liabilities (EL) base as ringgit deposits and non-deposit liabilities, net of interbank assets; Appendix 4 Part A lists "RM Fixed Deposits Accepted". Earlier versions of the same policy document: EL defined this way since 1 September 2007; SRR 2.0% of EL from 20 March 2020 (applies to all 2024 cutoffs). BNM, 19 Mar 2020: "lowered … from 3.00% to 2.00% effective 20 March 2020" (https://www.bnm.gov.my/-/additional-measures-to-further-support-smes-and-individuals-affected-by-the-covid-19-outbre-1); BNM, 8 May 2025 (https://www.bnm.gov.my/-/srr-0525) |
| Liquidity premium | **0.5%** base; sensitivity **0%** and **1.0%** | Term-funding benefit of deposits; the FCA analysis below describes the liquidity premium |
| Cost ratio | **1.0** base (conservative); sensitivity **0.75** and **0.5** | Share of `bnm_base_fee` assumed as the bank's real per-transaction cost. `bnm_base_fee` is a customer price cap, so the real cost is likely lower |

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
| Assumed transaction cost | (0.2878 + 25.6356) / 1.40 | −18.52 |
| Fixed deposit earnings (estimate) | FD 0 | 0.00 |
| Operating-balance earnings | 18,313.53 × 0.98 × 0.03 / 12 | +44.87 |
| **Contribution** | | **+26.64** |
| **RaR** (3 months) | 3 × 26.64 | **RM79.92** |

- **FSL A:** flagged (FD 0 < RM100,000) at **RM25.64** a month.
- **FSL B:** flagged (shortfall 18.23 > 0 and fixed deposit earnings 0 do not cover it); uncovered **RM18.23** a month.
- **SRR formula (23 Nov 2026):** this customer has no fixed deposit, so every figure in this example is unchanged.
- **Reading:** the relationship still contributes, but because of the operating balance, not the deposit the waiver was granted for.

## Sensitivity design

Two assumptions are uncertain, so both are shown, as customer-level variants and as portfolio totals.

- **Cost ratio (1.0 / 0.75 / 0.5).** This scales only the transaction cost. **It dominates the headline result** and decides its sign.
- **Liquidity premium (0% / 0.5% / 1.0%).** This scales only FD earnings. Customers with no FD are unaffected. In this data its effect is **substantial**: it moves the April total by about RM6.9m, and it flips the FD-threshold total from negative to positive.

**April 2024, Revenue at Risk over 3 months (M6 Test, 1,000 customers, read-only).** Each row varies one assumption, with the other at base.

| Group | Cost ratio 1.0 / 0.75 / 0.5 (premium 0.5%) | Premium 0% / 0.5% / 1.0% (cost ratio 1.0) |
|---|---|---|
| FD-threshold tiers (SME_S, SME_M, CORP_L) | **+RM0.63m / +RM2.58m / +RM4.54m** | −RM1.14m / +RM0.63m / +RM2.39m |
| Policy-exempt tiers (CORP_XL, GOV) | **−RM7.09m / −RM2.66m / +RM1.76m** | −RM8.80m / −RM7.09m / −RM5.38m |
| All customers | −RM6.46m / −RM0.08m / +RM6.30m | −RM9.93m / −RM6.46m / −RM2.99m |
| Customers with negative RaR | **259 / 173 / 68** | — |
| Customers flagged by FSL check B (non-policy) | 329 / 291 / 205 | — |
| Uncovered a month, check B (non-policy) | RM869,318.19 / RM491,368.43 / RM177,050.03 | — |

Check B policy-exempt at base: 96 customers, RM3,865,735.39 a month. Check A: 165 customers, RM335,436.84 a month (unchanged by the SRR formula). Customers with negative fixed deposit earnings: 15.

**SRR formula: before and after (April 2024, M6 Test, read-only, 23 Nov 2026).** Before = `fd × (OPR + premium − offer_rate) / 12`; after = `fd × ((1 − SRR) × (OPR + premium) − offer_rate) / 12`.

| Measure | Before | After |
|---|---|---|
| RaR, FD-threshold tiers (cost 1.0, premium 0.5%) | +RM878,485.68 | +RM626,596.11 |
| RaR, policy-exempt tiers | −RM6,842,915.33 | −RM7,087,215.15 |
| RaR, all customers | −RM5,964,429.65 | −RM6,460,619.04 |
| Cost ratio 1.0 / 0.75 / 0.5, FD-threshold | +0.88m / +2.84m / +4.79m | +0.63m / +2.58m / +4.54m |
| Cost ratio 1.0 / 0.75 / 0.5, policy-exempt | −6.84m / −2.42m / +2.00m | −7.09m / −2.66m / +1.76m |
| Cost ratio 1.0 / 0.75 / 0.5, all | −5.96m / +0.42m / +6.80m | −6.46m / −0.08m / +6.30m |
| Premium 0% / 0.5% / 1.0%, FD-threshold | −0.92m / +0.88m / +2.68m | −1.14m / +0.63m / +2.39m |
| Premium 0% / 0.5% / 1.0%, policy-exempt | −8.59m / −6.84m / −5.10m | −8.80m / −7.09m / −5.38m |
| Premium 0% / 0.5% / 1.0%, all | −9.51m / −5.96m / −2.42m | −9.93m / −6.46m / −2.99m |
| Negative RaR, cost 1.0 / 0.75 / 0.5 | 242 / 160 / 65 | 259 / 173 / 68 |
| Check B non-policy customers, cost 1.0 / 0.75 / 0.5 | 314 / 275 / 195 | 329 / 291 / 205 |
| Check B non-policy uncovered a month, cost 1.0 | RM826,316.33 | RM869,318.19 |
| Check B non-policy uncovered a month, cost 0.75 | RM459,845.97 | RM491,368.43 |
| Check B non-policy uncovered a month, cost 0.5 | RM161,998.95 | RM177,050.03 |
| Check B policy-exempt (base) | 95 · RM3,792,166.15 | 96 · RM3,865,735.39 |
| Check A | 165 · RM335,436.84 | 165 · RM335,436.84 (unchanged) |
| Customers with negative FD earnings | 8 | 15 |

The table below records the earlier check B rule change of 22 Nov 2026, under the earlier FD formula.

**Check B before and after the owner rule (April 2024, M6 Test, read-only, 22 Nov 2026).** Earlier rule: `max(0, cost − fee) > FD earnings`, so negative FD earnings could flag B with no transaction shortfall.

| Cost ratio | 1.0 | 0.75 | 0.5 |
|---|---|---|---|
| Customers flagged, earlier rule (non-policy) | 314 | 275 | 196 |
| Customers flagged, owner rule (non-policy) | 314 | 275 | 195 |
| Uncovered a month, earlier rule | RM828,703.31 | RM462,232.94 | RM164,385.92 |
| Uncovered a month, owner rule | RM826,316.33 | RM459,845.97 | RM161,998.95 |

Under that earlier formula, policy-exempt check B was unchanged (95 customers, RM3,792,166.15 a month), and so was check A (165). Revenue at Risk totals and every row of both sensitivities are **identical** under both rules: check B never enters the contribution.

**How to read it:**
- **Total RaR:** the cost-ratio range spans about RM12.8m and the premium range about RM6.9m. The headline sign therefore depends on assumptions the data cannot settle. The UI shows both sensitivities with equal weight; a negative figure means the estimated contribution is negative at the assumed cost, nothing more.
- **Worked example** (customer 604, no FD): contribution is +RM26.64 / +RM31.27 / +RM35.90 a month at cost ratio 1.0 / 0.75 / 0.5, and FSL B is RM18.23 / RM13.60 / RM8.97. The premium has no effect, because there is no FD.

## Sources and citation status

| Topic | Status and support |
|---|---|
| BNM OPR and SRR | **Verified** (BNM pages listed under Parameters) |
| SRR applies to fixed deposits | BNM, *Policy Document on Statutory Reserve Requirement*, BNM/RH/PD 029-41, issued 15 May 2025, https://www.bnm.gov.my/documents/20124/938039/pd_SRR_15May2025.pdf: para 6.1 (EL base = ringgit deposits and non-deposit liabilities, net of interbank assets); Appendix 4 Part A lists "RM Fixed Deposits Accepted". Earlier versions of the same policy document: EL base defined this way since 1 September 2007; SRR 2.0% of EL from 20 March 2020 (applies to all 2024 cutoffs). Supplied by the owner (23 Nov 2026) |
| SRR balances earn no interest | e.g. HSBC Bank Malaysia Berhad, financial statements 30 Sep 2025: "non-interest bearing statutory deposits … Section 26(2)(c) and 26(3) of the Central Bank of Malaysia Act 2009". Supplied by the owner (23 Nov 2026) |
| Account analysis / earnings credit (AFP) | **Verified**: https://www.financialprofessionals.org/training-resources/resources/articles/Details/an-introduction-to-account-analysis-statements. Balances are used "to offset banking fees through earnings credits"; formula "EC = CB x (1 – RR) x ECR (D/365)". The page states a 365-day basis only |
| Funds transfer pricing and liquidity premium (FCA) | **Verified**: FCA, *Cash savings profitability analysis* (published 18/09/2024), https://www.fca.org.uk/data/cash-savings-profitability-analysis/printable/print. It compares "the interest expense paid to customers with the income generated through FTP", and describes "the Liquidity Premium, which reflects the benefit earned by deposits which remove liquidity risk (such as deposits with a fixed contractual term)" |
| BNM 2013 pricing reform | **Verified**: BNM, *A New Pricing Strategy to Promote Greater Efficiency* (20 March 2013), https://www.bnm.gov.my/-/a-new-pricing-strategy-to-promote-greater-efficiency. "Effective 2 May 2013, the fee for Interbank GIRO or IBG transactions that is performed online via internet banking and mobile banking, will be at 10 sen." |
| Bank Islam business IBG RM0.10, RENTAS RM2.00 | **Verified** from BNM's *Comparative Tables — Businesses* (https://www.bnm.gov.my/documents/20124/57659/Comparative_Tables_Businesses_v7.xlsx, linked from https://www.bnm.gov.my/e-payment-services-and-fees). A current comparison, not dated to 2024 |
| PayNet business IBG charges | **Not verified**: https://paynet.my/business-interbank-GIRO/charges-transaction.html returned HTTP 403 to the fetch tool |

## Limitations

- **Cost proxy:** `bnm_base_fee` stands in for the bank's per-transaction cost. Actual PayNet charges to banks are not public, and the real-world BNM figure is a **customer price cap**, but a price cap does not by itself show whether the proxy overstates or understates the bank's real cost; the direction of bias is **uncertain** without actual cost data. The cost-ratio sensitivity (1.0 / 0.75 / 0.5) shows how strongly the headline depends on this.
- **Synthetic standard fees:** the synthetic standard fee (base × 1.05 to 1.40) can exceed real price caps, e.g. online IBG RM0.10. This is a known simplification of the synthetic data.
- **Failed payments:** these carry no cost in the source counts (only inbound plus successful outbound are counted).
- **SRR on fixed deposits:** the reserve is applied to the whole FD balance at the cutoff's SRR rate. BNM computes the requirement on an averaged EL base net of interbank assets, so the per-customer share is an approximation.
- **OPR as a funding proxy:** OPR is an **overnight** rate, used as a simplified proxy for term funding value. The liquidity premium sensitivity partly addresses this.
- **Costs left out:** no operating, staff, credit or capital costs.
- **Basis by tier:** this is an observed property of the synthetic source, not a documented generator rule. Re-verify the hashes and `TIER_TERMS` if the source changes.
- **OPR table range:** the table is deliberately limited to verified dates; verified rates end **10 Jul 2024**. Later cutoffs (for example a July 2024 or later assessment) show Finance contribution as unavailable, with the reason "OPR not verified for this cutoff (verified rates end 10 Jul 2024)", until a verified row is added. This is deliberate fail-closed behaviour.
- **What the numbers are not:** an estimate of relationship contribution, not audited profit, a forecast of money given up, or a retention saving.

## Where it appears

- **API:** the customer detail record has `finance_metrics` (components, contribution, RaR, FSL A/B, both sensitivities, unavailable reasons, sources). `/api/summary` has `finance_metrics` portfolio totals by basis, by tier and by flagged / not flagged, with coverage and a separate policy bucket. Sensitivity keys are strings ("1.0", "0.005"); the UI orders columns by the `cost_ratios` and `liquidity_premiums` lists, never by key order.
- **Finance tab (customer):** "Relationship contribution (estimate)" shows:
  - predicted risk and contribution at stake (3 months) side by side, never multiplied;
  - the monthly contribution with, only when each check is true, "Fee waiver condition not met" and "Fixed deposits don't cover waived transaction cost" beside it;
  - for a negative contribution, the sentence "Estimated relationship contribution is negative at the assumed cost; see cost sensitivity.";
  - the four components;
  - check A and check B as separate cards (policy exemptions labelled), never added;
  - the cost-ratio and liquidity-premium tables, one shared component, side by side, always open.
- **Overview:** "Revenue at Risk and fee subsidy leakage", between the flagged financial context and the queue:
  - FD-threshold tiers (SME_S, SME_M, CORP_L) and policy-exempt tiers (CORP_XL, GOV) as separate panels by default;
  - checks A and B in separate rows;
  - "The sign of these totals depends on both assumptions; both matter equally.";
  - both sensitivity tables, equally sized, with "All customers combined" as a secondary last row;
  - a secondary combined line, and a collapsed by-tier table.
- **Summary card (Finance section, render-8):** one server-written sentence, never sent to the provider, built from the flags:
  - positive: "Contribution at stake over May–Jul 2024: RM79.92 (estimated relationship contribution; waiver condition not met; fixed deposits don't cover waived transaction cost)." Only the checks that are true are listed;
  - negative: "Estimated relationship contribution is negative at the assumed cost; see cost sensitivity. (−RM X a month)." Each true check is appended inside the bracket;
  - POLICY_EXEMPT check-B results are not flagged on the card;
  - on the card, check A reads "waiver condition not met" (one word shorter, for the word budget); the UI keeps "Fee waiver condition not met".

## Card length

- 240 words is a **design target**, not a rejection rule. The count covers the deterministic card sections plus the template questions; AI link text and AI questions are excluded (they have their own limits).
- April 2024 (M6 Test, render-8): max **241** words on all 206 flagged cards and on all 1,000 cards (customer 72 is the only card at 241; it was 240 under render-7). The one-word growth is the approved "fixed deposits" wording; nothing was shortened to compensate. Min / median: 203 / 217 (flagged), 195 / 214 (all).
- The theoretical worst case is **264** words (263 under render-7). It needs a combination not present in the data: a year-spanning period, flagged, every Operations and Finance fact present and notable, a negative contribution with checks A and B both true, the three longest driver labels and a friction driver. The same combination was 262 under the stage-1 sentence. It is pinned at 264 and by a ceiling guard at 270 (`test_longest_theoretical_card_stays_under_its_ceiling_guard`).
