"""Versioned allowlist of cutoff-safe business facts. No outcome/review joins for summaries."""
import hashlib
import json
from flask import abort
from . import repository as repo, cases, briefings
from .validation import validate_record, require
from .db import get_db

VERSION = 'm6-evidence-3'  # m6-evidence-3: collections (inbound) / payments (outbound) terminology.
# Definitions intentionally cover only verified existing UI/export concepts.
# Unknown predictors are excluded, even if the export provides a plausible label.
DICTIONARY = {
 'combined_flow_mean_1m_myr': ('Combined transaction flow', 'Activity', 'MYR/month', 1, 'Recorded monthly combined transaction flow'),
 'combined_flow_mean_3m_myr': ('Recent transaction flow', 'Activity', 'MYR/month', 3, 'Mean combined transaction flow'),
 'combined_flow_mean_12m_myr': ('Trailing transaction flow', 'Activity', 'MYR/month', 12, 'Mean combined transaction flow'),
 'combined_flow_ratio_3m_to_12m': ('Transaction activity', 'Activity', 'baseline ratio', 3, 'Recent mean as a proportion of the trailing mean; not a reduction'),
 'inbound_flow_ratio_3m_to_12m': ('Collections', 'Activity', 'baseline ratio', 3, 'Recent collections mean as a proportion of trailing mean; not a reduction'),
 'outbound_flow_ratio_3m_to_12m': ('Payments', 'Activity', 'baseline ratio', 3, 'Recent payments mean as a proportion of trailing mean; not a reduction'),
 'login_failure_rate_3m': ('Login difficulties', 'Operations', 'rate', 3, 'Recorded login failure rate; cause and customer experience unknown'),
 'outbound_failure_rate_3m': ('Payment failures', 'Operations', 'rate', 3, 'Recorded payment failure rate; cause and complaint unknown'),
 'outbound_bank_failure_rate_3m': ('Bank-attributed payment failures', 'Operations', 'rate', 3, 'Recorded bank-attributed failure rate; precise technical cause unknown'),
 'passive_session_rate_3m': ('Sessions without transactions', 'Operations', 'rate', 3, 'Recorded session rate; customer intention unknown'),
 'fd_maturing_30d_count': ('Fixed deposits approaching maturity', 'Finance', 'count', 0, 'Deposits scheduled to mature within thirty days of cutoff; no inference of withdrawal'),
 'fd_balance_myr': ('Fixed deposit balances', 'Finance', 'MYR', 0, 'Recorded exposure at cutoff; not profit'),
 'non_fd_balance_myr': ('Operating account balances', 'Finance', 'MYR', 0, 'Recorded exposure at cutoff; not profit'),
 'estimated_fee_mean_3m_myr': ('Estimated monthly fees', 'Finance', 'MYR/month estimate', 3, 'Historical monthly estimate; not verified profit or guaranteed savings'),
 'estimated_waiver_mean_3m_myr': ('Estimated monthly waivers', 'Finance', 'MYR/month estimate', 3, 'Separate historical monthly estimate; not intervention costs or proof of unprofitability'),
 # m6-evidence-2: recency/frequency definitions copied from the research project's
 # data/features_v1/feature_dictionary.csv (read-only source). Null = no event yet or an
 # incomplete window, and is omitted; there are no sentinel values.
 'outbound_count_mean_3m': ('Successful payments per month', 'Operations', 'transactions/month', 3, 'Mean monthly count of successful payments over trailing 3 months'),
 'outbound_count_mean_12m': ('Usual successful payments per month', 'Operations', 'transactions/month', 12, 'Mean monthly count of successful payments over trailing 12 months'),
 'outbound_success_recency_days': ('Days since last successful payment', 'Operations', 'days', 0, 'Calendar days from last known successful payment date to cutoff'),
 'login_success_count_mean_3m': ('Successful logins per month', 'Operations', 'events/month', 3, 'Mean monthly login success count over trailing 3 months'),
 'login_success_count_mean_12m': ('Usual successful logins per month', 'Operations', 'events/month', 12, 'Mean monthly login success count over trailing 12 months'),
 'login_success_recency_days': ('Days since last successful login', 'Operations', 'days', 0, 'Calendar days since last successful login available by cutoff'),
}
EVENT_UNITS = ('days', 'transactions/month', 'events/month')


def period(cutoff, months):
    if not months:
        return dict(as_of=cutoff)
    year, index = divmod(int(cutoff[:4])*12 + int(cutoff[5:7]) - months, 12)
    return dict(start=f'{year:04d}-{index+1:02d}-01', end=cutoff, months=months)


