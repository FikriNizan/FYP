"""Explicit, cutoff-safe observed outcomes and descriptive monitoring."""
import calendar
import csv
from collections import Counter, defaultdict
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
import hashlib
import json
import math
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


def same_outcome_evidence(prior, row):
    """Compare persisted outcome evidence, leaving full-file provenance untouched."""
    return (all(prior[key] == row[key] for key in (
        'prediction_id','outcome_month','baseline_sum_cents','future_sum_cents','target_churn'))
        and json.loads(prior['future_flows_json']) == row['future_flows'])


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
            elif not same_outcome_evidence(prior,row):
                raise ConflictError('A different outcome is already published for this prediction')
        return dict(**result,changed=changed,dry_run=True)
    changed, _present = insert_rows(rows, 'research_file')
    return dict(**result,changed=changed,dry_run=False)


def insert_rows(rows, source_kind, source_batches=None):
    """All-or-nothing write. A row whose evidence equals an existing outcome is a no-op that keeps the
    existing row ('already present'); a different outcome for the same prediction is a conflict that rolls
    back every row of this call. Returns (newly inserted, already present)."""
    db = get_db()
    changed = present = 0
    db.execute('BEGIN IMMEDIATE')
    try:
        for row in rows:
            prior = db.execute('SELECT * FROM observed_outcomes WHERE prediction_id=?',
                               (row['prediction_id'],)).fetchone()
            if prior:
                if not same_outcome_evidence(prior,row):
                    raise ConflictError('A different outcome is already published for this prediction')
                present += 1
                continue
            db.execute('INSERT INTO observed_outcomes (prediction_id,outcome_month,observed_through,baseline_sum_cents,'
                       'future_sum_cents,target_churn,future_flows_json,source_sha256,imported_at,source_kind,'
                       'source_batches_json) VALUES (?,?,?,?,?,?,?,?,?,?,?)',
                (row['prediction_id'],row['outcome_month'],row['observed_through'],
                 row['baseline_sum_cents'],row['future_sum_cents'],row['target_churn'],
                 encode(row['future_flows']),row['source_sha256'],now(),source_kind,
                 encode(source_batches) if source_batches is not None else None))
            changed += 1
        db.commit()
    except Exception:
        db.rollback()
        raise
    return changed, present


# ---------- Outcomes derived from later published monthly packages (no research files are read).
#
# The research label (audit_targets.py) is, in integer cents, 8 x (flows t+1..t+3) <= (flows t-11..t), with a
# positive baseline and all three future months present. Every published package stores the predictors
# "over N complete months ending at cutoff", so:
#   baseline_sum_cents(t) = combined_flow_mean_12m_myr of the assessment at t   x 1200
#   flow_cents(t+k)       = combined_flow_mean_1m_myr of the assessment at t+k  x 100   (k = 1, 2, 3)
# and the t+3 package's combined_flow_mean_3m_myr x 300 must equal the future sum (cross-check).
CENT_TOLERANCE = 0.01  # A value more than a hundredth of a cent from whole cents is not accepted.


def whole_cents(value, scale):
    if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
        return None
    exact = value * scale
    cents = round(exact)
    return cents if abs(exact - cents) <= CENT_TOLERANCE else None


def published_batch(cutoff, protocol):
    """The one full published assessment for a cutoff under the protocol; None when absent or ambiguous."""
    rows = get_db().execute("SELECT * FROM batches WHERE cutoff_month=? AND protocol_sha256=? "
                            "AND source_kind<>'notebook_case_sample'", (cutoff, protocol)).fetchall()
    return rows[0] if len(rows) == 1 else None


def horizon_months(cutoff):
    return [shift_month(cutoff, step) for step in (1, 2, 3)]


def package_coverage(batch):
    """Later published assessments for the three forecast months, and the first month still missing."""
    sources = [published_batch(month, batch['protocol_sha256']) for month in horizon_months(batch['cutoff_month'])]
    missing = next((month for month, source in zip(horizon_months(batch['cutoff_month']), sources) if source is None), None)
    return sources, missing


