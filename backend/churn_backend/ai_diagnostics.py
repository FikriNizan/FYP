"""Translate error metadata to fixed diagnostic vocabulary; never emit provider prose."""
import re
import json
import os

STATUSES={value:value for value in (
    'INVALID_ARGUMENT','UNAUTHENTICATED','PERMISSION_DENIED','NOT_FOUND','RESOURCE_EXHAUSTED',
    'FAILED_PRECONDITION','DEADLINE_EXCEEDED','UNAVAILABLE','INTERNAL','UNKNOWN','CANCELLED',
    'OUT_OF_RANGE','UNIMPLEMENTED','ALREADY_EXISTS','ABORTED','DATA_LOSS')}
STATUSES.update({
    'invalid_request':'INVALID_ARGUMENT','parameter_unknown':'INVALID_ARGUMENT',
    'failed_precondition':'FAILED_PRECONDITION','authentication':'UNAUTHENTICATED',
    'permission_denied':'PERMISSION_DENIED','not_found':'NOT_FOUND','model_not_found':'NOT_FOUND',
    'quota_exceeded':'RESOURCE_EXHAUSTED','rate_limit_exceeded':'RESOURCE_EXHAUSTED',
    'too_many_requests':'RESOURCE_EXHAUSTED','api_error':'INTERNAL',
    'invalid_request_error':'INVALID_ARGUMENT','authentication_error':'UNAUTHENTICATED',
    'permission_error':'PERMISSION_DENIED','rate_limit_error':'RESOURCE_EXHAUSTED'})
REASONS=set(('API_KEY_INVALID','API_KEY_EXPIRED','API_KEY_REVOKED','API_KEY_LEAKED','API_KEY_SERVICE_BLOCKED',
    'API_KEY_HTTP_REFERRER_BLOCKED','API_KEY_IP_ADDRESS_BLOCKED','SERVICE_DISABLED',
    'BILLING_DISABLED','CONSUMER_INVALID','ACCESS_TOKEN_EXPIRED','ACCESS_TOKEN_SCOPE_INSUFFICIENT',
    'QUOTA_EXCEEDED','RATE_LIMIT_EXCEEDED','MODEL_NOT_FOUND','MODEL_NOT_SUPPORTED','LOCATION_POLICY_VIOLATED'))
DESCRIPTIONS=[
    (r'client has issued a malformed or illegal request', 'malformed_http_request', 'HTTP server reports that the client issued a malformed or illegal request.'),
    (r'request cannot be fulfilled due to bad syntax', 'malformed_http_request', 'HTTP server reports bad request syntax.'),
    (r'api.?key.{0,80}(?:leak|compromis|expos)', 'key_reported_leaked', 'Provider reports that the API key was leaked or compromised.'),
    (r'api.?key.{0,30}(?:expired|expiration)', 'key_expired', 'Provider reports an expired API key.'),
    (r'api.?key.{0,30}revoked', 'key_revoked', 'Provider reports a revoked API key.'),
    (r'(?:api.?key.{0,30}(?:not valid|invalid|not found)|invalid api.?key)', 'key_invalid', 'Provider reports an invalid API key.'),
    (r'(?:api.?key|referre?r|ip address).{0,60}(?:restrict|blocked)', 'key_restricted', 'Provider reports an API key restriction.'),
    (r'(?:billing|payment).{0,60}(?:required|disabled|not enabled|enable|unavailable)', 'billing_prerequisite', 'Provider reports a billing prerequisite.'),
    (r'(?:user location|region|country).{0,40}(?:not supported|unavailable|restricted)', 'location_prerequisite', 'Provider reports a location prerequisite.'),
    (r'precondition|prerequisite', 'prerequisite_not_met', 'Provider reports an unmet prerequisite.'),
    (r'unknown (?:name|field|parameter)|unrecognized (?:field|parameter)|cannot find field', 'unknown_parameter', 'Provider reports an unrecognised request field.'),
    (r'(?:not supported|unsupported).{0,60}(?:schema|json)|(?:schema|json).{0,60}(?:not supported|unsupported)', 'schema_unsupported', 'Provider reports an unsupported schema option.'),
    (r'(?:invalid|unsupported|unknown).{0,50}(?:argument|parameter|field|value)|(?:field|parameter).{0,50}(?:invalid|unsupported)', 'invalid_parameter', 'Provider reports an invalid request parameter.'),
    (r'quota|rate.?limit', 'quota_or_rate_limit', 'Provider reports a quota or rate limit.'),
]

