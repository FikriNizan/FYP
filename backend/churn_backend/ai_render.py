"""Server-rendered summary card for the monthly retention meeting.

The server writes every fact sentence from saved evidence, in fixed sections. Gemini may add one
short note per section and audience-tagged questions; a {{fact}} placeholder in its text resolves to
the fact's plain NAME only, never its value. Ranking uses only this customer's saved SHAP drivers:
a fact is "notable" when its feature is among the saved higher/lower risk drivers. No thresholds.
"""
import re
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from . import briefings
from .ai_evidence import DICTIONARY, period

VERSION = 'render-10'  # render-5: Finance 'contribution at stake' sentence (RaR/FSL); render-6: stage-2 wording;
                      # render-7: check B owner rule (2026-11-22) and 'Combined flow' terminology;
                      # render-8: FD earnings net of SRR (2026-11-23) and check B 'fixed deposits' wording;
                      # render-9: plain bottom line (likelihood, threshold meaning, top-3 signals, rounded usual flow,
                      # dated footnote) and 'Based on' for summary questions (2026-11-27);
                      # render-10: semicolons in the top-3 signals list when a label contains a comma (2026-11-27).
TOKEN = re.compile(r'\{\{([a-zA-Z0-9_.]+)\}\}')
CARD_SECTIONS = ('bottom_line', 'operations', 'finance', 'weighed')
AUDIENCE_ORDER = ('operations', 'finance')
TITLES = dict(bottom_line='Bottom line', link='What links these signals', operations='Operations: what is happening',
              finance='Finance: what is at stake', weighed='What the model weighed', closing='Decision')
FRICTION = ('login_failure_rate_3m', 'outbound_failure_rate_3m', 'outbound_bank_failure_rate_3m', 'passive_session_rate_3m')
PLAIN_NAMES = {'prediction.risk': 'the estimated risk', 'prediction.threshold': 'the review threshold',
               'prediction.flag': 'the review flag'}
NOT_NOTABLE = 'None of the service or online-banking measures are among the main signals for this estimate.'
WEIGHED_NOTE = 'Signals the model weighed, not proven causes.'
CLOSING = "Prioritisation is the committee's decision."
SERVICE_CLOSING = 'Service issues can be checked and fixed independently of the outreach decision.'
QUESTION_LIMIT = 2  # Exactly one Operations and one Finance question when evidence allows.
BASE_CHECKS = ['saved_prediction_identity', 'shap_reconstruction_2e-10', 'raw_calibration_2e-10', 'deterministic_formatting']
AI_CHECKS = ['known_references', 'link_rules', 'question_rules', 'numeric_date_rules', 'interpretation_rules']


