"""All-rule, privacy-safe analysis of bounded narrative; no repairs or guessed links."""
import re
from . import ai_evidence
from .ai_contract import limits_for, REFERENCE_MIN, REFERENCE_MAX
from .validation import strict_json, ValidationError

MESSAGES={
 'output_size':'Oversized or empty AI output','malformed_json':'Invalid JSON','schema':'Invalid narrative schema',
 'question_count':'Invalid question count','evidence_references':'Unknown evidence references',
 'placeholder_reference':'Unlinked placeholder',
 'protected_content':'Unprotected quantity/date/markup','prohibited_claim':'Prohibited narrative claim',
 'unprotected_comparison':'Unprotected comparison',
 'verification_question':'Question must invite verification','question_relevance':'Question topic lacks relevant evidence',
 'unresolved_placeholder':'Unresolved placeholder',
 # Summary link/question contract (m6-narrative-6).
 'link_fields':'Invalid link fields','link_length':'AI link note exceeds bounded length',
 'link_sections':'Link note must connect at least two card sections','link_list_only':'Link note only lists facts',
 'question_fields':'Invalid question fields',
 'question_audience':'Question audience lacks matching evidence','question_length':'Question exceeds bounded length',
 'model_word_limit':'AI text exceeds bounded length',
 # Client questions (m6-narrative-7).
 'client_language':'Client question uses internal or competitor language','client_data_request':'Client question requests internal data',
 'client_offer':'Client question offers bank pricing or terms actions',
 # Both purposes (m6-narrative-9): cite only what the card's bottom line and activity tile show.
 'citation_scope':'Citation outside the allowed references',
}


def citation_scope(refs,allowed,lower):
    """Known IDs the item may not cite: outside the allowed set, and any lower-risk driver."""
    outside=[r for r in dict.fromkeys(refs) if r not in allowed]
    return dict(disallowed=outside,lower_risk=[r for r in outside if r in lower]) if outside else None


def lower_ids(evidence):
    return {prefix+d['feature'] for d in evidence['explanation']['lower_risk_drivers'] for prefix in ('feature.','signal.')}


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


