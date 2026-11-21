"""Phase B demo builder on temporary databases only; never the real Working, M6 Test or demo files."""
from contextlib import closing
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import demo_session as demo  # noqa: E402
import local_session as local  # noqa: E402


class DemoSessionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        (root / 'artifacts').mkdir()
        self.source, self.demo = root / 'artifacts' / 'm6.sqlite', root / 'artifacts' / 'm8-demo.sqlite'
        self.package = root / 'prepared-2024-05'
        self.package.mkdir()
        for name in ('features.csv', 'manifest.json'):
            (self.package / name).write_text('x', encoding='utf-8')
        self.make_source(['2024-02-29', '2024-03-31', '2024-04-30'])
        for item in [patch.object(local, 'ROOT', root), patch.object(local, 'WORKING', root / 'working.sqlite'), patch.object(local, 'TEST', root / 'm5.sqlite'),
                     patch.object(local, 'M6_TEST', self.source), patch.object(local, 'M8_DEMO', self.demo),
                     patch.object(demo, 'PACKAGE', self.package), patch.object(demo, 'PREPARE_SCRIPT', root / 'absent.py')]:
            item.start(); self.addCleanup(item.stop)

    def make_source(self, months):
        if self.source.exists():
            self.source.unlink()
        with closing(sqlite3.connect(self.source)) as db:
            db.executescript((ROOT / 'backend' / 'churn_backend' / 'schema.sql').read_text())
            db.executescript((ROOT / 'backend' / 'churn_backend' / 'migrations' / '004_observed_outcomes.sql').read_text())
            for month in months:
                db.execute("INSERT INTO batches VALUES (?,?,'prepared_month_scored','p',1,'{}','now')", (month, month))
                db.execute("INSERT INTO predictions VALUES (?,?,'1',0.1,0,'{}','{}','{}','[]')", (month + ':1', month))
                db.execute("INSERT INTO observed_outcomes VALUES (?,'2024-05-31','2024-05-31',1,0,0,'[]','s','now')", (month + ':1',))
            db.commit()

    def count(self, path, table):
        with closing(sqlite3.connect(path)) as db:
            return db.execute('SELECT count(*) FROM ' + table).fetchone()[0]

    def test_build_clears_outcomes_only_in_the_copy_and_records_its_origin(self):
        result = demo.build()
        self.assertEqual(result['assessments'], ['2024-02-29', '2024-03-31', '2024-04-30'])
        self.assertEqual((result['outcomes_removed_in_copy'], result['outcomes_left']), (3, 0))
        self.assertEqual(self.count(self.demo, 'observed_outcomes'), 0)
        self.assertEqual(self.count(self.source, 'observed_outcomes'), 3)  # Source untouched.
        self.assertEqual(self.count(self.demo, 'predictions'), 3)
        self.assertEqual(json.loads(Path(str(self.demo) + '.origin.json').read_text())['purpose'], demo.PURPOSE)
        self.assertIn('m8-demo --backend-port 5086 --frontend-port 5196', result['launch'])

    def test_rebuild_is_explicit_and_replaces_only_this_demo(self):
        demo.build()
        with self.assertRaises(SystemExit): demo.build()
        demo.build(rebuild=True)
        self.assertEqual(self.count(self.demo, 'observed_outcomes'), 0)
        origin = Path(str(self.demo) + '.origin.json')
        origin.write_text(json.dumps(dict(purpose='someone else')), encoding='utf-8')
        with self.assertRaises(SystemExit): demo.build(rebuild=True)
        self.assertTrue(self.demo.exists())  # A file not recorded as this demo is left untouched.

    def test_wrong_assessments_or_missing_package_stop_before_use(self):
        self.make_source(['2024-02-29', '2024-03-31', '2024-04-30', '2024-05-31'])
        with self.assertRaises(SystemExit): demo.build()
        for name in ('features.csv', 'manifest.json'):
            (self.package / name).unlink()
        self.make_source(['2024-02-29', '2024-03-31', '2024-04-30'])
        with self.assertRaises(SystemExit) as stopped: demo.build(rebuild=True)
        self.assertIn('--research-root', str(stopped.exception))

    def test_launcher_accepts_only_the_confirmed_demo_file(self):
        demo.build()
        self.assertEqual(local.selected_database('m8-demo')[0], self.demo.resolve())
        with patch.object(local, 'M8_DEMO', self.source):
            with self.assertRaises(ValueError): local.selected_database('m8-demo')


if __name__ == '__main__':
    unittest.main()
