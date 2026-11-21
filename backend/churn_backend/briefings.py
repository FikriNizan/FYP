"""Read-only, deterministic RM briefing content shared by JSON preview and PDF."""
import hashlib
import math
import re
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP, localcontext

from . import cases, repository as repo
from .db import get_db
from .validation import require


def number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def money(value):
    if not number(value):
        return 'Not provided'
    amount = Decimal(str(value))
    with localcontext() as context:
        context.prec = max(28, amount.adjusted() + 4)
        rounded = amount.quantize(Decimal('.01'), rounding=ROUND_HALF_UP)
    return ('-' if math.copysign(1, value) < 0 else '') + f'RM\u00a0{abs(rounded):,.2f}'


def percent(value, digits=1):
    return f'{value * 100:.{digits}f}%' if number(value) else 'Not provided'


def month(value):
    return date.fromisoformat(value).strftime('%B %Y')


def dated(value, missing='Not provided'):
    if not value:
        return missing
    stamp = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if stamp.tzinfo:
        stamp = stamp.astimezone(timezone(timedelta(hours=8)))
    return f'{stamp.day} {stamp:%b %Y}'


def signed_percent(value):
    return ('\u2212' if value < 0 else '+' if value > 0 else '') + f'{abs(value):.1f}%'


def forecast(cutoff):
    cutoff = date.fromisoformat(cutoff)
    def ahead(n):
        index = cutoff.year * 12 + cutoff.month - 1 + n
        return date(index // 12, index % 12 + 1, 1)
    first, last = ahead(1), ahead(3)
    return f'{first:%b}{" " + str(first.year) if first.year != last.year else ""}–{last:%b %Y}'


LABELS = {
    'combined_flow_ratio_3m_to_12m': 'Transaction value',
    'inbound_flow_ratio_3m_to_12m': 'Collections',
    'outbound_flow_ratio_3m_to_12m': 'Payments',
    'outbound_failure_rate_3m': 'Payment failures',
    'outbound_bank_failure_rate_3m': 'Bank-attributed payment failures',
    'login_failure_rate_3m': 'Login difficulties',
    'passive_session_rate_3m': 'Sessions without transactions',
    'fd_maturing_30d_count': 'Fixed deposits maturing within 30 days',
    'non_fd_balance_myr': 'Operating account balances', 'fd_balance_myr': 'Fixed deposit balances',
    'login_success_count_mean_12m': 'Usual successful logins',
    'approver_session_share_3m': 'Sessions involving approvers',
}


def driver_label(driver):
    return LABELS.get(driver['feature']) or driver.get('label') or driver['feature'].replace('_', ' ')


def driver_value(driver):
    value, feature = driver.get('value'), driver['feature']
    if value is None:
        return 'Not provided'
    if '_ratio_' in feature:
        return percent(value, 2) + ' of the twelve-month average'
    if '_rate_' in feature or '_share_' in feature:
        return percent(value)
    if feature.endswith('_myr'):
        return money(value)
    return f'{value:,.2f}'.rstrip('0').rstrip('.') if number(value) else str(value)


# Client-safe RM question bank (wording approved by the project owner). Every predictor in
# feature_schema.json maps to one family; families without a client question are listed in
# NO_CLIENT_QUESTION. Questions never mention the model, scores, internal records or other banks.
CLIENT_FAMILY_FEATURES = {
    'collections': ['inbound_flow_mean_1m_myr', 'inbound_flow_mean_3m_myr', 'inbound_flow_mean_6m_myr', 'inbound_flow_mean_12m_myr',
                    'inbound_flow_change_3m_vs_previous_3m', 'inbound_flow_ratio_3m_to_12m', 'inbound_flow_cv_12m',
                    'inbound_zero_months_3m', 'inbound_count_mean_3m', 'inbound_count_mean_12m', 'inbound_share_3m',
                    'inbound_recency_months'],
    'payments': ['outbound_flow_mean_1m_myr', 'outbound_flow_mean_3m_myr', 'outbound_flow_mean_6m_myr', 'outbound_flow_mean_12m_myr',
                 'outbound_flow_change_3m_vs_previous_3m', 'outbound_flow_ratio_3m_to_12m', 'outbound_flow_cv_12m',
                 'outbound_zero_months_3m', 'outbound_count_mean_3m', 'outbound_count_mean_12m', 'outbound_success_recency_days',
                 'outbound_submitted_count_mean_3m'],
    'transaction_value': ['combined_flow_mean_1m_myr', 'combined_flow_mean_3m_myr', 'combined_flow_mean_6m_myr',
                          'combined_flow_mean_12m_myr', 'combined_flow_change_3m_vs_previous_3m', 'combined_flow_ratio_3m_to_12m',
                          'combined_flow_cv_12m', 'combined_zero_months_3m'],
    'login': ['login_failure_rate_3m'],
    'online_banking': ['passive_session_rate_3m', 'session_duration_mean_3m_sec', 'session_transactions_mean_3m',
                       'session_started_count_mean_3m', 'session_started_count_mean_12m',
                       'session_started_count_change_3m_vs_previous_3m', 'session_completed_count_mean_3m',
                       'active_login_users_mean_3m', 'active_login_users_mean_12m', 'active_login_users_change_3m_vs_previous_3m',
                       'login_success_count_mean_3m', 'login_success_count_mean_12m',
                       'login_success_count_change_3m_vs_previous_3m', 'login_success_recency_days', 'approver_session_share_3m'],
    'payment_failures': ['outbound_failure_rate_3m', 'outbound_bank_failure_rate_3m', 'outbound_processing_rate_3m',
                         'outbound_failure_count_mean_3m', 'outbound_processing_count_mean_3m'],
    'service_friction': ['session_timeout_rate_3m', 'session_forced_drop_rate_3m', 'friction_count_mean_3m',
                         'bank_friction_count_mean_3m', 'friction_response_mean_3m_ms', 'friction_retries_mean_3m'],
    'fixed_deposits': ['fd_maturing_30d_count', 'fd_balance_myr', 'fd_average_balance_myr', 'fd_balance_mean_3m_myr',
                       'fd_balance_mean_12m_myr', 'fd_balance_change_3m_vs_previous_3m', 'active_fd_count', 'closed_fd_count',
                       'fd_balance_weighted_offer_rate'],
    'fees': ['estimated_fee_mean_3m_myr', 'estimated_waiver_mean_3m_myr', 'catalog_effective_fee_mean_myr', 'catalog_waiver_mean_pct'],
    'accounts': ['non_fd_balance_myr', 'active_account_count'],
}
# Static attributes, and device-security monitoring that should not be raised in a sales conversation.
NO_CLIENT_QUESTION = ('tier_id', 'customer_type', 'sector_code', 'untrusted_device_session_share_3m')
CLIENT_FAMILIES = {feature: family for family, features in CLIENT_FAMILY_FEATURES.items() for feature in features}
CLIENT_QUESTIONS = {
    'collections': 'Have there been any changes in how or when your customers pay you?',
    'payments': 'Have your supplier or payroll payments changed recently, for example in timing or in how you make them?',
    'transaction_value': 'How has business activity been for you lately, and do you expect any changes ahead?',
    'login': 'Have you or your team had any difficulty signing in to online banking?',
    'online_banking': "Is our online banking still meeting your team's day-to-day needs?",
    'payment_failures': 'Have any of your payments been delayed or not gone through as expected?',
    'service_friction': 'Has online banking been slow, timed out or disconnected for you recently?',
    'fees': 'Are the fees and charges on your accounts clear and in line with what you expected?',
    'accounts': 'Are your current accounts still set up the way you need for day-to-day operations?',
}
FD_PLANS_QUESTION = 'What are your plans for your fixed deposits, including any coming up for renewal?'
FD_SURPLUS_QUESTION = "Do you have any surplus funds you're planning to place, now or in the coming months?"
FALLBACK_QUESTION = 'How is your business going, and is there anything we could do to support you better?'
QUESTION_LIMIT = 3


def has_fixed_deposits(customer):
    """Presence check on saved values (not a threshold): any active FD count or FD balance above zero."""
    features = customer.get('features') or {}
    values = [features.get('active_fd_count'), features.get('fd_balance_myr'), (customer.get('finance') or {}).get('fd_balance_myr')]
    return any(number(value) and value > 0 for value in values)


def discussion_questions(customer):
    """Client-safe questions an RM can ask directly. Triggers are the saved higher-risk drivers only,
    strongest first; at most one question per family and three in total. The source (plain driver
    label and value) is for the RM's eyes only and never appears in the question text."""
    from .ai_render import driver_name
    drivers = sorted((customer.get('explanation') or {}).get('higher_risk_drivers') or [],
                     key=lambda d: -(d.get('contribution_logodds') or 0))
    questions, seen = [], set()
    for driver in drivers:
        family = CLIENT_FAMILIES.get(driver['feature'])
        if family is None or family in seen:
            continue
        seen.add(family)
        if family == 'fixed_deposits':
            text = FD_PLANS_QUESTION if has_fixed_deposits(customer) else FD_SURPLUS_QUESTION
        else:
            text = CLIENT_QUESTIONS[family]
        questions.append(dict(family=family, source=driver_name(driver['feature'], driver) + ': ' + driver_value(driver), text=text))
        if len(questions) == QUESTION_LIMIT:
            break
    return questions or [dict(family='general', source='General relationship check-in', text=FALLBACK_QUESTION)]


def selected_ids(values):
    require(isinstance(values, list) and all(isinstance(v, str) and re.fullmatch(r'[A-Za-z0-9_-]{1,128}', v) for v in values),
            'Select valid case IDs from Reviewed Customers.')
    ids = list(dict.fromkeys(values))
    require(1 <= len(ids) <= 10, 'Select between one and ten unique prioritised cases.')
    return ids


def section(title, paragraphs=None, rows=None, items=None):
    return dict(title=title, paragraphs=paragraphs or [], rows=rows or [], items=items or [])


def document(case, sources):
    original, latest = case['original'], case['latest']
    review, opened = case['current_review'], case['original_review']
    ops, finance = latest.get('operations') or {}, latest.get('finance') or {}
    recent, usual = ops.get('combined_flow_mean_3m_myr'), ops.get('combined_flow_mean_12m_myr')
    comparable = number(recent) and number(usual) and usual > 0
    if comparable:
        change = (recent / usual - 1) * 100
        activity = 'Similar to usual' if abs(change) < .05 else f'{abs(change):.1f}% {"lower" if change < 0 else "higher"}'
        activity += ' versus the trailing twelve-month average.'
        activity_glance = ('Similar to usual' if abs(change) < .05 else signed_percent(change))
    else:
        activity_glance = 'Not comparable'
        activity = 'A comparable activity change is unavailable: a recorded recent average and a positive trailing twelve-month average are required.'
    history_available = any(isinstance(row.get('snapshot_month'), str) and row['snapshot_month'] <= latest['cutoff_month'] and any(number(row.get(key)) for key in ['combined_flow_myr','inbound_myr','outbound_success_myr']) for row in latest.get('flow_history', []))
    history_note = [] if history_available else ['No cutoff-safe monthly flow history was supplied; this briefing uses the saved aggregate measures.']
    newer = latest['cutoff_month'] > original['cutoff_month']
    latest_notes = [] if newer else ['No newer assessment month is available.']
    if latest['cutoff_month'] == original['cutoff_month'] and latest['batch_id'] != original['batch_id']:
        latest_notes.append('A distinct saved batch exists for the same assessment cutoff; this is not a newer month. See the exact identifiers below.')
    latest_notes.append('A later risk estimate does not revise the original judgement or close the case.')
    signals = []
    explanation = latest.get('explanation') or {}
    for key, direction in [('higher_risk_drivers', 'Pushed the estimate higher'), ('lower_risk_drivers', 'Pushed the estimate lower')]:
        for driver in explanation.get(key, []):
            if len(signals) < 3:
                signals.append([driver_label(driver), f'{driver_value(driver)} · {direction}'])
    tasks = case.get('follow_ups') or []
    follow_rows = []
    for task in tasks:
        event = task['current']
        status = {'planned':'Planned', 'attempted':'Attempted', 'delivered':'Completed', 'cancelled':'Cancelled'}[event['action_status']]
        follow_rows.append([f'{status} · {task["action_type"].replace("_", " ")}',
                            f'{dated(event["action_date"])} · {event.get("recorded_by") or "Not provided"} · {event.get("notes") or "No notes"}'])
    ops_all = [['Payment failure rate', ops.get('outbound_failure_rate_3m')],
               ['Bank-attributed payment failure rate', ops.get('outbound_bank_failure_rate_3m')],
               ['Login difficulty rate', ops.get('login_failure_rate_3m')],
               ['Sessions without transactions', ops.get('passive_session_rate_3m')]]
    ops_rows = [[label, percent(value)] for label, value in ops_all] if any(number(v) for _, v in ops_all) else []
    planned = sorted(dated(t['current']['action_date']) for t in tasks if t['current']['action_status'] == 'planned' and t['current'].get('action_date'))
    questions = discussion_questions(latest)
    for question in questions:
        question['month'] = month(latest['cutoff_month'])
    trace = [
        ['Case ID', case['case_id']], ['Case version', str(case['version'])],
        ['Original batch', original['batch_id']], ['Original prediction', original['prediction_id']],
        ['Original review version', str((case.get('review_history') or [{}])[0].get('version', 'Not provided'))],
        ['Current review version', str(review['version'])],
        ['Current review prediction', review['prediction_id']],
        ['Current committee month', month(review['assessment_month'])],
        ['Latest batch', latest['batch_id']], ['Latest prediction', latest['prediction_id']],
    ]
    sample = any(sources.get(c['batch_id']) == 'notebook_case_sample' for c in [original, latest])
    snapshot = dict(case_id=case['case_id'], case_version=case['version'], review_version=review['version'],
                    original_prediction_id=original['prediction_id'], latest_prediction_id=latest['prediction_id'],
                    evidence_hash=hashlib.sha256(repo.encode(dict(case=case, sources=sources)).encode()).hexdigest())
    return dict(case_id=case['case_id'], snapshot=snapshot, customer_id=original['cus_id'],
                name=latest.get('customer_name') or original.get('customer_name') or 'Customer '+original['cus_id'],
                # Retained legacy preview fields; AI routes independently resolve server evidence.
                ai_context={k:latest[k] for k in ['cutoff_month', 'calibrated_risk']},
                sample_note='Single-case sample evidence is included. This briefing does not represent a complete portfolio.' if sample else None,
                original=section('At the time of review', ['Rationale: '+(opened.get('reason') or 'No original rationale supplied.')], [
                    ['Assessment month', month(original['cutoff_month'])],
                    ['Predicted risk', percent(original['calibrated_risk'])],
                    ['Forecast window', forecast(original['cutoff_month'])],
                    ['Original reviewer', opened.get('reviewer') or 'Not provided'],
                    ['Case opened', dated(case.get('created_at'))]]),
                latest=section('Latest available assessment', latest_notes, [
                    ['Assessment month', month(latest['cutoff_month'])],
                    ['Predicted risk', percent(latest['calibrated_risk'])],
                    ['Forecast window', forecast(latest['cutoff_month'])]]),
                activity=section('Observed activity through '+month(latest['cutoff_month']), [activity,
                    *history_note],
                    [['Latest 3-month average', money(recent)], ['Trailing 12-month average', money(usual)]]),
                signals=section('Signals to investigate', ['Model signals describe influence on the saved estimate, not confirmed complaints, causes or probability-point effects.'], signals),
                operations=section('Operations context', [review.get('operations_notes') or 'No committee Operations notes recorded.',
                    *([] if ops_rows else ['No Operations rates were recorded for this assessment.']),
                    *(['Saved rates for the three months through '+month(latest['cutoff_month'])+'.'] if ops_rows else [])], ops_rows),
                finance=section('Finance context', [review.get('finance_notes') or 'No committee Finance notes recorded.',
                    'Balances are exposures. Fees and waivers are separate historical three-month monthly estimates, not verified profit, actual invoices or retention savings.'], [
                        ['Operating balances', money(finance.get('non_fd_balance_myr'))],
                        ['Fixed-deposit balances', money(finance.get('fd_balance_myr'))],
                        ['Estimated monthly fees', money(finance.get('estimated_monthly_fee_myr'))],
                        ['Estimated monthly waivers', money(finance.get('estimated_monthly_waiver_myr'))]]),
                decision=section('Current committee rationale & next step', [
                    *(['Deliberate reassessment for '+month(review['assessment_month'])+'.'] if review['prediction_id'] != original['prediction_id'] else []),
                    'Rationale unchanged since the original review.' if (review.get('reason') or '') == (opened.get('reason') or '') else 'Rationale: '+(review.get('reason') or 'No rationale supplied.'),
                    *([] if tasks else ['No follow-up has been recorded; this briefing can be prepared before outreach.'])], [
                        ['Reviewer', review.get('reviewer') or 'Not provided'], ['Review saved', dated(review.get('updated_at'))],
                        ['Case owner', case.get('owner') or 'Unassigned'], ['Case due date', dated(case.get('next_action_date'), 'Not set')],
                        ['Case status', case['status'].capitalize()]]),
                followups=section('Follow-up recorded', rows=follow_rows) if follow_rows else None,
                glance=[
                    dict(label='Committee decision', value='Prioritise for RM', note='Case '+case['status']),
                    dict(label='Predicted risk, latest', value=percent(latest['calibrated_risk']),
                         note=month(latest['cutoff_month'])+' \u00b7 was '+percent(original['calibrated_risk'])+' at review ('+month(original['cutoff_month'])+')'),
                    dict(label='Activity vs usual', value=activity_glance, note='3-month vs trailing 12-month average'),
                    dict(label='Case due date', value=dated(case.get('next_action_date'), 'Not set'),
                         note='Owner: '+(case.get('owner') or 'Unassigned')+(' \u00b7 Planned contact '+planned[0] if planned else ''))],
                risk_definition='Predicted risk is the calibrated estimate that average combined transaction flow over the forecast window falls to half or less of the trailing twelve-month average. It is not account-closure risk.',
                prepared_on=dated(datetime.now(timezone.utc).isoformat()),
                questions=questions, traceability=trace)


def load(values):
    ids = selected_ids(values)
    db = get_db()
    # One consistent read snapshot across all selected cases and the batch registry.
    db.execute('BEGIN')
    try:
        sources = {r['batch_id']:r['source_kind'] for r in db.execute('SELECT batch_id,source_kind FROM batches')}
        records = [cases.record(cases.case_row(case_id), True) for case_id in ids]
        require(all(c['current_review']['decision'] == 'prioritise' for c in records),
                'One or more selected cases are no longer prioritised. Return to Reviewed Customers and select currently prioritised cases.')
        items = [document(c, {k:sources[k] for k in {c['original']['batch_id'],c['latest']['batch_id']}}) for c in records]
        return dict(items=items, snapshots=[item['snapshot'] for item in items])
    finally:
        db.rollback()  # Read transaction only. No persisted preparation/export state.
