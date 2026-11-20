"""All-rule, privacy-safe analysis of bounded narrative; no repairs or guessed links."""
import re
from . import ai_evidence
from .ai_contract import limits_for, KINDS, REFERENCE_MIN, REFERENCE_MAX, reference_registry
from .validation import strict_json, ValidationError

MESSAGES={
 'output_size':'Oversized or empty AI output','malformed_json':'Invalid JSON','schema':'Invalid narrative schema',
 'block_count':'Invalid narrative block count','question_count':'Invalid question count',
 'block_fields':'Invalid block fields','text_length':'Invalid narrative text',
 'evidence_references':'Unknown evidence references','statement_kind':'Statement kind mismatch',
 'placeholder_reference':'Unlinked placeholder','missing_protected_clause':'Factual statements require protected fact clauses',
 'protected_content':'Unprotected quantity/date/markup','prohibited_claim':'Prohibited narrative claim',
 'unprotected_comparison':'Unprotected comparison','placeholder_boundary':'Fact placeholder must be an independent clause',
 'verification_question':'Question must invite verification','question_relevance':'Question topic lacks relevant evidence',
 'unresolved_placeholder':'Unresolved placeholder','resolved_word_limit':'Draft exceeds bounded length',
 # Summary notes contract (m6-narrative-5).
 'note_fields':'Invalid note fields','note_length':'AI note exceeds bounded length',
 'section_reference':'Note cites evidence from another section','question_fields':'Invalid question fields',
 'question_audience':'Question audience lacks matching evidence','question_length':'Question exceeds bounded length',
 'model_word_limit':'AI text exceeds bounded length',
}


def json_type(value):
    return ('null' if value is None else 'boolean' if isinstance(value,bool) else 'array' if isinstance(value,list)
        else 'object' if isinstance(value,dict) else 'string' if isinstance(value,str) else 'number')


def reference_labeler(evidence,token):
    facts=evidence['facts']
    trusted={part for key in facts for part in key.split('.')}
    trusted.update({'features','signals','operations','finance','explanation','calibrated_risk',
        'probability_cutoff','review_alert','higher_risk_drivers','lower_risk_drivers'})
    aliases={}
    def safe_id(value):
        if isinstance(value,str):
            match=token.fullmatch(value)
            bare=match[1] if match else value
            if bare in facts or (len(bare)<=128 and all(part in trusted for part in bare.split('.'))):
                return value
        key=(type(value).__name__,str(value) if isinstance(value,(str,int,float,bool,type(None))) else repr(type(value)))
        if key not in aliases:
            aliases[key]='unknown_'+str(len(aliases)+1)
        return aliases[key]
    return safe_id


