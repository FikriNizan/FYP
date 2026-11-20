"""Constructed, isolated acceptance fixtures; never open the working portfolio."""
import copy
import json
from pathlib import Path
import re
import tempfile
import unittest
from unittest.mock import patch

from churn_backend import create_app
from churn_backend import repository as repo
from churn_backend.constants import FINANCE_FIELDS
from churn_backend.db import get_db
from churn_backend.importer import import_demo
from churn_backend.briefings import discussion_questions, money


class BriefingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.app = create_app(dict(TESTING=True, DATABASE=str(Path(self.temp.name)/'test.sqlite')))
        self.client = self.app.test_client()
        with self.app.app_context():
            import_demo()
        self.original = self.client.get('/api/customers/944').json['customer']
        self.id = self.original['prediction_id']
        self.review(self.id)

    def review(self, case_id, decision='prioritise', version=0, reason='Original committee rationale'):
        extra = {'expected_case_version':self.client.get('/api/cases/'+case_id).json['case']['version']} if version else {}
        response = self.client.put('/api/predictions/'+case_id+'/review', json=dict(
            decision=decision, reason=reason, reviewer='Committee', owner='RM A', expected_version=version, **extra))
        self.assertEqual(response.status_code, 200)

    def preview(self, ids=None):
        return self.client.get('/api/briefings', query_string=[('case_id', i) for i in (ids or [self.id])])

    def pdf(self, preview, ids=None):
        return self.client.post('/api/briefings/pdf', json=dict(case_ids=ids or [self.id], snapshots=preview['snapshots']))

    def dump(self):
        with self.app.app_context():
            return '\n'.join(get_db().iterdump())

    def batch(self, month='2024-03-31', count=1, risk=.12, long=False):
        evidence = copy.deepcopy(self.original['explanation'])
        evidence.update(cutoff_month=month, calibrated_risk=risk, review_alert=0)
        entries = []
        for i in range(count):
            e = copy.deepcopy(evidence)
            e['cus_id'] = '944' if i == 0 else str(1000+i)
            features = {FINANCE_FIELDS['non_fd_balance_myr']:2016997.13,
                        FINANCE_FIELDS['fd_balance_myr']:0,
                        FINANCE_FIELDS['estimated_monthly_fee_myr']:None,
                        FINANCE_FIELDS['estimated_monthly_waiver_myr']:0,
                        'combined_flow_mean_3m_myr':50, 'combined_flow_mean_12m_myr':100}
            entries.append(dict(evidence=e, features=features, customer=dict(customer_name=
                'Constructed long company ' + ('Alpha & Beta <Trading> ' * 35 if long else str(i)))))
        with self.app.app_context():
            # Deliberately bypass importer for software fixtures, never claimed as a valid research export.
            return repo.save_batch(month, 'saved_shap_export', evidence['protocol_sha256'], entries,
                                   dict(constructed_fixture=True))['batch_id']

    def test_preview_pdf_are_repeatable_read_only_and_include_sample_provenance(self):
        before = self.dump()
        preview = self.preview().json
        self.assertEqual(preview, self.preview([self.id, self.id]).json)
        item = preview['items'][0]
        self.assertIn('Single-case sample', item['sample_note'])
        self.assertIn('No newer assessment month is available.', item['latest']['paragraphs'])
        self.assertIn('No follow-up has been recorded', ' '.join(item['decision']['paragraphs']))
        self.assertIn('positive trailing twelve-month average', item['activity']['paragraphs'][0])
        pdf = self.pdf(preview)
        self.assertEqual(pdf.status_code, 200)
        self.assertEqual(pdf.mimetype, 'application/pdf')
        self.assertTrue(pdf.data.startswith(b'%PDF-'))
        self.assertIn('attachment;', pdf.headers['Content-Disposition'])
        self.assertEqual(pdf.data, self.pdf(preview).data)
        self.assertEqual(self.dump(), before)

    def test_february_origin_march_lower_risk_keeps_original_current_and_latest_distinct(self):
        # Current judgement changes; immutable opening rationale remains separately available.
        self.review(self.id, version=1, reason='Current rationale')
        follow = self.client.post('/api/cases/'+self.id+'/follow-ups', json=dict(expected_version=2,
            action_type='customer_contact', action_status='planned', action_date='2026-11-10',
            recorded_by='RM A', notes='Proposed discussion; no contact yet'))
        self.assertEqual(follow.status_code, 201)
        march = self.batch()
        before = self.dump()
        item = self.preview().json['items'][0]
        self.assertIn(['Assessment month', 'February 2024'], item['original']['rows'])
        self.assertIn(['Predicted risk', '84.4%'], item['original']['rows'])
        self.assertIn('Rationale: Original committee rationale', item['original']['paragraphs'])
        self.assertIn('Rationale: Current rationale', item['decision']['paragraphs'])
        self.assertIn(['Assessment month', 'March 2024'], item['latest']['rows'])
        self.assertIn(['Predicted risk', '12.0%'], item['latest']['rows'])
        self.assertIn(['Forecast window', 'Apr–Jun 2024'], item['latest']['rows'])
        self.assertEqual(item['glance'][1]['value'], '12.0%')
        self.assertIn('was 84.4% at review (February 2024)', item['glance'][1]['note'])
        self.assertEqual(item['glance'][0]['value'], 'Prioritise for RM')
        self.assertIn(['Latest batch', march], item['traceability'])
        self.assertEqual(item['finance']['rows'][0][1], 'RM\u00a02,016,997.13')
        self.assertEqual([r[1] for r in item['finance']['rows'][1:]], ['RM\u00a00.00','Not provided','RM\u00a00.00'])
        self.assertIn('Planned', item['followups']['rows'][0][0])
        self.assertEqual(item['original']['rows'][-1][0], 'Case opened')
        self.assertIn('Review saved', [r[0] for r in item['decision']['rows']])
        self.assertEqual(self.pdf(self.preview().json).status_code, 200)
        self.assertEqual(self.dump(), before)

    def test_unchanged_rationale_is_not_repeated_and_planned_contact_is_beside_due_date(self):
        self.client.post('/api/cases/'+self.id+'/follow-ups', json=dict(expected_version=1,
            action_type='customer_contact', action_status='planned', action_date='2026-11-18',
            recorded_by='RM A', notes='Proposed discussion; no contact yet'))
        item = self.preview().json['items'][0]
        self.assertIn('Rationale unchanged since the original review.', item['decision']['paragraphs'])
        self.assertNotIn('Rationale: Original committee rationale', item['decision']['paragraphs'])
        self.assertEqual(item['glance'][3]['value'], 'Not set')
        self.assertIn('Planned contact 18 Nov 2026', item['glance'][3]['note'])
        self.assertIn(['Case due date', 'Not set'], item['decision']['rows'])
        self.assertEqual(len(item['glance']), 4)
        self.assertTrue(item['prepared_on'])

    def test_same_cutoff_distinct_batch_is_not_a_newer_month(self):
        self.batch(month='2024-02-29')
        item = self.preview().json['items'][0]
        self.assertIn('No newer assessment month is available.', item['latest']['paragraphs'])
        self.assertTrue(any('distinct saved batch' in p for p in item['latest']['paragraphs']))

    def test_order_deduplication_limit_and_multiple_pdf_cases(self):
        batch = self.batch(count=11)
        ids = [c['prediction_id'] for c in self.client.get('/api/customers', query_string=dict(batch_id=batch)).json['items']]
        ids = [self.id]+[id for id in ids if id != next(c['prediction_id'] for c in self.client.get('/api/customers', query_string=dict(batch_id=batch)).json['items'] if c['cus_id']=='944')]
        for id in ids[1:]:
            self.review(id)
        selection = [ids[2], ids[0], ids[1], ids[2]]
        preview = self.preview(selection).json
        self.assertEqual([i['case_id'] for i in preview['items']], selection[:3])
        self.assertEqual(self.pdf(preview, selection).status_code, 200)
        self.assertEqual(self.preview(ids[:10]).status_code, 200)
        self.assertEqual(self.pdf(self.preview(ids[:10]).json, ids[:10]).status_code, 200)
        self.assertEqual(self.preview(ids).status_code, 422)
        self.assertEqual(self.client.get('/api/briefings').status_code, 422)
        self.assertEqual(self.preview(['bad/id']).status_code, 422)
        self.assertEqual(self.preview(['missing']).status_code, 404)

    def test_stale_review_case_or_latest_requires_fresh_preview_before_pdf(self):
        preview = self.preview().json
        self.review(self.id, version=1, reason='Updated while preview was open')
        response = self.pdf(preview)
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json['error']['code'], 'briefing_changed')
        self.assertEqual(self.pdf(response.json['briefing']).status_code, 200)
        preview = response.json['briefing']
        response = self.client.put('/api/cases/'+self.id, json=dict(expected_version=2,status='closed',
            owner='RM B',next_action_date=None,notes='Manual closure',recorded_by='Committee'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.pdf(preview).status_code, 409)
        preview = self.preview().json  # Closed case remains eligible while decision is prioritise.
        self.assertEqual(self.pdf(preview).status_code, 200)
        self.batch()
        self.assertEqual(self.pdf(preview).status_code, 409)
        self.review(self.id, decision='monitor', version=2)
        self.assertEqual(self.pdf(preview).status_code, 422)
        self.assertEqual(self.preview().status_code, 422)

    def test_invalid_export_payload_and_render_failure_are_not_partial_pdfs(self):
        self.assertEqual(self.client.post('/api/briefings/pdf', json=dict(case_ids=[self.id], snapshots=[], html='evil')).status_code, 422)
        preview = self.preview().json
        self.assertEqual(self.pdf(preview, [self.id, 'missing']).status_code, 404)
        with patch('churn_backend.briefing_pdf.render', side_effect=RuntimeError('Constructed export failure')):
            response = self.pdf(preview)
        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.mimetype, 'application/json')
        self.assertEqual(self.pdf(preview).status_code, 200)

    def test_question_evidence_is_not_padded_or_duplicated(self):
        # No triggering driver: one general check-in question (previously an empty list).
        from churn_backend.briefings import FALLBACK_QUESTION
        self.assertEqual([q['text'] for q in discussion_questions({})], [FALLBACK_QUESTION])
        drivers = [dict(feature='outbound_failure_rate_3m',value=.2), dict(feature='outbound_bank_failure_rate_3m',value=.1), dict(feature='login_failure_rate_3m',value=None)]
        # Two payment-failure drivers share one family; login is its own family (values are not inspected).
        self.assertEqual([q['family'] for q in discussion_questions(dict(explanation=dict(higher_risk_drivers=drivers)))],
                         ['payment_failures', 'login'])
        self.assertEqual([q['text'] for q in discussion_questions(dict(operations=dict(combined_flow_mean_3m_myr=0,combined_flow_mean_12m_myr=0)))],
                         [FALLBACK_QUESTION])

    def test_client_questions_follow_driver_strength_one_per_family_and_at_most_three(self):
        def driver(feature, weight, value=0.5):
            return dict(feature=feature, contribution_logodds=weight, value=value)
        drivers = [driver('login_failure_rate_3m', 0.2), driver('combined_flow_ratio_3m_to_12m', 0.9), driver('combined_flow_cv_12m', 0.8),
                   driver('outbound_failure_rate_3m', 0.5), driver('tier_id', 0.7), driver('estimated_fee_mean_3m_myr', 0.1)]
        questions = discussion_questions(dict(explanation=dict(higher_risk_drivers=drivers)))
        # Strongest first; the second transaction-value driver and the static attribute add nothing; capped at three.
        self.assertEqual([q['family'] for q in questions], ['transaction_value', 'payment_failures', 'login'])

    def test_client_families_cover_every_predictor_exactly_once(self):
        from churn_backend.briefings import CLIENT_FAMILY_FEATURES, NO_CLIENT_QUESTION
        from churn_backend.constants import PREDICTORS
        mapped = [f for features in CLIENT_FAMILY_FEATURES.values() for f in features] + list(NO_CLIENT_QUESTION)
        self.assertEqual(len(mapped), len(set(mapped)))
        self.assertEqual(set(mapped), set(PREDICTORS))
        self.assertEqual(len(PREDICTORS), 78)
        no_question = discussion_questions(dict(explanation=dict(higher_risk_drivers=[
            dict(feature=f, contribution_logodds=1, value=1) for f in NO_CLIENT_QUESTION])))
        self.assertEqual([q['family'] for q in no_question], ['general'])

    def test_fixed_deposit_question_uses_presence_not_threshold(self):
        from churn_backend.briefings import FD_PLANS_QUESTION, FD_SURPLUS_QUESTION
        trigger = dict(higher_risk_drivers=[dict(feature='fd_balance_change_3m_vs_previous_3m', contribution_logodds=1, value=-0.4)])
        for features, expected in [(dict(active_fd_count=2, fd_balance_myr=0), FD_PLANS_QUESTION),
                                   (dict(active_fd_count=0, fd_balance_myr=150000.0), FD_PLANS_QUESTION),
                                   (dict(active_fd_count=0, fd_balance_myr=0), FD_SURPLUS_QUESTION),
                                   ({}, FD_SURPLUS_QUESTION)]:
            with self.subTest(features=features):
                [question] = discussion_questions(dict(explanation=trigger, features=features))
                self.assertEqual(question['text'], expected)

    def test_every_client_question_is_client_safe(self):
        import re
        from churn_backend import briefings
        texts = list(briefings.CLIENT_QUESTIONS.values()) + [briefings.FD_PLANS_QUESTION, briefings.FD_SURPLUS_QUESTION,
                                                            briefings.FALLBACK_QUESTION]
        self.assertEqual(len(texts), 12)  # 9 single-text families + both FD branches + fallback.
        banned = re.compile(r'\b(?:model\w*|estimat\w*|risk\w*|scor\w*|flag\w*|threshold\w*|churn\w*|attrition|predict\w*|'
                            r'recorded|records?|data|other banks?|another bank|competitor\w*|switch\w*)\b', re.I)
        numbers = re.compile(r'\d|\b(?:one|two|three|four|five|six|seven|eight|nine|ten|twelve|first|second|third|half|percent|'
                             r'January|February|March|April|May|June|July|August|September|October|November|December|20\d\d)\b', re.I)
        for text in texts:
            with self.subTest(text=text):
                self.assertIsNone(banned.search(text))
                self.assertIsNone(numbers.search(text))
                self.assertTrue(text.endswith('?'))

    def test_question_source_is_for_the_rm_and_never_in_the_question(self):
        drivers = [dict(feature='login_failure_rate_3m', contribution_logodds=1, value=0.5)]
        [question] = discussion_questions(dict(explanation=dict(higher_risk_drivers=drivers)))
        self.assertEqual(question['source'], 'Login failure rate: 50.0%')
        self.assertNotIn('50', question['text'])
        self.assertNotIn('failure rate', question['text'].lower())

    def test_money_rounding_and_unsupported_font_error_preserve_exact_saved_data(self):
        self.assertEqual(money(78.705), 'RM\u00a078.71')
        self.assertEqual(money(-1234.567), '-RM\u00a01,234.57')
        self.assertEqual(money(0), 'RM\u00a00.00')
        self.assertEqual(money(None), 'Not provided')
        # PDF embeds both bundled static Open Sans faces; no fontTools runtime dependency.
        pdf = self.pdf(self.preview().json)
        self.assertEqual(pdf.status_code, 200)
        self.assertIn(b'OpenSansRoman-Regular', pdf.data)
        self.assertIn(b'OpenSansRoman-Bold', pdf.data)
        self.assertGreaterEqual(pdf.data.count(b'/FontFile2'), 2)
        from churn_backend.briefing_pdf import render, UnsupportedPdfText
        supported = self.preview().json
        supported['items'][0]['name'] = '\u2212 \u2013 \u00b7 \u2022 \u2265 \u2018pelanggan\u2019 \u201cMelayu English\u201d'
        self.assertTrue(render(supported).startswith(b'%PDF-'))
        supported['items'][0]['name'] = 'Unsupported \U0001f98a'
        with self.assertRaises(UnsupportedPdfText):
            render(supported)
        self.review(self.id, version=1, reason='Unsupported glyph \U0001f98a')
        before = self.dump()
        response = self.pdf(self.preview().json)
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json['error']['code'], 'pdf_font_unsupported')
        self.assertEqual(self.dump(), before)

    def test_long_name_and_multiline_notes_flow_over_real_a4_pages(self):
        self.batch(long=True)
        self.review(self.id, version=1, reason=('Line of saved evidence & plain <text>.\n' * 90))
        pdf = self.pdf(self.preview().json)
        self.assertEqual(pdf.status_code, 200)
        self.assertGreater(len(re.findall(rb'/Type\s*/Page\b', pdf.data)), 1)
        self.assertRegex(pdf.data, rb'/MediaBox\s*\[\s*0\s+0\s+595\.\d+\s+841\.\d+\s*\]')
