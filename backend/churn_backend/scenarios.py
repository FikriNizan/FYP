"""Read-only access to the Milestone 7 OPR scenario package (artifacts/m7-scenarios/<version>/).

The package is produced offline by scripts/opr_scenarios.py in the modelling environment. This module
never writes anything and never touches a database: scenario scores are hypothetical and are not
saved predictions. The manifest's file hashes are checked on every read.
"""
import hashlib
import json
from pathlib import Path
from flask import current_app
from .validation import ValidationError, require

KIND = 'txb_scenario_package'
PACKAGE_FILES = ('scores.csv', 'drift.json')
NOTE = ('This scenario changes deposit-related inputs only. Collections, payments, digital and friction inputs '
        "are unchanged by assumption, so the model's main drivers do not move.")


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def package_dir():
    configured = current_app.config.get('TXB_SCENARIO_DIR')
    return Path(configured) if configured else None


def load():
    """Returns the scenario summary for the UI, or a not-generated state. Raises on a tampered package."""
    folder = package_dir()
    if folder is None or not (folder / 'manifest.json').is_file():
        return dict(state='not_generated')
    manifest = json.loads((folder / 'manifest.json').read_text(encoding='utf-8'))
    require(manifest.get('kind') == KIND, 'Not a scenario package')
    for name in PACKAGE_FILES:
        require((folder / name).is_file() and manifest.get('files', {}).get(name) == digest(folder / name),
                'Scenario package file does not match its manifest')
    payload = json.loads((folder / 'drift.json').read_text(encoding='utf-8'))
    require(payload.get('version') == manifest.get('version'), 'Scenario package versions differ')
    gates = manifest['gates']
    require(not any(gates['parity']['mismatches'].values()) and gates['reproduction']['flag_mismatches'] == 0
            and gates['reproduction']['max_abs_raw_difference'] <= gates['reproduction']['tolerance']
            and gates['reproduction']['max_abs_risk_difference'] <= gates['reproduction']['tolerance'],
            'Scenario package gates did not pass')
    return dict(state='ready', version=manifest['version'], register=manifest['register'], gates=gates,
                reference=manifest['reference'], psi=payload['psi'], scenarios=payload['scenarios'], note=NOTE,
                package_sha256=dict(manifest=digest(folder / 'manifest.json'), **manifest['files']))


def safe_load():
    try:
        return load()
    except (ValidationError, ValueError, KeyError, OSError):
        return dict(state='invalid')
