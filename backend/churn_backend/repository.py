"""Immutable evidence snapshots; reviews and dated actions are separate records."""
import hashlib
import json
import time
import uuid
from datetime import datetime, timezone

from .constants import DECISIONS, FINANCE_FIELDS, OPS_FIELDS
from .db import get_db
from .validation import ConflictError, ValidationError, horizon_end, require


def now():
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def encode(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def save_batch(month, kind, protocol, entries, source):
    require(bool(entries), "The selected month contains no customers")
    identities = [e["evidence"]["cus_id"] for e in entries]
    require(len(set(identities)) == len(identities), "Duplicate customer in selected batch")
    payload = dict(month=month, kind=kind, protocol=protocol, entries=entries, source=source)
    batch_id = hashlib.sha256(encode(payload).encode()).hexdigest()
    db = get_db()
    existing = db.execute("SELECT batch_id FROM batches WHERE batch_id=?", (batch_id,)).fetchone()
    if existing:
        return dict(batch_id=batch_id, records=len(entries), already_imported=True)
    with db:
        db.execute("INSERT INTO batches VALUES (?,?,?,?,?,?,?)",
                   (batch_id, month, kind, protocol, len(entries), encode(source), now()))
        for entry in entries:
            evidence = entry["evidence"]
            prediction_id = hashlib.sha256((batch_id + ":" + evidence["cus_id"]).encode()).hexdigest()
            db.execute("INSERT INTO predictions VALUES (?,?,?,?,?,?,?,?,?)",
                       (prediction_id, batch_id, evidence["cus_id"], evidence["calibrated_risk"],
                        evidence["review_alert"], encode(evidence), encode(entry.get("features", {})),
                        encode(entry.get("customer", {})), encode(entry.get("flows", []))))
    return dict(batch_id=batch_id, records=len(entries), already_imported=False)


def publish_prepared(month, entries, source):
    """Recheck the occupied cutoff under the write lock; commit all rows together."""
    from .monthly import existing
    from .constants import PROTOCOL_SHA256
    db = get_db()
    started = time.perf_counter()
    db.execute('BEGIN IMMEDIATE')
    try:
        prior = existing(month, source['prepared_identity'])
        if prior:
            db.rollback()
            return prior
        batch_id = hashlib.sha256(('prepared:' + source['prepared_identity']).encode()).hexdigest()
        db.execute('INSERT INTO batches VALUES (?,?,?,?,?,?,?)',
                   (batch_id, month, 'prepared_month_scored', PROTOCOL_SHA256, len(entries), encode(source), now()))
        for entry in entries:
            evidence = entry['evidence']
            prediction_id = hashlib.sha256((batch_id + ':' + evidence['cus_id']).encode()).hexdigest()
            db.execute('INSERT INTO predictions VALUES (?,?,?,?,?,?,?,?,?)',
                       (prediction_id, batch_id, evidence['cus_id'], evidence['calibrated_risk'],
                        evidence['review_alert'], encode(evidence), encode(entry['features']), '{}', '[]'))
        recorded = {**source, 'timings':{**source.get('timings', {}), 'publication_before_commit_seconds':time.perf_counter()-started}}
        db.execute('UPDATE batches SET source_json=? WHERE batch_id=?',(encode(recorded),batch_id))
        db.commit()
        return dict(batch_id=batch_id, cutoff_month=month, records=len(entries), already_imported=False)
    except Exception:
        db.rollback()
        raise


def batches():
    rows = get_db().execute("SELECT * FROM batches ORDER BY cutoff_month DESC, imported_at DESC").fetchall()
    return [batch_record(row) for row in rows]


def batch_record(row):
    coverage = get_db().execute('SELECT count(*) records, '
        "sum(CASE WHEN coalesce(nullif(json_extract(s.customer_json,'$.customer_name'),''),nullif(json_extract(p.customer_json,'$.customer_name'),'')) IS NOT NULL THEN 1 ELSE 0 END) names, "
        'sum(CASE WHEN json_array_length(s.flows_json)>0 OR json_array_length(p.flows_json)>0 THEN 1 ELSE 0 END) histories '
        'FROM predictions p LEFT JOIN supplemental_evidence s USING(prediction_id) WHERE p.batch_id=?',(row['batch_id'],)).fetchone()
    source = json.loads(row['source_json'])
    source['evidence_coverage'] = dict(records=coverage['records'],names_available=coverage['names'] or 0,histories_available=coverage['histories'] or 0)
    source['customer_names_loaded'] = bool(source.get('customer_names_loaded') or coverage['names'])
    source['flow_history_loaded'] = bool(source.get('flow_history_loaded') or coverage['histories'])
    return dict(batch_id=row["batch_id"], cutoff_month=row["cutoff_month"],
                source_kind=row["source_kind"], record_count=row["record_count"],
                protocol_sha256=row["protocol_sha256"], imported_at=row["imported_at"],
                source=source)


def select_batch(month=None, batch_id=None):
    db = get_db()
    if batch_id:
        row = db.execute("SELECT * FROM batches WHERE batch_id=?", (batch_id,)).fetchone()
        if row is not None and month and row["cutoff_month"] != month:
            raise ValidationError("batch_id and month identify different batches")
    else:
        condition, params = ("WHERE cutoff_month=?", (month,)) if month else ("", ())
        row = db.execute(f"SELECT * FROM batches {condition} ORDER BY cutoff_month DESC, "
                         "CASE source_kind WHEN 'saved_shap_export' THEN 0 ELSE 1 END, "
                         "imported_at DESC LIMIT 1", params).fetchone()
    return row


def prediction_row(prediction_id):
    return get_db().execute("SELECT p.*, b.cutoff_month, b.source_kind FROM predictions p "
                            "JOIN batches b USING(batch_id) WHERE prediction_id=?",
                            (prediction_id,)).fetchone()


def review_record(prediction_id):
    row = get_db().execute("SELECT * FROM reviews WHERE prediction_id=?", (prediction_id,)).fetchone()
    if row is None:
        return dict(decision="awaiting_review", reason="", operations_notes="", finance_notes="",
                    owner="", next_action_date=None, reviewer=None, version=0, updated_at=None)
    return dict(**json.loads(row["body_json"]), version=row["version"], updated_at=row["updated_at"])


def action_records(prediction_id):
    rows = get_db().execute("SELECT * FROM actions WHERE prediction_id=? ORDER BY recorded_at, action_id",
                           (prediction_id,)).fetchall()
    return [dict(**json.loads(r["body_json"]), action_id=r["action_id"], recorded_at=r["recorded_at"])
            for r in rows]


def customer_record(row, detail=False):
    features, customer = json.loads(row["features_json"]), json.loads(row["customer_json"])
    supplement = get_db().execute('SELECT * FROM supplemental_evidence WHERE prediction_id=?',(row['prediction_id'],)).fetchone()
    if supplement:
        extra = json.loads(supplement['customer_json'])
        if extra.get('customer_name'):
            customer = {**customer,**extra}
    evidence = json.loads(row["evidence_json"])
    record = dict(prediction_id=row["prediction_id"], batch_id=row["batch_id"], cus_id=row["cus_id"],
                  cutoff_month=evidence["cutoff_month"], customer_name=customer.get("customer_name"),
                  sector_code=features.get("sector_code"), tier_id=features.get("tier_id"),
                  customer_type=features.get("customer_type"), calibrated_risk=row["risk"],
                  review_alert=bool(row["review_alert"]), probability_cutoff=evidence["probability_cutoff"],
                  review=review_record(row["prediction_id"]),
                  finance={label: features.get(field) for label, field in FINANCE_FIELDS.items()})
    record['workflow'] = workflow_context(row,record['review'],record['review_alert'],evidence['cutoff_month'])
    if detail:
        record.update(explanation=evidence, features=features,
                      feature_count=len(features), operations={name: features.get(name) for name in OPS_FIELDS},
                      flow_history=(json.loads(supplement['flows_json']) if supplement and json.loads(supplement['flows_json'])
                                    else json.loads(row["flows_json"])), actions=action_records(row["prediction_id"]),
                      supplemental_provenance=json.loads(supplement['provenance_json']) if supplement else None,
                      assessment_window_end=horizon_end(evidence["cutoff_month"]),
                      outcome_status="not_loaded", actual_attrition=None,
                      finance_note="Fee and waiver figures are historical three-month monthly estimates; "
                                   "balances are exposures. These are not verified profit or retention savings.")
    return record


def workflow_context(row, review, flagged, cutoff_month):
    db = get_db()
    cases = db.execute('SELECT c.*, origin.cus_id, b.cutoff_month origin_month, origin.risk origin_risk '
        'FROM reviewed_cases c JOIN predictions origin ON origin.prediction_id=c.prediction_id '
        'JOIN batches b ON b.batch_id=origin.batch_id WHERE origin.cus_id=? ORDER BY c.created_at,c.case_id',
        (row['cus_id'],)).fetchall()
    active = [c for c in cases if c['status'] in ('open','deferred')]
    own = next((c for c in cases if c['prediction_id']==row['prediction_id']),None)
    if own is None:
        linked = db.execute('SELECT case_id FROM review_case_links WHERE prediction_id=?',(row['prediction_id'],)).fetchone()
        own = next((c for c in cases if c['case_id']==linked['case_id']),None) if linked else None
    chosen = own or (active[0] if len(active)==1 else None)
    earlier = db.execute('SELECT 1 FROM reviews r JOIN predictions p USING(prediction_id) '
        'JOIN batches b USING(batch_id) WHERE p.cus_id=? AND b.cutoff_month<=? LIMIT 1',
        (row['cus_id'],cutoff_month)).fetchone()
    if review['version']:
        state='reviewed'
    elif len(active)>1:
        state='case_conflict'
    elif chosen and chosen['status']!='closed':
        state='existing_case'
    elif not flagged:
        state='below_threshold'
    elif earlier or cases:
        state='needs_reassessment'
    else:
        state='needs_first_review'
    return dict(state=state,case_id=chosen['case_id'] if chosen else None,
                case_version=chosen['version'] if chosen else None,
                case_status=chosen['status'] if chosen else None,
                origin_month=chosen['origin_month'] if chosen else None,
                origin_risk=chosen['origin_risk'] if chosen else None,
                origin_decision=json.loads(chosen['original_review_json'])['decision'] if chosen else None,
                active_cases=[dict(case_id=c['case_id'],status=c['status'],origin_month=c['origin_month'],version=c['version']) for c in active],
                prior_review=bool(earlier or cases))


def batch_customers(batch_id):
    rows = get_db().execute("SELECT * FROM predictions WHERE batch_id=? ORDER BY risk DESC, cus_id",
                           (batch_id,)).fetchall()
    return [customer_record(row) for row in rows]


def summary(batch):
    customers = batch_customers(batch["batch_id"])
    flagged = [c for c in customers if c["review_alert"]]
    counts = {decision: sum(c["review"]["decision"] == decision for c in customers) for decision in DECISIONS}
    flag_counts = {decision: sum(c["review"]["decision"] == decision for c in flagged) for decision in DECISIONS}
    finance = {}
    for field in FINANCE_FIELDS:
        for scope, records in (("all", customers), ("flagged", flagged)):
            values = [c["finance"][field] for c in records if c["finance"][field] is not None]
            finance[f"{scope}_{field}"] = dict(total=sum(values) if values else None,
                                                records_with_value=len(values), records=len(records))
    return dict(batch=batch_record(batch), population=len(customers), flagged=len(flagged),
                workflow_counts={state:sum(c['workflow']['state']==state for c in customers) for state in
                                 ('reviewed','existing_case','case_conflict','below_threshold','needs_reassessment','needs_first_review')},
                needs_committee_review=sum(c['workflow']['state'] in ('needs_first_review','needs_reassessment') for c in flagged),
                below_threshold=len(customers)-len(flagged),
                mean_risk=sum(c["calibrated_risk"] for c in customers)/len(customers),
                review_counts=counts, flagged_review_counts=flag_counts, finance=finance,
                risk_definition="Next-three-month average combined flow at most 50% of "
                                "a positive trailing-twelve-month average",
                target_horizon_months=3,
                limitations=["SHAP contributions are model explanations, not causal effects.",
                             "Unknown financial values remain null; totals include coverage counts.",
                             "Action logging does not establish retention effectiveness."])


def save_review(prediction_id, body):
    db = get_db()
    db.execute("BEGIN IMMEDIATE")
    try:
        if prediction_row(prediction_id) is None:
            raise LookupError("Prediction not found")
        existing = review_record(prediction_id)
        if existing["version"] != body["expected_version"]:
            raise ConflictError("This review changed. Reload it before saving your decision.")
        saved = {key: value for key, value in body.items() if key not in ('expected_version','case_id','expected_case_version')}
        version, timestamp = existing["version"] + 1, now()
        prediction = db.execute('SELECT p.cus_id,b.cutoff_month FROM predictions p JOIN batches b USING(batch_id) '
                                'WHERE p.prediction_id=?',(prediction_id,)).fetchone()
        active = db.execute("SELECT c.* FROM reviewed_cases c JOIN predictions p ON p.prediction_id=c.prediction_id "
                            "WHERE p.cus_id=? AND c.status IN ('open','deferred') ORDER BY c.created_at,c.case_id",
                            (prediction['cus_id'],)).fetchall()
        own = db.execute('SELECT * FROM reviewed_cases WHERE prediction_id=?',(prediction_id,)).fetchone()
        if not own:
            linked = db.execute('SELECT c.* FROM review_case_links l JOIN reviewed_cases c USING(case_id) '
                                'WHERE l.prediction_id=?',(prediction_id,)).fetchone()
            own = linked
        chosen = own
        if chosen is None and active:
            if len(active)>1 and not body.get('case_id'):
                raise ConflictError('Multiple active cases exist. Select the case to reassess; no case was created.')
            chosen = next((c for c in active if c['case_id']==body.get('case_id')),None) if body.get('case_id') else active[0]
        if body.get('case_id') and (chosen is None or chosen['case_id'] != body['case_id']):
            raise ConflictError('The selected case is no longer available for this customer. Reload before saving.')
        if chosen and body.get('expected_case_version') != chosen['version']:
            raise ConflictError('This case changed. Reload the current case and your review draft before saving.')
        db.execute("INSERT INTO reviews VALUES (?,?,?,?) ON CONFLICT(prediction_id) "
                   "DO UPDATE SET version=excluded.version, body_json=excluded.body_json, "
                   "updated_at=excluded.updated_at", (prediction_id, version, encode(saved), timestamp))
        db.execute("INSERT INTO review_history(prediction_id,version,body_json,saved_at) VALUES (?,?,?,?)",
                   (prediction_id, version, encode(saved), timestamp))
        if chosen is None:
            prior = db.execute('SELECT c.case_id FROM reviewed_cases c JOIN predictions p ON p.prediction_id=c.prediction_id '
                               'WHERE p.cus_id=? AND c.status="closed" ORDER BY c.created_at',(prediction['cus_id'],)).fetchall()
            db.execute("INSERT INTO reviewed_cases VALUES (?,?,?,'open',?,?,1,?,?)",
                       (prediction_id, prediction_id, encode(saved), saved['owner'], saved['next_action_date'], timestamp, timestamp))
            db.execute("INSERT INTO case_events(case_id,version,body_json,recorded_at) VALUES (?,1,?,?)",
                       (prediction_id, encode(dict(kind='case_created', status='open', recorded_by=saved['reviewer'], notes=saved['reason'],
                                                   previous_closed_cases=[r['case_id'] for r in prior])), timestamp))
        else:
            if prediction_id != chosen['prediction_id']:
                db.execute('INSERT INTO review_case_links VALUES (?,?,?,?) ON CONFLICT(prediction_id) DO UPDATE SET '
                           'review_version=excluded.review_version,linked_at=excluded.linked_at',
                           (prediction_id,chosen['case_id'],version,timestamp))
            next_case_version = chosen['version']+1
            db.execute('UPDATE reviewed_cases SET version=?,updated_at=? WHERE case_id=?',
                       (next_case_version,timestamp,chosen['case_id']))
            db.execute('INSERT INTO case_events(case_id,version,body_json,recorded_at) VALUES (?,?,?,?)',
                       (chosen['case_id'],next_case_version,encode(dict(kind='committee_reassessment',
                         prediction_id=prediction_id,assessment_month=prediction['cutoff_month'],review_version=version,
                         decision=saved['decision'],recorded_by=saved['reviewer'],notes=saved['reason'])),timestamp))
        db.commit()
    except Exception:
        db.rollback()
        raise
    return review_record(prediction_id)


def review_history(prediction_id):
    rows = get_db().execute("SELECT * FROM review_history WHERE prediction_id=? ORDER BY version",
                           (prediction_id,)).fetchall()
    return [dict(**json.loads(r["body_json"]), version=r["version"], saved_at=r["saved_at"]) for r in rows]


def save_action(prediction_id, body):
    require(prediction_row(prediction_id) is not None, "Prediction not found")
    action_id, timestamp = uuid.uuid4().hex, now()
    db = get_db()
    with db:
        db.execute("INSERT INTO actions VALUES (?,?,?,?)", (action_id, prediction_id, encode(body), timestamp))
    return dict(**body, action_id=action_id, recorded_at=timestamp)
