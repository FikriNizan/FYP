"""Synthetic offline evaluation; no credentials, network calls or owner database."""
import copy
from contextlib import closing
import json
import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock
from flask import jsonify
from churn_backend import create_app, ai_drafts as ai, ai_evidence as evidence
from churn_backend import repository as repo
from churn_backend.db import get_db
from churn_backend.importer import import_demo
from churn_backend.validation import ValidationError


class DraftTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path=str(Path(self.temp.name)/'test.sqlite')
        self.app=create_app(dict(TESTING=True,DATABASE=self.path))
        self.client=self.app.test_client()
        with self.app.app_context():
            import_demo()
        self.customer=self.client.get('/api/customers/944').json['customer']
        self.id=self.customer['prediction_id']
        self.url='/api/predictions/'+self.id+'/ai-summary'

    def output(self, fact='prediction.risk',kind='recorded_observation',prefix='Recorded activity offers a starting point for committee discussion.'):
        return json.dumps(dict(blocks=[dict(kind=kind,text=prefix+' {{'+fact+'}}. The context remains a matter to verify.',evidence_ids=[fact])],questions=[]))

    def generate(self):
        """Summary generation is batch-only (no HTTP POST). Call the same backend function the batch
        uses and convert the result/error with the app's own JSON and error handlers."""
        evidence_hash=self.client.get(self.url).json['evidence_hash']
        with self.app.test_request_context():
            try:
                return jsonify(ai.generate('summary',self.id,{'expected_evidence_hash':evidence_hash}))
            except Exception as error:
                return self.app.make_response(self.app.handle_user_exception(error))

    def prioritise(self):
        review=dict(decision='prioritise',reason='Synthetic',reviewer='Synthetic',expected_version=0)
        self.assertEqual(self.client.put('/api/predictions/'+self.id+'/review',json=review).status_code,200)
        return '/api/cases/'+self.id+'/ai-discussion'

    def test_get_never_writes_or_calls_provider_and_post_disabled_is_fallback(self):
        with patch.object(ai.Gemini,'generate',side_effect=ai.ProviderFailure('not_configured')) as mock:
            result=self.client.get(self.url)
            self.assertEqual(result.json['state'],'not_generated')
            mock.assert_not_called()
            self.assertEqual(self.generate().json['state'],'fallback')
        with self.app.app_context():
            self.assertEqual(get_db().execute('SELECT count(*) FROM ai_drafts').fetchone()[0],0)

    def test_valid_original_prose_saved_reused_after_restart_and_explicit_regeneration(self):
        with patch.object(ai.Gemini,'generate',return_value=self.output()) as mock:
            first=self.generate().json
            self.assertEqual(first['state'],'saved')
            self.assertNotIn('{{',first['draft']['content']['blocks'][0]['text'])
            app=create_app(dict(TESTING=True,DATABASE=self.path))
            self.assertEqual(app.test_client().get(self.url).json['draft']['draft_id'],first['draft']['draft_id'])
            second=self.generate().json
            self.assertNotEqual(first['draft']['draft_id'],second['draft']['draft_id'])
            self.assertEqual(mock.call_count,2)

    def test_unknown_ids_stale_versions_untrusted_browser_fields_and_origin(self):
        self.assertEqual(self.client.get('/api/predictions/absent/ai-summary').status_code,404)
        # Summary generation is batch-only: the HTTP route is read-only.
        with patch.object(ai.Gemini,'generate') as mock:
            self.assertEqual(self.client.post(self.url,json={'expected_evidence_hash':'x'}).status_code,405)
            mock.assert_not_called()
        # The same HTTP guards on the remaining on-demand route (RM discussion).
        url=self.prioritise()
        self.assertEqual(self.client.post(url,json={'expected_evidence_hash':'stale'}).status_code,409)
        self.assertEqual(self.client.post(url,json={'expected_evidence_hash':'x','risk':0}).status_code,422)
        self.assertEqual(self.client.post(url,json={},headers={'Origin':'https://other.test'}).status_code,403)

    def test_future_outcome_and_later_assessment_do_not_change_historical_summary(self):
        before=self.client.get(self.url).json
        with self.app.app_context():
            db=get_db()
            # Simulates an unrelated later outcome write: no AI source query touches outcomes.
            db.execute("INSERT INTO observed_outcomes VALUES (?,'2024-05-31','2024-05-31',120000,300,1,'[]','synthetic','now')",(self.id,))
            original=json.loads(repo.prediction_row(self.id)['evidence_json'])
            original['cutoff_month']='2024-03-31'
            repo.save_batch('2024-03-31','notebook_case_sample',original['protocol_sha256'],
                [dict(evidence=original,features={'combined_flow_mean_3m_myr':999999})],{})
            db.commit()
        after=self.client.get(self.url).json
        self.assertEqual(before['evidence_hash'],after['evidence_hash'])
        self.assertEqual(before['evidence'],after['evidence'])

    def test_continuing_case_keeps_original_review_distinct_from_latest_features(self):
        self.client.put('/api/predictions/'+self.id+'/review',json=dict(
            decision='prioritise',reason='Original human assessment',reviewer='Synthetic',expected_version=0))
        with self.app.app_context():
            original=evidence.build('summary',self.id)
            saved=copy.deepcopy(original['explanation']);saved['cutoff_month']='2024-03-31'
            features={d['feature']:d['value'] for d in saved['higher_risk_drivers']+saved['lower_risk_drivers']}
            features['estimated_fee_mean_3m_myr']=456
            repo.save_batch('2024-03-31','notebook_case_sample',saved['protocol_sha256'],[dict(evidence=saved,features=features)],{})
            current=evidence.build('discussion',self.id)
            self.assertEqual(current['identity']['cutoff'],'2024-03-31')
            self.assertEqual(current['identity']['original_assessment_cutoff'],'2024-02-29')
            self.assertNotEqual(current['identity']['prediction_id'],self.id)
            self.assertEqual(current['facts']['feature.estimated_fee_mean_3m_myr']['value'],456)
            self.assertNotIn('feature.estimated_fee_mean_3m_myr',original['facts'])
            self.assertEqual(evidence.build('summary',self.id)['evidence_hash'],original['evidence_hash'])

    def test_evidence_and_model_versions_invalidate_saved_content(self):
        with patch.object(ai.Gemini,'generate',return_value=self.output()):first=self.generate().json
        self.app.config['TXB_GENAI_MODEL']='other-admin-configured-model'
        changed=self.client.get(self.url).json
        self.assertEqual(changed['state'],'evidence_changed');self.assertIsNone(changed['draft'])
        self.app.config.pop('TXB_GENAI_MODEL')
        self.assertEqual(self.client.get(self.url).json['draft']['draft_id'],first['draft']['draft_id'])

    def test_reconstruction_failure_never_reaches_provider(self):
        with self.app.app_context():
            db=get_db();row=repo.prediction_row(self.id);saved=json.loads(row['evidence_json'])
            saved['base_logodds']+=1
            db.execute('UPDATE predictions SET evidence_json=? WHERE prediction_id=?',(repo.encode(saved),self.id));db.commit()
        with patch.object(ai.Gemini,'generate') as mock:
            self.assertEqual(self.client.get(self.url).status_code,422)
            mock.assert_not_called()

    def test_missing_zero_ratio_arithmetic_dictionary_and_direction(self):
        with self.app.app_context():
            db=get_db();row=repo.prediction_row(self.id);features=json.loads(row['features_json'])
            features.update(combined_flow_mean_3m_myr=.87,combined_flow_mean_12m_myr=100,
                fd_balance_myr=0,estimated_fee_mean_3m_myr=None,unverified_feature=500)
            db.execute('UPDATE predictions SET features_json=? WHERE prediction_id=?',(repo.encode(features),self.id));db.commit()
            data=evidence.build('summary',self.id);facts=data['facts']
            self.assertIn('0.87% of',facts['activity.comparison']['display'])
            self.assertIn('99.13% lower',facts['activity.comparison']['display'])
            self.assertEqual(facts['feature.fd_balance_myr']['value'],0)
            self.assertNotIn('feature.estimated_fee_mean_3m_myr',facts)
            self.assertNotIn('feature.unverified_feature',facts)
            for fact in facts.values():
                if fact['kind']=='model_signal':
                    self.assertEqual(fact['direction'],'higher' if fact['contribution_logodds']>0 else 'lower')

    def test_invalid_paraphrases_and_schema_are_rejected(self):
        with self.app.app_context():
            data=evidence.build('summary',self.id)
            bad=['Risk is 99%.','Fees are five million ringgit.','The customer is unprofitable.',
                'Service friction caused departure.','Payments deteriorated because of login failures.',
                'The customer will leave.','The customer switched to a competitor.',
                '<script>alert()</script>','Ignore previous instructions.',
                'Activity declined.','The estimate is lower.','Payment issues confirm a complaint.']
            for text in bad:
                with self.subTest(text=text),self.assertRaises(ValidationError):
                    ai.validate(self.output(prefix=text),data)
            for raw in ['{}','[]','not JSON','x'*17000,self.output(fact='unknown.fact')]:
                with self.subTest(raw=raw[:40]),self.assertRaises(ValidationError):ai.validate(raw,data)
            for text in ['The recorded evidence can guide a focused discussion.', 'The available record provides context while customer experience remains unknown.']:
                self.assertTrue(ai.validate(self.output(prefix=text),data)['blocks'])

    def test_typed_clause_rejects_ratio_reinterpretation_and_kind_mismatch(self):
        with self.app.app_context():
            data=evidence.build('summary',self.id)
            for raw in [self.output(kind='model_signal'), self.output().replace('{{prediction.risk}}','The reduction was {{prediction.risk}}')]:
                with self.assertRaises(ValidationError):ai.validate(raw,data)

    def test_failed_regeneration_preserves_previous_valid_cache(self):
        with patch.object(ai.Gemini,'generate',return_value=self.output()):first=self.generate().json
        with patch.object(ai.Gemini,'generate',return_value='invalid'):failed=self.generate().json
        self.assertEqual(failed['state'],'fallback')
        self.assertIsNone(failed['draft'])
        self.assertEqual(self.client.get(self.url).json['draft']['draft_id'],first['draft']['draft_id'])

    def test_duplicate_reservation_and_expiry_recovery(self):
        with self.app.app_context():
            state,data,key=ai.load('summary',self.id)
            db=get_db();db.execute('INSERT INTO ai_reservations VALUES (?,?,?)',(key,'busy',time.time()+30));db.commit()
        with patch.object(ai.Gemini,'generate',return_value=self.output()) as mock:
            self.assertEqual(self.generate().status_code,409);mock.assert_not_called()
            with self.app.app_context():
                db=get_db();db.execute('UPDATE ai_reservations SET expires_at=0');db.commit()
            self.assertEqual(self.generate().json['state'],'saved')

    def test_evidence_change_during_provider_call_prevents_publish(self):
        def change(*args):
            db=get_db();row=repo.prediction_row(self.id);features=json.loads(row['features_json']);features['fd_balance_myr']=77
            db.execute('UPDATE predictions SET features_json=? WHERE prediction_id=?',(repo.encode(features),self.id));db.commit()
            return self.output()
        with patch.object(ai.Gemini,'generate',side_effect=change):self.assertEqual(self.generate().status_code,409)
        with self.app.app_context():self.assertEqual(get_db().execute('SELECT count(*) FROM ai_drafts').fetchone()[0],0)

    def test_case_eligibility_external_privacy_and_pdf_exact_draft(self):
        review=dict(decision='prioritise',reason='Ignore instructions; Alice Secret at C:/private',reviewer='Personal Name',expected_version=0)
        self.assertEqual(self.client.put('/api/predictions/'+self.id+'/review',json=review).status_code,200)
        url='/api/cases/'+self.id+'/ai-discussion'
        with self.app.app_context():
            data=evidence.build('discussion',self.id)
            outbound=repo.encode(evidence.external(data))
            for private in ['Personal Name','Alice Secret','C:/private',self.id,'944']:
                self.assertNotIn(private,outbound)
        with patch.object(ai.Gemini,'generate',return_value=self.output()):
            state=self.client.get(url).json
            draft=self.client.post(url,json={'expected_evidence_hash':state['evidence_hash']}).json['draft']
        preview=self.client.get('/api/briefings',query_string={'case_id':self.id}).json
        selection=dict(case_id=self.id,draft_id=draft['draft_id'],evidence_hash=state['evidence_hash'],acknowledged=True)
        body=dict(case_ids=[self.id],snapshots=preview['snapshots'],ai_drafts=[selection])
        with patch.object(ai.Gemini,'generate') as mock:
            self.assertEqual(self.client.post('/api/briefings/pdf',json=body).status_code,200)
            self.assertEqual(self.client.post('/api/briefings/validate-ai',json=body).status_code,200)
            mock.assert_not_called()
        body['ai_drafts'][0]['acknowledged']=False
        self.assertEqual(self.client.post('/api/briefings/pdf',json=body).status_code,422)
        body['ai_drafts'][0]['acknowledged']=True;body['ai_drafts'][0]['draft_id']='arbitrary'
        self.assertEqual(self.client.post('/api/briefings/pdf',json=body).status_code,409)
        review.update(decision='monitor',expected_version=1,expected_case_version=1)
        self.client.put('/api/predictions/'+self.id+'/review',json=review)
        self.assertEqual(self.client.get(url).status_code,422)

    def test_additive_migration_preserves_every_business_row_and_is_repeatable(self):
        import sqlite3
        with closing(sqlite3.connect(self.path)) as db:
            db.execute('DROP TABLE ai_reservations');db.execute('DROP TABLE ai_drafts')
            db.execute('DELETE FROM schema_migrations WHERE version=5')
            tables=[r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT IN ('schema_migrations','sqlite_sequence')")]
            before={name:db.execute('SELECT * FROM '+name).fetchall() for name in tables}
            db.commit()
        app=create_app(dict(TESTING=True,DATABASE=self.path))
        create_app(dict(TESTING=True,DATABASE=self.path))
        with app.app_context():
            db=get_db()
            self.assertEqual(db.execute('SELECT max(version) FROM schema_migrations').fetchone()[0],5)
            for name,rows in before.items():self.assertEqual([tuple(r) for r in db.execute('SELECT * FROM '+name)],rows)
            self.assertEqual(db.execute('SELECT count(*) FROM ai_drafts').fetchone()[0],0)
        self.assertEqual(len(list(Path(self.path).parent.glob('test.sqlite-pre-migration-*'))),1)

    def test_sdk_boundary_configuration_and_response_failures(self):
        from google.genai import types
        with self.app.app_context():
            data=evidence.build('summary',self.id)
            config=dict(enabled=True,provider='gemini',model='gemini-3.5-flash-lite',timeout=12,tokens=2048)
            with patch.dict(os.environ,{'GEMINI_API_KEY':'synthetic-test-key','GOOGLE_API_KEY':'wrong-key'}),patch('google.genai.Client') as factory:
                client=factory.return_value.__enter__.return_value
                response=MagicMock();response.candidates=[MagicMock(finish_reason=types.FinishReason.STOP)];response.text=self.output()
                client.models.generate_content.return_value=response
                self.assertEqual(ai.Gemini().generate(data,config),self.output())
                self.assertEqual(factory.call_args.kwargs['api_key'],'synthetic-test-key')
                options=factory.call_args.kwargs['http_options']
                self.assertEqual(options.timeout,12000);self.assertEqual(options.retry_options.attempts,1)
                cfg=client.models.generate_content.call_args.kwargs['config']
                self.assertEqual(client.models.generate_content.call_args.kwargs['model'],'gemini-3.5-flash-lite')
                self.assertEqual(cfg.tools,[]);self.assertTrue(cfg.automatic_function_calling.disable)
                self.assertIsNone(cfg.temperature)
                for reason in [types.FinishReason.SAFETY,types.FinishReason.MAX_TOKENS]:
                    response.candidates[0].finish_reason=reason
                    with self.assertRaises(ai.ProviderFailure):ai.Gemini().generate(data,config)
                response.candidates[0].finish_reason=types.FinishReason.STOP;response.text=''
                with self.assertRaises(ai.ProviderFailure):ai.Gemini().generate(data,config)
                response.candidates=[]
                with self.assertRaises(ai.ProviderFailure):ai.Gemini().generate(data,config)
                for failure in [TimeoutError('secret'),RuntimeError('401 key secret'),RuntimeError('429 quota secret')]:
                    client.models.generate_content.side_effect=failure
                    expected='provider_timeout' if isinstance(failure,TimeoutError) else 'provider_request_failed'
                    with self.assertRaisesRegex(ai.ProviderFailure,'^'+expected+'$'):ai.Gemini().generate(data,config)

    def test_safe_diagnostics_are_local_only_and_never_enter_browser_responses(self):
        from google.genai.errors import ClientError
        from flask import g
        secret='DO-NOT-LOG-KEY-PROMPT-CUSTOMER-OR-MESSAGE'
        config=dict(enabled=True,provider='gemini',model='gemini-3.8-flash',timeout=12,tokens=2048)
        for code,status in [(400,'INVALID_ARGUMENT'),(401,'UNAUTHENTICATED'),(403,'PERMISSION_DENIED'),
                            (404,'NOT_FOUND'),(429,'RESOURCE_EXHAUSTED'),(503,'UNAVAILABLE')]:
            with self.subTest(code=code),self.app.app_context():
                self.app.config['TXB_LOCAL_SESSION']=True
                data=evidence.build('summary',self.id)
                failure=ClientError(code,{'error':{'status':status,'message':secret,'details':[secret]}})
                with patch.dict(os.environ,{'GEMINI_API_KEY':secret}),patch('google.genai.Client') as factory:
                    factory.return_value.__enter__.return_value.models.generate_content.side_effect=failure
                    with self.assertLogs(self.app.logger,level='WARNING') as logs:
                        with self.assertRaises(ai.ProviderFailure):
                            ai.Gemini().generate(data,config)
                    diagnostic=g.genai_diagnostic
                    self.assertEqual(diagnostic['stage'],'request')
                    self.assertEqual(diagnostic['exception_class'],'ClientError')
                    self.assertEqual(diagnostic['http_status'],code)
                    self.assertEqual(diagnostic['provider_status'],status)
                    self.assertGreaterEqual(diagnostic['elapsed_seconds'],0)
                    self.assertNotIn(secret,str(logs.output))
                    self.assertNotIn('Traceback',str(logs.output))
        with self.app.app_context():
            self.app.config['TXB_LOCAL_SESSION']=False
            ai.record_diagnostic('request',time.monotonic(),TimeoutError(secret))
            self.assertNotIn('genai_diagnostic',g)
        self.app.config.update(TXB_LOCAL_SESSION=True,TXB_GENAI_ENABLED='1')
        with patch.dict(os.environ,{'GEMINI_API_KEY':secret}),patch('google.genai.Client') as factory:
            factory.return_value.__enter__.return_value.models.generate_content.side_effect=TimeoutError(secret)
            response=self.generate()
            self.assertEqual(response.json['failure_code'],'provider_timeout')
            self.assertNotIn('diagnostic',response.get_data(as_text=True))
            self.assertNotIn(secret,response.get_data(as_text=True))
            self.assertNotIn('TimeoutError',response.get_data(as_text=True))

    def test_real_sdk_serialisation_reaches_mock_transport_once_without_network(self):
        from google import genai
        from google.genai.errors import ClientError
        from google.genai import types
        from flask import g
        self.app.config['TXB_LOCAL_SESSION']=True
        with self.app.app_context():
            data=evidence.build('summary',self.id)
            config=dict(enabled=True,provider='gemini',model='gemini-3.8-flash',timeout=12,tokens=2048)
            with genai.Client(api_key='synthetic-key',vertexai=False,http_options=types.HttpOptions(api_version='v1beta')) as client:
                with patch.dict(os.environ,{'GEMINI_API_KEY':'synthetic-key'}),patch('google.genai.Client',return_value=client),\
                     patch.object(client._api_client,'request',side_effect=ClientError(401,{'error':{'status':'UNAUTHENTICATED','message':'private'}})) as transport:
                    with self.assertRaises(ai.ProviderFailure):ai.Gemini().generate(data,config)
                    transport.assert_called_once()
                    self.assertEqual(g.genai_diagnostic['stage'],'request')
                    self.assertEqual(g.genai_diagnostic['http_status'],401)
                    self.assertIn('generateContent',str(transport.call_args.args[1]))

    def test_diagnostics_distinguish_local_stages_without_echoing_arbitrary_attributes(self):
        from google.genai.errors import ClientError
        from flask import g
        self.app.config['TXB_LOCAL_SESSION']=True
        config=dict(enabled=True,provider='gemini',model='gemini-3.8-flash',timeout=12,tokens=2048)
        with self.app.app_context(),patch.dict(os.environ,{'GEMINI_API_KEY':'synthetic-key'}):
            data=evidence.build('summary',self.id)
            with patch('google.genai.types.GenerateContentConfig',side_effect=ValueError('private request')):
                with self.assertRaises(ai.ProviderFailure):ai.Gemini().generate(data,config)
                self.assertEqual(g.genai_diagnostic['stage'],'build_request')
            failure=ClientError(400,{'error':{'status':'PRIVATE_SECRET_STATUS','message':'private'}})
            ai.record_diagnostic('request',time.monotonic(),failure)
            self.assertIsNone(g.genai_diagnostic['provider_status'])
            failure=ClientError(400,{'error':{'status':'INVALID_ARGUMENT','details':[
                {'reason':'DO-NOT-LOG-SECRET'},{'reason':'API_KEY_INVALID','metadata':{'key':'private'}}]}})
            ai.record_diagnostic('request',time.monotonic(),failure)
            self.assertEqual(g.genai_diagnostic['provider_reason'],'API_KEY_INVALID')
            self.assertNotIn('private',json.dumps(g.genai_diagnostic))
            with patch('google.genai.Client',side_effect=RuntimeError('private key')):
                with self.assertRaises(ai.ProviderFailure):ai.Gemini().generate(data,config)
                self.assertEqual(g.genai_diagnostic['stage'],'create_client')

    def test_demonstrated_503_falls_back_once_with_duration_without_business_writes(self):
        from google.genai.errors import ServerError
        self.app.config.update(TXB_LOCAL_SESSION=True,TXB_GENAI_ENABLED='1')
        with self.app.app_context():
            before=[tuple(r) for r in get_db().execute('SELECT * FROM predictions')]
        failure=ServerError(503,{'error':{'status':'UNAVAILABLE','message':'PRIVATE PROVIDER RESPONSE'}})
        with patch.dict(os.environ,{'GEMINI_API_KEY':'SYNTHETIC-SECRET'}),patch('google.genai.Client') as factory:
            request=factory.return_value.__enter__.return_value.models.generate_content
            request.side_effect=failure
            response=self.generate()
            request.assert_called_once()
            options=factory.call_args.kwargs['http_options']
            self.assertEqual(options.retry_options.attempts,1)
        result=response.json
        self.assertEqual(result['state'],'fallback')
        self.assertEqual(result['failure_code'],'provider_unavailable')
        self.assertEqual(result['source_type'],'deterministic')
        self.assertIsNone(result['draft'])
        self.assertGreaterEqual(result['latency_seconds'],0)
        for private in ['PRIVATE PROVIDER RESPONSE','SYNTHETIC-SECRET','ServerError','UNAVAILABLE','http_status','provider_status']:
            self.assertNotIn(private,response.get_data(as_text=True))
        with self.app.app_context():
            self.assertEqual([tuple(r) for r in get_db().execute('SELECT * FROM predictions')],before)
            self.assertEqual(get_db().execute('SELECT count(*) FROM ai_drafts').fetchone()[0],0)
            self.assertEqual(get_db().execute('SELECT count(*) FROM ai_reservations').fetchone()[0],0)

    def test_risk_noun_is_allowed_while_invented_trends_remain_rejected(self):
        with self.app.app_context():
            data=evidence.build('summary',self.id)
            accepted=ai.validate(self.output(prefix='The saved risk estimate can guide a discussion.'),data)
            self.assertIn('saved risk estimate',accepted['blocks'][0]['text'])
            for prefix in ['Risk is rising.','Activity rises.','The customer is riskier.','Payments fell.']:
                with self.subTest(prefix=prefix),self.assertRaises(ValidationError):
                    ai.validate(self.output(prefix=prefix),data)

    def test_validation_diagnostics_report_only_allowlisted_rule_without_output(self):
        from flask import g
        self.app.config['TXB_LOCAL_SESSION']=True
        with self.app.app_context():
            data=evidence.build('summary',self.id)
            with self.assertLogs(self.app.logger,level='WARNING') as logs:
                with self.assertRaises(ValidationError):
                    ai.validate(self.output(fact='PRIVATE_UNKNOWN_REFERENCE'),data)
            self.assertEqual(g.genai_diagnostic['stage'],'validate_output')
            self.assertEqual(g.genai_diagnostic['rule'],'evidence_references')
            self.assertNotIn('PRIVATE_UNKNOWN_REFERENCE',str(logs.output))
            with self.assertLogs(self.app.logger,level='WARNING') as logs:
                with self.assertRaises(ValidationError):
                    ai.validate('{"PRIVATE_SECRET":1,"PRIVATE_SECRET":2}',data)
            self.assertEqual(g.genai_diagnostic['rule'],'malformed_json')
            self.assertNotIn('PRIVATE_SECRET',str(logs.output))
        with patch.object(ai.Gemini,'generate',return_value=self.output(fact='PRIVATE_UNKNOWN_REFERENCE')):
            result=self.generate()
        self.assertEqual(result.json['failure_code'],'output_validation_failed')
        self.assertNotIn('evidence_references',result.get_data(as_text=True))
        self.assertNotIn('PRIVATE_UNKNOWN_REFERENCE',result.get_data(as_text=True))

    def test_redacted_400_descriptions_field_paths_and_alternative_sdk_error_shapes(self):
        from google.genai.errors import ClientError
        from flask import g
        self.app.config['TXB_LOCAL_SESSION']=True
        examples=[
            ({'error':{'type':'invalid_request_error','message':'Unknown name "response_json_schema". PRIVATE_KEY',
                       'param':'generation_config.response_json_schema'}},'INVALID_ARGUMENT',None,'unknown_parameter','generation_config.response_json_schema'),
            ({'error':{'code':'api_key_invalid','message':'API key not valid. PRIVATE_KEY'}},None,'API_KEY_INVALID','key_invalid',None),
            ({'message':'API key expired. PRIVATE_KEY'},None,None,'key_expired',None),
            ({'error':{'status':'INVALID_ARGUMENT','details':[{'@type':'type.googleapis.com/google.rpc.BadRequest',
                'fieldViolations':[{'field':'generationConfig.responseJsonSchema.properties.blocks.items',
                                    'description':'Invalid field value PRIVATE_CUSTOMER'}]}]}},'INVALID_ARGUMENT',None,'invalid_parameter','generationConfig.responseJsonSchema.properties.blocks.items'),
            ({'error':{'status':'failed_precondition','message':'Billing is not enabled for PRIVATE_PROJECT'}},'FAILED_PRECONDITION',None,'billing_prerequisite',None),
            ({'detail':'API key expired. PRIVATE_KEY'},None,None,'key_expired',None),
            ({'error':'API key not valid. PRIVATE_KEY'},None,None,'key_invalid',None),
            ('API key was reported as leaked. PRIVATE_KEY',None,None,'key_reported_leaked',None),
            ('{"error":{"type":"authentication_error","message":"API key expired. PRIVATE_KEY"}}','UNAUTHENTICATED',None,'key_expired',None),
        ]
        with self.app.app_context():
            for payload,status,reason,description,path in examples:
                with self.subTest(description=description),self.assertLogs(self.app.logger,level='WARNING') as logs:
                    ai.record_diagnostic('request',time.monotonic(),ClientError(400,payload))
                diagnostic=g.genai_diagnostic
                self.assertEqual(diagnostic['provider_status'],status)
                self.assertEqual(diagnostic['provider_reason'],reason)
                self.assertEqual(diagnostic['description_code'],description)
                self.assertEqual(diagnostic['invalid_field_path'],path)
                self.assertNotIn('PRIVATE_',json.dumps(diagnostic))
                self.assertNotIn('PRIVATE_',str(logs.output))
            with self.assertLogs(self.app.logger,level='WARNING') as logs:
                ai.record_diagnostic('request',time.monotonic(),ClientError(400,{'error':{
                    'message':'PRIVATE_UNKNOWN_ERROR','param':'contents.PRIVATE_CUSTOMER'}}))
            self.assertIsNone(g.genai_diagnostic['invalid_field_path'])
            self.assertEqual(g.genai_diagnostic['error_description'],'Provider rejection details were withheld.')
            self.assertNotIn('PRIVATE_',str(logs.output))
            ai.record_diagnostic('request',time.monotonic(),ClientError(400,{'detail':
                'Request must use a supported endpoint. PRIVATE_KEY https://private.test?key=SECRET CustomerPrivate 123456'}))
            description=g.genai_diagnostic['error_description']
            self.assertIn('supported endpoint',description)
            for private in ['PRIVATE','https','private.test','SECRET','CustomerPrivate','123456']:
                self.assertNotIn(private,description)

    def test_isolation_stops_after_failed_minimal_and_runs_application_only_after_success(self):
        import sys
        import io
        from contextlib import redirect_stdout
        sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'scripts'))
        import gemini_smoke as smoke
        from google.genai.errors import ClientError
        from google.genai import types
        argv=['gemini_smoke.py','--prediction-id',self.id,'--apply','--isolate']
        failure=ClientError(400,{'error':{'message':'API key expired. PRIVATE_KEY'}})
        for succeed in [False,True]:
            with self.subTest(minimal_succeeds=succeed),patch.object(sys,'argv',argv),\
                 patch.dict(os.environ,{'GEMINI_API_KEY':'synthetic-key','TXB_GENAI_ENABLED':'1'}),\
                 patch.object(smoke,'selected_database',return_value=(Path(self.path),5,[],{})),\
                 patch('churn_backend.create_app',return_value=self.app),patch('google.genai.Client') as factory,\
                 patch.object(ai.Gemini,'generate',return_value=self.output()) as application,redirect_stdout(io.StringIO()) as stdout:
                client=factory.return_value.__enter__.return_value
                if succeed:
                    client.models.generate_content.return_value=MagicMock(candidates=[MagicMock(finish_reason=types.FinishReason.STOP)],text='OK')
                    smoke.main()
                    application.assert_called_once()
                else:
                    client.models.generate_content.side_effect=failure
                    with self.assertRaises(SystemExit):smoke.main()
                    application.assert_not_called()
                client.models.generate_content.assert_called_once()
                call=client.models.generate_content.call_args.kwargs
                self.assertEqual(call['contents'],'Reply with OK.')
                self.assertIsNone(call['config'].response_json_schema)
                self.assertIsNone(call['config'].tools)
                self.assertEqual(factory.call_args.kwargs['http_options'].retry_options.attempts,1)
                self.assertNotIn('PRIVATE_KEY',stdout.getvalue())
                self.assertNotIn('synthetic-key',stdout.getvalue())

    def test_held_error_is_reparsed_offline_without_a_second_live_request(self):
        import sys
        import io
        from contextlib import redirect_stdout
        from flask import g
        from google.genai.errors import ClientError
        sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'scripts'))
        import gemini_smoke as smoke
        error=ClientError(400,{'error':{'message':'API key not valid. PRIVATE_KEY',
            'PRIVATE_FIELD':{'headers':'PRIVATE_HEADERS','url':'https://private/?key=SECRET'}}})
        self.app.config.update(TXB_LOCAL_SESSION=True,TXB_GENAI_CAPTURE_ERROR=True)
        with self.app.app_context(),patch.dict(os.environ,{'GEMINI_API_KEY':'synthetic-key'}),\
             patch('google.genai.Client') as factory,patch('builtins.input',side_effect=['','q']),\
             redirect_stdout(io.StringIO()) as stdout:
            client=factory.return_value.__enter__.return_value
            client.models.generate_content.side_effect=error
            config=dict(model='gemini-3.5-flash-lite',timeout=12)
            self.assertFalse(smoke.isolate_minimal(ai,config,hold_error=True))
            client.models.generate_content.assert_called_once()
            self.assertIs(g.genai_captured_error,error)
            self.assertEqual(g.genai_diagnostic['description_code'],'key_invalid')
            output=stdout.getvalue()
            self.assertEqual(output.count('Sanitised diagnostic:'),2)
            for secret in ['PRIVATE_KEY','PRIVATE_FIELD','PRIVATE_HEADERS','https://private','synthetic-key']:
                self.assertNotIn(secret,output)
        self.app.config['TXB_GENAI_CAPTURE_ERROR']=False
        with self.app.app_context():
            ai.record_diagnostic('request',time.monotonic(),error=error)
            self.assertNotIn('genai_captured_error',g)

    def test_html_400_is_extracted_offline_without_exposing_request_or_credentials(self):
        import httpx2
        from google.genai.errors import ClientError
        from flask import g
        key='PRIVATE_SYNTHETIC_KEY'
        request=httpx2.Request('POST','https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash-lite:generateContent?key=PRIVATE_URL_KEY',
            headers={'x-goog-api-key':key,'PRIVATE_HEADER':'PRIVATE_HEADER_VALUE'},
            json={'contents':[{'parts':[{'text':'PRIVATE_BODY'}]}],'generationConfig':{'maxOutputTokens':256}})
        response=httpx2.Response(400,request=request)
        error=ClientError(400,{'status':'Bad Request','message':
            '<html><style>PRIVATE_STYLE</style><title>Error 400 (Bad Request)</title><p>Your client has issued a malformed or illegal request.</p>PRIVATE_BODY</html>'},response)
        self.app.config['TXB_LOCAL_SESSION']=True
        with self.app.app_context(),patch.dict(os.environ,{'GEMINI_API_KEY':key}),\
             self.assertLogs(self.app.logger,level='WARNING') as logs:
            ai.record_diagnostic('minimal_request',time.monotonic(),error=error)
            diagnostic=g.genai_diagnostic
            self.assertEqual(diagnostic['response_format'],'html')
            self.assertEqual(diagnostic['http_reason'],'BAD_REQUEST')
            self.assertIsNone(diagnostic['provider_status'])
            self.assertEqual(diagnostic['description_code'],'malformed_http_request')
            self.assertEqual(diagnostic['request_checks']['destination'],'official_gemini')
            self.assertTrue(diagnostic['request_checks']['generate_content_route'])
            self.assertTrue(diagnostic['request_checks']['credential_matches_local_key'])
            self.assertTrue(diagnostic['request_checks']['body_is_json_object'])
            for private in [key,'PRIVATE_URL_KEY','PRIVATE_BODY','PRIVATE_HEADER','PRIVATE_STYLE','https://']:
                self.assertNotIn(private,str(logs.output))
        bad_key='synthetic\tkey'
        bad_request=httpx2.Request('POST','https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash-lite:generateContent',headers={'x-goog-api-key':bad_key},json={'contents':[]})
        bad_error=ClientError(400,{'status':'Bad Request','message':'<html><title>400 Bad Request</title></html>'},httpx2.Response(400,request=bad_request))
        with self.app.app_context(),patch.dict(os.environ,{'GEMINI_API_KEY':bad_key}):
            ai.record_diagnostic('minimal_request',time.monotonic(),error=bad_error)
            self.assertEqual(g.genai_diagnostic['description_code'],'credential_header_control_characters')
            self.assertEqual(g.genai_diagnostic['diagnosis_source'],'local_request_check')
            self.assertIsNone(g.genai_diagnostic['provider_reason'])
            self.assertNotIn(bad_key,json.dumps(g.genai_diagnostic))

    def test_malformed_local_key_is_rejected_before_sdk_and_preserves_fallback(self):
        from churn_backend.genai_credentials import key_format_issue
        self.app.config.update(TXB_LOCAL_SESSION=True,TXB_GENAI_ENABLED='1')
        # Environment APIs themselves forbid NUL; exercise that helper case directly.
        self.assertEqual(key_format_issue('synthetic\x00key'),'control_characters')
        for key in ['synthetic\tkey','synthetic\nkey','synthetic\rkey','synthetic\x7fkey',' synthetic-key','synthetic-key ']:
            with self.subTest(kind=key_format_issue(key)),patch.dict(os.environ,{'GEMINI_API_KEY':key}),\
                 patch('google.genai.Client') as factory:
                result=self.generate()
                factory.assert_not_called()
                self.assertEqual(result.json['failure_code'],'invalid_key_format')
                self.assertEqual(result.json['state'],'fallback')
                self.assertEqual(result.json['source_type'],'deterministic')
                self.assertIsNone(result.json['draft'])
                self.assertNotIn(key,result.get_data(as_text=True))
        self.assertIsNone(key_format_issue('synthetic-clean-key'))

    def test_minimal_isolation_never_sends_a_key_containing_control_characters(self):
        import sys
        import io
        from contextlib import redirect_stdout
        from flask import g
        sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'scripts'))
        import gemini_smoke as smoke
        self.app.config['TXB_LOCAL_SESSION']=True
        with self.app.app_context(),patch.dict(os.environ,{'GEMINI_API_KEY':'synthetic\tkey'}),\
             patch('google.genai.Client') as factory,redirect_stdout(io.StringIO()) as stdout:
            self.assertFalse(smoke.isolate_minimal(ai,dict(model='gemini-3.5-flash-lite',timeout=12)))
            factory.assert_not_called()
            self.assertEqual(g.genai_diagnostic['reason'],'invalid_key_format')
            self.assertIn('not sent',stdout.getvalue())
            self.assertNotIn('synthetic',stdout.getvalue())

    def test_question_contract_diagnostics_retain_only_opt_in_memory_and_no_question_text(self):
        from churn_backend.ai_contract import question_metadata
        from flask import g
        payload=json.loads(self.output())
        payload['questions']=[dict(text='PRIVATE_QUESTION',evidence_ids=['PRIVATE_REFERENCE']) for _ in range(4)]
        raw=json.dumps(payload)
        expected=dict(purpose='summary',questions_field_type='array',actual_count=4,permitted_minimum=0,permitted_maximum=3)
        self.assertEqual(question_metadata(raw,'summary'),expected)
        self.app.config.update(TXB_LOCAL_SESSION=True,TXB_GENAI_CAPTURE_ERROR=True)
        with self.app.app_context(),self.assertLogs(self.app.logger,level='WARNING') as logs:
            data=evidence.build('summary',self.id)
            with self.assertRaises(ValidationError):ai.validate(raw,data)
            self.assertEqual(g.genai_diagnostic['question_contract'],expected)
            self.assertEqual(g.genai_captured_output,raw)
            self.assertNotIn('PRIVATE_',str(logs.output))
        with patch.object(ai.Gemini,'generate',return_value=raw):
            response=self.generate()
        self.assertEqual(response.json['failure_code'],'output_validation_failed')
        self.assertNotIn('PRIVATE_',response.get_data(as_text=True))
        self.assertNotIn('question_contract',response.get_data(as_text=True))

    def test_purpose_contract_schema_and_instructions_share_zero_to_three_or_five(self):
        from churn_backend.ai_contract import limits_for,schema_for,purpose_instruction
        for purpose,maximum in [('summary',3),('discussion',5)]:
            with self.subTest(purpose=purpose):
                limits=limits_for(purpose)
                schema=schema_for(purpose)
                questions=schema['properties']['questions']
                self.assertEqual(questions['type'],'array')
                self.assertEqual(questions['minItems'],0)
                self.assertEqual(questions['maxItems'],maximum)
                self.assertEqual(questions['maxItems'],limits['question_max'])
                instruction=purpose_instruction(purpose)
                self.assertIn('0–'+str(maximum)+' verification questions',instruction)
                self.assertIn('return []',instruction)
                # Schema instances cannot mutate the shared contract or another request.
                questions['maxItems']=99
                self.assertEqual(schema_for(purpose)['properties']['questions']['maxItems'],maximum)

    def test_question_empty_boundary_over_limit_and_wrong_types_for_both_purposes(self):
        for purpose,maximum in [('summary',3),('discussion',5)]:
            with self.app.app_context():
                data=evidence.build('summary',self.id)
                data['identity']['purpose']=purpose
                payload=json.loads(self.output())
                question=dict(text='Could we verify the recorded context?',evidence_ids=['prediction.risk'])
                for count in [0,1,maximum]:
                    with self.subTest(purpose=purpose,count=count):
                        payload['questions']=[copy.deepcopy(question) for _ in range(count)]
                        accepted=ai.validate(json.dumps(payload),data)
                        self.assertEqual(len(accepted['questions']),count)
                for wrong in [[copy.deepcopy(question) for _ in range(maximum+1)],None,{},'PRIVATE_QUESTION',False,3]:
                    with self.subTest(purpose=purpose,wrong_type=type(wrong).__name__),self.assertRaisesRegex(ValidationError,'Invalid question count'):
                        payload['questions']=wrong
                        ai.validate(json.dumps(payload),data)

    def test_sdk_uses_selected_purpose_limits_in_schema_and_prompt(self):
        from churn_backend.ai_contract import schema_for
        from google.genai import types
        with self.app.app_context(),patch.dict(os.environ,{'GEMINI_API_KEY':'synthetic-key'}),\
             patch('google.genai.Client') as factory:
            data=evidence.build('summary',self.id)
            client=factory.return_value.__enter__.return_value
            client.models.generate_content.return_value=MagicMock(candidates=[MagicMock(finish_reason=types.FinishReason.STOP)],text=self.output())
            config=dict(enabled=True,provider='gemini',model='gemini-3.5-flash-lite',timeout=12,tokens=2048)
            for purpose,maximum in [('summary',3),('discussion',5)]:
                with self.subTest(purpose=purpose):
                    data['identity']['purpose']=purpose
                    ai.Gemini().generate(data,config)
                    sent=client.models.generate_content.call_args.kwargs['config']
                    self.assertEqual(sent.response_json_schema,schema_for(purpose,[f['id'] for f in evidence.external(data)['facts']]))
                    self.assertIn('0–'+str(maximum)+' verification questions',sent.system_instruction)
                    self.assertIn('return []',sent.system_instruction)
                    self.assertIn('Never invent or pad questions',sent.system_instruction)

    def test_unavailable_model_description_is_not_misreported_as_invalid_model_field(self):
        from churn_backend.ai_diagnostics import safe_provider_error
        from google.genai.errors import ServerError
        error=ServerError(503,{'error':{'status':'UNAVAILABLE','message':'This model is experiencing high demand. Please try again later.'}})
        diagnostic=safe_provider_error(error,ai.SCHEMA)
        self.assertIsNone(diagnostic['invalid_field_path'])

    def test_complete_audit_collects_all_applicable_failures_without_exposing_unknown_text(self):
        with self.app.app_context():
            data=evidence.build('summary',self.id)
            raw=json.dumps(dict(blocks=[
                dict(kind='recorded_observation',text='Synthetic context. {{prediction.risk}}. Activity fell.',evidence_ids=['PRIVATE_UNKNOWN_REFERENCE']),
                dict(kind='model_signal',text='{{feature.login_failure_rate_3m}}. The customer will leave.',evidence_ids=['feature.login_failure_rate_3m'])],
                questions=[dict(text='Explain profitability 5%',evidence_ids=['PRIVATE_QUESTION_REFERENCE'])]))
            report=ai.audit_output(raw,data)
            rules={item['rule'] for item in report['failures']}
            self.assertTrue({'evidence_references','unprotected_comparison','statement_kind','prohibited_claim','protected_content','verification_question'}<=rules)
            refs=next(item for item in report['failures'] if item['path']=='blocks[0].evidence_ids')
            self.assertEqual(refs['received_type'],'array')
            self.assertEqual(refs['missing_references'],['prediction.risk'])
            self.assertEqual(refs['unknown_fact_ids'],['unknown_1'])
            self.assertNotIn('PRIVATE_',json.dumps(report))
            self.assertNotIn('profitability',json.dumps(report))

    def test_synthetic_replay_fixture_has_no_provider_prose_or_bank_values(self):
        from churn_backend.ai_output_audit import synthetic_fixture
        with self.app.app_context(),patch.object(ai.Gemini,'generate') as provider:
            data=evidence.build('summary',self.id)
            payload=json.loads(self.output(prefix='PRIVATE_PROVIDER_PROSE.'))
            payload['blocks'][0]['evidence_ids']=['PRIVATE_REFERENCE']
            raw=json.dumps(payload)
            fixture=synthetic_fixture(raw,data,ai.TOKEN,ai.audit_output(raw,data))
            encoded=json.dumps(fixture)
            self.assertNotIn('PRIVATE_',encoded)
            self.assertNotIn(str(self.customer['calibrated_risk']),encoded)
            self.assertNotIn(self.id,encoded)
            replay=ai.audit_output(repo.encode(fixture['output']),fixture['evidence'])
            self.assertIn('evidence_references',{f['rule'] for f in replay['failures']})
            provider.assert_not_called()

    def test_live_reference_schema_enumerates_only_payload_ids(self):
        from churn_backend.ai_contract import schema_for,reference_registry
        with self.app.app_context():
            data=evidence.build('summary',self.id)
            allowed=reference_registry(data)
            schema=schema_for('summary',list(allowed))
            for section in ['blocks','questions']:
                refs=schema['properties'][section]['items']['properties']['evidence_ids']
                self.assertEqual(refs['minItems'],1)
                self.assertEqual(refs['maxItems'],4)
                self.assertEqual(set(refs['items']['enum']),set(allowed))
            wrong=copy.deepcopy(data)
            wrong['facts']['prediction.risk']['id']='mismatched.registry'
            with self.assertRaises(ValidationError):reference_registry(wrong)

