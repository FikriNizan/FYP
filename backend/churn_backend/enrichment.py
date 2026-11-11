"""Accepted supplemental names and observed flows for an exact saved batch."""
import json
from pathlib import Path
from flask import current_app

from . import repository as repo
from .db import get_db
from .importer import read_customer_master, read_flows, sha256
from .validation import ConflictError, ValidationError, require

MASTER = Path('data/final_v4_0_1/cleaned/company_population_clean.csv')
FLOWS = Path('data/final_v4_0_1/cleaned/monthly_flows.csv')


def prepare(batch_id):
    batch = repo.select_batch(batch_id=batch_id)
    require(batch is not None, 'Batch not found')
    root = current_app.config.get('TXB_RESEARCH_ROOT')
    require(root and Path(root).is_dir(), 'Trusted research root is unavailable for enrichment')
    root = Path(root).resolve()
    source_paths = {'customer_master':(root/MASTER).resolve(), 'monthly_flows':(root/FLOWS).resolve()}
    for path in source_paths.values():
        require(path.is_relative_to(root), 'Supporting source escapes the configured research root')
    rows = get_db().execute('SELECT prediction_id,cus_id,features_json FROM predictions WHERE batch_id=? ORDER BY cus_id',(batch_id,)).fetchall()
    ids = {row['cus_id'] for row in rows}
    features = {(row['cus_id'],batch['cutoff_month']):json.loads(row['features_json']) for row in rows}
    paths = {name:path if path.is_file() else None for name,path in source_paths.items()}
    initial_hashes = {name:sha256(path) if path else None for name,path in paths.items()}
    master = read_customer_master(paths['customer_master'],ids,allow_missing=True)
    flows = read_flows(paths['monthly_flows'],batch['cutoff_month'],ids,features,allow_missing=True)
    hashes = {name:sha256(path) if path else None for name,path in paths.items()}
    require(hashes == initial_hashes, 'Supporting source changed during validation; retry from the unchanged files')
    coverage = dict(records=len(rows),names_available=sum(bool(master.get(id,{}).get('customer_name')) for id in ids),
                    histories_available=sum(bool(flows.get(id)) for id in ids),
                    master_file_available=paths['customer_master'] is not None,
                    flows_file_available=paths['monthly_flows'] is not None)
    entries = [(row['prediction_id'],master.get(row['cus_id'],{}),flows.get(row['cus_id'],[])) for row in rows]
    return dict(batch_id=batch_id,cutoff_month=batch['cutoff_month'],file_sha256=hashes,coverage=coverage,entries=entries)


def apply(batch_id, *, replace=False, dry_run=True):
    prepared = prepare(batch_id)  # All source validation happens before any write.
    db = get_db()
    changes = []
    for prediction_id,customer,flows in prepared['entries']:
        old = db.execute('SELECT * FROM supplemental_evidence WHERE prediction_id=?',(prediction_id,)).fetchone()
        same = (old is not None and json.loads(old['customer_json']) == customer and json.loads(old['flows_json']) == flows
                and json.loads(old['provenance_json'])['file_sha256'] == prepared['file_sha256'])
        if not same:
            if old is not None and not replace and not dry_run:
                raise ConflictError('Supporting evidence differs. Preview the source and use explicit --replace to record a correction.')
            changes.append((prediction_id,customer,flows,old['version'] if old else None))
    result = {key:value for key,value in prepared.items() if key != 'entries'}
    result.update(dry_run=dry_run,changed=len(changes),unchanged=len(prepared['entries'])-len(changes),
                  replacement_needed=any(version is not None for _,_,_,version in changes))
    if dry_run or not changes:
        return result
    db.execute('BEGIN IMMEDIATE')
    try:
        for prediction_id,customer,flows,old_version in changes:
            old = db.execute('SELECT * FROM supplemental_evidence WHERE prediction_id=?',(prediction_id,)).fetchone()
            if (old['version'] if old else None) != old_version:
                raise ConflictError('Supporting evidence changed concurrently. Preview again before applying.')
            if old:
                db.execute('INSERT INTO supplemental_history VALUES (?,?,?,?,?,?)',
                           (prediction_id,old['version'],old['customer_json'],old['flows_json'],old['provenance_json'],old['applied_at']))
            stamp = repo.now()
            provenance = dict(file_sha256=prepared['file_sha256'],coverage=prepared['coverage'],batch_id=batch_id,
                              cutoff_month=prepared['cutoff_month'],applied_at=stamp,correction=bool(old))
            db.execute('INSERT INTO supplemental_evidence VALUES (?,?,?,?,?,?) ON CONFLICT(prediction_id) DO UPDATE SET '
                       'customer_json=excluded.customer_json,flows_json=excluded.flows_json,provenance_json=excluded.provenance_json,'
                       'version=excluded.version,applied_at=excluded.applied_at',
                       (prediction_id,repo.encode(customer),repo.encode(flows),repo.encode(provenance),old['version']+1 if old else 1,stamp))
        db.commit()
    except Exception:
        db.rollback()
        raise
    return result
