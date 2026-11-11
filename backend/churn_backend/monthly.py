"""Validate ready monthly features, score outside SQLite, then publish atomically."""
import csv
import hashlib
import io
import json
import math
from pathlib import Path
import re
import subprocess
import tempfile
import threading
import time

from flask import current_app

from .constants import CATEGORIES, PREDICTORS, PROTOCOL_SHA256, SCHEMA
from . import repository as repo
from .validation import ValidationError, month_end, require, strict_json, validate_record

DIRECTORY = Path(__file__).resolve().parent
SCHEMA_SHA = hashlib.sha256((DIRECTORY/'feature_schema.json').read_bytes()).hexdigest()
CONTRACT = json.loads((DIRECTORY/'scorer_contract.json').read_text())
CSV_LIMIT = 5 * 1024 * 1024
MANIFEST_LIMIT = 64 * 1024
REQUEST_LIMIT = CSV_LIMIT + MANIFEST_LIMIT + 512 * 1024
_scoring_slot = threading.BoundedSemaphore(1)


class MonthlyError(Exception):
    def __init__(self, message, code='scoring_failed', status=503):
        super().__init__(message)
        self.code, self.status = code, status


def digest(data):
    return hashlib.sha256(data).hexdigest()


def validate_package(csv_bytes, manifest_bytes, expected_rows=1000):
    require(0 < len(csv_bytes) <= CSV_LIMIT, 'Select a non-empty feature CSV no larger than 5 MiB.')
    require(0 < len(manifest_bytes) <= MANIFEST_LIMIT, 'Select a companion JSON manifest no larger than 64 KiB.')
    try:
        manifest = strict_json(manifest_bytes.decode('utf-8-sig'))
        text = csv_bytes.decode('utf-8-sig')
    except UnicodeError as error:
        raise ValidationError('CSV and manifest must be UTF-8 text.') from error
    fields = {'kind','package_version','cutoff_month','row_count','predictor_count','feature_version',
              'feature_schema_sha256','protocol_sha256','files','source'}
    require(isinstance(manifest, dict) and set(manifest) == fields, 'Manifest fields must match the prepared-month contract, including source provenance.')
    try:
        json.dumps(manifest, allow_nan=False)
    except ValueError as error:
        raise ValidationError('Manifest numbers must be finite.') from error
    expected = dict(kind='txb_prepared_month', package_version='1.0.0', feature_version=SCHEMA['feature_version'],
                    feature_schema_sha256=SCHEMA_SHA, protocol_sha256=PROTOCOL_SHA256)
    for key, value in expected.items():
        require(manifest.get(key) == value, 'Manifest differs in '+key+'. Select a package prepared for the frozen application contract.')
    require(type(manifest['row_count']) is int and manifest['row_count'] == expected_rows,
            f'This server requires exactly {expected_rows} unique customers in one complete month.')
    require(type(manifest['predictor_count']) is int and manifest['predictor_count'] == len(PREDICTORS), 'Manifest predictor_count must be 78.')
    cutoff = month_end(manifest['cutoff_month'])
    require(isinstance(manifest['source'], dict), 'Manifest source provenance must be a JSON object.')
    require(isinstance(manifest['files'], dict) and set(manifest['files']) == {'features.csv'}, 'Manifest file ledger must describe features.csv only.')
    file = manifest['files']['features.csv']
    require(isinstance(file, dict) and set(file) == {'bytes','sha256'} and type(file['bytes']) is int,
            'Manifest features.csv needs bytes and sha256.')
    require(file['bytes'] == len(csv_bytes) and file['sha256'] == digest(csv_bytes),
            'Feature CSV checksum or byte length differs from the manifest. Select the matching original two files.')
    reader = csv.reader(io.StringIO(text, newline=''), strict=True)
    rows, seen = [], set()
    columns = SCHEMA['key_columns'] + PREDICTORS
    try:
        require(next(reader, None) == columns, 'CSV header must match the exact ordered two keys and 78 frozen predictors; labels, outcomes and scores are not accepted.')
        for index, values in enumerate(reader, 2):
            require(len(values) == len(columns), f'Malformed CSV data row {index}; expected 80 columns.')
            customer, stamp = values[:2]
            require(bool(re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,199}', customer)), f'Invalid customer ID at CSV row {index}. IDs must be non-blank, unpadded identifiers.')
            require(stamp == cutoff, 'Every CSV cutoff must equal the manifest month-end date; mixed months are not accepted.')
            require(customer not in seen, 'Repeated customer-month key in the CSV; submit one row per customer.')
            seen.add(customer)
            features = {}
            for name, value in zip(PREDICTORS, values[2:]):
                if name in CATEGORIES:
                    require(not any(ord(c) < 32 for c in value), f'Invalid categorical text in {name} at row {index}.')
                    features[name] = value if value != '' else None
                elif value == '':
                    features[name] = None
                else:
                    require(bool(re.fullmatch(r'[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?', value)), f'Invalid numeric text in {name} at row {index}.')
                    number = float(value)
                    require(math.isfinite(number), f'Non-finite numeric value in {name} at row {index}.')
                    features[name] = number
            usual = features['combined_flow_mean_12m_myr']
            require(usual is not None and usual > 0, 'Each customer requires a positive combined_flow_mean_12m_myr baseline.')
            rows.append(dict(cus_id=customer, cutoff_month=cutoff, features=features))
            require(len(rows) <= expected_rows, f'CSV exceeds the server population policy of {expected_rows} customers.')
    except csv.Error as error:
        raise ValidationError('Malformed CSV quoting or row structure.') from error
    require(len(rows) == expected_rows, 'CSV row count differs from the declared complete portfolio.')
    identity = digest(repo.encode(dict(csv_sha256=digest(csv_bytes), manifest_sha256=digest(manifest_bytes),
                    protocol_sha256=PROTOCOL_SHA256, champion_sha256=CONTRACT['champion_sha256'], schema_sha256=SCHEMA_SHA)).encode())
    return dict(manifest=manifest, rows=rows, cutoff_month=cutoff, identity=identity,
                csv_sha256=digest(csv_bytes), manifest_sha256=digest(manifest_bytes))


def existing(month, identity):
    rows = repo.get_db().execute('SELECT * FROM batches WHERE cutoff_month=?', (month,)).fetchall()
    if not rows:
        return None
    for row in rows:
        if row['source_kind'] == 'prepared_month_scored' and json.loads(row['source_json']).get('prepared_identity') == identity:
            return dict(batch_id=row['batch_id'], records=row['record_count'], already_imported=True, cutoff_month=month)
    raise MonthlyError('An assessment is already published for this cutoff. A different package cannot replace it.', 'assessment_conflict', 409)


def run_scorer(csv_bytes):
    root, python = current_app.config.get('TXB_RESEARCH_ROOT'), current_app.config.get('TXB_MODEL_PYTHON')
    if not root or not python:
        raise MonthlyError('Monthly scoring is not configured. Ask the administrator to configure the trusted research root and modelling Python.', 'scoring_unavailable')
    if not Path(root).is_dir() or not Path(python).is_file():
        raise MonthlyError('The configured scoring environment is unavailable. Ask the administrator to check the local model setup.', 'scoring_unavailable')
    timeout = current_app.config['TXB_SCORING_TIMEOUT_SECONDS']
    if not _scoring_slot.acquire(blocking=False):
        raise MonthlyError('Another monthly package is being processed. Wait for it to finish, then resubmit.', 'scoring_busy')
    try:
        with tempfile.TemporaryDirectory(prefix='txb-score-') as temporary:
            folder = Path(temporary)
            features, output = folder/'features.csv', folder/'result.json'
            features.write_bytes(csv_bytes)  # Exact received bytes, not a CSV rewrite.
            try:
                result = subprocess.run([str(python), '-I', str(DIRECTORY/'model_worker.py'),
                    '--research-root', str(Path(root).resolve()), '--features', str(features), '--output', str(output)],
                    cwd=folder, capture_output=True, timeout=timeout, check=False, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            except subprocess.TimeoutExpired as error:
                current_app.logger.warning('Monthly scorer exceeded its configured timeout')
                raise MonthlyError('Scoring timed out. No assessment was published; ask the administrator to check the modelling environment before retrying.', 'scoring_timeout', 504) from error
            except OSError as error:
                current_app.logger.exception('Monthly scorer could not start')
                raise MonthlyError('The scoring process could not start. No assessment was published.', 'scoring_unavailable') from error
            if result.returncode != 0:
                current_app.logger.error('Monthly scorer failed (exit %s): %s', result.returncode, result.stderr[-4000:].decode('utf-8', errors='replace'))
                raise MonthlyError('The saved model could not score or verify this package. No assessment was published; ask the administrator to inspect the local scoring log.')
            if not output.is_file() or output.stat().st_size > 16 * 1024 * 1024:
                raise MonthlyError('The scorer returned an incomplete result. No assessment was published.')
            try:
                return strict_json(output.read_text(encoding='utf-8'))
            except (UnicodeError, ValidationError) as error:
                current_app.logger.exception('Monthly scorer returned invalid JSON')
                raise MonthlyError('The scorer returned invalid evidence. No assessment was published.') from error
    finally:
        _scoring_slot.release()


def verify_output(package, output):
    require(isinstance(output, dict) and output.get('csv_sha256') == package['csv_sha256'], 'Scorer input identity differs.')
    require(output.get('champion_sha256') == CONTRACT['champion_sha256'] and output.get('protocol_sha256') == PROTOCOL_SHA256, 'Scorer champion/protocol differs.')
    records = output.get('records')
    require(isinstance(records, list) and len(records) == len(package['rows']), 'Scorer row count differs.')
    inputs = {r['cus_id']:r for r in package['rows']}
    entries, seen = [], set()
    for value in records:
        record = validate_record(value)
        customer = record['cus_id']
        require(customer in inputs and customer not in seen and record['cutoff_month'] == package['cutoff_month'], 'Scorer output keys differ from the submitted month.')
        seen.add(customer)
        features = inputs[customer]['features']
        for group in ['higher_risk_drivers','lower_risk_drivers']:
            require(len(record[group]) <= 5, 'Scorer must return top_k=5 model signals.')
            for driver in record[group]:
                actual, expected = driver['value'], features[driver['feature']]
                require(actual == expected, 'Scorer driver value differs from submitted features.')
        entries.append(dict(evidence=record, features=features, customer={}, flows=[]))
    return entries


def process(csv_bytes, manifest_bytes):
    start = time.perf_counter()
    package = validate_package(csv_bytes, manifest_bytes, current_app.config['TXB_MONTHLY_POPULATION'])
    validation_seconds = time.perf_counter() - start
    prior = existing(package['cutoff_month'], package['identity'])
    if prior:
        return dict(**prior, timings=dict(validation_seconds=validation_seconds, scoring_seconds=0, verification_seconds=0, publication_seconds=0))
    score_start = time.perf_counter()
    output = run_scorer(csv_bytes)
    scoring_seconds = time.perf_counter() - score_start
    verify_start = time.perf_counter()
    try:
        entries = verify_output(package, output)
    except (ValidationError, KeyError, TypeError, ValueError) as error:
        current_app.logger.exception('Monthly scorer output failed saved-evidence verification')
        raise MonthlyError('Scored evidence failed verification. No assessment was published; ask the administrator to inspect the local scoring log.') from error
    timings = dict(validation_seconds=validation_seconds, scoring_seconds=scoring_seconds,
                   verification_seconds=time.perf_counter()-verify_start)
    source = dict(prepared_identity=package['identity'], csv_sha256=package['csv_sha256'], manifest_sha256=package['manifest_sha256'],
                  package_version='1.0.0', feature_version=SCHEMA['feature_version'], feature_schema_sha256=SCHEMA_SHA,
                  champion_sha256=CONTRACT['champion_sha256'], protocol_sha256=PROTOCOL_SHA256,
                  prepared_manifest=package['manifest'], scorer=output.get('provenance', {}),
                  customer_names_loaded=False, flow_history_loaded=False, timings=timings)
    publish_start = time.perf_counter()
    result = repo.publish_prepared(package['cutoff_month'], entries, source)
    publication_seconds = time.perf_counter()-publish_start
    if not result['already_imported']:
        from . import enrichment
        enrichment_start = time.perf_counter()
        try:
            supplement = enrichment.apply(result['batch_id'],dry_run=False)
            result['enrichment'] = dict(status='available',coverage=supplement['coverage'])
        except (ValidationError, OSError, ValueError) as error:
            current_app.logger.warning('Optional monthly enrichment was unavailable or invalid: %s',error)
            result['enrichment'] = dict(status='unavailable',message='Supporting names or flows could not be accepted. The scored assessment remains published; ask the administrator to inspect the local log and run the batch enrichment preview.')
        enrichment_seconds=time.perf_counter()-enrichment_start
    else:
        enrichment_seconds=0
    return dict(**result, timings={**timings, 'publication_seconds':publication_seconds,
                                   'enrichment_seconds':enrichment_seconds})
