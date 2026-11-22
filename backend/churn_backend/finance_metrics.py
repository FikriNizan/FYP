"""Revenue at Risk (RaR) and Fee Subsidy Leakage (FSL), IR Objective 3.

Deterministic, monthly MYR estimates at the assessment cutoff, computed from each prediction's saved
features. See docs/FINANCE_METRICS.md for every formula, parameter, source and limitation. These are
estimates of relationship contribution: not audited profit, not expected loss.
"""
import math
from datetime import date
from collections import defaultdict
from .db import get_db
import json

# Tier terms from the research project's data/final_v4_0_1/cleaned/ref_corporate_tier.csv
# (sha256 0fa6e1c72c7f183ec0d1255c2a6dc02dfaa10c3dcadfdb194b72c288d2817f98, read-only source).
# waiver_basis is uniform per customer and fully determined by tier in fee_matrix_clean.csv
# (sha256 2df2b489b18cc6ada3a60df99c7a1564fd6b9a0c8b1427142ffac96ab8b7041f): verified 1000/1000 customers.
# Verified for all 14,000 contracts: standard = bnm_base_fee x (1 + markup); effective = standard x (1 - waiver_pct).
TIER_TERMS = {
    'SME_S': dict(markup=0.40, fd_threshold_myr=100000.0, basis='FD_THRESHOLD'),
    'SME_M': dict(markup=0.30, fd_threshold_myr=500000.0, basis='FD_THRESHOLD'),
    'CORP_L': dict(markup=0.15, fd_threshold_myr=2000000.0, basis='FD_THRESHOLD'),
    'CORP_XL': dict(markup=0.05, fd_threshold_myr=5000000.0, basis='POLICY_EXEMPT'),
    'GOV': dict(markup=0.05, fd_threshold_myr=3000000.0, basis='POLICY_EXEMPT'),
}
# Bank Negara Malaysia rates, checked against the official pages. Only verified ranges are listed;
# a cutoff outside them makes the measures unavailable rather than guessed.
OPR_TABLE = [
    dict(start='2023-05-03', end='2024-07-10', rate=0.03,
         source='BNM Monetary Policy Statement 3 May 2023 (https://www.bnm.gov.my/-/monetary-policy-statement-03052023); '
                'held at 24 Jan 2024, 7 Mar 2024 and 9 May 2024 MPC meetings (https://www.bnm.gov.my/monetary-stability/opr-decisions)'),
]
SRR_TABLE = [
    dict(start='2020-03-20', end='2025-05-15', rate=0.02,
         source='BNM 19 Mar 2020: SRR lowered from 3.00% to 2.00% effective 20 March 2020'),
    dict(start='2025-05-16', end=None, rate=0.01,
         source='BNM 8 May 2025: SRR lowered from 2% to 1% effective 16 May 2025 (https://www.bnm.gov.my/-/srr-0525)'),
]
# Fail closed after the last verified OPR date: later cutoffs show Finance contribution as unavailable.
OPR_VERIFIED_THROUGH = max(row['end'] for row in OPR_TABLE)
_through = date.fromisoformat(OPR_VERIFIED_THROUGH)
SRR_UNVERIFIED = 'SRR not verified for this cutoff'
OPR_UNVERIFIED = f'OPR not verified for this cutoff (verified rates end {_through.day} {_through:%b %Y})'
BASE_PREMIUM = 0.005
LIQUIDITY_PREMIUMS = (0.0, 0.005, 0.01)
# Share of bnm_base_fee assumed as the bank's per-transaction cost. bnm_base_fee is a customer price cap; without
# actual cost data the direction of bias is uncertain. 1.0 is the base case. This assumption decides the headline sign.
BASE_COST_RATIO = 1.0
COST_RATIOS = (1.0, 0.75, 0.5)
WINDOW_MONTHS = 3


def number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def rate_on(table, cutoff):
    day = str(cutoff)[:10]
    for row in table:
        if row['start'] <= day and (row['end'] is None or day <= row['end']):
            return row
    return None


def fd_earnings(fd_balance, offer_rate, opr, premium, srr):
    """FD value to the bank: balance x ((1 - SRR) x (OPR + liquidity premium) - rate paid) / 12. The SRR share of
    the deposit is held at BNM and earns nothing; the rate paid is on the full balance. Can be negative when the
    rate paid exceeds the funding value; never clipped. A genuine zero balance earns zero."""
    if not number(fd_balance):
        return None, 'fixed deposit balance missing'
    if fd_balance == 0:
        return 0.0, None
    if not number(offer_rate):
        return None, 'fixed deposit offer rate missing'
    if opr is None:
        return None, OPR_UNVERIFIED
    if srr is None:
        return None, SRR_UNVERIFIED
    return fd_balance * ((1 - srr) * (opr + premium) - offer_rate) / 12, None


