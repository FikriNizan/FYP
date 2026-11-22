import React, { useEffect, useState } from 'react';
import { Link, useLocation, useSearchParams } from 'react-router-dom';
import { api } from '../api.js';
import { count, decisionLabel, forecastLabel, millionsPlain, monthLabel, percent, workflowLabel } from '../format.js';
import { assessmentLink } from '../navigation.js';
import { ErrorNotice, RiskBadge } from '../components/Common.jsx';

const limit = 50;
const DECISION_OPTIONS = ['prioritise','monitor','no_immediate_action'];
// Every figure comes from /api/summary and /api/customers; nothing here is calculated.
export default function Overview({ batch, revision }) {
  const [params,setParams] = useSearchParams();
  const location = useLocation();
  const filter = ['flagged','awaiting','all'].includes(params.get('filter')) ? params.get('filter') : 'flagged';
  // Only listed decisions filter; a legacy decision=awaiting_review link shows All decisions (the awaiting tab covers it).
  const decision = DECISION_OPTIONS.includes(params.get('decision')) ? params.get('decision') : '';
  const query = params.get('q') || '';
  const [searchText, setSearchText] = useState(query);
  useEffect(()=>setSearchText(query),[query]);
  const offset = Math.max(0,Number.parseInt(params.get('offset') || '0',10) || 0);
  function update(values) { const next = new URLSearchParams(params); for (const [key,value] of Object.entries(values)) value ? next.set(key,String(value)) : next.delete(key); setParams(next); }
  const customerLink = id => assessmentLink('/customer/'+encodeURIComponent(id),batch)+'&return='+encodeURIComponent(location.search);
  const [data, setData] = useState(null);
  const [error, setError] = useState('');
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    let active = true;
    setData(null); setError('');
    const params = { q: query, limit, offset };
    if (filter !== 'all') params.flagged = true;
    if (filter === 'awaiting') params.workflow = 'needs_review';
    else if (decision) params.decision = decision;
    Promise.all([api.summary(batch), api.customers(batch, params)]).then(([summary, list]) => {
      if (active) setData({ summary, list });
    }).catch(error => { if (active) setError(error.message); });
    return () => { active = false; };
  }, [batch, revision, filter, decision, query, offset, attempt]);
  if (error) return <><ErrorNotice message={error} /><button onClick={() => setAttempt(old => old + 1)}>Try again</button></>;
  if (!data || data.summary.batch.batch_id !== batch) return <p role="status">Loading portfolio…</p>;
  const { summary, list } = data;
  const chooseFilter = value => update({filter:value,offset:0,decision:''});
  const awaiting = summary.needs_committee_review ?? summary.flagged_review_counts.awaiting_review;
  const balances = summary.flagged_balances;
  return <>
    <div className="heading"><div><h1>Overview</h1><p className="muted">Who needs the committee's attention · Information through {monthLabel(summary.batch.cutoff_month)} · Forecast {forecastLabel(summary.batch.cutoff_month)}</p></div></div>
    {summary.batch.source_kind === 'notebook_case_sample' && <p className="scope-note">Single-case sample · These totals describe this saved case, not the full portfolio.</p>}
    <div className="stats" role="group" aria-label="Assessment at a glance">
      <div className="stat"><span>Customers assessed</span><strong className="number">{count(summary.population)}</strong><small>{monthLabel(summary.batch.cutoff_month)} assessment</small></div>
      <div className="stat"><span>Flagged for review</span><strong className="number">{count(summary.flagged)}</strong><small>{percent(summary.flagged_share)} of customers</small></div>
      <div className="stat"><span>Flagged, awaiting review</span><strong className="number">{count(awaiting)}</strong><small>No decision saved yet</small></div>
      <Link className="stat" to={assessmentLink('/finance',batch)} aria-label="Deposits held by flagged customers: open the finance picture"><span>Deposits held by flagged customers</span><strong className="number">{millionsPlain(balances?.total)}</strong><small>Fixed deposits {millionsPlain(balances?.fixed_deposits)} · Operating {millionsPlain(balances?.operating)}</small><small className="stat-link">Open finance picture ›</small></Link>
    </div>
    <section className="panel" aria-labelledby="queue-title"><div className="section-heading"><div><h2 id="queue-title">Review queue</h2><p className="muted">Ranked by predicted risk. Open a customer to see why.</p></div></div>
      <div className="toolbar"><div className="filters" role="group" aria-label="Customer filter">
        {[['flagged','Flagged'],['awaiting','Flagged · awaiting review'],['all','All customers']].map(([key,label]) => <button key={key} aria-pressed={filter === key} onClick={() => chooseFilter(key)}>{label}</button>)}
      </div><form className="search" onSubmit={event => { event.preventDefault(); update({q:searchText.trim(),offset:0}); }}><label htmlFor="query" className="muted">Find customer</label><input id="query" type="search" placeholder="Company name or ID" value={searchText} onChange={event => setSearchText(event.target.value)} /><button type="submit">Search</button></form></div>
      <div className="queue-options"><label htmlFor="queue-decision">This assessment decision</label><select id="queue-decision" value={filter==='awaiting' ? '' : decision} onChange={event=>update({decision:event.target.value,filter:filter==='awaiting' ? 'flagged' : filter,offset:0})}><option value="">All decisions</option>{DECISION_OPTIONS.map(d=><option key={d} value={d}>{decisionLabel(d)}</option>)}</select><span className="muted">{count(list.total)} matching {list.total===1 ? 'customer' : 'customers'}</span></div>
      <div className="table-wrap"><table><thead><tr><th scope="col">Customer</th><th scope="col">Predicted risk</th><th scope="col">This assessment decision</th><th scope="col">Workflow</th></tr></thead><tbody>
        {list.items.map(c => <tr key={c.prediction_id}><td><Link className="customer-name" to={customerLink(c.cus_id)}>{c.customer_name || 'Customer ' + c.cus_id}</Link><div className="muted">ID {c.cus_id}</div></td><td><strong>{percent(c.calibrated_risk)}</strong><br /><RiskBadge flagged={c.review_alert} /></td><td>{decisionLabel(c.review.decision)}</td><td><strong>{workflowLabel(c.workflow?.state,c.workflow?.origin_month===c.cutoff_month)}</strong>{c.workflow?.case_status && <div className="muted">Case: {c.workflow?.case_status}</div>}<div><Link className="button" to={c.workflow?.case_id ? '/cases/'+c.workflow?.case_id : customerLink(c.cus_id)}>{c.workflow?.case_id ? 'Open case' : 'Open review'}</Link></div></td></tr>)}
        {!list.items.length && <tr><td colSpan="4">No customers match these filters.</td></tr>}
      </tbody></table></div>
      <div className="pagination"><span className="muted">{list.items.length ? `${offset + 1}–${Math.min(offset + limit, list.total)}` : '0'} of {count(list.total)} {list.total===1 ? 'customer' : 'customers'}</span><div className="pagination-controls"><button disabled={!offset} onClick={() => update({offset:Math.max(0,offset-limit)})}>Previous</button><button disabled={offset+limit >= list.total} onClick={() => update({offset:offset+limit})}>Next</button></div></div>
    </section>
  </>;
}
