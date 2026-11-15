"""Explicit local-mode safety without starting user servers or opening user databases."""
from contextlib import closing
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import local_session as local
import monitoring_scenario as scenario


class LocalSessionTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.working=self.root/'backend'/'instance'/'churn.sqlite'
        self.test=self.root/'artifacts'/'test.sqlite'
        self.working.parent.mkdir(parents=True)
        self.test.parent.mkdir(parents=True)
        with closing(sqlite3.connect(self.working)) as db:
            db.executescript((ROOT/'backend'/'churn_backend'/'schema.sql').read_text())
            db.execute('CREATE TABLE schema_migrations(version INTEGER PRIMARY KEY,applied_at TEXT)')
            db.execute("INSERT INTO schema_migrations VALUES(4,'now')")
            db.commit()
        self.patchers=[patch.object(local,'WORKING',self.working),patch.object(local,'TEST',self.test)]
        for item in self.patchers: item.start();self.addCleanup(item.stop)

    def test_explicit_selection_missing_path_and_alias_guard(self):
        with self.assertRaises(ValueError): local.selected_database('unknown')
        with self.assertRaises(FileNotFoundError): local.selected_database('test')
        self.test.hardlink_to(self.working)
        with self.assertRaises(ValueError): local.selected_database('test')
        self.test.unlink()
        local.copy_database(self.working,self.test)
        self.assertEqual(local.selected_database('working')[0],self.working.resolve())
        self.assertEqual(local.selected_database('test')[0],self.test.resolve())

    def test_child_environment_overrides_stale_route_and_path(self):
        with patch.dict(local.os.environ,{'CHURN_DB_PATH':'wrong.sqlite','VITE_API_TARGET':'http://wrong:9999'}):
            env=local.child_environment('test',self.test.resolve())
        self.assertEqual(env['CHURN_DB_PATH'],str(self.test.resolve()))
        self.assertEqual(env['VITE_API_TARGET'],'http://127.0.0.1:5000')
        self.assertEqual(env['TXB_LOCAL_MODE'],'test')
        self.assertEqual(env['TXB_LOCAL_SESSION'],'1')

    def test_new_copy_records_source_and_refuses_overwrite(self):
        destination=self.root/'artifacts'/'new.sqlite'
        with patch.object(local,'ROOT',self.root):
            result=local.new_test(self.working,destination,'isolated test')
            record=json.loads(Path(result['metadata']).read_text())
            self.assertEqual(record['source'],str(self.working.resolve()))
            self.assertEqual(record['purpose'],'isolated test')
            with self.assertRaises(FileExistsError): local.new_test(self.working,destination,'again')

    def test_readiness_identity_and_owned_cleanup(self):
        class Child:
            def __init__(self): self.pid=123;self.alive=True;self.terminated=False
            def poll(self): return None if self.alive else 0
            def terminate(self): self.terminated=True;self.alive=False
            def wait(self,timeout): return 0
        child=Child()
        expected=local.expected_identity('test',self.test.resolve())
        with patch.object(local,'read_context',return_value=expected):
            self.assertEqual(local.await_context('http://local',child,expected,deadline=.1),expected)
        with patch.object(local,'read_context',return_value={**expected,'mode':'working'}):
            with self.assertRaises(RuntimeError): local.await_context('http://local',child,expected,deadline=.1)
        untouched=Child();untouched.pid=456
        local.stop_owned([child])
        self.assertTrue(child.terminated)
        self.assertFalse(untouched.terminated)

    def test_scenario_refuses_working_or_uncertain_paths(self):
        local.copy_database(self.working,self.test)
        with patch.object(scenario,'WORKING',self.working),patch.object(scenario,'TEST',self.test),\
             patch.object(scenario,'selected_database',return_value=(self.test.resolve(),4,[],{})):
            self.assertEqual(scenario.safe_test_database(self.test),self.test.resolve())
            with self.assertRaises(ValueError): scenario.safe_test_database(self.working)

    def test_launch_routes_both_children_to_one_test_database_and_stops_them(self):
        local.copy_database(self.working,self.test)
        class Child:
            next_id=100
            def __init__(self,cmd,**kwargs):
                self.pid=Child.next_id;Child.next_id+=1
                self.cmd=cmd;self.kwargs=kwargs;self.alive=True
            def poll(self): return None if self.alive else 0
            def terminate(self): self.alive=False
            def wait(self,timeout): return 0
        children=[]
        def spawn(cmd,**kwargs):
            child=Child(cmd,**kwargs);children.append(child);return child
        expected=local.expected_identity('test',self.test.resolve())
        context={**expected,'schema_version':4,'assessment_months':[],'predictions':0}
        with patch.object(local,'free_port'),patch.object(local.subprocess,'Popen',side_effect=spawn),\
             patch.object(local,'await_context',return_value=context),\
             patch.object(local.time,'sleep',side_effect=KeyboardInterrupt):
            with patch.object(local,'ROOT',ROOT):
                # Paths to the project's existing Python/Node/Vite are checked before spawn.
                local.launch('test')
        self.assertEqual(len(children),2)
        self.assertEqual(children[0].kwargs['env']['CHURN_DB_PATH'],str(self.test.resolve()))
        self.assertEqual(children[1].kwargs['env']['VITE_API_TARGET'],local.BACKEND_URL)
        self.assertIn('5000',children[0].cmd)
        self.assertIn('5173',children[1].cmd)
        self.assertTrue(all(not child.alive for child in children))


if __name__=='__main__':
    unittest.main()
