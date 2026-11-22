"""Offline retry-policy and batch-summary tests. Provider mocked; no credentials, network or owner DB."""
import io
import json
import os
import sys
import tempfile
import time
import unittest
from contextlib import redirect_stdout, redirect_stderr
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from churn_backend import create_app, ai_drafts as ai
from churn_backend.db import get_db
from churn_backend.importer import import_demo

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'scripts'))
import generate_summaries as batch  # noqa: E402
from tests.hermetic import unconfigured

PF = ai.ProviderFailure


def output(fact='feature.login_failure_rate_3m'):
    """Discussion purpose (m6-narrative-7): two client-safe questions."""
    return json.dumps(dict(questions=[
        dict(text='Have you or your team had any difficulty signing in to online banking?', evidence_ids=[fact]),
        dict(text='Have any of your payments been delayed or not gone through as expected?', evidence_ids=['feature.outbound_failure_rate_3m'])]))


def notes(fact='prediction.risk'):
    """Summary contract (m6-narrative-6): one link note citing two card sections, plus questions."""
    other = 'feature.login_failure_rate_3m'
    link = dict(text='For this customer, {{'+fact+'}} and {{'+other+'}} both belong in the review discussion.', evidence_ids=[fact, other])
    return json.dumps(dict(link=link, questions=[]))


def quota_error(quota_id):
    from google.genai.errors import ClientError
    return ClientError(429, {'error': {'code': 429, 'status': 'RESOURCE_EXHAUSTED', 'message': 'PRIVATE PROVIDER TEXT',
        'details': [{'@type': 'type.googleapis.com/google.rpc.QuotaFailure', 'violations': [{'quotaId': quota_id}]}]}})


class Base(unittest.TestCase):
    def setUp(self):
        unconfigured(self)  # Never inherit saved TXB_*/Gemini settings.
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = str(Path(self.temp.name) / 'test.sqlite')
        self.app = create_app(dict(TESTING=True, DATABASE=self.path, TXB_LOCAL_SESSION=True))
        self.client = self.app.test_client()
        with self.app.app_context():
            import_demo()
        self.id = self.client.get('/api/customers/944').json['customer']['prediction_id']
        with self.app.app_context():
            row = get_db().execute('SELECT batch_id,review_alert FROM predictions WHERE prediction_id=?', (self.id,)).fetchone()
        self.batch = row['batch_id']
        self.assertEqual(row['review_alert'], 1)
        self.sleeps = []
        for name, kwargs in [('sleep', dict(side_effect=self.sleeps.append)), ('jitter', dict(return_value=1.0))]:
            patcher = patch.object(ai, name, **kwargs)
            patcher.start()
            self.addCleanup(patcher.stop)

    def summary(self, retry):
        with self.app.app_context():
            evidence_hash = ai.load('summary', self.id)[0]['evidence_hash']
            return ai.generate('summary', self.id, {'expected_evidence_hash': evidence_hash}, retry=retry)

    def counts(self):
        with self.app.app_context():
            db = get_db()
            return [db.execute('SELECT count(*) FROM '+t).fetchone()[0] for t in ('ai_drafts', 'ai_reservations')]

    def run_batch(self, **options):
        args = SimpleNamespace(**{**dict(batch_id=self.batch, dry_run=False, limit=20, min_interval=0, keep_rejected=False), **options})
        lines = []
        with self.app.app_context():
            code = batch.run(args, lines.append)
        return code, '\n'.join(lines)