def build(purpose, record_id):
    case = None
    if purpose == 'discussion':
        case = cases.record(cases.case_row(record_id), True)
        require(case['current_review']['decision'] == 'prioritise', 'Case is no longer prioritised for RM.')
        prediction_id = case['latest']['prediction_id']
    else:
        prediction_id = record_id
    row = repo.prediction_row(prediction_id)
    if row is None:
        abort(404, description='Prediction not found')
    saved = json.loads(row['evidence_json'])
    validate_record(saved)  # Complete sum, clipping term, reference and raw calibration checks.
    require(saved['cus_id'] == row['cus_id'] and saved['cutoff_month'] == row['cutoff_month']
            and saved['calibrated_risk'] == row['risk'] and saved['review_alert'] == row['review_alert'],
            'Saved prediction identity is inconsistent.')
    features = json.loads(row['features_json'])
    cutoff = saved['cutoff_month']
    source = dict(batch_id=row['batch_id'], prediction_id=prediction_id)
    facts = {}
    def add(key, label, value, units, observation, meaning, kind='recorded_observation', direction=None, group=None):
        if value is None:
            return
        if units.startswith('MYR') or units in ('rate','probability','baseline ratio','count')+EVENT_UNITS:
            require(briefings.number(value), 'Non-numeric saved business fact')
        if units in ('rate','probability'):
            require(0 <= value <= 1, 'Saved rate/probability outside its units')
        if units in ('baseline ratio','count')+EVENT_UNITS:
            require(value >= 0, 'Negative saved count/ratio')
        if units.startswith('MYR'):
            display = briefings.money(value) + (' per month (historical estimate)' if 'estimate' in units else ' per month' if '/month' in units else '')
        elif units == 'baseline ratio':
            display = briefings.percent(value, 2) + ' of the trailing twelve-month average'
        elif units in ('rate', 'probability'):
            display = briefings.percent(value, 2)
        elif units == 'days':
            display = f'{value:,.0f} days'
        elif units in EVENT_UNITS:
            display = f'{value:,.1f} per month'
        else:
            display = str(value)
        # A full typed clause protects meaning as well as the number during substitution.
        clause = f'{label}: {display}'
        if direction:
            clause += f'; contributed toward a {direction} saved model estimate'
        if 'start' in observation:
            clause += f' (recorded {observation["start"]} to {observation["end"]})'
        elif 'as_of' in observation:
            clause += f' (as of {observation["as_of"]})'
        elif 'forecast' in observation:
            clause += f' (forecast {observation["forecast"]}, assessment cutoff {observation["cutoff"]})'
        facts[key] = dict(id=key, label=label, value=value, display=display, clause=clause,
            units=units, period=observation, meaning=meaning, kind=kind, direction=direction, group=group,
            source=source, eligible_for=['statement','question'],
            coverage='Available saved aggregate; constituent observation completeness is not independently established')
    add('prediction.risk', 'Predicted volume-drop risk', saved['calibrated_risk'], 'probability',
        dict(cutoff=cutoff, forecast=briefings.forecast(cutoff)), 'Defined next-three-month volume drop, not account closure')
    add('prediction.threshold', 'Saved review threshold', saved['probability_cutoff'], 'probability', dict(as_of=cutoff), 'Queue policy; distinct from half-of-baseline outcome rule')
    add('prediction.flag', 'Saved review alert', bool(saved['review_alert']), 'boolean', dict(as_of=cutoff), 'Saved full precision flag; never inferred from rounded risk')
    for feature, definition in DICTIONARY.items():
        label, group, units, months, meaning = definition
        add('feature.'+feature, label, features.get(feature), units, period(cutoff, months), meaning, group=group)
    recent, usual = features.get('combined_flow_mean_3m_myr'), features.get('combined_flow_mean_12m_myr')
    if briefings.number(recent) and briefings.number(usual) and usual > 0:
        ratio = recent / usual
        text = f'{ratio*100:.2f}% of the trailing twelve-month average'
        text += f' ({abs(1-ratio)*100:.2f}% {"lower" if ratio < 1 else "higher"})' if ratio != 1 else ' (unchanged)'
        add('activity.comparison', 'Recorded recent activity', text, 'derived comparison',
            dict(recent=period(cutoff,3), baseline=period(cutoff,12)), 'Deterministic comparison of historical averages, not forecast outcome')
    for key, direction in [('higher_risk_drivers','higher'), ('lower_risk_drivers','lower')]:
        for driver in saved[key]:
            feature = driver['feature']
            if feature in features:
                actual,expected=driver['value'],features[feature]
                matches=(abs(actual-expected)<=1e-8*max(1,abs(actual))
                    if briefings.number(actual) and briefings.number(expected) else actual==expected)
                require(matches, 'Feature and saved model signal values disagree.')
            if feature not in DICTIONARY:
                continue
            label, group, units, months, meaning = DICTIONARY[feature]
            fact_id = 'signal.'+feature
            add(fact_id, label, driver['value'], units, period(cutoff,months), meaning,
                'model_signal', direction, group)
            if fact_id in facts:
                facts[fact_id]['contribution_logodds'] = driver['contribution_logodds']
                facts[fact_id]['attribution_units'] = saved['explanation_units']
    # Only explicitly whitelisted historical flow fields through this assessment cutoff.
    supplement = get_db().execute('SELECT flows_json FROM supplemental_evidence WHERE prediction_id=?',(prediction_id,)).fetchone()
    flows = json.loads(supplement['flows_json']) if supplement and json.loads(supplement['flows_json']) else json.loads(row['flows_json'])
    for flow in flows[-12:]:
        observation_month=flow.get('snapshot_month')
        if not isinstance(observation_month,str) or observation_month>cutoff:
            continue
        for key,label in [('combined_flow_myr','Combined monthly flow'),('inbound_myr','Monthly collections'),('outbound_success_myr','Successful monthly payments')]:
            value=flow.get(key)
            if briefings.number(value):
                add('flow.'+observation_month.replace('-','')+'.'+key,label,value,'MYR',dict(as_of=observation_month),
                    'Recorded monthly flow, not a future outcome',group='Activity')
    identity = dict(purpose=purpose, batch_id=row['batch_id'], prediction_id=prediction_id,
        customer_id=row['cus_id'], cutoff=cutoff, protocol=saved['protocol_sha256'], model=saved['model'],
        feature_version='1.0.0', dictionary_version=VERSION)
    context = None
    if case:
        review = case['current_review']
        original = case['original']
        validate_record(original['explanation'])
        add('committee.original_assessment', 'Original reviewed assessment',
            briefings.month(original['cutoff_month'])+'; saved predicted volume-drop risk '+briefings.percent(original['calibrated_risk'],2),
            'dated assessment',dict(assessment=original['cutoff_month']),
            'Original reviewed prediction; separate from latest assessment', 'recorded_committee_context')
        facts['committee.original_assessment']['source'] = dict(batch_id=original['batch_id'],prediction_id=original['prediction_id'])
        # Human text stays local: send opaque references, never personal names or raw notes.
        context = dict(case_id=case['case_id'], case_version=case['version'],
            original_prediction_id=case['original']['prediction_id'], original_cutoff=case['original']['cutoff_month'],
            current_review=review, latest_prediction_id=prediction_id,
            follow_ups=case.get('follow_ups',[]))
        add('committee.context', 'Human-recorded committee rationale', review.get('reason') or 'No rationale supplied',
            'quoted human context', dict(assessment=review['assessment_month'], saved=review.get('updated_at')),
            'Attributed human assessment; not independently verified bank fact', 'recorded_committee_context')
        facts['committee.context']['clause'] = 'The committee recorded the following rationale (human assessment): '+(review.get('reason') or 'No rationale supplied')
        for name in ['operations_notes','finance_notes']:
            if review.get(name):
                add('committee.'+name, 'Human-recorded '+name.replace('_',' '), review[name][:2000],
                    'quoted human context', dict(assessment=review['assessment_month'], saved=review.get('updated_at')),
                    'Attributed human assessment, not verified fact', 'recorded_committee_context')
        identity['original_assessment_cutoff']=case['original']['cutoff_month']
        identity['committee_assessment_cutoff']=review['assessment_month']
        for index,task in enumerate((case.get('follow_ups') or [])[:5]):
            event=task['current']
            add('committee.followup_'+str(index), 'Dated human-recorded follow-up',
                task['action_type'].replace('_',' ')+'; '+event['action_status']+'; '+str(event.get('action_date') or 'date unavailable'),
                'human workflow record',dict(event_date=event.get('action_date'),recorded_at=event.get('recorded_at')),
                'Workflow record; not evidence of retention effectiveness or information used in earlier prediction',
                'recorded_committee_context')
    semantic = dict(identity=identity, facts=facts, context=context, explanation=saved)
    fingerprint = hashlib.sha256(repo.encode(semantic).encode()).hexdigest()
    return dict(**semantic, evidence_hash=fingerprint)


