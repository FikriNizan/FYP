import React from 'react';
import { activityChange, isNumber, money, monthLabel, percent } from '../format.js';
import { ratioWidth } from '../presentation.js';
import Icon from './Icon.jsx';

// Service levels come from the backend: "high" means above the 75th percentile of this assessment's customers.
export const LEVEL_RULE = 'High = higher than 3 in 4 customers in this assessment.';
const serviceMetrics = [
  ['login_failure_rate_3m','Sign-in failures','lock','Sign-in failures are high: check user access, security tokens and locked users with the customer’s administrator.'],
  ['passive_session_rate_3m','Sessions without transactions','screen','Many sessions end without a transaction: ask whether online banking still meets the team’s day-to-day needs.'],
  ['outbound_failure_rate_3m','Outgoing payment failures','payment-failed','Outgoing payments often fail: check beneficiary details, limits and cut-off times.'],
  ['outbound_bank_failure_rate_3m','Payment failures on our side','bank','Payments are failing on the bank’s side: raise it with payment operations before the call.'],
];
const levelWord = { high:'High', usual:'Usual', not_provided:'Not provided' };

export default function OperationsPerspective({ operations:ops, levels = {}, cutoff }) {
  const average=ops.combined_flow_mean_12m_myr, recent=ops.combined_flow_mean_3m_myr;
  const positiveAverage=isNumber(average) && average>0;
  const activity=activityChange(recent,average);
  const chip=activity==='Not provided' ? 'muted' : 'activity-chip '+(activity.endsWith('lower') ? 'lower' : 'higher');
  const level = key => levels[key]?.level || 'not_provided';
  const high = serviceMetrics.filter(([key]) => level(key) === 'high');
  return <section className="perspective perspective-operations">
    <h2 className="sr-only">Operations perspective</h2>
    <section className="panel service-panel" aria-labelledby="service-title">
      <h2 id="service-title">Service experience</h2>
      <p className="muted">Last 3 months, recorded through {monthLabel(cutoff)}. {LEVEL_RULE}</p>
      <div className="service-metrics">{serviceMetrics.map(([key,label,icon])=><div className="service-metric" key={key}>
        <span className={'round ' + (level(key)==='high' ? 'red' : '')}><Icon name={icon} /></span>
        <span className="service-label">{label}</span>
        <strong className={'service-value'+(!isNumber(ops[key]) ? ' unavailable-value' : '')}>{percent(ops[key])}</strong>
        <span className={'level ' + level(key)}>{levelWord[level(key)]}</span>
        <span className="service-track" aria-hidden="true"><i className={level(key)==='high' ? 'high' : ''} style={{width:ratioWidth(ops[key],1)+'%'}} /></span>
      </div>)}</div>
      {high.length > 0 && <div className="hints">{high.map(([key,,,hint]) => <p className="hint" key={key}><span className="round small"><Icon name="info" /></span><span>{hint}</span></p>)}</div>}
    </section>
    <section className="panel activity-panel" aria-labelledby="activity-title">
      <div className="section-heading"><div><h2 id="activity-title">Activity level</h2><p className="muted">Combined flow (collections and payments together), per month</p></div><span className={chip}>{activity}</span></div>
      <div className="activity-comparison">
        {[['Usual (12-month average)',average,'usual'],['Recent (last 3 months)',recent,'recent']].map(([label,value,kind])=><div className={'activity-row '+kind} key={kind}>
          <span className="activity-label">{label}</span>
          <span className="activity-track" aria-hidden="true"><i style={{width:ratioWidth(value,average)+'%'}} />{positiveAverage && <span className="attrition-marker" />}</span>
          <strong className={!isNumber(value) ? 'unavailable-value' : ''}>{money(value)}</strong>
        </div>)}
        {positiveAverage && <p className="activity-reference">Attrition reference · {money(average/2)}</p>}
      </div>
      <p className="muted activity-explanation">The red dashed line is half of usual. Averaging at or below it over the next three months counts as activity halved; those months are not yet observed.</p>
    </section>
  </section>;
}