# Plain driver labels for every predictor (2-5 words, no values). Meanings follow the research
# project's data/features_v1/feature_dictionary.csv and, where its definition is generic, the actual
# computation in feature_engineering_v1.py (both read-only sources). inbound = "collections",
# outbound = "payments", combined = "combined flow".
DRIVER_LABELS = {
    'inbound_flow_mean_1m_myr': 'Collections, latest month',
    'inbound_flow_mean_3m_myr': 'Collections, 3-month average',
    'inbound_flow_mean_6m_myr': 'Collections, 6-month average',
    'inbound_flow_mean_12m_myr': 'Collections, 12-month average',
    'inbound_flow_change_3m_vs_previous_3m': 'Collections, quarter-on-quarter change',
    'inbound_flow_ratio_3m_to_12m': 'Collections vs 12-month average',
    'inbound_flow_cv_12m': 'Collection variability, 12 months',
    'inbound_zero_months_3m': 'Months without collections',
    'outbound_flow_mean_1m_myr': 'Payments, latest month',
    'outbound_flow_mean_3m_myr': 'Payments, 3-month average',
    'outbound_flow_mean_6m_myr': 'Payments, 6-month average',
    'outbound_flow_mean_12m_myr': 'Payments, 12-month average',
    'outbound_flow_change_3m_vs_previous_3m': 'Payments, quarter-on-quarter change',
    'outbound_flow_ratio_3m_to_12m': 'Payments vs 12-month average',
    'outbound_flow_cv_12m': 'Payment variability, 12 months',
    'outbound_zero_months_3m': 'Months without payments',
    'combined_flow_mean_1m_myr': 'Combined flow, latest month',
    'combined_flow_mean_3m_myr': 'Combined flow, 3-month average',
    'combined_flow_mean_6m_myr': 'Combined flow, 6-month average',
    'combined_flow_mean_12m_myr': 'Combined flow, 12-month average',
    'combined_flow_change_3m_vs_previous_3m': 'Combined flow, quarter-on-quarter change',
    'combined_flow_ratio_3m_to_12m': 'Combined flow vs 12-month average',
    'combined_flow_cv_12m': 'Combined flow variability, 12 months',
    'combined_zero_months_3m': 'Months without transactions',
    'inbound_count_mean_3m': 'Collection count, 3 months',
    'inbound_count_mean_12m': 'Collection count, 12 months',
    'outbound_count_mean_3m': 'Successful payments, 3 months',
    'outbound_count_mean_12m': 'Successful payments, 12 months',
    'inbound_share_3m': 'Collections share of combined flow',
    'outbound_success_recency_days': 'Days since last successful payment',
    'inbound_recency_months': 'Months since last collection',
    'outbound_submitted_count_mean_3m': 'Payments submitted per month',
    'outbound_failure_count_mean_3m': 'Failed payments per month',
    'outbound_processing_count_mean_3m': 'Payments in processing per month',
    'outbound_failure_rate_3m': 'Payment failure rate',
    'outbound_bank_failure_rate_3m': 'Bank-side payment failure rate',
    'outbound_processing_rate_3m': 'Share of payments in processing',
    'session_started_count_mean_3m': 'Online sessions started, 3 months',
    'session_started_count_mean_12m': 'Online sessions started, 12 months',
    'session_started_count_change_3m_vs_previous_3m': 'Online sessions, quarter-on-quarter change',
    'login_success_count_mean_3m': 'Successful logins, 3 months',
    'login_success_count_mean_12m': 'Successful logins, 12 months',
    'login_success_count_change_3m_vs_previous_3m': 'Successful logins, quarter-on-quarter change',
    'active_login_users_mean_3m': 'Active login users, 3 months',
    'active_login_users_mean_12m': 'Active login users, 12 months',
    'active_login_users_change_3m_vs_previous_3m': 'Active login users, quarter-on-quarter change',
    'session_completed_count_mean_3m': 'Online sessions completed per month',
    'login_success_recency_days': 'Days since last successful login',
    'session_duration_mean_3m_sec': 'Average online session length',
    'session_transactions_mean_3m': 'Transactions per online session',
    'passive_session_rate_3m': 'Sessions without transactions',
    'session_timeout_rate_3m': 'Sessions ended by timeout',
    'session_forced_drop_rate_3m': 'Sessions ended by forced drop',
    'approver_session_share_3m': 'Sessions by approver users',
    'untrusted_device_session_share_3m': 'Sessions from untrusted devices',
    'login_failure_rate_3m': 'Login failure rate',
    'friction_count_mean_3m': 'Service friction events per month',
    'bank_friction_count_mean_3m': 'Bank-side friction events per month',
    'friction_response_mean_3m_ms': 'Response time during friction events',
    'friction_retries_mean_3m': 'Retries per friction event',
    'active_account_count': 'Active accounts',
    'active_fd_count': 'Active fixed deposits',
    'closed_fd_count': 'Inactive fixed deposits',  # Computed as FD status not ACTIVE.
    'fd_maturing_30d_count': 'Deposits maturing within 30 days',
    'fd_balance_myr': 'Fixed deposit balance',
    'fd_average_balance_myr': 'Total average fixed deposit balance',  # Sum of each active FD's average_amount.
    'non_fd_balance_myr': 'Operating account balance',
    'fd_balance_mean_3m_myr': 'Fixed deposit balance, 3-month average',
    'fd_balance_mean_12m_myr': 'Fixed deposit balance, 12-month average',
    'fd_balance_change_3m_vs_previous_3m': 'Fixed deposits, quarter-on-quarter change',
    'fd_balance_weighted_offer_rate': 'Fixed deposit offered rate',
    'tier_id': 'Customer tier',
    'customer_type': 'Customer type',
    'sector_code': 'Business sector',
    'catalog_effective_fee_mean_myr': 'Contracted fee per transaction',
    'catalog_waiver_mean_pct': 'Contracted fee waiver level',
    'estimated_fee_mean_3m_myr': 'Estimated monthly fees',
    'estimated_waiver_mean_3m_myr': 'Estimated monthly waivers',
}