def inspect_output(raw,evidence,token,quantity,prohibited,comparison):
    facts=evidence['facts']
    sent=reference_registry(evidence)
    bounds=limits_for(evidence['identity']['purpose'])
    errors=[]
    resolved={'blocks':[],'questions':[]}
    safe_id=reference_labeler(evidence,token)
    def issue(rule,path,**details):
        errors.append(dict(rule=rule,path=path,**details))
    report=dict(purpose=evidence['identity']['purpose'],expected_reference_structure=
        'array of '+str(REFERENCE_MIN)+'–'+str(REFERENCE_MAX)+' unique bare fact IDs from the current provider payload; placeholders belong in text only',
        supplied_fact_count=len(sent),failures=errors)
    if not isinstance(raw,str) or len(raw.encode())>16000:
        issue('output_size','$',received_type=json_type(raw))
        return report,None
    try:
        parsed=strict_json(raw)
    except ValidationError:
        issue('malformed_json','$')
        return report,None
    if not isinstance(parsed,dict):
        issue('schema','$',received_type=json_type(parsed))
        return report,None
    if set(parsed)!={'blocks','questions'}:
        issue('schema','$')
    words=0
    checked=set()
    words_complete=True
    for section,is_question in [('blocks',False),('questions',True)]:
        entries=parsed.get(section)
        low=bounds['question_min' if is_question else 'block_min']
        high=bounds['question_max' if is_question else 'block_max']
        if not isinstance(entries,list) or not low<=len(entries)<=high:
            issue('question_count' if is_question else 'block_count',section,received_type=json_type(entries) if section in parsed else 'missing',
                actual_count=len(entries) if isinstance(entries,list) else None,minimum=low,maximum=high)
        if not isinstance(entries,list):
            words_complete=False
            continue
        for index,entry in enumerate(entries):
            path=f'{section}[{index}]'
            expected={'text','evidence_ids'} if is_question else {'kind','text','evidence_ids'}
            if not isinstance(entry,dict):
                issue('block_fields',path,received_type=json_type(entry));words_complete=False;continue
            if set(entry)!=expected:
                issue('block_fields',path)
            text=entry.get('text')
            refs=entry.get('evidence_ids')
            tokens=token.findall(text) if isinstance(text,str) else []
            valid_refs=isinstance(refs,list) and all(isinstance(r,str) for r in refs)
            missing=[safe_id(t) for t in dict.fromkeys(tokens) if not isinstance(refs,list) or t not in refs]
            unknown=[safe_id(r) for r in refs if not isinstance(r,str) or r not in sent] if isinstance(refs,list) else []
            refs_ok=valid_refs and REFERENCE_MIN<=len(refs)<=REFERENCE_MAX and not unknown and len(set(refs))==len(refs)
            if not refs_ok:
                issue('evidence_references',path+'.evidence_ids',received_type=json_type(refs) if 'evidence_ids' in entry else 'missing',
                    actual_count=len(refs) if isinstance(refs,list) else None,missing_references=missing,unknown_fact_ids=unknown,
                    duplicate_references=valid_refs and len(set(refs))!=len(refs),
                    invalid_entries=[dict(path=path+'.evidence_ids['+str(i)+']',received_type=json_type(r),id=safe_id(r))
                        for i,r in enumerate(refs) if not isinstance(r,str) or r not in sent] if isinstance(refs,list) else [])
            if not is_question:
                kind=entry.get('kind')
                if kind not in KINDS or (valid_refs and any(facts[r]['kind']!=kind for r in refs if r in facts)):
                    issue('statement_kind',path+'.kind',received_type=json_type(kind))
            if not isinstance(text,str) or not 1<=len(text)<=1600:
                issue('text_length',path+'.text',received_type=json_type(text));words_complete=False
            if not isinstance(text,str):
                continue
            if missing:
                issue('placeholder_reference',path+'.text',missing_references=missing)
            if not is_question and (not valid_refs or set(tokens)!=set(refs)):
                issue('missing_protected_clause',path+'.text')
            plain=token.sub('',text)
            if any(c in plain for c in '{}<>`\\') or quantity.search(plain):
                issue('protected_content',path+'.text')
            if prohibited.search(plain):
                issue('prohibited_claim',path+'.text')
            if comparison.search(plain):
                issue('unprotected_comparison',path+'.text')
            if any((text[:m.start()].rstrip() and text[:m.start()].rstrip()[-1] not in '.!?')
                or (text[m.end():].lstrip() and text[m.end():].lstrip()[0] not in '.!?') for m in token.finditer(text)):
                issue('placeholder_boundary',path+'.text')
            if is_question:
                if not text.endswith('?') or not re.match(r'^(?:Could|Can|Would|Has|Have|Is|Are|What|How|Do|Does)\b',text):
                    issue('verification_question',path+'.text')
                if valid_refs:
                    for topic,identifiers in [('login|signing in',('login',)),('payment',('flow','failure')),
                            ('deposit|maturity',('fd_',)),('fees?|waivers?',('fee','waiver')),('balance',('balance',))]:
                        if re.search(r'\b(?:'+topic+r')\w*\b',plain,re.I) and not any(any(i in r for i in identifiers) for r in refs):
                            issue('question_relevance',path+'.evidence_ids')
            if all(t in sent for t in tokens):
                rendered=token.sub(lambda m:facts[m[1]]['clause'],text)
                if '{{' in rendered or '}}' in rendered:
                    issue('unresolved_placeholder',path+'.text')
                words+=len(rendered.split())
                resolved[section].append({**entry,'text':rendered})
            else:
                words_complete=False
                issue('unresolved_placeholder',path+'.text',unknown_fact_ids=[safe_id(t) for t in tokens if t not in sent])
            if valid_refs:
                checked.update(r for r in refs if r in sent)
    if words>bounds['word_max']:
        issue('resolved_word_limit','$',maximum=bounds['word_max'])
    report['resolved_word_count_complete']=words_complete
    report['failure_count']=len(errors)
    if errors:
        return report,None
    return report,dict(**resolved,evidence_ids=sorted(checked),checks=[
        'saved_prediction_identity','shap_reconstruction_2e-10','raw_calibration_2e-10',
        'schema_length','known_references','statement_kind','protected_fact_clauses','numeric_date_rules','interpretation_rules'])


