import React, { useEffect, useState } from 'react';
import { Link, useLocation, useSearchParams } from 'react-router-dom';
import { api } from '../api.js';
import { count, decisionLabel, forecastLabel, monthLabel, percent } from '../format.js';
import { assessmentLink } from '../navigation.js';
import { ErrorNotice, RiskBadge } from '../components/Common.jsx';
import { ConnectionState } from '../components/Workspace.jsx';
import FinanceCard from '../components/FinanceCard.jsx';

const limit = 50;
const financeCards = [
  { key:'non_fd_balance_myr', label:'Operating account balances', icon:'wallet', kind:'exposure' },
  { key:'fd_balance_myr', label:'Fixed deposit balances', icon:'deposit', kind:'exposure' },
  { key:'estimated_monthly_fee_myr', label:'Estimated monthly fees', icon:'receipt', kind:'estimate' },
  { key:'estimated_monthly_waiver_myr', label:'Estimated monthly waivers', icon:'waiver', kind:'estimate' },
];
export default function Overview({ batch, revision }) {
  const [params,setParams] = useSearchParams();
  const location = useLocation();
  const filter = ['flagged','awaiting','all'].includes(params.get('filter')) ? params.get('filter') : 'flagged';
  const decision = params.get('decision') || '';
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
    if (filter === 'awaiting') params.decision = 'awaiting_review';
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
  const awaiting = summary.flagged_review_counts.awaiting_review;
  const reviewed = summary.flagged-awaiting;
  return <>
    <div className="heading"><div><h1>Overview</h1><p className="muted">Information through {monthLabel(summary.batch.cutoff_month)} · Forecast {forecastLabel(summary.batch.cutoff_month)} · Batch {batch.slice(0,8)}</p></div><ConnectionState /></div>
    {summary.batch.source_kind === 'notebook_case_sample' && <p className="scope-note">Single-case sample · These totals describe this saved case, not the full portfolio.</p>}
    <div className="stats">
      <div className="stat"><span>Customers assessed</span><strong className="number">{count(summary.population)}</strong></div>
      <div className="stat"><span>Flagged for review</span><strong className="number">{count(summary.flagged)}</strong><small className="muted">{count(summary.below_threshold)} below the review threshold</small></div>
      <div className="stat"><span>Flagged and awaiting review</span><strong className="number">{count(awaiting)}</strong><small className="muted">{count(summary.flagged_review_counts.prioritise)} prioritised for RM</small></div>
    </div>
    <div className="review-progress"><div><strong>Flagged review progress</strong><span>{count(reviewed)} reviewed · {count(awaiting)} awaiting</span></div><progress max={summary.flagged || 1} value={reviewed} aria-label="Reviewed flagged customers" /><small>{summary.flagged ? 'Based on all flagged customers in the selected batch.' : 'No flagged customers in this assessment.'}</small></div>
    <section className="finance-context" aria-labelledby="finance-context-title">
      <div className="section-heading"><div><h2 id="finance-context-title">Financial context for flagged customers</h2><p className="muted">Totals across the {count(summary.flagged)} flagged customers in this assessment.</p></div></div>
      <div className="finance-cards">
        {financeCards.map(({key,label,icon,kind}) => {
          const value = summary.finance['flagged_' + key];
          const coverage = value.records ? Math.round(value.records_with_value / value.records * 100) : 0;
          return <FinanceCard key={key} label={label} icon={icon} kind={kind} value={value.total}>
            <div className="finance-coverage"><span className="coverage-track" aria-hidden="true"><i style={{width:coverage+'%'}} /></span><small className="muted">{count(value.records_with_value)} of {count(value.records)} records available</small></div>
          </FinanceCard>;
        })}
      </div>
      <p className="muted finance-note">Balances are exposures. Fees and waivers are separate historical estimates; they do not establish profit or potential savings.</p>
    </section>
    <section className="panel"><h2>Customer review queue</h2><p className="muted">Highest predicted risk first. Consider the evidence from both Operations and Finance before deciding.</p>
      <div className="toolbar"><div className="filters" role="group" aria-label="Customer filter">
        {[['flagged','Flagged'],['awaiting','Flagged · awaiting review'],['all','All customers']].map(([key,label]) => <button key={key} aria-pressed={filter === key} onClick={() => chooseFilter(key)}>{label}</button>)}
      </div><form className="search" onSubmit={event => { event.preventDefault(); update({q:searchText.trim(),offset:0}); }}><label htmlFor="query" className="muted">Find customer</label><input id="query" type="search" placeholder="Company name or ID" value={searchText} onChange={event => setSearchText(event.target.value)} /><button type="submit">Search</button></form></div>
      <div className="queue-options"><label htmlFor="queue-decision">Committee decision</label><select id="queue-decision" value={filter==='awaiting' ? 'awaiting_review' : decision} onChange={event=>update({decision:event.target.value,filter:filter==='awaiting' ? 'flagged' : filter,offset:0})}><option value="">All decisions</option>{['awaiting_review','prioritise','monitor','no_immediate_action'].map(d=><option key={d} value={d}>{decisionLabel(d)}</option>)}</select><span className="muted">{count(list.total)} matching {list.total===1 ? 'customer' : 'customers'}</span></div>
      <div className="table-wrap"><table><thead><tr><th scope="col">Customer</th><th scope="col">Predicted risk</th><th scope="col">Committee decision</th><th scope="col">Review</th></tr></thead><tbody>
        {list.items.map(c => <tr key={c.prediction_id}><td><Link className="customer-name" to={customerLink(c.cus_id)}>{c.customer_name || 'Customer ' + c.cus_id}</Link><div className="muted">ID {c.cus_id}</div></td><td><strong>{percent(c.calibrated_risk)}</strong><br /><RiskBadge flagged={c.review_alert} /></td><td>{decisionLabel(c.review.decision)}</td><td><Link className="button" to={customerLink(c.cus_id)}>Open review</Link></td></tr>)}
        {!list.items.length && <tr><td colSpan="4">No customers match these filters.</td></tr>}
      </tbody></table></div>
      <div className="pagination"><span className="muted">{list.items.length ? `${offset + 1}–${Math.min(offset + limit, list.total)}` : '0'} of {count(list.total)} {list.total===1 ? 'customer' : 'customers'}</span><div className="pagination-controls"><button disabled={!offset} onClick={() => update({offset:Math.max(0,offset-limit)})}>Previous</button><button disabled={offset+limit >= list.total} onClick={() => update({offset:offset+limit})}>Next</button></div></div>
    </section>
  </>;
}
