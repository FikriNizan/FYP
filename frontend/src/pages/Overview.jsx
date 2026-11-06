import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../api.js';
import { count, decisionLabel, forecastLabel, money, monthLabel, percent } from '../format.js';
import { assessmentLink } from '../navigation.js';
import { ErrorNotice, RiskBadge } from '../components/Common.jsx';

const limit = 50;
export default function Overview({ batch, revision }) {
  const [filter, setFilter] = useState('flagged');
  const [searchText, setSearchText] = useState('');
  const [query, setQuery] = useState('');
  const [page, setPage] = useState({ batch, offset: 0 });
  const offset = page.batch === batch ? page.offset : 0;
  const [data, setData] = useState(null);
  const [error, setError] = useState('');
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    let active = true;
    setData(null); setError('');
    const params = { q: query, limit, offset };
    if (filter !== 'all') params.flagged = true;
    if (filter === 'awaiting') params.decision = 'awaiting_review';
    Promise.all([api.summary(batch), api.customers(batch, params)]).then(([summary, list]) => {
      if (active) setData({ summary, list });
    }).catch(error => { if (active) setError(error.message); });
    return () => { active = false; };
  }, [batch, revision, filter, query, offset, attempt]);
  if (error) return <><ErrorNotice message={error} /><button onClick={() => setAttempt(old => old + 1)}>Try again</button></>;
  if (!data || data.summary.batch.batch_id !== batch) return <p role="status">Loading portfolio…</p>;
  const { summary, list } = data;
  const chooseFilter = value => { setFilter(value); setPage({ batch, offset: 0 }); };
  return <>
    <div className="heading"><div><h1>Monthly overview</h1><p className="muted">Information through {monthLabel(summary.batch.cutoff_month)} · Forecast {forecastLabel(summary.batch.cutoff_month)}</p></div></div>
    <div className="stats">
      <div className="stat"><span>Customers assessed</span><strong className="number">{count(summary.population)}</strong></div>
      <div className="stat"><span>Flagged for review</span><strong className="number">{count(summary.flagged)}</strong><small className="muted">{count(summary.below_threshold)} below the review threshold</small></div>
      <div className="stat"><span>Flagged, awaiting review</span><strong className="number">{count(summary.flagged_review_counts.awaiting_review)}</strong><small className="muted">{count(summary.flagged_review_counts.prioritise)} prioritised for RM</small></div>
    </div>
    <section className="panel"><h2>Customer review queue</h2><p className="muted">Highest predicted risk first. Consider the evidence from both Operations and Finance before deciding.</p>
      <div className="toolbar"><div className="filters" role="group" aria-label="Customer filter">
        {[['flagged','Flagged'],['awaiting','Flagged · awaiting review'],['all','All customers']].map(([key,label]) => <button key={key} aria-pressed={filter === key} onClick={() => chooseFilter(key)}>{label}</button>)}
      </div><form className="search" onSubmit={event => { event.preventDefault(); setQuery(searchText.trim()); setPage({ batch, offset: 0 }); }}><label htmlFor="query" className="muted">Find customer</label><input id="query" type="search" placeholder="Company name or ID" value={searchText} onChange={event => setSearchText(event.target.value)} /><button type="submit">Search</button></form></div>
      <div className="table-wrap"><table><thead><tr><th scope="col">Customer</th><th scope="col">Predicted risk</th><th scope="col">Committee decision</th><th scope="col">Review</th></tr></thead><tbody>
        {list.items.map(c => <tr key={c.prediction_id}><td><Link className="customer-name" to={assessmentLink('/customer/' + encodeURIComponent(c.cus_id), batch)}>{c.customer_name || 'Customer ' + c.cus_id}</Link><div className="muted">ID {c.cus_id}</div></td><td><strong>{percent(c.calibrated_risk)}</strong><br /><RiskBadge flagged={c.review_alert} /></td><td>{decisionLabel(c.review.decision)}</td><td><Link className="button" to={assessmentLink('/customer/' + encodeURIComponent(c.cus_id), batch)}>Open review</Link></td></tr>)}
        {!list.items.length && <tr><td colSpan="4">No customers match these filters.</td></tr>}
      </tbody></table></div>
      <div className="pagination"><span className="muted">{list.total ? `${offset + 1}–${Math.min(offset + limit, list.total)}` : '0'} of {count(list.total)} customers</span><div className="pagination-controls"><button disabled={!offset} onClick={() => setPage({ batch, offset: Math.max(0, offset-limit) })}>Previous</button><button disabled={offset+limit >= list.total} onClick={() => setPage({ batch, offset: offset+limit })}>Next</button></div></div>
    </section>
    <section className="panel"><details><summary>Financial context for flagged customers</summary>
      {[['non_fd_balance_myr','Operating account balances'],['fd_balance_myr','Fixed deposit balances'],['estimated_monthly_fee_myr','Estimated monthly fees'],['estimated_monthly_waiver_myr','Estimated monthly waivers']].map(([key,label]) => {
        const value = summary.finance['flagged_' + key];
        return <div className="signal" key={key}><span>{label}</span><span className="signal-value">{money(value.total)}<br /><small className="muted">{count(value.records_with_value)} of {count(value.records)} have values</small></span></div>;
      })}
      <p className="muted">Balances are exposures. Fees and waivers are separate historical estimates; they do not establish profit or potential savings.</p>
    </details></section>
  </>;
}
