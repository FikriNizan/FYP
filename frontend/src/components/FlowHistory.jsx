import React from 'react';
import { isNumber, money, monthLabel } from '../format.js';

export default function FlowHistory({ history = [], baseline }) {
  const rows = history.filter(r => isNumber(r.combined_flow_myr));
  if (!rows.length) return <section className="panel"><h2>Recorded transaction activity</h2><p className="muted">No transaction history was provided for this assessment.</p></section>;
  const top = Math.max(1, ...rows.map(r => r.combined_flow_myr), isNumber(baseline) ? baseline : 0) * 1.1;
  const x = i => 80 + i * (650 / rows.length);
  const y = value => 215 - (value / top) * 170;
  const tick = value => top >= 1e6 ? (value/1e6).toFixed(1)+'m' : top >= 1000 ? (value/1000).toFixed(1)+'k' : Math.round(value).toLocaleString('en-MY');
  return <section className="panel"><h2>Recorded transaction activity</h2>
    <svg className="chart" viewBox="0 0 780 255" role="img" aria-label="Monthly combined transaction values, with a zero baseline. Exact amounts are in the table below.">
      {[0,.5,1].map(f => <g key={f}><line className="grid" x1="75" x2="750" y1={y(f*top)} y2={y(f*top)} /><text x="4" y={y(f*top)+4}>{tick(f*top)}</text></g>)}
      {rows.map((row,i) => <g key={row.snapshot_month}><rect x={x(i)} y={y(row.combined_flow_myr)} width={650/rows.length*.65} height={Math.max(0,215-y(row.combined_flow_myr))} fill={i >= rows.length-3 ? '#6154d9' : '#9ca9bf'}><title>{monthLabel(row.snapshot_month)}: {money(row.combined_flow_myr)}</title></rect><text x={x(i)} y="238">{new Date(row.snapshot_month+'T00:00:00Z').toLocaleDateString('en-MY',{month:'short',timeZone:'UTC'})}</text></g>)}
      {isNumber(baseline) && <line className="baseline" x1="75" x2="750" y1={y(baseline)} y2={y(baseline)} />}
    </svg>
    <div className="legend"><span>Earlier months</span><span>Latest three observed months</span></div>
    <p className="muted">Combined incoming and successful outgoing transactions, MYR. {isNumber(baseline) ? 'Dashed line: trailing twelve-month monthly average.' : ''}</p>
    <details><summary>Read exact monthly amounts</summary><div className="table-wrap"><table><thead><tr><th scope="col">Month</th><th scope="col">Incoming</th><th scope="col">Successful outgoing</th><th scope="col">Combined</th></tr></thead><tbody>{history.map(row => <tr key={row.snapshot_month}><td>{monthLabel(row.snapshot_month)}</td><td>{money(row.inbound_myr)}</td><td>{money(row.outbound_success_myr)}</td><td>{money(row.combined_flow_myr)}</td></tr>)}</tbody></table></div></details>
  </section>;
}