# General descriptions retain only fixed protocol/error vocabulary, never arbitrary
# provider tokens. Unknown runs collapse to one marker; identifiers/URLs are absent.
SAFE_WORDS=set(('api key keys invalid valid expired revoked leaked compromised missing required '
    'credential credentials authentication authorization unauthenticated unauthorized permission denied '
    'access forbidden restricted restrictions blocked disabled enabled enable unavailable unsupported '
    'billing payment prerequisite precondition account project region location country verification '
    'request requests argument arguments parameter parameters field fields unknown unrecognized '
    'schema json response format endpoint version model supported found not no cannot must please '
    'is are was were has have been be use using pass provide renew check failed error errors '
    'a an the this that for with without and or of to in at from by as reported detected '
    'quota limit exceeded exhausted token tokens header bearer service resource bad malformed '
    'does do support before after only name value type string integer boolean array object').split())


def safe_description(messages):
    for message in messages:
        # Do not let HTML/style boilerplate consume the bounded diagnostic excerpt.
        message=re.sub(r'<style\b[^>]*>.*?</style>|<script\b[^>]*>.*?</script>',' ',message,flags=re.I|re.S)
        message=re.sub(r'<[^>]*>',' ',message)
        words=re.findall(r'[A-Za-z][A-Za-z0-9_\'-]*|[^\sA-Za-z]+',message[:4096])
        output=[]
        recognised=0
        for word in words[:80]:
            if word.lower() in SAFE_WORDS:
                output.append(word.lower());recognised+=1
            elif not output or output[-1]!='[redacted]':
                output.append('[redacted]')
        if recognised>=2:
            return ' '.join(output)[:220]
    return 'Provider rejection details were withheld.'


def safe_request_checks(error):
    """Derived booleans/categories only; no headers, URLs or body values escape."""
    result={}
    try:
        request=error.response.request
        url=request.url
        result['destination']='official_gemini' if url.host=='generativelanguage.googleapis.com' else 'other'
        result['https']=url.scheme=='https'
        result['method_post']=request.method=='POST'
        result['generate_content_route']=bool(re.fullmatch(r'/v1beta/models/[a-zA-Z0-9_.-]+:generateContent',url.path))
        key=os.environ.get('GEMINI_API_KEY')
        if key:
            result['credential_matches_local_key']=request.headers.get('x-goog-api-key')==key
            result['key_has_surrounding_whitespace']=key!=key.strip()
            result['key_has_non_ascii']=not key.isascii()
            result['key_has_control_characters']=any(ord(c)<32 or ord(c)==127 for c in key)
        content=request.content
        if isinstance(content,bytes) and len(content)<=65536:
            try:
                parsed=json.loads(content)
                result['body_is_json_object']=isinstance(parsed,dict)
                if isinstance(parsed,dict):
                    allowed={'contents','generationConfig','systemInstruction','tools','toolConfig','safetySettings'}
                    result['known_body_fields']=sorted(set(parsed)&allowed)
                    result['unknown_body_field_count']=len(set(parsed)-allowed)
            except (ValueError,UnicodeError):
                result['body_is_json_object']=False
    except Exception:
        # Some SDK errors have no attached request. Never stringify that exception.
        pass
    return result


def error_nodes(details):
    """Bounded traversal of known error envelopes, excluding metadata/request bodies."""
    queue=[details]
    nodes=[]
    for _ in range(60):
        if not queue:
            break
        value=queue.pop(0)
        if isinstance(value,str):
            if len(value)<=16384 and value.lstrip().startswith(('{','[')):
                try:
                    queue.append(json.loads(value))
                    continue
                except (ValueError,RecursionError):
                    pass
            nodes.append({'message':value[:4096]})
        elif isinstance(value,list):
            queue.extend(value[:20])
        elif isinstance(value,dict):
            nodes.append(value)
            for name in ['error','errors','detail','details','fieldViolations','field_violations']:
                if name in value:
                    queue.append(value[name])
    return nodes


