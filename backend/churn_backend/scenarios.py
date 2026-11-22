"""Read-only access to the Milestone 7 OPR scenario package (artifacts/m7-scenarios/<version>/).

The package is produced offline by scripts/opr_scenarios.py in the modelling environment. This module
never writes anything and never touches a database: scenario scores are hypothetical and are not
saved predictions. On every read the manifest's file hashes are checked and the full package
contract is validated (types, scenario ids, predictor keys, finite numbers, bounds, consistent counts,
gates and scores coverage) before the state is 'ready'. Anything malformed is 'invalid'.
"""
import csv
import hashlib
import io
import json
import math
from pathlib import Path
from flask import current_app
from .constants import CATEGORIES, PREDICTORS
from .validation import ValidationError, require

KIND = 'txb_scenario_package'
PACKAGE_FILES = ('scores.csv', 'drift.json')
SCENARIO_IDS = ('no_shock', 'mild', 'severe')
SCORE_HEADER = ['scenario', 'cus_id', 'scenario_raw_probability', 'scenario_calibrated_risk', 'scenario_review_alert']
COUNT_FIELDS = ('cohort_size', 'fds_maturing_in_window', 'assigned_exit_customers', 'eligible_exit_customers', 'eligible_exit_fds',
                'exit_affected_customers', 'exit_affected_fds', 'repriced_customers', 'repriced_fds',
                'fds_no_active_post_maturity', 'fds_missing_post_maturity_snapshots', 'fds_rate_missing', 'cells_changed',
                'customers_score_changed', 'april_fd_holders_among_assigned')
NOTE = ('This scenario changes deposit-related inputs only. Transaction activity, digital engagement and service-friction '
        'input values are held constant. Scenario-specific SHAP explanations are not computed.')


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def package_dir():
    configured = current_app.config.get('TXB_SCENARIO_DIR')
    return Path(configured) if configured else None


def is_int(value):
    return isinstance(value, int) and not isinstance(value, bool)


def is_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def count(value, label):
    require(is_int(value) and value >= 0, f'{label} must be a non-negative whole number')
    return value


def unit(value, label, optional=False):
    if optional and value is None:
        return value
    require(is_number(value) and 0 <= value <= 1, f'{label} must be a finite number between 0 and 1')
    return value


def mapping(value, label):
    require(isinstance(value, dict), f'{label} must be an object')
    return value


def text(value, label):
    require(isinstance(value, str) and value.strip() != '', f'{label} must be text')
    return value


def comparison(entry, label, customers, categorical=False):
    mapping(entry, label)
    require(is_number(entry.get('psi')) and entry['psi'] >= 0, f'{label} PSI must be finite and non-negative')
    if categorical:
        require(entry.get('ks') is None, f'{label} KS must be absent for a category')
    else:
        unit(entry.get('ks'), f'{label} KS', optional=True)
    text(entry.get('reading'), f'{label} reading')
    for side in ('reference', 'current'):
        share = unit(entry.get('null_share_' + side), f'{label} missing share', optional=True)
        available = count(entry.get(side + '_available'), f'{label} available count')
        require(available <= customers, f'{label} available count exceeds the customers')
        require(share is None or abs(share * customers + available - customers) < 1e-6, f'{label} coverage does not reconcile')
    require(count(entry.get('changed_values'), f'{label} changed values') <= customers, f'{label} changed values exceed the customers')
    return entry


def check_gates(gates):
    mapping(gates, 'gates')
    parity, reproduction = mapping(gates.get('parity'), 'parity gate'), mapping(gates.get('reproduction'), 'reproduction gate')
    features = parity.get('features')
    require(isinstance(features, list) and features and all(name in PREDICTORS for name in features), 'Parity features are invalid')
    mismatches = mapping(parity.get('mismatches'), 'parity mismatches')
    require(sorted(mismatches) == sorted(features) and all(count(v, 'parity mismatch') == 0 for v in mismatches.values()),
            'Scenario package parity gate did not pass')
    tolerance = reproduction.get('tolerance')
    require(is_number(tolerance) and 0 < tolerance <= 1e-9, 'Reproduction tolerance is invalid')
    for key in ('max_abs_raw_difference', 'max_abs_risk_difference'):
        require(is_number(reproduction.get(key)) and 0 <= reproduction[key] <= tolerance, 'Scenario package reproduction gate did not pass')
    require(count(reproduction.get('flag_mismatches'), 'flag mismatches') == 0, 'Scenario package reproduction gate did not pass')
    count(reproduction.get('saved_flagged'), 'saved flagged')


