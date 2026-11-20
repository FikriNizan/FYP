"""Offline tests for Revenue at Risk (RaR) and Fee Subsidy Leakage (FSL). Hand-calculated values."""
import json
import tempfile
import unittest
from pathlib import Path
from churn_backend import create_app, ai_drafts as ai, ai_evidence as evidence, ai_render as render
from churn_backend import finance_metrics as fm
from churn_backend.db import get_db
from churn_backend.importer import import_demo

APRIL = '2024-04-30'
# Owner's worked example: April 2024 prediction 36d5187951d9..., customer 604 (saved feature values).
WORKED = dict(tier_id='SME_S', estimated_fee_mean_3m_myr=0.2877666667, estimated_waiver_mean_3m_myr=25.6355666667,
              non_fd_balance_myr=18313.53, fd_balance_myr=0.0, fd_balance_weighted_offer_rate=None,
              catalog_waiver_mean_pct=0.7998571429)


def features(**changes):
    return {**WORKED, **changes}


class FormulaTests(unittest.TestCase):
    def test_worked_example_to_the_cent(self):
        m = fm.customer_metrics(WORKED, APRIL)
        c = m['components']
        self.assertAlmostEqual(c['fee_income'], 0.2877666667)
        self.assertAlmostEqual(c['transaction_cost'], (0.2877666667 + 25.6355666667) / 1.40)   # 18.5167
        self.assertEqual(c['fd_earnings'], 0.0)
        self.assertAlmostEqual(c['operating_earnings'], 18313.53 * (1 - 0.02) * 0.03 / 12)     # 44.8681
        self.assertEqual(round(m['contribution_monthly'], 2), 26.64)
        self.assertEqual(round(m['rar_3m'], 2), 79.92)
        self.assertEqual((m['opr'], m['srr'], m['window_months']), (0.03, 0.02, 3))
        self.assertEqual((m['fsl_a']['status'], round(m['fsl_a']['monthly'], 2)), ('deal_broken', 25.64))
        self.assertEqual((m['fsl_b']['status'], round(m['fsl_b']['monthly'], 2)), ('deal_not_paying', 18.23))
        self.assertEqual(m['unavailable'], [])

    def test_missing_is_not_zero(self):
        # A genuine zero FD balance earns zero even though the offer rate is null.
        self.assertEqual(fm.customer_metrics(WORKED, APRIL)['components']['fd_earnings'], 0.0)
        no_fd = fm.customer_metrics(features(fd_balance_myr=None), APRIL)
        self.assertIsNone(no_fd['components']['fd_earnings'])
        self.assertIsNone(no_fd['contribution_monthly'])
        self.assertIsNone(no_fd['rar_3m'])
        self.assertIn('fixed deposit balance missing', no_fd['unavailable'])
        no_rate = fm.customer_metrics(features(fd_balance_myr=50000.0, fd_balance_weighted_offer_rate=None), APRIL)
        self.assertIn('fixed deposit offer rate missing', no_rate['unavailable'])
        self.assertIsNone(no_rate['contribution_monthly'])
        no_operating = fm.customer_metrics(features(non_fd_balance_myr=None), APRIL)
        self.assertIsNone(no_operating['components']['operating_earnings'])
        self.assertIsNone(no_operating['contribution_monthly'])
        self.assertIsNotNone(no_operating['components']['transaction_cost'])  # Other components still shown.
        no_fee = fm.customer_metrics(features(estimated_fee_mean_3m_myr=None), APRIL)
        self.assertIsNone(no_fee['contribution_monthly'])
        self.assertEqual(no_fee['fsl_b']['status'], 'unavailable')

    def test_negative_fd_earnings_are_shown_not_clipped(self):
        m = fm.customer_metrics(features(fd_balance_myr=1200000.0, fd_balance_weighted_offer_rate=0.04), APRIL)
        self.assertAlmostEqual(m['components']['fd_earnings'], 1200000.0 * (0.03 + 0.005 - 0.04) / 12)   # -500.00
        self.assertLess(m['components']['fd_earnings'], 0)

    def test_liquidity_premium_sensitivity(self):
        m = fm.customer_metrics(features(fd_balance_myr=1200000.0, fd_balance_weighted_offer_rate=0.03), APRIL)
        earnings = [round(s['fd_earnings'], 6) for s in m['sensitivity']]
        self.assertEqual([s['liquidity_premium'] for s in m['sensitivity']], [0.0, 0.005, 0.01])
        self.assertEqual(earnings, [0.0, 500.0, 1000.0])
        base = next(s for s in m['sensitivity'] if s['liquidity_premium'] == 0.005)
        self.assertAlmostEqual(base['contribution_monthly'], m['contribution_monthly'])
        self.assertAlmostEqual(m['sensitivity'][2]['contribution_monthly'] - m['sensitivity'][0]['contribution_monthly'], 1000.0)

    def test_cost_ratio_sensitivity_scales_transaction_cost_only(self):
        m = fm.customer_metrics(WORKED, APRIL)
        self.assertEqual([s['cost_ratio'] for s in m['cost_sensitivity']], [1.0, 0.75, 0.5])
        base_cost = (0.2877666667 + 25.6355666667) / 1.40
        for variant in m['cost_sensitivity']:
            with self.subTest(ratio=variant['cost_ratio']):
                self.assertAlmostEqual(variant['transaction_cost'], base_cost * variant['cost_ratio'])
                self.assertAlmostEqual(variant['contribution_monthly'], m['contribution_monthly'] + base_cost * (1 - variant['cost_ratio']))
                self.assertAlmostEqual(variant['rar_3m'], 3 * variant['contribution_monthly'])
        # Worked example: contribution 26.64 / 31.27 / 35.90; FSL B 18.23 / 13.60 / 8.97 a month.
        self.assertEqual([round(v['contribution_monthly'], 2) for v in m['cost_sensitivity']], [26.64, 31.27, 35.90])
        self.assertEqual([round(v['fsl_b_monthly'], 2) for v in m['cost_sensitivity']], [18.23, 13.6, 8.97])
        self.assertEqual(m['cost_ratio'], 1.0)  # Base case stays the conservative full price-cap cost.

    def test_check_a_uses_strictly_below_threshold_and_needs_an_active_waiver(self):
        below = fm.customer_metrics(features(fd_balance_myr=99999.99, fd_balance_weighted_offer_rate=0.03), APRIL)
        equal = fm.customer_metrics(features(fd_balance_myr=100000.0, fd_balance_weighted_offer_rate=0.03), APRIL)
        no_waiver = fm.customer_metrics(features(catalog_waiver_mean_pct=0.0), APRIL)
        self.assertEqual((below['fsl_a']['status'], below['fsl_a']['flagged']), ('deal_broken', True))
        self.assertEqual((equal['fsl_a']['status'], equal['fsl_a']['flagged']), ('deal_kept', False))
        self.assertEqual((no_waiver['fsl_a']['status'], no_waiver['fsl_b']['status']), ('no_active_waiver', 'no_active_waiver'))
        self.assertFalse(no_waiver['fsl_b']['flagged'])

    def test_policy_exempt_customers_are_excluded_from_a_and_labelled_in_b(self):
        m = fm.customer_metrics(features(tier_id='CORP_XL'), APRIL)
        self.assertEqual((m['waiver_basis'], m['fsl_a']['status'], m['fsl_a']['flagged']), ('POLICY_EXEMPT', 'policy_exemption', False))
        self.assertEqual((m['fsl_b']['status'], m['fsl_b']['flagged'], m['fsl_b']['policy']), ('policy', True, True))

    def test_check_b_boundary_equal_is_not_flagged(self):
        covered = fm.customer_metrics(features(estimated_fee_mean_3m_myr=10.0, estimated_waiver_mean_3m_myr=0.0), APRIL)
        self.assertEqual((covered['fsl_b']['shortfall'], covered['components']['fd_earnings']), (0.0, 0.0))
        self.assertEqual((covered['fsl_b']['status'], covered['fsl_b']['flagged']), ('covered', False))  # 0 > 0 is false.
        just_over = fm.customer_metrics(features(estimated_fee_mean_3m_myr=10.0, estimated_waiver_mean_3m_myr=4.2), APRIL)
        self.assertGreater(just_over['fsl_b']['shortfall'], 0)
        self.assertTrue(just_over['fsl_b']['flagged'])

    def test_unknown_tier_or_unverified_cutoff_makes_measures_unavailable(self):
        unknown = fm.customer_metrics(features(tier_id='NEW_TIER'), APRIL)
        self.assertIn('unknown tier', unknown['unavailable'])
        self.assertIsNone(unknown['rar_3m'])
        self.assertEqual(unknown['fsl_a']['status'], 'unavailable')
        later = fm.customer_metrics(WORKED, '2025-01-31')
        self.assertIn('OPR not verified for this cutoff', later['unavailable'])
        self.assertIsNone(later['rar_3m'])
        for cutoff in ['2024-02-29', '2024-03-31', APRIL]:
            self.assertEqual((fm.rate_on(fm.OPR_TABLE, cutoff)['rate'], fm.rate_on(fm.SRR_TABLE, cutoff)['rate']), (0.03, 0.02))

    def test_tier_terms_are_pinned_to_the_verified_reference(self):
        self.assertEqual({tier: (t['markup'], t['fd_threshold_myr'], t['basis']) for tier, t in fm.TIER_TERMS.items()}, {
            'SME_S': (0.40, 100000.0, 'FD_THRESHOLD'), 'SME_M': (0.30, 500000.0, 'FD_THRESHOLD'),
            'CORP_L': (0.15, 2000000.0, 'FD_THRESHOLD'), 'CORP_XL': (0.05, 5000000.0, 'POLICY_EXEMPT'),
            'GOV': (0.05, 3000000.0, 'POLICY_EXEMPT')})


class PortfolioAndCardTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.app = create_app(dict(TESTING=True, DATABASE=str(Path(self.temp.name) / 'test.sqlite')))
        with self.app.app_context():
            import_demo()
            db = get_db()
            row = db.execute('SELECT prediction_id, features_json FROM predictions').fetchone()
            self.id = row['prediction_id']
            base = json.loads(row['features_json'])
            # Keep the demo's saved driver value for non_fd_balance_myr (evidence integrity check); other inputs from WORKED.
            base.update({k: v for k, v in WORKED.items() if k != 'non_fd_balance_myr'})
            self.base = base
            db.execute('UPDATE predictions SET features_json=? WHERE prediction_id=?', (json.dumps(base), self.id))
            # Extra synthetic customers in the same batch (driver values unchanged; not scored).
            self.extra = {'p-policy': (dict(base, tier_id='CORP_XL'), 0), 'p-unknown': (dict(base, tier_id=None), 1),
                          'p-kept': (dict(base, fd_balance_myr=150000.0, fd_balance_weighted_offer_rate=0.03), 0)}
            for pid, (feats, alert) in self.extra.items():
                db.execute("INSERT INTO predictions SELECT ?,batch_id,?,risk,?,evidence_json,?,customer_json,flows_json "
                           "FROM predictions WHERE prediction_id=?", (pid, pid, alert, json.dumps(feats), self.id))
            db.commit()

    def test_portfolio_totals_coverage_and_groups(self):
        with self.app.app_context():
            report = fm.portfolio(get_db().execute('SELECT batch_id FROM predictions WHERE prediction_id=?', (self.id,)).fetchone()[0])
            cutoff = report['cutoff']
            all_features = [self.base] + [feats for feats, _ in self.extra.values()]
            metrics = [fm.customer_metrics(f, cutoff, with_sensitivity=False) for f in all_features]
        totals = report['totals']
        self.assertEqual((totals['customers'], totals['available']), (4, 3))   # Unknown tier is not covered.
        self.assertAlmostEqual(totals['rar_3m'], sum(m['rar_3m'] for m in metrics if m['rar_3m'] is not None))
        self.assertEqual(totals['fsl_a_customers'], 1)                        # Worked example only; p-kept meets the threshold.
        self.assertEqual(totals['policy_fsl_b_customers'], 1)                 # CORP_XL shown separately as policy.
        self.assertEqual(totals['both_customers'], 1)
        self.assertEqual(set(report['by_tier']), {'SME_S', 'CORP_XL', 'unknown'})
        self.assertEqual({k: v['customers'] for k, v in report['by_flag'].items()}, {'flagged': 2, 'not_flagged': 2})
        self.assertIn('must not be added', report['note'])
        # Cost-ratio and liquidity-premium sensitivities; the base case equals the headline totals.
        self.assertEqual(report['cost_ratios'], [1.0, 0.75, 0.5])
        self.assertAlmostEqual(totals['cost_sensitivity']['1.0']['rar_3m'], totals['rar_3m'])
        self.assertAlmostEqual(totals['premium_sensitivity']['0.005']['rar_3m'], totals['rar_3m'])
        self.assertAlmostEqual(totals['cost_sensitivity']['0.5']['rar_3m'],
                               sum(fm.customer_metrics(f, cutoff, cost_ratio=0.5)['rar_3m'] for f in all_features
                                   if fm.customer_metrics(f, cutoff)['rar_3m'] is not None))
        self.assertEqual(set(report['by_basis']), {'FD_THRESHOLD', 'POLICY_EXEMPT', 'unknown'})
        self.assertEqual(report['by_basis']['POLICY_EXEMPT']['customers'], 1)
        summary = self.app.test_client().get('/api/summary').json
        self.assertEqual(summary['finance_metrics']['totals']['customers'], 4)
        detail = self.app.test_client().get('/api/customers/944').json['customer']['finance_metrics']
        self.assertAlmostEqual(detail['rar_3m'], metrics[0]['rar_3m'])
        self.assertEqual([s['liquidity_premium'] for s in detail['sensitivity']], [0.0, 0.005, 0.01])

    def test_card_states_contribution_at_stake_with_flags_and_keeps_it_out_of_the_provider_payload(self):
        with self.app.app_context():
            data = evidence.build('summary', self.id)
            card = ai.fallback(data)
            payload = json.dumps(render.provider_payload(data))
        finance = [item['text'] for s in card['sections'] if s['id'] == 'finance' for item in s['items']]
        stake = next(text for text in finance if text.startswith('Contribution at stake'))
        from churn_backend.briefings import money, forecast
        expected = fm.customer_metrics(self.base, data['identity']['cutoff'], with_sensitivity=False)
        # Check B ignores operating-balance earnings by definition, so a large operating balance can still flag B.
        self.assertTrue(expected['fsl_a']['flagged'] and expected['fsl_b']['flagged'])
        self.assertEqual(stake, f"Contribution at stake over {forecast(data['identity']['cutoff'])}: {money(expected['rar_3m'])} "
                                '(estimated relationship contribution; not a loss forecast; fee waiver condition not met; '
                                'waiver cost exceeds deposit earnings).')
        self.assertNotIn('Contribution at stake', payload)  # Deterministic only: never sent to Gemini.
        self.assertLessEqual(render.card_words(card), 240)
        self.assertEqual(data['finance_metrics']['rar_3m'], expected['rar_3m'])

    def test_card_wording_for_negative_contribution_and_policy_exemption(self):
        with self.app.app_context():
            data = evidence.build('summary', self.id)
        negative = dict(data, finance_metrics=dict(contribution_monthly=-12.5, rar_3m=-37.5, fsl_a=dict(flagged=False),
                                                   fsl_b=dict(flagged=True, policy=True)))
        [text] = render.stake_line(negative)
        self.assertEqual(text['text'], 'Estimated relationship contribution is negative: -RM 12.50 a month (an estimate, not a loss forecast).')
        self.assertEqual(render.stake_line(dict(data, finance_metrics=dict(contribution_monthly=None))), [])


if __name__ == '__main__':
    unittest.main()
