import React, { useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { api } from '../api.js';
import { count, forecastLabel, isNumber, money, monthLabel, percent, readyAfterLabel } from '../format.js';
import { ErrorNotice } from '../components/Common.jsx';
import Icon from '../components/Icon.jsx';
import RateShock from '../components/RateShock.jsx';

// Every figure comes from /api/monitoring and /api/monitoring/trend; outcomes are never invented or counted as zero.
const TABS = [['outcomes', 'Outcomes', 'yes'], ['rate-shock', 'Rate-shock what-if', 'up']];
const score = v => isNumber(v) ? Number(v).toFixed(2) : 'Not provided';
const whole = v => isNumber(v) ? count(Math.round(v)) : 'Not provided';
const readiness = check => !check ? 'Not provided' : check.state === 'checked' ? 'Ready' : check.state === 'waiting' ? readyAfterLabel(check.ready_after_month) : 'Not checked';

function Tabs({ tab, choose }) {
  return <div className="perspective-tabs" role="tablist" aria-label="Monitoring view">{TABS.map(([key, label, icon]) =>
    <button key={key} type="button" role="tab" aria-selected={tab === key} tabIndex={tab === key ? 0 : -1} onClick={() => choose(key)}><Icon name={icon} />{label}</button>)}</div>;
}

function Readiness({ items, batch, choose }) {
  return <section className="panel" aria-labelledby="ready-title"><h2 id="ready-title">Which assessments can be checked</h2>
    <p className="muted">Each assessment is checked automatically once its three forecast months of data are uploaded.</p>
    <div className="ready">{items.map(item => { const ready = item.outcome_check?.state === 'checked';
      return <button key={item.batch_id} type="button" className="rstep" aria-pressed={item.batch_id === batch} onClick={() => choose(item.batch_id)}>
        <span className={'round ' + (ready ? 'green' : 'warn')}><Icon name={ready ? 'yes' : 'clock'} /></span>
        <span><b>{monthLabel(item.cutoff_month)}</b><span className="muted">{readiness(item.outcome_check)}</span></span></button>; })}</div>
  </section>;
}

function Matrix({ stats }) {
  return <div className="matrix" role="table" aria-label="Flags against observed outcomes">
    <span role="presentation" /><span className="mhead" role="columnheader">Activity halved</span><span className="mhead" role="columnheader">Activity held</span>
    <span className="mrow" role="rowheader">Flagged</span>
    <div className="mcell m-hit" role="cell"><b>{count(stats.true_positives)}</b><span>Caught</span></div>
    <div className="mcell m-fa" role="cell"><b>{count(stats.false_positives)}</b><span>False alarm</span><small>May include customers an RM kept</small></div>
    <span className="mrow" role="rowheader">Not flagged</span>
    <div className="mcell m-miss" role="cell"><b>{count(stats.false_negatives)}</b><span>Missed</span></div>
    <div className="mcell m-quiet" role="cell"><b>{count(stats.true_negatives)}</b><span>Correctly quiet</span></div>
  </div>;
}

function FollowUp({ title, data }) {
  const total = data.records || 0;
  return <div className="fu"><span><b>{title}</b><br /><span className="muted">{count(total)} {total === 1 ? 'customer' : 'customers'}</span></span>
    {total ? <div className="stack" role="img" aria-label={`${data.positives} halved, ${data.negatives} held`}>
      {data.positives > 0 && <span className="halved" style={{ width: data.positives / total * 100 + '%' }}>{count(data.positives)}</span>}
      {data.negatives > 0 && <span className="held" style={{ width: data.negatives / total * 100 + '%' }}>{count(data.negatives)}</span>}
    </div> : <span className="muted">None recorded</span>}</div>;
}

function Results({ data }) {
  const stats = data.observed_all, coverage = data.outcome_coverage, month = monthLabel(data.cutoff_month);
  const largest = Math.max(stats.expected_positives || 0, stats.positives || 0) || 1;
  const comparison = !isNumber(stats.expected_positives) ? '' : stats.positives > stats.expected_positives ? 'More drops than the predicted risk expected.' : stats.positives < stats.expected_positives ? 'Fewer drops than the predicted risk expected.' : 'As many drops as the predicted risk expected.';
  return <div className="two-columns">
    <section className="panel" aria-labelledby="flags-title"><h2 id="flags-title">How did {month}'s flags turn out?</h2>
      <p className="muted">{count(coverage.loaded)} customers · outcomes observed {forecastLabel(data.cutoff_month)}</p>
      {coverage.unavailable > 0 && <p className="muted">{count(coverage.unavailable)} unavailable outcomes are excluded and never counted as zero.</p>}
      <Matrix stats={stats} />
      <div className="plain">
        <p><span className="round"><Icon name="info" /></span><span><b>{count(stats.true_positives)} of {count(stats.flagged)}</b> flags were real drops ({percent(stats.precision)}).</span></p>
        <p><span className="round"><Icon name="info" /></span><span>The model caught <b>{count(stats.true_positives)} of {count(stats.positives)}</b> drops ({percent(stats.recall)}).</span></p>
      </div>
      <p className="muted">F1 {score(stats.f1)}</p>
    </section>
    <div>
      <section className="panel" aria-labelledby="expected-title"><h2 id="expected-title">Expected vs actual drops</h2><p className="muted">Does the predicted risk match what happened?</p>
        <div className="activity-row usual"><span><b>Expected</b><br /><span className="muted">sum of predicted risk</span></span><span className="activity-track" aria-hidden="true"><i style={{ width: (stats.expected_positives || 0) / largest * 100 + '%' }} /></span><strong>{whole(stats.expected_positives)}</strong></div>
        <div className="activity-row recent"><span><b>Actual</b><br /><span className="muted">observed drops</span></span><span className="activity-track" aria-hidden="true"><i style={{ width: (stats.positives || 0) / largest * 100 + '%' }} /></span><strong>{count(stats.positives)}</strong></div>
        <p>{comparison}</p></section>
      <section className="panel" aria-labelledby="followed-title"><h2 id="followed-title">Were flags followed up?</h2><p className="muted">Follow-up recorded inside the {forecastLabel(data.cutoff_month)} window</p>
        <FollowUp title="With recorded follow-up" data={data.documented_delivery} />
        <FollowUp title="No recorded follow-up" data={data.without_recorded_delivery} />
        <div className="key"><span><i className="halved" />Activity halved</span><span><i className="held" />Activity held</span></div>
        <p className="hint"><span className="round small"><Icon name="info" /></span><span>A followed-up customer who held their activity counts as a false alarm, but the RM may have kept them. No record does not prove no contact.</span></p></section>
    </div>
  </div>;
}

function MonthByMonth({ items }) {
  const cell = (item, value) => item.outcome_check?.state === 'checked' ? value : <span className="muted">{readiness(item.outcome_check)}</span>;
  return <section className="panel" aria-labelledby="months-title"><h2 id="months-title">Month by month</h2><p className="muted">Checked assessments only</p>
    <div className="table-wrap"><table className="mon-table sens"><thead><tr><th scope="col">Measure</th>{items.map(i => <th key={i.batch_id} scope="col">{monthLabel(i.cutoff_month)}</th>)}</tr></thead><tbody>
      <tr><th scope="row">Flags that were real drops</th>{items.map(i => <td key={i.batch_id}>{cell(i, percent(i.precision))}</td>)}</tr>
      <tr><th scope="row">Drops the model caught</th>{items.map(i => <td key={i.batch_id}>{cell(i, percent(i.recall))}</td>)}</tr>
      <tr><th scope="row">Expected vs actual drops</th>{items.map(i => <td key={i.batch_id}>{cell(i, `${whole(i.expected_positives)} / ${count(i.positives)}`)}</td>)}</tr>
    </tbody></table></div></section>;
}

function Movement({ data }) {
  const drift = data.drift;
  const flow = drift?.features?.find(f => f.feature === 'combined_flow_mean_1m_myr');
  return <section className="panel" aria-labelledby="movement-title"><h2 id="movement-title">Input movement since last month</h2>
    {drift ? <><p className="muted">{monthLabel(data.cutoff_month)} compared with {monthLabel(drift.previous_month)} · available before outcomes arrive</p>
      <div className="table-wrap"><table className="mon-table sens"><thead><tr><th scope="col">Measure</th><th scope="col">{monthLabel(drift.previous_month)}</th><th scope="col">{monthLabel(data.cutoff_month)}</th></tr></thead><tbody>
        <tr><th scope="row">Average predicted risk</th><td>{percent(drift.previous_mean_risk)}</td><td>{percent(drift.current_mean_risk)}</td></tr>
        <tr><th scope="row">Flagged customers</th><td>{count(drift.previous_flagged)}</td><td>{count(drift.current_flagged)}</td></tr>
        <tr><th scope="row">Median combined flow, latest month</th><td>{money(flow?.previous_median)}</td><td>{money(flow?.current_median)}</td></tr>
      </tbody></table></div><p className="muted">Descriptive only; no alert threshold. For a rate-shock what-if, see the other tab.</p></>
      : <p>There is no earlier saved assessment under the same protocol to compare.</p>}
  </section>;
}

function Outcomes({ batches }) {
  const [params, setParams] = useSearchParams();
  const batch = params.get('batch_id') || batches[0]?.batch_id;
  const [loaded, setLoaded] = useState(null), [trend, setTrend] = useState(null), [error, setError] = useState('');
  useEffect(() => { if (!batch) return; let active = true; setLoaded(null); setTrend(null); setError('');
    Promise.all([api.monitoring(batch), api.monitoringTrend(batch)]).then(([report, series]) => { if (active) { setLoaded(report); setTrend(series); } })
      .catch(e => { if (active) setError(e.message); });
    return () => { active = false; }; }, [batch]);
  const choose = id => { const next = new URLSearchParams(params); next.set('batch_id', id); setParams(next); };
  if (!batches.length) return <p>No saved assessments.</p>;
  if (error) return <ErrorNotice message={error} />;
  const data = loaded?.batch_id === batch ? loaded : null;
  if (!data || !trend) return <p role="status">Loading saved outcomes…</p>;
  const items = trend.batches || [];
  const anyChecked = items.some(i => i.outcome_check?.state === 'checked');
  const check = data.outcome_check;
  const month = monthLabel(data.cutoff_month);
  return <>
    <Readiness items={items} batch={batch} choose={choose} />
    {data.outcome_coverage.loaded > 0 ? <Results data={data} /> :
      <section className="panel"><div className="callout"><span className="round warn"><Icon name="clock" /></span><div>
        <p><b>{anyChecked ? `${month} cannot be checked yet.` : 'Nothing to check yet.'}</b></p>
        <p className="muted">{check?.state === 'not_checked'
          ? `${month}'s forecast months are published, but no outcomes are saved for it.`
          : `${month} forecasts ${forecastLabel(data.cutoff_month)}. It becomes checkable when the ${monthLabel(check?.ready_after_month)} package is uploaded in Monthly Assessments.`}</p></div></div></section>}
    <div className="two-columns"><MonthByMonth items={items} /><Movement data={data} /></div>
  </>;
}

export default function Monitoring({ batches = [] }) {
  const [params, setParams] = useSearchParams();
  const tab = params.get('tab') === 'rate-shock' ? 'rate-shock' : 'outcomes';
  const choose = key => { const next = new URLSearchParams(params); key === 'outcomes' ? next.delete('tab') : next.set('tab', key); setParams(next); };
  return <>
    <div className="heading"><div><h1>Monitoring</h1><p className="muted">Is the model still doing its job? Outcomes are checked automatically; the what-if is a hypothetical demonstration.</p></div></div>
    <Tabs tab={tab} choose={choose} />
    <div role="tabpanel" aria-label={tab === 'outcomes' ? 'Outcomes' : 'Rate-shock what-if'}>{tab === 'outcomes' ? <Outcomes batches={batches} /> : <RateShock />}</div>
  </>;
}
