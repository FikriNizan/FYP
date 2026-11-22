# Spatial (customer-holdout) test: pre-specified analysis plan

**Status:** declared before any holdout model is trained or any result is seen.
**Date:** 23 November 2026. **Author:** Fikri. **Commit:** this file is committed to GitHub (FikriNizan/FYP, `docs/research/`) before the run; the commit timestamp is the evidence of order.

## 1. Question
Does the frozen champion's final-test performance depend on having seen the same customers' earlier history during training? In other words: does the champion recipe perform as well on customers it has never seen?

## 2. Why
The accepted design is a temporal split: all 1,000 customers appear in training, validation and final test, at different months. That controls temporal leakage, but not non-independence between training and test rows from the same customer (Kapoor & Narayanan, 2023, leakage types L3.1 and L3.2). Block cross-validation is recommended wherever data have such dependence structure (Roberts et al., 2017); grouped splitting keeps the same group out of both training and test (scikit-learn, GroupKFold). This test adds a customer block on top of the existing temporal block. It responds to the second marker's request for spatial-temporal block splitting; rolling-origin folds already exist in tuning (3 folds) and calibration (6 folds).

## 3. Fixed inputs (read-only, checksum-verified)
- Research folder `fyp-data-refinement`: `data/splits_v1` (development.csv and test.csv, verified against `split_manifest.json`), `data/models/frozen_experiment_v1/frozen_protocol.json`, `data/models/final_test_v1/predictions.csv`.
- Dataset `synthetic-v4-913683e11b47c203`; 78 predictors; target, IDs and cutoff excluded from X.
- Nothing in `fyp-data-refinement` is written. All outputs go to `4.0 FYP Research and Finding/15 Spatial holdout test/`.

## 4. Champion recipe (unchanged)
CatBoost baseline (iterations 100, learning rate 0.1, depth 6, l2_leaf_reg 3, random_seed 99, thread_count 2), the project's own pipeline code; development period Dec 2020 – Jun 2023; Platt sigmoid fitted on pooled predictions from the frozen six calibration folds; alert flag = raw probability ≥ 0.2991379097436803 (the frozen raw boundary). No parameter, threshold or feature is changed.

## 5. Reproduction gate (runs first)
Rebuild the recipe on all 1,000 customers' development rows and score the final test. Pass if, on all 12,000 test rows, the maximum absolute difference from the saved champion raw probability is ≤ 1e-6 and every flag matches. If the gate fails, the run stops for review. If it is then continued, the rebuilt model replaces the saved predictions as the reference, and the deviation is reported.

## 6. Customer folds
- 5 folds. Within each tier, customers are shuffled with seed **20261123** and dealt to folds in turn, so each fold holds 200 customers with the tier mix of the whole population.
- For each fold k: train the unchanged recipe (including its six-fold calibration) on the development rows of the other 800 customers only; score the final-test rows of the 200 held-out customers.
- Combining the 5 folds gives one "unseen-customer" prediction for each of the 12,000 final-test rows (Oct 2023 – Sep 2024).
- A fold stops the run if a calibration fold lacks both classes or the sigmoid is not increasing (the recipe's own checks).

## 7. Comparison
Same 12,000 rows, two predictions per row: **champion** (saved frozen predictions; the model saw each customer's development history) vs **unseen-customer** (the model never saw that customer).
- **Primary:** average precision (AP) and ROC-AUC. They depend only on ranking, so calibration does not affect them.
- **Secondary (descriptive):** precision, recall and F1 at the frozen raw boundary; Brier score of sigmoid probabilities; the same metrics per fold and per tier.
- **Difference:** Δ = unseen-customer − champion.

## 8. Uncertainty
Paired customer-level bootstrap: 1,000 replicates, seed **20261123**. Each replicate draws 1,000 customers with replacement, keeps all 12 test months of each drawn customer, and recomputes Δ. Report the observed Δ and the 2.5th and 97.5th percentiles (95% interval).

## 9. Decision rule (fixed now)
- If the 95% interval of Δ for **both** AP and ROC-AUC includes 0: "No detectable degradation on unseen customers."
- If the interval for either primary metric lies entirely below 0: "Performance partly depends on customers seen in training." Reported as a limitation, with the size of the drop.
- If an interval lies entirely above 0: reported as observed, with no further claim.
- The size of Δ is reported in every case, not only the verdict.

## 10. What this test cannot change
The champion, its threshold, the saved predictions, SHAP and the app stay frozen whatever the result. The test is a robustness check, not model selection. No seed, fold count, metric or rule is changed after results are seen; any unplanned extra analysis is labelled exploratory.

## References
- Kapoor, S., & Narayanan, A. (2023). Leakage and the reproducibility crisis in machine-learning-based science. *Patterns, 4*(9), 100804. https://doi.org/10.1016/j.patter.2023.100804
- Roberts, D. R., et al. (2017). Cross-validation strategies for data with temporal, spatial, hierarchical, or phylogenetic structure. *Ecography, 40*(8), 913–929. https://doi.org/10.1111/ecog.02881
- scikit-learn developers. Cross-validation: iterators for grouped data (GroupKFold).