def driver_name(feature, driver=None):
    return DRIVER_LABELS.get(feature) or briefings.driver_label(driver or dict(feature=feature))


def day(value):
    parsed = date.fromisoformat(value[:10])
    return f'{parsed.day} {parsed:%b %Y}'


def span(period):
    start, end = date.fromisoformat(period['start']), date.fromisoformat(period['end'])
    return f'{start:%b}–{end:%b %Y}' if start.year == end.year else f'{start:%b %Y}–{end:%b %Y}'


def pct(value, digits=1):
    """briefings.percent with a trailing .0/.00 dropped for whole numbers only (40.0% -> 40%)."""
    return re.sub(r'\.0+%$', '%', briefings.percent(value, digits))


def name(fact_id, facts):
    """Name a placeholder resolves to; feature/signal facts use the same plain driver labels as the card."""
    if fact_id in PLAIN_NAMES:
        return PLAIN_NAMES[fact_id]
    feature = fact_id.split('.', 1)[1] if fact_id.startswith(('feature.', 'signal.')) else None
    return (DRIVER_LABELS.get(feature) or facts[fact_id]['label']).lower()


def resolve(text, facts):
    text = TOKEN.sub(lambda match: name(match[1], facts), text)
    return text[:1].upper() + text[1:]


def weights(evidence):
    saved = evidence['explanation']
    return {d['feature']: d['contribution_logodds'] for d in saved['higher_risk_drivers'] + saved['lower_risk_drivers']}