class RetryPolicyTests(Base):
    def test_batch_retries_503_with_exponential_jittered_backoff_then_saves(self):
        with patch.object(ai.Gemini, 'generate', side_effect=[PF('provider_unavailable'), PF('provider_unavailable'), notes()]) as mock:
            result = self.summary(ai.BATCH)
        self.assertEqual(mock.call_count, 3)
        self.assertEqual((result['state'], result['attempts']), ('saved', 3))
        self.assertEqual(self.sleeps, [2.0, 4.0])
        ai.jitter.assert_called_with(0.5, 1.0)
        self.assertEqual(self.counts(), [1, 0])

    def test_batch_retry_is_bounded_and_delay_capped(self):
        with patch.object(ai.Gemini, 'generate', side_effect=PF('provider_unavailable')) as mock:
            result = self.summary(dict(ai.BATCH, base=20))
        self.assertEqual(mock.call_count, 4)
        self.assertEqual((result['state'], result['failure_code'], result['attempts']), ('fallback', 'provider_unavailable', 4))
        self.assertEqual(self.sleeps, [20, 30, 30])
        self.assertEqual(self.counts(), [0, 0])

    def test_batch_retries_rate_limit_and_timeout(self):
        with patch.object(ai.Gemini, 'generate', side_effect=[PF('provider_rate_limited'), PF('provider_timeout'), notes()]) as mock:
            self.assertEqual(self.summary(ai.BATCH)['state'], 'saved')
        self.assertEqual(mock.call_count, 3)

    def test_validation_failure_and_unlisted_codes_are_never_retried(self):
        for side_effect, code in [('invalid', 'output_validation_failed'), (PF('provider_request_rejected'), 'provider_request_rejected')]:
            with self.subTest(code=code), patch.object(ai.Gemini, 'generate', side_effect=[side_effect]) as mock:
                result = self.summary(ai.BATCH)
                self.assertEqual((mock.call_count, result['failure_code'], result['attempts']), (1, code, 1))
        self.assertEqual(self.sleeps, [])

    def test_daily_quota_is_read_from_structured_metadata_and_stops_without_retry(self):
        self.assertEqual(ai.provider_failure_code(quota_error('GenerateRequestsPerDayPerProjectPerModel-FreeTier')), 'provider_quota_exhausted')
        self.assertEqual(ai.provider_failure_code(quota_error('GenerateRequestsPerMinutePerProjectPerModel-FreeTier')), 'provider_rate_limited')
        self.app.config.update(TXB_GENAI_ENABLED='1')
        with patch.dict(os.environ, {'GEMINI_API_KEY': 'synthetic-key'}), patch('google.genai.Client') as factory:
            request = factory.return_value.__enter__.return_value.models.generate_content
            request.side_effect = quota_error('GenerateRequestsPerDayPerProjectPerModel-FreeTier')
            result = self.summary(ai.BATCH)
            request.assert_called_once()
            self.assertEqual(factory.call_args.kwargs['http_options'].retry_options.attempts, 1)
        self.assertEqual(result['failure_code'], 'provider_quota_exhausted')
        self.assertNotIn('PRIVATE PROVIDER TEXT', json.dumps(result))

    def test_worst_case_reservation_covers_every_policy(self):
        self.assertEqual(ai.worst_case_seconds(ai.SINGLE, 30), 30)
        self.assertEqual(ai.worst_case_seconds(ai.ON_DEMAND, 30), 30)
        self.assertEqual(ai.worst_case_seconds(ai.BATCH, 30), 4*30+2+4+8)


class OnDemandDiscussionTests(Base):
    def setUp(self):
        unconfigured(self)  # Never inherit saved TXB_*/Gemini settings.
        super().setUp()
        review = dict(decision='prioritise', reason='Synthetic', reviewer='Synthetic', expected_version=0)
        self.assertEqual(self.client.put('/api/predictions/'+self.id+'/review', json=review).status_code, 200)
        self.url = '/api/cases/'+self.id+'/ai-discussion'

    def post(self):
        return self.client.post(self.url, json={'expected_evidence_hash': self.client.get(self.url).json['evidence_hash']}).json

    def test_one_retry_on_503_with_remaining_budget_as_second_timeout(self):
        with patch.object(ai.Gemini, 'generate', side_effect=[PF('provider_unavailable'), output()]) as mock:
            result = self.post()
        self.assertEqual((mock.call_count, result['state'], result['attempts']), (2, 'saved', 2))
        self.assertEqual(self.sleeps, [1.5])
        first, second = (call.args[1]['timeout'] for call in mock.call_args_list)
        self.assertLessEqual(second, first)
        self.assertLessEqual(first, 30)

    def test_no_retry_when_remaining_budget_is_under_ten_seconds(self):
        self.app.config['TXB_GENAI_TIMEOUT_SECONDS'] = '11'
        with patch.object(ai.Gemini, 'generate', side_effect=[PF('provider_unavailable'), output()]) as mock:
            result = self.post()
        self.assertEqual((mock.call_count, result['failure_code'], result['attempts']), (1, 'provider_unavailable', 1))

    def test_rate_limit_timeout_and_validation_are_not_retried_on_demand(self):
        for side_effect in [PF('provider_rate_limited'), PF('provider_timeout'), 'invalid']:
            with self.subTest(side_effect=str(side_effect)), patch.object(ai.Gemini, 'generate', side_effect=[side_effect, output()]) as mock:
                self.assertEqual(self.post()['state'], 'fallback')
                self.assertEqual(mock.call_count, 1)
        self.assertEqual(self.sleeps, [])