def customer_metrics(features, cutoff, premium=BASE_PREMIUM, with_sensitivity=True, cost_ratio=BASE_COST_RATIO):
    features = features or {}
    reasons = []
    tier_id = features.get('tier_id')
    tier = TIER_TERMS.get(tier_id)
    opr_row, srr_row = rate_on(OPR_TABLE, cutoff), rate_on(SRR_TABLE, cutoff)
    opr = opr_row['rate'] if opr_row else None
    srr = srr_row['rate'] if srr_row else None
    if tier is None:
        reasons.append('unknown tier')
    if opr is None:
        reasons.append(OPR_UNVERIFIED)
    if srr is None:
        reasons.append(SRR_UNVERIFIED)
    fee, waiver = features.get('estimated_fee_mean_3m_myr'), features.get('estimated_waiver_mean_3m_myr')
    operating, fd = features.get('non_fd_balance_myr'), features.get('fd_balance_myr')
    fee_income = fee if number(fee) else None
    if fee_income is None:
        reasons.append('estimated fees missing')
    cost = (fee + waiver) / (1 + tier['markup']) * cost_ratio if tier and number(fee) and number(waiver) else None
    if cost is None and tier and not number(waiver):
        reasons.append('estimated waivers missing')
    fd_value, fd_reason = fd_earnings(fd, features.get('fd_balance_weighted_offer_rate'), opr, premium, srr)
    if fd_reason and fd_reason not in reasons:
        reasons.append(fd_reason)
    if not number(operating):
        reasons.append('operating account balance missing')
    operating_value = operating * (1 - srr) * opr / 12 if number(operating) and opr is not None and srr is not None else None
    parts = [fee_income, cost, fd_value, operating_value]
    contribution = fee_income - cost + fd_value + operating_value if all(p is not None for p in parts) else None
    waiver_pct = features.get('catalog_waiver_mean_pct')
    active = waiver_pct > 0 if number(waiver_pct) else None
    basis = tier['basis'] if tier else None

    # FSL A ("deal broken"): FD_THRESHOLD waiver still active while the FD is below the tier threshold.
    if tier is None or active is None or not number(fd):
        fsl_a = dict(status='unavailable', flagged=False, monthly=None)
    elif basis == 'POLICY_EXEMPT':
        fsl_a = dict(status='policy_exemption', flagged=False, monthly=None)
    elif not active:
        fsl_a = dict(status='no_active_waiver', flagged=False, monthly=None)
    elif fd < tier['fd_threshold_myr']:
        fsl_a = dict(status='deal_broken', flagged=number(waiver), monthly=waiver if number(waiver) else None)
    else:
        fsl_a = dict(status='deal_kept', flagged=False, monthly=None)

    # FSL B ("deal not paying", owner rule 2026-11-22): the assumed transaction cost exceeds fee income
    # (a positive shortfall) and positive fixed deposit earnings do not cover it. Uncovered = shortfall - max(FD, 0).
    # Negative FD earnings are not folded into B; they stay visible as their own component.
    policy = basis == 'POLICY_EXEMPT'
    if active is None or cost is None or fee_income is None or fd_value is None:
        fsl_b = dict(status='unavailable', flagged=False, monthly=None, policy=policy)
    elif not active:
        fsl_b = dict(status='no_active_waiver', flagged=False, monthly=None, policy=policy)
    else:
        gap = cost - fee_income
        covered = max(fd_value, 0.0)
        flagged = gap > 0 and covered < gap
        fsl_b = dict(status=('policy' if policy else 'deal_not_paying') if flagged else 'covered', flagged=flagged,
                     monthly=gap - covered if flagged else None, shortfall=max(0.0, gap), policy=policy)

    result = dict(cutoff=str(cutoff)[:10], tier_id=tier_id, waiver_basis=basis, active_waiver=active,
                  fd_threshold_myr=tier['fd_threshold_myr'] if tier and basis == 'FD_THRESHOLD' else None,
                  opr=opr, srr=srr, liquidity_premium=premium, cost_ratio=cost_ratio, window_months=WINDOW_MONTHS,
                  components=dict(fee_income=fee_income, transaction_cost=cost, fd_earnings=fd_value,
                                  operating_earnings=operating_value),
                  contribution_monthly=contribution,
                  rar_3m=WINDOW_MONTHS * contribution if contribution is not None else None,
                  fsl_a=fsl_a, fsl_b=fsl_b, unavailable=reasons,
                  sources=dict(opr=opr_row['source'] if opr_row else None, srr=srr_row['source'] if srr_row else None))
    if with_sensitivity:
        result['sensitivity'] = []
        for value in LIQUIDITY_PREMIUMS:
            variant = customer_metrics(features, cutoff, value, with_sensitivity=False, cost_ratio=cost_ratio)
            result['sensitivity'].append(dict(liquidity_premium=value, fd_earnings=variant['components']['fd_earnings'],
                                              contribution_monthly=variant['contribution_monthly'], rar_3m=variant['rar_3m'],
                                              fsl_b_flagged=variant['fsl_b']['flagged']))
        result['cost_sensitivity'] = []
        for ratio in COST_RATIOS:
            variant = customer_metrics(features, cutoff, premium, with_sensitivity=False, cost_ratio=ratio)
            result['cost_sensitivity'].append(dict(cost_ratio=ratio, transaction_cost=variant['components']['transaction_cost'],
                                                   contribution_monthly=variant['contribution_monthly'], rar_3m=variant['rar_3m'],
                                                   fsl_b_flagged=variant['fsl_b']['flagged'], fsl_b_monthly=variant['fsl_b']['monthly']))
    return result


