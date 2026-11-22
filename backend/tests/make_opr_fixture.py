"""Builds the shared, representative OPR scenario-package fixture (synthetic, internally consistent).

    python backend/tests/make_opr_fixture.py

Writes backend/tests/fixtures/opr_package/{manifest.json, drift.json, scores.csv} and the API payload that
the backend serves for it, frontend/tests/fixtures/opr-scenarios.json. The backend test checks that
GET /api/scenarios on the package returns exactly that JSON, so backend and frontend tests share one
renderable contract. Figures are synthetic; they are not results.
"""
import csv
import hashlib
import importlib.util
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PACKAGE = ROOT / 'backend' / 'tests' / 'fixtures' / 'opr_package'
FRONTEND = ROOT / 'frontend' / 'tests' / 'fixtures' / 'opr-scenarios.json'
sys.dont_write_bytecode = True
sys.path.insert(0, str(ROOT / 'backend'))
from churn_backend import create_app, drift, scenarios  # noqa: E402
from churn_backend.constants import CATEGORIES, PREDICTORS  # noqa: E402

spec = importlib.util.spec_from_file_location('opr_scenarios', ROOT / 'scripts' / 'opr_scenarios.py')
opr = importlib.util.module_from_spec(spec)
spec.loader.exec_module(opr)

VERSION = 'fixture-opr'
CUSTOMERS = [f'F{i:02d}' for i in range(1, 9)]
SAVED_RISK = [0.05, 0.08, 0.12, 0.15, 0.22, 0.31, 0.44, 0.58]
SAVED_FLAGS = [0, 0, 0, 0, 0, 1, 1, 1]
SAVED_RAW = [r * 0.9 for r in SAVED_RISK]
# Per scenario: shocked deposit inputs and scores (synthetic). Mild changes one customer's score; severe two,
# and one severe customer loses all FD balances, so its weighted rate becomes undefined.
CHANGES = {
    'no_shock': dict(rate={}, balance={}, risk={}),
    'mild': dict(rate={'F02': 0.0326, 'F05': 0.0301}, balance={'F07': 0.0}, risk={'F07': 0.4412}),
    'severe': dict(rate={'F02': 0.0381, 'F05': 0.0356, 'F06': 0.0349}, balance={'F07': 0.0, 'F03': 0.0},
                   risk={'F07': 0.4431, 'F03': 0.1188}),
}
COUNTS = {
    'no_shock': dict(assigned_exit_customers=0, eligible_exit_customers=0, eligible_exit_fds=0, exit_affected_customers=0,
                     exit_affected_fds=0, repriced_customers=0, repriced_fds=0, cells_changed=0),
    'mild': dict(assigned_exit_customers=1, eligible_exit_customers=1, eligible_exit_fds=1, exit_affected_customers=1,
                 exit_affected_fds=1, repriced_customers=2, repriced_fds=3, cells_changed=7),
    'severe': dict(assigned_exit_customers=3, eligible_exit_customers=2, eligible_exit_fds=3, exit_affected_customers=2,
                   exit_affected_fds=2, repriced_customers=3, repriced_fds=3, cells_changed=12),
}


def reference_values():
    values = {}
    for index, name in enumerate(PREDICTORS):
        if name in CATEGORIES:
            values[name] = ['SME_S' if i % 2 else 'CORP_L' for i in range(len(CUSTOMERS))] if name == 'tier_id' else ['A'] * len(CUSTOMERS)
        elif name == 'fd_balance_weighted_offer_rate':
            values[name] = [None, 0.03, 0.031, None, 0.029, 0.03, 0.032, None]
        elif name == 'fd_balance_myr':
            values[name] = [0.0, 50000.0, 20000.0, 0.0, 90000.0, 150000.0, 60000.0, 0.0]
        else:
            values[name] = [float(index + i) for i in range(len(CUSTOMERS))]
    return values


