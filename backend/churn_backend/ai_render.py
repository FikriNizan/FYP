"""Server-rendered summary card for the monthly retention meeting.

The server writes every fact sentence from saved evidence, in fixed sections. Gemini may add one
short note per section and audience-tagged questions; a {{fact}} placeholder in its text resolves to
the fact's plain NAME only, never its value. Ranking uses only this customer's saved SHAP drivers:
a fact is "notable" when its feature is among the saved higher/lower risk drivers. No thresholds.
"""
import re
from datetime import date
from . import briefings
from .ai_evidence import DICTIONARY

VERSION = 'render-1'
TOKEN = re.compile(r'\{\{([a-zA-Z0-9_.]+)\}\}')
NOTE_SECTIONS = ('bottom_line', 'operations', 'finance', 'weighed')
TITLES = dict(bottom_line='Bottom line', operations='Operations: what is happening',
              finance='Finance: what is at stake', weighed='What the model weighed', closing='Decision')
FRICTION = ('login_failure_rate_3m', 'outbound_failure_rate_3m', 'outbound_bank_failure_rate_3m', 'passive_session_rate_3m')
PLAIN_NAMES = {'prediction.risk': 'the estimated risk', 'prediction.threshold': 'the review threshold',
               'prediction.flag': 'the review flag'}
NOT_NOTABLE = 'None of the service or online-banking measures are among the main signals for this estimate.'
WEIGHED_NOTE = 'These are signals the model weighed, not proven causes.'
CLOSING = "Prioritisation is the committee's decision."
SERVICE_CLOSING = 'Service issues can be checked and fixed independently of the outreach decision.'
QUESTION_LIMIT = 3
BASE_CHECKS = ['saved_prediction_identity', 'shap_reconstruction_2e-10', 'raw_calibration_2e-10', 'deterministic_formatting']
AI_CHECKS = ['known_references', 'section_references', 'numeric_date_rules', 'interpretation_rules', 'note_bounds']


def day(value):
    parsed = date.fromisoformat(value[:10])
    return f'{parsed.day} {parsed:%b %Y}'


def span(period):
    start, end = date.fromisoformat(period['start']), date.fromisoformat(period['end'])
    return f'{start:%b}–{end:%b %Y}' if start.year == end.year else f'{start:%b %Y}–{end:%b %Y}'


def name(fact_id, facts):
    return PLAIN_NAMES.get(fact_id) or facts[fact_id]['label'].lower()


def resolve(text, facts):
    text = TOKEN.sub(lambda match: name(match[1], facts), text)
    return text[:1].upper() + text[1:]


def weights(evidence):
    saved = evidence['explanation']
    return {d['feature']: d['contribution_logodds'] for d in saved['higher_risk_drivers'] + saved['lower_risk_drivers']}


def line(text, ids, features=(), source='evidence'):
    return dict(text=text, ids=list(ids), features=list(features), source=source)


def ranked(lines, w):
    """Notable lines first by |saved contribution|, then the rest in fixed dictionary order."""
    def weight(item):
        return max((abs(w[f]) for f in item['features'] if f in w), default=None)
    notable = sorted((l for l in lines if weight(l) is not None), key=lambda l: -weight(l))
    return notable, [l for l in lines if weight(l) is None]


def operations(evidence, w):
    facts, cutoff = evidence['facts'], day(evidence['identity']['cutoff'])
    def get(feature):
        return facts.get('feature.' + feature)
    lines = []
    for feature, template in [('login_failure_rate_3m', '{p} of login attempts failed ({period}).'),
                              ('outbound_failure_rate_3m', '{p} of outgoing payments failed ({period}).'),
                              ('outbound_bank_failure_rate_3m', '{p} of outgoing payments failed for bank-side reasons ({period}).'),
                              ('passive_session_rate_3m', '{p} of online banking sessions had no transaction ({period}).')]:
        fact = get(feature)
        if fact:
            lines.append(line(template.format(p=briefings.percent(fact['value'], 1), period=span(fact['period'])), [fact['id']], [feature]))
    context = []
    for recency, noun, short, long in [('outbound_success_recency_days', 'outgoing payment', 'outbound_count_mean_3m', 'outbound_count_mean_12m'),
                                       ('login_success_recency_days', 'login', 'login_success_count_mean_3m', 'login_success_count_mean_12m')]:
        fact = get(recency)
        if fact:
            days = f'{fact["value"]:,.0f}'
            context.append(line(f'Last successful {noun}: {days} day{"" if days == "1" else "s"} before {cutoff}.', [fact['id']], [recency]))
        a, b = get(short), get(long)
        label = 'Successful outgoing payments' if noun == 'outgoing payment' else 'Successful logins'
        if a and b:
            trend = 'lower' if a['value'] < b['value'] else 'higher' if a['value'] > b['value'] else 'the same'
            context.append(line(f'{label}: {a["value"]:,.1f} a month on average in {span(a["period"])}, compared with '
                                f'{b["value"]:,.1f} over the 12 months to {cutoff} ({trend}).', [a['id'], b['id']], [short, long]))
        elif a or b:
            only = a or b
            context.append(line(f'{label}: {only["value"]:,.1f} a month on average in {span(only["period"])}.', [only['id']],
                                [short if a else long]))
    notable, rest = ranked(lines + context, w)
    if notable:
        return (notable + rest)[:3]
    return [line(NOT_NOTABLE, [], source='standard')] + [l for l in context][:2]


