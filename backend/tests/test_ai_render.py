"""Offline tests for the server-rendered summary card (m6-narrative-5). No provider, network or owner DB."""
import copy
import json
import re
import sys
import tempfile
import unittest
from pathlib import Path
from churn_backend import create_app, ai_drafts as ai, ai_evidence as evidence, ai_render as render, repository
from churn_backend.db import get_db
from churn_backend.importer import import_demo
from churn_backend.validation import ValidationError
from tests.hermetic import unconfigured

# Full synthetic feature values for the demo customer (driver values are left unchanged).
EXTRA = dict(combined_flow_mean_12m_myr=1250000.0, combined_flow_mean_3m_myr=10881.0, outbound_flow_ratio_3m_to_12m=0.02,
             fd_balance_myr=0.0, fd_maturing_30d_count=0, estimated_fee_mean_3m_myr=420.5, estimated_waiver_mean_3m_myr=120.0,
             outbound_count_mean_3m=1.3, outbound_count_mean_12m=14.2, outbound_success_recency_days=41,
             login_success_count_mean_3m=12.0, login_success_recency_days=3)


def text_of(card):
    return ' '.join([item['text'] for s in card['sections'] for item in s['items']] + [q['text'] for q in card['questions']])


def section(card, key):
    return next(s for s in card['sections'] if s['id'] == key)