def build():
    reference = reference_values()
    results, rows = [], []
    for spec_ in opr.REGISTER['scenarios']:
        sid = spec_['id']
        current = {name: list(v) for name, v in reference.items()}
        for cus, rate in CHANGES[sid]['rate'].items():
            current['fd_balance_weighted_offer_rate'][CUSTOMERS.index(cus)] = rate
        for cus, balance in CHANGES[sid]['balance'].items():
            i = CUSTOMERS.index(cus)
            current['fd_balance_myr'][i] = balance
            current['fd_balance_weighted_offer_rate'][i] = None
            current['closed_fd_count'][i] = current['closed_fd_count'][i] + 1
        risk = list(SAVED_RISK)
        for cus, value in CHANGES[sid]['risk'].items():
            risk[CUSTOMERS.index(cus)] = value
        flags = [int(r >= 0.30) for r in risk]
        feature_drift = {name: drift.compare(reference[name], current[name], name in CATEGORIES) for name in PREDICTORS}
        flagged_saved = [i for i, f in enumerate(SAVED_FLAGS) if f]
        results.append(dict(
            id=sid, label=spec_['label'], shock_bp=spec_['shock_bp'], migrating_share=spec_['migrating_share'], cohort_size=6,
            april_fd_holders_among_assigned=COUNTS[sid]['assigned_exit_customers'], fds_maturing_in_window=5,
            fds_no_active_post_maturity=1, fds_missing_post_maturity_snapshots=0, fds_rate_missing=0, **COUNTS[sid],
            customers_score_changed=sum(1 for a, b in zip(SAVED_RISK, risk) if a != b),
            input_drift=feature_drift, changed_features=sorted(n for n, d in feature_drift.items() if d['changed_values']),
            prediction_change=dict(
                risk=drift.compare(SAVED_RISK, risk),
                crossed_into_review=sum(1 for a, b in zip(SAVED_FLAGS, flags) if not a and b),
                crossed_out_of_review=sum(1 for a, b in zip(SAVED_FLAGS, flags) if a and not b),
                flagged=sum(flags), saved_flagged=sum(SAVED_FLAGS), mean_risk=sum(risk) / len(risk),
                saved_mean_risk=sum(SAVED_RISK) / len(SAVED_RISK),
                flagged_only=dict(customers=len(flagged_saved), still_flagged=sum(flags[i] for i in flagged_saved),
                                  risk=drift.compare([SAVED_RISK[i] for i in flagged_saved], [risk[i] for i in flagged_saved]))),
            performance_change='Not computed: no outcomes exist under a hypothetical shock.'))
        for cus, raw, r, f in zip(CUSTOMERS, SAVED_RAW, risk, flags):
            rows.append([sid, cus, repr(raw), repr(r), f])
    PACKAGE.mkdir(parents=True, exist_ok=True)
    with (PACKAGE / 'scores.csv').open('w', encoding='utf-8', newline='') as handle:
        writer = csv.writer(handle, lineterminator='\n')
        writer.writerow(scenarios.SCORE_HEADER)
        writer.writerows(rows)
    payload = dict(kind='txb_scenario_drift', version=VERSION, note='Scenario output only: hypothetical, not saved predictions.',
                   psi=dict(bins=drift.BINS, epsilon=drift.EPSILON, value_bin_limit=drift.VALUE_BIN_LIMIT,
                            convention=list(drift.PSI_CONVENTION)), scenarios=results)
    (PACKAGE / 'drift.json').write_text(json.dumps(payload, indent=1, sort_keys=True, allow_nan=False) + '\n', encoding='utf-8', newline='\n')
    register = dict(opr.REGISTER, version=VERSION)
    manifest = dict(kind=scenarios.KIND, version=VERSION, register=register, batch_id='fixture-batch',
                    reference='Synthetic fixture: unshocked features and saved scores of 8 customers',
                    gates=dict(parity=dict(features=opr.ACCOUNT_FEATURES, mismatches={n: 0 for n in opr.ACCOUNT_FEATURES}),
                               reproduction=dict(max_abs_raw_difference=0.0, max_abs_risk_difference=0.0, flag_mismatches=0,
                                                 saved_flagged=sum(SAVED_FLAGS), tolerance=opr.TOLERANCE)),
                    files={name: hashlib.sha256((PACKAGE / name).read_bytes()).hexdigest() for name in scenarios.PACKAGE_FILES})
    (PACKAGE / 'manifest.json').write_text(json.dumps(manifest, indent=1, sort_keys=True, allow_nan=False) + '\n', encoding='utf-8', newline='\n')
    with tempfile.TemporaryDirectory() as temp:
        app = create_app(dict(TESTING=True, DATABASE=str(Path(temp) / 'fixture.sqlite'), TXB_SCENARIO_DIR=str(PACKAGE)))
        served = app.test_client().get('/api/scenarios').json  # Exactly what the API serves (empty database).
    FRONTEND.write_text(json.dumps(served, indent=1, sort_keys=True, allow_nan=False) + '\n', encoding='utf-8', newline='\n')
    return served


if __name__ == '__main__':
    print(build()['state'])
