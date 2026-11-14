"""Explicit, cutoff-safe observed outcomes and descriptive monitoring."""
import calendar
import csv
from collections import Counter, defaultdict
from datetime import date
from decimal import Decimal, InvalidOperation
import hashlib
import json
from pathlib import Path
from statistics import mean, median

from flask import current_app

from .constants import CATEGORIES, PREDICTORS, PROTOCOL_SHA256
from .db import get_db
from .repository import encode, now
from .validation import ConflictError, ValidationError, horizon_end, month_end, require


FLOW_COLUMNS = ('cus_id', 'snapshot_month', 'inbound_myr', 'inbound_count',
                'outbound_success_myr', 'outbound_success_count', 'source_complete', 'combined_flow_myr')
DOCUMENTED_DELIVERY_TYPES = ('rm_visit', 'customer_contact', 'service_fix')


def shift_month(cutoff, shift):
    parsed = date.fromisoformat(cutoff)
    year, zero = divmod(parsed.year * 12 + parsed.month - 1 + shift, 12)
    return date(year, zero + 1, calendar.monthrange(year, zero + 1)[1]).isoformat()


def cents(text, label):
    try:
        value = Decimal(text)
    except (InvalidOperation, TypeError):
        raise ValidationError(f'Invalid {label}') from None
    require(value.is_finite() and value >= 0 and value.as_tuple().exponent >= -2,
            f'{label} must be a finite, nonnegative MYR amount with at most two decimals')
    return int(value * 100)


def trusted_source():
    root = current_app.config.get('TXB_RESEARCH_ROOT')
    require(root, 'Configure TXB_RESEARCH_ROOT before loading observed outcomes')
    path = Path(root) / 'data/final_v4_0_1/cleaned/monthly_flows.csv'
    manifest = path.parent / 'cleaned_manifest.json'
    require(path.is_file() and manifest.is_file(), 'Trusted cleaned flows and manifest are unavailable')
    details = json.loads(manifest.read_text(encoding='utf-8'))
    require(details.get('status') == 'PASS' and 'monthly_flows.csv' in details.get('files', {}),
            'Trusted cleaned-flow manifest is not accepted')
    raw = path.read_bytes()
    require(len(raw) <= 50 * 1024 * 1024, 'Trusted cleaned flow file exceeds the outcome import limit')
    digest = hashlib.sha256(raw).hexdigest()
    record = details['files']['monthly_flows.csv']
    require(len(raw) == record['bytes'] and digest == record['sha256'],
            'Trusted cleaned flow differs from its manifest')
    return path, digest, len(raw)


def read_flows(path, customer_ids, first_month, last_month):
    by_customer = defaultdict(dict)
    with path.open(newline='', encoding='utf-8') as handle:
        reader = csv.DictReader(handle)
        require(reader.fieldnames == list(FLOW_COLUMNS), 'Trusted flow columns differ from the accepted contract')
        for row in reader:
            require(None not in row and all(value is not None for value in row.values()), 'Malformed trusted flow row')
            customer, month = row['cus_id'], month_end(row['snapshot_month'])
            if customer not in customer_ids or not first_month <= month <= last_month:
                continue
            require(month not in by_customer[customer], 'Duplicate trusted customer-month flow')
            amounts = [cents(row[field], field) for field in ('inbound_myr','outbound_success_myr','combined_flow_myr')]
            require(amounts[0] + amounts[1] == amounts[2], 'Trusted combined flow does not reconcile')
            require(row['source_complete'] in ('True','False'), 'Invalid source completeness flag')
            by_customer[customer][month] = (amounts[2], row['source_complete'] == 'True')
    return by_customer


