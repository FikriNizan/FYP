"""Integration tests for evidence imports and decisions, not model evaluation."""
import copy
import csv
import hashlib
import json
import math
import tempfile
import unittest
from pathlib import Path

from churn_backend import create_app
from churn_backend.constants import (CALIBRATION_INTERCEPT, CALIBRATION_SLOPE,
                                      CATEGORIES, PREDICTORS, PROBABILITY_CUTOFF, RAW_BOUNDARY)
from churn_backend.importer import import_demo, import_shap
from churn_backend.validation import ValidationError, sigmoid

ROOT = Path(__file__).resolve().parents[1]


def fixture_export(directory):
    """Small constructed records to test joins/validation; not research results."""
    original = json.loads((ROOT / "demo" / "notebook_case.json").read_text())["record"]
    low = copy.deepcopy(original)
    low.update(cus_id="test-low", raw_probability=.1, review_alert=0)
    low["calibrated_risk"] = sigmoid(CALIBRATION_SLOPE * math.log(.1 / .9) + CALIBRATION_INTERCEPT)
    driver_sum = sum(d["contribution_logodds"] for key in ("higher_risk_drivers", "lower_risk_drivers") for d in low[key])
    low["other_features_contribution_logodds"] = (math.log(low["calibrated_risk"] / (1 - low["calibrated_risk"]))
                                                - low["base_logodds"] - driver_sum
                                                - low["probability_clip_adjustment_logodds"])
    records = []
    for month in ("2024-01-31", "2024-02-29"):
        for template in (original, low):
            record = copy.deepcopy(template)
            record["cutoff_month"] = month
            records.append(record)
    directory.mkdir()
    (directory / "dashboard_explanations.jsonl").write_text("".join(json.dumps(r) + "\n" for r in records))
    with (directory / "feature_values.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["cus_id", "cutoff_month", *PREDICTORS])
        writer.writeheader()
        for record in records:
            row = {name: "fixture" if name in CATEGORIES else 1 for name in PREDICTORS}
            row.update(cus_id=record["cus_id"], cutoff_month=record["cutoff_month"],
                       combined_flow_mean_1m_myr=100, combined_flow_mean_12m_myr=100,
                       estimated_fee_mean_3m_myr=50, estimated_waiver_mean_3m_myr=5, fd_balance_myr=2000)
            for key in ("higher_risk_drivers", "lower_risk_drivers"):
                row.update({driver["feature"]: driver["value"] for driver in record[key]})
            writer.writerow(row)
    drivers = {d["feature"]: d for key in ("higher_risk_drivers", "lower_risk_drivers") for d in original[key]}
    with (directory / "feature_catalog.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["feature", "label", "group", "kind"])
        writer.writeheader()
        for name in PREDICTORS:
            writer.writerow(dict(feature=name, label=drivers.get(name, {}).get("label", name),
                                 group=drivers.get(name, {}).get("group", "Fixture group"),
                                 kind="categorical" if name in CATEGORIES else "numeric"))
    manifest = dict(status="PASS", version="1.0.0", champion="catboost_baseline", predictor_count=78,
                    protocol_sha256=original["protocol_sha256"], rows=4, customers=2, months=2,
                    calibration=dict(slope=CALIBRATION_SLOPE, intercept=CALIBRATION_INTERCEPT),
                    probability_cutoff=PROBABILITY_CUTOFF, raw_boundary=RAW_BOUNDARY,
                    models_fitted=False, calibration_fitted=False, thresholds_changed=False,
                    champion_reselected=False, target_used_as_predictor=False, files={})
    for path in directory.iterdir():
        manifest["files"][path.name] = dict(bytes=path.stat().st_size, sha256=hashlib.sha256(path.read_bytes()).hexdigest())
    (directory / "explainability_manifest.json").write_text(json.dumps(manifest))
    return directory


class BackendTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.config = dict(TESTING=True, DATABASE=str(self.root / "app.sqlite"))
        self.app = create_app(self.config)
        with self.app.app_context():
            self.demo = import_demo()
        self.client = self.app.test_client()
        self.prediction = self.client.get("/api/customers/944").json["customer"]["prediction_id"]

    def tearDown(self):
        self.temp.cleanup()

    def review_body(self, version=0):
        return dict(decision="prioritise", reason="Review observed friction with the customer.",
                    operations_notes="Confirm transaction failures.", finance_notes="Assess available fee estimates.",
                    owner="Example RM", next_action_date="2026-10-20", reviewer="Example reviewer", expected_version=version)

    def test_verified_sample_probability_and_partial_finance(self):
        data = self.client.get("/api/customers/944").json
        self.assertEqual(data["customer"]["calibrated_risk"], .8440919498232807)
        self.assertEqual(data["customer"]["probability_cutoff"], PROBABILITY_CUTOFF)
        self.assertEqual(data["customer"]["feature_count"], 10)
        self.assertIsNone(data["customer"]["finance"]["estimated_monthly_fee_myr"])
        self.assertEqual(data["customer"]["finance"]["non_fd_balance_myr"], 2016997.13)
        self.assertTrue(data["batch"]["source"]["sample_case_only"])
        self.assertIsNone(data["customer"]["actual_attrition"])

    def test_summary_is_sample_population_not_full_month(self):
        result = self.client.get("/api/summary").json
        self.assertEqual(result["population"], 1)
        self.assertEqual(result["flagged_review_counts"]["awaiting_review"], 1)
        self.assertIsNone(result["finance"]["all_estimated_monthly_fee_myr"]["total"])

    def test_review_persists_after_restart_without_changing_evidence(self):
        before = self.client.get("/api/customers/944").json["customer"]
        result = self.client.put(f"/api/predictions/{self.prediction}/review", json=self.review_body())
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.json["review"]["version"], 1)
        restarted = create_app(self.config).test_client()
        after = restarted.get("/api/customers/944").json["customer"]
        self.assertEqual(after["review"]["decision"], "prioritise")
        self.assertEqual(before["explanation"], after["explanation"])
        self.assertEqual(restarted.get("/api/summary").json["flagged_review_counts"]["prioritise"], 1)

    def test_stale_review_cannot_overwrite_a_meeting_decision(self):
        route = f"/api/predictions/{self.prediction}/review"
        self.assertEqual(self.client.put(route, json=self.review_body()).status_code, 200)
        self.assertEqual(self.client.put(route, json=self.review_body()).status_code, 409)
        changed = self.review_body(1)
        changed.update(decision="monitor", reason="Follow up next month.", expected_case_version=1)
        self.assertEqual(self.client.put(route, json=changed).status_code, 200)
        versions = self.client.get(f"/api/predictions/{self.prediction}/review-history").json["items"]
        self.assertEqual([item["version"] for item in versions], [1, 2])

    def test_invalid_review_cannot_write_scores_or_empty_reason(self):
        for change in ({"reason": ""}, {"calibrated_risk": .99}, {"expected_version": True},
                       {"next_action_date": "2026-02-30"}, {"decision": "churner"}):
            body = self.review_body()
            body.update(change)
            self.assertEqual(self.client.put(f"/api/predictions/{self.prediction}/review", json=body).status_code, 422)
        self.assertEqual(self.client.get("/api/customers/944").json["customer"]["review"]["version"], 0)

    def test_action_note_is_dated_and_does_not_relabel_outcome(self):
        route = f"/api/predictions/{self.prediction}/actions"
        body = dict(action_type="rm_visit", action_status="delivered", action_date="2024-03-04",
                    notes="Illustrative action for testing the workflow.", recorded_by="Example RM")
        result = self.client.post(route, json=body)
        self.assertEqual(result.status_code, 201)
        record = self.client.get("/api/customers/944").json["customer"]
        self.assertEqual(len(record["actions"]), 1)
        self.assertEqual(record["calibrated_risk"], .8440919498232807)
        self.assertIsNone(record["actual_attrition"])
        self.assertEqual(self.client.get(route).json["items"][0]["action_date"], "2024-03-04")

    def test_invalid_action_and_cross_origin_write_are_rejected(self):
        body = dict(action_type="rm_visit", action_status="delivered", action_date="2099-01-01",
                    notes="Future visit.", recorded_by="Example RM")
        self.assertEqual(self.client.post(f"/api/predictions/{self.prediction}/actions", json=body).status_code, 422)
        self.assertEqual(self.client.put(f"/api/predictions/{self.prediction}/review", json=self.review_body(),
                                        headers={"Origin": "https://unrelated.example"}).status_code, 403)

    def test_api_filters_pagination_and_errors(self):
        self.assertEqual(self.client.get("/api/customers?flagged=true&decision=awaiting_review&q=944").json["total"], 1)
        self.assertEqual(self.client.get("/api/customers?flagged=false").json["total"], 0)
        for query in ("flagged=yes", "decision=other", "limit=0", "offset=-1", "limit=abc", "month=2024-02-28"):
            self.assertEqual(self.client.get("/api/customers?" + query).status_code, 422)
        self.assertEqual(self.client.get("/api/customers/missing").status_code, 404)
        self.assertEqual(self.client.get("/api/summary?month=2024-03").status_code, 404)
        self.assertEqual(self.client.get("/api/summary?batch_id=" + self.demo["batch_id"] + "&month=2024-03").status_code, 422)
        self.assertEqual(self.client.get("/does-not-exist").json["error"]["code"], "not_found")

    def test_demo_import_is_idempotent_and_keeps_reviews(self):
        self.client.put(f"/api/predictions/{self.prediction}/review", json=self.review_body())
        with self.app.app_context():
            again = import_demo()
        self.assertTrue(again["already_imported"])
        self.assertEqual(len(self.client.get("/api/months").json["items"]), 1)
        self.assertEqual(self.client.get("/api/customers/944").json["customer"]["review"]["version"], 1)

    def test_full_export_import_join_coverage_and_month_isolation(self):
        directory = fixture_export(self.root / "export")
        with self.app.app_context():
            feb = import_shap(directory, "2024-02")
            jan = import_shap(directory, "2024-01")
            duplicate = import_shap(directory, "2024-02")
        self.assertTrue(duplicate["already_imported"])
        self.assertEqual(self.client.get("/api/summary").json["population"], 2)
        record = self.client.get("/api/customers/944").json["customer"]
        self.assertEqual(record["feature_count"], 78)
        self.assertEqual(record["finance"]["estimated_monthly_fee_myr"], 50)
        self.assertEqual(self.client.get("/api/customers?flagged=false").json["total"], 1)
        self.client.put(f"/api/predictions/{record['prediction_id']}/review", json=self.review_body())
        earlier = self.client.get("/api/customers/944?batch_id=" + jan["batch_id"]).json["customer"]
        self.assertEqual(earlier["review"]["decision"], "awaiting_review")
        history = self.client.get("/api/customers/944/history?batch_id=" + feb["batch_id"]).json["items"]
        self.assertEqual([row["cutoff_month"] for row in history], ["2024-01-31", "2024-02-29"])
        self.assertEqual(len(self.client.get("/api/customers/944/history?batch_id=" + jan["batch_id"]).json["items"]), 1)

    def test_tampered_import_leaves_published_data_unchanged(self):
        directory = fixture_export(self.root / "export")
        path = directory / "dashboard_explanations.jsonl"
        path.write_text(path.read_text().replace('"calibrated_risk": 0.844', '"calibrated_risk": 0.944'))
        with self.app.app_context():
            with self.assertRaises(ValidationError):
                import_shap(directory, "2024-02")
        self.assertEqual(len(self.client.get("/api/months").json["items"]), 1)

    def test_import_rejects_non_reconstructing_explanation_even_with_updated_hash(self):
        directory = fixture_export(self.root / "export")
        path = directory / "dashboard_explanations.jsonl"
        records = [json.loads(line) for line in path.read_text().splitlines()]
        records[0]["other_features_contribution_logodds"] += 1
        path.write_text("".join(json.dumps(row) + "\n" for row in records))
        manifest_path = directory / "explainability_manifest.json"
        manifest = json.loads(manifest_path.read_text())
        manifest["files"][path.name] = dict(bytes=path.stat().st_size, sha256=hashlib.sha256(path.read_bytes()).hexdigest())
        manifest_path.write_text(json.dumps(manifest))
        with self.app.app_context():
            with self.assertRaisesRegex(ValidationError, "reconstruct"):
                import_shap(directory, "2024-01")

    def test_future_flows_are_absent_from_imported_snapshot(self):
        directory = fixture_export(self.root / "export")
        flow_file = self.root / "flows.csv"
        columns = ["cus_id", "snapshot_month", "inbound_myr", "inbound_count", "outbound_success_myr",
                   "outbound_success_count", "source_complete", "combined_flow_myr"]
        with flow_file.open("w", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=columns)
            writer.writeheader()
            for customer in ("944", "test-low"):
                for month in ("2024-01-31", "2024-02-29", "2024-03-31"):
                    writer.writerow(dict(cus_id=customer, snapshot_month=month, inbound_myr=30, inbound_count=1,
                                         outbound_success_myr=70, outbound_success_count=1,
                                         source_complete=True, combined_flow_myr=100))
        with self.app.app_context():
            result = import_shap(directory, "2024-02", flows_path=flow_file)
        data = self.client.get("/api/customers/944?batch_id=" + result["batch_id"]).json["customer"]
        self.assertEqual([row["snapshot_month"] for row in data["flow_history"]], ["2024-01-31", "2024-02-29"])

    def test_cli_import_and_help(self):
        directory = fixture_export(self.root / "export")
        runner = self.app.test_cli_runner()
        result = runner.invoke(args=["import-shap", "--directory", str(directory), "--month", "2024-02"])
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertEqual(json.loads(result.output)["records"], 2)
        result = runner.invoke(args=["import-shap", "--directory", str(directory), "--month", "2024-03"])
        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("Requested month", result.output)

    def test_selected_sample_history_does_not_switch_to_another_batch(self):
        directory = fixture_export(self.root / "export")
        with self.app.app_context():
            import_shap(directory, "2024-02")
        history = self.client.get("/api/customers/944/history?batch_id=" + self.demo["batch_id"]).json["items"]
        self.assertEqual(history[-1]["prediction_id"], self.prediction)

    def test_customer_names_join_by_identifier(self):
        directory = fixture_export(self.root / "export")
        master = self.root / "customers.csv"
        master.write_text("cus_id,cus_name\ntest-low,Example B\n944,Example A\n")
        with self.app.app_context():
            result = import_shap(directory, "2024-02", customer_master=master)
        data = self.client.get("/api/customers/944?batch_id=" + result["batch_id"]).json
        self.assertEqual(data["customer"]["customer_name"], "Example A")

    def test_other_protocol_and_target_leakage_are_rejected(self):
        directory = fixture_export(self.root / "export")
        path = directory / "dashboard_explanations.jsonl"
        original_text = path.read_text()
        manifest_path = directory / "explainability_manifest.json"
        manifest = json.loads(manifest_path.read_text())
        for altered in (original_text.replace("6ae6d17ef0dcb7c3b0b7e090bed0dbae475024f5c0606f71ad100411adb5a4dc", "a" * 64),
                        original_text.replace('"schema_version":', '"target_churn": 1, "schema_version":')):
            path.write_text(altered)
            manifest["files"][path.name] = dict(bytes=path.stat().st_size, sha256=hashlib.sha256(path.read_bytes()).hexdigest())
            manifest_path.write_text(json.dumps(manifest))
            with self.app.app_context():
                with self.assertRaises(ValidationError):
                    import_shap(directory, "2024-02")

    def test_distinct_simultaneous_review_attempts_only_one_succeeds(self):
        import concurrent.futures
        def save():
            client = self.app.test_client()
            return client.put(f"/api/predictions/{self.prediction}/review", json=self.review_body()).status_code
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            statuses = list(executor.map(lambda unused: save(), range(2)))
        self.assertEqual(sorted(statuses), [200, 409])

    def test_health_readiness_and_json_validation(self):
        self.assertEqual(self.client.get("/api/health").json["status"], "ok")
        self.assertFalse(self.client.get("/api/metadata").json["live_model_scoring"])
        route = f"/api/predictions/{self.prediction}/review"
        self.assertEqual(self.client.put(route, data="{broken", content_type="application/json").status_code, 422)
        self.assertEqual(self.client.put(route, data='{"decision":"monitor","decision":"prioritise"}',
                                        content_type="application/json").status_code, 422)
        self.assertEqual(self.client.put(route, data="[]", content_type="application/json").status_code, 422)

    def test_action_date_uses_malaysian_business_date(self):
        from datetime import date
        from unittest.mock import patch
        body = dict(action_type="customer_contact", action_status="delivered", action_date="2026-10-15",
                    notes="Software test only.", recorded_by="Example RM")
        with patch("churn_backend.validation.business_today", return_value=date(2026, 10, 15)):
            self.assertEqual(self.client.post(f"/api/predictions/{self.prediction}/actions", json=body).status_code, 201)


if __name__ == "__main__":
    unittest.main()
