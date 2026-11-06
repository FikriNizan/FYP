"""The frozen full-development champion policy, never fitted by this app."""
import json
from pathlib import Path

VERSION = "0.3.0"
MODEL = "catboost_baseline"
PROTOCOL_SHA256 = "6ae6d17ef0dcb7c3b0b7e090bed0dbae475024f5c0606f71ad100411adb5a4dc"
RAW_BOUNDARY = 0.2991379097436803
PROBABILITY_CUTOFF = 0.2586013233784648
CALIBRATION_SLOPE = 0.9588242871048336
CALIBRATION_INTERCEPT = -0.23690175755868847
SCHEMA = json.loads((Path(__file__).parent / "feature_schema.json").read_text())
PREDICTORS = SCHEMA["predictor_columns"]
CATEGORIES = SCHEMA["categorical_columns"]
DECISIONS = ("awaiting_review", "prioritise", "monitor", "no_immediate_action")
ACTION_TYPES = ("rm_visit", "customer_contact", "service_fix", "other")
ACTION_STATUSES = ("planned", "attempted", "delivered", "cancelled")
FINANCE_FIELDS = {
    "estimated_monthly_fee_myr": "estimated_fee_mean_3m_myr",
    "estimated_monthly_waiver_myr": "estimated_waiver_mean_3m_myr",
    "fd_balance_myr": "fd_balance_myr",
    "non_fd_balance_myr": "non_fd_balance_myr",
}
OPS_FIELDS = (
    "combined_flow_mean_1m_myr", "combined_flow_mean_3m_myr",
    "combined_flow_mean_12m_myr", "combined_flow_ratio_3m_to_12m",
    "inbound_flow_ratio_3m_to_12m", "outbound_flow_ratio_3m_to_12m",
    "login_failure_rate_3m", "outbound_failure_rate_3m",
    "outbound_bank_failure_rate_3m", "passive_session_rate_3m",
    "session_transactions_mean_3m",
)