def prepare(batch_id, as_of):
    as_of = month_end(as_of)
    require(as_of <= date.today().isoformat(), 'Observed-through month cannot be in the future')
    db = get_db()
    batch = db.execute('SELECT * FROM batches WHERE batch_id=?', (batch_id,)).fetchone()
    require(batch is not None, 'Assessment batch not found')
    cutoff = batch['cutoff_month']
    end = horizon_end(cutoff)
    predictions = db.execute('SELECT prediction_id,cus_id,features_json FROM predictions WHERE batch_id=?',
                             (batch_id,)).fetchall()
    require(len(predictions) == batch['record_count'], 'Published prediction count differs from its batch')
    if as_of < end:
        return dict(batch_id=batch_id, cutoff_month=cutoff, outcome_month=end,
                    observed_through=as_of, mature=False, records=len(predictions), available=0,
                    unavailable=len(predictions), rows=[], source_sha256=None)
    path, digest, size = trusted_source()
    first = shift_month(cutoff, -11)
    flows = read_flows(path, {row['cus_id'] for row in predictions}, first, end)
    prepared = []
    unavailable = 0
    for prediction in predictions:
        history = flows[prediction['cus_id']]
        baseline_months = [shift_month(cutoff, step) for step in range(-11, 1)]
        future_months = [shift_month(cutoff, step) for step in (1, 2, 3)]
        required_months = baseline_months + future_months
        if any(month not in history or not history[month][1] for month in required_months):
            unavailable += 1
            continue
        baseline = sum(history[month][0] for month in baseline_months)
        future = sum(history[month][0] for month in future_months)
        require(baseline > 0, 'A positive trailing twelve-month flow is required')
        features = json.loads(prediction['features_json'])
        saved = features.get('combined_flow_mean_12m_myr')
        require(type(saved) in (int,float) and abs(saved - baseline/1200) <= 0.000001,
                'Trusted historical baseline differs from the published feature')
        prepared.append(dict(prediction_id=prediction['prediction_id'],outcome_month=end,
                             observed_through=as_of,baseline_sum_cents=baseline,future_sum_cents=future,
                             target_churn=int(8 * future <= baseline),
                             future_flows=[dict(month=month,combined_flow_myr=history[month][0]/100)
                                           for month in future_months],source_sha256=digest))
    require(path.stat().st_size == size and hashlib.sha256(path.read_bytes()).hexdigest() == digest,
            'Trusted flow file changed during outcome preparation')
    return dict(batch_id=batch_id,cutoff_month=cutoff,outcome_month=end,observed_through=as_of,
                mature=True,records=len(predictions),available=len(prepared),unavailable=unavailable,
                rows=prepared,source_sha256=digest)


def publish(batch_id, as_of, dry_run=True):
    result = prepare(batch_id, as_of)
    rows = result.pop('rows')
    if not result['mature']:
        return dict(**result,changed=0,dry_run=True)
    if dry_run:
        db = get_db()
        changed = 0
        for row in rows:
            prior = db.execute('SELECT * FROM observed_outcomes WHERE prediction_id=?',
                               (row['prediction_id'],)).fetchone()
            if prior is None:
                changed += 1
            elif not all(prior[key] == row[key] for key in ('outcome_month','baseline_sum_cents',
                    'future_sum_cents','target_churn','source_sha256')):
                raise ConflictError('A different outcome is already published for this prediction')
        return dict(**result,changed=changed,dry_run=True)
    db = get_db()
    changed = 0
    db.execute('BEGIN IMMEDIATE')
    try:
        for row in rows:
            prior = db.execute('SELECT * FROM observed_outcomes WHERE prediction_id=?',
                               (row['prediction_id'],)).fetchone()
            if prior:
                same = all(prior[key] == row[key] for key in ('outcome_month','baseline_sum_cents',
                    'future_sum_cents','target_churn','source_sha256'))
                if not same:
                    raise ConflictError('A different outcome is already published for this prediction')
                continue
            db.execute('INSERT INTO observed_outcomes VALUES (?,?,?,?,?,?,?,?,?)',
                (row['prediction_id'],row['outcome_month'],row['observed_through'],
                 row['baseline_sum_cents'],row['future_sum_cents'],row['target_churn'],
                 encode(row['future_flows']),row['source_sha256'],now()))
            changed += 1
        db.commit()
    except Exception:
        db.rollback()
        raise
    return dict(**result,changed=changed,dry_run=False)


def delivered_by_customer():
    rows = get_db().execute("SELECT p.cus_id,t.action_type,json_extract(e.body_json,'$.action_date') action_date "
        'FROM follow_up_events e JOIN follow_ups t USING(follow_up_id) '
        'JOIN reviewed_cases c USING(case_id) JOIN predictions p ON p.prediction_id=c.prediction_id '
        "WHERE json_extract(e.body_json,'$.action_status')='delivered' ").fetchall()
    result = defaultdict(list)
    for row in rows:
        if row['action_type'] in DOCUMENTED_DELIVERY_TYPES:
            result[row['cus_id']].append(dict(type=row['action_type'],date=row['action_date']))
    return result


