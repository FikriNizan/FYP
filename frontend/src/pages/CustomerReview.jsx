import React, { useEffect, useState } from 'react';
import { Link, useParams, useSearchParams } from 'react-router-dom';
import { api } from '../api.js';
import { activityChange, decisionLabel, forecastLabel, money, monthLabel, percent, tierLabel, workflowLabel } from '../format.js';
import { ErrorNotice } from '../components/Common.jsx';
import FinancePerspective from '../components/FinancePerspective.jsx';
import OperationsPerspective from '../components/OperationsPerspective.jsx';
import CustomerSummary from '../components/CustomerSummary.jsx';
import Signals from '../components/Signals.jsx';
import FlowHistory from '../components/FlowHistory.jsx';
import ReviewForm from '../components/ReviewForm.jsx';
import Icon from '../components/Icon.jsx';
import { PerspectiveTabs } from '../components/Workspace.jsx';

const decisionBadge = { awaiting_review:'b-wait', prioritise:'b-pri', monitor:'b-mon', no_immediate_action:'b-no' };

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
  const decision = c.review.decision || 'awaiting_review';
  return <>
    <Link className="back-link" to={'/overview'+(params.get('return')?.startsWith('?') ? params.get('return') : '?batch_id='+encodeURIComponent(batch))}><Icon name="left" />Review queue</Link>
    <section className="panel" aria-label="Customer at a glance"><div className="case-head">
      <div><h1>{c.customer_name || 'Customer '+c.cus_id}</h1><p className="muted">CIF {c.cus_id} · {tierLabel(c.tier_id)} · {monthLabel(c.cutoff_month)} assessment</p>
        <div className="badges"><span className={'badge ' + (decisionBadge[decision] || '')}>{decisionLabel(decision)}</span><span className="badge">{workflowLabel(c.workflow?.state,c.workflow?.origin_month===c.cutoff_month)}</span>{c.workflow?.case_id && <Link to={'/cases/'+c.workflow.case_id}>Open existing case</Link>}</div></div>
      <div><p className="muted">Predicted risk · {forecastLabel(c.cutoff_month)}</p><strong className={'number '+(c.review_alert ? 'risk' : '')}>{percent(c.calibrated_risk)}</strong>
        <p className="muted">{c.review_alert ? 'At or above' : 'Below'} the review threshold ({percent(c.probability_cutoff)})</p></div>
      <div><p className="muted">Recent activity vs usual</p><strong className={'number '+(activity==='Not provided' ? 'unavailable-value' : '')}>{money(ops.combined_flow_mean_3m_myr)}</strong>
        <p>{activity==='Not provided' ? <span className="muted">Not provided</span> : <span className={'activity-chip '+(activity.endsWith('lower') ? 'lower' : 'higher')}>{activity}</span>}</p></div>
    </div></section>
    <div className="review-layout"><div>{c.workflow?.case_id && c.review.version===0 && <section className="panel"><h2>Existing case context</h2><p>{c.workflow.origin_month > c.cutoff_month ? 'A case was opened from a later assessment in ' : 'Case opened from '}{monthLabel(c.workflow.origin_month)} with a {decisionLabel(c.workflow.origin_decision)} decision. This assessment predicts {percent(c.calibrated_risk)}. The case remains {c.workflow.case_status}. No committee review has been saved for this assessment.</p><Link className="button" to={'/cases/'+c.workflow.case_id}>Continue existing case</Link></section>}{c.workflow?.state==='case_conflict' && <section className="panel"><h2>Multiple active cases</h2><p>Select the case to reassess in the decision form. Existing cases are preserved.</p>{c.workflow.active_cases.map(item=><Link key={item.case_id} className="button" to={'/cases/'+item.case_id}>{monthLabel(item.origin_month)} case</Link>)}</section>}
      <PerspectiveTabs value={perspective} onChange={setPerspective} />
      <div id="perspective-panel" role="tabpanel" aria-label={perspective+' evidence'} tabIndex={0}>
      {perspective==='Summary' && <CustomerSummary key={c.prediction_id+':'+revision} recordId={c.prediction_id}>
        <FlowHistory history={c.flow_history} baseline={ops.combined_flow_mean_12m_myr} cutoff={c.cutoff_month} /><Signals customer={c} />
      </CustomerSummary>}
      {perspective==='Operations' && <OperationsPerspective operations={ops} levels={c.service_levels} cutoff={c.cutoff_month} />}
      {perspective==='Finance' && <FinancePerspective finance={finance} metrics={c.finance_metrics} batch={c.batch_id} cutoff={c.cutoff_month} />}
      </div>
    </div><ReviewForm key={c.prediction_id+':'+c.review.version} customer={c} workflow={workflow} /></div>
  </>;
}