def inspect_notes(raw,evidence,token,quantity,prohibited,comparison):
    """Summary contract (m6-narrative-6): one optional link note + at most one question per audience.
    The server renders every fact sentence; content, reference, question and length rules apply to
    everything the model wrote. A link must connect facts from different card sections, not list them."""
    from .ai_render import plan, section_ids, allowed_references
    from .ai_contract import AUDIENCES
    bounds=limits_for('summary')
    sections=section_ids(plan(evidence))
    allowed,lower=set(allowed_references(evidence)),lower_ids(evidence)
    known=set().union(*sections.values())
    section_of={fact_id:key for key,ids in sections.items() for fact_id in ids}
    safe_id=reference_labeler(evidence,token)
    errors=[]
    def issue(rule,path,**details):
        errors.append(dict(rule=rule,path=path,**details))
    report=dict(purpose='summary',expected_reference_structure='link: '+str(bounds['link_min_refs'])+'–'+str(bounds['link_max_refs'])+
        ' unique bare fact IDs from at least two card sections ([] when empty); questions: '+str(REFERENCE_MIN)+'–'+str(REFERENCE_MAX)+' IDs',
        supplied_fact_count=len(known),failures=errors)
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
    if set(parsed)!={'link','questions'}:
        issue('schema','$')
    words=0
    def content_rules(text,refs,path,minimum,maximum):
        nonlocal words
        tokens=token.findall(text)
        valid_refs=isinstance(refs,list) and all(isinstance(r,str) for r in refs)
        unknown=[safe_id(r) for r in refs if not isinstance(r,str) or r not in known] if isinstance(refs,list) else []
        if not (valid_refs and minimum<=len(refs)<=maximum and not unknown and len(set(refs))==len(refs)):
            issue('evidence_references',path+'.evidence_ids',received_type=json_type(refs),
                actual_count=len(refs) if isinstance(refs,list) else None,unknown_fact_ids=unknown,
                duplicate_references=valid_refs and len(set(refs))!=len(refs))
        elif (scope:=citation_scope(refs,allowed,lower)):
            issue('citation_scope',path+'.evidence_ids',**scope)
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
        words+=len(text.split())
        return tokens,valid_refs and not unknown
    link=parsed.get('link')
    if not isinstance(link,dict) or set(link)!={'text','evidence_ids'} or not isinstance(link.get('text'),str):
        issue('link_fields','link',received_type=json_type(link))
    elif not link['text'].strip():
        if link['evidence_ids']!=[]:
            issue('evidence_references','link.evidence_ids',actual_count=len(link['evidence_ids'])
                if isinstance(link['evidence_ids'],list) else None)
    else:
        text,refs=link['text'],link['evidence_ids']
        tokens,valid=content_rules(text,refs,'link',bounds['link_min_refs'],bounds['link_max_refs'])
        if len(text.split())>bounds['link_words'] or len(text)>bounds['link_chars']:
            issue('link_length','link.text',maximum=bounds['link_words'])
        if valid and len({section_of[r] for r in refs})<2:
            issue('link_sections','link.evidence_ids')
        # A list of fact names is not a link: too many placeholders, or placeholders with almost no connecting words.
        connecting=[w for w in re.findall(r"[A-Za-z][A-Za-z'-]*",token.sub(' ',text)) if w.lower() not in ('and','or')]
        if len(tokens)>bounds['link_max_placeholders'] or (len(tokens)>=2 and len(connecting)<bounds['link_min_connecting_words']):
            issue('link_list_only','link.text',placeholder_count=len(tokens),connecting_words=len(connecting))
    questions=parsed.get('questions')
    if not isinstance(questions,list) or not bounds['question_min']<=len(questions)<=bounds['question_max']:
        issue('question_count','questions',received_type=json_type(questions) if 'questions' in parsed else 'missing',
            actual_count=len(questions) if isinstance(questions,list) else None,
            minimum=bounds['question_min'],maximum=bounds['question_max'])
    seen=set()
    for index,question in enumerate(questions if isinstance(questions,list) else []):
        path=f'questions[{index}]'
        if not isinstance(question,dict) or set(question)!={'audience','text','evidence_ids'} or not isinstance(question.get('text'),str):
            issue('question_fields',path,received_type=json_type(question))
            continue
        text,refs,audience=question['text'],question['evidence_ids'],question['audience']
        _,valid_refs=content_rules(text,refs,path,REFERENCE_MIN,REFERENCE_MAX)
        if len(text.split())>bounds['question_words'] or len(text)>bounds['question_chars']:
            issue('question_length',path+'.text',maximum=bounds['question_words'])
        plain=token.sub('',text)
        # Summary questions ask about the situation or service, never for a value the card already shows.
        if not text.endswith('?') or not re.match(r'^(?:Has|Have|Is|Are|Could|Did|Does|Do|Can)\b',text):
            issue('verification_question',path+'.text')
        if audience not in AUDIENCES or audience in seen or not valid_refs or not set(refs)&sections.get(audience,set()):
            issue('question_audience',path+'.audience')
        seen.add(audience)
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
        kept=drop_unfit_items(errors,link,questions)
        if kept is None:
            return report,None
        report['dropped']=kept['dropped']
        return report,kept
    return report,dict(link=link,questions=questions)


# Item-level acceptance (summary only, 21 Nov 2026; citation_scope added in m6-narrative-9). These kinds of
# failure mean an optional item does not fit the card, not that the model wrote something unsafe: the
# failing item is dropped (never stored or shown) and every other item must have passed every rule.
LINK_FIT_RULES={'link_sections','link_list_only','link_length','citation_scope'}
QUESTION_FIT_RULES={'question_relevance','citation_scope'}  # citation_scope: m6-narrative-9 (27 Nov 2026).
QUESTION_FIT=re.compile(r'questions\[(\d+)\]\.evidence_ids')