def check_register(register, scenarios):
    mapping(register, 'register')
    listed = register.get('scenarios')
    require(isinstance(listed, list) and [mapping(s, 'register scenario').get('id') for s in listed] == list(SCENARIO_IDS),
            'Register scenarios are incomplete')
    for entry, scenario in zip(listed, scenarios):
        require(entry.get('shock_bp') == scenario['shock_bp'] and entry.get('migrating_share') == scenario['migrating_share'],
                'Register and scenario assumptions differ')
    for key in ('own_pass_through', 'competitor_pass_through'):
        unit(register.get(key), key)
    count(register.get('lag_months'), 'lag months')
    for key in ('effective_date', 'repricing_from', 'window_end', 'cohort', 'renewal_rule', 'migrant_rule', 'non_migrant_rule',
                'transaction_response', 'fees_and_waivers', 'version', 'pass_through_note', 'competitor_pass_through_use'):
        text(register.get(key), key)
    count(register.get('seed'), 'seed')
    text(mapping(register.get('sources'), 'sources').get('opr_decisions'), 'OPR decisions source')


def check_scenario(scenario, expected_id, customers):
    mapping(scenario, 'scenario')
    require(scenario.get('id') == expected_id, 'Scenario ids are not no_shock, mild, severe in order')
    text(scenario.get('label'), 'scenario label')
    count(scenario.get('shock_bp'), 'shock')
    unit(scenario.get('migrating_share'), 'migrating share')
    values = {key: count(scenario.get(key), key) for key in COUNT_FIELDS}
    require(values['assigned_exit_customers'] >= values['eligible_exit_customers'] >= values['exit_affected_customers']
            and values['eligible_exit_fds'] >= values['exit_affected_fds']
            and values['fds_maturing_in_window'] >= values['exit_affected_fds'] + values['repriced_fds']
            and values['repriced_fds'] >= values['repriced_customers']
            and values['cohort_size'] >= values['assigned_exit_customers'] >= values['april_fd_holders_among_assigned']
            and values['customers_score_changed'] <= customers, 'Scenario counts are inconsistent')
    drift = mapping(scenario.get('input_drift'), 'input drift')
    require(sorted(drift) == sorted(PREDICTORS), 'Input drift must cover exactly the 78 predictors')
    for name, entry in drift.items():
        comparison(entry, name, customers, name in CATEGORIES)
    changed = scenario.get('changed_features')
    require(isinstance(changed, list) and changed == sorted(n for n, d in drift.items() if d['changed_values']),
            'Changed features do not match the input drift')
    change = mapping(scenario.get('prediction_change'), 'prediction change')
    comparison(change.get('risk'), 'score', customers)
    require(change['risk']['reference_available'] == customers, 'Score coverage differs from the customers')
    for key in ('crossed_into_review', 'crossed_out_of_review', 'flagged', 'saved_flagged'):
        require(count(change.get(key), key) <= customers, f'{key} exceeds the customers')
    unit(change.get('mean_risk'), 'mean risk')
    unit(change.get('saved_mean_risk'), 'saved mean risk')
    require(change['flagged'] == change['saved_flagged'] + change['crossed_into_review'] - change['crossed_out_of_review'],
            'Flagged count does not reconcile with review crossings')
    only = mapping(change.get('flagged_only'), 'flagged-only view')
    require(count(only.get('customers'), 'flagged customers') == change['saved_flagged']
            and count(only.get('still_flagged'), 'still flagged') <= only['customers'], 'Flagged-only view is inconsistent')
    comparison(only.get('risk'), 'flagged-only score', only['customers'])
    if expected_id == 'no_shock':
        require(not changed and values['cells_changed'] == 0 and values['customers_score_changed'] == 0
                and change['crossed_into_review'] == change['crossed_out_of_review'] == 0, 'The no-shock reference must not change')
    return change['flagged']


