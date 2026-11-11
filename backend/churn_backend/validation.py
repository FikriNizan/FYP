"""Validate saved evidence and human input before any database write."""
import calendar
import json
import math
import re
from datetime import date, datetime, timedelta, timezone

from .constants import (ACTION_STATUSES, ACTION_TYPES, CALIBRATION_INTERCEPT,
                        CALIBRATION_SLOPE, DECISIONS, MODEL, PREDICTORS,
                        PROBABILITY_CUTOFF, PROTOCOL_SHA256, RAW_BOUNDARY)


class ValidationError(ValueError):
    pass


class ConflictError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise ValidationError(message)


def strict_json(text):
    def bad_constant(value):
        raise ValidationError(f"Non-finite JSON constant: {value}")

    def unique_object(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result, f"Duplicate JSON field: {key}")
            result[key] = value
        return result

    try:
        return json.loads(text, parse_constant=bad_constant, object_pairs_hook=unique_object)
    except json.JSONDecodeError as exc:
        raise ValidationError("Invalid JSON") from exc


def iso_date(value, label="date"):
    require(isinstance(value, str) and bool(re.fullmatch(r"\d{4}-\d{2}-\d{2}", value)),
            f"{label} must be YYYY-MM-DD")
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValidationError(f"Invalid {label}") from exc


def month_end(value, allow_short=False):
    if allow_short and isinstance(value, str) and re.fullmatch(r"\d{4}-\d{2}", value):
        try:
            year, month = map(int, value.split("-"))
            value = date(year, month, calendar.monthrange(year, month)[1]).isoformat()
        except ValueError as exc:
            raise ValidationError("Invalid month") from exc
    parsed = iso_date(value, "month")
    require(parsed.day == calendar.monthrange(parsed.year, parsed.month)[1],
            "Month must be a month-end date")
    return parsed.isoformat()


def horizon_end(cutoff):
    parsed = iso_date(cutoff)
    year, zero_month = divmod(parsed.year * 12 + parsed.month - 1 + 3, 12)
    return date(year, zero_month + 1, calendar.monthrange(year, zero_month + 1)[1]).isoformat()


def finite(value, label):
    require(isinstance(value, (int, float)) and not isinstance(value, bool),
            f"{label} must be numeric")
    require(math.isfinite(value), f"{label} must be finite")
    return float(value)


def sigmoid(value):
    if value >= 0:
        return 1.0 / (1.0 + math.exp(-value))
    exp_value = math.exp(value)
    return exp_value / (1.0 + exp_value)


def business_today():
    return datetime.now(timezone(timedelta(hours=8))).date()


def text_field(body, key, maximum=4000, required=False):
    value = body.get(key, "")
    require(isinstance(value, str), f"{key} must be text")
    value = value.strip()
    require(len(value) <= maximum, f"{key} exceeds {maximum} characters")
    require(not required or bool(value), f"{key} is required")
    return value


RECORD_FIELDS = {
    "schema_version", "model", "protocol_sha256", "cus_id", "cutoff_month",
    "calibrated_risk", "review_alert", "probability_cutoff", "raw_boundary",
    "raw_probability", "explanation_units", "base_logodds", "reference_probability",
    "probability_clip_adjustment_logodds", "higher_risk_drivers", "lower_risk_drivers",
    "other_features_contribution_logodds", "interpretation",
}