def finance(evidence, w):
    facts = evidence['facts']
    def get(feature):
        return facts.get('feature.' + feature)
    trend = []
    ratio = get('combined_flow_ratio_3m_to_12m')
    if ratio:
        r = ratio['value']
        change = 'unchanged' if r == 1 else f'{briefings.percent(abs(1 - r), 2)} {"lower" if r < 1 else "higher"}'
        trend.append(line(f'Average monthly transaction value in {span(ratio["period"])} was {briefings.percent(r, 2)} of its '
                          f'12-month average (which includes these 3 months): {change}.', [ratio['id']], ['combined_flow_ratio_3m_to_12m']))
    lines = []
    for feature, noun in [('inbound_flow_ratio_3m_to_12m', 'incoming'), ('outbound_flow_ratio_3m_to_12m', 'outgoing')]:
        fact = get(feature)
        if fact:
            lines.append(line(f'Average monthly {noun} payments in {span(fact["period"])} were {briefings.percent(fact["value"], 2)} '
                              f'of their 12-month average (which includes these 3 months).', [fact['id']], [feature]))
    operating = get('non_fd_balance_myr')
    if operating:
        lines.append(line(f'Operating account balances on {day(operating["period"]["as_of"])}: {briefings.money(operating["value"])}.',
                          [operating['id']], ['non_fd_balance_myr']))
    deposit, maturing = get('fd_balance_myr'), get('fd_maturing_30d_count')
    if deposit or maturing:  # One deposit sentence keeps the Finance section short.
        when = day((deposit or maturing)['period']['as_of'])
        parts = [f'Fixed deposit balances on {when}: {briefings.money(deposit["value"])}'] if deposit else []
        if maturing:
            n = int(maturing['value'])
            due = ('no fixed deposits are due to mature within 30 days' if n == 0 else
                   f'{n} fixed deposit{" is" if n == 1 else "s are"} due to mature within 30 days')
            parts.append(due if deposit else f'{due[:1].upper()}{due[1:]} of {when}')
        lines.append(line('; '.join(parts) + '.', [f['id'] for f in (deposit, maturing) if f], ['fd_balance_myr', 'fd_maturing_30d_count']))
    fee, waiver = get('estimated_fee_mean_3m_myr'), get('estimated_waiver_mean_3m_myr')
    if fee or waiver:
        parts = []
        if fee:
            parts.append(f'estimated fees averaged {briefings.money(fee["value"])} a month ({span(fee["period"])})')
        if waiver:
            parts.append(f'estimated waivers averaged {briefings.money(waiver["value"])} a month')
        text = '; '.join(parts)
        lines.append(line(text[0].upper() + text[1:] + '. These are historical estimates, not profit.',
                          [f['id'] for f in (fee, waiver) if f], ['estimated_fee_mean_3m_myr', 'estimated_waiver_mean_3m_myr']))
    notable, rest = ranked(lines, w)
    return (trend + notable + rest)[:6]


def bottom_line(evidence):
    facts, saved = evidence['facts'], evidence['explanation']
    lines = []
    risk = facts.get('prediction.risk')
    if risk:
        lines.append(line('Estimated chance that average monthly transaction value over '
                          f'{briefings.forecast(evidence["identity"]["cutoff"])} falls to half or less of its 12-month average: '
                          f'{briefings.percent(risk["value"], 1)}.', ['prediction.risk']))
    flag, threshold = facts.get('prediction.flag'), facts.get('prediction.threshold')
    if flag and threshold:
        t = briefings.percent(threshold['value'], 1)
        text = (f'Flagged for committee review: the estimate is at or above the {t} review threshold.' if flag['value']
                else f'Not flagged: the estimate is below the {t} review threshold.')
        lines.append(line(text, ['prediction.flag', 'prediction.threshold']))
    if saved['higher_risk_drivers']:
        top = max(saved['higher_risk_drivers'], key=lambda d: d['contribution_logodds'])
        if top['feature'] in DICTIONARY:
            family = ('service and online-banking measures' if DICTIONARY[top['feature']][1] == 'Operations'
                      else 'transaction value and balance measures')
        else:
            family = (top.get('group') or 'other').lower() + ' measures'
        lines.append(line(f'The strongest signals for this estimate concern {family}.', []))
    usual = facts.get('feature.combined_flow_mean_12m_myr')
    if usual:
        lines.append(line(f'Usual monthly transaction value (12-month average): {briefings.money(usual["value"])}.', [usual['id']]))
    return lines