def safe_provider_error(error, schema):
    result=dict(provider_status=None,provider_reason=None,description_code=None,
                error_description='Provider rejection details were withheld.',invalid_field_path=None)
    nodes=error_nodes(getattr(error,'details',None))
    if not nodes:
        # SDK response JSON is already buffered; this performs no HTTP request.
        response=getattr(error,'response',None)
        if response is not None:
            try:
                nodes=error_nodes(response.json())
            except Exception:
                pass
    result['error_shape']='structured' if any(set(n)&{'status','code','type','reason','error'} for n in nodes) else 'message_only' if nodes else 'unrecognised'
    for value in [getattr(error,'status',None)]+[n.get(k) for n in nodes for k in ['status','type','code']]:
        if isinstance(value,str) and value in STATUSES:
            result['provider_status']=STATUSES[value]
            break
    messages=[]
    fields=[]
    for node in nodes:
        for reason in [node.get('reason'),node.get('code')]:
            if isinstance(reason,str) and reason.upper() in REASONS:
                result['provider_reason']=reason.upper()
        for key in ['message','description','error_description','error_message','detail']:
            if isinstance(node.get(key),str):
                messages.append(node[key][:4096])
        for key in ['field','param','parameter']:
            if isinstance(node.get(key),str):
                fields.append(node[key][:256])
    if isinstance(getattr(error,'message',None),str):
        messages.append(error.message[:4096])
    result['response_format']='html' if any(re.search(r'<!doctype\s+html|<html\b|<title\b',m,re.I) for m in messages) else 'text_or_json'
    if isinstance(getattr(error,'status',None),str) and error.status.upper().replace(' ','_') in {'BAD_REQUEST','UNAUTHORIZED','FORBIDDEN','NOT_FOUND','SERVICE_UNAVAILABLE'}:
        result['http_reason']=error.status.upper().replace(' ','_')
    result['request_checks']=safe_request_checks(error)
    for pattern,code,description in DESCRIPTIONS:
        if any(re.search(pattern,message,re.I) for message in messages):
            result.update(description_code=code,error_description=description)
            break
    if not result['description_code']:
        result['error_description']=safe_description(messages)
    approved={'model','contents','systemInstruction','system_instruction','tools','toolConfig','tool_config'}
    for prefix in ['generationConfig','generation_config']:
        approved.add(prefix)
        for field in ['responseMimeType','response_mime_type','maxOutputTokens','max_output_tokens',
                      'temperature','thinkingConfig','thinking_config','responseSchema','response_schema',
                      'responseJsonSchema','response_json_schema']:
            approved.update([field,prefix+'.'+field])
        def walk(value,path):
            approved.add(path)
            if isinstance(value,dict):
                for key,item in value.items():
                    walk(item,path+'.'+key)
            elif isinstance(value,list):
                for index,item in enumerate(value):
                    walk(item,path+'['+str(index)+']')
        for field in ['responseSchema','response_schema','responseJsonSchema','response_json_schema']:
            for candidate in (schema if isinstance(schema,list) else [schema]):  # One schema per purpose.
                walk(candidate,prefix+'.'+field)
    for message in messages:
        fields.extend(re.findall(r'\b(?:generationConfig|generation_config)\.[A-Za-z_][A-Za-z0-9_.\[\]]*',message))
        fields.extend(re.findall(r'''(?:field|parameter|name)\s*[:=]?\s*["']([A-Za-z_][A-Za-z0-9_.\[\]]*)["']''',message,re.I))
    for field in fields:
        if field in approved:
            result['invalid_field_path']=field
            break
    checks=result['request_checks']
    if checks.get('credential_matches_local_key') and checks.get('key_has_control_characters'):
        result.update(description_code='credential_header_control_characters',
            error_description='Local request inspection found control characters in the configured credential sent with this rejected request.',
            diagnosis_source='local_request_check')
    return result
