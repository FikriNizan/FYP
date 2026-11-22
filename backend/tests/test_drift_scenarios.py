"""Milestone 7: PSI/KS on hand-checkable fixtures and the read-only scenario package. No network, no model."""
import hashlib
import json
import math
import shutil
import tempfile
import unittest
from pathlib import Path
from churn_backend import create_app, drift
from churn_backend.db import get_db
from churn_backend.importer import import_demo
from tests.hermetic import unconfigured

try:
    from scipy.stats import ks_2samp
except ImportError:  # The app .venv has no scipy; this comparison runs in the modelling environment.
    ks_2samp = None

E = drift.EPSILON


def term(a, e):
    a, e = max(a, E), max(e, E)
    return (a - e) * math.log(a / e)


class PsiTests(unittest.TestCase):
    def test_identical_distributions_give_exactly_zero(self):
        values = [0.1 * i for i in range(50)] + [None] * 5
        self.assertEqual(drift.psi(values, list(values)), 0.0)
        self.assertEqual(drift.ks(values, list(values)), 0.0)

    def test_value_bins_by_hand(self):
        # Two distinct reference values -> one bin per value (+ unseen + null bins).
        self.assertAlmostEqual(drift.psi([0, 0, 1, 1], [0, 1, 1, 1]), term(.25, .5) + term(.75, .5), places=12)
        self.assertAlmostEqual(drift.psi([0, 0, 1, 1], [0, 1, 1, 1]), 0.274653072, places=8)

    def test_zero_share_uses_epsilon(self):
        # The value 2 is unseen in the reference: its bin has reference share 0, replaced by epsilon.
        expected = term(.25, .5) + term(.25, 0)
        self.assertAlmostEqual(drift.psi([0, 0, 1, 1], [0, 0, 1, 2]), expected, places=12)
        self.assertEqual(drift.EPSILON, 1e-4)

    def test_missing_values_have_their_own_bin(self):
        expected = term(0, .25) + term(.75, .5)
        self.assertAlmostEqual(drift.psi([1, 2, None, None], [1, None, None, None]), expected, places=12)
        self.assertEqual(drift.null_share([1, None, float('nan'), 2]), 0.5)

    def test_reference_decile_edges_by_hand(self):
        reference, current = list(range(1, 21)), list(range(11, 31))
        self.assertEqual(drift.bin_rule(reference), ('edges', [2, 4, 6, 8, 10, 12, 14, 16, 18]))
        # Reference: 2 values per bin (0.1 each). Current: 0 in bins 1-5, 0.1 in bins 6-9, 0.6 above 18.
        expected = 5 * term(0, .1) + term(.6, .1)
        self.assertAlmostEqual(drift.psi(reference, current), expected, places=12)

    def test_categories_get_value_bins_and_no_ks(self):
        result = drift.compare(['A', 'A', 'B', None], ['A', 'B', 'B', None], categorical=True)
        self.assertAlmostEqual(result['psi'], term(.25, .5) + term(.5, .25), places=12)
        self.assertIsNone(result['ks'])

    def test_compare_reports_non_missing_coverage_and_reading(self):
        result = drift.compare([1.0, None, 3.0, 4.0], [1.0, None, None, 4.0])
        self.assertEqual((result['reference_available'], result['current_available']), (3, 2))
        self.assertEqual(result['reading'], drift.reading(result['psi']))
        self.assertEqual(drift.compare([1.0, 2.0], [1.0, 2.0])['reading'], 'No shift')

    def test_reading_is_the_stated_convention(self):
        self.assertEqual(drift.PSI_CONVENTION, (0.10, 0.25))
        self.assertEqual([drift.reading(v) for v in (0.0999, 0.1, 0.2499, 0.25)],
                         ['Little shift', 'Moderate shift', 'Moderate shift', 'Large shift'])