class RenderTests(unittest.TestCase):
    def setUp(self):
        unconfigured(self)  # Never inherit saved TXB_*/Gemini settings.
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.app = create_app(dict(TESTING=True, DATABASE=str(Path(self.temp.name) / 'test.sqlite')))
        with self.app.app_context():
            import_demo()
            db = get_db()
            row = db.execute('SELECT prediction_id,features_json FROM predictions').fetchone()
            features = json.loads(row['features_json'])
            features.update(EXTRA)
            db.execute('UPDATE predictions SET features_json=?', (json.dumps(features),))
            db.commit()
            self.id = row['prediction_id']
            self.evidence = evidence.build('summary', self.id)

    def with_drivers(self, higher, lower=()):
        """Same facts, different saved driver ranking (renderer input only; no rescoring)."""
        data = copy.deepcopy(self.evidence)
        def driver(feature, weight):
            return dict(feature=feature, contribution_logodds=weight, value=None, group='Synthetic', label=feature)
        data['explanation']['higher_risk_drivers'] = [driver(f, w) for f, w in higher]
        data['explanation']['lower_risk_drivers'] = [driver(f, w) for f, w in lower]
        return data

    def test_sections_order_titles_and_closing(self):
        card = ai.fallback(self.evidence)
        self.assertEqual(card['format'], 'sections-1')
        self.assertEqual([s['id'] for s in card['sections']], ['bottom_line', 'operations', 'finance', 'weighed', 'footnote', 'closing'])
        self.assertEqual([s['title'] for s in card['sections']], ['Bottom line', 'Operations: what is happening',
                         'Finance: what is at stake', 'What the model weighed', '', 'Decision'])
        self.assertEqual([item['text'] for item in section(card, 'footnote')['items']], [render.footnote(self.evidence)])
        closing = [item['text'] for item in section(card, 'closing')['items']]
        self.assertEqual(closing, [render.CLOSING, render.SERVICE_CLOSING])  # Demo has positive friction drivers.

    def test_plain_sentences_match_saved_values(self):
        card = ai.fallback(self.evidence)
        bottom = [item['text'] for item in section(card, 'bottom_line')['items']]
        self.assertEqual(bottom[0], 'Estimated chance that average monthly combined flow (Collection + Disbursement) over Mar–May 2024 '
                                    'falls to half or less of its usual level: 84.4%, more likely than not.')
        self.assertEqual(bottom[1], 'Flagged for committee review: at or above the 25.9% threshold, which was set from past data '
                                    'to balance catching real cases against false alerts.')
        self.assertEqual(bottom[3], 'Usual monthly combined flow (12-month average): RM\u00a01.3 million.')  # Rounded half-up.
        # The exact amount is unchanged in the supporting evidence (and on the Finance tab).
        self.assertEqual(self.evidence['facts']['feature.combined_flow_mean_12m_myr']['display'], 'RM\u00a01,250,000.00 per month')
        finance = [item['text'] for item in section(card, 'finance')['items']]
        # Exact ratio 0.87% stays in supporting evidence; the card states the gap: 1 - 0.0087046122 = 99.13%.
        self.assertEqual(finance[0], 'Combined flow in Dec 2023–Feb 2024 averaged 99.13% below its 12-month average.')
        self.assertEqual(self.evidence['facts']['feature.combined_flow_ratio_3m_to_12m']['display'],
                         '0.87% of the trailing twelve-month average')
        self.assertIn('Operating account balances on 29 Feb 2024: RM 2,016,997.13.', finance)
        self.assertIn('Fixed deposits on 29 Feb 2024: RM\u00a00.00; none due to mature within 30 days.', finance)
        operations = [item['text'] for item in section(card, 'operations')['items']]
        self.assertEqual(operations[0], '40% of payments failed (Dec 2023–Feb 2024).')  # Largest friction driver first; whole % without .0.
        unflagged = copy.deepcopy(self.evidence)
        unflagged['facts']['prediction.flag']['value'] = False
        self.assertIn('Not flagged: below the 25.9% threshold, which was set from past data to balance catching real cases '
                      'against false alerts.',
                      [item['text'] for item in section(ai.fallback(unflagged), 'bottom_line')['items']])

    def test_fallback_reads_on_its_own_without_jargon_or_placeholders(self):
        card = ai.fallback(self.evidence)
        text = text_of(card)
        self.assertNotIn('{{', text)
        self.assertIsNone(re.search(r'\d{4}-\d{2}-\d{2}', text))
        for jargon in ['saved model estimate', 'volume-drop', 'logodds', 'SHAP', 'worth', 'profitable']:
            self.assertNotIn(jargon, text)
        self.assertTrue(all(s['items'] for s in card['sections']))
        self.assertEqual([(q['audience'], q['source']) for q in card['questions']], [('operations', 'template'), ('finance', 'template')])
        self.assertFalse(any(item['source'] == 'ai' for s in card['sections'] for item in s['items']))

    def test_placeholders_resolve_to_names_only_and_ai_items_are_tagged(self):
        link = dict(text='{{feature.login_failure_rate_3m}} and {{feature.non_fd_balance_myr}} both matter for this customer.',
                    evidence_ids=['feature.login_failure_rate_3m', 'feature.non_fd_balance_myr'])
        questions = [dict(audience='finance', text='Could Finance check {{feature.non_fd_balance_myr}}?',
                          evidence_ids=['feature.non_fd_balance_myr'])]
        card = render.render_summary(self.evidence, link, questions)
        note = section(card, 'link')['items'][0]
        self.assertEqual((note['source'], note['text']), ('ai', 'Login failure rate and operating account balance both matter for this customer.'))
        self.assertNotIn('50%', note['text'])
        finance = next(q for q in card['questions'] if q['audience'] == 'finance')
        self.assertEqual(finance['text'], 'Could Finance check operating account balance?')
        # An AI finance question is kept; the missing Operations audience gets a template; Operations is listed first.
        self.assertEqual([(q['audience'], q['source']) for q in card['questions']], [('operations', 'template'), ('finance', 'ai')])
        self.assertIn('link_rules', card['checks'])

    def test_friction_led_and_flow_led_customers_get_different_emphasis(self):
        friction = ai.fallback(self.with_drivers([('login_failure_rate_3m', 2.0), ('combined_flow_ratio_3m_to_12m', 0.5)]))
        flow = ai.fallback(self.with_drivers([('combined_flow_ratio_3m_to_12m', 2.0), ('inbound_flow_ratio_3m_to_12m', 0.5)]))
        self.assertEqual(section(friction, 'operations')['items'][0]['text'], '50% of login attempts failed (Dec 2023–Feb 2024).')
        self.assertEqual(section(flow, 'operations')['items'][0]['text'], render.NOT_NOTABLE)
        self.assertIn('Last successful payment: 41 days before 29 Feb 2024.',
                      [item['text'] for item in section(flow, 'operations')['items']])
        self.assertEqual(section(friction, 'weighed')['items'][0]['text'], 'Login failure rate: weighed toward higher risk.')
        self.assertEqual(section(flow, 'weighed')['items'][0]['text'], 'Combined flow vs 12-month average: weighed toward higher risk.')
        self.assertIn('Strongest signals raising the estimate: login failure rate and combined flow vs 12-month average '
                      '(details in Signals to investigate).', text_of(friction))
        self.assertIn('Strongest signals raising the estimate: combined flow vs 12-month average and collections vs 12-month average '
                      '(details in Signals to investigate).', text_of(flow))
        self.assertIn(render.SERVICE_CLOSING, text_of(friction))
        self.assertNotIn(render.SERVICE_CLOSING, text_of(flow))
        self.assertTrue(friction['questions'][0]['text'].startswith('Could Operations check whether the recorded login failure rate points'))

    def test_frequency_pair_states_direction_from_exact_values(self):
        card = ai.fallback(self.with_drivers([('outbound_count_mean_3m', 1.0)]))
        self.assertEqual(section(card, 'operations')['items'][0]['text'],
                         'Successful payments: 1.3 a month in Dec 2023–Feb 2024, below the 12-month average (14.2).')

    def test_finance_is_trend_first_and_neutral(self):
        finance = [item['text'] for item in section(ai.fallback(self.evidence), 'finance')['items']]
        self.assertTrue(finance[0].startswith('Combined flow in'))
        fees = next(text for text in finance if text.startswith('Estimated fees'))
        self.assertEqual(fees, 'Estimated fees RM\u00a0420.50 a month and waivers RM\u00a0120.00 a month (Dec 2023–Feb 2024); '
                               'historical estimates, not profit.')
        self.assertLessEqual(len(finance), 6)

    def test_server_card_length_is_bounded_for_demo_and_every_fixture(self):
        sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'scripts'))
        import evaluate_m6
        # Deterministic server output only; AI text has its own limits. render-9 (27 Nov 2026): 240 -> 300. The plainer
        # bottom line and dated footnote add ~60 words; demo max 228 -> 288, keeping the same 12-word headroom.
        limit = 300
        self.assertLessEqual(render.card_words(ai.fallback(self.evidence)), limit)
        app = create_app(dict(TESTING=True, DATABASE=str(Path(self.temp.name) / 'fixtures.sqlite')))
        checked = 0
        for example, prediction_id, _, _ in evaluate_m6.build_examples(app):
            if example.get('case'):
                continue  # Discussion keeps its block contract until stage 2.
            with app.app_context():
                data = evidence.build('summary', prediction_id)
                with self.subTest(example=example['id']):
                    self.assertLessEqual(render.card_words(ai.fallback(data)), limit)
                    self.assertEqual(ai.validate(evaluate_m6.SUMMARY_NOTES, data)['format'], 'sections-1')  # Renders; no card limit.
                checked += 1
        self.assertEqual(checked, 6)

    def test_longest_theoretical_card_stays_under_its_ceiling_guard(self):
        """Regression guard, not the design target. 240 words is a design target for real cards (the
        representative test above; April data max 240). This synthetic card combines the longest variant of
        every conditional piece: demo cutoff 29 Feb 2024 (every 3-month period spans a year), flagged, every
        Operations/Finance fact present and notable, negative contribution with checks A and B both true,
        the three longest driver labels ranked first and a friction driver (service closing and friction
        question). It is 325 words today (264 under render-8, before the render-9 bottom line and footnote; 263 before render-8
        'fixed deposits'; 262 under the stage-1 sentence). The count covers the deterministic
        card and template questions only; AI link text and AI questions are excluded."""
        longest_labels = ['outbound_processing_count_mean_3m', 'outbound_processing_rate_3m', 'session_started_count_mean_3m']
        drivers = [(f, 100.0 - i) for i, f in enumerate(longest_labels)]
        # Small weights make every Operations/Finance line notable, longest first.
        lines = {'login_success_count_mean_12m': 15, 'login_success_count_mean_3m': 15, 'outbound_count_mean_12m': 15,
                 'outbound_count_mean_3m': 15, 'passive_session_rate_3m': 12, 'outbound_bank_failure_rate_3m': 11,
                 'outbound_success_recency_days': 10, 'login_success_recency_days': 10, 'login_failure_rate_3m': 9,
                 'outbound_failure_rate_3m': 8, 'estimated_fee_mean_3m_myr': 20, 'fd_balance_myr': 16,
                 'inbound_flow_ratio_3m_to_12m': 12, 'outbound_flow_ratio_3m_to_12m': 12, 'non_fd_balance_myr': 10}
        drivers += [(f, 0.001 * n) for f, n in lines.items()]
        data = self.with_drivers(drivers)
        data['facts']['prediction.flag']['value'] = True
        data['finance_metrics'] = dict(contribution_monthly=-9999999.99, rar_3m=-29999999.97, fsl_a=dict(flagged=True),
                                       fsl_b=dict(flagged=True, policy=False))
        card = ai.fallback(data)
        text = text_of(card)
        self.assertIn("Estimated relationship contribution is negative at the assumed cost; see cost sensitivity. ", text)
        self.assertIn("waiver condition not met; fixed deposits don't cover waived transaction cost).", text)
        self.assertIn(render.SERVICE_CLOSING, text)
        self.assertEqual(len(section(card, 'finance')['items']), 6)
        self.assertEqual(len(section(card, 'operations')['items']), 3)
        self.assertEqual(render.card_words(card), 325)  # Pinned so any growth is noticed (render-8: 264).
        self.assertLessEqual(render.card_words(card), 331)  # Ceiling guard, same +6 headroom (render-8: 270).

    def test_ai_text_within_its_own_limits_is_accepted_regardless_of_card_length(self):
        # m6-narrative-9: allowed references only (top-3 higher-risk drivers; non_fd_balance is a lower-risk driver).
        link_text = 'and the review can discuss {{feature.outbound_failure_rate_3m}} beside {{feature.combined_flow_ratio_3m_to_12m}} together.'
        link = dict(text=' '.join(['and'] * (25 - len(link_text.split()))) + ' ' + link_text,
                    evidence_ids=['feature.outbound_failure_rate_3m', 'feature.combined_flow_ratio_3m_to_12m'])
        def question(audience, fact, opener):
            text = opener + ' ' + ' '.join(['the'] * (24 - len(opener.split()))) + ' situation?'
            return dict(audience=audience, text=text, evidence_ids=[fact])
        questions = [question('operations', 'feature.outbound_failure_rate_3m', 'Has the customer described its'),
                     question('finance', 'feature.combined_flow_ratio_3m_to_12m', 'Has the customer described its')]
        self.assertEqual([len(link['text'].split())] + [len(q['text'].split()) for q in questions], [25, 25, 25])
        with self.app.app_context():
            card = ai.validate(json.dumps(dict(link=link, questions=questions)), self.evidence)
        self.assertEqual([s['id'] for s in card['sections']][:2], ['bottom_line', 'link'])
        self.assertEqual([q['source'] for q in card['questions']], ['ai', 'ai'])

    def test_footnote_appears_once_on_every_card(self):
        # Only Operations compares with a 12-month average: no Finance ratios and no bottom-line usual value.
        only_ops = self.with_drivers([('outbound_count_mean_3m', 1.0)])
        for fact in ['feature.combined_flow_ratio_3m_to_12m', 'feature.inbound_flow_ratio_3m_to_12m',
                     'feature.outbound_flow_ratio_3m_to_12m', 'feature.combined_flow_mean_12m_myr']:
            del only_ops['facts'][fact]
        card = ai.fallback(only_ops)
        # The risk sentence names the forecast target's 12-month baseline; it is not a recorded 3-month vs 12-month comparison.
        recorded = section(card, 'bottom_line')['items'][1:] + section(card, 'finance')['items']
        self.assertFalse(any('12-month' in item['text'] for item in recorded))
        self.assertIn('12-month average', section(card, 'operations')['items'][0]['text'])
        self.assertEqual([s['id'] for s in card['sections']][-2:], ['footnote', 'closing'])
        self.assertEqual(text_of(card).count(render.footnote(only_ops, with_usual=False)), 1)
        self.assertNotIn('Usual monthly combined flow', text_of(card))  # No line d, so no usual-flow footnote sentence.
        # No other 12-month sentence remains: the risk sentence's baseline (12 months ending at cutoff,
        # outcomes.py) still uses a 12-month average, so the footnote stays (owner decision).
        for fact in ['feature.outbound_count_mean_12m', 'feature.login_success_count_mean_12m']:
            del only_ops['facts'][fact]
        card = ai.fallback(only_ops)
        risk_sentence = section(card, 'bottom_line')['items'][0]['text']
        footnote = render.footnote(only_ops, with_usual=False)
        self.assertNotIn('12-month average', text_of(card).replace(risk_sentence, '').replace(footnote, ''))
        self.assertEqual([s['id'] for s in card['sections']][-2:], ['footnote', 'closing'])
        self.assertEqual(text_of(card).count(footnote), 1)

    def test_every_predictor_has_a_short_plain_driver_label(self):
        predictors = json.loads((Path(render.__file__).parent / 'feature_schema.json').read_text())['predictor_columns']
        self.assertEqual(set(render.DRIVER_LABELS), set(predictors))
        for feature, label in render.DRIVER_LABELS.items():
            with self.subTest(feature=feature):
                self.assertTrue(2 <= len(label.split()) <= 5, label)
                self.assertNotIn('_', label)
                self.assertIsNone(re.search(r'\b(?:myr|sec|ms|pct|cv)\b', label, re.I), label)
                self.assertIsNone(re.search(r'\b(?:inbound|outbound|incoming|outgoing)\b', label, re.I), label)

    def test_weighed_section_and_provider_payload_use_the_same_plain_labels(self):
        data = self.with_drivers([('session_duration_mean_3m_sec', 2.0), ('closed_fd_count', -1.0), ('inbound_share_3m', 0.5)])
        weighed_lines = [item['text'] for item in section(ai.fallback(data), 'weighed')['items']]
        self.assertEqual(weighed_lines[:3], ['Average online session length: weighed toward higher risk.',
                                             'Inactive fixed deposits: weighed toward lower risk.',
                                             'Collections share of combined flow: weighed toward higher risk.'])
        payload = render.provider_payload(self.evidence)
        names = {fact['id']: fact['name'] for s in payload['sections'] for l in s['lines'] for fact in l['facts']}
        self.assertEqual(names['feature.login_failure_rate_3m'], 'login failure rate')
        self.assertEqual(names['signal.combined_flow_ratio_3m_to_12m'], 'combined flow vs 12-month average')
        self.assertEqual(names['feature.non_fd_balance_myr'], 'operating account balance')

    def test_card_uses_collections_and_payments_terminology(self):
        text = text_of(ai.fallback(self.evidence))
        self.assertIsNone(re.search(r'\b(?:incoming|outgoing|inbound|outbound)\b', text, re.I))
        self.assertIn('Collections in Dec 2023–Feb 2024 averaged 84.98% below their 12-month average.', text)
        self.assertIn('Payments in Dec 2023–Feb 2024 averaged 98% below their 12-month average.', text)
        # The supporting-evidence panel on the same screen uses the same terms (m6-evidence-6).
        self.assertEqual(evidence.VERSION, 'm6-evidence-6')
        self.assertEqual(self.evidence['facts']['feature.combined_flow_ratio_3m_to_12m']['label'], 'Combined flow')
        self.assertEqual(self.evidence['facts']['feature.login_failure_rate_3m']['label'], 'Login failure rate')
        for fact in self.evidence['facts'].values():
            with self.subTest(fact=fact['id']):
                self.assertIsNone(re.search(r'\b(?:incoming|outgoing|inbound|outbound)\b', fact['label'] + ' ' + fact['meaning'], re.I))
        self.assertEqual(self.evidence['facts']['feature.inbound_flow_ratio_3m_to_12m']['label'], 'Collections')
        self.assertEqual(render.DRIVER_LABELS['fd_average_balance_myr'], 'Total average fixed deposit balance')

    # render-9 (27 Nov 2026, supervisor feedback on customer 689). Replaces the driver_family test: the bottom line now
    # names the top-3 higher-risk drivers with the Signals to investigate labels instead of one driver's family.
    def customer_689(self):
        """Customer-689-like renderer input (April 2024): a copy of the evidence only; nothing saved is changed."""
        data = self.with_drivers([('passive_session_rate_3m', 0.1), ('session_duration_mean_3m_sec', 0.9),
                                  ('login_failure_rate_3m', 0.4), ('outbound_failure_rate_3m', 0.6)],
                                 lower=[('outbound_flow_ratio_3m_to_12m', -0.5)])
        data['identity']['cutoff'] = '2024-04-30'
        facts = data['facts']
        facts['prediction.risk']['value'], facts['prediction.threshold']['value'] = 0.567, 0.259
        facts['prediction.flag']['value'] = True
        facts['feature.combined_flow_mean_12m_myr']['value'] = 115794564.30
        return data

    def test_customer_689_bottom_line_and_footnote_read_exactly(self):
        card = ai.fallback(self.customer_689())
        self.assertEqual([item['text'] for item in section(card, 'bottom_line')['items']], [
            'Estimated chance that average monthly combined flow (Collection + Disbursement) over May–Jul 2024 falls to half or '
            'less of its usual level: 56.7%, more likely than not.',
            'Flagged for committee review: at or above the 25.9% threshold, which was set from past data to balance catching '
            'real cases against false alerts.',
            'Strongest signals raising the estimate: average online session length, payment failure rate and login failure rate '
            '(details in Signals to investigate).',
            'Usual monthly combined flow (12-month average): RM 115.8 million.'])
        self.assertEqual([item['text'] for item in section(card, 'footnote')['items']], [
            'Prediction for May–Jul 2024, based on data up to 30 Apr 2024. "Usual monthly combined flow" is the monthly '
            'average from May 2023 to Apr 2024.'])
        # Evidence IDs stay on each item for the audit trail.
        self.assertEqual([item['evidence_ids'] for item in section(card, 'bottom_line')['items']],
                         [['prediction.risk'], ['prediction.flag', 'prediction.threshold'], [], ['feature.combined_flow_mean_12m_myr']])
        self.assertNotIn('payments vs 12-month average', section(card, 'bottom_line')['items'][2]['text'].lower())  # A lower driver.

    def test_likelihood_phrase_follows_the_displayed_percentage_and_the_saved_flag(self):
        def risk_line(risk, flagged):
            data = copy.deepcopy(self.evidence)
            data['facts']['prediction.risk']['value'], data['facts']['prediction.flag']['value'] = risk, flagged
            return section(ai.fallback(data), 'bottom_line')['items'][0]['text']
        middle = 'below even odds, but high enough to review'
        for risk, flagged, ending in [(0.567, True, ': 56.7%, more likely than not.'),
                                      (0.5, True, ': 50%, more likely than not.'),           # Boundary: exactly 50%.
                                      (0.4996, True, ': 50%, more likely than not.'),        # Displays as 50%.
                                      (0.4994, True, f': 49.9%, {middle}.'),
                                      (0.259, True, f': 25.9%, {middle}.'),                  # Boundary: exactly the threshold.
                                      (0.2589, False, ': 25.9%.'),                           # Below threshold: no phrase.
                                      (0.12, False, ': 12%.'),
                                      (0.2, True, f': 20%, {middle}.'),                      # Saved flag is used, not recomputed.
                                      (0.3, False, ': 30%.')]:
            with self.subTest(risk=risk, flagged=flagged):
                self.assertTrue(risk_line(risk, flagged).endswith(ending), risk_line(risk, flagged))

    def test_usual_flow_is_rounded_for_reading(self):
        for value, expected in [(115794564.30, 'RM 115.8 million'), (1250000.0, 'RM 1.3 million'),
                                (1000000.0, 'RM 1.0 million'), (168831.4, 'RM 168,831'), (999999.49, 'RM 999,999'),
                                (999999.5, 'RM 1.0 million'), (999949999.99, 'RM 999.9 million'),
                                (999950000.0, 'RM 1.0 billion'), (2345678901.0, 'RM 2.3 billion'), (0.0, 'RM 0')]:
            with self.subTest(value=value):
                self.assertEqual(render.short_money(value), expected)

    def test_top_signals_line_lists_up_to_three_higher_risk_drivers_with_the_signals_labels(self):
        available = [('outbound_failure_rate_3m', 0.2), ('session_duration_mean_3m_sec', 0.9), ('login_failure_rate_3m', 0.5),
                     ('passive_session_rate_3m', 0.7)]
        expected = {0: render.NO_SIGNAL,
                    1: 'payment failure rate',
                    2: 'average online session length and payment failure rate',
                    3: 'average online session length, login failure rate and payment failure rate',
                    4: 'average online session length, sessions without transactions and login failure rate'}
        for count, names in expected.items():
            with self.subTest(count=count):
                data = self.with_drivers(available[:count], lower=[('fd_balance_myr', -5.0)])  # Strongest overall, but lower.
                line = section(ai.fallback(data), 'bottom_line')['items'][2]
                self.assertEqual(line['text'], names if count == 0 else
                                 f'Strongest signals raising the estimate: {names} (details in Signals to investigate).')
                self.assertNotIn('fixed deposit', line['text'].lower())
                # Parity with Signals to investigate: same labels (repository.driver_labels), same strongest-first order.
                labels = repository.driver_labels(data['explanation'])
                shown = sorted(data['explanation']['higher_risk_drivers'], key=lambda d: -abs(d['contribution_logodds']))[:3]
                if shown:
                    self.assertIn(render.joined([render.in_sentence(labels[d['feature']]) for d in shown]), line['text'])
        self.assertFalse(hasattr(render, 'driver_family'))

    def test_labels_keep_a_leading_acronym_in_the_sentence(self):
        self.assertEqual(render.in_sentence('FD balance'), 'FD balance')
        self.assertEqual(render.in_sentence('Payment failure rate'), 'payment failure rate')
        self.assertEqual(render.joined(['FD balance', 'Login failure rate'][:2]), 'FD balance and Login failure rate')
        self.assertEqual(render.in_sentence('A'), 'a')

    def test_footnote_months_follow_the_saved_cutoff(self):
        for cutoff, expected in [
                ('2024-04-30', 'Prediction for May–Jul 2024, based on data up to 30 Apr 2024. "Usual monthly combined flow" is '
                               'the monthly average from May 2023 to Apr 2024.'),
                ('2024-11-30', 'Prediction for Dec 2024–Feb 2025, based on data up to 30 Nov 2024. "Usual monthly combined flow" '
                               'is the monthly average from Dec 2023 to Nov 2024.'),
                ('2024-12-31', 'Prediction for Jan–Mar 2025, based on data up to 31 Dec 2024. "Usual monthly combined flow" is '
                               'the monthly average from Jan 2024 to Dec 2024.')]:
            with self.subTest(cutoff=cutoff):
                data = copy.deepcopy(self.evidence)
                data['identity']['cutoff'] = cutoff
                self.assertEqual(section(ai.fallback(data), 'footnote')['items'][0]['text'], expected)

    def test_meeting_questions_carry_a_deterministic_based_on_line(self):
        card = ai.fallback(self.evidence)
        self.assertEqual([(q['audience'], q['source'], q['basis']) for q in card['questions']],
                         [('operations', 'template', 'Payment failure rate'), ('finance', 'template', 'Combined flow vs 12-month average')])
        asked = render.render_summary(self.evidence, None, [dict(audience='operations', text='Has the customer raised payment problems?',
                                                                 evidence_ids=['feature.outbound_failure_rate_3m', 'prediction.risk'])])
        self.assertEqual(asked['questions'][0]['basis'], 'Payment failure rate; The estimated risk')

    def test_allowed_references_are_the_shown_signals_usual_flow_and_prediction_never_a_lower_risk_driver(self):
        self.assertEqual(render.allowed_references(self.evidence), [
            'feature.combined_flow_mean_12m_myr', 'feature.combined_flow_ratio_3m_to_12m', 'feature.inbound_flow_ratio_3m_to_12m',
            'feature.outbound_failure_rate_3m', 'prediction.flag', 'prediction.risk', 'prediction.threshold',
            'signal.combined_flow_ratio_3m_to_12m', 'signal.inbound_flow_ratio_3m_to_12m', 'signal.outbound_failure_rate_3m'])
        # A lower-risk driver is never citable, even when it is the usual-flow fact or the activity tile.
        data = self.with_drivers([('login_failure_rate_3m', 1.0)],
                                 lower=[('combined_flow_ratio_3m_to_12m', -1.0), ('combined_flow_mean_12m_myr', -0.5)])
        self.assertEqual(render.allowed_references(data), ['feature.login_failure_rate_3m', 'prediction.flag', 'prediction.risk',
                                                           'prediction.threshold', 'signal.login_failure_rate_3m'])
        payload = render.provider_payload(self.evidence)
        self.assertEqual((payload['customer'], payload['allowed_references']), ('Customer A', render.allowed_references(self.evidence)))

    def test_ai_items_citing_a_lower_risk_driver_or_outside_the_allowed_set_are_dropped(self):
        data = self.customer_689()
        lower = 'feature.outbound_flow_ratio_3m_to_12m'  # The saved 689 link note cited this lower-risk driver.
        ops = dict(audience='operations', text='Has the customer reported trouble completing payments online?',
                   evidence_ids=['feature.outbound_failure_rate_3m'])
        link = dict(text='Failed logins and payment failures both concern online banking, alongside the change in {{' + lower + '}}.',
                    evidence_ids=['feature.login_failure_rate_3m', lower])
        raw = json.dumps(dict(link=link, questions=[ops]))
        with self.app.app_context():
            failure = next(f for f in ai.audit_output(raw, data)['failures'] if f['rule'] == 'citation_scope')
            self.assertEqual((failure['path'], failure['disallowed'], failure['lower_risk']), ('link.evidence_ids', [lower], [lower]))
            card = ai.validate(raw, data)
        self.assertNotIn('link', [s['id'] for s in card['sections']])
        self.assertNotIn('alongside the change', text_of(card))
        self.assertEqual(card['dropped'], [dict(item='link', rules=['citation_scope'])])
        self.assertEqual([(q['audience'], q['source']) for q in card['questions']], [('operations', 'ai'), ('finance', 'template')])
        # Outside the allowed set (operating balance is not a shown signal): the question is dropped, the template fills.
        outside = dict(audience='finance', text='Has the customer told the relationship team about changes to its business needs?',
                       evidence_ids=['feature.non_fd_balance_myr'])
        with self.app.app_context():
            card = ai.validate(json.dumps(dict(link=dict(text='', evidence_ids=[]), questions=[ops, outside])), data)
        self.assertEqual(card['dropped'], [dict(item='question:1/finance', rules=['citation_scope'])])
        self.assertEqual([(q['audience'], q['source']) for q in card['questions']], [('operations', 'ai'), ('finance', 'template')])
        # Allowed references are accepted.
        allowed = dict(text='{{feature.outbound_failure_rate_3m}} sits alongside the change in {{feature.combined_flow_ratio_3m_to_12m}} '
                            'for this customer.', evidence_ids=['feature.outbound_failure_rate_3m', 'feature.combined_flow_ratio_3m_to_12m'])
        with self.app.app_context():
            card = ai.validate(json.dumps(dict(link=allowed, questions=[ops])), data)
        self.assertNotIn('dropped', card)
        self.assertEqual(section(card, 'link')['items'][0]['source'], 'ai')

if __name__ == '__main__':
    unittest.main()