def inspect_notes(raw,evidence,token,quantity,prohibited,comparison):
    """Summary contract: model text is short section notes + audience-tagged questions only.
    The server renders every fact sentence, so clause/kind/block/boundary rules do not apply here;
    content, reference, question and length rules apply to everything the model wrote."""
    from .ai_render import plan, section_ids, NOTE_SECTIONS
    from .ai_contract import AUDIENCES
    bounds=limits_for('summary')
    sections=section_ids(plan(evidence))
    known=set().union(*sections.values())
    safe_id=reference_labeler(evidence,token)
    errors=[]
    def issue(rule,path,**details):
        errors.append(dict(rule=rule,path=path,**details))
    report=dict(purpose='summary',expected_reference_structure='array of '+str(REFERENCE_MIN)+'–'+str(REFERENCE_MAX)+
        ' unique bare fact IDs from the same card section; [] for an empty note',supplied_fact_count=len(known),failures=errors)
    if not isinstance(raw,str) or len(raw.encode())>16000:
        issue('output_size','$',received_type=json_type(raw))
        return report,None
    try:
        parsed=strict_json(raw)
    except ValidationError:
        issue('malformed_json','$')
        return report,None
    if not isinstance(parsed,dict):
        issue('schema','$',received_type=json_type(parsed))
        return report,None
    if set(parsed)!={'notes','questions'}:
        issue('schema','$')
    words=0
    def check_text(text,refs,path,allowed,max_words,length_rule):
        nonlocal words
        tokens=token.findall(text)
        valid_refs=isinstance(refs,list) and all(isinstance(r,str) for r in refs)
        unknown=[safe_id(r) for r in refs if not isinstance(r,str) or r not in known] if isinstance(refs,list) else []
        if not (valid_refs and REFERENCE_MIN<=len(refs)<=REFERENCE_MAX and not unknown and len(set(refs))==len(refs)):
            issue('evidence_references',path+'.evidence_ids',received_type=json_type(refs),
                actual_count=len(refs) if isinstance(refs,list) else None,unknown_fact_ids=unknown,
                duplicate_references=valid_refs and len(set(refs))!=len(refs))
        elif allowed is not None and not set(refs)<=allowed:
            issue('section_reference',path+'.evidence_ids')
        if any(t not in known for t in tokens):
            issue('unresolved_placeholder',path+'.text',unknown_fact_ids=[safe_id(t) for t in tokens if t not in known])
        if not valid_refs or any(t not in refs for t in tokens):
            issue('placeholder_reference',path+'.text',missing_references=[safe_id(t) for t in dict.fromkeys(tokens)
                if not valid_refs or t not in refs])
        plain=token.sub('',text)
        if any(c in plain for c in '{}<>`\\') or quantity.search(plain):
            issue('protected_content',path+'.text')
        if prohibited.search(plain):
            issue('prohibited_claim',path+'.text')
        if comparison.search(plain):
            issue('unprotected_comparison',path+'.text')
        count=len(text.split())
        words+=count
        if count>max_words or len(text)>bounds['note_chars']:
            issue(length_rule,path+'.text',maximum=max_words)
        return tokens,valid_refs
    notes=parsed.get('notes')
    if not isinstance(notes,dict) or set(notes)!=set(NOTE_SECTIONS):
        issue('note_fields','notes',received_type=json_type(notes))
    for key in NOTE_SECTIONS:
        note=notes.get(key) if isinstance(notes,dict) else None
        path='notes.'+key
        if not isinstance(note,dict) or set(note)!={'text','evidence_ids'} or not isinstance(note.get('text'),str):
            if isinstance(notes,dict) and key in notes:
                issue('note_fields',path,received_type=json_type(note))
            continue
        if not note['text'].strip():
            if note['evidence_ids']!=[]:
                issue('evidence_references',path+'.evidence_ids',actual_count=len(note['evidence_ids'])
                    if isinstance(note['evidence_ids'],list) else None)
            continue
        check_text(note['text'],note['evidence_ids'],path,sections[key],bounds['note_words'],'note_length')
    questions=parsed.get('questions')
    if not isinstance(questions,list) or not bounds['question_min']<=len(questions)<=bounds['question_max']:
        issue('question_count','questions',received_type=json_type(questions) if 'questions' in parsed else 'missing',
            actual_count=len(questions) if isinstance(questions,list) else None,
            minimum=bounds['question_min'],maximum=bounds['question_max'])
    for index,question in enumerate(questions if isinstance(questions,list) else []):
        path=f'questions[{index}]'
        if not isinstance(question,dict) or set(question)!={'audience','text','evidence_ids'} or not isinstance(question.get('text'),str):
            issue('question_fields',path,received_type=json_type(question))
            continue
        text,refs,audience=question['text'],question['evidence_ids'],question['audience']
        _,valid_refs=check_text(text,refs,path,None,bounds['question_words'],'question_length')
        plain=token.sub('',text)
        if not text.endswith('?') or not re.match(r'^(?:Could|Can|Would|Has|Have|Is|Are|What|How|Do|Does)\b',text):
            issue('verification_question',path+'.text')
        if audience not in AUDIENCES or not valid_refs or not set(refs)&sections.get(audience,set()):
            issue('question_audience',path+'.audience')
        if valid_refs:
            for topic,identifiers in [('login|signing in',('login',)),('payment',('flow','failure','outbound')),
                    ('deposit|maturity',('fd_',)),('fees?|waivers?',('fee','waiver')),('balance',('balance',))]:
                if re.search(r'\b(?:'+topic+r')\w*\b',plain,re.I) and not any(any(i in r for i in identifiers) for r in refs):
                    issue('question_relevance',path+'.evidence_ids')
    if words>bounds['model_words']:
        issue('model_word_limit','$',maximum=bounds['model_words'])
    report['model_word_count']=words
    report['failure_count']=len(errors)
    if errors:
        return report,None
    return report,dict(notes=notes,questions=questions)


