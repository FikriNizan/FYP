"""Phase B verification gate: outcomes derived from published packages must equal the trusted labels.

    .\\.venv\\Scripts\\python.exe scripts\\verify_package_outcomes.py --db artifacts\\m8-gate.sqlite ^
        --research-root <R> --model-python C:\\Users\\fikri\\fyp-model-env\\Scripts\\python.exe ^
        --publish artifacts\\m8-packages\\prepared-2024-05 --publish artifacts\\m8-packages\\prepared-2024-06 ^
        --publish artifacts\\m8-packages\\prepared-2024-07

1. Refuses the Working, Milestone 5 and Milestone 6 databases; the database must be a Test copy under artifacts/.
2. Optionally publishes prepared packages into that copy through the normal monthly path (frozen model scoring).
3. For every assessment whose three forecast months are now published, derives outcomes IN MEMORY from the
   packages (outcomes.derive; nothing is written) and compares them per customer with
   (a) the research labels data/features_v1/targets_NOT_FEATURES.csv (read-only), and
   (b) any outcome rows already stored in the copy (file-derived), using the app's own evidence comparison.
Exit code 0 only when every derived label matches every trusted label for every checked assessment.
"""
import argparse
import csv
import json
import os
from pathlib import Path
import sys

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))
sys.path.insert(0, str(ROOT / 'scripts'))
import local_session  # noqa: E402  (reuses the confirmed database paths)


def safe_database(path):
    target = Path(path).resolve(strict=True)
    protected = [local_session.WORKING, local_session.M6_TEST, local_session.TEST]
    if any(p.exists() and os.path.samefile(target, p) for p in protected):
        raise SystemExit('STOPPED: use a separate Test copy, never the Working, Milestone 5 or Milestone 6 database')
    if (ROOT / 'artifacts').resolve() not in target.parents:
        raise SystemExit('STOPPED: the gate database must be a Test copy under artifacts/')
    return target


def trusted_labels(research_root):
    path = Path(research_root) / 'data' / 'features_v1' / 'targets_NOT_FEATURES.csv'
    labels = {}
    with path.open(newline='', encoding='utf-8') as handle:
        for row in csv.DictReader(handle):
            if row['label_eligible'] == 'True':
                labels[(row['cus_id'], row['cutoff_month'])] = int(float(row['target_churn']) if row['target_churn'] not in ('True', 'False')
                                                                   else row['target_churn'] == 'True')
    return labels


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--db', required=True)
    parser.add_argument('--research-root', required=True)
    parser.add_argument('--model-python')
    parser.add_argument('--publish', action='append', default=[], help='Prepared package folder (features.csv + manifest.json)')
    args = parser.parse_args(argv)
    database = safe_database(args.db)
    from churn_backend import create_app, monthly, outcomes
    from churn_backend.db import get_db
    app = create_app(dict(DATABASE=str(database), TXB_RESEARCH_ROOT=args.research_root,
                          TXB_MODEL_PYTHON=args.model_python, TXB_SCORING_TIMEOUT_SECONDS=600))
    labels = trusted_labels(args.research_root)
    report, ok = [], True
    with app.app_context():
        for folder in args.publish:
            folder = Path(folder)
            result = monthly.process((folder / 'features.csv').read_bytes(), (folder / 'manifest.json').read_bytes())
            print('Published', result['cutoff_month'], result['batch_id'][:12], 'already imported' if result['already_imported'] else 'new',
                  '| enrichment', result.get('enrichment', {}).get('status'), flush=True)
        db = get_db()
        for batch in db.execute("SELECT * FROM batches WHERE source_kind<>'notebook_case_sample' ORDER BY cutoff_month").fetchall():
            derived = outcomes.derive(batch['batch_id'])
            if not derived['mature']:
                print(batch['cutoff_month'], 'waiting for', derived['waiting_for_month'], flush=True)
                continue
            predictions = {row['prediction_id']: row for row in
                           db.execute('SELECT prediction_id,cus_id,review_alert FROM predictions WHERE batch_id=?', (batch['batch_id'],))}
            matched = mismatched = missing_trusted = stored_same = stored_different = 0
            tp = fp = fn = tn = 0
            for row in derived['rows']:
                prediction = predictions[row['prediction_id']]
                trusted = labels.get((prediction['cus_id'], batch['cutoff_month']))
                if trusted is None:
                    missing_trusted += 1
                elif trusted == row['target_churn']:
                    matched += 1
                else:
                    mismatched += 1
                prior = db.execute('SELECT * FROM observed_outcomes WHERE prediction_id=?', (row['prediction_id'],)).fetchone()
                if prior is not None:
                    if outcomes.same_outcome_evidence(prior, row):
                        stored_same += 1
                    else:
                        stored_different += 1
                flagged, positive = prediction['review_alert'], row['target_churn']
                tp += flagged and positive; fp += flagged and not positive
                fn += (not flagged) and positive; tn += (not flagged) and not positive
            entry = dict(cutoff_month=batch['cutoff_month'], batch_id=batch['batch_id'][:12], records=derived['records'],
                         derived=derived['available'], unavailable=derived['unavailable'], reasons=derived['unavailable_reasons'],
                         matched=matched, mismatched=mismatched, missing_trusted=missing_trusted,
                         positives=sum(r['target_churn'] for r in derived['rows']), tp=tp, fp=fp, fn=fn, tn=tn,
                         stored_same=stored_same, stored_different=stored_different)
            ok = ok and mismatched == 0 and missing_trusted == 0 and derived['unavailable'] == 0 and stored_different == 0
            report.append(entry)
            print(json.dumps(entry), flush=True)
    print('GATE', 'PASS' if ok and report else 'FAIL')
    return 0 if ok and report else 1


if __name__ == '__main__':
    sys.exit(main())
