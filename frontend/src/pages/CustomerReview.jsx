import React, { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { api } from '../api.js';
import { activityChange, decisionLabel, forecastLabel, money, monthLabel, percent } from '../format.js';
import { Definition, ErrorNotice, RiskBadge } from '../components/Common.jsx';
import Signals from '../components/Signals.jsx';
import FlowHistory from '../components/FlowHistory.jsx';
import ReviewForm from '../components/ReviewForm.jsx';

export default function CustomerReview({ batch, revision, workflow }) {
  const { id } = useParams();
  const [customer, setCustomer] = useState(null);
  const [error, setError] = useState('');
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    let active = true;
    setCustomer(null); setError('');
    api.customer(id, batch).then(result => { if (active) setCustomer(result.customer); })
      .catch(error => { if (active) setError(error.message); });
    return () => { active = false; };
  }, [id, batch, revision, attempt]);
  if (error) return <><ErrorNotice message={error} /><button onClick={() => setAttempt(old => old + 1)}>Try again</button></>;
  if (!customer || customer.cus_id !== id || customer.batch_id !== batch) return <p role="status">Loading customer…</p>;
  const c = customer, ops = c.operations, finance = c.finance;
  return <>
    <div className="heading"><div><h1>{c.customer_name || 'Customer '+c.cus_id}</h1><p className="muted">ID {c.cus_id} · {monthLabel(c.cutoff_month)} assessment · {c.customer_type || 'Type not provided'}</p></div><span className="badge">{decisionLabel(c.review.decision)}</span></div>
    <div className="review-layout"><div>
      <section className="panel"><div className="prediction-stats"><div><h2>Predicted risk</h2><strong className={'number '+(c.review_alert ? 'risk' : '')}>{percent(c.calibrated_risk)}</strong><p className="muted">For {forecastLabel(c.cutoff_month)}</p><RiskBadge flagged={c.review_alert} /></div>
        <div><h2>Observed activity</h2><strong className="number">{activityChange(ops.combined_flow_mean_3m_myr,ops.combined_flow_mean_12m_myr)}</strong><p className="muted">Latest three-month average versus the trailing twelve-month average</p></div></div>
        <details><summary>What do these numbers mean?</summary><p><strong>Risk estimate:</strong> the model estimates the chance that average combined transaction activity over the next three months will be at most half of the positive trailing twelve-month average. It does not predict account closure.</p><p><strong>Review threshold:</strong> {percent(c.probability_cutoff,2)}. This sets which predictions are flagged. It is different from the 50% activity rule used to define the outcome.</p><p><strong>Observed activity:</strong> already recorded transactions; this is separate from the forecast. An outcome has not been loaded for this assessment.</p></details>
      </section>
      <Signals customer={c} />
      <FlowHistory history={c.flow_history} baseline={ops.combined_flow_mean_12m_myr} />
      <div className="two-columns"><section className="panel"><h2>Operations perspective</h2><dl>
        <Definition label="Login failure rate · latest 3 months" value={percent(ops.login_failure_rate_3m)} /><Definition label="Outgoing payment failure rate · latest 3 months" value={percent(ops.outbound_failure_rate_3m)} /><Definition label="Bank-attributed payment failure rate" value={percent(ops.outbound_bank_failure_rate_3m)} /><Definition label="Sessions without transactions" value={percent(ops.passive_session_rate_3m)} />
      </dl><p className="muted spaced">Check the service experience with the customer. These measures do not establish the reason for reduced activity.</p></section>
      <section className="panel"><h2>Finance perspective</h2><dl><Definition label="Operating account balances" value={money(finance.non_fd_balance_myr)} /><Definition label="Fixed deposit balances" value={money(finance.fd_balance_myr)} /><Definition label="Estimated monthly fees" value={money(finance.estimated_monthly_fee_myr)} /><Definition label="Estimated monthly waivers" value={money(finance.estimated_monthly_waiver_myr)} /></dl><p className="muted spaced">Balances show exposure. Fees and waivers are separate historical estimates, not verified profit or retention savings.</p></section></div>
    </div><ReviewForm key={c.prediction_id+':'+c.review.version} customer={c} workflow={workflow} /></div>
  </>;
}