def synthetic_fixture(raw,evidence,token,report):
    """Reference/shape replay with invented prose/values; never persist provider prose."""
    safe_id=reference_labeler(evidence,token)
    replacement={}
    for key,fact in evidence['facts'].items():
        replacement[key]=dict(id=key,label='Synthetic fact',value=0,display='Synthetic value',
            clause='Synthetic recorded fact',kind=fact['kind'],direction=fact.get('direction'),
            group=fact.get('group'),units='synthetic',period={},meaning='Synthetic fixture only',
            eligible_for=['statement','question'])
    result=dict(blocks=[],questions=[])
    try:
        parsed=strict_json(raw)
    except ValidationError:
        parsed={}
    if isinstance(parsed,dict):
        for section in ['blocks','questions']:
            entries=parsed.get(section)
            if not isinstance(entries,list):
                result[section]=None if entries is None else 'synthetic_wrong_type'
                continue
            for entry in entries:
                if not isinstance(entry,dict):
                    result[section].append(None);continue
                item={}
                if 'kind' in entry:
                    item['kind']=entry['kind'] if entry['kind'] in KINDS else 'synthetic_unknown_kind'
                if 'text' in entry:
                    if isinstance(entry['text'],str):
                        placeholders=['{{'+safe_id(t)+'}}' for t in token.findall(entry['text'])]
                        item['text']=('Synthetic context. '+'. '.join(placeholders)+'.' if section=='blocks'
                            else 'Could we verify the recorded context?')
                    else:
                        item['text']=None
                if 'evidence_ids' in entry:
                    refs=entry['evidence_ids']
                    item['evidence_ids']=[safe_id(r) if isinstance(r,str) else {} for r in refs] if isinstance(refs,list) else None if refs is None else 'synthetic_wrong_type'
                if set(entry)-{'kind','text','evidence_ids'}:
                    item['synthetic_unknown_field']=None
                result[section].append(item)
    return dict(format='m6-synthetic-contract-replay-1',scope='References and structure; all prose/values replaced. Original prose-specific failures appear only as safe rule metadata.',
        evidence=dict(identity=dict(purpose=evidence['identity']['purpose'],cutoff='2000-01-31'),facts=replacement),
        output=result,captured_audit=report)


def save_synthetic_fixture(raw,evidence,token,report):
    import json
    import uuid
    from pathlib import Path
    destination=Path(__file__).resolve().parents[2]/'artifacts'/('m6-contract-capture-'+uuid.uuid4().hex+'.json')
    destination.parent.mkdir(parents=True,exist_ok=True)
    with destination.open('x',encoding='utf-8') as handle:
        json.dump(synthetic_fixture(raw,evidence,token,report),handle,indent=2)
    return str(destination)
