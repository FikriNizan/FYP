import React, { useState } from 'react';
import { isNumber, money, monthLabel } from '../format.js';
import { observedMonths } from '../flows.js';

const WIDTH = 780, HEIGHT = 280, PLOT_LEFT = 75, PLOT_RIGHT = 640;
const compact = value => value >= 1e6 ? 'RM ' + (value / 1e6).toFixed(2) + 'm' : value >= 1e3 ? 'RM ' + Math.round(value / 1e3) + 'k' : 'RM ' + Math.round(value);

export default function FlowHistory({ history = [], baseline, cutoff }) {
  const [measure,setMeasure] = useState('combined_flow_myr');
  const [active,setActive] = useState(null);
  const rows = observedMonths(history,cutoff);
  const labels = {combined_flow_myr:'Combined flow',inbound_myr:'Incoming flow',outbound_success_myr:'Successful outgoing flow'};
  if (!rows.length) return <section className="panel"><h2>Recorded transaction activity</h2><p className="muted">No transaction history was provided for this assessment.</p></section>;
  // The volume-attrition rule uses a positive trailing twelve-month average of combined flow.
  const average = measure==='combined_flow_myr' && isNumber(baseline) && baseline > 0 ? baseline : null;
  const attrition = average === null ? null : average / 2;
  const top = Math.max(1, ...rows.map(r => isNumber(r[measure]) ? r[measure] : 0), average || 0) * 1.1;
  const step = (PLOT_RIGHT - PLOT_LEFT) / rows.length, barWidth = step * .65;
  const x = i => PLOT_LEFT + 8 + i * step;
  const y = value => 215 - (value / top) * 170;
  const tick = value => top >= 1e6 ? (value/1e6).toFixed(1)+'m' : top >= 1000 ? (value/1000).toFixed(1)+'k' : Math.round(value).toLocaleString('en-MY');
  const latest = rows.at(-1), previous = rows.at(-2);
  const takeaway = isNumber(latest[measure]) ? `${monthLabel(latest.snapshot_month)}: ${money(latest[measure])}.`
    : `${monthLabel(latest.snapshot_month)}: this measure was not provided.`;
  const averageY = average === null ? 0 : y(average);
  const attritionY = attrition === null ? 0 : y(attrition);
  const attritionLabelY = Math.min(Math.max(attritionY, averageY + 34), 232);
  const hovered = active === null ? null : rows[active];
  const hoveredValue = hovered && isNumber(hovered[measure]) ? hovered[measure] : null;
  const tipLeft = hovered ? Math.min(Math.max((x(active) + barWidth / 2) / WIDTH * 100, 15), 80) : 0;
  const tipTop = hovered ? (hoveredValue === null ? 150 : y(hoveredValue)) / HEIGHT * 100 : 0;
  return <section className="panel"><div className="section-heading"><div><h2>Recorded transaction activity</h2><p className="muted">How has activity changed? · {monthLabel(rows[0].snapshot_month)}–{monthLabel(latest.snapshot_month)}</p></div><label className="chart-control">Measure<select value={measure} onChange={e=>{setMeasure(e.target.value);setActive(null);}}>{Object.entries(labels).map(([key,label])=><option key={key} value={key}>{label}</option>)}</select></label></div>
    <p className="chart-takeaway">{takeaway}{isNumber(latest[measure]) && isNumber(previous?.[measure]) && previous[measure]>0 && <> {Math.abs((latest[measure]/previous[measure]-1)*100).toFixed(1)}% {latest[measure]>=previous[measure] ? 'higher' : 'lower'} than the previous recorded month.</>}</p>
    <div className="chart-wrap" style={{position:'relative'}}>
    <svg className="chart" viewBox={`0 0 ${WIDTH} ${HEIGHT}`} role="img" aria-label={`${labels[measure]} by observed month in MYR. Missing months are gaps.${average !== null ? ' Two reference lines show the trailing twelve-month average and the attrition reference, which is half of that average.' : ''} Exact amounts are in the table below.`}>
      <text x="4" y="22">MYR</text>
      {[0,.5,1].map(f => <g key={f}><line className="grid" x1={PLOT_LEFT} x2={PLOT_RIGHT} y1={y(f*top)} y2={y(f*top)} /><text x="4" y={y(f*top)+4}>{tick(f*top)}</text></g>)}
      {rows.map((row,i) => <g key={row.snapshot_month} className={'col'+(active === i ? ' is-active' : '')}>
        {isNumber(row[measure]) ? <rect x={x(i)} y={y(row[measure])} width={barWidth} height={Math.max(0,215-y(row[measure]))} className={i >= rows.length-3 ? 'bar-recent' : 'bar-earlier'} /> : <text x={x(i)} y="206">—</text>}
        <text x={x(i)} y="238">{new Date(row.snapshot_month+'T00:00:00Z').toLocaleDateString('en-MY',{month:'short',timeZone:'UTC'})}</text>
        <path className="hit" d={`M${PLOT_LEFT+i*step} 40 h${step} V215 h${-step} Z`} fill="transparent" onPointerEnter={()=>setActive(i)} onPointerLeave={()=>setActive(null)} onPointerDown={()=>setActive(i)} />
      </g>)}
      {average !== null && <g>
        <line className="baseline" x1={PLOT_LEFT} x2={PLOT_RIGHT} y1={averageY} y2={averageY} stroke="#3c4a7d" strokeWidth="1.75" strokeDasharray="1 5" strokeLinecap="round" />
        <text className="line-label average" x={PLOT_RIGHT + 10} y={averageY + 3}>12-month average</text><text className="line-value average" x={PLOT_RIGHT + 10} y={averageY + 16}>{compact(average)}</text>
        <line className="reference-line" x1={PLOT_LEFT} x2={PLOT_RIGHT} y1={attritionY} y2={attritionY} stroke="#d92550" strokeWidth="1.5" strokeDasharray="7 4" />
        <text className="line-label attrition" x={PLOT_RIGHT + 10} y={attritionLabelY + 3}>Attrition reference</text><text className="line-value attrition" x={PLOT_RIGHT + 10} y={attritionLabelY + 16}>{compact(attrition)}</text>
      </g>}
      <text x="345" y="270">Observed month</text>
    </svg>
    {hovered && <div className="chart-tooltip" aria-hidden="true" style={{position:'absolute',left:tipLeft+'%',top:tipTop+'%',transform:`translate(${-tipLeft}%,calc(-100% - 10px))`,pointerEvents:'none'}}>
      <strong>{monthLabel(hovered.snapshot_month)}</strong>
      <span>{hoveredValue === null ? labels[measure]+': not provided' : `${labels[measure]}: ${money(hoveredValue)}`}</span>
      {hoveredValue !== null && average !== null && <span>{Math.abs((hoveredValue/average-1)*100).toFixed(1)}% {hoveredValue >= average ? 'above' : 'below'} the 12-month average</span>}
    </div>}
    </div>
    <div className="legend"><span className="key-earlier">Earlier months</span><span className="key-recent">Latest three calendar months</span>{average !== null && <><span className="key-average">12-month average</span><span className="key-attrition">Attrition reference</span></>}</div>
    {average !== null && <p className="chart-reference-note"><strong>How to read the lines.</strong> The dotted line is the trailing twelve-month average of combined flow. The red dashed line is the attrition reference: half of that average. The defined drop is a next-three-month average at or below this reference. Those months are not yet observed, so the line shows the reference level, not an outcome.</p>}
    <p className="muted">{labels[measure]}, MYR. Gaps mean not provided; zero remains zero.{average === null ? ' No positive trailing twelve-month average was provided, so reference lines are not drawn.' : ''}</p>
    <details><summary>Read exact monthly amounts</summary><div className="table-wrap"><table><thead><tr><th scope="col">Month</th><th scope="col">Incoming (MYR)</th><th scope="col">Successful outgoing (MYR)</th><th scope="col">Combined (MYR)</th></tr></thead><tbody>{rows.map(row => <tr key={row.snapshot_month}><td>{monthLabel(row.snapshot_month)}</td><td>{money(row.inbound_myr)}</td><td>{money(row.outbound_success_myr)}</td><td>{money(row.combined_flow_myr)}</td></tr>)}</tbody></table></div></details>
  </section>;
}