def drop_unfit_items(errors,link,questions):
    """Returns the kept items plus rule IDs of what was dropped, or None for whole-draft rejection:
    any other rule on any item (safety, references, audience, schema, word limit) rejects the whole draft,
    and so does a draft with nothing left after dropping."""
    dropped_link,dropped_questions=[],{}
    for error in errors:
        match=QUESTION_FIT.fullmatch(error['path'])
        if error['rule'] in LINK_FIT_RULES and error['path'].startswith('link'):
            dropped_link.append(error['rule'])
        elif error['rule'] in QUESTION_FIT_RULES and match:
            dropped_questions.setdefault(int(match[1]),[]).append(error['rule'])
        else:
            return None
    kept_link=dict(text='',evidence_ids=[]) if dropped_link else link
    kept_questions=[q for index,q in enumerate(questions) if index not in dropped_questions]
    if not kept_link['text'].strip() and not kept_questions:
        return None  # Nothing valid remains: a full fallback, not an empty Gemini draft.
    dropped=([dict(item='link',rules=sorted(set(dropped_link)))] if dropped_link else [])+[
        dict(item=f'question:{index}/{questions[index]["audience"]}',rules=sorted(set(rules)))
        for index,rules in sorted(dropped_questions.items())]
    return dict(link=kept_link,questions=kept_questions,dropped=dropped)


# Words a client must never hear from the RM (internal model language, internal records, other banks).
CLIENT_BANNED = re.compile(r"\b(?:model\w*|estimat\w*|risk\w*|scor\w*|flag\w*|threshold\w*|churn\w*|attrition|predict\w*|"
    r"recorded|records?|data|other banks?|another bank|competitor\w*|switch\w*)\b", re.I)
# Requests for internal figures: "how many/much ...", or "what is/are ... rate/number/count/amount/balance/total/level/percentage".
CLIENT_DATA_REQUEST = re.compile(r"\bhow (?:many|much)\b|^what (?:is|are|was|were) (?:the|your)\b[^?]*"
    r"\b(?:rates?|numbers?|counts?|amounts?|balances?|totals?|levels?|percentages?)\b", re.I)
# Offers of bank actions on pricing or terms commit the bank to a conversation the committee decides:
# "Would you like (us) to review/reduce/waive/...", "Can we lower ...", or discount/rebate/waive wording.
CLIENT_OFFER = re.compile(r"\b(?:would you like|do you want|shall we|can we|could we|may we|should we)\b(?:\s+[\w']+){0,4}?\s+"
    r"(?:review|reduce|waive|discount|lower|change|adjust|revise|renegotiate|reprice|match)\b"
    r"|\b(?:discount\w*|rebate\w*|waive|waived|waiving|reduce your fees?|lower your fees?|fee reductions?)\b", re.I)
CLIENT_OPENING = re.compile(r'^(?:Has|Have|Is|Are|Could|Can|Would|Did|Does|Do|What|How)\b')


