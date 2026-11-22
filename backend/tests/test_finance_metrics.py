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
        self.assertAlmostEqual(m['components']['fd_earnings'], 1200000.0 * ((1 - 0.02) * (0.03 + 0.005) - 0.04) / 12)   # -570.00
        self.assertAlmostEqual(m['components']['fd_earnings'], -570.0)
        self.assertLess(m['components']['fd_earnings'], 0)

    def test_fd_earnings_formula_nets_srr(self):
        # Owner formula (2026-11-23): fd x ((1 - SRR) x (OPR + premium) - offer rate) / 12.
        value, reason = fm.fd_earnings(1200000.0, 0.025, 0.03, 0.005, 0.02)
        self.assertIsNone(reason)
        self.assertAlmostEqual(value, 1200000.0 * (0.98 * 0.035 - 0.025) / 12)   # 930.00
        self.assertAlmostEqual(value, 930.0)
        self.assertLess(value, 1200000.0 * (0.035 - 0.025) / 12)                 # Below the old formula (1,000.00).
        # Signed, never clipped.
        self.assertAlmostEqual(fm.fd_earnings(1200000.0, 0.04, 0.03, 0.005, 0.02)[0], -570.0)
        # SRR unavailable: FD earnings unavailable with a clear reason, like OPR.
        self.assertEqual(fm.fd_earnings(1200000.0, 0.025, 0.03, 0.005, None), (None, 'SRR not verified for this cutoff'))
        self.assertEqual(fm.fd_earnings(1200000.0, 0.025, None, 0.005, 0.02), (None, fm.OPR_UNVERIFIED))
        # A genuine zero balance earns zero, whatever the rates.
        self.assertEqual(fm.fd_earnings(0.0, None, None, 0.005, None), (0.0, None))
        self.assertEqual(fm.fd_earnings(0.0, 0.03, 0.03, 0.005, 0.02), (0.0, None))
        # In customer_metrics, a cutoff with OPR but no SRR row makes FD earnings and the contribution unavailable.
        original = fm.SRR_TABLE[:]
        try:
            fm.SRR_TABLE[:] = []
            m = fm.customer_metrics(features(fd_balance_myr=1200000.0, fd_balance_weighted_offer_rate=0.025), APRIL)
        finally:
            fm.SRR_TABLE[:] = original
        self.assertIsNone(m['components']['fd_earnings'])
        self.assertIsNone(m['contribution_monthly'])
        self.assertEqual(m['unavailable'].count('SRR not verified for this cutoff'), 1)
        self.assertEqual(m['fsl_b']['status'], 'unavailable')
        # Every sensitivity variant uses the new formula.
        m = fm.customer_metrics(features(fd_balance_myr=1200000.0, fd_balance_weighted_offer_rate=0.025), APRIL)
        for variant in m['sensitivity']:
            self.assertAlmostEqual(variant['fd_earnings'], 1200000.0 * (0.98 * (0.03 + variant['liquidity_premium']) - 0.025) / 12)

    def test_liquidity_premium_sensitivity(self):
        m = fm.customer_metrics(features(fd_balance_myr=1200000.0, fd_balance_weighted_offer_rate=0.03), APRIL)
        earnings = [round(s['fd_earnings'], 6) for s in m['sensitivity']]
        self.assertEqual([s['liquidity_premium'] for s in m['sensitivity']], [0.0, 0.005, 0.01])
        self.assertEqual(earnings, [-60.0, 430.0, 920.0])
        base = next(s for s in m['sensitivity'] if s['liquidity_premium'] == 0.005)
        self.assertAlmostEqual(base['contribution_monthly'], m['contribution_monthly'])
        self.assertAlmostEqual(m['sensitivity'][2]['contribution_monthly'] - m['sensitivity'][0]['contribution_monthly'], 980.0)

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

    def test_check_b_review_probe_negative_fd_does_not_create_a_transaction_shortfall(self):
        # Review probe: fee income RM100, assumed transaction cost RM72.14, FD earnings -RM20 -> not flagged.
        m = fm.customer_metrics(features(estimated_fee_mean_3m_myr=100.0, estimated_waiver_mean_3m_myr=0.996,
                                         fd_balance_myr=48000.0, fd_balance_weighted_offer_rate=0.0393), APRIL)
        self.assertAlmostEqual(m['components']['transaction_cost'], 72.14)
        self.assertAlmostEqual(m['components']['fd_earnings'], -20.0)
        self.assertEqual((m['fsl_b']['status'], m['fsl_b']['flagged'], m['fsl_b']['monthly'], m['fsl_b']['shortfall']),
                         ('covered', False, None, 0.0))
        self.assertLess(m['components']['fd_earnings'], 0)  # Still visible as its own component.

    def test_check_b_shortfall_with_non_positive_fd_is_uncovered_in_full(self):
        for rate, expected_fd in [(0.0393, -20.0), (0.0343, 0.0)]:
            with self.subTest(fd=expected_fd):
                m = fm.customer_metrics(features(fd_balance_myr=48000.0, fd_balance_weighted_offer_rate=rate), APRIL)
                self.assertAlmostEqual(m['components']['fd_earnings'], expected_fd)
                shortfall = m['components']['transaction_cost'] - m['components']['fee_income']
                self.assertTrue(m['fsl_b']['flagged'])
                self.assertAlmostEqual(m['fsl_b']['monthly'], shortfall)   # Not shortfall - FD (negative FD not folded in).
                self.assertEqual(round(m['fsl_b']['monthly'], 2), 18.23)

    def test_check_b_positive_fd_covers_or_partly_covers_the_shortfall(self):
        covered = fm.customer_metrics(features(fd_balance_myr=48000.0, fd_balance_weighted_offer_rate=0.0193), APRIL)
        self.assertAlmostEqual(covered['components']['fd_earnings'], 60.0)
        self.assertEqual((covered['fsl_b']['status'], covered['fsl_b']['flagged']), ('covered', False))
        partly = fm.customer_metrics(features(fd_balance_myr=48000.0, fd_balance_weighted_offer_rate=0.0323), APRIL)
        self.assertAlmostEqual(partly['components']['fd_earnings'], 8.0)
        self.assertTrue(partly['fsl_b']['flagged'])
        self.assertEqual(round(partly['fsl_b']['monthly'], 2), 10.23)

    def test_revenue_at_risk_and_sensitivities_do_not_depend_on_check_b(self):
        for rate in (0.04, 0.035, 0.033, 0.02):
            with self.subTest(rate=rate):
                m = fm.customer_metrics(features(fd_balance_myr=48000.0, fd_balance_weighted_offer_rate=rate), APRIL)
                c = m['components']
                self.assertAlmostEqual(m['rar_3m'], 3 * (c['fee_income'] - c['transaction_cost'] + c['fd_earnings'] + c['operating_earnings']))
                for variant in m['sensitivity']:
                    self.assertAlmostEqual(variant['rar_3m'], 3 * (c['fee_income'] - c['transaction_cost'] + variant['fd_earnings'] + c['operating_earnings']))
                for variant in m['cost_sensitivity']:
                    self.assertAlmostEqual(variant['rar_3m'], 3 * (c['fee_income'] - variant['transaction_cost'] + c['fd_earnings'] + c['operating_earnings']))

    def test_tier_threshold_is_exposed_only_for_deposit_condition_tiers(self):
        self.assertEqual(fm.customer_metrics(WORKED, APRIL)['fd_threshold_myr'], 100000.0)
        self.assertIsNone(fm.customer_metrics(features(tier_id='GOV'), APRIL)['fd_threshold_myr'])
        self.assertIsNone(fm.customer_metrics(features(tier_id='NEW_TIER'), APRIL)['fd_threshold_myr'])

    def test_unknown_tier_or_unverified_cutoff_makes_measures_unavailable(self):
        unknown = fm.customer_metrics(features(tier_id='NEW_TIER'), APRIL)
        self.assertIn('unknown tier', unknown['unavailable'])
        self.assertIsNone(unknown['rar_3m'])
        self.assertEqual(unknown['fsl_a']['status'], 'unavailable')
        later = fm.customer_metrics(WORKED, '2025-01-31')
        self.assertIn('OPR not verified for this cutoff (verified rates end 10 Jul 2024)', later['unavailable'])
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
        self.assertNotRegex(report['note'], r'(?i)loss')
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
        self.assertEqual(summary['finance_metrics']['bases_tiers'],
                         {'FD_THRESHOLD': ['SME_S', 'SME_M', 'CORP_L'], 'POLICY_EXEMPT': ['CORP_XL', 'GOV']})
        balances, finance = summary['flagged_balances'], summary['finance']
        self.assertEqual((balances['fixed_deposits'], balances['operating']),
                         (finance['flagged_fd_balance_myr']['total'], finance['flagged_non_fd_balance_myr']['total']))
        self.assertAlmostEqual(balances['total'], sum(v for v in (balances['fixed_deposits'], balances['operating']) if v is not None))
        self.assertEqual((balances['records'], summary['flagged_share']), (summary['flagged'], summary['flagged'] / summary['population']))
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
                                "(estimated relationship contribution; waiver condition not met; "
                                "fixed deposits don't cover waived transaction cost).")
        for item in (i for s in card['sections'] for i in s['items']):
            self.assertNotRegex(item['text'], r'(?i)loss')
        self.assertNotIn('Contribution at stake', payload)  # Deterministic only: never sent to Gemini.
        self.assertLessEqual(render.card_words(card), 240)
        self.assertEqual(data['finance_metrics']['rar_3m'], expected['rar_3m'])

    def test_card_wording_for_negative_contribution_and_policy_exemption(self):
        from churn_backend.briefings import forecast, money
        with self.app.app_context():
            data = evidence.build('summary', self.id)
        sentence = 'Estimated relationship contribution is negative at the assumed cost; see cost sensitivity.'
        b_label = "fixed deposits don't cover waived transaction cost"
        def stake(contribution, a, b, policy=False):
            metrics = dict(contribution_monthly=contribution, rar_3m=3 * contribution, fsl_a=dict(flagged=a),
                           fsl_b=dict(flagged=b, policy=policy))
            [text] = render.stake_line(dict(data, finance_metrics=metrics))
            self.assertFalse(text['external'])
            self.assertNotRegex(text['text'], r'(?i)loss')
            return text['text']
        # Negative contribution with check B false (e.g. negative FD earnings): figure only, no B label.
        self.assertEqual(stake(-12.5, False, False), sentence + f' ({money(-12.5)} a month).')
        # Negative with check B true: the B label sits beside the figure.
        self.assertEqual(stake(-12.5, False, True), sentence + f' ({money(-12.5)} a month; {b_label}).')
        # Policy-exempt B results are not flagged on the card.
        self.assertEqual(stake(-12.5, False, True, policy=True), sentence + f' ({money(-12.5)} a month).')
        prefix = f"Contribution at stake over {forecast(data['identity']['cutoff'])}: {money(30.0)} (estimated relationship contribution"
        # Positive: only the checks that are true.
        self.assertEqual(stake(10.0, True, False), prefix + '; waiver condition not met).')
        self.assertEqual(stake(10.0, False, True), prefix + f'; {b_label}).')
        self.assertEqual(stake(10.0, False, False), prefix + ').')
        self.assertEqual(render.stake_line(dict(data, finance_metrics=dict(contribution_monthly=None))), [])


if __name__ == '__main__':
    unittest.main()
