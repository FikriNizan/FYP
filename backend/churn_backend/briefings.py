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


def forecast(cutoff):
    cutoff = date.fromisoformat(cutoff)
    def ahead(n):
        index = cutoff.year * 12 + cutoff.month - 1 + n
        return date(index // 12, index % 12 + 1, 1)
    first, last = ahead(1), ahead(3)
    return f'{first:%b}{" " + str(first.year) if first.year != last.year else ""}–{last:%b %Y}'


LABELS = {
    'combined_flow_ratio_3m_to_12m': 'Transaction activity',
    'inbound_flow_ratio_3m_to_12m': 'Incoming payments',
    'outbound_flow_ratio_3m_to_12m': 'Outgoing payments',
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


def discussion_questions(customer):
    """Same bounded evidence rules as the existing discussionQuestions helper; no padding."""
    ops = customer.get('operations') or {}
    questions, seen = [], set()
    recent, usual = ops.get('combined_flow_mean_3m_myr'), ops.get('combined_flow_mean_12m_myr')
    if number(recent) and number(usual) and usual > 0 and recent < usual:
        questions.append(dict(source='Observed three- and twelve-month flow averages', text=
                              'Recent recorded transaction activity is lower than the trailing average. Has the way you use these accounts changed?'))
    for driver in (customer.get('explanation') or {}).get('higher_risk_drivers', []):
        feature, value = driver['feature'], driver.get('value')
        if not number(value) or value <= 0:
            continue
        if feature == 'login_failure_rate_3m':
            category, text = 'login', 'The recorded login difficulty rate contributed to this estimate. Have you experienced difficulties signing in?'
        elif feature == 'passive_session_rate_3m':
            category, text = 'sessions', 'Some recorded sessions had no transactions. Was that consistent with what your team intended to do?'
        elif feature in ('outbound_failure_rate_3m', 'outbound_bank_failure_rate_3m'):
            category, text = 'payment', 'The recorded payment failure rate contributed to this estimate. Have you experienced difficulties completing payments?'
        else:
            continue
        if category not in seen:
            questions.append(dict(source=driver_label(driver), text=text))
            seen.add(category)
    return questions[:3]


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
    review, opened = original['review'], case['original_review']
    ops, finance = latest.get('operations') or {}, latest.get('finance') or {}
    recent, usual = ops.get('combined_flow_mean_3m_myr'), ops.get('combined_flow_mean_12m_myr')
    comparable = number(recent) and number(usual) and usual > 0
    if comparable:
        change = (recent / usual - 1) * 100
        activity = 'Similar to usual' if abs(change) < .05 else f'{abs(change):.1f}% {"lower" if change < 0 else "higher"}'
        activity += ' versus the trailing twelve-month average.'
    else:
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
                signals.append(f'{driver_label(driver)}: {driver_value(driver)} · {direction}')
    tasks = case.get('follow_ups') or []
    follow_rows = []
    for task in tasks:
        event = task['current']
        status = {'planned':'Planned', 'attempted':'Attempted', 'delivered':'Completed', 'cancelled':'Cancelled'}[event['action_status']]
        follow_rows.append([f'{status} · {task["action_type"].replace("_", " ")}',
                            f'{dated(event["action_date"])} · {event.get("recorded_by") or "Not provided"} · {event.get("notes") or "No notes"}'])
    questions = discussion_questions(latest)
    for question in questions:
        question['month'] = month(latest['cutoff_month'])
    trace = [
        ['Case ID', case['case_id']], ['Case version', str(case['version'])],
        ['Original batch', original['batch_id']], ['Original prediction', original['prediction_id']],
        ['Original review version', str((case.get('review_history') or [{}])[0].get('version', 'Not provided'))],
        ['Current review version', str(review['version'])],
        ['Latest batch', latest['batch_id']], ['Latest prediction', latest['prediction_id']],
    ]
    sample = any(sources.get(c['batch_id']) == 'notebook_case_sample' for c in [original, latest])
    snapshot = dict(case_id=case['case_id'], case_version=case['version'], review_version=review['version'],
                    original_prediction_id=original['prediction_id'], latest_prediction_id=latest['prediction_id'],
                    evidence_hash=hashlib.sha256(repo.encode(dict(case=case, sources=sources)).encode()).hexdigest())
    return dict(case_id=case['case_id'], snapshot=snapshot, customer_id=original['cus_id'],
                name=latest.get('customer_name') or original.get('customer_name') or 'Customer '+original['cus_id'],
                # Only these two fields are used by the unchanged, explicitly unavailable AI preview.
                ai_context={k:latest[k] for k in ['cutoff_month', 'calibrated_risk']},
                sample_note='Single-case sample evidence is included. This briefing does not represent a complete portfolio.' if sample else None,
                original=section('At the time of review', [
                    f'{month(original["cutoff_month"])} · Predicted risk {percent(original["calibrated_risk"])}',
                    'Forecast '+forecast(original['cutoff_month']), opened.get('reason') or 'No original rationale supplied.',
                    'Original reviewer: '+(opened.get('reviewer') or 'Not provided'),
                    'Case opened: '+dated(case.get('created_at'))]),
                latest=section('Latest available assessment', [
                    f'{month(latest["cutoff_month"])} · Predicted risk {percent(latest["calibrated_risk"])}',
                    'Forecast '+forecast(latest['cutoff_month']), *latest_notes]),
                activity=section('Observed activity through '+month(latest['cutoff_month']), [activity,
                    'Saved three-month and trailing twelve-month averages ending at this assessment cutoff; no future observations are inferred.', *history_note],
                    [['Latest 3-month average', money(recent)], ['Trailing 12-month average', money(usual)]]),
                signals=section('Signals to investigate', ['Model signals describe influence on the saved estimate, not confirmed complaints, causes or probability-point effects.'], items=signals),
                operations=section('Operations context', [review.get('operations_notes') or 'No committee Operations notes recorded.',
                    'Saved aggregate rates for the latest three months through '+month(latest['cutoff_month'])+'. No monthly service trend is inferred.'], [
                        ['Payment failure rate', percent(ops.get('outbound_failure_rate_3m'))],
                        ['Bank-attributed payment failure rate', percent(ops.get('outbound_bank_failure_rate_3m'))],
                        ['Login difficulty rate', percent(ops.get('login_failure_rate_3m'))],
                        ['Sessions without transactions', percent(ops.get('passive_session_rate_3m'))]]),
                finance=section('Finance context', [review.get('finance_notes') or 'No committee Finance notes recorded.',
                    'Balances are exposures. Fees and waivers are separate historical three-month monthly estimates, not verified profit, actual invoices or retention savings.'], [
                        ['Operating balances', money(finance.get('non_fd_balance_myr'))],
                        ['Fixed-deposit balances', money(finance.get('fd_balance_myr'))],
                        ['Estimated monthly fees', money(finance.get('estimated_monthly_fee_myr'))],
                        ['Estimated monthly waivers', money(finance.get('estimated_monthly_waiver_myr'))]]),
                decision=section('Current committee rationale & next step', [review.get('reason') or 'No rationale supplied.',
                    'Reviewer: '+(review.get('reviewer') or 'Not provided')+' · Review saved: '+dated(review.get('updated_at')),
                    'Owner: '+(case.get('owner') or 'Unassigned')+' · Next follow-up: '+dated(case.get('next_action_date'), 'Not scheduled')+' · Case: '+case['status'].capitalize(),
                    'Plans and recorded contact are separate; consult the case timeline for the full event history.' if tasks else 'No follow-up has been recorded; this briefing can be prepared before outreach.'], follow_rows),
                questions=questions, traceability=trace)


def load(values):
    ids = selected_ids(values)
    db = get_db()
    # One consistent read snapshot across all selected cases and the batch registry.
    db.execute('BEGIN')
    try:
        sources = {r['batch_id']:r['source_kind'] for r in db.execute('SELECT batch_id,source_kind FROM batches')}
        records = [cases.record(cases.case_row(case_id), True) for case_id in ids]
        require(all(c['original']['review']['decision'] == 'prioritise' for c in records),
                'One or more selected cases are no longer prioritised. Return to Reviewed Customers and select currently prioritised cases.')
        items = [document(c, {k:sources[k] for k in {c['original']['batch_id'],c['latest']['batch_id']}}) for c in records]
        return dict(items=items, snapshots=[item['snapshot'] for item in items])
    finally:
        db.rollback()  # Read transaction only. No persisted preparation/export state.
