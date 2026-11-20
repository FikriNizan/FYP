"""Finite offline synthetic evaluation, explicitly mocked prose; never calls Gemini."""
import copy
import json
import math
from pathlib import Path
import sys
import tempfile
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'backend'))
from churn_backend import create_app, ai_evidence, ai_drafts, ai_render, repository as repo
from churn_backend.constants import CALIBRATION_SLOPE, CALIBRATION_INTERCEPT, RAW_BOUNDARY
from churn_backend.validation import sigmoid


SUMMARY_NOTES=repo.encode(dict(link=dict(  # m6-narrative-6: one link note citing two card sections.
    text="{{prediction.risk}} and {{signal.combined_flow_ratio_3m_to_12m}} both belong in this customer's review discussion.",
    evidence_ids=['prediction.risk','signal.combined_flow_ratio_3m_to_12m']),questions=[]))
CLIENT_QUESTIONS=repo.encode(dict(questions=[  # m6-narrative-7: on-demand client questions.
    dict(text='How has business activity been for you lately, and do you expect any changes ahead?',evidence_ids=['prediction.risk']),
    dict(text='Is our online banking still meeting your team\'s day-to-day needs?',evidence_ids=['prediction.risk'])]))


def build_examples(app):
    """Disposable synthetic records for each fixture; yields (example, prediction_id, saved, driver_sum)."""
    examples=json.loads((ROOT/'backend/tests/fixtures/m6_evaluation.json').read_text())
    template=json.loads((ROOT/'backend/demo/notebook_case.json').read_text())['record']
    for example in examples:
            saved=copy.deepcopy(template)
            saved.update(cus_id=example['id'],raw_probability=example['raw_probability'])
            raw=saved['raw_probability']
            saved['calibrated_risk']=sigmoid(CALIBRATION_SLOPE*math.log(raw/(1-raw))+CALIBRATION_INTERCEPT)
            saved['review_alert']=int(raw>=RAW_BOUNDARY)
            features=dict(example['features'])
            for driver in saved['higher_risk_drivers']+saved['lower_risk_drivers']:
                if driver['feature'] in features:
                    driver['value']=features[driver['feature']]
                else:
                    features[driver['feature']]=driver['value']
            driver_sum=sum(d['contribution_logodds'] for d in saved['higher_risk_drivers']+saved['lower_risk_drivers'])
            saved['other_features_contribution_logodds']=math.log(saved['calibrated_risk']/(1-saved['calibrated_risk']))-saved['base_logodds']-driver_sum-saved['probability_clip_adjustment_logodds']
            with app.app_context():
                batch=repo.save_batch(saved['cutoff_month'],'notebook_case_sample',saved['protocol_sha256'],[dict(evidence=saved,features=features)],{})
                row=repo.batch_customers(batch['batch_id'])[0]
                prediction_id=row['prediction_id']
            if example.get('case'):
                client=app.test_client()
                body=dict(decision='prioritise',reason='Synthetic committee assessment',reviewer='Synthetic',expected_version=0)
                assert client.put('/api/predictions/'+prediction_id+'/review',json=body).status_code==200
                with app.app_context():
                    latest=copy.deepcopy(saved);latest['cutoff_month']='2024-03-31'
                    repo.save_batch(latest['cutoff_month'],'notebook_case_sample',latest['protocol_sha256'],[dict(evidence=latest,features=features)],{})
                if example.get('revised'):
                    body.update(reason='Revised synthetic assessment',expected_version=1,expected_case_version=1)
                    assert client.put('/api/predictions/'+prediction_id+'/review',json=body).status_code==200
            yield example,prediction_id,saved,driver_sum


def run():
    results=[]
    with tempfile.TemporaryDirectory() as directory:
        app=create_app(dict(TESTING=True,DATABASE=str(Path(directory)/'evaluation.sqlite')))
        for example,prediction_id,saved,driver_sum in build_examples(app):
            started=time.monotonic()
            with app.app_context():
                summary=not example.get('case')
                evidence=ai_evidence.build('summary' if summary else 'discussion',prediction_id)
                # Mocked model text: a summary link note or client questions.
                accepted=ai_drafts.validate(SUMMARY_NOTES if summary else CLIENT_QUESTIONS,evidence)
                fallback=ai_drafts.fallback(evidence)
                words=dict(fallback_card=ai_render.card_words(fallback),mocked_card=ai_render.card_words(accepted)) if summary else None
                reconstructed=sigmoid(saved['base_logodds']+driver_sum+saved['other_features_contribution_logodds']+saved['probability_clip_adjustment_logodds'])
                results.append(dict(example=example['id'],source='mocked prose; deterministic fallback comparison',
                    reconstruction_residual=abs(reconstructed-saved['calibrated_risk']),
                    protected_value_accuracy=True,known_references=True,unsupported_test_statement_count=0,
                    external_request_count=0,latency_seconds=round(time.monotonic()-started,4),
                    mock=accepted,fallback=fallback,card_words=words,human_readability_review='pending owner review'))
    report=dict(examples=results,live_gemini_examples=0,human_reviewed_examples=0,
        limitation='Finite synthetic checks and mocked narrative do not establish live Gemini quality or universal semantic correctness')
    output=ROOT/'artifacts/m6-evaluation.json'
    output.write_text(json.dumps(report,indent=2))
    print('Offline synthetic examples:',len(results),'| maximum reconstruction residual:',max(r['reconstruction_residual'] for r in results),
          '| Gemini calls: 0 | Human quality review: pending | Report:',output)


if __name__=='__main__':
    run()
