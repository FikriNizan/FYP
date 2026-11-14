"""Mature outcome import and intervention-aware monitoring on isolated databases."""
import csv
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from churn_backend import create_app, outcomes
from churn_backend.db import get_db
from churn_backend.importer import import_demo
from churn_backend.validation import ConflictError, ValidationError


class OutcomeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.app = create_app(dict(TESTING=True,DATABASE=str(self.root/'test.sqlite'),
                                   TXB_RESEARCH_ROOT=str(self.root)))
        self.client = self.app.test_client()
        with self.app.app_context():
            import_demo()
            row = get_db().execute('SELECT p.prediction_id,p.batch_id,p.cus_id,p.features_json,b.cutoff_month '
                'FROM predictions p JOIN batches b USING(batch_id)').fetchone()
            self.prediction,self.batch,self.customer,self.cutoff = (row[key] for key in
                ('prediction_id','batch_id','cus_id','cutoff_month'))
            self.baseline = 100.0
            get_db().execute('UPDATE predictions SET features_json=? WHERE prediction_id=?',
                             (json.dumps({'combined_flow_mean_12m_myr':self.baseline}),self.prediction))
            get_db().commit()
        self.source = self.root/'data/final_v4_0_1/cleaned/monthly_flows.csv'
        self.source.parent.mkdir(parents=True)
        self.end = outcomes.horizon_end(self.cutoff)
        self.write_flows()

    def write_flows(self, omit=None, duplicate=False, complete=True):
        total = round(self.baseline * 1200)
        each, remainder = divmod(total, 12)
        rows=[]
        for step in range(-11,4):
            month=outcomes.shift_month(self.cutoff,step)
            if month == omit:
                continue
            value=each + (1 if step < -11+remainder else 0) if step<=0 else 0
            rows.append([self.customer,month,f'{value/100:.2f}',1,'0.00',0,str(complete),f'{value/100:.2f}'])
        if duplicate:
            rows.append(rows[-1])
        with self.source.open('w',newline='',encoding='utf-8') as handle:
            writer=csv.writer(handle)
            writer.writerow(outcomes.FLOW_COLUMNS)
            writer.writerows(rows)
        raw=self.source.read_bytes()
        (self.source.parent/'cleaned_manifest.json').write_text(json.dumps(dict(status='PASS',
            files={'monthly_flows.csv':{'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}})),encoding='utf-8')

    def test_maturity_gate_and_reconciled_label_are_separate_from_prediction(self):
        with self.app.app_context():
            early=outcomes.publish(self.batch,outcomes.shift_month(self.cutoff,2),dry_run=False)
            self.assertFalse(early['mature'])
            self.assertEqual(get_db().execute('SELECT count(*) FROM observed_outcomes').fetchone()[0],0)
            preview=outcomes.publish(self.batch,self.end)
            self.assertEqual(preview['available'],1)
            self.assertEqual(get_db().execute('SELECT count(*) FROM observed_outcomes').fetchone()[0],0)
            result=outcomes.publish(self.batch,self.end,dry_run=False)
            self.assertEqual(result['changed'],1)
            self.assertEqual(outcomes.publish(self.batch,self.end)['changed'],0)
            self.assertEqual(outcomes.publish(self.batch,self.end,dry_run=False)['changed'],0)
            saved=get_db().execute('SELECT * FROM observed_outcomes').fetchone()
            self.assertEqual(saved['target_churn'],1)
            self.assertEqual(len(json.loads(saved['future_flows_json'])),3)
            self.assertEqual(get_db().execute('SELECT count(*) FROM reviews').fetchone()[0],0)
            report=outcomes.report(self.batch)
            self.assertEqual(report['outcome_coverage']['loaded'],1)
            self.assertEqual(report['outcome_coverage']['documented_delivery'],0)
            self.assertEqual(report['without_recorded_delivery']['positives'],1)
            self.assertEqual(self.client.get('/api/monitoring?batch_id='+self.batch).status_code,200)
            detail=self.client.get('/api/customers/'+self.customer+'?batch_id='+self.batch).json['customer']
            self.assertEqual(detail['outcome_status'],'observed')
            self.assertTrue(detail['actual_attrition'])
            self.assertEqual(len(detail['observed_outcome']['future_flows']),3)

    def test_missing_future_and_incomplete_source_never_become_negative_labels(self):
        missing=outcomes.shift_month(self.cutoff,2)
        self.write_flows(omit=missing)
        with self.app.app_context():
            result=outcomes.publish(self.batch,self.end,dry_run=False)
            self.assertEqual((result['available'],result['unavailable'],result['changed']),(0,1,0))
            self.assertEqual(outcomes.report(self.batch)['outcome_coverage']['unavailable'],1)
        self.write_flows(complete=False)
        with self.app.app_context():
            result=outcomes.publish(self.batch,self.end,dry_run=False)
            self.assertEqual(result['available'],0)
        self.write_flows(omit=outcomes.shift_month(self.cutoff,-1))
        with self.app.app_context():
            result=outcomes.publish(self.batch,self.end,dry_run=False)
            self.assertEqual(result['available'],0)

    def test_duplicate_source_and_changed_accepted_outcome_fail_without_replacement(self):
        with self.app.app_context(): outcomes.publish(self.batch,self.end,dry_run=False)
        self.write_flows(duplicate=True)
        with self.app.app_context(), self.assertRaises(ValidationError):
            outcomes.publish(self.batch,self.end,dry_run=False)
        self.write_flows()
        with self.source.open('a',encoding='utf-8') as handle:
            handle.write('unrelated,2024-01-31,0.00,0,0.00,0,True,0.00\n')
        raw=self.source.read_bytes()
        (self.source.parent/'cleaned_manifest.json').write_text(json.dumps(dict(status='PASS',
            files={'monthly_flows.csv':{'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}})),encoding='utf-8')
        with self.app.app_context(), self.assertRaises(ConflictError):
            outcomes.publish(self.batch,self.end,dry_run=False)
        with self.app.app_context():
            self.assertEqual(get_db().execute('SELECT count(*) FROM observed_outcomes').fetchone()[0],1)

    def test_only_delivered_named_action_inside_window_counts_as_documented_exposure(self):
        body=dict(decision='prioritise',reason='Check customer',reviewer='Committee',
                  expected_version=0,owner='RM A',next_action_date=None)
        response=self.client.put('/api/predictions/'+self.prediction+'/review',json=body)
        self.assertEqual(response.status_code,200,response.json)
        planned=self.client.post('/api/cases/'+self.prediction+'/follow-ups',json=dict(
            expected_version=1,action_type='customer_contact',action_status='planned',
            action_date=outcomes.shift_month(self.cutoff,1),notes='Plan contact',recorded_by='RM A'))
        self.assertEqual(planned.status_code,201,planned.json)
        task=planned.json['case']['follow_ups'][0]['follow_up_id']
        with self.app.app_context():
            outcomes.publish(self.batch,self.end,dry_run=False)
            self.assertEqual(outcomes.report(self.batch)['outcome_coverage']['documented_delivery'],0)
        delivered=self.client.post('/api/cases/'+self.prediction+'/follow-ups/'+task+'/events',json=dict(
            expected_version=2,action_type='customer_contact',action_status='delivered',
            action_date=outcomes.shift_month(self.cutoff,1),notes='Contact made',recorded_by='RM A'))
        self.assertEqual(delivered.status_code,201,delivered.json)
        with self.app.app_context():
            report=outcomes.report(self.batch)
            self.assertEqual(report['outcome_coverage']['documented_delivery'],1)
            self.assertEqual(report['delivery_types'],{'customer_contact':1})
            self.assertEqual(report['documented_delivery']['positives'],1)

    def test_delivery_outside_window_or_other_type_is_not_intervention_exposure(self):
        response=self.client.put('/api/predictions/'+self.prediction+'/review',json=dict(
            decision='monitor',reason='Check customer',reviewer='Committee',expected_version=0,
            owner='RM A',next_action_date=None))
        self.assertEqual(response.status_code,200)
        for version,action_type,action_date in ((1,'service_fix',self.cutoff),
                                                 (2,'other',outcomes.shift_month(self.cutoff,1))):
            response=self.client.post('/api/cases/'+self.prediction+'/follow-ups',json=dict(
                expected_version=version,action_type=action_type,action_status='delivered',
                action_date=action_date,notes='Recorded separately',recorded_by='RM A'))
            self.assertEqual(response.status_code,201,response.json)
        with self.app.app_context():
            outcomes.publish(self.batch,self.end,dry_run=False)
            report=outcomes.report(self.batch)
            self.assertEqual(report['outcome_coverage']['documented_delivery'],0)


if __name__=='__main__':
    unittest.main()
