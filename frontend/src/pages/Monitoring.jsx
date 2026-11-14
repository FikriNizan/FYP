import React, { useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { api } from '../api.js';
import { count, monthLabel, percent } from '../format.js';
import { ConnectionState } from '../components/Workspace.jsx';
import { ErrorNotice } from '../components/Common.jsx';

const shown = value => value == null ? 'Not available' : percent(value);
const fixed = value => value == null ? 'Not available' : Number(value).toFixed(3);

function Group({ title, data }) {
  return <article className="context-card"><h3>{title}</h3><p><strong>{count(data.records)}</strong> outcomes</p>
    <dl className="monitoring-facts"><dt>Observed volume-drop rate</dt><dd>{shown(data.observed_rate)}</dd>
      <dt>Mean saved predicted risk</dt><dd>{shown(data.mean_risk)}</dd>
      <dt>Brier score</dt><dd>{fixed(data.brier)}</dd>
      <dt>Flagged cases with observed drop</dt><dd>{shown(data.flagged_positive)}</dd></dl></article>;
}

export default function Monitoring({ batches }) {
  const [params, setParams] = useSearchParams();
  const batch = params.get('batch_id') || batches[0]?.batch_id;
  const [data, setData] = useState(null);
  const [error, setError] = useState('');
  useEffect(() => {
    if (!batch) return;
    let active = true;
    setData(null); setError('');
    api.monitoring(batch).then(result => { if (active) setData(result); })
      .catch(err => { if (active) setError(err.message); });
    return () => { active = false; };
  }, [batch]);
  const drift = data?.drift;
  const examples = ['combined_flow_mean_3m_myr','combined_flow_mean_12m_myr','login_failure_rate_3m',
    'outbound_failure_rate_3m','non_fd_balance_myr','fd_balance_myr','tier_id','customer_type','sector_code'];
  return <>
    <div className="heading"><div><h1>Outcome monitoring</h1><p className="muted">Observed volume drops, recorded follow-up delivery and saved predictions remain separate.</p></div><ConnectionState unavailable={!!error}>{error ? 'Saved data unavailable' : data ? 'Connected to saved data' : 'Loading saved data…'}</ConnectionState></div>
    <section className="panel"><h2>Assessment to inspect</h2><label htmlFor="monitoring-batch">Assessment</label>{batches.length ?
      <select id="monitoring-batch" value={batch} onChange={event=>setParams({batch_id:event.target.value})}>{batches.map(item=><option key={item.batch_id} value={item.batch_id}>{monthLabel(item.cutoff_month)} · {count(item.record_count)} customers · {item.batch_id.slice(0,6)}</option>)}</select> : <p>No saved assessments.</p>}
      <p className="muted">Outcomes are loaded by an explicit administrator action after the full three-month window is recorded. This page does not create labels from later assessments.</p></section>
    {error && <ErrorNotice message={error}/>}
    {data && <>
      <section className="panel"><h2>Outcome availability</h2><p className="muted">{monthLabel(data.cutoff_month)} assessment · outcome window ends {monthLabel(data.outcome_month)}.</p>
        <div className="monitoring-counts"><div><span>Saved predictions</span><strong>{count(data.records)}</strong></div><div><span>Observed outcomes loaded</span><strong>{count(data.outcome_coverage.loaded)}</strong></div><div><span>Outcome unavailable</span><strong>{count(data.outcome_coverage.unavailable)}</strong></div><div><span>Documented delivery in window</span><strong>{count(data.outcome_coverage.documented_delivery)}</strong></div></div>
        <p className="muted">Unavailable includes outcomes not imported or incomplete source coverage. It is never counted as a zero or a negative outcome.</p></section>
      <section className="panel"><h2>Descriptive observed outcomes</h2><p className="muted">Delivery means a saved, completed RM visit, customer contact or service fix dated inside this assessment's next three months. Planned work, attempts and notes do not qualify.</p>
        <div className="context-grid"><Group title="Documented delivery" data={data.documented_delivery}/><Group title="No recorded delivery" data={data.without_recorded_delivery}/></div>
        <p className="muted">No recorded delivery does not prove that no action occurred. These groups are selected, not a controlled comparison. Differences do not prove retention benefit or model error.</p></section>
      <section className="panel"><h2>Input and risk movement</h2>{drift ? <><p className="muted">Compared with {monthLabel(drift.previous_month)} under the same frozen protocol. Descriptive movement only; no alert threshold is assigned.</p>
        <div className="monitoring-counts"><div><span>Mean risk, earlier</span><strong>{shown(drift.previous_mean_risk)}</strong></div><div><span>Mean risk, selected</span><strong>{shown(drift.current_mean_risk)}</strong></div><div><span>Flagged share, earlier</span><strong>{shown(drift.previous_flagged_rate)}</strong></div><div><span>Flagged share, selected</span><strong>{shown(drift.current_flagged_rate)}</strong></div></div>
        <div className="table-wrap"><table><thead><tr><th scope="col">Saved feature</th><th scope="col">Earlier available</th><th scope="col">Selected available</th><th scope="col">Earlier median / distribution</th><th scope="col">Selected median / distribution</th></tr></thead><tbody>
          {examples.map(name=>drift.features.find(item=>item.feature===name)).filter(Boolean).map(item=><tr key={item.feature}><th scope="row">{item.feature.replaceAll('_',' ')}</th><td>{count(item.previous_available)} / {count(drift.previous_records)}</td><td>{count(item.current_available)} / {count(drift.current_records)}</td><td>{item.previous_median == null ? 'Category mix' : fixed(item.previous_median)}</td><td>{item.current_median == null ? (item.distribution_difference == null ? 'Not available' : `Category distribution difference ${fixed(item.distribution_difference)}`) : fixed(item.current_median)}</td></tr>)}
        </tbody></table></div><p className="muted">Numeric medians use each feature's saved units. Category difference ranges from 0 (same mix) to 1 (no overlap). Availability is shown beside every comparison.</p></> : <p>There is no earlier saved assessment under the same protocol to compare.</p>}</section>
      <p className="muted">{data.interpretation}</p>
    </>}
  </>;
}
