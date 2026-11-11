"""Read-only post-publication comparison against archived row evidence, never inference."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import sqlite3
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'backend'))
from churn_backend.validation import validate_record


def compare(database, batch_id, reference, reference_manifest, verification, package_manifest):
    report = json.loads(Path(verification).read_text(encoding='utf-8'))
    manifest_bytes = Path(package_manifest).read_bytes()
    assert report['status'] == 'PASS'
    assert hashlib.sha256(manifest_bytes).hexdigest() == report['package_manifest_sha256'], 'Wrong offline package identity'
    package = json.loads(manifest_bytes)
    reference_bytes = Path(reference).read_bytes()
    assert hashlib.sha256(reference_bytes).hexdigest() == report['reference_explanations_sha256'], 'Wrong archived row reference identity'
    ledger = json.loads(Path(reference_manifest).read_text(encoding='utf-8'))
    assert ledger['files']['dashboard_explanations.jsonl']['sha256'] == report['reference_explanations_sha256']
    cutoff = package['cutoff_month']
    archived = {}
    for line in reference_bytes.decode('utf-8').splitlines():
        row = json.loads(line)
        if row['cutoff_month'] == cutoff:
            key = (row['cus_id'],row['cutoff_month'])
            assert key not in archived, 'Duplicate archived key'
            archived[key] = row
    with sqlite3.connect(Path(database).resolve().as_uri()+'?mode=ro',uri=True) as db:
        db.row_factory = sqlite3.Row
        batch = db.execute('SELECT * FROM batches WHERE batch_id=?',(batch_id,)).fetchone()
        assert batch and batch['source_kind'] == 'prepared_month_scored' and batch['cutoff_month'] == cutoff
        source = json.loads(batch['source_json'])
        assert source['manifest_sha256'] == report['package_manifest_sha256']
        assert source['champion_sha256'] == report['champion_sha256']
        assert source['csv_sha256'] == package['files']['features.csv']['sha256']
        rows = [json.loads(row[0]) for row in db.execute('SELECT evidence_json FROM predictions WHERE batch_id=?',(batch_id,))]
    fresh = {(row['cus_id'],row['cutoff_month']):row for row in rows}
    assert len(rows) == len(fresh) == len(archived) == package['row_count'] == report['matched_customer_months'] == 1000
    assert fresh.keys() == archived.keys(), 'Customer-month keys differ'
    maximum = dict(raw_probability=0.0, calibrated_risk=0.0, shap_logodds=0.0)
    policy = ['schema_version','model','protocol_sha256','raw_boundary','probability_cutoff','review_alert','explanation_units']
    terms = ['base_logodds','other_features_contribution_logodds','probability_clip_adjustment_logodds']
    for key, row in fresh.items():
        validate_record(row)
        old = archived[key]
        for name in policy:
            assert row[name] == old[name], f'Policy differs: {key} {name}'
        for name in ['raw_probability','calibrated_risk']:
            difference = abs(row[name]-old[name]); maximum[name] = max(maximum[name],difference)
            assert difference <= 1e-12, f'Probability differs: {key} {name}'
        differences = [abs(row[name]-old[name]) for name in terms]
        for direction in ['higher_risk_drivers','lower_risk_drivers']:
            assert len(row[direction]) == len(old[direction])
            for driver, baseline in zip(row[direction],old[direction]):
                for name in ['feature','label','group','value']:
                    assert driver[name] == baseline[name], f'Driver differs: {key} {name}'
                differences.append(abs(driver['contribution_logodds']-baseline['contribution_logodds']))
        maximum['shap_logodds'] = max(maximum['shap_logodds'],*differences)
        assert all(math.isfinite(d) and d <= 1e-8 for d in differences), f'SHAP differs: {key}'
    return dict(status='PASS',batch_id=batch_id,cutoff_month=cutoff,matched_customer_months=len(rows),
                max_absolute_difference=maximum,score_tolerance=1e-12,shap_tolerance=1e-8,
                reference_provenance='archived dashboard_explanations.jsonl, verified against explainability_manifest.json and offline verification.json',
                timings=source['timings'],scope='Historical reproduction after web publication; no live-bank or production-readiness claim')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ['database','batch-id','reference','reference-manifest','verification','package-manifest']:
        parser.add_argument('--'+name,required=True)
    print(json.dumps(compare(**vars(parser.parse_args())),indent=2))
