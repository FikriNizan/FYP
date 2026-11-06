"""Cross-assessment worklist and versioned human follow-up, separate from predictions."""
import json
import uuid

from werkzeug.exceptions import NotFound

from .db import get_db
from . import repository as repo
from .validation import (ConflictError, require, text_field, iso_date, validate_action, business_today)


def case_row(case_id):
    row = get_db().execute('SELECT * FROM reviewed_cases WHERE case_id=?', (case_id,)).fetchone()
    if row is None:
        raise NotFound('Reviewed case not found')
    return row


def tasks(case_id):
    rows = get_db().execute('SELECT * FROM follow_ups WHERE case_id=? ORDER BY created_at,follow_up_id', (case_id,)).fetchall()
    result = []
    for row in rows:
        events = get_db().execute('SELECT * FROM follow_up_events WHERE follow_up_id=? ORDER BY event_id', (row['follow_up_id'],)).fetchall()
        history = [dict(**json.loads(e['body_json']), recorded_at=e['recorded_at'], event_id=e['event_id']) for e in events]
        result.append(dict(**dict(row), current=history[-1], history=history))
    return result


def record(row, detail=False):
    original = repo.customer_record(repo.prediction_row(row['prediction_id']), detail=detail)
    latest_row = get_db().execute(
        "SELECT p.* FROM predictions p JOIN batches b USING(batch_id) WHERE p.cus_id=? "
        "ORDER BY b.cutoff_month DESC, CASE b.source_kind WHEN 'saved_shap_export' THEN 0 ELSE 1 END, "
        "COALESCE(json_extract(b.source_json,'$.customer_names_loaded'),0) DESC, "
        "COALESCE(json_extract(b.source_json,'$.flow_history_loaded'),0) DESC, b.imported_at DESC,b.batch_id DESC LIMIT 1",
        (original['cus_id'],)).fetchone()
    result = dict(row)
    result['original_review'] = json.loads(result.pop('original_review_json'))
    result.update(original=original, latest=repo.customer_record(latest_row, detail=detail))
    follow_ups = tasks(row['case_id'])
    result['follow_up_counts'] = {state: sum(t['current']['action_status'] == state for t in follow_ups)
                                  for state in ('planned','attempted','delivered','cancelled')}
    if detail:
        result['follow_ups'] = follow_ups
        events = get_db().execute('SELECT * FROM case_events WHERE case_id=? ORDER BY version', (row['case_id'],)).fetchall()
        result['history'] = [dict(**json.loads(e['body_json']), version=e['version'], recorded_at=e['recorded_at']) for e in events]
        result['review_history'] = repo.review_history(row['prediction_id'])
    return result


def listing(query='', status=None, decision=None, owner='', offset=0, limit=50):
    rows = get_db().execute('SELECT * FROM reviewed_cases ORDER BY updated_at DESC,case_id').fetchall()
    items = [record(row) for row in rows]
    query, owner = query.casefold(), owner.casefold()
    items = [c for c in items if (not status or c['status'] == status)
             and (not decision or c['original_review']['decision'] == decision)
             and (not owner or owner in c['owner'].casefold())
             and (not query or query in c['original']['cus_id'].casefold()
                  or query in (c['latest']['customer_name'] or c['original']['customer_name'] or '').casefold())]
    return dict(items=items[offset:offset+limit], total=len(items), offset=offset, limit=limit)


def validate_write(body, fields):
    require(isinstance(body, dict) and not set(body)-fields, 'Unknown case fields')
    require(type(body.get('expected_version')) is int and body['expected_version'] >= 1,
            'expected_version must be a positive integer')


def locked(case_id, body):
    row = case_row(case_id)
    if body['expected_version'] != row['version']:
        raise ConflictError('This case changed. Your draft is preserved; load the latest case before saving again.')
    return row


def event(row, payload):
    db, stamp = get_db(), repo.now()
    version = row['version'] + 1
    db.execute('UPDATE reviewed_cases SET version=?,updated_at=? WHERE case_id=?', (version,stamp,row['case_id']))
    db.execute('INSERT INTO case_events(case_id,version,body_json,recorded_at) VALUES (?,?,?,?)',
               (row['case_id'],version,repo.encode(payload),stamp))


def update(case_id, body):
    validate_write(body, {'expected_version','status','owner','next_action_date','notes','recorded_by'})
    require(body.get('status') in ('open','deferred','closed'), 'Invalid case status')
    owner = text_field(body,'owner',maximum=200)
    author = text_field(body,'recorded_by',maximum=200,required=True)
    notes = text_field(body,'notes',required=True)
    due = body.get('next_action_date')
    if due is not None:
        iso_date(due,'next_action_date')
    db = get_db()
    db.execute('BEGIN IMMEDIATE')
    try:
        row = locked(case_id,body)
        db.execute('UPDATE reviewed_cases SET status=?,owner=?,next_action_date=? WHERE case_id=?',
                   (body['status'],owner,due,case_id))
        event(row,dict(kind='case_updated',status=body['status'],owner=owner,next_action_date=due,notes=notes,recorded_by=author))
        db.commit()
    except Exception:
        db.rollback()
        raise
    return record(case_row(case_id),True)


def follow_up(case_id, body, follow_up_id=None):
    validate_write(body, {'expected_version','action_type','action_status','action_date','notes','recorded_by'})
    action = validate_action({key:value for key,value in body.items() if key != 'expected_version'})
    if action['action_status'] != 'planned':
        require(iso_date(action['action_date']) <= business_today(), 'An actual event cannot have a future date')
    db = get_db()
    db.execute('BEGIN IMMEDIATE')
    try:
        row = locked(case_id,body)
        require(row['status'] != 'closed', 'Reopen this case before recording a follow-up')
        if follow_up_id:
            task = db.execute('SELECT * FROM follow_ups WHERE follow_up_id=? AND case_id=?', (follow_up_id,case_id)).fetchone()
            if task is None:
                raise NotFound('Follow-up not found in this case')
            latest = db.execute('SELECT body_json FROM follow_up_events WHERE follow_up_id=? ORDER BY event_id DESC LIMIT 1', (follow_up_id,)).fetchone()
            current = json.loads(latest['body_json'])
            require(current['action_status'] not in ('delivered','cancelled'), 'This follow-up is complete; create a new follow-up')
            require(action['action_type'] == task['action_type'], 'Action type cannot change on an existing follow-up')
            require(action['action_status'] != 'planned', 'Record an attempt, completion or cancellation of this task')
            if current['action_status'] == 'attempted':
                require(action['action_date'] >= current['action_date'], 'A later event cannot predate the last attempt')
        else:
            require(action['action_status'] != 'cancelled', 'Create a planned or actual follow-up first')
            follow_up_id = uuid.uuid4().hex
            db.execute('INSERT INTO follow_ups VALUES (?,?,?,?,?)',
                       (follow_up_id,case_id,action['action_type'],action['action_date'] if action['action_status']=='planned' else None,repo.now()))
        db.execute('INSERT INTO follow_up_events(follow_up_id,body_json,recorded_at) VALUES (?,?,?)',
                   (follow_up_id,repo.encode(action),repo.now()))
        event(row,dict(kind='follow_up_event',follow_up_id=follow_up_id,**action))
        db.commit()
    except Exception:
        db.rollback()
        raise
    return record(case_row(case_id),True)
