"""Mature outcome import and intervention-aware monitoring on isolated databases."""
import csv
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

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

    def source_rows(self):
        with self.source.open(newline='',encoding='utf-8') as handle:
            return list(csv.reader(handle))

    def save_source_rows(self, rows, update_manifest=True):
        with self.source.open('w',newline='',encoding='utf-8') as handle:
            csv.writer(handle).writerows(rows)
        if update_manifest:
            raw=self.source.read_bytes()
            (self.source.parent/'cleaned_manifest.json').write_text(json.dumps(dict(status='PASS',
                files={'monthly_flows.csv':{'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}})),
                encoding='utf-8')

    def add_second_customer(self):
        with self.app.app_context():
            get_db().execute("INSERT INTO predictions(prediction_id,batch_id,cus_id,risk,review_alert,evidence_json,features_json,customer_json,flows_json) "
                "SELECT 'prediction-b',batch_id,'customer-b',risk,0,evidence_json,features_json,customer_json,flows_json "
                'FROM predictions WHERE prediction_id=?',(self.prediction,))
            get_db().execute('UPDATE batches SET record_count=2 WHERE batch_id=?',(self.batch,))
            get_db().commit()

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

    def test_unrelated_file_growth_is_idempotent_and_preserves_provenance(self):
        with self.app.app_context(): outcomes.publish(self.batch,self.end,dry_run=False)
        with self.app.app_context():
            original=dict(get_db().execute('SELECT * FROM observed_outcomes').fetchone())
        self.write_flows(duplicate=True)
        with self.app.app_context(), self.assertRaises(ValidationError):
            outcomes.publish(self.batch,self.end,dry_run=False)
        rows=self.source_rows()[:-1]
        rows.append([self.customer,outcomes.shift_month(self.cutoff,4),'0.00',0,'0.00',0,'True','0.00'])
        rows.append(['unrelated','2024-01-31','0.00',0,'0.00',0,'True','0.00'])
        self.save_source_rows(rows)
        with self.app.app_context():
            self.assertEqual(outcomes.publish(self.batch,self.end)['changed'],0)
            self.assertEqual(outcomes.publish(self.batch,self.end,dry_run=False)['changed'],0)
            later=outcomes.shift_month(self.cutoff,4)
            self.assertEqual(outcomes.publish(self.batch,later)['changed'],0)
            self.assertEqual(outcomes.publish(self.batch,later,dry_run=False)['changed'],0)
            self.assertEqual(dict(get_db().execute('SELECT * FROM observed_outcomes').fetchone()),original)
            self.assertEqual(get_db().execute('SELECT count(*) FROM observed_outcomes').fetchone()[0],1)
        missing=outcomes.shift_month(self.cutoff,2)
        self.save_source_rows([row for row in self.source_rows() if len(row)<2 or row[1]!=missing])
        with self.app.app_context():
            self.assertEqual(outcomes.publish(self.batch,self.end,dry_run=False)['available'],0)
            self.assertEqual(dict(get_db().execute('SELECT * FROM observed_outcomes').fetchone()),original)

    def test_partial_source_can_grow_without_rewriting_accepted_customer(self):
        self.add_second_customer()
        with self.app.app_context():
            first=outcomes.publish(self.batch,self.end,dry_run=False)
            self.assertEqual((first['available'],first['unavailable'],first['changed']),(1,1,1))
            accepted=dict(get_db().execute('SELECT * FROM observed_outcomes WHERE prediction_id=?',(self.prediction,)).fetchone())
        rows=self.source_rows()
        rows.extend([["customer-b",*row[1:]] for row in rows[1:]])
        self.save_source_rows(rows)
        with self.app.app_context():
            preview=outcomes.publish(self.batch,self.end)
            self.assertEqual((preview['available'],preview['unavailable'],preview['changed']),(2,0,1))
            self.assertEqual(get_db().execute('SELECT count(*) FROM observed_outcomes').fetchone()[0],1)
            applied=outcomes.publish(self.batch,self.end,dry_run=False)
            self.assertEqual(applied['changed'],1)
            self.assertEqual(dict(get_db().execute('SELECT * FROM observed_outcomes WHERE prediction_id=?',(self.prediction,)).fetchone()),accepted)
            self.assertEqual(outcomes.publish(self.batch,self.end,dry_run=False)['changed'],0)
            self.assertEqual(get_db().execute('SELECT count(*) FROM observed_outcomes').fetchone()[0],2)

    def test_changed_future_sum_and_same_total_breakdown_both_conflict(self):
        with self.app.app_context(): outcomes.publish(self.batch,self.end,dry_run=False)
        original=self.source_rows()
        future=outcomes.shift_month(self.cutoff,1)
        for row in original:
            if row[1]==future:
                row[2]=row[7]='1.00'
        self.save_source_rows(original)
        with self.app.app_context(), self.assertRaises(ConflictError): outcomes.publish(self.batch,self.end)
        with self.app.app_context(), self.assertRaises(ConflictError): outcomes.publish(self.batch,self.end,dry_run=False)
        same_total=self.source_rows()
        for row in same_total:
            if row[1]==outcomes.shift_month(self.cutoff,2): row[2]=row[7]='0.50'
            if row[1]==future: row[2]=row[7]='0.50'
        self.save_source_rows(same_total)
        with self.app.app_context(), self.assertRaises(ConflictError): outcomes.publish(self.batch,self.end)
        with self.app.app_context(), self.assertRaises(ConflictError): outcomes.publish(self.batch,self.end,dry_run=False)
        changed_label=self.source_rows()
        for row in changed_label:
            if row[1] in [outcomes.shift_month(self.cutoff,i) for i in (1,2,3)]:
                row[2]=row[7]='100.00'
        self.save_source_rows(changed_label)
        with self.app.app_context(), self.assertRaises(ConflictError): outcomes.publish(self.batch,self.end)
        with self.app.app_context(), self.assertRaises(ConflictError): outcomes.publish(self.batch,self.end,dry_run=False)
        with self.app.app_context():
            self.assertEqual(get_db().execute('SELECT count(*) FROM observed_outcomes').fetchone()[0],1)

    def test_checksum_and_preparation_race_still_fail(self):
        rows=self.source_rows()
        rows.append(['unrelated','2024-01-31','0.00',0,'0.00',0,'True','0.00'])
        self.save_source_rows(rows,update_manifest=False)
        with self.app.app_context(), self.assertRaises(ValidationError):
            outcomes.publish(self.batch,self.end)
        self.save_source_rows(rows)
        original_read=outcomes.read_flows
        def change_after_read(*args):
            result=original_read(*args)
            with self.source.open('a',encoding='utf-8') as handle: handle.write('\n')
            return result
        with self.app.app_context(),patch.object(outcomes,'read_flows',side_effect=change_after_read),self.assertRaises(ValidationError):
            outcomes.publish(self.batch,self.end)

    def test_new_row_rolls_back_when_later_existing_row_conflicts(self):
        self.add_second_customer()
        with self.app.app_context(): outcomes.publish(self.batch,self.end,dry_run=False)
        rows=self.source_rows()
        rows.extend([["customer-b",*row[1:]] for row in rows[1:]])
        for row in rows:
            if row[0]==self.customer and row[1]==outcomes.shift_month(self.cutoff,1):
                row[2]=row[7]='1.00'
        self.save_source_rows(rows)
        original_prepare=outcomes.prepare
        def reordered(*args):
            result=original_prepare(*args)
            result['rows'].reverse()
            return result
        with self.app.app_context(),patch.object(outcomes,'prepare',side_effect=reordered):
            with self.assertRaises(ConflictError): outcomes.publish(self.batch,self.end)
            with self.assertRaises(ConflictError): outcomes.publish(self.batch,self.end,dry_run=False)
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

    def test_first_window_month_dates_count_and_endpoints_do_not_write(self):
        self.cutoff='2024-04-30'
        self.end=outcomes.horizon_end(self.cutoff)
        self.write_flows()
        with self.app.app_context():
            get_db().execute("UPDATE batches SET cutoff_month=?,source_kind='prepared_month_scored' WHERE batch_id=?",(self.cutoff,self.batch))
            get_db().commit()
            self.assertEqual(outcomes.performance([])['reference_brier'],None)
            self.assertEqual(outcomes.outcome_state('2999-07-31',0,1),'window_open')
            self.assertEqual(outcomes.outcome_state('2024-07-31',0,1),'not_loaded')
            self.assertEqual(outcomes.outcome_state('2024-07-31',1,2),'partly_loaded')
            self.assertEqual(outcomes.outcome_state('2024-07-31',1,1),'loaded')
            outcomes.publish(self.batch,self.end,dry_run=False)
            db=get_db()
            # An eligible completed task is attached to the saved case; use direct rows
            # to cover dates that the human action API may reject for its own reasons.
            db.execute("INSERT INTO reviews(prediction_id,version,body_json,updated_at) VALUES(?,1,'{}','2024-05-01T00:00:00Z')",(self.prediction,))
            db.execute("INSERT INTO reviewed_cases(case_id,prediction_id,original_review_json,status,owner,next_action_date,version,created_at,updated_at) VALUES(?,?,'{}','open','',NULL,1,'2024-05-01T00:00:00Z','2024-05-01T00:00:00Z')",(self.prediction,self.prediction))
            for i,day in enumerate(('2024-04-30','2024-05-01','2024-05-10','2024-08-01')):
                task=f'task-{i}'
                db.execute("INSERT INTO follow_ups(follow_up_id,case_id,action_type,planned_date,created_at) VALUES(?,?,'rm_visit',?,'2024-05-01T00:00:00Z')",(task,self.prediction,day))
                db.execute("INSERT INTO follow_up_events(follow_up_id,body_json,recorded_at) VALUES(?,?,'2024-05-01T00:00:00Z')",(task,json.dumps(dict(action_date=day,action_status='delivered'))))
            db.commit()
            report=outcomes.report(self.batch)
            self.assertEqual(report['outcome_coverage']['documented_delivery'],1)
            self.assertEqual(report['delivery_types'],{'rm_visit':2})
            self.assertEqual(report['observed_all']['flagged_positives'],report['observed_all']['positives'] if report['observed_all']['flagged'] else 0)
            p=report['observed_all']['observed_rate']
            self.assertAlmostEqual(report['observed_all']['reference_brier'],p*(1-p))
        before=hashlib.sha256((self.root/'test.sqlite').read_bytes()).digest()
        self.assertEqual(self.client.get('/api/monitoring?batch_id='+self.batch).status_code,200)
        response=self.client.get('/api/monitoring/trend?batch_id='+self.batch)
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.json['batches'][0]['state'],'loaded')
        self.assertEqual(before,hashlib.sha256((self.root/'test.sqlite').read_bytes()).digest())

    def test_trend_filters_protocol_sample_orders_and_keeps_unloaded_null(self):
        with self.app.app_context():
            db=get_db()
            for batch_id,cutoff,source,protocol in (
                ('prepared-march','2024-03-31','prepared_month_scored',None),
                ('prepared-april','2024-04-30','prepared_month_scored',None),
                ('other-protocol','2024-01-31','prepared_month_scored','other')):
                db.execute("INSERT INTO batches(batch_id,cutoff_month,source_kind,protocol_sha256,record_count,source_json,imported_at) "
                    "SELECT ?,?,?,COALESCE(?,protocol_sha256),1,'{}','2024-05-01T00:00:00Z' FROM batches WHERE batch_id=?",
                    (batch_id,cutoff,source,protocol,self.batch))
                db.execute("INSERT INTO predictions(prediction_id,batch_id,cus_id,risk,review_alert,evidence_json,features_json,customer_json,flows_json) "
                    "SELECT ?,?,cus_id,risk,review_alert,evidence_json,features_json,customer_json,flows_json FROM predictions WHERE prediction_id=?",
                    ('prediction-'+batch_id,batch_id,self.prediction))
            db.commit()
            series=outcomes.trend('prepared-april')
            self.assertEqual([b['batch_id'] for b in series['batches']],['prepared-march','prepared-april'])
            self.assertTrue(all(b['state']=='not_loaded' for b in series['batches']))
            self.assertTrue(all(b['observed_rate'] is None and b['brier'] is None and b['gap'] is None
                and b['reference_brier'] is None for b in series['batches']))
            self.assertEqual(outcomes.report('prepared-april')['drift']['previous_batch_id'],'prepared-march')

    def test_performance_counts_flagged_positives_and_reference_brier(self):
        rows=[dict(target_churn=1,risk=.8,review_alert=1),
              dict(target_churn=0,risk=.2,review_alert=1),
              dict(target_churn=1,risk=.3,review_alert=0),
              dict(target_churn=0,risk=.1,review_alert=0)]
        result=outcomes.performance(rows)
        self.assertEqual(result['flagged_positives'],1)
        self.assertEqual(result['flagged'],2)
        self.assertEqual(result['flagged_positive'],.5)
        self.assertEqual(result['observed_rate'],.5)
        self.assertEqual(result['reference_brier'],.25)
        self.assertEqual(tuple(result[k] for k in ('true_positives','false_positives','false_negatives','true_negatives')),(1,1,1,1))
        self.assertEqual((result['precision'],result['recall'],result['f1']),(.5,.5,.5))
        self.assertEqual(result['flagged_positive'],result['precision'])
        empty=outcomes.performance([])
        self.assertEqual(tuple(empty[k] for k in ('true_positives','false_positives','false_negatives','true_negatives')),(0,0,0,0))
        self.assertIsNone(empty['precision'])
        self.assertIsNone(empty['recall'])
        self.assertIsNone(empty['f1'])
        no_flags=outcomes.performance([dict(target_churn=1,risk=.4,review_alert=0)])
        self.assertIsNone(no_flags['precision'])
        self.assertEqual(no_flags['recall'],0)
        self.assertEqual(no_flags['f1'],0)
        no_positives=outcomes.performance([dict(target_churn=0,risk=.2,review_alert=1)])
        self.assertEqual(no_positives['precision'],0)
        self.assertIsNone(no_positives['recall'])
        self.assertEqual(no_positives['f1'],0)
        all_negative=outcomes.performance([dict(target_churn=0,risk=.2,review_alert=0)])
        self.assertIsNone(all_negative['f1'])

    def test_report_groups_use_their_own_loaded_denominators(self):
        self.add_second_customer()
        rows=self.source_rows()
        for row in rows[1:]:
            copied=['customer-b',*row[1:]]
            if copied[1] in [outcomes.shift_month(self.cutoff,i) for i in (1,2,3)]:
                copied[2]=copied[7]='100.00'
            rows.append(copied)
            if row[1]==outcomes.shift_month(self.cutoff,3):
                break
        self.save_source_rows(rows)
        with self.app.app_context():
            outcomes.publish(self.batch,self.end,dry_run=False)
            db=get_db()
            db.execute("INSERT INTO reviews(prediction_id,version,body_json,updated_at) VALUES(?,1,'{}','2024-05-01T00:00:00Z')",(self.prediction,))
            db.execute("INSERT INTO reviewed_cases(case_id,prediction_id,original_review_json,status,owner,next_action_date,version,created_at,updated_at) VALUES(?,?,'{}','open','',NULL,1,'2024-05-01T00:00:00Z','2024-05-01T00:00:00Z')",(self.prediction,self.prediction))
            db.execute("INSERT INTO follow_ups(follow_up_id,case_id,action_type,planned_date,created_at) VALUES('visit',?,'rm_visit',?,'2024-05-01T00:00:00Z')",(self.prediction,outcomes.shift_month(self.cutoff,1)))
            db.execute("INSERT INTO follow_up_events(follow_up_id,body_json,recorded_at) VALUES('visit',?,'2024-05-01T00:00:00Z')",(json.dumps(dict(action_date=outcomes.shift_month(self.cutoff,1),action_status='delivered')),))
            db.commit()
            report=outcomes.report(self.batch)
            self.assertEqual(report['outcome_coverage']['loaded'],2)
            self.assertEqual(report['observed_all']['records'],2)
            self.assertEqual(report['documented_delivery']['records'],1)
            self.assertEqual(report['without_recorded_delivery']['records'],1)
            self.assertEqual(report['documented_delivery']['positives'],1)
            self.assertEqual(report['without_recorded_delivery']['positives'],0)
            self.assertEqual(report['observed_all']['positives'],1)
            self.assertEqual(report['documented_delivery']['reference_brier'],0)
            self.assertEqual(report['without_recorded_delivery']['reference_brier'],0)


if __name__=='__main__':
    unittest.main()