def derive(batch_id):
    """Outcome rows for one assessment from the later published packages, computed in memory only."""
    db = get_db()
    batch = db.execute('SELECT * FROM batches WHERE batch_id=?', (batch_id,)).fetchone()
    require(batch is not None, 'Assessment batch not found')
    cutoff, end = batch['cutoff_month'], horizon_end(batch['cutoff_month'])
    predictions = db.execute('SELECT prediction_id,cus_id,features_json FROM predictions WHERE batch_id=?', (batch_id,)).fetchall()
    sources, missing = package_coverage(batch)
    result = dict(batch_id=batch_id, cutoff_month=cutoff, outcome_month=end, window=horizon_months(cutoff),
                  records=len(predictions), waiting_for_month=missing, mature=missing is None, rows=[], available=0,
                  unavailable=len(predictions), unavailable_reasons={}, source_batches=[], source_sha256=None)
    if missing:
        return result
    later = []
    for source in sources:
        later.append({row['cus_id']: json.loads(row['features_json']) for row in
                      db.execute('SELECT cus_id,features_json FROM predictions WHERE batch_id=?', (source['batch_id'],))})
    result['source_batches'] = [dict(batch_id=s['batch_id'], cutoff_month=s['cutoff_month'],
                                     csv_sha256=json.loads(s['source_json']).get('csv_sha256')) for s in sources]
    source_sha = hashlib.sha256(encode(dict(kind='published_packages', batch_id=batch_id,
                                            sources=result['source_batches'])).encode()).hexdigest()
    reasons = Counter()
    for prediction in predictions:
        features = json.loads(prediction['features_json'])
        baseline = whole_cents(features.get('combined_flow_mean_12m_myr'), 1200)
        if not baseline:  # None, or a zero baseline: not eligible under the research rule.
            reasons['baseline_unavailable'] += 1
            continue
        if any(prediction['cus_id'] not in month for month in later):
            reasons['customer_missing_from_later_package'] += 1
            continue
        flows = [whole_cents(month[prediction['cus_id']].get('combined_flow_mean_1m_myr'), 100) for month in later]
        if any(flow is None for flow in flows):
            reasons['monthly_flow_unavailable'] += 1
            continue
        check = whole_cents(later[2][prediction['cus_id']].get('combined_flow_mean_3m_myr'), 300)
        if check is None or abs(check - sum(flows)) > 1:
            reasons['three_month_cross_check_failed'] += 1
            continue
        result['rows'].append(dict(prediction_id=prediction['prediction_id'], outcome_month=end, observed_through=end,
                                   baseline_sum_cents=baseline, future_sum_cents=sum(flows),
                                   target_churn=int(8 * sum(flows) <= baseline),
                                   future_flows=[dict(month=month, combined_flow_myr=flow / 100)
                                                 for month, flow in zip(result['window'], flows)],
                                   source_sha256=source_sha))
    result.update(available=len(result['rows']), unavailable=len(predictions) - len(result['rows']),
                  unavailable_reasons=dict(reasons), source_sha256=source_sha)
    return result


def publish_derived(batch_id):
    """Derive and save one assessment's outcomes. Never raises on a conflict: that batch is rolled back
    and reported, and existing outcomes stay as they are."""
    derived = derive(batch_id)
    rows = derived.pop('rows')
    summary = {key: derived[key] for key in ('batch_id', 'cutoff_month', 'outcome_month', 'window', 'records',
                                             'available', 'unavailable', 'unavailable_reasons', 'waiting_for_month')}
    if not derived['mature']:
        return dict(summary, status='waiting', inserted=0, already_present=0)
    if not rows:
        return dict(summary, status='not_available', inserted=0, already_present=0)
    try:
        inserted, present = insert_rows(rows, 'published_packages', derived['source_batches'])
    except ConflictError as error:
        return dict(summary, status='conflict', inserted=0, already_present=0, message=str(error))
    return dict(summary, status='checked' if inserted else 'already_present', inserted=inserted, already_present=present)


