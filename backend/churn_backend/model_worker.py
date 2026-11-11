"""Isolated trusted scorer. No uploaded paths or executable content are loaded."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import time

sys.dont_write_bytecode = True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--research-root', required=True)
    parser.add_argument('--features', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    directory = Path(__file__).resolve().parent
    root = Path(args.research_root).resolve()
    contract = json.loads((directory/'scorer_contract.json').read_text(encoding='utf-8'))
    def fingerprints():
        for relative, expected in contract['files'].items():
            path = (root/relative).resolve()
            if not path.is_relative_to(root) or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
                raise ValueError('Trusted scorer artifact fingerprint mismatch: ' + relative)
    fingerprints()
    spec = importlib.util.spec_from_file_location('frozen_constants', directory/'constants.py')
    constants = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(constants)
    sys.path.insert(0, str(root))
    import pandas as pd
    from shap_explainability_v1 import load_context, explain_rows, dashboard_record
    started = time.perf_counter()
    context = load_context(root/'data/models/frozen_experiment_v1', root/'data/models/final_refit_v1')
    if (context['protocol_sha256'] != constants.PROTOCOL_SHA256 or
        list(context['predictors']) != constants.PREDICTORS or
        list(context['categories']) != constants.CATEGORIES or
        context['model'].raw_boundary != constants.RAW_BOUNDARY or
        context['model'].probability_cutoff != constants.PROBABILITY_CUTOFF or
        context['slope'] != constants.CALIBRATION_SLOPE or
        context['intercept'] != constants.CALIBRATION_INTERCEPT):
        raise ValueError('Loaded scorer differs from frozen application policy')
    loaded = time.perf_counter()
    numeric = [name for name in constants.PREDICTORS if name not in constants.CATEGORIES]
    frame = pd.read_csv(args.features, dtype={**{key:'string' for key in ['cus_id','cutoff_month']+constants.CATEGORIES},
                                             **{key:'float64' for key in numeric}},
                        keep_default_na=False, na_values=[''], float_precision='round_trip')
    result = explain_rows(context, frame, batch_size=1000, progress=False)
    records = [dashboard_record(context, result, i, top_k=5) for i in range(len(frame))]
    fingerprints()
    output = dict(records=records, csv_sha256=hashlib.sha256(Path(args.features).read_bytes()).hexdigest(),
                  protocol_sha256=constants.PROTOCOL_SHA256, champion_sha256=contract['champion_sha256'],
                  provenance=dict(adapter_version='1.0.0', trusted_contract_sha256=hashlib.sha256((directory/'scorer_contract.json').read_bytes()).hexdigest(),
                                  context_seconds=loaded-started, explanation_seconds=time.perf_counter()-loaded,
                                  checks=result['checks'], top_k=5))
    Path(args.output).write_text(json.dumps(output, allow_nan=False), encoding='utf-8')


if __name__ == '__main__':
    main()
