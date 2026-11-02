from pathlib import Path
import re
import tempfile
import unittest

from churn_backend import create_app


class FrontendServingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.client = create_app({"TESTING": True, "DATABASE": str(Path(self.temp.name)/"test.sqlite")}).test_client()

    def test_dashboard_and_module_imports_are_served(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/html", response.content_type)
        for asset in re.findall(r'(?:src|href)="(/assets/[^\"]+)"', response.text):
            result = self.client.get(asset)
            self.assertEqual(result.status_code, 200, asset)
            result.close()
        for name in ("api.js", "format.js"):
            result = self.client.get("/assets/src/"+name)
            self.assertEqual(result.status_code, 200)
            result.close()
        response.close()

    def test_api_index_and_missing_assets_have_explicit_responses(self):
        self.assertEqual(self.client.get("/api").json["version"], "0.2.0")
        self.assertEqual(self.client.get("/assets/no-such-file.js").status_code, 404)
        self.assertEqual(self.client.get("/api/months").json["items"], [])


if __name__ == "__main__":
    unittest.main()
