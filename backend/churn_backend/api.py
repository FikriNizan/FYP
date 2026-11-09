from flask import Blueprint, abort, jsonify, request, send_file
from io import BytesIO

from . import repository as repo
from . import cases
from . import briefings
from .db import get_db
from .constants import ACTION_STATUSES, ACTION_TYPES, DECISIONS, VERSION
from .validation import (month_end, require, strict_json, validate_action, validate_review)

api = Blueprint("api", __name__, url_prefix="/api")


def selected_batch():
    month = request.args.get("month")
    if month is not None:
        month = month_end(month, allow_short=True)
    batch = repo.select_batch(month, request.args.get("batch_id"))
    if batch is None:
        abort(404, description="No batch found. Import the demo or a completed SHAP export first.")
    return batch


def body():
    require(request.is_json, "Send Content-Type: application/json")
    return strict_json(request.get_data(as_text=True))


def existing_prediction(prediction_id):
    row = repo.prediction_row(prediction_id)
    if row is None:
        abort(404, description="Prediction not found")
    return row


@api.get("/health")
def health():
    return jsonify(status="ok", version=VERSION, batches=len(repo.batches()))


@api.get("/metadata")
def metadata():
    return jsonify(version=VERSION, decisions=list(DECISIONS), action_types=list(ACTION_TYPES),
                   action_statuses=list(ACTION_STATUSES), display_timezone="Asia/Kuala_Lumpur",
                   timestamps="UTC ISO 8601", outcome_monitoring=False, live_model_scoring=False,
                   review_identity="User-entered attribution for this local prototype; not authenticated identity",
                   data_access="Local saved evidence snapshots")


@api.get("/months")
def months():
    return jsonify(items=repo.batches())


@api.get("/summary")
def summary():
    return jsonify(repo.summary(selected_batch()))


@api.get("/customers")
def customers():
    batch = selected_batch()
    items = repo.batch_customers(batch["batch_id"])
    query = request.args.get("q", "").strip().casefold()
    if query:
        items = [item for item in items if query in item["cus_id"].casefold()
                 or query in (item["customer_name"] or "").casefold()]
    flagged = request.args.get("flagged")
    require(flagged in (None, "true", "false"), "flagged must be true or false")
    if flagged is not None:
        items = [item for item in items if item["review_alert"] == (flagged == "true")]
    decision = request.args.get("decision")
    require(decision is None or decision in DECISIONS, "Invalid decision filter")
    if decision:
        items = [item for item in items if item["review"]["decision"] == decision]
    try:
        limit, offset = int(request.args.get("limit", "100")), int(request.args.get("offset", "0"))
    except ValueError:
        require(False, "limit and offset must be integers")
    require(1 <= limit <= 1000 and offset >= 0, "Invalid pagination range")
    return jsonify(batch=repo.batch_record(batch), total=len(items), limit=limit, offset=offset,
                   items=items[offset:offset+limit])


@api.get("/customers/<cus_id>")
def customer(cus_id):
    batch = selected_batch()
    row = get_db().execute("SELECT * FROM predictions WHERE batch_id=? AND cus_id=?",
                                (batch["batch_id"], cus_id)).fetchone()
    if row is None:
        abort(404, description="Customer not present in this batch")
    return jsonify(batch=repo.batch_record(batch), customer=repo.customer_record(row, detail=True))


@api.get("/customers/<cus_id>/history")
def customer_history(cus_id):
    batch = selected_batch()
    rows = get_db().execute("SELECT p.*, b.cutoff_month, b.source_kind, b.imported_at FROM predictions p "
                                 "JOIN batches b USING(batch_id) WHERE p.cus_id=? "
                                 "AND (b.cutoff_month<? OR b.batch_id=?) "
                                 "ORDER BY b.cutoff_month DESC, "
                                 "CASE b.source_kind WHEN 'saved_shap_export' THEN 0 ELSE 1 END, b.imported_at DESC",
                                 (cus_id, batch["cutoff_month"], batch["batch_id"])).fetchall()
    if not rows:
        abort(404, description="No imported history for this customer")
    chosen = {}
    for row in rows:
        chosen.setdefault(row["cutoff_month"], repo.customer_record(row))
    return jsonify(cus_id=cus_id, through_month=batch["cutoff_month"],
                   items=[chosen[key] for key in sorted(chosen)])


