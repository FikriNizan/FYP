"""Offline tests for the server-rendered summary card (m6-narrative-5). No provider, network or owner DB."""
import copy
import json
import re
import sys
import tempfile
import unittest
from pathlib import Path
from churn_backend import create_app, ai_drafts as ai, ai_evidence as evidence, ai_render as render
from churn_backend.db import get_db
from churn_backend.importer import import_demo
from churn_backend.validation import ValidationError

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
        self.assertEqual([s['id'] for s in card['sections']], ['bottom_line', 'operations', 'finance', 'weighed', 'closing'])
        self.assertEqual([s['title'] for s in card['sections']], ['Bottom line', 'Operations: what is happening',
                         'Finance: what is at stake', 'What the model weighed', 'Decision'])
        closing = [item['text'] for item in section(card, 'closing')['items']]
        self.assertEqual(closing, [render.CLOSING, render.SERVICE_CLOSING])  # Demo has positive friction drivers.

    def test_plain_sentences_match_saved_values(self):
        card = ai.fallback(self.evidence)
        bottom = [item['text'] for item in section(card, 'bottom_line')['items']]
        self.assertEqual(bottom[0], 'Estimated chance that average monthly transaction value over Mar–May 2024 falls to half or less '
                                    'of its 12-month average: 84.4%.')
        self.assertEqual(bottom[1], 'Flagged for committee review: the estimate is at or above the 25.9% review threshold.')
        self.assertEqual(bottom[3], 'Usual monthly transaction value (12-month average): RM 1,250,000.00.')
        finance = [item['text'] for item in section(card, 'finance')['items']]
        self.assertEqual(finance[0], 'Average monthly transaction value in Dec 2023–Feb 2024 was 0.87% of its 12-month average '
                                     '(which includes these 3 months): 99.13% lower.')
        self.assertIn('Operating account balances on 29 Feb 2024: RM 2,016,997.13.', finance)
        self.assertIn('Fixed deposit balances on 29 Feb 2024: RM 0.00; no fixed deposits are due to mature within 30 days.', finance)
        operations = [item['text'] for item in section(card, 'operations')['items']]
        self.assertEqual(operations[0], '40.0% of outgoing payments failed (Dec 2023–Feb 2024).')  # Largest friction driver first.
        unflagged = copy.deepcopy(self.evidence)
        unflagged['facts']['prediction.flag']['value'] = False
        self.assertIn('Not flagged: the estimate is below the 25.9% review threshold.',
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
        notes = {key: dict(text='', evidence_ids=[]) for key in render.NOTE_SECTIONS}
        notes['operations'] = dict(text='The team may want to look at {{feature.login_failure_rate_3m}} together.',
                                   evidence_ids=['feature.login_failure_rate_3m'])
        questions = [dict(audience='finance', text='Could Finance check {{feature.non_fd_balance_myr}}?',
                          evidence_ids=['feature.non_fd_balance_myr'])]
        card = render.render_summary(self.evidence, notes, questions)
        note = section(card, 'operations')['items'][-1]
        self.assertEqual((note['source'], note['text']), ('ai', 'The team may want to look at login difficulties together.'))
        self.assertNotIn('50.0%', note['text'])
        self.assertEqual(card['questions'][0]['text'], 'Could Finance check operating account balances?')
        # An AI finance question is kept; only the missing Operations audience gets a template.
        self.assertEqual([(q['audience'], q['source']) for q in card['questions']], [('finance', 'ai'), ('operations', 'template')])
        self.assertIn('note_bounds', card['checks'])

    def test_friction_led_and_flow_led_customers_get_different_emphasis(self):
        friction = ai.fallback(self.with_drivers([('login_failure_rate_3m', 2.0), ('combined_flow_ratio_3m_to_12m', 0.5)]))
        flow = ai.fallback(self.with_drivers([('combined_flow_ratio_3m_to_12m', 2.0), ('inbound_flow_ratio_3m_to_12m', 0.5)]))
        self.assertEqual(section(friction, 'operations')['items'][0]['text'], '50.0% of login attempts failed (Dec 2023–Feb 2024).')
        self.assertEqual(section(flow, 'operations')['items'][0]['text'], render.NOT_NOTABLE)
        self.assertIn('Last successful outgoing payment: 41 days before 29 Feb 2024.',
                      [item['text'] for item in section(flow, 'operations')['items']])
        self.assertEqual(section(friction, 'weighed')['items'][0]['text'], 'Login difficulties: weighed toward higher risk.')
        self.assertEqual(section(flow, 'weighed')['items'][0]['text'], 'Transaction activity: weighed toward higher risk.')
        self.assertIn('service and online-banking measures', text_of(friction))
        self.assertIn('transaction value and balance measures', text_of(flow))
        self.assertIn(render.SERVICE_CLOSING, text_of(friction))
        self.assertNotIn(render.SERVICE_CLOSING, text_of(flow))
        self.assertTrue(friction['questions'][0]['text'].startswith('Could Operations check whether the recorded login difficulties'))

    def test_frequency_pair_states_direction_from_exact_values(self):
        card = ai.fallback(self.with_drivers([('outbound_count_mean_3m', 1.0)]))
        self.assertEqual(section(card, 'operations')['items'][0]['text'],
                         'Successful outgoing payments: 1.3 a month on average in Dec 2023–Feb 2024, '
                         'compared with 14.2 over the 12 months to 29 Feb 2024 (lower).')

    def test_finance_is_trend_first_and_neutral(self):
        finance = [item['text'] for item in section(ai.fallback(self.evidence), 'finance')['items']]
        self.assertTrue(finance[0].startswith('Average monthly transaction value'))
        fees = next(text for text in finance if text.startswith('Estimated fees'))
        self.assertTrue(fees.endswith('These are historical estimates, not profit.'))
        self.assertLessEqual(len(finance), 6)

    def test_card_word_limit_holds_for_demo_and_every_fixture(self):
        sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'scripts'))
        import evaluate_m6
        limit = 320
        self.assertLessEqual(render.card_words(ai.fallback(self.evidence)), limit)
        app = create_app(dict(TESTING=True, DATABASE=str(Path(self.temp.name) / 'fixtures.sqlite')))
        checked = 0
        for example, prediction_id, _, _ in evaluate_m6.build_examples(app):
            if example.get('case'):
                continue  # Discussion keeps its block contract until stage 2.
            with app.app_context():
                data = evidence.build('summary', prediction_id)
                for card in [ai.fallback(data), ai.validate(evaluate_m6.SUMMARY_NOTES, data)]:
                    with self.subTest(example=example['id']):
                        self.assertLessEqual(render.card_words(card), limit)
                checked += 1
        self.assertEqual(checked, 6)

    def test_rendered_card_over_the_word_limit_is_rejected(self):
        with self.app.app_context(), patch_limit(20):
            raw = json.dumps(dict(notes={key: dict(text='', evidence_ids=[]) for key in render.NOTE_SECTIONS}, questions=[]))
            with self.assertRaisesRegex(ValidationError, 'Rendered card exceeds bounded length'):
                ai.validate(raw, self.evidence)


class patch_limit:
    """Temporarily lower the rendered-card limit to prove it is enforced after rendering."""
    def __init__(self, words):
        self.words = words

    def __enter__(self):
        from churn_backend import ai_contract
        self.original = ai_contract.LIMITS['summary']['card_words']
        ai_contract.LIMITS['summary']['card_words'] = self.words

    def __exit__(self, *exc):
        from churn_backend import ai_contract
        ai_contract.LIMITS['summary']['card_words'] = self.original


if __name__ == '__main__':
    unittest.main()