def weighed(evidence):
    saved, facts = evidence['explanation'], evidence['facts']
    drivers = sorted(saved['higher_risk_drivers'] + saved['lower_risk_drivers'], key=lambda d: -abs(d['contribution_logodds']))[:3]
    lines = []
    for driver in drivers:
        feature = driver['feature']
        label = DICTIONARY[feature][0] if feature in DICTIONARY else briefings.driver_label(driver)
        direction = 'higher' if driver['contribution_logodds'] > 0 else 'lower'
        signal = 'signal.' + feature
        lines.append(line(f'{label}: weighed toward {direction} risk.', [signal] if signal in facts else [], [feature]))
    if lines:
        lines.append(line(WEIGHED_NOTE, [], source='standard'))
    return lines


def plan(evidence):
    w = weights(evidence)
    return dict(bottom_line=bottom_line(evidence), operations=operations(evidence, w),
                finance=finance(evidence, w), weighed=weighed(evidence))


def section_ids(card_plan):
    return {key: {i for l in lines for i in l['ids']} for key, lines in card_plan.items()}


def service_issue(evidence):
    return any(d['feature'] in FRICTION and d['contribution_logodds'] > 0 for d in evidence['explanation']['higher_risk_drivers'])


def templates(evidence, card_plan):
    facts, ids = evidence['facts'], section_ids(card_plan)
    result = []
    if ids['operations']:
        friction = [d['feature'] for d in sorted(evidence['explanation']['higher_risk_drivers'], key=lambda d: -d['contribution_logodds'])
                    if d['feature'] in FRICTION and 'feature.' + d['feature'] in ids['operations']]
        if friction:
            text = (f'Could Operations check whether the recorded {DICTIONARY[friction[0]][0].lower()} point to a '
                    'service problem that can be fixed?')
            cited = ['feature.' + friction[0]]
        else:
            text = ("Could Operations confirm whether the customer's recent online-banking and payment activity "
                    'matches what the relationship team expects?')
            cited = sorted(ids['operations'])[:1]
        result.append(dict(audience='operations', text=text, source='template', evidence_ids=cited))
    if ids['finance']:
        trend = 'feature.combined_flow_ratio_3m_to_12m'
        result.append(dict(audience='finance', source='template', evidence_ids=[trend] if trend in ids['finance'] else sorted(ids['finance'])[:1],
                           text='Could Finance confirm what the recent change in transaction value means for the balances and fees recorded for this customer?'))
    return result


def render_summary(evidence, notes=None, questions=None):
    """Same sections with or without AI text; with none it is the deterministic fallback card."""
    facts, card_plan = evidence['facts'], plan(evidence)
    sections = []
    for key in NOTE_SECTIONS:
        items = [dict(text=l['text'], source=l['source'], evidence_ids=l['ids']) for l in card_plan[key]]
        note = (notes or {}).get(key)
        if note and note['text'].strip():
            items.append(dict(text=resolve(note['text'], facts), source='ai', evidence_ids=list(note['evidence_ids'])))
        sections.append(dict(id=key, title=TITLES[key], items=items))
    asked = [dict(audience=q['audience'], text=resolve(q['text'], facts), source='ai', evidence_ids=list(q['evidence_ids']))
             for q in questions or []]
    for template in templates(evidence, card_plan):
        if len(asked) < QUESTION_LIMIT and not any(q['audience'] == template['audience'] for q in asked):
            asked.append(template)
    closing = [CLOSING] + ([SERVICE_CLOSING] if service_issue(evidence) else [])
    sections.append(dict(id='closing', title=TITLES['closing'],
                         items=[dict(text=text, source='standard', evidence_ids=[]) for text in closing]))
    cited = {i for s in sections for item in s['items'] for i in item['evidence_ids']} | {i for q in asked for i in q['evidence_ids']}
    ai_used = notes is not None or questions is not None
    return dict(format='sections-1', sections=sections, questions=asked, evidence_ids=sorted(cited),
                checks=BASE_CHECKS + (AI_CHECKS if ai_used else []))


def card_words(content):
    return (sum(len(item['text'].split()) for s in content['sections'] for item in s['items'])
            + sum(len(q['text'].split()) for q in content['questions']))


def provider_payload(evidence):
    """What Gemini sees: the card's own sentences per section, with citable fact names. No identifiers."""
    facts, card_plan = evidence['facts'], plan(evidence)
    sections = []
    for key in NOTE_SECTIONS:
        sections.append(dict(section=key, title=TITLES[key], lines=[dict(sentence=l['text'], facts=[
            dict(id=i, placeholder='{{' + i + '}}', name=name(i, facts), kind=facts[i]['kind'],
                 direction=facts[i].get('direction'), group=facts[i].get('group')) for i in l['ids']]) for l in card_plan[key]]))
    return dict(customer='Customer A', purpose='summary', cutoff=evidence['identity']['cutoff'], sections=sections,
                limits='Signals show what the estimate weighed, not causes. Balances are exposures; fees and waivers are '
                       "historical estimates, not profit. Prioritisation is the committee's decision.")