def line(text, ids, features=(), source='evidence', twelve=False, external=True):
    """twelve=True marks a sentence that uses a 12-month average (drives the single card footnote).
    external=False keeps a deterministic card sentence out of the provider payload."""
    return dict(text=text, ids=list(ids), features=list(features), source=source, twelve=twelve, external=external)


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
                              ('outbound_failure_rate_3m', '{p} of payments failed ({period}).'),
                              ('outbound_bank_failure_rate_3m', '{p} of payments failed for bank-side reasons ({period}).'),
                              ('passive_session_rate_3m', '{p} of online banking sessions had no transaction ({period}).')]:
        fact = get(feature)
        if fact:
            lines.append(line(template.format(p=pct(fact['value'], 1), period=span(fact['period'])), [fact['id']], [feature]))
    context = []
    for recency, noun, short, long in [('outbound_success_recency_days', 'payment', 'outbound_count_mean_3m', 'outbound_count_mean_12m'),
                                       ('login_success_recency_days', 'login', 'login_success_count_mean_3m', 'login_success_count_mean_12m')]:
        fact = get(recency)
        if fact:
            days = f'{fact["value"]:,.0f}'
            context.append(line(f'Last successful {noun}: {days} day{"" if days == "1" else "s"} before {cutoff}.', [fact['id']], [recency]))
        a, b = get(short), get(long)
        label = 'Successful payments' if noun == 'payment' else 'Successful logins'
        if a and b:
            relation = 'below' if a['value'] < b['value'] else 'above' if a['value'] > b['value'] else 'equal to'
            context.append(line(f'{label}: {a["value"]:,.1f} a month in {span(a["period"])}, {relation} the 12-month '
                                f'average ({b["value"]:,.1f}).', [a['id'], b['id']], [short, long], twelve=True))
        elif a or b:
            only = a or b
            context.append(line(f'{label}: {only["value"]:,.1f} a month in {span(only["period"])}.', [only['id']],
                                [short if a else long], twelve=only is b))
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
        trend.append(line(f'Combined flow in {span(ratio["period"])} {relative(ratio["value"], "its")}.', [ratio['id']],
                          ['combined_flow_ratio_3m_to_12m'], twelve=True))
    lines = []
    for feature, noun in [('inbound_flow_ratio_3m_to_12m', 'Collections'), ('outbound_flow_ratio_3m_to_12m', 'Payments')]:
        fact = get(feature)
        if fact:
            lines.append(line(f'{noun} in {span(fact["period"])} {relative(fact["value"], "their")}.', [fact['id']],
                              [feature], twelve=True))
    operating = get('non_fd_balance_myr')
    if operating:
        lines.append(line(f'Operating account balances on {day(operating["period"]["as_of"])}: {briefings.money(operating["value"])}.',
                          [operating['id']], ['non_fd_balance_myr']))
    deposit, maturing = get('fd_balance_myr'), get('fd_maturing_30d_count')
    if deposit or maturing:  # One deposit sentence keeps the Finance section short.
        when = day((deposit or maturing)['period']['as_of'])
        parts = [f'Fixed deposits on {when}: {briefings.money(deposit["value"])}'] if deposit else []
        if maturing:
            n = int(maturing['value'])
            if deposit:
                parts.append(f'{"none" if n == 0 else n} due to mature within 30 days')
            else:
                parts.append(f'{"No" if n == 0 else n} fixed deposit{"" if n == 1 else "s"} due to mature within 30 days of {when}')
        lines.append(line('; '.join(parts) + '.', [f['id'] for f in (deposit, maturing) if f], ['fd_balance_myr', 'fd_maturing_30d_count']))
    fee, waiver = get('estimated_fee_mean_3m_myr'), get('estimated_waiver_mean_3m_myr')
    if fee or waiver:
        parts = []
        if fee:
            parts.append(f'fees {briefings.money(fee["value"])} a month')
        if waiver:
            parts.append(f'waivers {briefings.money(waiver["value"])} a month')
        lines.append(line(f'Estimated {" and ".join(parts)} ({span((fee or waiver)["period"])}); historical estimates, not profit.',
                          [f['id'] for f in (fee, waiver) if f], ['estimated_fee_mean_3m_myr', 'estimated_waiver_mean_3m_myr']))
    notable, rest = ranked(lines, w)
    return (trend + stake_line(evidence) + notable + rest)[:6]


FSL_A_TEXT = 'waiver condition not met'  # Card only (word budget); the UI says 'Fee waiver condition not met'.
FSL_B_TEXT = "fixed deposits don't cover waived transaction cost"
NEGATIVE_TEXT = 'Estimated relationship contribution is negative at the assumed cost; see cost sensitivity.'


def stake_line(evidence):
    """Revenue at Risk next to (never multiplied by) the risk %: 3 months of estimated relationship
    contribution, plus any fee subsidy leakage flag. Deterministic; not sent to the provider."""
    metrics = evidence.get('finance_metrics') or {}
    contribution, rar = metrics.get('contribution_monthly'), metrics.get('rar_3m')
    if contribution is None:
        return []
    # Check A and B wording follows each flag only: a negative contribution does not imply either check.
    flags = []
    if (metrics.get('fsl_a') or {}).get('flagged'):
        flags.append(FSL_A_TEXT)
    fsl_b = metrics.get('fsl_b') or {}
    if fsl_b.get('flagged') and not fsl_b.get('policy'):
        flags.append(FSL_B_TEXT)
    if contribution >= 0:
        text = (f'Contribution at stake over {briefings.forecast(evidence["identity"]["cutoff"])}: {briefings.money(rar)} '
                '(estimated relationship contribution' + ''.join('; ' + flag for flag in flags) + ').')
    else:
        text = (NEGATIVE_TEXT + f' ({briefings.money(contribution)} a month'
                + ''.join('; ' + flag for flag in flags) + ').')
    return [line(text, [], external=False)]


def relative(ratio, possessive):
    """3-month mean vs 12-month mean from the exact saved ratio; the ratio itself stays in supporting evidence."""
    if ratio == 1:
        return f'matched {possessive} 12-month average'
    return f'averaged {pct(abs(1 - ratio), 2)} {"below" if ratio < 1 else "above"} {possessive} 12-month average'


