import React, { useId } from 'react';
import { count, isNumber, millions, money, percent } from '../format.js';

// Every figure comes from the backend finance_metrics payload; nothing here is recalculated.
export const NEGATIVE_TEXT = 'Estimated relationship contribution is negative at the assumed cost; see cost sensitivity.';
export const FSL_A_TEXT = 'Fee waiver condition not met';
export const FSL_B_TEXT = "Deposits don't cover waived transaction cost";
const SIGN_TEXT = 'The sign of these totals depends on both assumptions; both matter equally.';
const COST_CAPTION = 'Cost ratio 1.0 / 0.75 / 0.5: share of the BNM base fee assumed as the bank’s per-transaction cost. Changes transaction cost only.';
const PREMIUM_CAPTION = 'Liquidity premium 0% / 0.5% / 1.0%: term-funding value added to OPR for fixed deposits. Changes fixed deposit earnings only.';

const premiumLabel = key => (Number(key) * 100).toFixed(1) + '%';
const flagLabel = (flagged, policy) => flagged === true ? (policy ? 'Policy' : 'Flagged') : flagged === false ? 'Not flagged' : 'Not provided';

export function SensitivityTable({ title, caption, columns, rows, rowHeader = 'Measure' }) {
  const id = useId();
  return <section className="finance-sensitivity" aria-labelledby={id}>
    <h3 id={id}>{title}</h3>
    <p className="muted">{caption}</p>
    <div className="table-wrap"><table>
      <thead><tr><th scope="col">{rowHeader}</th>{columns.map(c => <th key={c.key} scope="col">{c.label}</th>)}</tr></thead>
      <tbody>{rows.map(row => <tr key={row.label} className={row.secondary ? 'secondary-row' : undefined}>
        <th scope="row">{row.label}</th>{row.values.map((value, i) => <td key={columns[i].key}>{value}</td>)}
      </tr>)}</tbody>
    </table></div>
  </section>;
}

function Sensitivities({ cost, premium }) {
  return <div className="finance-sensitivities">
    <SensitivityTable title="Cost ratio sensitivity" caption={COST_CAPTION} {...cost} />
    <SensitivityTable title="Liquidity premium sensitivity" caption={PREMIUM_CAPTION} {...premium} />
  </div>;
}

const base = (label, isBase) => isBase ? label + ' (base)' : label;

function checkAText(a) {
  if (a.flagged) return [FSL_A_TEXT, 'Fixed deposit below the tier threshold while the waiver is active. Waived fees: ' + money(a.monthly) + ' a month.'];
  return {
    deal_kept: ['Waiver condition met', 'Fixed deposit at or above the tier threshold.'],
    no_active_waiver: ['No active waiver', 'Nothing is waived, so the check does not apply.'],
    policy_exemption: ['Policy exemption', 'Waived by policy, not by a deposit threshold; check A does not apply.'],
  }[a.status] || ['Not provided', 'An input needed for this check is missing.'];
}

function checkBText(b) {
  if (b.flagged && b.policy) return ['Policy', 'Waived transaction cost beyond what deposits earn: ' + money(b.monthly) + ' a month. Shown separately because the waiver is a policy exemption.'];
  if (b.flagged) return ['Flagged', 'Waived transaction cost beyond what deposits earn: ' + money(b.monthly) + ' a month.'];
  return {
    covered: ['Not flagged', 'Fixed deposit earnings cover the waived transaction cost.'],
    no_active_waiver: ['No active waiver', 'Nothing is waived, so the check does not apply.'],
  }[b.status] || ['Not provided', 'An input needed for this check is missing.'];
}

