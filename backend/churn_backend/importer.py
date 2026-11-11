"""Read completed local SHAP exports. No model fitting or pickle loading."""
import csv
import hashlib
import re
from pathlib import Path

from .constants import (CALIBRATION_INTERCEPT, CALIBRATION_SLOPE, CATEGORIES,
                        MODEL, PREDICTORS, PROBABILITY_CUTOFF, RAW_BOUNDARY)
from .repository import save_batch
from .validation import (ValidationError, finite, month_end, require,
                         strict_json, validate_record)


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def csv_rows(path):
    with Path(path).open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        require(reader.fieldnames is not None and len(set(reader.fieldnames)) == len(reader.fieldnames),
                f"Missing or duplicated columns in {Path(path).name}")
        columns = reader.fieldnames
        rows = list(reader)
    require(all(None not in row and all(value is not None for value in row.values()) for row in rows),
            f"Malformed CSV row in {Path(path).name}")
    return columns, rows


def number(value, name, missing=False):
    if value == "" and missing:
        return None
    try:
        parsed = float(value)
    except (ValueError, TypeError) as exc:
        raise ValidationError(f"Invalid numeric value in {name}") from exc
    return finite(parsed, name)


def checked_file(directory, manifest, filename):
    files = manifest.get("files")
    require(isinstance(files, dict), "Invalid manifest file ledger")
    info = files.get(filename)
    require(isinstance(info, dict), f"Missing file entry: {filename}")
    path = directory / filename
    require(path.is_file(), f"Missing export file: {filename}")
    require(path.stat().st_size == info.get("bytes") and sha256(path) == info.get("sha256"),
            f"Checksum/size mismatch: {filename}")
    return path


def read_features(path):
    columns, rows = csv_rows(path)
    require(set(columns) == {"cus_id", "cutoff_month", *PREDICTORS} and len(columns) == 80,
            "feature_values.csv must contain exactly the two keys and 78 accepted predictors")
    result = {}
    for row in rows:
        key = (row["cus_id"], month_end(row["cutoff_month"]))
        require(bool(key[0].strip()) and key not in result, "Invalid/duplicate feature-table key")
        result[key] = {name: (row[name] or None) if name in CATEGORIES else
                       number(row[name], name, missing=True) for name in PREDICTORS}
    return result


def read_customer_master(path, selected_ids, allow_missing=False):
    if path is None:
        return {}
    columns, rows = csv_rows(path)
    require({"cus_id", "cus_name"}.issubset(columns), "Customer master needs cus_id and cus_name")
    result, seen = {}, set()
    for row in rows:
        require(bool(re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,199}',row["cus_id"]))
                and row["cus_id"] not in seen, "Invalid/duplicate master customer")
        seen.add(row["cus_id"])
        if row["cus_id"] in selected_ids:
            require(len(row["cus_name"]) <= 500, "Customer name exceeds 500 characters")
            result[row["cus_id"]] = dict(customer_name=row["cus_name"] or None)
    if not allow_missing:
        require(selected_ids <= seen, "Customer master does not cover the selected month")
    return result


def read_flows(path, month, selected_ids, features, allow_missing=False):
    if path is None:
        return {}
    columns, rows = csv_rows(path)
    required = {"cus_id", "snapshot_month", "inbound_myr", "inbound_count",
                "outbound_success_myr", "outbound_success_count", "source_complete", "combined_flow_myr"}
    require(set(columns) == required, "monthly_flows.csv columns differ from the ETL export")
    result = {customer: [] for customer in selected_ids}
    seen = set()
    for row in rows:
        stamp = month_end(row["snapshot_month"])
        if stamp > month or row["cus_id"] not in selected_ids:
            continue  # Future observations never enter this snapshot's evidence.
        key = (row["cus_id"], stamp)
        require(key not in seen, "Duplicate monthly flow key")
        seen.add(key)
        require(row["source_complete"].lower() in ("true", "1"), "Incomplete flow source")
        flow = dict(snapshot_month=stamp)
        for name in ("inbound_myr", "outbound_success_myr", "combined_flow_myr",
                     "inbound_count", "outbound_success_count"):
            value = number(row[name], name)
            require(value >= 0, f"Negative flow/count in {name}")
            if name.endswith("_count"):
                require(value.is_integer(), "Flow counts must be integers")
                value = int(value)
            flow[name] = value
        require(abs(flow["inbound_myr"] + flow["outbound_success_myr"] - flow["combined_flow_myr"]) <= .011,
                "Combined flow does not reconcile")
        result[row["cus_id"]].append(flow)
    for customer, history in result.items():
        history.sort(key=lambda item: item["snapshot_month"])
        if allow_missing and (not history or history[-1]["snapshot_month"] != month):
            result[customer] = []
            continue
        require(history and history[-1]["snapshot_month"] == month, "Missing selected-month flow")
        current = features[(customer, month)]["combined_flow_mean_1m_myr"]
        require(current is not None and abs(history[-1]["combined_flow_myr"] - current) <= .011,
                "Monthly flow differs from the saved feature snapshot")
        result[customer] = history[-12:]
    return result


