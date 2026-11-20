"""Purpose-specific output bounds shared by SDK schema, instructions and validation."""
from .validation import require, strict_json, ValidationError

CONTRACT_VERSION='m6-narrative-8'
REFERENCE_MIN=1
REFERENCE_MAX=4

LIMITS={
    # Summary (m6-narrative-5): the server writes every fact sentence; limits bound model-written text
    # (four section notes + questions). card_words bounds the whole rendered card.
    # Limits bound model-written text only. Card length comes from server sentences and is kept
    # short by tests on server output, never by rejecting AI text.
    # m6-narrative-6: one optional link note (2-3 facts from >=2 sections) and at most one question per audience.
    'summary':dict(question_min=0,question_max=2,link_words=25,link_chars=200,link_min_refs=2,link_max_refs=3,
        link_max_placeholders=3,link_min_connecting_words=4,question_words=25,question_chars=200,model_words=100),
    # m6-narrative-7: the on-demand purpose produces only 2-3 client-safe questions for the RM meeting.
    'discussion':dict(question_min=2,question_max=3,question_refs_max=3,question_words=30,question_chars=220),
}


def limits_for(purpose):
    require(purpose in LIMITS,'Unknown AI output purpose')
    return dict(LIMITS[purpose])


def reference_registry(evidence,payload=None):
    if payload is None:
        from .ai_evidence import external
        payload=external(evidence)
    registry={}
    if 'sections' in payload:  # Summary payload: facts are attached to the card's own sentences.
        listed=[fact for section in payload['sections'] for line in section['lines'] for fact in line['facts']]
    else:
        listed=payload['facts']
    for fact in listed:
        fact_id=fact['id']
        require(fact_id in evidence['facts'] and evidence['facts'][fact_id]['id']==fact_id
            and fact_id not in registry,'Provider evidence registry identity mismatch')
        require(fact['placeholder']=='{{'+fact_id+'}}' and fact['kind']==evidence['facts'][fact_id]['kind'],
            'Provider evidence placeholder/kind mismatch')
        registry[fact_id]=fact
    require(bool(registry),'Provider evidence registry is empty')
    return registry


AUDIENCES=['operations','finance']


def summary_schema(limits):
    def references():
        return dict(type='array',items=dict(type='string'))
    link=dict(type='object',additionalProperties=False,required=['text','evidence_ids'],properties={
        'text':dict(type='string'),'evidence_ids':references()})
    question=dict(type='object',additionalProperties=False,required=['audience','text','evidence_ids'],properties={
        'audience':dict(type='string',enum=list(AUDIENCES)),'text':dict(type='string'),'evidence_ids':references()})
    return dict(type='object',additionalProperties=False,required=['link','questions'],properties={
        'link':link,
        'questions':dict(type='array',minItems=limits['question_min'],maxItems=limits['question_max'],items=question)})


def client_schema(limits):
    question=dict(type='object',additionalProperties=False,required=['text','evidence_ids'],properties={
        'text':dict(type='string'),'evidence_ids':dict(type='array',items=dict(type='string'))})
    return dict(type='object',additionalProperties=False,required=['questions'],properties={
        'questions':dict(type='array',minItems=limits['question_min'],maxItems=limits['question_max'],items=question)})


def schema_for(purpose):
    """Provider schema describes shape only. Gemini rejects schemas whose constraints have
    'too many states' (long enums, nested array bounds), so known IDs, 1–4 reference counts
    and uniqueness are enforced by ai_output_audit (inspect_notes / inspect_client_questions), not here."""
    limits=limits_for(purpose)
    if purpose=='summary':
        return summary_schema(limits)
    require(purpose=='discussion','Unknown AI output purpose')
    return client_schema(limits)

def purpose_instruction(purpose):
    bounds=limits_for(purpose)
    if purpose=='summary':
        return ('Purpose: Customer Summary card for a monthly retention meeting, read by non-technical Operations and Finance staff. '
            'The server already writes every fact sentence shown in payload sections (bottom_line, operations, finance, weighed); '
            'the card alone is the main explanation. You may add ONE optional link.text: a single plain-English sentence (at most '+str(bounds['link_words'])+
            ' words) that says what connects '+str(bounds['link_min_refs'])+'–'+str(bounds['link_max_refs'])+' facts from at least two different sections. '
            'Never list fact names; return an empty string with [] when nothing genuinely links. '
            'The questions field must be a JSON array containing '+str(bounds['question_min'])+'–'+str(bounds['question_max'])+
            ' verification questions: at most one with audience operations and at most one with audience finance. '
            "Ask about the customer's situation or the bank's service, never for a value: the card already shows every value. "
            'Zero questions is valid: return [] when evidence is insufficient. '
            'Never invent or pad questions to meet a minimum. Shorter output is preferable when evidence is limited.')
    if purpose=='discussion':
        return ('Purpose: client questions for a relationship manager (RM) meeting or call with Customer A. '
            'Write '+str(bounds['question_min'])+'–'+str(bounds['question_max'])+' open, polite questions the RM can say directly to the client, '
            "about the client's business, how they pay and get paid, their use of online banking, their deposits or their fees. "
            'Each question is at most '+str(bounds['question_words'])+' words and uses a different topic. '
            'The client must never hear internal language: no model, estimate, risk, score, flag, threshold, churn, attrition, '
            'prediction, records or data, and never mention other banks or competitors. Never ask the client for numbers, counts '
            'or amounts, and never quote numbers, dates or the facts themselves. Do not presuppose a problem or its cause. '
            "Ask about the client's situation and experience; never offer reviews, discounts, waivers or changes to fees or terms.")
    require(False,'Unknown AI output purpose')

def reference_instruction(purpose='discussion'):
    if purpose=='discussion':
        return ('Reference contract: each question cites 1–3 unique bare fact IDs copied exactly from sections[].lines[].facts[].id '
            'in evidence_ids, for the RM to see why it was asked. Question text never contains placeholders, fact names or values.')
    if purpose=='summary':
        return ('Reference contract: to name a fact, write its placeholder exactly, e.g. {{prediction.risk}}; the card replaces it with the '
            "fact's name, never its value. Cite every placeholder you use in that item's evidence_ids: unique bare IDs copied exactly "
            'from sections[].lines[].facts[].id. A non-empty link cites 2–3 facts from at least two different sections; an empty link has '
            'evidence_ids []. A question cites '+str(REFERENCE_MIN)+'–'+str(REFERENCE_MAX)+' facts. An operations question must cite at least '
            'one operations fact, and a finance question at least one finance fact.')
    require(False,'Unknown AI output purpose')

def question_metadata(raw,purpose):
    bounds=limits_for(purpose)
    field_type='unavailable'
    count=None
    if isinstance(raw,str) and len(raw.encode())<=16000:
        try:
            parsed=strict_json(raw)
            if isinstance(parsed,dict):
                if 'questions' not in parsed:
                    field_type='missing'
                else:
                    questions=parsed['questions']
                    field_type=('array' if isinstance(questions,list) else 'object' if isinstance(questions,dict)
                        else 'null' if questions is None else 'boolean' if isinstance(questions,bool)
                        else 'string' if isinstance(questions,str) else 'number')
                    count=len(questions) if isinstance(questions,list) else None
        except ValidationError:
            pass
    return dict(purpose=purpose,questions_field_type=field_type,actual_count=count,
        permitted_minimum=bounds['question_min'],permitted_maximum=bounds['question_max'])