def check_scores(raw, scenarios, customers):
    rows = list(csv.reader(io.StringIO(raw.decode('utf-8'))))
    require(rows and rows[0] == SCORE_HEADER, 'Scenario scores header differs from the contract')
    body = rows[1:]
    require(len(body) == len(SCENARIO_IDS) * customers, 'Scenario scores do not cover every scenario and customer')
    seen, members, flagged = set(), {s: set() for s in SCENARIO_IDS}, {s: 0 for s in SCENARIO_IDS}
    for row in body:
        require(len(row) == 5 and row[0] in members, 'Malformed scenario score row')
        key = (row[0], row[1])
        require(row[1] and key not in seen, 'Duplicate scenario score row')
        seen.add(key)
        members[row[0]].add(row[1])
        try:
            values = float(row[2]), float(row[3])
        except ValueError:
            raise ValidationError('Scenario scores must be numbers') from None
        require(all(math.isfinite(v) and 0 <= v <= 1 for v in values) and row[4] in ('0', '1'), 'Scenario score out of range')
        flagged[row[0]] += row[4] == '1'
    require(len({frozenset(m) for m in members.values()}) == 1, 'Scenarios cover different customers')
    for scenario_id, expected in scenarios.items():
        require(flagged[scenario_id] == expected, 'Scenario flagged count does not match its scores')


def load():
    """Returns the scenario summary for the UI, or a not-generated state. Raises on a malformed or tampered package."""
    folder = package_dir()
    if folder is None or not (folder / 'manifest.json').is_file():
        return dict(state='not_generated')
    manifest = mapping(json.loads((folder / 'manifest.json').read_text(encoding='utf-8')), 'manifest')
    require(manifest.get('kind') == KIND, 'Not a scenario package')
    files = mapping(manifest.get('files'), 'manifest files')
    require(sorted(files) == sorted(PACKAGE_FILES), 'Manifest files differ from the contract')
    for name in PACKAGE_FILES:
        require((folder / name).is_file() and files[name] == digest(folder / name), 'Scenario package file does not match its manifest')
    payload = mapping(json.loads((folder / 'drift.json').read_text(encoding='utf-8')), 'drift')
    version = text(manifest.get('version'), 'version')
    require(payload.get('kind') == 'txb_scenario_drift' and payload.get('version') == version, 'Scenario package versions differ')
    psi = mapping(payload.get('psi'), 'PSI settings')
    require(count(psi.get('bins'), 'bins') > 0 and is_number(psi.get('epsilon')) and psi['epsilon'] > 0
            and count(psi.get('value_bin_limit'), 'value bin limit') > 0 and psi.get('convention') == [0.10, 0.25],
            'PSI settings are invalid')
    scenarios = payload.get('scenarios')
    require(isinstance(scenarios, list) and len(scenarios) == len(SCENARIO_IDS), 'Scenario list is incomplete')
    first_change = mapping(mapping(scenarios[0], 'scenario').get('prediction_change'), 'prediction change')
    customers = count(mapping(first_change.get('risk'), 'score comparison').get('reference_available'), 'customers')
    require(customers > 0, 'Scenario package has no customers')
    flagged = {expected: check_scenario(s, expected, customers) for s, expected in zip(scenarios, SCENARIO_IDS)}
    check_gates(manifest.get('gates'))
    require(all(s['prediction_change']['saved_flagged'] == manifest['gates']['reproduction']['saved_flagged'] for s in scenarios),
            'Saved flagged count differs from the reproduction gate')
    check_register(manifest.get('register'), scenarios)
    require(manifest['register']['version'] == version, 'Register version differs')
    text(manifest.get('reference'), 'reference')
    check_scores((folder / 'scores.csv').read_bytes(), flagged, customers)
    from . import ai_render  # Plain input names, the same labels the summary card uses.
    # batch_id names the saved assessment the package stressed; the API layer resolves its month (this module never
    # touches a database).
    return dict(state='ready', version=version, batch_id=text(manifest.get('batch_id'), 'batch_id'),
                register=manifest['register'], gates=manifest['gates'],
                reference=manifest['reference'], psi=psi, scenarios=scenarios, note=NOTE,
                feature_labels={name: ai_render.driver_name(name) for name in PREDICTORS},
                package_sha256=dict(manifest=digest(folder / 'manifest.json'), **files))


def safe_load():
    try:
        return load()
    except (ValidationError, ValueError, KeyError, OSError, AttributeError, TypeError, UnicodeError, IndexError):
        return dict(state='invalid')
