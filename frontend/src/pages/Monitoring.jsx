import React, { useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { api } from '../api.js';
import { count, isNumber, money, monthLabel, percent } from '../format.js';
import { ConnectionState } from '../components/Workspace.jsx';
import { ErrorNotice } from '../components/Common.jsx';
import { BrierBars, TrendChart } from '../components/MonitoringCharts.jsx';
import { curatedFeatures, featureMeta } from '../monitoringFeatures.js';
import { classificationCopy, monitoringCopy } from '../monitoringCopy.js';

const stateText={window_open:'Window open',not_loaded:'Not loaded',partly_loaded:'Partly loaded',loaded:'Loaded'};
const shown=v=>v==null?'Not provided':percent(v);
const points=v=>v==null?'Not provided':`${v>=0?'+':''}${(v*100).toFixed(1)} pts`;
const score=v=>v==null?'Not provided':Number(v).toFixed(3);
const pair=(a,b)=>`${count(a)} of ${count(b)}`;
const shortMonth=v=>new Date(v+'T00:00:00Z').toLocaleDateString('en-MY',{month:'short',year:'numeric',timeZone:'UTC'});
function windowLabel(cutoff) {
  const [year,month]=cutoff.split('-').map(Number);
  const start=new Date(Date.UTC(year,month,1)).toISOString().slice(0,10);
  const end=new Date(Date.UTC(year,month+2,1)).toISOString().slice(0,10);
  return `${shortMonth(start).split(' ')[0]} to ${shortMonth(end)}`;
}
function DeliveryCard({title,data}) {
  return <article className="mon-delivery-card"><h3>{title}</h3><dl>
    <dt>Customers</dt><dd>{count(data.records)}</dd>
    <dt>Observed drop rate</dt><dd>{pair(data.positives,data.records)} ({shown(data.observed_rate)})</dd>
    <dt>Mean predicted risk</dt><dd>{shown(data.mean_risk)}</dd>
    <dt>Flagged that dropped</dt><dd>{pair(data.flagged_positives,data.flagged)}</dd>
  </dl></article>;
}
function ClassificationDetails({stats}) {
  return <details className="mon-classification"><summary>Classification details</summary>
    <p className="muted">Descriptive results at the saved review policy. Missed observed drops: {count(stats.false_negatives)}.</p>
    <div className="table-wrap"><table className="mon-table"><thead><tr><th scope="col">Saved flag</th><th scope="col">Observed drop</th><th scope="col">No observed drop</th></tr></thead><tbody>
      <tr><th scope="row">Flagged</th><td>{count(stats.true_positives)}</td><td>{count(stats.false_positives)}</td></tr>
      <tr><th scope="row">Not flagged</th><td>{count(stats.false_negatives)}</td><td>{count(stats.true_negatives)}</td></tr>
    </tbody></table></div>
    <dl className="mon-classification-facts">
      <dt>Precision</dt><dd>{shown(stats.precision)} ({pair(stats.true_positives,stats.flagged)})</dd><dd>{classificationCopy.precision}</dd>
      <dt>Recall</dt><dd>{shown(stats.recall)} ({pair(stats.true_positives,stats.positives)})</dd><dd>{classificationCopy.recall}</dd>
      <dt>F1</dt><dd>{score(stats.f1)} ({count(2*stats.true_positives)} / {count(2*stats.true_positives+stats.false_positives+stats.false_negatives)})</dd><dd>{classificationCopy.f1}</dd>
    </dl><p className="muted">These results do not justify changing the saved threshold on this historical cohort.</p>
  </details>;
}
function featureValue(v,unit) {
  if (!isNumber(v)) return 'Not provided';
  if(unit==='money') return money(v);
  if(unit==='fraction') return percent(v);
  if(unit==='ratio') return `${new Intl.NumberFormat('en-MY',{maximumFractionDigits:2}).format(v)}×`;
  return new Intl.NumberFormat('en-MY',{maximumFractionDigits:2}).format(v)+(unit==='days'||unit==='months'||unit==='seconds'||unit==='milliseconds'?` ${unit}`:'');
}
function FeatureRows({items,drift}) {
  let last='';
  return items.map(item=>{const meta=featureMeta(item.feature), group=meta.group!==last?meta.group:null;last=meta.group;
    const categorical=item.unit==='categorical total variation';
    const change=categorical?(item.distribution_difference==null?'-':Number(item.distribution_difference).toFixed(2)):
      !isNumber(item.previous_median)||item.previous_median===0||!isNumber(item.current_median)?'-':
      `${((item.current_median/item.previous_median-1)*100).toFixed(1)}%`;
    const availability=item.previous_available<drift.previous_records||item.current_available<drift.current_records?
      <small>Available {count(item.previous_available)} of {count(drift.previous_records)} / {count(item.current_available)} of {count(drift.current_records)}</small>:null;
    return <React.Fragment key={item.feature}>{group&&<tr className="mon-feature-group"><th colSpan="4" scope="rowgroup">{group}</th></tr>}
      <tr><th scope="row">{meta.label}{meta.unit==='saved units'&&<small>Saved units</small>}{availability}</th>
      <td>{categorical?'Category mix':featureValue(item.previous_median,meta.unit)}</td>
      <td>{categorical?'Category mix':featureValue(item.current_median,meta.unit)}</td>
      <td>{categorical?`Mix difference ${change} (0 same, 1 no overlap)`:change}</td></tr></React.Fragment>;
  });
}
export default function Monitoring({batches=[]}) {
  const [params,setParams]=useSearchParams(),batch=params.get('batch_id')||batches[0]?.batch_id;
  const [loadedData,setData]=useState(null),[trend,setTrend]=useState(null),[error,setError]=useState('');
  const [population,setPopulation]=useState('all');
  useEffect(()=>{if(!batch)return;let active=true;setData(null);setTrend(null);setError('');
    Promise.all([api.monitoring(batch),api.monitoringTrend(batch)]).then(([report,series])=>{if(active){setData(report);setTrend(series);}})
      .catch(err=>{if(active)setError(err.message);});return()=>{active=false};},[batch]);
  const data=loadedData?.batch_id===batch?loadedData:null;
  const coverage=data?.outcome_coverage,loaded=coverage?.loaded||0;
  const stats=population==='without_recorded_delivery'?data?.without_recorded_delivery:data?.observed_all;
  const drift=data?.drift;
  const features=drift?.features||[];
  const curated=curatedFeatures.map(name=>features.find(item=>item.feature===name)).filter(Boolean);
  const grouped=items=>Object.values(items.reduce((a,item)=>{(a[featureMeta(item.feature).group]??=[]).push(item);return a;},{})).flat();
  return <>
    <div className="heading"><div><h1>Outcome monitoring</h1><p className="muted">Model-owner and analyst review of saved predictions and later observed outcomes, by monthly assessment.</p></div><ConnectionState unavailable={!!error}>{error?'Saved data unavailable':data?'Connected to saved data':'Loading saved data…'}</ConnectionState></div>
    {error&&<ErrorNotice message={error}/>}
    <section className="panel mon-status"><div className="mon-batch-tabs">{batches.length>6?<><label htmlFor="monitoring-batch">Assessment</label><select id="monitoring-batch" value={batch} onChange={e=>setParams({batch_id:e.target.value})}>{batches.map(b=><option key={b.batch_id} value={b.batch_id}>{monthLabel(b.cutoff_month)}</option>)}</select></>:
      [...batches].reverse().map(b=><button key={b.batch_id} type="button" aria-pressed={batch===b.batch_id} onClick={()=>setParams({batch_id:b.batch_id})}>{shortMonth(b.cutoff_month)}</button>)}{!batches.length&&<p>No saved assessments.</p>}</div>
      {data&&<><div className="mon-status-row"><span className={`mon-state mon-state-${data.state}`}>{stateText[data.state]}</span><div><span className="mon-label">Outcome window</span><strong>{windowLabel(data.cutoff_month)}</strong></div><div className="mon-coverage"><progress value={loaded} max={data.records||1} aria-label="Observed outcome coverage"/><span>{count(loaded)} of {count(data.records)} predictions have an observed outcome</span></div></div>
        {data.state==='window_open'&&<p>Outcomes cannot be assessed yet. The three-month window ends {shortMonth(data.outcome_month)}.</p>}
        {data.state==='not_loaded'&&<><p>The window has ended, but no outcomes are loaded for this assessment.</p><details><summary>Administrator import command</summary><code>python -m flask --app app load-outcomes --batch-id {data.batch_id} --observed-through {data.outcome_month}</code><p>Add <code>--apply</code> to save; requires <code>TXB_RESEARCH_ROOT</code>.</p></details></>}
        {data.state==='partly_loaded'&&<p>{count(coverage.unavailable)} unavailable outcomes are excluded and never counted as zero.</p>}</>}
    </section>
    {data&&<>
      {loaded>0&&<section className="panel mon-panel"><h2>Model performance</h2>
        <label className="mon-population-label" htmlFor="mon-population">Performance population</label>
        <select id="mon-population" value={population} onChange={e=>setPopulation(e.target.value)}>
          <option value="all">All customers with loaded outcomes</option>
          <option value="without_recorded_delivery">Without recorded delivery</option>
        </select>
        <p className="muted">Predicted and observed over the same {count(stats.records)} customers. No verdict is assigned.</p>
        {stats.records>0?<><div className="mon-performance"><div><div className="mon-performance-tiles"><div className="mon-tile mon-tile-navy"><span>Mean predicted risk</span><strong>{shown(stats.mean_risk)}</strong></div><div className="mon-tile mon-tile-rose"><span>Observed drop rate</span><strong>{shown(stats.observed_rate)}</strong></div><div className="mon-tile mon-tile-plain"><span>Gap</span><strong>{points(stats.observed_rate-stats.mean_risk)}</strong></div></div><p className="muted">Navy is predicted, rose is observed, in every chart on this page.</p></div>
          <div><span className="mon-label">Brier score, lower is better</span><p className="muted">Same-group constant reference</p><BrierBars model={stats.brier} reference={stats.reference_brier}/><p>Flagged cases that dropped: {pair(stats.flagged_positives,stats.flagged)}</p></div></div>
          <ClassificationDetails stats={stats}/></>:<p className="mon-empty">No customers with loaded outcomes in this selected population. Performance ratios are unavailable.</p>}
        <p className="muted">Based on {count(stats.records)} of {count(loaded)} customers with loaded outcomes; {count(data.records)} saved predictions in this assessment.</p>
        {coverage.documented_delivery>0&&<p className="muted">All-customer results include documented delivery during the outcome window. Without recorded delivery does not mean no intervention occurred.</p>}
      </section>}
      {loaded>0&&<section className="panel mon-panel"><h2>Recorded delivery and outcomes</h2><p>{count(coverage.documented_delivery)} of {count(loaded)} loaded customers have a documented delivery.</p>
        {coverage.documented_delivery>0?<div className="mon-delivery-grid"><DeliveryCard title="Documented delivery" data={data.documented_delivery}/><DeliveryCard title="No recorded delivery" data={data.without_recorded_delivery}/></div>:<p className="mon-empty">No documented deliveries were recorded for customers with loaded outcomes.</p>}
        <p className="muted">Delivery actions: RM visit {count(data.delivery_types?.rm_visit||0)} · Customer contact {count(data.delivery_types?.customer_contact||0)} · Service fix {count(data.delivery_types?.service_fix||0)}. Counts are actions, not customers.</p>
        <p className="muted">Groups are selected, not controlled. No recorded delivery does not prove nothing happened.</p></section>}
      <section className="panel mon-panel"><h2>Cross-month comparison</h2><p className="muted">{count(trend?.batches?.length)} assessments under the same frozen protocol. Each month uses all customers with loaded outcomes, independent of the Model performance selector. Not a fitted trend.</p><TrendChart batches={trend?.batches||[]}/>
        <div className="table-wrap"><table className="mon-table"><thead><tr>{['Assessment','State','Loaded','Predicted','Observed','Gap','Brier','Reference','Flagged share'].map(label=><th key={label} scope="col">{label}</th>)}</tr></thead><tbody>{trend?.batches?.map(item=><tr key={item.batch_id} className={item.batch_id===batch?'mon-selected':''}><th scope="row">{shortMonth(item.cutoff_month)}</th><td><span className={`mon-state mon-state-${item.state}`}>{stateText[item.state]}</span></td><td>{count(item.loaded)} of {count(item.records)}</td><td>{item.loaded?shown(item.mean_risk_loaded):'Not provided'}</td><td>{shown(item.observed_rate)}</td><td>{points(item.gap)}</td><td>{score(item.brier)}</td><td>{score(item.reference_brier)}</td><td>{shown(item.flagged_rate_all)}</td></tr>)}</tbody></table></div></section>
      <section className="panel mon-panel"><h2>Input and risk movement</h2>{drift?<><p className="muted">Compared with {shortMonth(drift.previous_month)}, same protocol. Descriptive only; no alert threshold.</p><div className="mon-movement"><div><span className="mon-label">Mean predicted risk</span><strong>from {shown(drift.previous_mean_risk)} to {shown(drift.current_mean_risk)}, {points(drift.current_mean_risk-drift.previous_mean_risk)}</strong></div><div><span className="mon-label">Flagged share</span><strong>from {shown(drift.previous_flagged_rate)} to {shown(drift.current_flagged_rate)}, {points(drift.current_flagged_rate-drift.previous_flagged_rate)}</strong></div></div>
        <div className="table-wrap"><table className="mon-table"><thead><tr><th>Feature</th><th>Earlier</th><th>Selected</th><th>Change</th></tr></thead><tbody><FeatureRows items={grouped(curated)} drift={drift}/></tbody></table></div>
        <details className="mon-expander"><summary>Show all 78 features</summary><div className="table-wrap"><table className="mon-table"><thead><tr><th>Feature</th><th>Earlier</th><th>Selected</th><th>Change</th></tr></thead><tbody><FeatureRows items={features} drift={drift}/></tbody></table></div></details></>:<p>There is no earlier saved assessment under the same protocol to compare.</p>}</section>
      <section className="panel mon-panel"><details><summary>How to read this page</summary>{monitoringCopy.map(text=><p key={text}>{text}</p>)}<p>{data.interpretation}</p></details></section>
    </>}
  </>;
}
