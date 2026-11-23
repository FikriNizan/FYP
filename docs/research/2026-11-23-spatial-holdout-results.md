# Spatial (customer-holdout) test: results

Plan: `2026-11-23-spatial-holdout-predeclaration.md` (commit 4548232), fixed before this run. Run on 23 Nov 2026 in `fyp-model-env` (CatBoost 1.2.8), 8.4 minutes, notebook executed without errors. Research folder listing unchanged. Full outputs: `Project Module (FYP)\4.0 FYP Research and Finding\15 Spatial holdout test\results\`.

**Reproduction gate:** passed exactly. The recipe rebuilt on all 1,000 customers matched the saved champion on all 12,000 test rows (maximum raw-probability difference 0.0; 0 flag mismatches).

**Design:** 5 customer folds stratified by tier (seed 20261123; 200 customers each). Each fold trained the unchanged recipe on 800 customers and scored the 200 unseen customers' final-test months (Oct 2023 – Sep 2024). 1,000-replicate paired customer bootstrap.

| Metric | Champion (saw customers) | Unseen customers | Δ (unseen − champion) | 95% interval |
|---|---:|---:|---:|---|
| Average precision (primary) | 0.4066 | 0.4164 | +0.0098 | −0.0023 to +0.0223 |
| ROC-AUC (primary) | 0.7953 | 0.7943 | −0.0010 | −0.0046 to +0.0028 |
| Precision | 0.3938 | 0.3986 | +0.0048 | −0.0053 to +0.0157 |
| Recall | 0.5162 | 0.5059 | −0.0102 | −0.0263 to +0.0072 |
| F1 | 0.4467 | 0.4459 | −0.0009 | −0.0118 to +0.0118 |
| Brier | 0.1099 | 0.1096 | −0.0002 | −0.0011 to +0.0006 |

**Verdict (pre-declared rule):** No detectable degradation on unseen customers. Both primary intervals include zero.

Descriptive breakdowns (no decision attached): ΔAP by fold +0.024, +0.018, −0.018, +0.010, +0.013. By tier: CORP_L +0.026, SME_M +0.008, SME_S +0.004, CORP_XL −0.008, GOV −0.066 (GOV: 22 positives in 480 rows, too few to interpret).

The champion, its threshold, saved predictions, SHAP and the app are unchanged.
