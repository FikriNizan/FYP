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
        response = self.client.put('/api/predictions/'+case_id+'/review', json=dict(
            decision=decision, reason=reason, reviewer='Committee', owner='RM A', expected_version=version))
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
        follow = self.client.post('/api/cases/'+self.id+'/follow-ups', json=dict(expected_version=1,
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
        for id in ids:
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
        response = self.client.put('/api/cases/'+self.id, json=dict(expected_version=1,status='closed',
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
        self.assertEqual(discussion_questions({}), [])
        drivers = [dict(feature='outbound_failure_rate_3m',value=.2), dict(feature='outbound_bank_failure_rate_3m',value=.1), dict(feature='login_failure_rate_3m',value=None)]
        self.assertEqual(len(discussion_questions(dict(explanation=dict(higher_risk_drivers=drivers)))), 1)
        self.assertEqual(discussion_questions(dict(operations=dict(combined_flow_mean_3m_myr=0,combined_flow_mean_12m_myr=0))), [])

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
