"""Purpose-specific output bounds shared by SDK schema, instructions and validation."""
from .validation import require, strict_json, ValidationError

CONTRACT_VERSION='m6-narrative-3'
KINDS=['recorded_observation','model_signal','recorded_committee_context']
REFERENCE_MIN=1
REFERENCE_MAX=4

LIMITS={
    'summary':dict(block_min=1,block_max=4,question_min=0,question_max=3,word_max=220),
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
    for fact in payload['facts']:
        fact_id=fact['id']
        require(fact_id in evidence['facts'] and evidence['facts'][fact_id]['id']==fact_id
            and fact_id not in registry,'Provider evidence registry identity mismatch')
        require(fact['placeholder']=='{{'+fact_id+'}}' and fact['kind']==evidence['facts'][fact_id]['kind'],
            'Provider evidence placeholder/kind mismatch')
        registry[fact_id]=fact
    require(bool(registry),'Provider evidence registry is empty')
    return registry


def schema_for(purpose,allowed_ids=None):
    limits=limits_for(purpose)
    def references():
        items=dict(type='string')
        if allowed_ids is not None:
            require(bool(allowed_ids) and all(isinstance(key,str) for key in allowed_ids),'Invalid provider reference allowlist')
            items['enum']=sorted(set(allowed_ids))
        return dict(type='array',minItems=REFERENCE_MIN,maxItems=REFERENCE_MAX,items=items)
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
        introduction='Purpose: Customer Summary. Write a short paragraph and at most three useful points; aim for 80–130 narrative words.'
    else:
        introduction='Purpose: RM discussion draft. Write a short discussion outline; aim for 120–200 narrative words.'
    return (introduction+' Return '+str(bounds['block_min'])+'–'+str(bounds['block_max'])+' factual blocks. '
        'The questions field must be a JSON array containing '+str(bounds['question_min'])+'–'+str(bounds['question_max'])+
        ' verification questions. Zero questions is valid: return [] when evidence is insufficient. '
        'Never invent or pad questions to meet a minimum. Shorter output is preferable when evidence is limited.')


def reference_instruction():
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
