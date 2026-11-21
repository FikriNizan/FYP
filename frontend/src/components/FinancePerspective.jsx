import React from 'react';
import { Link } from 'react-router-dom';
import { dateLabel, isNumber, money, tierLabel } from '../format.js';
import { assessmentLink } from '../navigation.js';
import { balanceShares, ratioWidth } from '../presentation.js';
import { FSL_A_TEXT, FSL_B_TEXT, NEGATIVE_TEXT } from './FinanceMetrics.jsx';
import Icon from './Icon.jsx';

// Every figure comes from the backend (finance fields and finance_metrics); nothing here is recalculated.
const signed = value => isNumber(value) ? money(value) : money(null);

function YesNo({ question, answer, tone, detail, children }) {
  const icon = tone === 'yes' ? 'yes' : tone === 'no' ? 'no' : 'minus';
  return <div className="yn"><span className={'round ' + (tone === 'yes' ? 'green' : tone === 'no' ? 'red' : '')}><Icon name={icon} /></span>
    <span>{question}{detail}{children}</span><span className={'ans ' + (tone || 'other')}>{answer}</span></div>;
}

function checkA(a) {
  if (a.flagged) return ['No', 'no', <p className="muted">{FSL_A_TEXT}: the fixed deposit is below the agreed level, but fees are still waived ({money(a.monthly)} a month).</p>];
  return { deal_kept:['Yes','yes'], policy_exemption:['Policy exemption',''], no_active_waiver:['No active waiver',''] }[a.status] || ['Not provided',''];
}

function checkB(b) {
  if (b.policy && b.status !== 'unavailable' && b.status !== 'no_active_waiver') return ['Policy exemption', ''];
  if (b.flagged) return ['No', 'no', <><p className="muted">{FSL_B_TEXT}</p><p className="muted">Uncovered: {money(b.monthly)} a month.</p></>];
  return { covered:['Yes','yes'], no_active_waiver:['No active waiver',''] }[b.status] || ['Not provided',''];
}

function Breakdown({ metrics }) {
  const c = metrics.components;
  const rows = [['Fee income', c.fee_income], ['Assumed transaction cost', isNumber(c.transaction_cost) ? -c.transaction_cost : null],
    ['Deposit earnings', c.fd_earnings], ['Operating-balance earnings', c.operating_earnings], ['Contribution a month', metrics.contribution_monthly]];
  const largest = Math.max(0, ...rows.map(([, v]) => isNumber(v) ? Math.abs(v) : 0));
  return <section className="panel" aria-labelledby="breakdown-title"><h2 id="breakdown-title">Where the monthly figure comes from</h2>
    <p className="muted">Estimated, per month</p>
    {rows.map(([label, value]) => <div className="wf" key={label}><span>{label}</span>
      <span className="bar" aria-hidden="true">{isNumber(value) && <i className={value < 0 ? 'minus' : 'plus'} style={{ width: ratioWidth(Math.abs(value), largest) + '%' }} />}</span>
      <strong className={!isNumber(value) ? 'unavailable-value' : ''}>{signed(value)}</strong></div>)}
  </section>;
}

export default function FinancePerspective({ finance, metrics, batch, cutoff }) {
  const operating = finance.non_fd_balance_myr, deposit = finance.fd_balance_myr;
  const shares = balanceShares(operating, deposit);
  const contribution = metrics?.contribution_monthly;
  const policy = metrics?.waiver_basis === 'POLICY_EXEMPT';
  const [aAnswer, aTone, aDetail] = metrics ? checkA(metrics.fsl_a) : [];
  const [bAnswer, bTone, bDetail] = metrics ? checkB(metrics.fsl_b) : [];
  return <section className="perspective perspective-finance">
    <h2 className="sr-only">Finance perspective</h2>
    <div className="two-columns">
      {metrics ? <div className="finance-card" role="group" aria-label="Estimated monthly relationship contribution">
        <div className="finance-top"><span className="round"><Icon name="coin" /></span><h3>Relationship contribution (estimate)</h3></div>
        <p className="muted">Contribution at stake · next 3 months</p>
        <div className="finance-value">{money(metrics.rar_3m)} <small>{isNumber(contribution) ? money(contribution) + ' a month' : 'Not provided'}</small></div>
        <p className="muted">Shown beside the risk, never multiplied by it.</p>
        {isNumber(contribution) && contribution < 0 && <p className="finance-negative">{NEGATIVE_TEXT}</p>}
        {metrics.unavailable.length > 0 && <ul className="finance-unavailable" aria-label="Unavailable inputs">{metrics.unavailable.map(reason => <li key={reason}>Not provided: {reason}</li>)}</ul>}
        <YesNo question="Fee waiver deal kept?" answer={aAnswer} tone={aTone} detail={aDetail} />
        <YesNo question="Do deposits pay for the waived fees?" answer={bAnswer} tone={bTone} detail={bDetail} />
      </div> : <div className="finance-card"><p>Relationship contribution is not provided for this assessment.</p></div>}
      <div className="finance-card estimate" role="group" aria-label="Where the money sits">
        <div className="finance-top"><span className="round teal"><Icon name="bank" /></span><div><h3>Where the money sits</h3><p className="muted">Balances on {dateLabel(cutoff)} · exposure, not income</p></div></div>
        {shares && <div className="alloc" role="img" aria-label={`Operating ${shares.operating.toFixed(1)} percent, fixed deposit ${shares.deposit.toFixed(1)} percent`}>
          {shares.operating > 0 && <span className="op" style={{ width: shares.operating + '%' }}>Operating {shares.operating.toFixed(0)}%</span>}
          {shares.deposit > 0 && <span className="fd" style={{ width: shares.deposit + '%' }}>Fixed deposit {shares.deposit.toFixed(0)}%</span>}
        </div>}
        <div className="acc"><span className="round teal"><Icon name="wallet" /></span><span>Operating accounts<br /><span className="muted">Day-to-day current accounts</span></span><b className={!isNumber(operating) ? 'unavailable-value' : ''}>{money(operating)}</b></div>
        <div className="acc"><span className="round violet"><Icon name="safe" /></span><span>Fixed deposits<br /><span className="muted">Term placements</span></span><b className={!isNumber(deposit) ? 'unavailable-value' : ''}>{money(deposit)}</b></div>
        {metrics && (policy ? <p className="need"><b>Fee waiver by policy exemption</b></p>
          : isNumber(metrics.fd_threshold_myr) && <div className="need"><p><b>Fee waiver condition</b> <span className="muted">· fixed deposit needed for {tierLabel(metrics.tier_id)}</span></p>
            <span className="activity-track" role="img" aria-label={`${money(deposit)} of ${money(metrics.fd_threshold_myr)} required`}><i style={{ width: ratioWidth(deposit, metrics.fd_threshold_myr) + '%' }} /></span>
            <span className="muted">{money(deposit)} of {money(metrics.fd_threshold_myr)} required</span></div>)}
      </div>
    </div>
    {metrics && <Breakdown metrics={metrics} />}
    <p className="muted">Waived fees: {money(finance.estimated_monthly_waiver_myr)} a month. Fees and waivers are historical estimates, not invoices. {batch && <Link to={assessmentLink('/finance', batch)}>Portfolio assumptions and sensitivity: Finance picture</Link>}</p>
  </section>;
}