THRESHOLD_MEANING = 'which was set from past data to balance catching real cases against false alerts'
NO_SIGNAL = 'No signal raised the estimate notably.'
TOP_SIGNALS = 3
# Always citable: the usual-flow line (d), the "Recent activity vs usual" tile, and the prediction itself.
ALWAYS_ALLOWED = ('feature.combined_flow_mean_12m_myr', 'feature.combined_flow_ratio_3m_to_12m',
                  'prediction.risk', 'prediction.flag', 'prediction.threshold')


def likelihood(risk, flagged):
    """Phrase chosen from the percentage the card displays (a displayed 50% always reads 'more likely than not').
    The middle band uses the saved flag, never a recomputed comparison with the threshold."""
    if float(pct(risk, 1).rstrip('%')) >= 50:
        return 'more likely than not'
    return 'below even odds, but high enough to review' if flagged else None


def short_money(value):
    """Readable amount for the card: RM x.x billion / RM x.x million, else whole ringgit. Exact amounts stay on Finance."""
    amount, sign = abs(Decimal(str(value))), '-' if value < 0 else ''
    if amount.quantize(Decimal('1'), rounding=ROUND_HALF_UP) < 10**6:
        return f'{sign}RM {amount.quantize(Decimal("1"), rounding=ROUND_HALF_UP):,}'
    millions = (amount / 10**6).quantize(Decimal('.1'), rounding=ROUND_HALF_UP)
    if millions < 1000:
        return f'{sign}RM {millions} million'
    return f'{sign}RM {(amount / 10**9).quantize(Decimal(".1"), rounding=ROUND_HALF_UP):,} billion'


def top_higher(evidence):
    """Top saved higher-risk drivers by contribution; stable sort, as in Signals to investigate."""
    drivers = evidence['explanation']['higher_risk_drivers']
    return sorted(drivers, key=lambda d: -abs(d['contribution_logodds']))[:TOP_SIGNALS]


def in_sentence(label):
    """Lowercase the first letter unless the label starts with an acronym ('FD balance' stays)."""
    return label if len(label) > 1 and label[1].isupper() else label[:1].lower() + label[1:]


def joined(labels):
    """'a, b and c'; when any label itself contains a comma (e.g. 'successful payments, 3 months'), items are
    separated by semicolons so the list stays unambiguous: 'a; b, c; and d' (two items: 'a, b; and c')."""
    if len(labels) == 1:
        return labels[0]
    if any(',' in label for label in labels):
        return '; '.join(labels[:-1]) + '; and ' + labels[-1]
    return ', '.join(labels[:-1]) + ' and ' + labels[-1]


def allowed_references(evidence):
    """IDs AI text may cite: the top-3 higher-risk drivers named in the bottom line, the usual-flow and
    recent-vs-usual facts, and the prediction. A lower-risk driver is never citable, whatever else applies."""
    facts, saved = evidence['facts'], evidence['explanation']
    ids = {prefix + d['feature'] for d in top_higher(evidence) for prefix in ('feature.', 'signal.')} | set(ALWAYS_ALLOWED)
    ids -= {prefix + d['feature'] for d in saved['lower_risk_drivers'] for prefix in ('feature.', 'signal.')}
    # m6-narrative-11: only IDs the card payload actually lists (a signal.* fact exists only if its driver is
    # among the weighed signals); listing others invited citations the validator rejects as unknown.
    listed = set().union(*section_ids(plan(evidence)).values())
    return sorted(i for i in ids if i in facts and i in listed)


# m6-narrative-10: questions never cite the prediction itself; Finance questions may cite only usual or recent
# combined flow (the usual-flow line counts as Finance evidence although it sits in the bottom line).
FINANCE_QUESTION_FACTS = ('feature.combined_flow_mean_12m_myr', 'feature.combined_flow_ratio_3m_to_12m')


def question_allowed(evidence):
    """IDs any question (summary or RM client) may cite: the allowed references without prediction.*."""
    return [i for i in allowed_references(evidence) if not i.startswith('prediction.')]


