# Frozen model artifacts — future integration

The current backend imports completed, verified SHAP exports. It does not load a model binary for new scoring.

The future scorer will need the exact champion binary, categorical/feature schema and ordering, calibration parameters, threshold/target policy, training/evaluation provenance and version/hash manifest. Record their sources and compatibility as one versioned bundle. Do not independently swap a model, calibrator or schema.

Everything except this README is excluded from Git. No fitted model artifact was recreated for this starter. Keep the existing authoritative exports where they are until the integration milestone.