def performance(rows):
    if not rows:
        return dict(records=0,positives=0,observed_rate=None,mean_risk=None,brier=None,
                    flagged=0,flagged_positive=None)
    return dict(records=len(rows),positives=sum(row['target_churn'] for row in rows),
                observed_rate=mean(row['target_churn'] for row in rows),
                mean_risk=mean(row['risk'] for row in rows),
                brier=mean((row['risk']-row['target_churn'])**2 for row in rows),
                flagged=sum(row['review_alert'] for row in rows),
                flagged_positive=(sum(row['target_churn'] for row in rows if row['review_alert']) /
                    sum(row['review_alert'] for row in rows) if any(row['review_alert'] for row in rows) else None))


def drift(current, previous):
    if previous is None:
        return None
    db = get_db()
    def values(batch):
        rows = db.execute('SELECT risk,review_alert,features_json FROM predictions WHERE batch_id=?',
                          (batch['batch_id'],)).fetchall()
        return [dict(row,features=json.loads(row['features_json'])) for row in rows]
    before, after = values(previous), values(current)
    features = []
    for name in PREDICTORS:
        old = [item['features'].get(name) for item in before]
        new = [item['features'].get(name) for item in after]
        old_values = [value for value in old if value is not None]
        new_values = [value for value in new if value is not None]
        entry = dict(feature=name,previous_available=len(old_values),current_available=len(new_values),
                     previous_missing_rate=1-len(old_values)/len(before),
                     current_missing_rate=1-len(new_values)/len(after))
        if name in CATEGORIES:
            a,b = Counter(old_values),Counter(new_values)
            groups = set(a)|set(b)
            entry['distribution_difference'] = (sum(abs(a[k]/len(old_values)-b[k]/len(new_values))
                for k in groups)/2 if old_values and new_values else None)
            entry['unit'] = 'categorical total variation'
        else:
            entry['previous_median'] = median(old_values) if old_values else None
            entry['current_median'] = median(new_values) if new_values else None
            entry['unit'] = 'saved feature units'
        features.append(entry)
    return dict(previous_batch_id=previous['batch_id'],previous_month=previous['cutoff_month'],
                previous_records=len(before),current_records=len(after),
                previous_mean_risk=mean(x['risk'] for x in before),
                current_mean_risk=mean(x['risk'] for x in after),
                previous_flagged_rate=mean(x['review_alert'] for x in before),
                current_flagged_rate=mean(x['review_alert'] for x in after),features=features)


def report(batch_id):
    db = get_db()
    batch = db.execute('SELECT * FROM batches WHERE batch_id=?',(batch_id,)).fetchone()
    require(batch is not None, 'Assessment batch not found')
    rows = db.execute('SELECT p.prediction_id,p.cus_id,p.risk,p.review_alert,o.target_churn,o.outcome_month '
        'FROM predictions p LEFT JOIN observed_outcomes o USING(prediction_id) WHERE p.batch_id=?',(batch_id,)).fetchall()
    delivered = delivered_by_customer()
    mature = []
    for row in rows:
        if row['target_churn'] is None:
            continue
        start = shift_month(batch['cutoff_month'],1)
        applicable = [item for item in delivered[row['cus_id']] if start <= item['date'] <= row['outcome_month']]
        mature.append(dict(row,delivered_actions=applicable,documented_exposure=bool(applicable)))
    exposed = [row for row in mature if row['documented_exposure']]
    unrecorded = [row for row in mature if not row['documented_exposure']]
    previous = db.execute('SELECT * FROM batches WHERE cutoff_month<? AND protocol_sha256=? '
        'ORDER BY cutoff_month DESC, imported_at DESC LIMIT 1',
        (batch['cutoff_month'],batch['protocol_sha256'])).fetchone()
    return dict(batch_id=batch_id,cutoff_month=batch['cutoff_month'],
                outcome_month=horizon_end(batch['cutoff_month']),records=len(rows),
                outcome_coverage=dict(loaded=len(mature),unavailable=len(rows)-len(mature),
                    documented_delivery=len(exposed),without_recorded_delivery=len(unrecorded)),
                observed_all=performance(mature),documented_delivery=performance(exposed),
                without_recorded_delivery=performance(unrecorded),
                delivery_types=dict(Counter(item['type'] for row in exposed for item in row['delivered_actions'])),
                drift=drift(batch,previous),
                interpretation='Outcomes are observed volume-drop labels, not account closures. Delivery is based only on saved delivered follow-up events dated inside the prediction window. No recorded delivery does not prove no intervention. These are selected descriptive groups, not causal effects or an unbiased portfolio estimate.')