def derive_after_publish(new_batch):
    """Run after a monthly package is published: every earlier assessment whose forecast window includes the
    new month is checked. Idempotent; assessments still waiting for data are reported as waiting."""
    db = get_db()
    earlier = db.execute("SELECT * FROM batches WHERE protocol_sha256=? AND cutoff_month<? AND "
                         "source_kind<>'notebook_case_sample' ORDER BY cutoff_month",
                         (new_batch['protocol_sha256'], new_batch['cutoff_month'])).fetchall()
    return [publish_derived(batch['batch_id']) for batch in earlier
            if new_batch['cutoff_month'] in horizon_months(batch['cutoff_month'])]


def outcome_check(batch):
    """Data-based readiness of one assessment for the Monthly Assessments and Monitoring views."""
    db = get_db()
    records = db.execute('SELECT count(*) FROM predictions WHERE batch_id=?', (batch['batch_id'],)).fetchone()[0]
    loaded = db.execute('SELECT count(*) FROM observed_outcomes o JOIN predictions p USING(prediction_id) '
                        'WHERE p.batch_id=?', (batch['batch_id'],)).fetchone()[0]
    _sources, missing = package_coverage(batch)
    state = 'checked' if loaded else 'waiting' if missing else 'not_checked'
    # Owner decision: a waiting assessment is labelled by the LAST month of its forecast window
    # ("Ready after July 2024 data" for April 2024); waiting_for_month is the first month still missing.
    return dict(state=state, loaded=loaded, records=records, waiting_for_month=missing if not loaded else None,
                ready_after_month=horizon_end(batch['cutoff_month']), window=horizon_months(batch['cutoff_month']))


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
        return dict(records=0,positives=0,negatives=0,expected_positives=None,observed_rate=None,mean_risk=None,brier=None,
                    reference_brier=None,flagged=0,flagged_positives=0,flagged_positive=None,
                    true_positives=0,false_positives=0,false_negatives=0,true_negatives=0,
                    precision=None,recall=None,f1=None)
    observed_rate = mean(row['target_churn'] for row in rows)
    flagged = sum(row['review_alert'] for row in rows)
    flagged_positives = sum(row['target_churn'] for row in rows if row['review_alert'])
    false_positives = flagged - flagged_positives
    false_negatives = sum(row['target_churn'] for row in rows) - flagged_positives
    true_negatives = len(rows) - flagged_positives - false_positives - false_negatives
    f1_denominator = 2*flagged_positives + false_positives + false_negatives
    return dict(records=len(rows),positives=sum(row['target_churn'] for row in rows),
                negatives=len(rows)-sum(row['target_churn'] for row in rows),
                expected_positives=sum(row['risk'] for row in rows),
                observed_rate=observed_rate,reference_brier=observed_rate*(1-observed_rate),
                mean_risk=mean(row['risk'] for row in rows),
                brier=mean((row['risk']-row['target_churn'])**2 for row in rows),
                flagged=flagged,flagged_positives=flagged_positives,
                flagged_positive=flagged_positives/flagged if flagged else None,
                true_positives=flagged_positives,false_positives=false_positives,
                false_negatives=false_negatives,true_negatives=true_negatives,
                precision=flagged_positives/flagged if flagged else None,
                recall=flagged_positives/(flagged_positives+false_negatives)
                    if flagged_positives+false_negatives else None,
                f1=2*flagged_positives/f1_denominator if f1_denominator else None)


def outcome_state(outcome_month, loaded, records):
    if outcome_month > date.today().isoformat():
        return 'window_open'
    if loaded == 0:
        return 'not_loaded'
    if loaded < records:
        return 'partly_loaded'
    return 'loaded'


def batch_rows(batch_id):
    return get_db().execute('SELECT p.prediction_id,p.cus_id,p.risk,p.review_alert,o.target_churn,o.outcome_month '
        'FROM predictions p LEFT JOIN observed_outcomes o USING(prediction_id) WHERE p.batch_id=?',(batch_id,)).fetchall()


