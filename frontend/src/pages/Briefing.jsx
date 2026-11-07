import React, { useEffect, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { api } from '../api.js';
import { activityChange, caseStatusLabel, dateLabel, driverLabel, driverValue, forecastLabel, money, monthLabel, percent } from '../format.js';
import { discussionQuestions } from '../briefing.js';
import { assessmentLink } from '../navigation.js';
import { ErrorNotice } from '../components/Common.jsx';
import { ConnectionState } from '../components/Workspace.jsx';
import AIBriefingDraft from '../components/AIBriefingDraft.jsx';

export default function Briefing({ batches = [] }) {
  const [params] = useSearchParams();
  const back=params.get('worklist');
  const reviewedPath='/reviewed'+(back?.startsWith('?') ? back : '');
  const ids = [...new Set(params.getAll('case_id'))];
  const selectionKey = ids.join(',');
  const [items,setItems] = useState(null);
  const [error,setError] = useState('');
  const [attempt,setAttempt] = useState(0);
  useEffect(()=>{
    let active=true; setItems(null); setError('');
    if (!ids.length || ids.length>10) return;
    Promise.all(ids.map(id=>api.case(id))).then(results=>{if(active) setItems(results.map(r=>r.case));}).catch(e=>{if(active)setError(e.message);});
    return ()=>{active=false;};
  },[selectionKey,attempt]);
  const invalid = items?.some(c=>c.original.review.decision!=='prioritise');
  return <>
    <div className="heading no-print"><div><h1>RM Briefing</h1><p className="muted">Structured briefing preview from explicitly selected saved cases. Review before sharing.</p></div><div className="heading-actions"><Link className="button" to={reviewedPath}>Choose cases</Link><button disabled={!items?.length || invalid} onClick={()=>window.print()}>Print briefing</button><button disabled title="Server PDF export is not integrated">Export PDF · unavailable</button></div></div>
    {!ids.length || ids.length>10 ? <section className="panel empty"><h2>Select up to ten prioritised cases</h2><p>Choose cases in Reviewed Customers, then open a briefing.</p></section> : error ? <><ErrorNotice message={error} /><button onClick={()=>setAttempt(n=>n+1)}>Try again</button></> : !items ? <p role="status">Loading selected case evidence…</p> : invalid ? <ErrorNotice message="One or more selected cases are no longer prioritised. Return to Reviewed Customers and select currently prioritised cases." /> : items.map(c=>{
      const original=c.original, latest=c.latest, review=c.original.review, ops=latest.operations || {}, finance=latest.finance || {};
      const questions=discussionQuestions(latest);
      const sample = batches.some(b=>[original.batch_id,latest.batch_id].includes(b.batch_id) && b.source_kind==='notebook_case_sample');
      const change = activityChange(ops.combined_flow_mean_3m_myr,ops.combined_flow_mean_12m_myr);
      return <article className="panel briefing-sheet" key={c.case_id}><div className="section-heading"><div><h2>{latest.customer_name || original.customer_name || 'Customer '+original.cus_id}</h2><p className="muted">Relationship discussion brief · Customer {original.cus_id} · Case {c.case_id.slice(0,12)}</p></div><ConnectionState /></div>
        <div className="briefing-context"><section><h3>At the time of review</h3><p>{monthLabel(original.cutoff_month)} · Predicted risk {percent(original.calibrated_risk)}</p><p className="muted">Forecast {forecastLabel(original.cutoff_month)}</p><p>{c.original_review.reason}</p></section><section><h3>Latest available assessment</h3><p>{monthLabel(latest.cutoff_month)} · Predicted risk {percent(latest.calibrated_risk)}</p><p className="muted">Forecast {forecastLabel(latest.cutoff_month)}</p>{latest.cutoff_month<=original.cutoff_month && <p className="muted">No newer assessment month is available.</p>}</section></div>
        {sample && <p className="scope-note">Single-case sample evidence is included. This briefing does not represent a complete portfolio.</p>}
        <section className="briefing-section"><h3>Observed activity through {monthLabel(latest.cutoff_month)}</h3><p>{change==='Not provided' ? 'Comparable three- and twelve-month averages were not provided.' : change+' versus the trailing twelve-month average.'}</p><dl><dt>Latest 3-month average</dt><dd>{money(ops.combined_flow_mean_3m_myr)}</dd><dt>Trailing 12-month average</dt><dd>{money(ops.combined_flow_mean_12m_myr)}</dd></dl></section>
        <section className="briefing-section"><h3>Signals to investigate</h3>{latest.explanation?.higher_risk_drivers?.length ? <ul>{latest.explanation.higher_risk_drivers.slice(0,3).map(d=><li key={d.feature}><strong>{driverLabel(d)}:</strong> {driverValue(d)} · Pushed the estimate higher</li>)}</ul> : <p>Not provided.</p>}<p className="muted">Model signals are discussion prompts, not confirmed causes.</p></section>
        <div className="briefing-context"><section><h3>Operations context</h3><p>{review.operations_notes || 'No committee Operations notes recorded.'}</p><p>Payment failure rate: {percent(ops.outbound_failure_rate_3m)}</p><p>Login difficulty rate: {percent(ops.login_failure_rate_3m)}</p></section><section><h3>Finance context</h3><dl><dt>Operating balances</dt><dd>{money(finance.non_fd_balance_myr)}</dd><dt>Fixed-deposit balances</dt><dd>{money(finance.fd_balance_myr)}</dd><dt>Estimated monthly fees</dt><dd>{money(finance.estimated_monthly_fee_myr)}</dd><dt>Estimated monthly waivers</dt><dd>{money(finance.estimated_monthly_waiver_myr)}</dd></dl><p>{review.finance_notes || 'No committee Finance notes recorded.'}</p><p className="muted">Balances are exposures; fees and waivers are historical estimates.</p></section></div>
        <section className="briefing-section"><h3>Current committee rationale &amp; next step</h3><p>{review.reason}</p><p>Reviewer: {review.reviewer || 'Not provided'} · Owner: {c.owner || 'Unassigned'} · Next follow-up: {dateLabel(c.next_action_date)} · Case: {caseStatusLabel(c.status)}</p><p className="muted">{c.follow_ups?.length ? 'Consult the case timeline for the recorded plan and actual activity.' : 'No follow-up has been recorded; this briefing can be prepared before outreach.'}</p></section>
        <section className="briefing-section"><h3>Questions for the customer</h3>{questions.length ? <ol>{questions.map((q,i)=><li key={i}><p>{q.text}</p><small className="muted">Evidence: {q.source} · {monthLabel(latest.cutoff_month)}</small></li>)}</ol> : <p>No evidence-linked question is available from the supplied measures. Review the case before preparing questions.</p>}</section>
        <AIBriefingDraft customer={latest} />
        <details className="briefing-sources"><summary>Evidence sources and identifiers</summary><p className="source-id">Original batch: {original.batch_id}<br />Latest batch: {latest.batch_id}<br />Original prediction: {original.prediction_id}<br />Latest prediction: {latest.prediction_id}</p><p className="no-print"><Link to={assessmentLink('/customer/'+encodeURIComponent(original.cus_id),original.batch_id)}>Original evidence</Link> · <Link to={assessmentLink('/customer/'+encodeURIComponent(latest.cus_id),latest.batch_id)}>Latest evidence</Link></p></details>
        <p className="print-only source-id">Original batch: {original.batch_id} · Prediction: {original.prediction_id}<br />Latest batch: {latest.batch_id} · Prediction: {latest.prediction_id}</p>
      </article>;
    })}
  </>;
}
