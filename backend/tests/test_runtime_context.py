"""Development runtime identity exposes no full path and never writes via GET."""
import hashlib
from pathlib import Path
import tempfile
import unittest

from churn_backend import create_app


class RuntimeContextTests(unittest.TestCase):
    def test_disabled_and_mismatched_context(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'fixture.sqlite'
            app=create_app(dict(TESTING=True,DATABASE=str(path),TXB_LOCAL_SESSION=True,TXB_LOCAL_MODE='test'))
            client=app.test_client()
            result=client.get('/api/runtime-context')
            self.assertEqual(result.status_code,200)
            self.assertEqual(result.json['mode'],'unknown')
            self.assertEqual(result.json['database_filename'],'fixture.sqlite')
            self.assertEqual(result.json['database_path_sha256'],hashlib.sha256(str(path.resolve()).casefold().encode()).hexdigest())
            self.assertNotIn(str(path.parent),result.get_data(as_text=True))
            app.config['TXB_LOCAL_SESSION']=False
            self.assertEqual(client.get('/api/runtime-context').status_code,404)


if __name__=='__main__':
    unittest.main()
