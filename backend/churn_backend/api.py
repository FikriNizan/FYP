from flask import Blueprint, abort, jsonify, request

from . import repository as repo
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