class BatchCommandTests(Base):
    def test_dry_run_makes_zero_calls_and_writes_nothing(self):
        with self.app.app_context():
            before = [tuple(r) for r in get_db().execute('SELECT * FROM predictions')]
        with patch.object(ai.Gemini, 'generate') as provider, patch('google.genai.Client') as factory:
            code, text = self.run_batch(dry_run=True)
            provider.assert_not_called()
            factory.assert_not_called()
        self.assertEqual(code, 0)
        self.assertIn('eligible (flagged): 1 | already cached: 0 | to generate: 1', text)
        self.assertIn('Dry run: zero API calls', text)
        self.assertEqual(self.counts(), [0, 0])
        with self.app.app_context():
            self.assertEqual([tuple(r) for r in get_db().execute('SELECT * FROM predictions')], before)

    def test_only_the_saved_flag_selects_customers(self):
        with self.app.app_context():
            db = get_db()
            for pid, cus, risk, alert in [('p-high-unflagged', 'c1', 0.99, 0), ('p-low-flagged', 'c2', 0.01, 1)]:
                db.execute("INSERT INTO predictions SELECT ?,batch_id,?,?,?,evidence_json,features_json,customer_json,flows_json "
                           "FROM predictions WHERE prediction_id=?", (pid, cus, risk, alert, self.id))
            db.commit()
            self.assertEqual(batch.eligible_ids(db, self.batch), [self.id, 'p-low-flagged'])
            with self.assertRaises(ValueError):
                batch.eligible_ids(db, 'unknown-batch')

    def test_generates_then_resumes_by_skipping_stored_draft(self):
        with patch.object(ai.Gemini, 'generate', return_value=notes()) as provider:
            code, text = self.run_batch()
            self.assertEqual(code, 0)
            self.assertIn('Generated: 1 | Fallback by reason: {} | Skipped (cached): 0 | Remaining: 0', text)
            code, text = self.run_batch()
            self.assertEqual(provider.call_count, 1)
        self.assertIn('already cached: 1 | to generate: 0', text)
        self.assertIn('Generated: 0 | Fallback by reason: {} | Skipped (cached): 1 | Remaining: 0', text)
        self.assertRegex(text, r'Elapsed: \d+\.\ds')

    def test_outcome_line_counts_accepted_drops_and_fallbacks(self):
        unfit = json.dumps(dict(link=dict(text='Failed logins and sessions without transactions both concern online banking access.',
                                          evidence_ids=['feature.login_failure_rate_3m', 'feature.passive_session_rate_3m']),
                                questions=[dict(audience='operations', text='Has the customer reported trouble signing in?',
                                                evidence_ids=['feature.login_failure_rate_3m'])]))
        with patch.object(ai.Gemini, 'generate', return_value=unfit):
            code, text = self.run_batch()
        self.assertEqual(code, 0)
        self.assertIn('Generated: 1 | Fallback by reason: {}', text)
        self.assertIn('Outcomes: accepted 1 (link dropped 1 | question dropped 0) | fallback 0', text)

    def simulated(self, results, ids=('a', 'b', 'c'), **options):
        ids = list(ids)
        load = lambda purpose, pid: (dict(state='not_generated', evidence_hash='h-'+pid), None, None)
        with patch.object(batch, 'eligible_ids', return_value=ids), patch.object(ai, 'load', side_effect=load), \
             patch.object(ai, 'generate', side_effect=results) as generate:
            code, text = self.run_batch(**options)
        return code, text, generate

    def test_limit_and_minimum_interval_between_requests(self):
        saved = dict(state='saved')
        code, text, generate = self.simulated([saved, saved, saved], limit=2, min_interval=5)
        self.assertEqual(generate.call_count, 2)
        self.assertEqual(generate.call_args_list[1].args[2], {'expected_evidence_hash': 'h-b'})
        self.assertEqual(generate.call_args.kwargs['retry']['base'], 10)  # Retries never undercut the interval.
        self.assertIn('Generated: 2', text)
        self.assertIn('Remaining: 1', text)
        self.assertEqual(len(self.sleeps), 1)
        self.assertTrue(4.5 < self.sleeps[0] <= 5)

    def test_daily_quota_stops_cleanly_and_reports_remaining(self):
        fallback = lambda code: dict(state='fallback', failure_code=code)
        code, text, generate = self.simulated([dict(state='saved'), fallback('provider_quota_exhausted'), dict(state='saved')])
        self.assertEqual((code, generate.call_count), (2, 2))
        self.assertIn('daily quota exhausted. 2 flagged customers remain', text)
        self.assertIn('Generated: 1 | Fallback by reason: {"provider_quota_exhausted": 1}', text)
        code, text, generate = self.simulated([fallback('provider_rate_limited'), dict(state='saved')])
        self.assertEqual((code, generate.call_count), (2, 1))
        self.assertIn('rate limit persisted after retries. 3 flagged customers remain', text)
        code, text, generate = self.simulated([fallback('provider_unavailable'), fallback('output_validation_failed'), dict(state='saved')])
        self.assertEqual((code, generate.call_count), (0, 3))
        self.assertIn('{"output_validation_failed": 1, "provider_unavailable": 1}', text)

    def test_repeating_configuration_or_request_errors_stop_immediately(self):
        for failure in ['not_configured', 'invalid_key_format', 'provider_authentication_failed',
                        'provider_access_denied', 'provider_model_unavailable', 'provider_request_rejected']:
            with self.subTest(failure=failure):
                code, text, generate = self.simulated([dict(state='fallback', failure_code=failure),
                                                       dict(state='saved'), dict(state='saved')])
                self.assertEqual((code, generate.call_count), (2, 1))
                self.assertIn(f'Stopped: {failure} would repeat for every customer', text)
                self.assertIn('3 flagged customers remain', text)
                self.assertIn('Generated: 0 | Fallback by reason: {"'+failure+'": 1}', text)

    def test_three_consecutive_unavailable_customers_stop_the_run(self):
        unavailable = dict(state='fallback', failure_code='provider_unavailable')
        # A success resets the count: stop only after the third consecutive outage (6th call); 7th never runs.
        code, text, generate = self.simulated([unavailable, unavailable, dict(state='saved'), unavailable, unavailable,
                                               unavailable, dict(state='saved')], ids='abcdefg')
        self.assertEqual((code, generate.call_count), (2, 6))
        self.assertIn('Stopped: Gemini unavailable for 3 consecutive customers (likely outage). 6 flagged customers remain.', text)
        self.assertIn('Generated: 1 | Fallback by reason: {"provider_unavailable": 5}', text)

    def test_keep_rejected_writes_ignored_jsonl_without_console_text(self):
        artifacts = Path(self.temp.name) / 'artifacts'
        artifacts.mkdir()
        raw = notes(fact='PRIVATE_UNKNOWN_REFERENCE')
        with patch.object(batch, 'ARTIFACTS', artifacts), patch.object(ai.Gemini, 'generate', return_value=raw):
            code, text = self.run_batch()
            self.assertEqual(list(artifacts.iterdir()), [])  # Not opted in: nothing written.
            self.app.config['TXB_GENAI_KEEP_REJECTED'] = True
            with self.assertLogs(self.app.logger, 'WARNING') as logs:
                code, text = self.run_batch(keep_rejected=True)
        self.assertEqual(code, 0)
        self.assertIn('Rejected outputs kept: 1', text)
        self.assertNotIn('PRIVATE_UNKNOWN_REFERENCE', text)
        self.assertNotIn('PRIVATE_UNKNOWN_REFERENCE', str(logs.output))
        [path] = artifacts.iterdir()
        self.assertTrue(path.name.startswith('m6-rejected-') and path.suffix == '.jsonl')
        [record] = [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines()]
        self.assertEqual(record['prediction_id'], self.id)
        self.assertEqual(record['raw_output'], raw)
        self.assertEqual(record['first_rule'], 'evidence_references')
        self.assertIn({'rule': 'evidence_references', 'path': 'link.evidence_ids'}, record['rules'])
        self.assertEqual(self.counts(), [0, 0])

    def test_command_pins_m6_test_database_and_requires_configuration(self):
        with patch.object(batch, 'selected_database', return_value=(Path(self.path), 5, [], {})) as selected, \
             patch('churn_backend.create_app', return_value=self.app), redirect_stdout(io.StringIO()) as stdout:
            with self.assertRaises(SystemExit) as exit_:
                batch.main(['--batch-id', self.batch, '--dry-run'])
        self.assertEqual(exit_.exception.code, 0)
        selected.assert_called_once_with('m6-test')
        self.assertIn('to generate: 1', stdout.getvalue())
        with patch.object(batch, 'selected_database') as selected, patch.dict(os.environ, {'TXB_GENAI_ENABLED': '0'}), \
             redirect_stderr(io.StringIO()):
            for argv in (['--batch-id', self.batch], ['--batch-id', self.batch, '--database', 'x']):
                with self.assertRaises(SystemExit) as exit_:
                    batch.main(argv)
                self.assertEqual(exit_.exception.code, 2)
            selected.assert_not_called()


if __name__ == '__main__':
    unittest.main()
