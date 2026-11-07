import React from 'react';
import { isNumber } from '../format.js';
import { balanceShares, relativeEstimateWidths } from '../presentation.js';
import FinanceCard from './FinanceCard.jsx';
import Icon from './Icon.jsx';

const missingCaption='No value was supplied for this assessment.';

export default function FinancePerspective({ finance }) {
  const operating=finance.non_fd_balance_myr, deposit=finance.fd_balance_myr;
  const shares=balanceShares(operating,deposit);
  const widths=relativeEstimateWidths(finance.estimated_monthly_fee_myr,finance.estimated_monthly_waiver_myr);
  const shareCaption=(value,other,share)=> !isNumber(value) ? missingCaption
    : !isNumber(other) ? 'Share not shown while the other balance is not provided'
    : shares ? share.toFixed(1)+'% of the two recorded balances' : null;
  return <section className="perspective perspective-finance">
    <h2>Finance perspective</h2>
    <p className="muted">Balance exposure and historical monthly estimates, shown separately.</p>
    <h3 className="finance-group-title">Balance exposure</h3>
    <div className="perspective-finance-cards">
      <FinanceCard label="Operating account balances" icon="wallet" kind="exposure" value={operating} missing={!isNumber(operating)}><small className="finance-caption muted">{shareCaption(operating,deposit,shares?.operating)}</small></FinanceCard>
      <FinanceCard label="Fixed deposit balances" icon="deposit" kind="exposure" value={deposit} missing={!isNumber(deposit)}><small className="finance-caption muted">{shareCaption(deposit,operating,shares?.deposit)}</small></FinanceCard>
    </div>
    {shares && <div className="panel balance-split-panel">
      <div className="balance-split" role="img" aria-label={`Operating ${shares.operating.toFixed(1)} percent, fixed deposit ${shares.deposit.toFixed(1)} percent`}>
        <i className="split-operating" style={{width:shares.operating+'%'}} /><i className="split-deposit" style={{width:shares.deposit+'%'}} />
      </div>
      <div className="split-legend"><span><i className="split-operating" aria-hidden="true" />Operating {shares.operating.toFixed(1)}%</span><span><i className="split-deposit" aria-hidden="true" />Fixed deposit {shares.deposit.toFixed(1)}%</span></div>
    </div>}
    <h3 className="finance-group-title">Historical monthly estimates</h3>
    <div className="perspective-finance-cards">
      {[
        ['estimated_monthly_fee_myr','Estimated monthly fees','receipt','fee'],
        ['estimated_monthly_waiver_myr','Estimated monthly waivers','waiver','waiver'],
      ].map(([key,label,icon,widthKey])=><FinanceCard key={key} label={label} icon={icon} kind="estimate" value={finance[key]} missing={!isNumber(finance[key])}>
        {!isNumber(finance[key]) ? <small className="finance-caption muted">{missingCaption}</small> : widths && <div className="finance-coverage"><span className="coverage-track" aria-hidden="true"><i style={{width:widths[widthKey]+'%'}} /></span><small className="muted">Relative to the larger estimate</small></div>}
      </FinanceCard>)}
    </div>
    <div className="perspective-callout"><Icon name="info" /><p><strong>How to read this.</strong> Balances show exposure. Fees and waivers are separate historical three-month monthly estimates, not verified profit, actual invoices or retention savings.</p></div>
  </section>;
}
