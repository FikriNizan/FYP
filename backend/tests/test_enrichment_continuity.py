"""Cutoff-safe supporting evidence and one case across deliberate monthly reviews."""
import copy
import csv
import json
from pathlib import Path
import tempfile
import unittest

from churn_backend import create_app, enrichment, repository as repo
from churn_backend.constants import CALIBRATION_INTERCEPT,CALIBRATION_SLOPE
from churn_backend.db import get_db
from churn_backend.importer import import_demo
from churn_backend.validation import sigmoid
import math


class ContinuityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.database = self.root/'test.sqlite'
        self.app = create_app(dict(TESTING=True,DATABASE=str(self.database),TXB_RESEARCH_ROOT=str(self.root)))
        self.client = self.app.test_client()
        with self.app.app_context():
            import_demo()
        original = self.client.get('/api/customers/944').json['customer']
        self.original_id = original['prediction_id']
        self.original_batch = original['batch_id']
        self.review(self.original_id,0,'prioritise')
        evidence = copy.deepcopy(original['explanation'])
        evidence['cutoff_month']='2024-04-30'
        with self.app.app_context():
            self.batch = repo.save_batch('2024-04-30','prepared_month_scored',evidence['protocol_sha256'],
                [dict(evidence=evidence,features={'combined_flow_mean_1m_myr':30,'combined_flow_mean_12m_myr':100})],
                dict(customer_names_loaded=False,flow_history_loaded=False))['batch_id']
        self.latest = self.client.get('/api/customers/944?batch_id='+self.batch).json['customer']
        self.master = self.root/enrichment.MASTER
        self.flows = self.root/enrichment.FLOWS
        self.master.parent.mkdir(parents=True,exist_ok=True)
        self.flows.parent.mkdir(parents=True,exist_ok=True)

    def review(self,prediction,version,decision,case_version=None):
        body=dict(expected_version=version,decision=decision,reason='Deliberate committee judgement',reviewer='Committee',
                  owner='RM A',next_action_date=None)
        if case_version is not None:
            body.update(case_id=self.original_id,expected_case_version=case_version)
        return self.client.put('/api/predictions/'+prediction+'/review',json=body)

    def sources(self):
        with self.master.open('w',newline='',encoding='utf-8') as file:
            writer=csv.writer(file);writer.writerow(['cus_id','cus_name']);writer.writerow(['944','Alpha Holdings'])
        with self.flows.open('w',newline='',encoding='utf-8') as file:
            writer=csv.writer(file);writer.writerow(['cus_id','snapshot_month','inbound_myr','inbound_count',
                'outbound_success_myr','outbound_success_count','source_complete','combined_flow_myr'])
            writer.writerow(['944','2024-02-29',0,0,0,0,'True',0])
            writer.writerow(['944','2024-04-30',10,1,20,1,'True',30])
            writer.writerow(['944','2024-05-31',999,1,1,1,'True',1000])

    def test_enrichment_is_stored_cutoff_safe_and_idempotent(self):
        self.sources()
        with self.app.app_context():
            preview=enrichment.apply(self.batch)
            self.assertEqual(preview['coverage']['names_available'],1)
            self.assertEqual(preview['coverage']['histories_available'],1)
            self.assertEqual(preview['changed'],1)
            self.assertEqual(enrichment.apply(self.batch,dry_run=False)['changed'],1)
            self.assertEqual(enrichment.apply(self.batch,dry_run=False)['changed'],0)
            self.assertEqual(get_db().execute('SELECT count(*) FROM supplemental_history').fetchone()[0],0)
            self.assertEqual(get_db().execute('SELECT count(*) FROM predictions WHERE batch_id=?',(self.batch,)).fetchone()[0],1)
        after=self.client.get('/api/customers/944?batch_id='+self.batch).json['customer']
        self.assertEqual(after['customer_name'],'Alpha Holdings')
        self.assertEqual([row['snapshot_month'] for row in after['flow_history']],['2024-02-29','2024-04-30'])
        self.assertEqual(after['flow_history'][0]['combined_flow_myr'],0)
        self.assertEqual(after['flow_history'][-1]['combined_flow_myr'],after['features']['combined_flow_mean_1m_myr'])
        self.assertEqual(self.client.get('/api/customers?batch_id='+self.batch+'&q=Alpha').json['total'],1)
        self.assertEqual(self.client.get('/api/months').json['items'][0]['source']['evidence_coverage']['names_available'],1)
        self.assertEqual(self.client.get('/api/customers/944?batch_id='+self.original_batch).json['customer']['flow_history'],[])

    def test_invalid_source_keeps_accepted_evidence_until_explicit_correction(self):
        self.sources()
        with self.app.app_context(): enrichment.apply(self.batch,dry_run=False)
        with self.master.open('a',encoding='utf-8') as file: file.write('944,Duplicate\n')
        with self.app.app_context(), self.assertRaises(ValueError): enrichment.apply(self.batch,dry_run=False)
        self.assertEqual(self.client.get('/api/customers/944?batch_id='+self.batch).json['customer']['customer_name'],'Alpha Holdings')
        self.sources()
        text=self.master.read_text(encoding='utf-8').replace('Alpha Holdings','Revised Name')
        self.master.write_text(text,encoding='utf-8')
        with self.app.app_context():
            from churn_backend.validation import ConflictError
            with self.assertRaises(ConflictError): enrichment.apply(self.batch,dry_run=False)
            self.assertEqual(enrichment.apply(self.batch,dry_run=False,replace=True)['changed'],1)
            self.assertEqual(get_db().execute('SELECT count(*) FROM supplemental_history').fetchone()[0],1)

    def test_optional_missing_and_partial_sources_are_honest(self):
        with self.app.app_context():
            result=enrichment.apply(self.batch,dry_run=False)
            self.assertEqual(result['coverage']['names_available'],0)
            self.assertEqual(result['coverage']['histories_available'],0)
        self.assertIsNone(self.client.get('/api/customers/944?batch_id='+self.batch).json['customer']['customer_name'])
        self.sources()
        self.flows.unlink()
        with self.app.app_context():
            partial=enrichment.apply(self.batch,dry_run=False,replace=True)
            self.assertEqual(partial['coverage']['names_available'],1)
            self.assertEqual(partial['coverage']['histories_available'],0)

    def test_duplicate_or_invalid_flow_source_cannot_replace_saved_evidence(self):
        self.sources()
        with self.app.app_context(): enrichment.apply(self.batch,dry_run=False)
        original=self.client.get('/api/customers/944?batch_id='+self.batch).json['customer']['flow_history']
        with self.flows.open('a',encoding='utf-8') as file:
            file.write('944,2024-04-30,10,1,20,1,True,30\n')
        with self.app.app_context(), self.assertRaises(ValueError):
            enrichment.apply(self.batch,dry_run=False,replace=True)
        self.assertEqual(self.client.get('/api/customers/944?batch_id='+self.batch).json['customer']['flow_history'],original)
        self.sources()
        self.flows.write_text(self.flows.read_text(encoding='utf-8').replace('944,2024-04-30,10,1,20,1,True,30',
            '944,2024-04-30,-10,1,20,1,True,10'),encoding='utf-8')
        with self.app.app_context(), self.assertRaises(ValueError):
            enrichment.apply(self.batch,dry_run=False,replace=True)
        self.assertEqual(self.client.get('/api/customers/944?batch_id='+self.batch).json['customer']['flow_history'],original)

    def test_existing_case_is_not_reopened_or_redecided_by_a_new_prediction(self):
        latest=self.latest
        self.assertEqual(latest['review']['decision'],'awaiting_review')
        self.assertEqual(latest['workflow']['state'],'existing_case')
        self.assertEqual(latest['workflow']['case_id'],self.original_id)
        self.assertEqual(self.client.get('/api/customers?batch_id='+self.batch+'&workflow=needs_review').json['total'],0)
        self.assertEqual(self.client.get('/api/summary?batch_id='+self.batch).json['needs_committee_review'],0)
        case=self.client.get('/api/cases/'+self.original_id).json['case']
        self.assertEqual(case['current_review']['decision'],'prioritise')
        self.assertEqual(case['latest']['cutoff_month'],'2024-04-30')

    def test_deliberate_reassessment_links_same_case_and_updates_briefing(self):
        self.assertEqual(self.review(self.latest['prediction_id'],0,'monitor').status_code,409)
        accepted=self.review(self.latest['prediction_id'],0,'monitor',1)
        self.assertEqual(accepted.status_code,200,accepted.json)
        case=self.client.get('/api/cases/'+self.original_id).json['case']
        self.assertEqual(case['current_review']['decision'],'monitor')
        self.assertEqual(case['original_review']['decision'],'prioritise')
        self.assertEqual(case['original']['cutoff_month'],'2024-02-29')
        self.assertEqual(case['current_review']['assessment_month'],'2024-04-30')
        self.assertEqual(len(case['review_history']),2)
        self.assertEqual(case['history'][-1]['kind'],'committee_reassessment')
        self.assertEqual(self.client.get('/api/cases').json['total'],1)
        self.assertEqual(self.client.get('/api/briefings?case_id='+self.original_id).status_code,422)
        self.assertEqual(self.review(self.original_id,1,'prioritise',1).status_code,409)
        self.assertEqual(self.review(self.original_id,1,'prioritise',2).status_code,200)
        self.assertEqual(self.client.get('/api/cases/'+self.original_id).json['case']['current_review']['decision'],'monitor')

    def test_closed_case_starts_new_episode_and_deferred_case_continues(self):
        change=dict(expected_version=1,status='closed',owner='RM A',next_action_date=None,notes='Close manually',recorded_by='Committee')
        self.assertEqual(self.client.put('/api/cases/'+self.original_id,json=change).status_code,200)
        self.assertEqual(self.latest['workflow']['state'],'existing_case')  # Earlier response is immutable.
        fresh=self.client.get('/api/customers/944?batch_id='+self.batch).json['customer']
        self.assertEqual(fresh['workflow']['state'],'needs_reassessment')
        self.assertEqual(self.review(fresh['prediction_id'],0,'monitor').status_code,200)
        self.assertEqual(self.client.get('/api/cases').json['total'],2)
        new=self.client.get('/api/cases/'+fresh['prediction_id']).json['case']
        self.assertEqual(new['history'][0]['previous_closed_cases'],[self.original_id])

    def test_deferred_and_below_threshold_still_show_existing_case(self):
        change=dict(expected_version=1,status='deferred',owner='RM A',next_action_date=None,
                    notes='Defer manually',recorded_by='Committee')
        self.assertEqual(self.client.put('/api/cases/'+self.original_id,json=change).status_code,200)
        april=self.client.get('/api/customers/944?batch_id='+self.batch).json['customer']
        self.assertEqual(april['workflow']['state'],'existing_case')
        self.assertEqual(april['workflow']['case_status'],'deferred')
        self.assertEqual(self.review(april['prediction_id'],0,'monitor',2).status_code,200)
        case=self.client.get('/api/cases/'+self.original_id).json['case']
        self.assertEqual(case['status'],'deferred')
        self.assertEqual(self.client.get('/api/cases').json['total'],1)
        evidence=copy.deepcopy(april['explanation'])
        evidence.update(cutoff_month='2024-05-31',raw_probability=.1,review_alert=0)
        risk=sigmoid(CALIBRATION_SLOPE*math.log(.1/.9)+CALIBRATION_INTERCEPT)
        evidence['calibrated_risk']=risk
        driver_sum=sum(d['contribution_logodds'] for group in ['higher_risk_drivers','lower_risk_drivers'] for d in evidence[group])
        evidence['other_features_contribution_logodds']=math.log(risk/(1-risk))-evidence['base_logodds']-driver_sum-evidence['probability_clip_adjustment_logodds']
        with self.app.app_context():
            batch=repo.save_batch('2024-05-31','saved_shap_export',evidence['protocol_sha256'],
                [dict(evidence=evidence,features={'combined_flow_mean_1m_myr':20})],dict())['batch_id']
        may=self.client.get('/api/customers/944?batch_id='+batch).json['customer']
        self.assertFalse(may['review_alert'])
        self.assertEqual(may['review']['decision'],'awaiting_review')
        self.assertEqual(may['workflow']['state'],'existing_case')
        self.assertEqual(self.client.get('/api/summary?batch_id='+batch).json['needs_committee_review'],0)
        self.assertEqual(self.client.get('/api/cases?status=deferred').json['total'],1)

    def test_legacy_multiple_active_cases_require_explicit_selection(self):
        original=self.client.get('/api/customers/944?batch_id='+self.original_batch).json['customer']
        evidence=copy.deepcopy(original['explanation']);evidence['cutoff_month']='2024-03-31'
        with self.app.app_context():
            march_batch=repo.save_batch('2024-03-31','saved_shap_export',evidence['protocol_sha256'],[dict(evidence=evidence)],dict())['batch_id']
            march=get_db().execute('SELECT prediction_id FROM predictions WHERE batch_id=?',(march_batch,)).fetchone()[0]
            with get_db():
                get_db().execute('INSERT INTO reviews VALUES (?,?,?,?)',(march,1,repo.encode(dict(decision='monitor',reason='Legacy',reviewer='Committee')),'2026-01-01'))
                get_db().execute("INSERT INTO reviewed_cases VALUES (?,?,?,'open','RM B',NULL,1,'2026-01-01','2026-01-01')",
                                 (march,march,repo.encode(dict(decision='monitor',reason='Legacy',reviewer='Committee'))))
                get_db().execute('INSERT INTO case_events(case_id,version,body_json,recorded_at) VALUES (?,1,?,?)',
                                 (march,repo.encode(dict(kind='case_created',status='open')),'2026-01-01'))
        april=self.client.get('/api/customers/944?batch_id='+self.batch).json['customer']
        self.assertEqual(april['workflow']['state'],'case_conflict')
        self.assertIsNone(april['workflow']['case_id'])
        self.assertEqual(len(april['workflow']['active_cases']),2)
        self.assertEqual(self.review(april['prediction_id'],0,'prioritise').status_code,409)
        self.assertEqual(self.client.get('/api/cases').json['total'],2)
        self.assertEqual(self.review(april['prediction_id'],0,'monitor',1).status_code,200)
        self.assertEqual(self.client.get('/api/cases').json['total'],2)
        self.assertEqual(self.client.get('/api/cases/'+self.original_id).json['case']['current_review']['decision'],'monitor')