def inspect_client_questions(raw,evidence,token,quantity,prohibited,comparison):
    """Client questions (m6-narrative-7): 2-3 open questions the RM can ask the client directly.
    Existing content rules apply, plus client-safe language and no requests for internal data.
    Open What/How questions are allowed, unlike internal summary questions."""
    from .ai_render import plan, section_ids, allowed_references
    bounds=limits_for('discussion')
    known=set().union(*section_ids(plan(evidence)).values())
    allowed,lower=set(allowed_references(evidence)),lower_ids(evidence)
    safe_id=reference_labeler(evidence,token)
    errors=[]
    def issue(rule,path,**details):
        errors.append(dict(rule=rule,path=path,**details))
    report=dict(purpose='discussion',expected_reference_structure='questions: 1–'+str(bounds['question_refs_max'])+
        ' unique bare fact IDs each; no placeholders in question text',supplied_fact_count=len(known),failures=errors)
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
    if set(parsed)!={'questions'}:
        issue('schema','$')
    questions=parsed.get('questions')
    if not isinstance(questions,list) or not bounds['question_min']<=len(questions)<=bounds['question_max']:
        issue('question_count','questions',received_type=json_type(questions) if 'questions' in parsed else 'missing',
            actual_count=len(questions) if isinstance(questions,list) else None,
            minimum=bounds['question_min'],maximum=bounds['question_max'])
    for index,question in enumerate(questions if isinstance(questions,list) else []):
        path=f'questions[{index}]'
        if not isinstance(question,dict) or set(question)!={'text','evidence_ids'} or not isinstance(question.get('text'),str):
            issue('question_fields',path,received_type=json_type(question))
            continue
        text,refs=question['text'],question['evidence_ids']
        valid_refs=isinstance(refs,list) and all(isinstance(r,str) for r in refs)
        unknown=[safe_id(r) for r in refs if not isinstance(r,str) or r not in known] if isinstance(refs,list) else []
        if not (valid_refs and 1<=len(refs)<=bounds['question_refs_max'] and not unknown and len(set(refs))==len(refs)):
            issue('evidence_references',path+'.evidence_ids',received_type=json_type(refs),
                actual_count=len(refs) if isinstance(refs,list) else None,unknown_fact_ids=unknown,
                duplicate_references=valid_refs and len(set(refs))!=len(refs))
        elif (scope:=citation_scope(refs,allowed,lower)):
            issue('citation_scope',path+'.evidence_ids',**scope)  # Discussion: any failure is a whole fallback.
        if token.search(text):
            issue('client_language',path+'.text',reason='placeholder')  # Placeholders resolve to internal metric names.
        plain=token.sub('',text)
        if any(c in plain for c in '{}<>`\\') or quantity.search(plain):
            issue('protected_content',path+'.text')
        if prohibited.search(plain):
            issue('prohibited_claim',path+'.text')
        if comparison.search(plain):
            issue('unprotected_comparison',path+'.text')
        if CLIENT_BANNED.search(plain):
            issue('client_language',path+'.text')
        if CLIENT_DATA_REQUEST.search(plain):
            issue('client_data_request',path+'.text')
        if CLIENT_OFFER.search(plain):
            issue('client_offer',path+'.text')
        if not text.endswith('?') or not CLIENT_OPENING.match(text):
            issue('verification_question',path+'.text')
        if len(text.split())>bounds['question_words'] or len(text)>bounds['question_chars']:
            issue('question_length',path+'.text',maximum=bounds['question_words'])
    report['failure_count']=len(errors)
    if errors:
        return report,None
    return report,dict(questions=questions)


def synthetic_fixture(raw,evidence,token,report):
    """Structure-only fixture for the link/question contracts: all prose, references and bank values are
    replaced; rule metadata is kept. No offline replay (the validators need the real saved evidence)."""
    safe_id=reference_labeler(evidence,token)
    def item(entry):
        if not isinstance(entry,dict):
            return None
        result={}
        for key,value in entry.items():
            if key=='text':
                result['text']='Could we verify the recorded context?' if isinstance(value,str) else None
            elif key=='evidence_ids':
                result['evidence_ids']=[safe_id(r) if isinstance(r,str) else {} for r in value] if isinstance(value,list) else 'synthetic_wrong_type'
            elif key=='audience':
                result['audience']=value if value in ('operations','finance') else 'synthetic_unknown_audience'
            else:
                result['synthetic_unknown_field']=None
        return result
    try:
        parsed=strict_json(raw)
    except ValidationError:
        parsed={}
    output={}
    for key,value in (parsed.items() if isinstance(parsed,dict) else []):
        if key in ('link','questions'):
            output[key]=[item(entry) for entry in value] if isinstance(value,list) else item(value)
        else:
            output['synthetic_unknown_field']=None
    return dict(format='m6-synthetic-contract-structure-2',scope='Structure and safe reference labels only; all prose and values replaced.',
        purpose=evidence['identity']['purpose'],output=output,captured_audit=report)


def save_synthetic_fixture(raw,evidence,token,report):
    import json
    import uuid
    from pathlib import Path
    destination=Path(__file__).resolve().parents[2]/'artifacts'/('m6-contract-capture-'+uuid.uuid4().hex+'.json')
    destination.parent.mkdir(parents=True,exist_ok=True)
    with destination.open('x',encoding='utf-8') as handle:
        json.dump(synthetic_fixture(raw,evidence,token,report),handle,indent=2)
    return str(destination)
