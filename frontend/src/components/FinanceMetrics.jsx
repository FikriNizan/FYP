import React, { useId } from 'react';
import { count, millions, money, tierLabel } from '../format.js';
import Icon from './Icon.jsx';

// Every figure comes from the backend finance_metrics payload; nothing here is recalculated.
export const NEGATIVE_TEXT = 'Estimated relationship contribution is negative at the assumed cost; see cost sensitivity.';
export const FSL_A_TEXT = 'Fee waiver condition not met';
export const FSL_B_TEXT = "Fixed deposits don't cover waived transaction cost.";
export const SIGN_TEXT = 'The sign of these totals depends on both assumptions; both matter equally.';
export const DEFINITION = 'Contribution at stake = three months of estimated fees, minus assumed transaction cost, plus deposit earnings. An estimate, not audited profit.';

const premiumLabel = key => (Number(key) * 100).toFixed(1) + '%';
const base = (label, isBase) => isBase ? label + ' (base)' : label;

// One component for both sensitivities: same heading level, same rows, always visible.
export function SensitivityTable({ title, caption, columns, rows, rowHeader = 'Group' }) {
  const id = useId();
  return <section className="panel finance-sensitivity" aria-labelledby={id}>
    <h2 id={id}>{title}</h2>
    <p className="muted">{caption}</p>
    <div className="table-wrap"><table className="sens">
      <thead><tr><th scope="col">{rowHeader}</th>{columns.map(c => <th key={c.key} scope="col">{c.label}</th>)}</tr></thead>
      <tbody>{rows.map(row => <tr key={row.label} className={row.secondary ? 'secondary-row' : undefined}>
        <th scope="row">{row.label}</th>{row.values.map((value, i) => <td key={columns[i].key}>{value}</td>)}
      </tr>)}</tbody>
    </table></div>
  </section>;
}

const GROUPS = [
  ['FD_THRESHOLD', 'Tiers with a deposit condition', 'Deposit-condition tiers', 'safe', ''],
  ['POLICY_EXEMPT', 'Policy-exempt tiers', 'Policy-exempt tiers', 'bank', 'teal'],
];
const pair = (customers, monthly) => count(customers) + ' customers · ' + money(monthly) + ' a month';

function GroupCard({ title, tiers, group, policy, icon, tone }) {
  return <article className={'finance-card' + (policy ? ' estimate' : '')} aria-label={title}>
    <div className="finance-top"><span className={'round ' + tone}><Icon name={icon} /></span><div><h3>{title}</h3><p className="muted">{tiers.map(tierLabel).join(', ')}</p></div></div>
    <strong className={'gval ' + (group.rar_3m < 0 ? 'neg' : group.rar_3m > 0 ? 'pos' : '')}>{millions(group.rar_3m)}</strong>
    <p className="muted">Contribution at stake, next 3 months · {count(group.available)} of {count(group.customers)} customers available</p>
    {group.rar_3m < 0 && <p className="finance-negative">{NEGATIVE_TEXT}</p>}
    <dl className="finance-group-checks">
      <dt>{FSL_A_TEXT}</dt><dd>{policy ? 'Policy exemption: not checked' : pair(group.fsl_a_customers, group.fsl_a_monthly)}</dd>
      <dt>{policy ? 'Waived transaction cost not covered by fixed deposits (policy exemption)' : "Fixed deposits don't cover waived transaction cost"}</dt><dd>{policy ? pair(group.policy_fsl_b_customers, group.policy_fsl_b_monthly) : pair(group.fsl_b_customers, group.fsl_b_monthly)}</dd>
    </dl>
  </article>;
}

export function PortfolioFinanceMetrics({ metrics }) {
  if (!metrics) return null;
  const { totals } = metrics;
  const groups = GROUPS.filter(([key]) => metrics.by_basis[key]);
  const rows = [...groups.map(([key, , rowLabel]) => ({ label: rowLabel, group: metrics.by_basis[key] })), { label: 'All customers', group: totals, secondary: true }];
  const table = (field, order, columnLabel, baseKey, rowHeader) => {
    // JSON object keys arrive sorted; the column order comes from the backend's own list.
    const keys = order.map(value => Object.keys(totals[field]).find(k => Number(k) === value)).filter(Boolean);
    return {
      rowHeader,
      columns: keys.map(k => ({ key: k, label: base(columnLabel(k), Number(k) === baseKey) })),
      rows: rows.map(r => ({ label: r.label, secondary: r.secondary, values: keys.map(k => millions(r.group[field][k].rar_3m)) })),
    };
  };
  return <div className="finance-metrics">
    <div className="groups">{groups.map(([key, label, , icon, tone]) => <GroupCard key={key} title={label} tiers={metrics.bases_tiers?.[key] || []} group={metrics.by_basis[key]} policy={key === 'POLICY_EXEMPT'} icon={icon} tone={tone} />)}</div>
    <p className="finance-combined muted">All customers combined: {millions(totals.rar_3m)} contribution at stake. The two fee-waiver checks overlap and are never added together.</p>
    <div className="groups finance-sensitivities">
      <SensitivityTable title="If transaction cost is lower" caption="Share of the BNM base fee treated as our cost"
        {...table('cost_sensitivity', metrics.cost_ratios, k => k, metrics.cost_ratio, 'Cost ratio')} />
      <SensitivityTable title="If deposits earn more or less" caption="Extra yield on fixed deposits above our offer rate"
        {...table('premium_sensitivity', metrics.liquidity_premiums, premiumLabel, metrics.liquidity_premium, 'Liquidity premium')} />
    </div>
    <p className="finance-sign">{SIGN_TEXT}</p>
  </div>;
}
