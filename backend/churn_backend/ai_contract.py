"""Purpose-specific output bounds shared by SDK schema, instructions and validation."""
from .validation import require, strict_json, ValidationError

CONTRACT_VERSION='m6-narrative-5'
KINDS=['recorded_observation','model_signal','recorded_committee_context']
REFERENCE_MIN=1
REFERENCE_MAX=4

LIMITS={
    # Summary (m6-narrative-5): the server writes every fact sentence; limits bound model-written text
    # (four section notes + questions). card_words bounds the whole rendered card.
    # Measured: a full-data fallback card is ~250 words, so model text gets ~100 words and the
    # rendered card (incl. any template questions) is checked against card_words after rendering.
    'summary':dict(question_min=0,question_max=3,note_words=25,note_chars=200,question_words=25,model_words=100,card_words=320),
    'discussion':dict(block_min=1,block_max=6,question_min=0,question_max=5,word_max=340),
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


NOTE_SECTIONS=['bottom_line','operations','finance','weighed']
AUDIENCES=['operations','finance']


def summary_schema(limits):
    def references():
        return dict(type='array',items=dict(type='string'))
    note=dict(type='object',additionalProperties=False,required=['text','evidence_ids'],properties={
        'text':dict(type='string'),'evidence_ids':references()})
    question=dict(type='object',additionalProperties=False,required=['audience','text','evidence_ids'],properties={
        'audience':dict(type='string',enum=list(AUDIENCES)),'text':dict(type='string'),'evidence_ids':references()})
    return dict(type='object',additionalProperties=False,required=['notes','questions'],properties={
        'notes':dict(type='object',additionalProperties=False,required=list(NOTE_SECTIONS),
            properties={key:dict(note) for key in NOTE_SECTIONS}),
        'questions':dict(type='array',minItems=limits['question_min'],maxItems=limits['question_max'],items=question)})


def schema_for(purpose):
    """Provider schema describes shape only. Gemini rejects schemas whose constraints have
    'too many states' (long enums, nested array bounds), so known IDs, 1–4 reference counts
    and uniqueness are enforced by ai_output_audit.inspect_output, not here."""
    limits=limits_for(purpose)
    if purpose=='summary':
        return summary_schema(limits)
    def references():
        return dict(type='array',items=dict(type='string'))
    block=dict(type='object',additionalProperties=False,required=['kind','text','evidence_ids'],properties={
        'kind':dict(type='string',enum=list(KINDS)),'text':dict(type='string'),'evidence_ids':references()})
    question=dict(type='object',additionalProperties=False,required=['text','evidence_ids'],properties={
        'text':dict(type='string'),'evidence_ids':references()})
    return dict(type='object',additionalProperties=False,required=['blocks','questions'],properties={
        'blocks':dict(type='array',minItems=limits['block_min'],maxItems=limits['block_max'],items=block),
        'questions':dict(type='array',minItems=limits['question_min'],maxItems=limits['question_max'],items=question)})


def purpose_instruction(purpose):
    bounds=limits_for(purpose)
    if purpose=='summary':
        return ('Purpose: Customer Summary card for a monthly retention meeting, read by non-technical Operations and Finance staff. '
            'The server already writes every fact sentence shown in payload sections (bottom_line, operations, finance, weighed). '
            'For each section you may write notes.<section>.text: at most one short plain-English sentence (at most '+str(bounds['note_words'])+
            " words) that helps the reader connect that section's facts, or an empty string with [] when there is nothing useful to add. "
            'The questions field must be a JSON array containing '+str(bounds['question_min'])+'–'+str(bounds['question_max'])+
            ' verification questions, each with audience operations or finance: internal checks staff could make before deciding. '
            'Zero questions is valid: return [] when evidence is insufficient. '
            'Never invent or pad questions to meet a minimum. Shorter output is preferable when evidence is limited.')
    else:
        introduction='Purpose: RM discussion draft. Write a short discussion outline; aim for 120–200 narrative words.'
    return (introduction+' Return '+str(bounds['block_min'])+'–'+str(bounds['block_max'])+' factual blocks. '
        'The questions field must be a JSON array containing '+str(bounds['question_min'])+'–'+str(bounds['question_max'])+
        ' verification questions. Zero questions is valid: return [] when evidence is insufficient. '
        'Never invent or pad questions to meet a minimum. Shorter output is preferable when evidence is limited.')


def reference_instruction(purpose='discussion'):
    if purpose=='summary':
        return ('Reference contract: to name a fact, write its placeholder exactly, e.g. {{prediction.risk}}; the card replaces it with the '
            "fact's name, never its value. Cite every placeholder you use in that item's evidence_ids: "+str(REFERENCE_MIN)+'–'+str(REFERENCE_MAX)+
            ' unique bare IDs copied exactly from sections[].lines[].facts[].id. An empty note has evidence_ids []. '
            'A note may cite only facts from its own section. An operations question must cite at least one operations fact, '
            'and a finance question at least one finance fact.')
    return ('Reference transport contract: every evidence_ids field is an array of '+str(REFERENCE_MIN)+'–'+str(REFERENCE_MAX)+
        ' unique strings copied EXACTLY from facts[].id. Use bare IDs there, never labels, IDs from another purpose, '
        'or {{placeholder}} strings. In text, use facts[].placeholder exactly, as a complete independent clause. '
        'Example transport only: {"kind":"recorded_observation","text":"{{prediction.risk}}.",'
        '"evidence_ids":["prediction.risk"]}. Each factual block may cite only facts with the same kind as that block; '
        'a model_signal block must use signal IDs, not feature observation IDs. Cite all placeholders used in the block. '
        'Do not cite extra facts absent from its text. Questions may cite known relevant fact IDs without repeating their values. '
        'The example shows syntax, not required wording or a required topic.')


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
