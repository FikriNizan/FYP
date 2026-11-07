import React, { useEffect, useState } from 'react';
import { Link, useParams, useSearchParams } from 'react-router-dom';
import { api } from '../api.js';
import { activityChange, decisionLabel, forecastLabel, monthLabel, percent } from '../format.js';
import { ErrorNotice, RiskBadge } from '../components/Common.jsx';
import FinancePerspective from '../components/FinancePerspective.jsx';
import OperationsPerspective from '../components/OperationsPerspective.jsx';
import Signals from '../components/Signals.jsx';
import FlowHistory from '../components/FlowHistory.jsx';
import ReviewForm from '../components/ReviewForm.jsx';
import { Explanation, PerspectiveTabs } from '../components/Workspace.jsx';
import { assessmentLink } from '../navigation.js';

export default function CustomerReview({ batch, revision, workflow }) {
  const { id } = useParams();
  const [params] = useSearchParams();
  const [perspective,setPerspective] = useState('Summary');
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
  const activity=activityChange(ops.combined_flow_mean_3m_myr,ops.combined_flow_mean_12m_myr);
  return <>
    <Link className="back-link" to={'/overview'+(params.get('return')?.startsWith('?') ? params.get('return') : '?batch_id='+encodeURIComponent(batch))}>← Back to review queue</Link>
    <div className="heading customer-context"><div><h1>{c.customer_name || 'Customer '+c.cus_id}</h1><p className="muted">Customer {c.cus_id} · {monthLabel(c.cutoff_month)} · Forecast {forecastLabel(c.cutoff_month)} · Batch {c.batch_id.slice(0,8)}</p><div className="context-badges"><RiskBadge flagged={c.review_alert} /><span className="badge">{decisionLabel(c.review.decision)}</span></div></div><div className="heading-actions"><button className="primary" onClick={()=>{document.getElementById('decision-section')?.scrollIntoView({behavior:'auto',block:'start'});document.getElementById('decision')?.focus({preventScroll:true});}}>Record decision</button>{c.review.version > 0 && <Link className="button" to={assessmentLink('/cases/'+c.prediction_id,batch)}>Open follow-up case</Link>}</div></div>
    <div className="review-layout"><div>
      <section className="panel"><div className="prediction-stats"><div><h2>Predicted risk</h2><strong className={'number '+(c.review_alert ? 'risk' : '')}>{percent(c.calibrated_risk)}</strong><p className="muted">For {forecastLabel(c.cutoff_month)}</p></div>
        <div><h2>Observed activity</h2><strong className={'number '+(activity==='Not provided' ? 'unavailable-value' : '')}>{activity}</strong><p className="muted">Latest three-month average versus the trailing twelve-month average</p></div></div>
        <Explanation><p><strong>Predicted risk:</strong> the estimated chance of the defined activity drop during {forecastLabel(c.cutoff_month)}.</p><p><strong>Review threshold:</strong> {percent(c.probability_cutoff,2)}. The saved model flag determines the queue; this policy is read-only here.</p><p><strong>What counts as a drop in activity?</strong> The next three months’ average combined transaction flow is at most half of a positive trailing twelve-month average. This concerns volume, not account closure.</p><p><strong>Observed activity:</strong> recorded through {monthLabel(c.cutoff_month)}. An outcome has not been loaded.</p></Explanation>
      </section>
      <PerspectiveTabs value={perspective} onChange={setPerspective} />
      <div id="perspective-panel" role="tabpanel" aria-label={perspective+' evidence'} tabIndex={0}>
      {perspective==='Summary' && <><FlowHistory history={c.flow_history} baseline={ops.combined_flow_mean_12m_myr} cutoff={c.cutoff_month} /><Signals customer={c} /></>}
      {perspective==='Operations' && <OperationsPerspective operations={ops} cutoff={c.cutoff_month} />}
      {perspective==='Finance' && <FinancePerspective finance={finance} />}
      {perspective!=='Summary' && <p className="muted shared-evidence-note">Model signals and recorded flow history are shared evidence in Summary. These views do not change your role or access.</p>}
      </div>
    </div><ReviewForm key={c.prediction_id+':'+c.review.version} customer={c} workflow={workflow} /></div>
  </>;
}
