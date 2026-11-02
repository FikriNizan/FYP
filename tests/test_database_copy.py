import importlib.util
from pathlib import Path
import sqlite3
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("copy_database", ROOT / "scripts" / "copy_database.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class DatabaseCopyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.source = Path(self.temp.name) / "source.sqlite"
        self.destination = Path(self.temp.name) / "copied" / "churn.sqlite"
        with sqlite3.connect(self.source) as connection:
            connection.executescript((ROOT / "backend" / "churn_backend" / "schema.sql").read_text())
            connection.execute("INSERT INTO batches VALUES ('batch','2024-02-29','test','protocol',1,'{}','now')")
            connection.execute("INSERT INTO predictions VALUES ('prediction','batch','944',0.84,1,'{}','{}','{}','[]')")
            connection.execute("INSERT INTO reviews VALUES ('prediction',1,'{\"decision\":\"monitor\"}','now')")
            connection.execute("INSERT INTO review_history(prediction_id,version,body_json,saved_at) VALUES ('prediction',1,'{}','now')")
            connection.execute("INSERT INTO actions VALUES ('action','prediction','{}','now')")

    def test_preserves_records_and_original(self):
        before = self.source.read_bytes()
        result = module.copy_database(self.source, self.destination)
        self.assertEqual(result["tables"], dict(batches=1,predictions=1,reviews=1,review_history=1,actions=1))
        self.assertEqual(self.source.read_bytes(), before)
        with sqlite3.connect(self.destination) as connection:
            self.assertEqual(connection.execute("SELECT body_json FROM reviews").fetchone()[0], '{"decision":"monitor"}')

    def test_refuses_overwrite(self):
        module.copy_database(self.source, self.destination)
        before = self.destination.read_bytes()
        with self.assertRaises(FileExistsError):
            module.copy_database(self.source, self.destination)
        self.assertEqual(self.destination.read_bytes(), before)

    def test_refuses_missing_or_same_source(self):
        with self.assertRaises(ValueError):
            module.copy_database(self.source.with_name("missing.sqlite"), self.destination)
        with self.assertRaises(ValueError):
            module.copy_database(self.source, self.source)

    def test_refuses_unrelated_database_without_creating_destination(self):
        other = Path(self.temp.name) / "other.sqlite"
        sqlite3.connect(other).close()
        with self.assertRaises(ValueError):
            module.copy_database(other, self.destination)
        self.assertFalse(self.destination.exists())


if __name__ == "__main__":
    unittest.main()
