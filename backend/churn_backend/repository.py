"""Immutable evidence snapshots; reviews and dated actions are separate records."""
import hashlib
import json
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


def batches():
    rows = get_db().execute("SELECT * FROM batches ORDER BY cutoff_month DESC, imported_at DESC").fetchall()
    return [batch_record(row) for row in rows]


def batch_record(row):
    return dict(batch_id=row["batch_id"], cutoff_month=row["cutoff_month"],
                source_kind=row["source_kind"], record_count=row["record_count"],
                protocol_sha256=row["protocol_sha256"], imported_at=row["imported_at"],
                source=json.loads(row["source_json"]))


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
    evidence = json.loads(row["evidence_json"])
    record = dict(prediction_id=row["prediction_id"], batch_id=row["batch_id"], cus_id=row["cus_id"],
                  cutoff_month=evidence["cutoff_month"], customer_name=customer.get("customer_name"),
                  sector_code=features.get("sector_code"), tier_id=features.get("tier_id"),
                  customer_type=features.get("customer_type"), calibrated_risk=row["risk"],
                  review_alert=bool(row["review_alert"]), probability_cutoff=evidence["probability_cutoff"],
                  review=review_record(row["prediction_id"]),
                  finance={label: features.get(field) for label, field in FINANCE_FIELDS.items()})
    if detail:
        record.update(explanation=evidence, features=features,
                      feature_count=len(features), operations={name: features.get(name) for name in OPS_FIELDS},
                      flow_history=json.loads(row["flows_json"]), actions=action_records(row["prediction_id"]),
                      assessment_window_end=horizon_end(evidence["cutoff_month"]),
                      outcome_status="not_loaded", actual_attrition=None,
                      finance_note="Fee and waiver figures are historical three-month monthly estimates; "
                                   "balances are exposures. These are not verified profit or retention savings.")
    return record


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
        saved = {key: value for key, value in body.items() if key != "expected_version"}
        version, timestamp = existing["version"] + 1, now()
        db.execute("INSERT INTO reviews VALUES (?,?,?,?) ON CONFLICT(prediction_id) "
                   "DO UPDATE SET version=excluded.version, body_json=excluded.body_json, "
                   "updated_at=excluded.updated_at", (prediction_id, version, encode(saved), timestamp))
        db.execute("INSERT INTO review_history(prediction_id,version,body_json,saved_at) VALUES (?,?,?,?)",
                   (prediction_id, version, encode(saved), timestamp))
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
