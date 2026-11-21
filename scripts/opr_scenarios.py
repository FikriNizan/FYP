"""Milestone 7: OPR shock drift demonstration (assumption-based synthetic stress scenarios).

Run with the modelling Python (catboost, pandas, numpy), never the app .venv:

    & $env:TXB_MODEL_PYTHON -I -B scripts\\opr_scenarios.py --research-root <R> --test-db artifacts\\m6-review.sqlite --out artifacts\\m7-scenarios\\m7-opr-1

What it does, in order (any failed gate stops the run and nothing is written):
1. Records a listing (path, size, mtime) of the read-only research folder.
2. Reads the April 2024 prepared features, the account snapshots and the saved April scores
   (the Test database is opened read-only).
3. Parity gate: the 11 account-derived predictors recomputed from the unperturbed snapshots must equal
   the saved April features exactly (nulls included).
4. Reproduction gate: the frozen champion (loaded read-only, sha256 checked) scores the unshocked April
   features; raw and calibrated scores must match the saved ones within 1e-12 and flags exactly.
5. Applies each scenario of the assumption register to an in-memory copy of the FD snapshot rows,
   recomputes the 11 predictors, scores the shocked copy (no SHAP) and measures PSI/KS.
6. Checks the research listing is unchanged, then writes the package to a NEW folder:
   manifest.json, scores.csv (scenario output only), drift.json.

Scenario scores are hypothetical. They never enter a predictions table or any database.
"""
import argparse
import csv
import hashlib
import importlib.util
import io
import json
import math
import os
import random
import sqlite3
import sys
from pathlib import Path

sys.dont_write_bytecode = True  # Never write __pycache__ into the read-only research folder.

ROOT = Path(__file__).resolve().parents[1]
VERSION = 'm7-opr-1'
SEED = 20240430
CUTOFF = '2024-04-30'
CHAMPION_FILE = 'catboost_baseline_final.joblib'
CHAMPION_SHA256 = '3d31eb0cfc36c2a8bb7fb072f9a63664ae2c3a940552c53c0f58ba94394346ec'
PROTOCOL_SHA256 = '6ae6d17ef0dcb7c3b0b7e090bed0dbae475024f5c0606f71ad100411adb5a4dc'
RAW_BOUNDARY = 0.2991379097436803
TOLERANCE = 1e-12
BNM_SOURCE = 'https://www.bnm.gov.my/monetary-stability/opr-decisions'

# Assumption register (owner-approved). Values are illustrative assumptions, fixed before any result was seen.
REGISTER = dict(
    version=VERSION, seed=SEED, cutoff=CUTOFF, direction='hike',
    effective_date='2024-02-01', lag_months=1, repricing_from='2024-03-01', window_end=CUTOFF,
    own_pass_through=0.5, competitor_pass_through=1.0,
    cohort='customers with an active FD in the 31 Jan 2024 snapshot (before the shock)',
    renewal_rule='an FD reprices or closes only at a maturity date (shown in the Jan 2024 snapshot) between 1 Mar and 30 Apr 2024; '
                 'no early withdrawal is assumed',
    migrant_rule='each FD of a migrating customer that matures in the window is closed from its maturity (status CLOSED, balances 0)',
    non_migrant_rule='each FD of other customers that matures in the window renews at its offer rate + own pass-through x shock',
    transaction_response='off: collections, payments, digital and friction inputs are unchanged by assumption',
    fees_and_waivers='unchanged',
    sources=dict(opr_decisions=BNM_SOURCE,
                 mps=['https://www.bnm.gov.my/-/monetary-policy-statement-05052020',
                      'https://www.bnm.gov.my/-/monetary-policy-statement-11052022',
                      'https://www.bnm.gov.my/-/monetary-policy-statement-03052023']),
    scenarios=[dict(id='no_shock', label='No shock', shock_bp=0, migrating_share=0.0),
               dict(id='mild', label='Mild', shock_bp=25, migrating_share=0.05),
               dict(id='severe', label='Severe', shock_bp=125, migrating_share=0.20)],
)
ACCOUNT_FEATURES = ['active_account_count', 'active_fd_count', 'closed_fd_count', 'fd_maturing_30d_count',
                    'fd_balance_myr', 'fd_average_balance_myr', 'non_fd_balance_myr', 'fd_balance_mean_3m_myr',
                    'fd_balance_mean_12m_myr', 'fd_balance_change_3m_vs_previous_3m', 'fd_balance_weighted_offer_rate']