class KsTests(unittest.TestCase):
    # Expected statistics checked by hand and against scipy.stats.ks_2samp(...).statistic (scipy 1.16, fyp-model-env).
    CASES = [([1, 2, 3, 4], [3, 4, 5, 6], 0.5),
             ([1, 1, 2, 2, 3], [1, 2, 2, 2, 2], 0.2),
             (list(range(1, 21)), list(range(11, 31)), 0.5),
             ([0.5, None, 1.5], [0.5, 1.5, None], 0.0)]

    def test_ks_statistic_on_hand_fixtures(self):
        for reference, current, expected in self.CASES:
            with self.subTest(reference=reference):
                self.assertAlmostEqual(drift.ks(reference, current), expected, places=12)
        self.assertIsNone(drift.ks([None], [1.0]))

    @unittest.skipUnless(ks_2samp, 'scipy is available only in the modelling environment')
    def test_ks_matches_scipy(self):
        for reference, current, _ in self.CASES:
            first = [v for v in reference if v is not None]
            second = [v for v in current if v is not None]
            self.assertAlmostEqual(drift.ks(reference, current), float(ks_2samp(first, second).statistic), places=12)


FIXTURE = Path(__file__).resolve().parent / 'fixtures' / 'opr_package'
FRONTEND_FIXTURE = Path(__file__).resolve().parents[2] / 'frontend' / 'tests' / 'fixtures' / 'opr-scenarios.json'


