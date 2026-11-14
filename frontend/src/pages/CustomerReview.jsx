import React, { useEffect, useState } from 'react';
import { Link, useParams, useSearchParams } from 'react-router-dom';
import { api } from '../api.js';
import { activityChange, decisionLabel, forecastLabel, monthLabel, percent, workflowLabel } from '../format.js';
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
    <div className="heading customer-context"><div>    <h1>{c.customer_name || 'Customer '+c.cus_id}</h1><p className="muted">{c.customer_name || 'Customer '+c.cus_id} · ID {c.cus_id} · {monthLabel(c.cutoff_month)} · Forecast {forecastLabel(c.cutoff_month)} · Batch {c.batch_id.slice(0,8)}</p><div className="context-badges"><RiskBadge flagged={c.review_alert} /><span className="badge">{workflowLabel(c.workflow?.state,c.workflow?.origin_month===c.cutoff_month)}</span></div></div><div className="heading-actions">{c.workflow?.case_id && <Link className="button primary" to={'/cases/'+c.workflow.case_id}>Open existing case</Link>}<button className={c.workflow?.case_id ? "button" : "primary"} onClick={()=>{document.getElementById('decision-section')?.scrollIntoView({behavior:'auto',block:'start'});document.getElementById('decision')?.focus({preventScroll:true});}}>{c.workflow?.case_id ? 'Record reassessment' : 'Record decision'}</button></div></div>
    <div className="review-layout"><div>{c.workflow?.case_id && c.review.version===0 && <section className="panel"><h2>Existing case context</h2><p>{c.workflow.origin_month > c.cutoff_month ? 'A case was opened from a later assessment in ' : 'Case opened from '}{monthLabel(c.workflow.origin_month)} with a {decisionLabel(c.workflow.origin_decision)} decision. This assessment predicts {percent(c.calibrated_risk)}. The case remains {c.workflow.case_status}. No committee review has been saved for this assessment.</p><Link className="button" to={'/cases/'+c.workflow.case_id}>Continue existing case</Link></section>}{c.workflow?.state==='case_conflict' && <section className="panel"><h2>Multiple active cases</h2><p>Select the case to reassess in the decision form. Existing cases are preserved.</p>{c.workflow.active_cases.map(item=><Link key={item.case_id} className="button" to={'/cases/'+item.case_id}>{monthLabel(item.origin_month)} case</Link>)}</section>}
      <section className="panel"><div className="prediction-stats"><div><h2>Predicted risk</h2><strong className={'number '+(c.review_alert ? 'risk' : '')}>{percent(c.calibrated_risk)}</strong><p className="muted">For {forecastLabel(c.cutoff_month)}</p></div>
        <div><h2>Observed activity</h2><strong className={'number '+(activity==='Not provided' ? 'unavailable-value' : '')}>{activity}</strong><p className="muted">Latest three-month average versus the trailing twelve-month average</p></div></div>
        <Explanation><p><strong>Predicted risk:</strong> the estimated chance of the defined activity drop during {forecastLabel(c.cutoff_month)}.</p><p><strong>Review threshold:</strong> {percent(c.probability_cutoff,2)}. The saved model flag determines the queue; this policy is read-only here.</p><p><strong>What counts as a drop in activity?</strong> The next three months’ average combined transaction flow is at most half of a positive trailing twelve-month average. This concerns volume, not account closure.</p><p><strong>Observed activity:</strong> recorded through {monthLabel(c.cutoff_month)}. {c.observed_outcome ? 'A separate observed outcome is shown below.' : 'An outcome has not been loaded.'}</p></Explanation>
      </section>
      <section className="panel"><h2>Observed outcome · {forecastLabel(c.cutoff_month)}</h2>{c.observed_outcome ? <><p><strong>{c.observed_outcome.target_churn ? 'Defined volume drop observed' : 'Defined volume drop not observed'}</strong></p><p className="muted">Complete three-month flow was recorded through {monthLabel(c.observed_outcome.outcome_month)}. The result is separate from the saved prediction and committee decision. It does not establish account closure or the effect of any follow-up.</p></> : <p className="muted">Not loaded. The full three-month recorded flow must be available before an outcome can be saved.</p>}</section>
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