export function CustomerFinanceMetrics({ metrics, risk }) {
  if (!metrics) return null;
  const { components: parts, contribution_monthly: contribution, fsl_a: a, fsl_b: b } = metrics;
  const bShown = b.flagged && !b.policy;
  const [aTitle, aDetail] = checkAText(a), [bTitle, bDetail] = checkBText(b);
  const costCols = metrics.cost_sensitivity.map(v => ({ key: String(v.cost_ratio), label: base(v.cost_ratio.toFixed(2).replace(/0$/, ''), v.cost_ratio === metrics.cost_ratio) }));
  const premiumCols = metrics.sensitivity.map(v => ({ key: String(v.liquidity_premium), label: base(premiumLabel(v.liquidity_premium), v.liquidity_premium === metrics.liquidity_premium) }));
  const rows = (list, first, firstKey) => [
    { label: first, values: list.map(v => money(v[firstKey])) },
    { label: 'Contribution a month', values: list.map(v => money(v.contribution_monthly)) },
    { label: 'Contribution at stake (3 months)', values: list.map(v => money(v.rar_3m)) },
    { label: 'Check B', values: list.map(v => flagLabel(v.fsl_b_flagged, b.policy)) },
  ];
  return <div className="finance-metrics">
    <h3 className="finance-group-title">Relationship contribution (estimate)</h3>
    <div className="finance-stake" role="group" aria-label="Risk and contribution at stake">
      <div><span className="muted">Predicted risk</span><strong>{percent(risk)}</strong></div>
      <div><span className="muted">Contribution at stake (3 months)</span><strong>{money(metrics.rar_3m)}</strong><small className="muted">Shown beside the risk, never multiplied by it.</small></div>
    </div>
    <div className="finance-contribution" role="group" aria-label="Estimated monthly relationship contribution">
      <span className="muted">Estimated relationship contribution</span>
      <strong className="finance-value">{isNumber(contribution) ? money(contribution) + ' a month' : 'Not provided'}</strong>
      {isNumber(contribution) && contribution < 0 && <p className="finance-negative">{NEGATIVE_TEXT}</p>}
      {(a.flagged || bShown) && <ul className="finance-flags">
        {a.flagged && <li>{FSL_A_TEXT}</li>}
        {bShown && <li>{FSL_B_TEXT}</li>}
      </ul>}
    </div>
    {metrics.unavailable.length > 0 && <ul className="finance-unavailable" aria-label="Unavailable inputs">{metrics.unavailable.map(reason => <li key={reason}>Not provided: {reason}</li>)}</ul>}
    <dl className="finance-components">
      <dt>Fee income</dt><dd>{money(parts.fee_income)}</dd>
      <dt>Transaction cost</dt><dd>{isNumber(parts.transaction_cost) ? money(-parts.transaction_cost) : money(null)}</dd>
      <dt>Fixed deposit earnings</dt><dd>{money(parts.fd_earnings)}</dd>
      <dt>Operating-balance earnings</dt><dd>{money(parts.operating_earnings)}</dd>
    </dl>
    <div className="finance-checks">
      <article className="finance-check" aria-label="Check A: deal broken"><h4>Check A · deal broken</h4><strong>{aTitle}</strong><p className="muted">{aDetail}</p></article>
      <article className="finance-check" aria-label="Check B: deal not paying"><h4>Check B · deal not paying</h4><strong>{bTitle}</strong><p className="muted">{bDetail}</p></article>
    </div>
    <p className="muted">Checks A and B overlap and are never added together.</p>
    <Sensitivities cost={{ columns: costCols, rows: rows(metrics.cost_sensitivity, 'Transaction cost a month', 'transaction_cost') }}
      premium={{ columns: premiumCols, rows: rows(metrics.sensitivity, 'Fixed deposit earnings a month', 'fd_earnings') }} />
    <p className="muted">Monthly estimates at OPR {percent(metrics.opr, 2)} and SRR {percent(metrics.srr, 2)}. Balances are exposures; fees and waivers are estimates, not audited profit.</p>
  </div>;
}

const GROUPS = [
  ['FD_THRESHOLD', 'FD-threshold tiers', 'SME_S, SME_M, CORP_L'],
  ['POLICY_EXEMPT', 'Policy-exempt tiers', 'CORP_XL, GOV'],
];
const pair = (customers, monthly) => count(customers) + ' customers · ' + money(monthly) + ' a month';

