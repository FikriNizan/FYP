import importlib.util
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("apply_react_update", ROOT / "scripts" / "apply_react_update.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class ReactUpdateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.source, self.destination = (Path(self.temp.name)/name for name in ["source","destination"])
        for root in [self.source,self.destination]:
            (root/"scripts").mkdir(parents=True)
            (root/"backend").mkdir()
            (root/"backend"/"app.py").write_text("app")
        (self.source/"page.js").write_text("new")
        (self.source/"new.js").write_text("new file")
        (self.destination/"page.js").write_text("old")
        (self.destination/"obsolete.js").write_text("obsolete")
        self.manifest={"files":{name:module.digest(self.source/name) for name in ["page.js","new.js"]},
                       "baseline":{"page.js":module.digest(self.destination/"page.js"),"obsolete.js":module.digest(self.destination/"obsolete.js")},"remove":["obsolete.js"]}
        self.write_manifest()

    def write_manifest(self):
        (self.source/"scripts"/"react_update_manifest.json").write_text(json.dumps(self.manifest))

    def test_preserves_database_and_git_and_backs_up_changed_source(self):
        database=self.destination/"backend"/"instance"/"churn.sqlite"
        database.parent.mkdir()
        database.write_bytes(b"existing customer database")
        (self.destination/".git").mkdir()
        (self.destination/".git"/"config").write_text("existing remote")
        result=module.update(self.source,self.destination,apply=True)
        self.assertEqual(database.read_bytes(),b"existing customer database")
        self.assertEqual((self.destination/".git"/"config").read_text(),"existing remote")
        self.assertEqual((self.destination/"page.js").read_text(),"new")
        self.assertFalse((self.destination/"obsolete.js").exists())
        self.assertEqual((Path(result["source_backup"])/"page.js").read_text(),"old")
        self.assertEqual(module.update(self.source,self.destination,apply=True)["files_to_change"],0)

    def test_local_edit_blocks_entire_update(self):
        (self.destination/"page.js").write_text("my local edit")
        with self.assertRaises(ValueError):module.update(self.source,self.destination,apply=True)
        self.assertFalse((self.destination/"new.js").exists())
        self.assertTrue((self.destination/"obsolete.js").exists())

    def test_preview_does_not_write(self):
        self.assertEqual(module.update(self.source,self.destination)["mode"],"preview")
        self.assertEqual((self.destination/"page.js").read_text(),"old")
        self.assertFalse((self.destination/".upgrade-backups").exists())

    def test_source_tampering_and_protected_paths_are_rejected(self):
        (self.source/"new.js").write_text("changed source")
        with self.assertRaises(ValueError):module.update(self.source,self.destination,apply=True)
        for name in ["../escape","backend/instance/churn.sqlite",".git/config"]:
            with self.assertRaises(ValueError):module.safe_path(self.destination,name)


if __name__ == "__main__":
    unittest.main()
