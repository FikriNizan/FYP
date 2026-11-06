"""Constructed workflow fixtures: software acceptance, not model evaluation."""
import copy
from contextlib import closing
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from churn_backend import create_app
from churn_backend import repository as repo
from churn_backend.db import get_db
from churn_backend.importer import import_demo

ROOT = Path(__file__).resolve().parents[1]


class CaseTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name)/'test.sqlite'
        self.app = create_app(dict(TESTING=True,DATABASE=str(self.path)))
        self.client = self.app.test_client()
        with self.app.app_context():
            import_demo()
        self.prediction = self.client.get('/api/customers/944').json['customer']['prediction_id']

    def review(self, decision='prioritise', version=0):
        return self.client.put('/api/predictions/'+self.prediction+'/review',json=dict(
            decision=decision, reason='Constructed committee rationale', reviewer='Committee',
            owner='RM A', next_action_date='2026-11-10',expected_version=version))

    def action(self, version=1, status='planned', date='2026-11-10'):
        return dict(expected_version=version,action_type='customer_contact',action_status=status,
                    action_date=date,notes='Constructed follow-up note',recorded_by='RM A')

    def case(self):
        return self.client.get('/api/cases/'+self.prediction).json['case']

    def test_saved_decisions_and_filters_survive_restart(self):
        self.assertEqual(self.client.get('/api/cases').json['total'],0)
        self.assertEqual(self.review().status_code,200)
        c = self.case()
        self.assertEqual(c['original_review']['decision'],'prioritise')
        self.assertEqual(c['follow_ups'],[])
        self.assertEqual(c['owner'],'RM A')
        self.assertEqual(self.client.get('/api/cases?owner=RM%20A&q=944&decision=prioritise&status=open').json['total'],1)
        self.assertEqual(self.client.get('/api/cases?decision=monitor').json['total'],0)
        restarted = create_app(dict(TESTING=True,DATABASE=str(self.path))).test_client()
        self.assertEqual(restarted.get('/api/cases').json['items'][0]['case_id'],self.prediction)
        self.assertFalse(list(self.path.parent.glob('test.sqlite-pre-migration-*')))
        self.review('monitor',1)
        self.assertEqual(self.case()['original_review']['decision'],'prioritise')
        self.assertEqual(self.case()['original']['review']['decision'],'monitor')
        self.assertEqual(len(self.case()['review_history']),2)
        self.review('no_immediate_action',2)
        self.assertEqual(len(self.client.get('/api/cases').json['items']),1)

    def test_january_prioritisation_survives_lower_february_and_later_backfill(self):
        sample = json.loads((ROOT/'demo'/'notebook_case.json').read_text())
        with self.app.app_context():
            evidence = copy.deepcopy(sample['record'])
            evidence['cutoff_month'] = '2024-01-31'
            result = repo.save_batch('2024-01-31','saved_shap_export',evidence['protocol_sha256'],
                                     [dict(evidence=evidence)],dict(constructed_fixture=True))
        january = self.client.get('/api/customers/944?batch_id='+result['batch_id']).json['customer']
        self.prediction = january['prediction_id']
        self.review()
        with self.app.app_context():
            evidence['cutoff_month'] = '2024-02-29'
            evidence['calibrated_risk'] = .12
            evidence['review_alert'] = 0
            # Repository fixture deliberately bypasses importer; not a valid research export.
            feb = repo.save_batch('2024-02-29','saved_shap_export',evidence['protocol_sha256'],
                                  [dict(evidence=evidence,flows=[])],dict(constructed_fixture=True))
            evidence['cutoff_month'] = '2023-12-31'
            repo.save_batch('2023-12-31','saved_shap_export',evidence['protocol_sha256'],
                            [dict(evidence=evidence)],dict(constructed_fixture=True))
        c = self.case()
        self.assertEqual(c['status'],'open')
        self.assertEqual(c['original']['cutoff_month'],'2024-01-31')
        self.assertGreater(c['original']['calibrated_risk'],.8)
        self.assertEqual(c['latest']['batch_id'],feb['batch_id'])
        self.assertEqual(c['latest']['calibrated_risk'],.12)
        self.assertEqual(c['original_review']['decision'],'prioritise')

    def test_task_plan_attempt_completion_preserves_dates_and_immutable_evidence(self):
        self.review()
        before = self.case()['original']['explanation']
        base = '/api/cases/'+self.prediction+'/follow-ups'
        response = self.client.post(base,json=self.action())
        self.assertEqual(response.status_code,201)
        task = response.json['case']['follow_ups'][0]
        url = base+'/'+task['follow_up_id']+'/events'
        response = self.client.post(url,json=self.action(2,'attempted','2026-01-01'))
        self.assertEqual(response.status_code,201)
        response = self.client.post(url,json=self.action(3,'delivered','2026-01-02'))
        self.assertEqual(response.status_code,201)
        c = response.json['case']
        task = c['follow_ups'][0]
        self.assertEqual(task['planned_date'],'2026-11-10')
        self.assertEqual([e['action_status'] for e in task['history']],['planned','attempted','delivered'])
        self.assertEqual(task['current']['action_date'],'2026-01-02')
        self.assertEqual(c['original']['explanation'],before)
        self.assertEqual(c['follow_up_counts']['delivered'],1)
        self.assertEqual(self.client.post(url,json=self.action(4,'delivered','2026-01-03')).status_code,422)

    def test_actual_event_without_plan_future_rejection_and_conflicts(self):
        self.review()
        url = '/api/cases/'+self.prediction+'/follow-ups'
        self.assertEqual(self.client.post(url,json=self.action(1,'delivered','2999-01-01')).status_code,422)
        self.assertEqual(self.client.post(url,json=self.action(1,'attempted','2026-01-01')).status_code,201)
        task = self.case()['follow_ups'][0]
        self.assertIsNone(task['planned_date'])
        self.assertEqual(self.client.post(url,json=self.action(1)).status_code,409)
        self.assertEqual(len(self.case()['follow_ups']),1)
        self.assertEqual(self.client.post(url+'/missing/events',json=self.action(2,'delivered','2026-01-02')).status_code,404)
        self.assertEqual(self.case()['version'],2)

    def test_manual_status_reason_attribution_and_stale_update(self):
        self.review()
        url = '/api/cases/'+self.prediction
        body = dict(expected_version=1,status='closed',owner='RM B',next_action_date=None,
                    notes='Customer confirmed no follow-up required',recorded_by='Committee')
        self.assertEqual(self.client.put(url,json={**body,'notes':''}).status_code,422)
        response = self.client.put(url,json=body)
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.json['case']['status'],'closed')
        self.assertEqual(self.client.put(url,json=body).status_code,409)
        self.assertEqual(self.client.post(url+'/follow-ups',json=self.action(2)).status_code,422)
        body.update(expected_version=2,status='deferred',notes='Await next committee meeting')
        self.assertEqual(self.client.put(url,json=body).status_code,200)
        body.update(expected_version=3,status='open',notes='Resume review')
        self.assertEqual(self.client.put(url,json=body).status_code,200)
        self.assertEqual([e.get('status') for e in self.case()['history']],['open','closed','deferred','open'])
        self.assertEqual(self.case()['original']['review']['decision'],'prioritise')

    def test_invalid_inputs_and_origin_never_write(self):
        self.review()
        self.assertEqual(self.client.get('/api/cases?limit=1001').status_code,422)
        self.assertEqual(self.client.get('/api/cases?offset=no').status_code,422)
        self.assertEqual(self.client.get('/api/cases?status=invalid').status_code,422)
        self.assertEqual(self.client.get('/api/cases/missing').status_code,404)
        url = '/api/cases/'+self.prediction+'/follow-ups'
        for body in ([],{**self.action(),'expected_version':True},{**self.action(),'unknown':'field'}, {**self.action(),'action_date':'invalid'}):
            self.assertEqual(self.client.post(url,json=body).status_code,422)
        self.assertEqual(self.client.post(url,json=self.action(),headers={'Origin':'https://elsewhere.example'}).status_code,403)
        self.assertEqual(self.case()['version'],1)


class MigrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name)/'legacy.sqlite'
        with closing(sqlite3.connect(self.path)) as db, db:
            db.executescript((ROOT/'churn_backend'/'schema.sql').read_text())
            db.execute("INSERT INTO batches VALUES ('b','2024-01-31','test','p',1,'{}','now')")
            evidence = json.loads((ROOT/'demo'/'notebook_case.json').read_text())['record']
            db.execute("INSERT INTO predictions VALUES ('p','b','944',.84,1,?,'{}','{}','[]')",(json.dumps(evidence),))
            original = json.dumps(dict(decision='prioritise',reason='Original',owner='RM A',reviewer='First'))
            current = json.dumps(dict(decision='monitor',reason='Revised',owner='RM B',reviewer='Second'))
            db.execute("INSERT INTO reviews VALUES ('p',2,?,'2026-01-02T00:00:00Z')",(current,))
            db.execute("INSERT INTO review_history(prediction_id,version,body_json,saved_at) VALUES ('p',1,?,'2026-01-01T00:00:00Z')",(original,))
            db.execute("INSERT INTO review_history(prediction_id,version,body_json,saved_at) VALUES ('p',2,?,'2026-01-02T00:00:00Z')",(current,))
            db.execute("INSERT INTO actions VALUES ('a','p','{}','now')")

    def test_legacy_upgrade_backup_preserves_every_old_row_and_backfills_once(self):
        with closing(sqlite3.connect(self.path)) as db:
            before = {name:db.execute('SELECT * FROM '+name).fetchall() for name in ('batches','predictions','reviews','review_history','actions')}
        app = create_app(dict(TESTING=True,DATABASE=str(self.path)))
        with app.app_context():
            db = get_db()
            for name,rows in before.items():
                self.assertEqual([tuple(r) for r in db.execute('SELECT * FROM '+name)],rows)
            case = db.execute('SELECT * FROM reviewed_cases').fetchone()
            self.assertEqual(json.loads(case['original_review_json'])['reason'],'Original')
            self.assertEqual(case['owner'],'RM B')
            self.assertEqual(db.execute('SELECT COUNT(*) FROM schema_migrations').fetchone()[0],2)
        backups = list(self.path.parent.glob('legacy.sqlite-pre-migration-*'))
        self.assertEqual(len(backups),1)
        with closing(sqlite3.connect(backups[0])) as db:
            self.assertEqual(db.execute('SELECT * FROM reviews').fetchall(),before['reviews'])
            self.assertIsNone(db.execute("SELECT name FROM sqlite_master WHERE name='reviewed_cases'").fetchone())
        create_app(dict(TESTING=True,DATABASE=str(self.path)))
        self.assertEqual(len(list(self.path.parent.glob('legacy.sqlite-pre-migration-*'))),1)

    def test_failed_migration_rolls_back_and_future_schema_is_refused(self):
        read = Path.read_text
        def broken(path,*args,**kwargs):
            text = read(path,*args,**kwargs)
            return text+'; INVALID SQL;' if path.name=='002_reviewed_cases.sql' else text
        with patch.object(Path,'read_text',broken):
            with self.assertRaises(sqlite3.Error):
                create_app(dict(TESTING=True,DATABASE=str(self.path)))
        with closing(sqlite3.connect(self.path)) as db, db:
            self.assertIsNone(db.execute("SELECT name FROM sqlite_master WHERE name='reviewed_cases'").fetchone())
            self.assertEqual(db.execute('SELECT COUNT(*) FROM reviews').fetchone()[0],1)
            db.execute('CREATE TABLE schema_migrations(version INTEGER PRIMARY KEY,applied_at TEXT)')
            db.execute("INSERT INTO schema_migrations VALUES (99,'now')")
        with self.assertRaises(RuntimeError):
            create_app(dict(TESTING=True,DATABASE=str(self.path)))