function GroupPanel({ title, tiers, group, policy }) {
  return <article className="finance-group" aria-label={title}>
    <h3>{title}</h3><p className="muted">{tiers} · {count(group.available)} of {count(group.customers)} customers available</p>
    <span className="muted">Contribution at stake (3 months)</span>
    <strong className="finance-value">{millions(group.rar_3m)}</strong>
    {group.rar_3m < 0 && <p className="finance-negative">{NEGATIVE_TEXT}</p>}
    <dl>
      <dt>Check A · deal broken</dt><dd>{policy ? 'Policy exemption: not checked' : pair(group.fsl_a_customers, group.fsl_a_monthly)}</dd>
      <dt>{policy ? 'Check B · policy' : 'Check B · deal not paying'}</dt><dd>{policy ? pair(group.policy_fsl_b_customers, group.policy_fsl_b_monthly) : pair(group.fsl_b_customers, group.fsl_b_monthly)}</dd>
    </dl>
  </article>;
}

export function PortfolioFinanceMetrics({ metrics }) {
  if (!metrics) return null;
  const { totals } = metrics;
  const groups = GROUPS.filter(([key]) => metrics.by_basis[key]);
  const row = (key, label) => ({ key, label, group: key === 'total' ? totals : metrics.by_basis[key] });
  const rows = [...groups.map(([key, label]) => row(key, label)), { ...row('total', 'All customers combined'), secondary: true }];
  const table = (field, order, columnLabel, baseKey) => {
    // JSON object keys arrive sorted; the column order comes from the backend's own list.
    const keys = order.map(value => Object.keys(totals[field]).find(k => Number(k) === value)).filter(Boolean);
    return {
      rowHeader: 'Group',
      columns: keys.map(k => ({ key: k, label: base(columnLabel(k), Number(k) === baseKey) })),
      rows: rows.map(r => ({ label: r.label, secondary: r.secondary, values: keys.map(k => millions(r.group[field][k].rar_3m)) })),
    };
  };
  const tiers = Object.entries(metrics.by_tier);
  return <div className="finance-metrics">
    <p className="muted">Contribution at stake is three months of estimated relationship contribution (fee income − transaction cost + deposit and operating-balance earnings). It is shown beside predicted risk and never multiplied by it. Base case: cost ratio {metrics.cost_ratio.toFixed(1)}, liquidity premium {premiumLabel(metrics.liquidity_premium)}.</p>
    <div className="finance-groups">{groups.map(([key, label, names]) => <GroupPanel key={key} title={label} tiers={names} group={metrics.by_basis[key]} policy={key === 'POLICY_EXEMPT'} />)}</div>
    <p className="muted">Checks A and B overlap and are never added together. Policy-exempt check B results are totalled separately.</p>
    <p className="finance-sign">{SIGN_TEXT}</p>
    <Sensitivities cost={table('cost_sensitivity', metrics.cost_ratios, k => k, metrics.cost_ratio)}
      premium={table('premium_sensitivity', metrics.liquidity_premiums, premiumLabel, metrics.liquidity_premium)} />
    <p className="finance-combined muted">All customers combined (secondary): {millions(totals.rar_3m)} contribution at stake · check A {pair(totals.fsl_a_customers, totals.fsl_a_monthly)} · check B {pair(totals.fsl_b_customers, totals.fsl_b_monthly)} · check B policy {pair(totals.policy_fsl_b_customers, totals.policy_fsl_b_monthly)}</p>
    <details><summary>By tier</summary><div className="table-wrap"><table>
      <thead><tr><th scope="col">Tier</th><th scope="col">Customers</th><th scope="col">Contribution at stake (3 months)</th><th scope="col">Check A</th><th scope="col">Check B</th><th scope="col">Check B · policy</th></tr></thead>
      <tbody>{tiers.map(([tier, g]) => <tr key={tier}><th scope="row">{tier}</th><td>{count(g.customers)}</td><td>{millions(g.rar_3m)}</td><td>{pair(g.fsl_a_customers, g.fsl_a_monthly)}</td><td>{pair(g.fsl_b_customers, g.fsl_b_monthly)}</td><td>{pair(g.policy_fsl_b_customers, g.policy_fsl_b_monthly)}</td></tr>)}</tbody>
    </table></div></details>
    <p className="muted">{metrics.note}</p>
  </div>;
}