@api.put("/predictions/<prediction_id>/review")
def save_review(prediction_id):
    existing_prediction(prediction_id)
    return jsonify(review=repo.save_review(prediction_id, validate_review(body())))


@api.get("/predictions/<prediction_id>/review-history")
def review_history(prediction_id):
    existing_prediction(prediction_id)
    return jsonify(items=repo.review_history(prediction_id))


@api.get("/predictions/<prediction_id>/actions")
def actions(prediction_id):
    existing_prediction(prediction_id)
    return jsonify(items=repo.action_records(prediction_id))


@api.post("/predictions/<prediction_id>/actions")
def save_action(prediction_id):
    existing_prediction(prediction_id)
    return jsonify(action=repo.save_action(prediction_id, validate_action(body()))), 201


@api.get('/cases')
def reviewed_cases():
    status, decision = request.args.get('status'), request.args.get('decision')
    require(status is None or status in ('open','deferred','closed'), 'Invalid case status')
    require(decision is None or decision in DECISIONS[1:], 'Invalid decision filter')
    try:
        offset, limit = int(request.args.get('offset','0')), int(request.args.get('limit','50'))
    except ValueError:
        require(False, 'limit and offset must be integers')
    require(offset >= 0 and 1 <= limit <= 100, 'Invalid pagination range')
    return jsonify(cases.listing(request.args.get('q','').strip(), status, decision,
                                request.args.get('owner','').strip(), offset, limit))


@api.get('/cases/<case_id>')
def reviewed_case(case_id):
    return jsonify(case=cases.record(cases.case_row(case_id),True))


@api.get('/briefings')
def briefing_preview():
    return jsonify(briefings.load(request.args.getlist('case_id')))


@api.post('/briefings/pdf')
def briefing_download():
    from .briefing_pdf import render, UnsupportedPdfText
    data = body()
    require(isinstance(data, dict) and set(data) == {'case_ids', 'snapshots'}, 'Send case_ids and preview snapshots only.')
    payload = briefings.load(data['case_ids'])
    require(isinstance(data['snapshots'], list), 'Preview snapshots are required before downloading.')
    if data['snapshots'] != payload['snapshots']:
        return jsonify(error=dict(code='briefing_changed', message='Saved evidence changed. Review the refreshed briefing before downloading.'), briefing=payload), 409
    # Only server-resolved, freshly validated facts are passed to the renderer.
    try:
        pdf = render(payload)
    except UnsupportedPdfText as error:
        return jsonify(error=dict(code='pdf_font_unsupported', message=str(error))), 422
    name = ('txb-rm-briefing-'+payload['items'][0]['customer_id'] if len(payload['items']) == 1
            else 'txb-rm-briefing-'+str(len(payload['items']))+'-cases')
    import re
    name = re.sub(r'[^A-Za-z0-9_-]', '_', name)[:100]+'.pdf'
    return send_file(BytesIO(pdf), mimetype='application/pdf', as_attachment=True, download_name=name)


@api.put('/cases/<case_id>')
def update_case(case_id):
    return jsonify(case=cases.update(case_id,body()))


@api.post('/cases/<case_id>/follow-ups')
def create_follow_up(case_id):
    return jsonify(case=cases.follow_up(case_id,body())),201


@api.post('/cases/<case_id>/follow-ups/<follow_up_id>/events')
def follow_up_event(case_id,follow_up_id):
    return jsonify(case=cases.follow_up(case_id,body(),follow_up_id)),201
