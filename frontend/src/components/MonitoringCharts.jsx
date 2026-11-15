import React from 'react';
import { count, percent } from '../format.js';

const score = value => value == null ? 'Not provided' : Number(value).toFixed(3);

export function BrierBars({ model, reference }) {
  const max = Math.max(model || 0,reference || 0,0.01);
  const width = value => value == null ? 0 : 160*value/max;
  return <svg className="mon-brier" viewBox="0 0 360 88" role="img" aria-label={`Brier score: model ${score(model)}, reference ${score(reference)}`}>
    <text x="0" y="29">Model</text><rect x="85" y="14" width={width(model)} height="20" rx="3" className="mon-chart-navy"/><text x={Math.min(250,92+width(model))} y="29">{score(model)}</text>
    <text x="0" y="65">Reference</text><rect x="85" y="50" width={width(reference)} height="20" rx="3" className="mon-chart-reference"/><text x={Math.min(250,92+width(reference))} y="65">{score(reference)}</text>
  </svg>;
}

export function TrendChart({ batches }) {
  if (!batches?.length) return <p>No assessments under this protocol are available for comparison.</p>;
  const values=batches.flatMap(b=>b.loaded ? [b.mean_risk_loaded,b.observed_rate].filter(v=>v!=null) : []);
  const peak=Math.max(...values,0.01);
  const scale=Math.ceil(peak*20)/20;
  const width=Math.max(620,batches.length*120+55);
  const barWidth=22;
  const aria=batches.map(b=>`${b.cutoff_month}: ${b.state}; predicted ${b.loaded ? percent(b.mean_risk_loaded) : 'unavailable'}, observed ${b.loaded ? percent(b.observed_rate) : 'unavailable'}`).join('; ');
  return <div className="mon-chart-scroll"><svg className="mon-trend-chart" viewBox={`0 0 ${width} 250`} role="img" aria-label={`Predicted and observed drop rates by assessment. ${aria}`}>
    {[0,.5,1].map(t=><g key={t}><line x1="50" x2={width-15} y1={205-160*t} y2={205-160*t} className="mon-grid"/><text x="2" y={209-160*t} className="mon-axis">{percent(scale*t,0)}</text></g>)}
    {batches.map((b,i)=>{const x=70+i*(width-85)/batches.length;const usable=(width-85)/batches.length;
      const height=v=>160*(v||0)/scale;
      return <g key={b.batch_id}>
        {b.loaded && b.mean_risk_loaded!=null && b.observed_rate!=null ? <>
          <rect x={x+usable/2-27} y={205-height(b.mean_risk_loaded)} width={barWidth} height={height(b.mean_risk_loaded)} rx="2" className="mon-chart-navy"/>
          <rect x={x+usable/2+5} y={205-height(b.observed_rate)} width={barWidth} height={height(b.observed_rate)} rx="2" className="mon-chart-rose"/>
        </> : <text x={x+usable/2} y="120" textAnchor="middle" className="mon-empty-label">{b.state.replaceAll('_',' ')}</text>}
        <text x={x+usable/2} y="230" textAnchor="middle" className="mon-axis">{new Date(b.cutoff_month+'T00:00:00Z').toLocaleDateString('en-MY',{month:'short',year:'numeric',timeZone:'UTC'})}</text>
      </g>})}
  </svg><p className="mon-chart-key"><span><i className="mon-key-navy"/>Mean predicted risk</span><span><i className="mon-key-rose"/>Observed drop rate</span><span>Unloaded months have no bars</span></p></div>;
}