ACCOUNT_COLUMNS = ['cus_id', 'acc_no', 'snapshot_month_clean', 'account_type', 'account_status_id',
                   'ledger_amount', 'average_amount', 'rate_offer', 'maturity_date_clean']
# Full history from the coverage start, as in the feature pipeline: pandas rolling means carry floating-point
# state along the series, so a shorter history differs in the last bits (up to 1.5e-8) and fails exact parity.
FIRST_MONTH = '2020-01-31'


def load_drift():
    spec = importlib.util.spec_from_file_location('drift', ROOT / 'backend' / 'churn_backend' / 'drift.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


drift = load_drift()


def need(condition, message):
    if not condition:
        raise SystemExit('STOPPED: ' + message)


def sha256_file(path):
    digest = hashlib.sha256()
    with open(path, 'rb') as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b''):
            digest.update(chunk)
    return digest.hexdigest()


def listing(folder):
    """Read-only fingerprint of every file's relative path, size and mtime under the research folder."""
    digest, count = hashlib.sha256(), 0
    for root, dirs, files in os.walk(folder):
        dirs.sort()
        for name in sorted(files):
            path = os.path.join(root, name)
            stat = os.stat(path)
            digest.update(f'{os.path.relpath(path, folder)}|{stat.st_size}|{stat.st_mtime_ns}\n'.encode())
            count += 1
    return dict(sha256=digest.hexdigest(), files=count)


# ---------- Account-derived predictors: mirrors feature_engineering_v1.py L231-246, L252-258, L351-365, L391.

def account_features(accounts, customers):
    """The 11 account-derived predictors at the April cutoff from month-end account snapshots."""
    import numpy as np
    import pandas as pd
    month = pd.to_datetime(accounts['snapshot_month_clean'], errors='raise')
    fd = accounts['account_type'].eq('FIXED_DEPOSIT')
    active = accounts['account_status_id'].eq('ACTIVE')
    fd_active = fd & active
    ledger = (pd.to_numeric(accounts['ledger_amount'], errors='raise') * 100).round().astype('int64')
    average = (pd.to_numeric(accounts['average_amount'], errors='raise') * 100).round().astype('int64')
    maturity = pd.to_datetime(accounts['maturity_date_clean'], errors='raise')
    rate_units = (pd.to_numeric(accounts['rate_offer']).fillna(0) * 1_000_000).round().astype('int64')
    sums = pd.DataFrame({
        'cus_id': accounts['cus_id'].to_numpy(), 'month': month.dt.to_period('M').dt.to_timestamp('M').to_numpy(),
        'active_account_count': active.astype(int).to_numpy(),
        'active_fd_count': fd_active.astype(int).to_numpy(),
        'closed_fd_count': (fd & ~active).astype(int).to_numpy(),
        'fd_balance_cents': (ledger * fd_active).to_numpy(),
        'fd_average_balance_cents': (average * fd_active).to_numpy(),
        'non_fd_balance_cents': (ledger * (~fd & active)).to_numpy(),
        'fd_rate_weighted_units': (ledger * fd_active * rate_units).to_numpy(),
        'fd_maturing_30d_count': (fd_active & maturity.ge(month) & maturity.le(month + pd.Timedelta(days=30))).astype(int).to_numpy(),
    }).groupby(['cus_id', 'month']).sum()
    months = pd.date_range(FIRST_MONTH, CUTOFF, freq='ME')
    grid = pd.MultiIndex.from_product([sorted(customers), months], names=['cus_id', 'month'])
    sums = sums.reindex(grid, fill_value=0).astype('int64')  # A month without rows sums to zero, as in the accumulator.

    def rolling(series, window):
        return series.groupby(level='cus_id', sort=False).transform(lambda v: v.rolling(window, min_periods=window).mean())

    def safe_ratio(numerator, denominator):
        return numerator / denominator.where(denominator.gt(0))

    fd_value = sums['fd_balance_cents'] / 100
    recent = rolling(fd_value, 3)
    out = pd.DataFrame({
        'active_account_count': sums['active_account_count'], 'active_fd_count': sums['active_fd_count'],
        'closed_fd_count': sums['closed_fd_count'], 'fd_maturing_30d_count': sums['fd_maturing_30d_count'],
        'fd_balance_myr': sums['fd_balance_cents'] / 100, 'fd_average_balance_myr': sums['fd_average_balance_cents'] / 100,
        'non_fd_balance_myr': sums['non_fd_balance_cents'] / 100,
        'fd_balance_mean_3m_myr': rolling(fd_value, 3), 'fd_balance_mean_12m_myr': rolling(fd_value, 12),
        'fd_balance_change_3m_vs_previous_3m': safe_ratio(recent, recent.groupby(level='cus_id', sort=False).shift(3)) - 1,
        'fd_balance_weighted_offer_rate': safe_ratio(sums['fd_rate_weighted_units'], sums['fd_balance_cents']) / 1_000_000,
    })
    at_cutoff = out.xs(pd.Timestamp(CUTOFF), level='month').astype('float64').round(10)
    return at_cutoff.reindex(sorted(customers))[ACCOUNT_FEATURES]