def question_references(evidence):
    """Per-audience IDs a summary question may cite; an empty list means omit that audience's question."""
    allowed = set(question_allowed(evidence))
    operations = section_ids(plan(evidence))['operations']
    return dict(operations=sorted(allowed & operations), finance=sorted(allowed & set(FINANCE_QUESTION_FACTS)))


def footnote(evidence, with_usual=True):
    """Forecast window and data cutoff, then the usual-flow baseline: the 12 months ending at the cutoff."""
    cutoff = evidence['identity']['cutoff']
    text = f'Prediction for {briefings.forecast(cutoff)}, based on data up to {day(cutoff)}.'
    if with_usual:
        base = period(cutoff, 12)
        start, end = date.fromisoformat(base['start']), date.fromisoformat(base['end'])
        text += f' "Usual monthly combined flow" is the monthly average from {start:%b %Y} to {end:%b %Y}.'
    return text


def bottom_line(evidence):
    facts = evidence['facts']
    lines = []
    risk, flag, threshold = facts.get('prediction.risk'), facts.get('prediction.flag'), facts.get('prediction.threshold')
    if risk:
        phrase = likelihood(risk['value'], bool(flag and flag['value']))
        lines.append(line('Estimated chance that average monthly combined flow (Collection + Disbursement) over '
                          f'{briefings.forecast(evidence["identity"]["cutoff"])} falls to half or less of its usual level: '
                          f'{pct(risk["value"], 1)}' + (f', {phrase}.' if phrase else '.'), ['prediction.risk'],
                          twelve=True))  # Usual level: the 12 months ending at cutoff (see footnote).
    if flag and threshold:
        t = pct(threshold['value'], 1)
        text = (f'Flagged for committee review: at or above the {t} threshold, {THRESHOLD_MEANING}.' if flag['value']
                else f'Not flagged: below the {t} threshold, {THRESHOLD_MEANING}.')
        lines.append(line(text, ['prediction.flag', 'prediction.threshold']))
    top = [in_sentence(driver_name(d['feature'], d)) for d in top_higher(evidence)]
    lines.append(line(f'Strongest signals raising the estimate: {joined(top)} (details in Signals to investigate).' if top
                      else NO_SIGNAL, []))
    usual = facts.get('feature.combined_flow_mean_12m_myr')
    if usual:
        lines.append(line(f'Usual monthly combined flow (12-month average): {short_money(usual["value"])}.', [usual['id']],
                          twelve=True))
    return lines


def weighed(evidence):
    saved, facts = evidence['explanation'], evidence['facts']
    drivers = sorted(saved['higher_risk_drivers'] + saved['lower_risk_drivers'], key=lambda d: -abs(d['contribution_logodds']))[:3]
    lines = []
    for driver in drivers:
        feature = driver['feature']
        label = driver_name(feature, driver)
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
            text = f'Could Operations check whether the recorded {driver_name(friction[0]).lower()} points to a fixable service problem?'
            cited = ['feature.' + friction[0]]
        else:
            text = 'Could Operations confirm whether recent online-banking and payment activity matches what the relationship team expects?'
            cited = sorted(ids['operations'])[:1]
        result.append(dict(audience='operations', text=text, source='template', evidence_ids=cited))
    if ids['finance']:
        trend = 'feature.combined_flow_ratio_3m_to_12m'
        result.append(dict(audience='finance', source='template', evidence_ids=[trend] if trend in ids['finance'] else sorted(ids['finance'])[:1],
                           text='Could Finance confirm what the combined flow change means for balances and fees?'))
    return result


