"""Explicit bounded live checks on synthetic M6 Test: one call, or gated isolation."""
import argparse
import os
import sys
import time
from local_session import ROOT, selected_database


def captured_structure(error):
    """Shape-only view: no scalar values, arbitrary field names, headers or URLs."""
    allowed={'error','errors','detail','details','message','description','error_description',
             'error_message','status','type','code','reason','fieldViolations','field_violations','field','param'}
    budget=[50]
    def shape(value,depth=0):
        budget[0]-=1
        if depth>=5 or budget[0]<=0:
            return 'bounded'
        if isinstance(value,dict):
            return {**{key:shape(item,depth+1) for key,item in list(value.items())[:20] if key in allowed},
                'unknown_fields':sum(1 for key in value if key not in allowed)}
        if isinstance(value,list):
            return {'list_items':[shape(item,depth+1) for item in value[:5]],'count':len(value)}
        return 'null' if value is None else 'string' if isinstance(value,str) else 'number' if isinstance(value,(int,float)) else 'other'
    return {name:shape(getattr(error,name,None)) for name in ['details','message','status','code']}


def review_captured_error(ai_drafts, error, stage, elapsed):
    """Re-extract one retained exception; this loop has no provider call path."""
    import json
    import importlib
    from flask import g
    from churn_backend import ai_diagnostics
    print('Captured error structure:',json.dumps(captured_structure(error),sort_keys=True))
    while True:
        try:
            command=input('Error retained in memory. Enter = reload extractor offline; q = discard and exit: ').strip().lower()
        except (EOFError,KeyboardInterrupt):
            break
        if command=='q':
            break
        if command:
            print('Only Enter (offline extraction) or q is supported. No live request will be made.')
            continue
        importlib.reload(ai_diagnostics)
        ai_drafts.record_diagnostic(stage,time.monotonic()-elapsed,error=error)
        print('Sanitised diagnostic:',json.dumps(g.get('genai_diagnostic',{}),sort_keys=True))


def review_captured_output(ai_drafts, raw, evidence):
    """Print only contract shape/count; revalidate the same memory-only output offline."""
    import json
    import importlib
    from churn_backend import ai_contract
    from churn_backend.validation import ValidationError
    from churn_backend.ai_output_audit import save_synthetic_fixture
    from flask import g
    audit=ai_drafts.audit_output(raw,evidence)
    destination=g.get('genai_synthetic_fixture') or save_synthetic_fixture(raw,evidence,ai_drafts.TOKEN,audit)
    print('Synthetic fixture:',destination)
    print('Contract audit:',json.dumps(audit,sort_keys=True))
    print('Question contract:',json.dumps(ai_contract.question_metadata(raw,evidence['identity']['purpose']),sort_keys=True))
    while True:
        try:
            command=input('Response retained in memory. Enter = validate offline; q = discard and exit: ').strip().lower()
        except (EOFError,KeyboardInterrupt):
            break
        if command=='q':
            break
        if command:
            print('Only Enter or q is supported. No live request will be made.')
            continue
        importlib.reload(ai_contract)
        importlib.reload(ai_drafts)
        print('Question contract:',json.dumps(ai_contract.question_metadata(raw,evidence['identity']['purpose']),sort_keys=True))
        print('Contract audit:',json.dumps(ai_drafts.audit_output(raw,evidence),sort_keys=True))
        try:
            ai_drafts.validate(raw,evidence)
            print('Offline validation: passed; nothing published or saved.')
        except ValidationError:
            print('Offline validation: rejected; nothing published or saved.')
            if g.get('genai_synthetic_fixture'):
                print('Synthetic fixture:',g.genai_synthetic_fixture)