# ---------- Inputs

def read_features(research_root):
    import pandas as pd
    folder = research_root / 'data' / 'milestone4' / 'prepared-2024-04'
    manifest = json.loads((folder / 'manifest.json').read_text(encoding='utf-8'))
    path = folder / 'features.csv'
    files = manifest.get('files') or {}
    recorded = (files.get('features.csv') or {}).get('sha256') if isinstance(files, dict) else None
    recorded = recorded or manifest.get('csv_sha256') or manifest.get('features_sha256')
    actual = sha256_file(path)
    need(recorded is None or recorded == actual, 'Prepared April features do not match their manifest checksum')
    header = next(csv.reader(io.StringIO(path.read_text(encoding='utf-8').splitlines()[0])))
    categories = ['tier_id', 'customer_type', 'sector_code']
    numeric = [c for c in header if c not in ('cus_id', 'cutoff_month', *categories)]
    frame = pd.read_csv(path, dtype={**{k: 'string' for k in ['cus_id', 'cutoff_month', *categories]},
                                     **{c: 'float64' for c in numeric}},
                        keep_default_na=False, na_values=[''], float_precision='round_trip')
    need(len(frame) == 1000 and frame.cutoff_month.eq(CUTOFF).all(), 'Expected 1,000 April 2024 feature rows')
    need(frame.cus_id.is_unique, 'Duplicate customers in the April features')
    return frame.set_index('cus_id', drop=False), dict(path=str(path.relative_to(research_root)), sha256=actual)


def read_accounts(research_root):
    import pandas as pd
    path = research_root / 'data' / 'final_v4_0_1' / 'cleaned' / 'account_metadata_clean.csv'
    frame = pd.read_csv(path, usecols=ACCOUNT_COLUMNS, dtype=str, keep_default_na=False, na_values=[''])
    month = pd.to_datetime(frame['snapshot_month_clean'])
    frame = frame[(month >= FIRST_MONTH) & (month <= CUTOFF)].reset_index(drop=True)
    return frame, dict(path=str(path.relative_to(research_root)), sha256=sha256_file(path))