class ScenarioPackageTests(unittest.TestCase):
    """The shared representative fixture (built by make_opr_fixture.py) is the valid package; malformed copies are invalid."""
    def setUp(self):
        unconfigured(self)  # Never inherit saved TXB_*/Gemini settings.
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.db = root / 'test.sqlite'
        self.package = root / 'package'
        self.app = create_app(dict(TESTING=True, DATABASE=str(self.db), TXB_SCENARIO_DIR=str(self.package)))
        with self.app.app_context():
            import_demo()

    def copy_fixture(self):
        shutil.copytree(FIXTURE, self.package)

    def rewrite(self, name, change, rehash=True):
        """Edit one package file and, by default, re-record its hash so only the contract check can reject it."""
        path = self.package / name
        if name.endswith('.json'):
            data = json.loads(path.read_text(encoding='utf-8'))
            result = change(data)
            data = data if result is None else result
            path.write_text(json.dumps(data), encoding='utf-8')
        else:
            path.write_text(change(path.read_text(encoding='utf-8')), encoding='utf-8')
        if rehash and name in ('drift.json', 'scores.csv'):
            manifest = json.loads((self.package / 'manifest.json').read_text(encoding='utf-8'))
            manifest['files'][name] = hashlib.sha256(path.read_bytes()).hexdigest()
            (self.package / 'manifest.json').write_text(json.dumps(manifest), encoding='utf-8')

    def get(self):
        before = hashlib.sha256(self.db.read_bytes()).hexdigest()
        response = self.app.test_client().get('/api/scenarios')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(hashlib.sha256(self.db.read_bytes()).hexdigest(), before)  # The reader never writes the database.
        return response

    def test_missing_package_is_not_generated(self):
        self.assertEqual(self.get().json, dict(state='not_generated'))

    def test_representative_package_is_ready_and_is_exactly_the_frontend_fixture(self):
        self.copy_fixture()
        body = self.get().json
        self.assertEqual(body['state'], 'ready')
        self.assertEqual(body, json.loads(FRONTEND_FIXTURE.read_text(encoding='utf-8')))  # One shared renderable contract.
        self.assertEqual(body['note'], 'This scenario changes deposit-related inputs only. Transaction activity, digital engagement '
                                       'and service-friction input values are held constant. Scenario-specific SHAP explanations are not computed.')
        self.assertNotIn('main drivers', json.dumps(body))
        self.assertEqual([s['id'] for s in body['scenarios']], ['no_shock', 'mild', 'severe'])
        with self.app.app_context():
            self.assertEqual(get_db().execute("SELECT count(*) FROM sqlite_master WHERE name LIKE '%scenario%'").fetchone()[0], 0)

    def test_stressed_assessment_month_is_resolved_read_only_from_the_package_batch(self):
        self.copy_fixture()
        body = self.get().json
        self.assertEqual((body['batch_id'], body['assessment']), ('fixture-batch', None))  # Not in this database.
        with self.app.app_context():
            batch_id, cutoff = get_db().execute('SELECT batch_id, cutoff_month FROM batches LIMIT 1').fetchone()
        self.rewrite('manifest.json', lambda m: m.update(batch_id=batch_id))
        body = self.get().json  # get() also proves the database bytes are unchanged.
        self.assertEqual(body['state'], 'ready')
        self.assertEqual((body['batch_id'], body['assessment']), (batch_id, dict(cutoff_month=cutoff)))
        self.rewrite('manifest.json', lambda m: m.update(batch_id=''))
        self.assertEqual(self.get().json, dict(state='invalid'))  # A package must name its batch.

    def test_tampered_file_or_failed_gate_is_rejected(self):
        self.copy_fixture()
        self.rewrite('scores.csv', lambda t: t + 'mild,F99,0.1,0.1,0\n', rehash=False)
        self.assertEqual(self.get().json, dict(state='invalid'))
        shutil.rmtree(self.package); self.copy_fixture()
        self.rewrite('manifest.json', lambda m: m['gates']['reproduction'].update(flag_mismatches=1))
        self.assertEqual(self.get().json, dict(state='invalid'))

    def test_malformed_packages_are_invalid_never_an_error(self):
        def drop_register_scenarios(m):
            del m['register']['scenarios']
        def drop_severe(d):
            d['scenarios'] = d['scenarios'][:2]
        def nan_psi(d):
            d['scenarios'][1]['input_drift']['fd_balance_myr']['psi'] = float('nan')
        def ks_out_of_range(d):
            d['scenarios'][2]['input_drift']['fd_balance_myr']['ks'] = 1.5
        def missing_predictor(d):
            del d['scenarios'][1]['input_drift']['tier_id']
        def inconsistent_counts(d):
            d['scenarios'][2]['exit_affected_customers'] = d['scenarios'][2]['assigned_exit_customers'] + 1
        def flagged_mismatch(d):
            d['scenarios'][2]['prediction_change']['flagged'] += 1
        def wrong_nested_type(d):
            d['scenarios'][1]['prediction_change'] = []
        def list_files(m):
            m['files'] = []
        cases = [
            ('manifest.json', lambda m: []), ('drift.json', lambda d: []), ('manifest.json', list_files),
            ('manifest.json', drop_register_scenarios), ('manifest.json', lambda m: m['gates'].update(parity=[])),
            ('drift.json', drop_severe), ('drift.json', nan_psi), ('drift.json', ks_out_of_range),
            ('drift.json', missing_predictor), ('drift.json', inconsistent_counts), ('drift.json', flagged_mismatch),
            ('drift.json', wrong_nested_type),
            ('scores.csv', lambda t: t.split('\n', 1)[0] + '\n'),            # Header only.
            ('scores.csv', lambda t: t.rsplit('\n', 2)[0] + '\n'),           # One customer short.
            ('scores.csv', lambda t: t.replace('scenario_review_alert', 'alert')),
            ('scores.csv', lambda t: t.replace(',1\n', ',0\n', 1)),          # Flagged total no longer reconciles.
        ]
        for name, change in cases:
            with self.subTest(file=name, case=getattr(change, '__name__', '')):
                shutil.rmtree(self.package, ignore_errors=True)
                self.copy_fixture()
                self.rewrite(name, change)
                self.assertEqual(self.get().json, dict(state='invalid'))

    def test_malformed_json_text_is_invalid(self):
        self.copy_fixture()
        (self.package / 'manifest.json').write_text('{not json', encoding='utf-8')
        self.assertEqual(self.get().json, dict(state='invalid'))


if __name__ == '__main__':
    unittest.main()