def import_shap(directory, month, customer_master=None, flows_path=None):
    directory = Path(directory).resolve()
    month = month_end(month, allow_short=True)
    manifest_path = directory / "explainability_manifest.json"
    require(manifest_path.is_file(), "explainability_manifest.json was not found")
    manifest = strict_json(manifest_path.read_text(encoding="utf-8"))
    require(isinstance(manifest, dict), "Invalid explainability manifest")
    require(manifest.get("status") == "PASS" and manifest.get("champion") == MODEL
            and manifest.get("version") == "1.0.0" and manifest.get("predictor_count") == 78,
            "Export is not a successful v1 champion explanation run")
    for flag in ("models_fitted", "calibration_fitted", "thresholds_changed", "champion_reselected",
                 "target_used_as_predictor"):
        require(manifest.get(flag) is False, f"Unsafe or missing export flag: {flag}")
    calibration = manifest.get("calibration", {})
    require(isinstance(calibration, dict), "Invalid calibration metadata")
    for field, expected in (("slope", CALIBRATION_SLOPE), ("intercept", CALIBRATION_INTERCEPT)):
        require(abs(finite(calibration.get(field), field) - expected) <= 1e-12,
                "Calibration differs from the full-data champion; the 20-customer fixture is not accepted")
    for field, expected in (("probability_cutoff", PROBABILITY_CUTOFF), ("raw_boundary", RAW_BOUNDARY)):
        require(abs(finite(manifest.get(field), field) - expected) <= 1e-14, "Frozen policy differs")
    paths = {name: checked_file(directory, manifest, name) for name in
             ("dashboard_explanations.jsonl", "feature_values.csv", "feature_catalog.csv")}
    columns, catalog = csv_rows(paths["feature_catalog.csv"])
    require({"feature", "label", "group", "kind"}.issubset(columns) and len(catalog) == 78
            and {row["feature"] for row in catalog} == set(PREDICTORS), "Feature catalog differs")
    catalog_by_name = {row["feature"]: row for row in catalog}
    for name, row in catalog_by_name.items():
        require(row["kind"] == ("categorical" if name in CATEGORIES else "numeric"), "Feature kinds differ")
    features = read_features(paths["feature_values.csv"])
    records, seen = [], set()
    with paths["dashboard_explanations.jsonl"].open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            record = validate_record(strict_json(line))
            key = (record["cus_id"], record["cutoff_month"])
            require(key not in seen and key in features, f"Repeated/unmatched explanation at line {line_number}")
            require(record["protocol_sha256"] == manifest.get("protocol_sha256"), "Protocol identity differs")
            seen.add(key)
            for driver in record["higher_risk_drivers"] + record["lower_risk_drivers"]:
                field = driver["feature"]
                actual, expected = driver["value"], features[key][field]
                require(driver["label"] == catalog_by_name[field]["label"]
                        and driver["group"] == catalog_by_name[field]["group"], "Driver catalog differs")
                if isinstance(actual, (int, float)) and isinstance(expected, (int, float)):
                    require(abs(actual - expected) <= 1e-8 * max(1, abs(actual)), "Driver value differs from features")
                else:
                    require(actual == expected, "Driver value differs from features")
            records.append(record)
    require(seen == set(features), "Features and explanations do not cover the same customer-months")
    require(len(records) == manifest.get("rows")
            and len({key[0] for key in seen}) == manifest.get("customers")
            and len({key[1] for key in seen}) == manifest.get("months"), "Export population differs")
    selected = [record for record in records if record["cutoff_month"] == month]
    require(bool(selected), "Requested month is not present in this export")
    selected_ids = {record["cus_id"] for record in selected}
    require(all(features[(customer, month)]["combined_flow_mean_12m_myr"] is not None
                and features[(customer, month)]["combined_flow_mean_12m_myr"] > 0
                for customer in selected_ids), "Selected customers need a positive historical flow baseline")
    master = read_customer_master(customer_master, selected_ids)
    flows = read_flows(flows_path, month, selected_ids, features)
    entries = [dict(evidence=record, features=features[(record["cus_id"], month)],
                    customer=master.get(record["cus_id"], {}), flows=flows.get(record["cus_id"], []))
               for record in sorted(selected, key=lambda record: record["cus_id"])]
    source = dict(description="Saved full-data champion SHAP export; historical synthetic data",
                  export_manifest_sha256=sha256(manifest_path), export_rows=manifest["rows"],
                  selected_month_rows=len(selected), full_feature_values=True,
                  customer_names_loaded=customer_master is not None, flow_history_loaded=flows_path is not None,
                  verified_files={name: manifest["files"][name]["sha256"] for name in paths})
    for name, path in (("customer_master_sha256", customer_master), ("flow_file_sha256", flows_path)):
        if path is not None:
            source[name] = sha256(path)
    return save_batch(month, "saved_shap_export", manifest["protocol_sha256"], entries, source)


def import_demo():
    path = Path(__file__).parent.parent / "demo" / "notebook_case.json"
    demo = strict_json(path.read_text(encoding="utf-8"))
    record = validate_record(demo["record"])
    partial = {driver["feature"]: driver["value"] for driver in
               record["higher_risk_drivers"] + record["lower_risk_drivers"]}
    source = dict(description="One exact case extracted from the user's executed full-data SHAP notebook",
                  notebook_sha256=demo["notebook_sha256"], sample_case_only=True,
                  full_feature_values=False, selected_month_rows=1,
                  note="This is not the full February population; 68 feature values, names and flow history are absent.")
    return save_batch(record["cutoff_month"], "notebook_case_sample", record["protocol_sha256"],
                      [dict(evidence=record, features=partial)], source)