def read_saved_scores(test_db):
    connection = sqlite3.connect(f'file:{Path(test_db).resolve().as_posix()}?mode=ro', uri=True)
    try:
        batch = connection.execute('SELECT batch_id FROM batches WHERE cutoff_month=?', (CUTOFF,)).fetchone()
        need(batch is not None, 'No April 2024 batch in the Test database')
        saved = {}
        for cus_id, risk, alert, evidence_json in connection.execute(
                'SELECT cus_id, risk, review_alert, evidence_json FROM predictions WHERE batch_id=?', (batch[0],)):
            evidence = json.loads(evidence_json)
            saved[cus_id] = dict(risk=risk, raw=evidence['raw_probability'], flag=int(alert))
        return batch[0], saved
    finally:
        connection.close()


def load_champion(research_root):
    models = research_root / 'data' / 'models'
    need(sha256_file(models / 'final_refit_v1' / CHAMPION_FILE) == CHAMPION_SHA256, 'Champion bundle sha256 differs')
    need(sha256_file(models / 'frozen_experiment_v1' / 'frozen_protocol.json') == PROTOCOL_SHA256, 'Protocol sha256 differs')
    sys.path.insert(0, str(research_root))
    try:
        from shap_explainability_v1 import load_context  # Verifies the refit, calibration map and frozen policy.
    finally:
        sys.path.remove(str(research_root))
    context = load_context(models / 'frozen_experiment_v1', models / 'final_refit_v1')
    need(context['protocol_sha256'] == PROTOCOL_SHA256, 'Loaded protocol differs')
    need(context['model'].raw_boundary == RAW_BOUNDARY, 'Raw boundary differs from the frozen policy')
    return context


def score(context, frame):
    """Raw probability, calibrated risk and flag from the frozen model. No SHAP."""
    model, predictors = context['model'], context['predictors']
    raw = [float(v) for v in model.raw_probability(frame[predictors])]
    risk = [float(v) for v in model.predict_proba(frame[predictors])[:, 1]]
    return raw, risk, [int(r >= model.raw_boundary) for r in raw]


# ---------- Scenarios

def jan_maturities(accounts):
    """FD accounts active on 31 Jan 2024 and the maturity date that snapshot shows (pre-shock contract date)."""
    jan = accounts[accounts.snapshot_month_clean.str.startswith('2024-01-31') & accounts.account_type.eq('FIXED_DEPOSIT')
                   & accounts.account_status_id.eq('ACTIVE')]
    return {row.acc_no: (row.cus_id, row.maturity_date_clean[:10]) for row in jan.itertuples()}


def apply_scenario(accounts, scenario, migrants, maturities):
    """In-memory copy with the register applied; returns the copy and counts. Rows outside Feb-Apr 2024 are untouched."""
    import pandas as pd
    shocked = accounts.copy()
    shock = scenario['shock_bp'] / 10_000
    window = {acc: (cus, maturity) for acc, (cus, maturity) in maturities.items()
              if REGISTER['repricing_from'] <= maturity <= REGISTER['window_end']}
    snapshot = shocked.snapshot_month_clean.str[:10]
    counts = dict(fds_maturing_in_window=len(window), fds_closed=0, fds_repriced=0, migrants_with_closures=0)
    if shock == 0 and not migrants:
        return shocked, counts
    closers = set()
    for acc, (cus, maturity) in sorted(window.items()):
        rows = shocked.acc_no.eq(acc) & snapshot.ge(maturity) & snapshot.le(CUTOFF) & shocked.account_type.eq('FIXED_DEPOSIT')
        if cus in migrants:
            shocked.loc[rows, ['account_status_id', 'ledger_amount', 'average_amount']] = ['CLOSED', '0', '0']
            counts['fds_closed'] += 1
            closers.add(cus)
        elif shock:
            rates = pd.to_numeric(shocked.loc[rows, 'rate_offer'])
            shocked.loc[rows, 'rate_offer'] = (rates + REGISTER['own_pass_through'] * shock).map(repr)
            counts['fds_repriced'] += 1
    counts['migrants_with_closures'] = len(closers)
    return shocked, counts