def render_summary(evidence, link=None, questions=None):
    """Same sections with or without AI text; with none it is the deterministic fallback card."""
    facts, card_plan = evidence['facts'], plan(evidence)
    sections = []
    for key in CARD_SECTIONS:
        sections.append(dict(id=key, title=TITLES[key],
                             items=[dict(text=l['text'], source=l['source'], evidence_ids=l['ids']) for l in card_plan[key]]))
        if key == 'bottom_line' and link and link['text'].strip():
            sections.append(dict(id='link', title=TITLES['link'], items=[dict(
                text=resolve(link['text'], facts), source='ai', evidence_ids=list(link['evidence_ids']))]))
    asked = [dict(audience=q['audience'], text=resolve(q['text'], facts), source='ai', evidence_ids=list(q['evidence_ids']))
             for q in questions or []]
    for template in templates(evidence, card_plan):
        if len(asked) < QUESTION_LIMIT and not any(q['audience'] == template['audience'] for q in asked):
            asked.append(template)
    asked.sort(key=lambda q: AUDIENCE_ORDER.index(q['audience']))
    for q in asked:  # Deterministic 'Based on' from the cited facts, using the card's plain labels.
        q['basis'] = basis(q['evidence_ids'], facts)
    if any(l['twelve'] for lines in card_plan.values() for l in lines):  # Every card: the risk sentence uses the usual level.
        sections.append(dict(id='footnote', title='', items=[dict(
            text=footnote(evidence, 'feature.combined_flow_mean_12m_myr' in facts), source='standard', evidence_ids=[])]))
    closing = [CLOSING] + ([SERVICE_CLOSING] if service_issue(evidence) else [])
    sections.append(dict(id='closing', title=TITLES['closing'],
                         items=[dict(text=text, source='standard', evidence_ids=[]) for text in closing]))
    cited = {i for s in sections for item in s['items'] for i in item['evidence_ids']} | {i for q in asked for i in q['evidence_ids']}
    ai_used = link is not None or questions is not None
    return dict(format='sections-1', sections=sections, questions=asked, evidence_ids=sorted(cited),
                checks=BASE_CHECKS + (AI_CHECKS if ai_used else []))


def basis(ids, facts):
    """RM-only 'Based on' line: plain names of the cited facts, each once in order of first appearance
    (feature.X and signal.X share one name)."""
    names = [name(i, facts) for i in ids if i in facts]
    return '; '.join(dict.fromkeys(n[:1].upper() + n[1:] for n in names))


def unique_basis(text):
    """Display-time de-duplication of a stored 'Based on' text (labels never contain '; ')."""
    return '; '.join(dict.fromkeys(text.split('; ')))


def render_client_questions(evidence, questions=None, standard=None):
    """AI-suggested client questions, or the standard (deterministic) bank as the fallback."""
    facts = evidence['facts']
    if questions is not None:
        items = [dict(text=q['text'], source='ai', basis=basis(q['evidence_ids'], facts), evidence_ids=list(q['evidence_ids']))
                 for q in questions]
    else:
        items = [dict(text=q['text'], source='standard', basis=q['source'], evidence_ids=[]) for q in standard or []]
    return dict(format='questions-1', questions=items, evidence_ids=sorted({i for q in items for i in q['evidence_ids']}),
                checks=BASE_CHECKS + (['known_references', 'client_language', 'numeric_date_rules', 'interpretation_rules']
                                      if questions is not None else []))


def card_words(content):
    return (sum(len(item['text'].split()) for s in content['sections'] for item in s['items'])
            + sum(len(q['text'].split()) for q in content['questions']))


def provider_payload(evidence):
    """What Gemini sees: the card's own sentences per section, with citable fact names. No identifiers."""
    facts, card_plan = evidence['facts'], plan(evidence)
    sections = []
    for key in CARD_SECTIONS:
        sections.append(dict(section=key, title=TITLES[key], lines=[dict(sentence=l['text'], facts=[
            dict(id=i, placeholder='{{' + i + '}}', name=name(i, facts), kind=facts[i]['kind'],
                 direction=facts[i].get('direction'), group=facts[i].get('group')) for i in l['ids']]) for l in card_plan[key]
                 if l.get('external', True)]))
    return dict(customer='Customer A', purpose=evidence['identity']['purpose'], cutoff=evidence['identity']['cutoff'], sections=sections,
                allowed_references=allowed_references(evidence),
                question_references=(question_references(evidence) if evidence['identity']['purpose'] == 'summary'
                                     else question_allowed(evidence)),
                limits='Signals show what the estimate weighed, not causes. Balances are exposures; fees and waivers are '
                       "historical estimates, not profit. Prioritisation is the committee's decision.")
