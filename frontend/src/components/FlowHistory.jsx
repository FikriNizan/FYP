import React, { useState } from 'react';
import { isNumber, money, monthLabel } from '../format.js';
import { observedMonths } from '../flows.js';

export default function FlowHistory({ history = [], baseline, cutoff }) {
  const [measure,setMeasure] = useState('combined_flow_myr');
  const rows = observedMonths(history,cutoff);
  const labels = {combined_flow_myr:'Combined flow',inbound_myr:'Incoming flow',outbound_success_myr:'Successful outgoing flow'};
  if (!rows.length) return <section className="panel"><h2>Recorded transaction activity</h2><p className="muted">No transaction history was provided for this assessment.</p></section>;
  const reference = measure==='combined_flow_myr' && isNumber(baseline) ? baseline : null;
  const top = Math.max(1, ...rows.map(r => isNumber(r[measure]) ? r[measure] : 0), reference || 0) * 1.1;
  const x = i => 80 + i * (650 / rows.length);
  const y = value => 215 - (value / top) * 170;
  const tick = value => top >= 1e6 ? (value/1e6).toFixed(1)+'m' : top >= 1000 ? (value/1000).toFixed(1)+'k' : Math.round(value).toLocaleString('en-MY');
  const latest = rows.at(-1), previous = rows.at(-2);
  const takeaway = isNumber(latest[measure]) ? `${monthLabel(latest.snapshot_month)}: ${money(latest[measure])}.`
    : `${monthLabel(latest.snapshot_month)}: this measure was not provided.`;
  return <section className="panel"><div className="section-heading"><div><h2>Recorded transaction activity</h2><p className="muted">How has activity changed? · {monthLabel(rows[0].snapshot_month)}–{monthLabel(latest.snapshot_month)}</p></div><label className="chart-control">Measure<select value={measure} onChange={e=>setMeasure(e.target.value)}>{Object.entries(labels).map(([key,label])=><option key={key} value={key}>{label}</option>)}</select></label></div>
    <p className="chart-takeaway">{takeaway}{isNumber(latest[measure]) && isNumber(previous?.[measure]) && previous[measure]>0 && <> {Math.abs((latest[measure]/previous[measure]-1)*100).toFixed(1)}% {latest[measure]>=previous[measure] ? 'higher' : 'lower'} than the previous recorded month.</>}</p>
    <svg className="chart" viewBox="0 0 780 280" role="img" aria-label={`${labels[measure]} by observed month in MYR. Missing months are gaps. Exact amounts are in the table below.`}>
      <text x="4" y="22">MYR</text>
      {[0,.5,1].map(f => <g key={f}><line className="grid" x1="75" x2="750" y1={y(f*top)} y2={y(f*top)} /><text x="4" y={y(f*top)+4}>{tick(f*top)}</text></g>)}
      {rows.map((row,i) => <g key={row.snapshot_month}>{isNumber(row[measure]) ? <rect x={x(i)} y={y(row[measure])} width={650/rows.length*.65} height={Math.max(0,215-y(row[measure]))} fill={i >= rows.length-3 ? '#356bd9' : '#c6d5ed'}><title>{monthLabel(row.snapshot_month)}: {money(row[measure])}</title></rect> : <text x={x(i)} y="206"><title>{monthLabel(row.snapshot_month)}: Not provided</title>—</text>}<text x={x(i)} y="238">{new Date(row.snapshot_month+'T00:00:00Z').toLocaleDateString('en-MY',{month:'short',timeZone:'UTC'})}</text></g>)}
      {reference !== null && <line className="baseline" x1="75" x2="750" y1={y(reference)} y2={y(reference)} />}
      <text x="345" y="270">Observed month</text>
    </svg>
    <div className="legend"><span>Earlier months</span><span>Latest three calendar months</span></div>
    <p className="muted">{labels[measure]}, MYR. Gaps mean not provided; zero remains zero. {reference !== null ? 'Dashed line: trailing twelve-month monthly average of combined flow.' : ''}</p>
    <details><summary>Read exact monthly amounts</summary><div className="table-wrap"><table><thead><tr><th scope="col">Month</th><th scope="col">Incoming (MYR)</th><th scope="col">Successful outgoing (MYR)</th><th scope="col">Combined (MYR)</th></tr></thead><tbody>{rows.map(row => <tr key={row.snapshot_month}><td>{monthLabel(row.snapshot_month)}</td><td>{money(row.inbound_myr)}</td><td>{money(row.outbound_success_myr)}</td><td>{money(row.combined_flow_myr)}</td></tr>)}</tbody></table></div></details>
  </section>;
}