def migrant_order(cohort):
    """One seeded shuffle; mild migrants are the first 5% and severe the first 20% (nested by design)."""
    order = sorted(cohort)
    random.Random(SEED).shuffle(order)
    return order


CATEGORIES = ('tier_id', 'customer_type', 'sector_code')


def as_list(series, categorical=False):
    return [None if (v is None or (isinstance(v, float) and math.isnan(v)) or v is getattr(__import__('pandas'), 'NA'))
            else (str(v) if categorical else float(v)) for v in series]


def run(research_root, test_db, out):
    research_root, out = Path(research_root).resolve(), Path(out).resolve()
    need(not out.exists(), f'Output already exists: {out}')
    need(not str(out).startswith(str(research_root)), 'Output must be outside the research folder')
    before = listing(research_root)
    features, features_source = read_features(research_root)
    accounts, accounts_source = read_accounts(research_root)
    batch_id, saved = read_saved_scores(test_db)
    customers = sorted(features.index)
    need(sorted(saved) == customers, 'Saved April scores and features cover different customers')

    # Gate 1: exact parity of the mirrored predictors on unperturbed snapshots.
    mirrored = account_features(accounts, customers)
    mismatches = {}
    for name in ACCOUNT_FEATURES:
        left, right = as_list(mirrored[name]), as_list(features.loc[customers, name])
        mismatches[name] = sum(1 for a, b in zip(left, right) if a != b)
    need(not any(mismatches.values()), f'Parity gate failed: {mismatches}')

    # Gate 2: the frozen champion reproduces the saved April scores on the unshocked features.
    context = load_champion(research_root)
    raw, risk, flags = score(context, features.loc[customers])
    max_raw = max(abs(r - saved[c]['raw']) for r, c in zip(raw, customers))
    max_risk = max(abs(r - saved[c]['risk']) for r, c in zip(risk, customers))
    flag_mismatches = sum(1 for f, c in zip(flags, customers) if f != saved[c]['flag'])
    reproduction = dict(max_abs_raw_difference=max_raw, max_abs_risk_difference=max_risk, flag_mismatches=flag_mismatches,
                        saved_flagged=sum(saved[c]['flag'] for c in customers), tolerance=TOLERANCE)
    need(max_raw <= TOLERANCE and max_risk <= TOLERANCE and flag_mismatches == 0, f'Reproduction gate failed: {reproduction}')

    maturities = jan_maturities(accounts)
    cohort = sorted({cus for cus, _ in maturities.values()})
    order = migrant_order(cohort)
    reference = {name: as_list(features.loc[customers, name], name in CATEGORIES)
                 for name in features.columns if name not in ('cus_id', 'cutoff_month')}
    saved_risk = [saved[c]['risk'] for c in customers]
    saved_flags = [saved[c]['flag'] for c in customers]
    rows, results = [], []
    for scenario in REGISTER['scenarios']:
        migrants = set(order[:round(scenario['migrating_share'] * len(cohort))])
        shocked_accounts, counts = apply_scenario(accounts, scenario, migrants, maturities)
        shocked = features.loc[customers].copy()
        recomputed = account_features(shocked_accounts, customers)
        for name in ACCOUNT_FEATURES:
            shocked[name] = recomputed[name].to_numpy()
        s_raw, s_risk, s_flags = score(context, shocked)
        current = {name: as_list(shocked[name], name in CATEGORIES) for name in reference}
        feature_drift = {name: drift.compare(reference[name], current[name], name in CATEGORIES) for name in reference}
        flagged_saved = [i for i, f in enumerate(saved_flags) if f]
        results.append(dict(
            id=scenario['id'], label=scenario['label'], shock_bp=scenario['shock_bp'], migrating_share=scenario['migrating_share'],
            cohort_size=len(cohort), migrants=len(migrants),
            april_fd_holders_among_migrants=sum(1 for c in migrants if (features.loc[c, 'fd_balance_myr'] or 0) > 0),
            **counts,
            input_drift=feature_drift,
            changed_features=sorted(n for n, d in feature_drift.items() if d['changed_values']),
            prediction_change=dict(
                risk=drift.compare(saved_risk, s_risk),
                crossed_into_review=sum(1 for a, b in zip(saved_flags, s_flags) if not a and b),
                crossed_out_of_review=sum(1 for a, b in zip(saved_flags, s_flags) if a and not b),
                flagged=sum(s_flags), saved_flagged=sum(saved_flags),
                mean_risk=sum(s_risk) / len(s_risk), saved_mean_risk=sum(saved_risk) / len(saved_risk),
                flagged_only=dict(customers=len(flagged_saved), still_flagged=sum(s_flags[i] for i in flagged_saved),
                                  risk=drift.compare([saved_risk[i] for i in flagged_saved], [s_risk[i] for i in flagged_saved]))),
            performance_change='Not computed: no outcomes exist under a hypothetical shock.'))
        for c, r, k, f in zip(customers, s_raw, s_risk, s_flags):
            rows.append([scenario['id'], c, repr(r), repr(k), f])

    after = listing(research_root)
    need(after == before, 'The research folder listing changed during the run')
    out.mkdir(parents=True)
    with (out / 'scores.csv').open('w', encoding='utf-8', newline='') as handle:
        writer = csv.writer(handle, lineterminator='\n')
        writer.writerow(['scenario', 'cus_id', 'scenario_raw_probability', 'scenario_calibrated_risk', 'scenario_review_alert'])
        writer.writerows(rows)
    drift_payload = dict(kind='txb_scenario_drift', version=VERSION, note='Scenario output only: hypothetical, not saved predictions.',
                         psi=dict(bins=drift.BINS, epsilon=drift.EPSILON, value_bin_limit=drift.VALUE_BIN_LIMIT,
                                  convention=list(drift.PSI_CONVENTION)),
                         scenarios=results)
    (out / 'drift.json').write_text(json.dumps(drift_payload, indent=1, sort_keys=True, allow_nan=False) + '\n', encoding='utf-8')
    manifest = dict(kind='txb_scenario_package', version=VERSION, register=REGISTER, batch_id=batch_id,
                    reference='Unshocked April 2024 features and the saved April scores',
                    gates=dict(parity=dict(features=ACCOUNT_FEATURES, mismatches=mismatches), reproduction=reproduction),
                    sources=dict(features=features_source, accounts=accounts_source,
                                 champion=dict(file=CHAMPION_FILE, sha256=CHAMPION_SHA256), protocol_sha256=PROTOCOL_SHA256),
                    research_listing=before,
                    files={name: sha256_file(out / name) for name in ('scores.csv', 'drift.json')})
    (out / 'manifest.json').write_text(json.dumps(manifest, indent=1, sort_keys=True, allow_nan=False) + '\n', encoding='utf-8')
    return manifest, results


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--research-root', required=True)
    parser.add_argument('--test-db', required=True, help='Test-session database (opened read-only)')
    parser.add_argument('--out', required=True, help='New folder, e.g. artifacts/m7-scenarios/m7-opr-1')
    args = parser.parse_args(argv)
    manifest, results = run(args.research_root, args.test_db, args.out)
    gates = manifest['gates']
    print('Parity gate: exact for', len(gates['parity']['features']), 'account-derived predictors')
    print('Reproduction gate:', json.dumps(gates['reproduction']))
    for r in results:
        p = r['prediction_change']
        print(f"{r['label']}: migrants {r['migrants']}/{r['cohort_size']} | FDs closed {r['fds_closed']} | repriced {r['fds_repriced']} | "
              f"changed inputs {len(r['changed_features'])} | score PSI {p['risk']['psi']:.6f} KS {p['risk']['ks']:.6f} | "
              f"into review {p['crossed_into_review']} out {p['crossed_out_of_review']} | flagged {p['flagged']} vs {p['saved_flagged']}")
    print('Package written:', args.out)
    return 0


if __name__ == '__main__':
    sys.exit(main())