def _group():
    return dict(customers=0, available=0, rar_3m=0.0, fsl_a_customers=0, fsl_a_monthly=0.0, fsl_b_customers=0,
                fsl_b_monthly=0.0, both_customers=0, policy_fsl_b_customers=0, policy_fsl_b_monthly=0.0,
                negative_fd_earnings=0, negative_rar_customers=0,
                cost_sensitivity={str(r): dict(rar_3m=0.0, negative_rar_customers=0, fsl_b_customers=0, fsl_b_monthly=0.0)
                                  for r in COST_RATIOS},
                premium_sensitivity={str(p): dict(rar_3m=0.0) for p in LIQUIDITY_PREMIUMS})


def _add(group, metrics):
    group['customers'] += 1
    if metrics['rar_3m'] is not None:
        group['available'] += 1
        group['rar_3m'] += metrics['rar_3m']
    a, b = metrics['fsl_a'], metrics['fsl_b']
    if a['flagged']:
        group['fsl_a_customers'] += 1
        group['fsl_a_monthly'] += a['monthly']
    if b['flagged'] and b['policy']:
        group['policy_fsl_b_customers'] += 1
        group['policy_fsl_b_monthly'] += b['monthly']
    elif b['flagged']:
        group['fsl_b_customers'] += 1
        group['fsl_b_monthly'] += b['monthly']
    if a['flagged'] and b['flagged'] and not b['policy']:
        group['both_customers'] += 1
    fd_value = metrics['components']['fd_earnings']
    if fd_value is not None and fd_value < 0:
        group['negative_fd_earnings'] += 1
    if metrics['rar_3m'] is not None and metrics['rar_3m'] < 0:
        group['negative_rar_customers'] += 1
    for variant in metrics['cost_sensitivity']:
        if variant['rar_3m'] is None:
            continue
        bucket = group['cost_sensitivity'][str(variant['cost_ratio'])]
        bucket['rar_3m'] += variant['rar_3m']
        bucket['negative_rar_customers'] += variant['rar_3m'] < 0
        if variant['fsl_b_flagged'] and not b['policy']:
            bucket['fsl_b_customers'] += 1
            bucket['fsl_b_monthly'] += variant['fsl_b_monthly']
    for variant in metrics['sensitivity']:
        if variant['rar_3m'] is not None:
            group['premium_sensitivity'][str(variant['liquidity_premium'])]['rar_3m'] += variant['rar_3m']


def portfolio(batch_id):
    """Totals by tier and by flagged / not flagged, with coverage. A and B overlap: never add them."""
    rows = get_db().execute('SELECT p.review_alert, p.features_json, b.cutoff_month FROM predictions p '
                            'JOIN batches b ON b.batch_id=p.batch_id WHERE p.batch_id=?', (batch_id,)).fetchall()
    total, tiers, flags, bases = _group(), defaultdict(_group), defaultdict(_group), defaultdict(_group)
    cutoff = None
    for row in rows:
        cutoff = row['cutoff_month']
        metrics = customer_metrics(json.loads(row['features_json']), cutoff)
        for group in (total, tiers[metrics['tier_id'] or 'unknown'], flags['flagged' if row['review_alert'] else 'not_flagged'],
                      bases[metrics['waiver_basis'] or 'unknown']):
            _add(group, metrics)
    bases_tiers = {basis: [tier for tier, terms in TIER_TERMS.items() if terms['basis'] == basis]
                   for basis in ('FD_THRESHOLD', 'POLICY_EXEMPT')}
    return dict(cutoff=cutoff, liquidity_premium=BASE_PREMIUM, cost_ratio=BASE_COST_RATIO, cost_ratios=list(COST_RATIOS),
                bases_tiers=bases_tiers, opr_verified_through=OPR_VERIFIED_THROUGH,
                opr_verified=cutoff is not None and rate_on(OPR_TABLE, cutoff) is not None,
                liquidity_premiums=list(LIQUIDITY_PREMIUMS), window_months=WINDOW_MONTHS, totals=total,
                by_basis=dict(sorted(bases.items())), by_tier=dict(sorted(tiers.items())), by_flag=dict(sorted(flags.items())),
                note='Contribution at stake is an estimate of relationship contribution, not audited profit. '
                     'Fee subsidy leakage checks A and B overlap; their totals must not be added.')