def external(evidence):
    """No customer/batch/case IDs, names, paths, attribution or free-text notes leave the server."""
    if evidence['identity']['purpose'] == 'summary':
        from .ai_render import provider_payload  # Summary card: the server's own sentences per section.
        return provider_payload(evidence)
    facts = []
    for fact in evidence['facts'].values():
        # Monthly combined totals provide the trajectory; collections/payments ratios above
        # already supply the channel comparison. Keep redundant monthly channels local.
        if fact['id'].startswith('flow.') and not fact['id'].endswith('.combined_flow_myr'):
            continue
        entry = {k:v for k,v in fact.items() if k not in ('source','clause','value','display')}
        entry['placeholder'] = '{{'+fact['id']+'}}'
        if fact['kind'] == 'recorded_committee_context':
            entry['meaning'] = 'Locally resolved quoted human rationale. You may reference this placeholder, but cannot interpret its unsent contents.'
        else:
            entry.update(value=fact['value'], display=fact['display'])
        facts.append(entry)
    return dict(customer='Customer A', purpose=evidence['identity']['purpose'], cutoff=evidence['identity']['cutoff'],
        original_assessment_cutoff=evidence['identity'].get('original_assessment_cutoff'),
        committee_assessment_cutoff=evidence['identity'].get('committee_assessment_cutoff'),
        facts=facts, limits='SHAP explains the estimate, not causes or changes over time. Balances are exposures. Unknown motives and future outcomes must remain unknown.')
