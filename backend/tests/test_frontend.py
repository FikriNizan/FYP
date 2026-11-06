from pathlib import Path
import tempfile
import unittest

from churn_backend import create_app


class FrontendServingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.frontend = self.root / "dist"
        (self.frontend / "assets").mkdir(parents=True)
        (self.frontend / "index.html").write_text('<!doctype html><div id="root"></div><script src="/assets/app.js"></script>')
        (self.frontend / "assets" / "app.js").write_text('console.log("built asset");')
        self.app = create_app({"TESTING": True, "DATABASE": str(self.root/"test.sqlite"), "FRONTEND_DIST": str(self.frontend)})
        self.client = self.app.test_client()

    def test_built_index_and_assets_are_served(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/html", response.content_type)
        self.assertIn('/assets/app.js', response.text)
        response.close()
        result = self.client.get("/assets/app.js")
        self.assertEqual(result.status_code, 200)
        self.assertIn("built asset", result.text)
        result.close()

    def test_unbuilt_frontend_is_explicit_and_api_still_works(self):
        (self.frontend / "index.html").unlink()
        self.assertEqual(self.client.get("/").status_code, 503)
        self.assertEqual(self.client.get("/").json["error"]["code"], "frontend_not_built")
        self.assertEqual(self.client.get("/api/health").status_code, 200)

    def test_api_index_and_missing_assets(self):
        self.assertEqual(self.client.get("/api").json["version"], "0.3.0")
        self.assertEqual(self.client.get("/assets/no-such-file.js").status_code, 404)
        self.assertEqual(self.client.get("/api/months").json["items"], [])

    def test_same_origin_write_through_preserved_development_host(self):
        self.app.test_cli_runner().invoke(args=["init-demo"])
        customer = self.client.get("/api/customers/944").json["customer"]
        response = self.client.put("/api/predictions/"+customer["prediction_id"]+"/review",
                                   base_url="http://127.0.0.1:5173", headers={"Origin":"http://127.0.0.1:5173"},
                                   json=dict(decision="monitor",reason="Development host test",reviewer="Developer",expected_version=0))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["review"]["version"], 1)


if __name__ == "__main__":
    unittest.main()