def mature_rows(batch, rows, delivered):
    start = (date.fromisoformat(batch['cutoff_month']) + timedelta(days=1)).isoformat()
    return [dict(row,delivered_actions=actions,documented_exposure=bool(actions))
        for row in rows if row['target_churn'] is not None
        for actions in [[item for item in delivered[row['cus_id']]
                         if start <= item['date'] <= row['outcome_month']]]]


def trend(batch_id):
    db = get_db()
    selected = db.execute('SELECT * FROM batches WHERE batch_id=?',(batch_id,)).fetchone()
    require(selected is not None, 'Assessment batch not found')
    batches = db.execute("SELECT * FROM batches WHERE protocol_sha256=? AND source_kind<>'notebook_case_sample' "
        'ORDER BY cutoff_month ASC, imported_at ASC',(selected['protocol_sha256'],)).fetchall()
    delivered = delivered_by_customer()
    items = []
    for batch in batches:
        rows = batch_rows(batch['batch_id'])
        mature = mature_rows(batch,rows,delivered)
        stats = performance(mature)
        outcome_month = horizon_end(batch['cutoff_month'])
        items.append(dict(batch_id=batch['batch_id'],cutoff_month=batch['cutoff_month'],
            outcome_month=outcome_month,records=len(rows),state=outcome_state(outcome_month,len(mature),len(rows)),
            loaded=len(mature),unavailable=len(rows)-len(mature),
            documented_delivery=sum(row['documented_exposure'] for row in mature),
            mean_risk_all=mean(row['risk'] for row in rows) if rows else None,
            flagged_rate_all=mean(row['review_alert'] for row in rows) if rows else None,
            mean_risk_loaded=stats['mean_risk'],observed_rate=stats['observed_rate'],
            gap=stats['observed_rate']-stats['mean_risk'] if mature else None,
            brier=stats['brier'],reference_brier=stats['reference_brier'],
            flagged_positive=stats['flagged_positive'],positives=stats['positives'] if mature else None,
            expected_positives=stats['expected_positives'],precision=stats['precision'],recall=stats['recall'],
            outcome_check=outcome_check(batch)))
    return dict(protocol_sha256=selected['protocol_sha256'],batches=items)


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
                previous_flagged=sum(x['review_alert'] for x in before),current_flagged=sum(x['review_alert'] for x in after),
                current_flagged_rate=mean(x['review_alert'] for x in after),features=features)


def report(batch_id):
    db = get_db()
    batch = db.execute('SELECT * FROM batches WHERE batch_id=?',(batch_id,)).fetchone()
    require(batch is not None, 'Assessment batch not found')
    rows = batch_rows(batch_id)
    delivered = delivered_by_customer()
    mature = mature_rows(batch,rows,delivered)
    exposed = [row for row in mature if row['documented_exposure']]
    unrecorded = [row for row in mature if not row['documented_exposure']]
    previous = db.execute("SELECT * FROM batches WHERE cutoff_month<? AND protocol_sha256=? AND source_kind<>'notebook_case_sample' "
        'ORDER BY cutoff_month DESC, imported_at DESC LIMIT 1',
        (batch['cutoff_month'],batch['protocol_sha256'])).fetchone()
    return dict(batch_id=batch_id,cutoff_month=batch['cutoff_month'],
                state=outcome_state(horizon_end(batch['cutoff_month']),len(mature),len(rows)),
                outcome_month=horizon_end(batch['cutoff_month']),records=len(rows),
                outcome_coverage=dict(loaded=len(mature),unavailable=len(rows)-len(mature),
                    documented_delivery=len(exposed),without_recorded_delivery=len(unrecorded)),
                observed_all=performance(mature),documented_delivery=performance(exposed),
                without_recorded_delivery=performance(unrecorded),
                delivery_types=dict(Counter(item['type'] for row in exposed for item in row['delivered_actions'])),
                drift=drift(batch,previous),outcome_check=outcome_check(batch),
                interpretation='Outcomes are observed volume-drop labels, not account closures. Delivery is based only on saved delivered follow-up events dated inside the prediction window. No recorded delivery does not prove no intervention. These are selected descriptive groups, not causal effects or an unbiased portfolio estimate.')
