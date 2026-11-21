"""Milestone 7 scenario generator. Register and seeded selection run everywhere; the pandas, real-data and scipy
tests run in the modelling environment (fyp-model-env) and are skipped in the app .venv."""
import importlib.util
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('opr_scenarios', ROOT / 'scripts' / 'opr_scenarios.py')
opr = importlib.util.module_from_spec(spec)
spec.loader.exec_module(opr)

try:
    import pandas as pd
except ImportError:
    pd = None
try:
    from scipy.stats import ks_2samp
except ImportError:
    ks_2samp = None
RESEARCH = Path(os.environ.get('TXB_RESEARCH_ROOT') or r'C:\Users\fikri\OneDrive - Asia Pacific University of Technology And Innovation (APU)'
                r'\Degree\SEM 6\Project Module (FYP)\fyp-data-refinement')
TEST_DB = ROOT / 'artifacts' / 'm6-review.sqlite'
REAL = pd is not None and (RESEARCH / 'data' / 'models' / 'final_refit_v1' / opr.CHAMPION_FILE).is_file() and TEST_DB.is_file()


class RegisterTests(unittest.TestCase):
    def test_register_is_pinned(self):
        r = opr.REGISTER
        self.assertEqual((r['version'], r['seed'], r['cutoff'], r['direction']), ('m7-opr-1', 20240430, '2024-04-30', 'hike'))
        self.assertEqual([(s['id'], s['shock_bp'], s['migrating_share']) for s in r['scenarios']],
                         [('no_shock', 0, 0.0), ('mild', 25, 0.05), ('severe', 125, 0.20)])
        self.assertEqual((r['effective_date'], r['lag_months'], r['repricing_from'], r['window_end']),
                         ('2024-02-01', 1, '2024-03-01', '2024-04-30'))
        self.assertEqual((r['own_pass_through'], r['competitor_pass_through']), (0.5, 1.0))
        self.assertTrue(r['transaction_response'].startswith('off'))
        self.assertIn('no early withdrawal', r['renewal_rule'])
        self.assertEqual(r['sources']['opr_decisions'], 'https://www.bnm.gov.my/monetary-stability/opr-decisions')
        self.assertEqual(opr.RAW_BOUNDARY, 0.2991379097436803)
        self.assertEqual(opr.TOLERANCE, 1e-12)

    def test_migrants_are_seeded_and_nested(self):
        cohort = [f'C{i:04d}' for i in range(398)]
        first, second = opr.migrant_order(cohort), opr.migrant_order(list(reversed(cohort)))
        self.assertEqual(first, second)  # Depends only on the seed and the set of customers.
        mild, severe = first[:round(0.05 * 398)], first[:round(0.20 * 398)]
        self.assertEqual((len(mild), len(severe)), (20, 80))
        self.assertTrue(set(mild) <= set(severe))


@unittest.skipUnless(pd is not None, 'pandas is available only in the modelling environment')
class MaturityRuleTests(unittest.TestCase):
    def accounts(self):
        rows = []
        for acc, cus, maturity in [('F1', 'A', '2024-03-15'), ('F2', 'A', '2024-06-01'), ('F3', 'B', '2024-04-10')]:
            for snap in ['2024-01-31', '2024-02-29', '2024-03-31', '2024-04-30']:
                rows.append(dict(cus_id=cus, acc_no=acc, snapshot_month_clean=snap, account_type='FIXED_DEPOSIT',
                                 account_status_id='ACTIVE', ledger_amount='1000', average_amount='1000',
                                 rate_offer='0.03', maturity_date_clean=maturity))
        return pd.DataFrame(rows)

    def test_only_fds_maturing_in_the_window_close_or_reprice(self):
        accounts = self.accounts()
        maturities = opr.jan_maturities(accounts)
        severe = dict(shock_bp=125, migrating_share=0.2)
        shocked, counts = opr.apply_scenario(accounts, severe, {'A'}, maturities)
        self.assertEqual((counts['fds_maturing_in_window'], counts['fds_closed'], counts['fds_repriced']), (2, 1, 1))
        get = lambda acc, snap, col: shocked[(shocked.acc_no == acc) & (shocked.snapshot_month_clean == snap)][col].item()
        # F1 (migrant A, matures 15 Mar): open before maturity, closed with zero balances from the March snapshot.
        self.assertEqual((get('F1', '2024-02-29', 'account_status_id'), get('F1', '2024-03-31', 'account_status_id')), ('ACTIVE', 'CLOSED'))
        self.assertEqual(get('F1', '2024-04-30', 'ledger_amount'), '0')
        # F2 (migrant A, matures in June): no early withdrawal, untouched.
        self.assertTrue(shocked[shocked.acc_no == 'F2'].equals(accounts[accounts.acc_no == 'F2']))
        # F3 (non-migrant B, matures 10 Apr): repriced by 50% x 125 bp only from the April snapshot.
        self.assertEqual(get('F3', '2024-03-31', 'rate_offer'), '0.03')
        self.assertAlmostEqual(float(get('F3', '2024-04-30', 'rate_offer')), 0.03 + 0.5 * 0.0125, places=12)
        unchanged, none = opr.apply_scenario(accounts, dict(shock_bp=0, migrating_share=0.0), set(), maturities)
        self.assertTrue(unchanged.equals(accounts))
        self.assertEqual(none['fds_closed'] + none['fds_repriced'], 0)