def isolate_minimal(ai_drafts, config, hold_error=False):
    """One synthetic request; no schema, evidence, tool, retry or database write."""
    from google import genai
    from google.genai import types
    from flask import g
    started=time.monotonic()
    from churn_backend.genai_credentials import key_format_issue
    if key_format_issue(os.environ.get('GEMINI_API_KEY')):
        ai_drafts.record_diagnostic('configuration',started,reason='invalid_key_format')
        print('Minimal request: not sent; local key format is invalid. Application request skipped.')
        import json
        print('Sanitised diagnostic:',json.dumps(g.get('genai_diagnostic',{}),sort_keys=True))
        return False
    stage='minimal_create_client'
    try:
        with genai.Client(api_key=os.environ['GEMINI_API_KEY'],vertexai=False,
                http_options=types.HttpOptions(api_version='v1beta',timeout=int(config['timeout']*1000),
                    retry_options=types.HttpRetryOptions(attempts=1))) as client:
            stage='minimal_request'
            result=client.models.generate_content(model=config['model'],contents='Reply with OK.',
                config=types.GenerateContentConfig(max_output_tokens=256))
            if not result.candidates or result.candidates[0].finish_reason!=types.FinishReason.STOP or not result.text:
                print('Minimal request: incomplete/blocked; application request skipped.')
                return False
        print('Minimal request: succeeded; model:',config['model'],'| Elapsed:',round(time.monotonic()-started,3))
        return True
    except Exception as error:
        ai_drafts.record_diagnostic(stage,started,error=error)
        import json
        print('Minimal request: failed; application request skipped.')
        print('Sanitised diagnostic:',json.dumps(g.get('genai_diagnostic',{}),sort_keys=True))
        if hold_error:
            review_captured_error(ai_drafts,error,stage,g.get('genai_diagnostic',{}).get('elapsed_seconds',0))
        return False


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prediction-id',required=True)
    parser.add_argument('--apply',action='store_true',help='Required: authorise the explicit bounded live check')
    parser.add_argument('--isolate',action='store_true',help='At most two calls: minimal first; application only if minimal succeeds')
    parser.add_argument('--hold-error',action='store_true',help='Keep a failure in memory for offline extractor reloads; never retries')
    args=parser.parse_args()
    if not args.apply:
        parser.error('Explicit --apply is required for one live request against synthetic Test evidence')
    if os.environ.get('TXB_GENAI_ENABLED')!='1' or not os.environ.get('GEMINI_API_KEY'):
        parser.error('Configure backend TXB_GENAI_ENABLED and GEMINI_API_KEY locally first')
    database,_,_,_=selected_database('m6-test')
    sys.path.insert(0,str(ROOT/'backend'))
    from churn_backend import create_app, ai_drafts
    app=create_app(dict(DATABASE=str(database),TXB_LOCAL_SESSION=True,TXB_LOCAL_MODE='m6-test',
                       TXB_GENAI_CAPTURE_ERROR=args.hold_error))
    with app.app_context():
        # Validate target/evidence before any live request, even the minimal isolation call.
        state,_,_=ai_drafts.load('summary',args.prediction_id)
        config=ai_drafts.settings()
        if args.isolate and not isolate_minimal(ai_drafts,config,hold_error=args.hold_error):
            raise SystemExit(1)
        result=ai_drafts.generate('summary',args.prediction_id,{'expected_evidence_hash':state['evidence_hash']})
        print('Single live request:',result['state'],'|',result.get('failure_code','validated saved draft'),
              '| Latency:',result.get('latency_seconds','unavailable'))
        from flask import g
        if g.get('genai_diagnostic'):
            import json
            print('Sanitised diagnostic:',json.dumps(g.genai_diagnostic,sort_keys=True))
        if result['state']!='saved':
            if args.hold_error and g.get('genai_captured_output') is not None:
                review_captured_output(ai_drafts,g.genai_captured_output,g.genai_captured_evidence)
            if args.hold_error and g.get('genai_captured_error') is not None:
                diagnostic=g.get('genai_diagnostic',{})
                review_captured_error(ai_drafts,g.genai_captured_error,diagnostic.get('stage','request'),
                                      diagnostic.get('elapsed_seconds',0))
            raise SystemExit(1)


if __name__=='__main__':
    main()