def validate_record(record):
    require(isinstance(record, dict) and set(record) == RECORD_FIELDS,
            "Explanation fields differ from the v1 target-free export schema")
    require(record["schema_version"] == "1.0.0" and record["model"] == MODEL,
            "Explanation is not the accepted champion export")
    require(isinstance(record["protocol_sha256"], str)
            and bool(re.fullmatch(r"[a-f0-9]{64}", record["protocol_sha256"])),
            "Invalid protocol checksum")
    require(record["protocol_sha256"] == PROTOCOL_SHA256,
            "Protocol identity differs from the accepted full-data experiment")
    require(isinstance(record["cus_id"], str) and record["cus_id"].strip()
            and len(record["cus_id"]) <= 200, "Invalid customer ID")
    month_end(record["cutoff_month"])
    for key in ("calibrated_risk", "raw_probability", "reference_probability"):
        require(0 <= finite(record[key], key) <= 1, f"{key} must be between zero and one")
    for key, expected in (("probability_cutoff", PROBABILITY_CUTOFF),
                          ("raw_boundary", RAW_BOUNDARY)):
        require(abs(finite(record[key], key) - expected) <= 1e-14,
                f"{key} differs from the frozen full-data policy")
    require(type(record["review_alert"]) is int and record["review_alert"] in (0, 1),
            "review_alert must be 0 or 1")
    require(record["review_alert"] == int(record["raw_probability"] >= RAW_BOUNDARY),
            "Review flag differs from the full-precision raw boundary")
    require(record["explanation_units"] ==
            "calibrated log-odds; not probability percentage points", "Incorrect explanation units")
    require(isinstance(record["interpretation"], str), "Missing explanation interpretation")
    total = finite(record["base_logodds"], "base_logodds")
    total += finite(record["other_features_contribution_logodds"], "other_features")
    total += finite(record["probability_clip_adjustment_logodds"], "clipping adjustment")
    seen = set()
    for key, sign in (("higher_risk_drivers", 1), ("lower_risk_drivers", -1)):
        require(isinstance(record[key], list) and len(record[key]) <= 78, "Invalid driver list")
        for driver in record[key]:
            require(isinstance(driver, dict) and set(driver) ==
                    {"feature", "label", "group", "value", "contribution_logodds"},
                    "Invalid driver fields")
            name = driver["feature"]
            require(isinstance(name, str) and name in PREDICTORS and name not in seen,
                    "Unknown or repeated explanation feature")
            seen.add(name)
            for field in ("label", "group"):
                require(isinstance(driver[field], str) and driver[field].strip(),
                        "Invalid driver label/group")
            value = driver["value"]
            require(value is None or isinstance(value, (str, int, float))
                    and not isinstance(value, bool), "Invalid driver value")
            if isinstance(value, (float, int)):
                finite(value, "driver value")
            contribution = finite(driver["contribution_logodds"], "contribution")
            require(sign * contribution > 0, "Explanation direction is inconsistent")
            total += contribution
    require(math.isfinite(total), "Explanation sum is not finite")
    require(abs(sigmoid(total) - record["calibrated_risk"]) <= 2e-10,
            "Explanation does not reconstruct the saved probability")
    require(abs(sigmoid(record["base_logodds"]) - record["reference_probability"]) <= 2e-10,
            "Reference probability differs from the explanation base")
    clipped = min(max(record["raw_probability"], 1e-12), 1 - 1e-12)
    calibrated = sigmoid(CALIBRATION_SLOPE * math.log(clipped / (1 - clipped))
                         + CALIBRATION_INTERCEPT)
    require(abs(calibrated - record["calibrated_risk"]) <= 2e-10,
            "Probability differs from the saved sigmoid calibration")
    return record


def validate_review(body):
    fields = {"decision", "reason", "operations_notes", "finance_notes", "owner",
              "next_action_date", "reviewer", "expected_version", "case_id", "expected_case_version"}
    require(isinstance(body, dict) and not set(body) - fields, "Unknown review fields")
    require(body.get("decision") in DECISIONS[1:], "Choose prioritise, monitor or no_immediate_action")
    version = body.get("expected_version")
    require(type(version) is int and version >= 0, "expected_version must be a non-negative integer")
    case_id = body.get('case_id')
    require(case_id is None or isinstance(case_id,str) and re.fullmatch(r'[A-Za-z0-9_-]{1,128}',case_id), 'Invalid case_id')
    case_version = body.get('expected_case_version')
    require(case_version is None or type(case_version) is int and case_version >= 1, 'Invalid expected_case_version')
    next_date = body.get("next_action_date")
    if next_date is not None:
        iso_date(next_date, "next_action_date")
    return dict(decision=body["decision"], reason=text_field(body, "reason", required=True),
                operations_notes=text_field(body, "operations_notes"),
                finance_notes=text_field(body, "finance_notes"),
                owner=text_field(body, "owner", maximum=200), next_action_date=next_date,
                reviewer=text_field(body, "reviewer", maximum=200, required=True),
                expected_version=version,case_id=case_id,expected_case_version=case_version)


def validate_action(body):
    fields = {"action_type", "action_status", "action_date", "notes", "recorded_by"}
    require(isinstance(body, dict) and not set(body) - fields, "Unknown action fields")
    require(body.get("action_type") in ACTION_TYPES, "Invalid action_type")
    require(body.get("action_status") in ACTION_STATUSES, "Invalid action_status")
    action_date = iso_date(body.get("action_date"), "action_date")
    if body["action_status"] in ("attempted", "delivered"):
        require(action_date <= business_today(), "An actual action cannot have a future date")
    return dict(action_type=body["action_type"], action_status=body["action_status"],
                action_date=action_date.isoformat(), notes=text_field(body, "notes", required=True),
                recorded_by=text_field(body, "recorded_by", maximum=200, required=True))
