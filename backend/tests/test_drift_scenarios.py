"""Milestone 7: PSI/KS on hand-checkable fixtures and the read-only scenario package. No network, no model."""
import math
import unittest
from churn_backend import drift

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


if __name__ == '__main__':
    unittest.main()