@unittest.skipUnless(ks_2samp is not None, 'scipy is available only in the modelling environment')
class ScipyComparisonTests(unittest.TestCase):
    def test_ks_matches_scipy_on_fixtures_and_random_samples(self):
        import random
        rng = random.Random(7)
        cases = [([1, 2, 3, 4], [3, 4, 5, 6]), ([1, 1, 2, 2, 3], [1, 2, 2, 2, 2]), (list(range(1, 21)), list(range(11, 31)))]
        cases += [([rng.gauss(0, 1) for _ in range(300)], [rng.gauss(.2, 1.1) for _ in range(250)]),
                  ([rng.randint(0, 4) for _ in range(500)], [rng.randint(0, 5) for _ in range(400)])]
        for first, second in cases:
            self.assertAlmostEqual(opr.drift.ks(first, second), float(ks_2samp(first, second).statistic), places=12)


@unittest.skipUnless(REAL, 'needs the research data, the champion and the Test database (modelling environment)')
class RealDataTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.mkdtemp()
        cls.manifest, cls.results = opr.run(RESEARCH, TEST_DB, Path(cls.temp) / 'first')
        opr.run(RESEARCH, TEST_DB, Path(cls.temp) / 'second')

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.temp)

    def test_gates_pass_exactly(self):
        gates = self.manifest['gates']
        self.assertEqual(set(gates['parity']['mismatches'].values()), {0})
        self.assertEqual(len(gates['parity']['features']), 11)
        r = gates['reproduction']
        self.assertLessEqual(max(r['max_abs_raw_difference'], r['max_abs_risk_difference']), 1e-12)
        self.assertEqual((r['flag_mismatches'], r['saved_flagged']), (0, 206))

    def test_same_seed_gives_byte_identical_packages(self):
        for name in ('manifest.json', 'scores.csv', 'drift.json'):
            first = (Path(self.temp) / 'first' / name).read_bytes()
            self.assertEqual(first, (Path(self.temp) / 'second' / name).read_bytes(), name)

    def test_no_shock_has_zero_drift_and_reproduces_saved_scores(self):
        none = next(r for r in self.results if r['id'] == 'no_shock')
        self.assertEqual(none['changed_features'], [])
        self.assertEqual({d['psi'] for d in none['input_drift'].values()}, {0.0})
        self.assertEqual({d['ks'] for d in none['input_drift'].values()} - {None}, {0.0})
        p = none['prediction_change']
        self.assertEqual((p['risk']['psi'], p['risk']['ks'], p['risk']['changed_values']), (0.0, 0.0, 0))
        self.assertEqual((p['crossed_into_review'], p['crossed_out_of_review'], p['flagged']), (0, 0, 206))

    def test_only_deposit_inputs_can_change(self):
        for r in self.results:
            self.assertTrue(set(r['changed_features']) <= set(opr.ACCOUNT_FEATURES), r['id'])
            self.assertEqual(r['performance_change'], 'Not computed: no outcomes exist under a hypothetical shock.')
        self.assertEqual(json.loads((Path(self.temp) / 'first' / 'drift.json').read_text())['note'],
                         'Scenario output only: hypothetical, not saved predictions.')


if __name__ == '__main__':
    unittest.main()
