import React from 'react';
import { activityChange, isNumber, money, monthLabel, percent } from '../format.js';
import { ratioWidth } from '../presentation.js';
import Icon from './Icon.jsx';

const serviceMetrics = [
  ['login_failure_rate_3m','Login failure rate','lock'],
  ['outbound_failure_rate_3m','Outgoing payment failure rate','payment-failed'],
  ['outbound_bank_failure_rate_3m','Bank-attributed payment failure rate','deposit'],
  ['passive_session_rate_3m','Sessions without transactions','clock'],
];

export default function OperationsPerspective({ operations:ops, cutoff }) {
  const average=ops.combined_flow_mean_12m_myr, recent=ops.combined_flow_mean_3m_myr;
  const positiveAverage=isNumber(average) && average>0;
  const activity=activityChange(recent,average);
  const chip=activity==='Not provided' ? 'muted' : 'activity-chip '+(activity.endsWith('lower') ? 'lower' : 'higher');
  return <section className="perspective perspective-operations">
    <h2>Operations perspective</h2>
    <p className="muted">Review recorded activity and service measures before investigating an issue.</p>
    <section className="panel activity-panel">
      <div className="section-heading"><div><h3>Activity level</h3><p className="muted">Combined flow, recorded through {monthLabel(cutoff)}</p></div><span className={chip}>{activity}</span></div>
      <div className="activity-comparison">
        {[['Trailing 12-month average',average,'usual'],['Latest 3-month average',recent,'recent']].map(([label,value,kind])=><div className={'activity-row '+kind} key={kind}>
          <span className="activity-label">{label}</span>
          <span className="activity-track" aria-hidden="true"><i style={{width:ratioWidth(value,average)+'%'}} />{positiveAverage && <span className="attrition-marker" />}</span>
          <strong className={!isNumber(value) ? 'unavailable-value' : ''}>{money(value)}</strong>
        </div>)}
        {positiveAverage && <p className="activity-reference">Attrition reference · {money(average/2)}</p>}
      </div>
      <p className="muted activity-explanation">The dashed marker is half of the 12-month average, the reference level for the defined volume drop. That drop concerns the next three months, which are not yet observed.</p>
    </section>
    <section className="panel service-panel">
      <h3>Service experience</h3>
      <p className="muted">Saved aggregate measures for the latest three months. No monthly service trend is supplied, so none is inferred.</p>
      <div className="service-metrics">{serviceMetrics.map(([key,label,icon])=><div className="service-metric" key={key}>
        <span className="service-icon"><Icon name={icon} /></span>
        <span className="service-label">{label}</span>
        <strong className={'service-value'+(!isNumber(ops[key]) ? ' unavailable-value' : '')}>{percent(ops[key])}</strong>
        <span className="service-track" aria-hidden="true"><i style={{width:ratioWidth(ops[key],1)+'%'}} /></span>
      </div>)}</div>
      <p className="muted service-scale">Bars use a 0–100% scale.</p>
    </section>
    <div className="perspective-callout"><Icon name="info" /><p><strong>Check the service experience with the customer.</strong> These measures do not establish the reason for reduced activity.</p></div>
  </section>;
}
