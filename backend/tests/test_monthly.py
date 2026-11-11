"""Prepared-package integration uses constructed evidence, never a saved scorer fallback."""
import copy
import csv
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from concurrent.futures import ThreadPoolExecutor
import subprocess
import sys
import threading

from churn_backend import create_app, monthly
from churn_backend.constants import PREDICTORS, CATEGORIES, PROTOCOL_SHA256
from churn_backend.db import get_db
from churn_backend.validation import ValidationError


class MonthlyTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.app = create_app({'TESTING':True, 'DATABASE':str(Path(self.folder.name)/'test.sqlite'), 'TXB_MONTHLY_POPULATION':1})
        self.client = self.app.test_client()
        self.record = json.loads((Path(__file__).parents[1]/'demo/notebook_case.json').read_text())['record']
        self.record['cutoff_month'] = '2024-04-30'
        self.row = {name:'fixture' if name in CATEGORIES else 0 for name in PREDICTORS}
        self.row.update(cus_id='944', cutoff_month='2024-04-30', combined_flow_mean_12m_myr=100)
        for key in ['higher_risk_drivers','lower_risk_drivers']:
            self.row.update({d['feature']:d['value'] for d in self.record[key]})

    def package(self, rows=None, columns=None):
        stream = io.StringIO(newline='')
        writer = csv.DictWriter(stream, fieldnames=columns or ['cus_id','cutoff_month',*PREDICTORS], extrasaction='ignore')
        writer.writeheader(); writer.writerows(rows or [self.row])
        data = stream.getvalue().encode()
        manifest = dict(kind='txb_prepared_month', package_version='1.0.0', feature_version=monthly.SCHEMA['feature_version'],
                        feature_schema_sha256=monthly.SCHEMA_SHA, protocol_sha256=PROTOCOL_SHA256,
                        cutoff_month='2024-04-30', row_count=1, predictor_count=78,
                        files={'features.csv':{'bytes':len(data),'sha256':monthly.digest(data)}}, source={'opaque':'../../never-open.py'})
        return data, json.dumps(manifest).encode()

    def post(self, data=None):
        csv_data, manifest = data or self.package()
        return self.client.post('/api/assessments', data={'features':(io.BytesIO(csv_data),'features.csv'), 'manifest':(io.BytesIO(manifest),'manifest.json')})

    def output(self):
        return dict(records=[copy.deepcopy(self.record)], csv_sha256=monthly.digest(self.package()[0]),
                    champion_sha256=monthly.CONTRACT['champion_sha256'], protocol_sha256=PROTOCOL_SHA256, provenance={})

    def counts(self):
        with self.app.app_context():
            return tuple(get_db().execute('SELECT count(*) FROM '+table).fetchone()[0] for table in ['batches','predictions','reviews','reviewed_cases'])

    def test_publish_repeat_conflict_and_no_enrichment(self):
        with patch.object(monthly,'run_scorer',return_value=self.output()) as scorer:
            first = self.post(); self.assertEqual(first.status_code,201,first.json)
            again = self.post(); self.assertEqual(again.status_code,200); self.assertTrue(again.json['already_imported'])
            self.assertEqual(first.json['batch_id'],again.json['batch_id']); scorer.assert_called_once()
            snapshot = self.counts()
            changed = {**self.row,'tier_id':'different'}
            conflict = self.post(self.package([changed])); self.assertEqual(conflict.status_code,409)
            self.assertEqual(snapshot,self.counts())
            customer = self.client.get('/api/customers/944?batch_id='+first.json['batch_id']).json['customer']
            self.assertIsNone(customer['customer_name']); self.assertEqual(customer['flow_history'],[])

    def test_checksum_failure_never_scores(self):
        data, manifest = self.package()
        with patch.object(monthly,'run_scorer') as scorer:
            self.assertEqual(self.post((data+b'\n',manifest)).status_code,422); scorer.assert_not_called()
        self.assertEqual(self.counts(),(0,0,0,0))

    def test_rehashed_invalid_schema_and_duplicate_are_rejected(self):
        for data in [self.package(columns=['cus_id','cutoff_month',*reversed(PREDICTORS)]),self.package([self.row,self.row])]:
            with self.subTest(), patch.object(monthly,'run_scorer') as scorer:
                self.assertEqual(self.post(data).status_code,422); scorer.assert_not_called()
        self.assertEqual(self.counts(),(0,0,0,0))

    def test_numeric_id_month_baseline_and_missing_validation(self):
        for changes in [{'cus_id':''},{'cutoff_month':'2024-05-31'},{'combined_flow_mean_12m_myr':0}, {'fd_balance_myr':'NaN'}, {'fd_balance_myr':'1e999'}, {'fd_balance_myr':'wat'}]:
            with self.subTest(changes=changes), self.assertRaises(ValidationError):
                monthly.validate_package(*self.package([{**self.row,**changes}]),expected_rows=1)
        package = monthly.validate_package(*self.package([{**self.row,'fd_balance_myr':'','tier_id':'001'}]),expected_rows=1)
        self.assertIsNone(package['rows'][0]['features']['fd_balance_myr'])
        self.assertEqual(package['rows'][0]['features']['tier_id'],'001')
        self.assertEqual(package['rows'][0]['features']['estimated_fee_mean_3m_myr'],self.row['estimated_fee_mean_3m_myr'])

    def test_strict_manifest_and_population(self):
        data, raw = self.package(); manifest = json.loads(raw)
        for change in [{'row_count':True},{'row_count':1000},{'kind':'other'},{'protocol_sha256':'bad'},{'files':{}}]:
            with self.subTest(change=change), self.assertRaises(ValidationError):
                monthly.validate_package(data,json.dumps({**manifest,**change}).encode(),1)
        for raw in [b'{"kind":1,"kind":2}',b'{"value":NaN}',b'[]']:
            with self.assertRaises(ValidationError): monthly.validate_package(data,raw,1)

    def test_scorer_failure_and_invalid_output_do_not_publish(self):
        with patch.object(monthly,'run_scorer',side_effect=monthly.MonthlyError('Scoring failed')):
            self.assertEqual(self.post().status_code,503)
        broken = self.output(); broken['records'][0]['review_alert'] = 0
        with patch.object(monthly,'run_scorer',return_value=broken):
            self.assertEqual(self.post().status_code,503)
        self.assertEqual(self.counts(),(0,0,0,0))

    def test_transaction_rolls_back_partial_insert_and_rechecks_cutoff(self):
        package = monthly.validate_package(*self.package(),1)
        entries = monthly.verify_output(package,self.output())
        source = {'prepared_identity':package['identity']}
        with self.app.app_context():
            from churn_backend import repository
            with self.assertRaises(Exception): repository.publish_prepared('2024-04-30',entries+entries,source)
            self.assertEqual(get_db().execute('SELECT count(*) FROM batches').fetchone()[0],0)
            repository.publish_prepared('2024-04-30',entries,source)
            self.assertTrue(repository.publish_prepared('2024-04-30',entries,source)['already_imported'])
            with self.assertRaises(monthly.MonthlyError): repository.publish_prepared('2024-04-30',entries,{'prepared_identity':'other'})

    def test_same_origin_and_note_limit_are_preserved(self):
        self.assertEqual(self.client.post('/api/assessments',headers={'Origin':'https://elsewhere.invalid'}).status_code,403)
        with patch.object(monthly,'run_scorer',return_value=self.output()):
            self.post()
        with self.app.app_context():
            prediction = get_db().execute('SELECT prediction_id FROM predictions').fetchone()[0]
        self.assertEqual(self.client.put('/api/predictions/'+prediction+'/review',data=' '*70000,content_type='application/json').status_code,413)

    def test_unconfigured_environment_still_serves_reads(self):
        self.assertEqual(self.client.get('/api/months').status_code,200)
        self.assertEqual(self.post().status_code,503)

    def test_new_publication_attaches_optional_trusted_evidence_without_changing_scores(self):
        from churn_backend import enrichment
        root=Path(self.folder.name)
        master=root/enrichment.MASTER; flows=root/enrichment.FLOWS
        master.parent.mkdir(parents=True,exist_ok=True);flows.parent.mkdir(parents=True,exist_ok=True)
        master.write_text('cus_id,cus_name\n944,Trusted Name\n',encoding='utf-8')
        flows.write_text('cus_id,snapshot_month,inbound_myr,inbound_count,outbound_success_myr,outbound_success_count,source_complete,combined_flow_myr\n'
                         '944,2024-04-30,0,0,0,0,True,0\n',encoding='utf-8')
        self.app.config['TXB_RESEARCH_ROOT']=str(root)
        with patch.object(monthly,'run_scorer',return_value=self.output()) as scorer:
            first=self.post();self.assertEqual(first.status_code,201,first.json)
            self.assertEqual(first.json['enrichment']['coverage']['names_available'],1)
            self.assertEqual(self.post().status_code,200)
            scorer.assert_called_once()
        customer=self.client.get('/api/customers/944?batch_id='+first.json['batch_id']).json['customer']
        self.assertEqual(customer['customer_name'],'Trusted Name')
        self.assertEqual(customer['flow_history'][0]['combined_flow_myr'],0)
        self.assertEqual(self.counts(),(1,1,0,0))
        with self.app.app_context():
            self.assertEqual(get_db().execute('SELECT version FROM supplemental_evidence').fetchone()[0],1)

    def test_simultaneous_publications_cannot_duplicate_a_cutoff(self):
        from churn_backend import repository
        package = monthly.validate_package(*self.package(),1)
        entries = monthly.verify_output(package,self.output())
        barrier = threading.Barrier(2)
        def publish(identity):
            with self.app.app_context():
                barrier.wait()
                try:
                    return repository.publish_prepared('2024-04-30',entries,{'prepared_identity':identity})
                except monthly.MonthlyError:
                    return 'conflict'
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(publish,['one','two']))
        self.assertEqual(results.count('conflict'),1)
        self.assertEqual(self.counts(),(1,1,0,0))

    def test_adapter_timeout_and_process_failure_are_safe(self):
        self.app.config.update(TXB_RESEARCH_ROOT=self.folder.name,TXB_MODEL_PYTHON=__file__)
        for effect in [subprocess.TimeoutExpired('worker',120),OSError('local-only diagnostic')]:
            with self.subTest(effect=effect), patch.object(monthly.subprocess,'run',side_effect=effect):
                response = self.post()
                self.assertIn(response.status_code,[503,504]); self.assertNotIn('local-only',str(response.json))
        with patch.object(monthly.subprocess,'run',return_value=subprocess.CompletedProcess([],1,stderr=b'local traceback')):
            response = self.post(); self.assertEqual(response.status_code,503)
            self.assertNotIn('traceback',response.json['error']['message'])
        self.assertEqual(self.counts(),(0,0,0,0))

    def test_worker_rejects_changed_trusted_source_before_model_import(self):
        root = Path(self.folder.name)
        relative = next(iter(monthly.CONTRACT['files']))
        altered = root/relative
        altered.parent.mkdir(parents=True,exist_ok=True)
        altered.write_text('raise RuntimeError("must never execute")',encoding='utf-8')
        result = subprocess.run([sys.executable,'-I',str(monthly.DIRECTORY/'model_worker.py'),
                                 '--research-root',str(root),'--features',str(root/'features.csv'),
                                 '--output',str(root/'output.json')],capture_output=True,timeout=10)
        self.assertNotEqual(result.returncode,0)
        self.assertIn(b'fingerprint mismatch',result.stderr)
        self.assertNotIn(b'RuntimeError: must never execute',result.stderr)
        self.assertFalse((root/'output.json').exists())
