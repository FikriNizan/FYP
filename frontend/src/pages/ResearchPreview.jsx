import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import { ConnectionState } from '../components/Workspace.jsx';

export default function ResearchPreview() {
  const [assumptions,setAssumptions] = useState({rate:25,renewal:80,competitor:10,passThrough:50});
  return <>
    <div className="heading"><div><h1>OPR design preview</h1><p className="muted">Hypothetical scenarios remain separate from saved customer evidence.</p></div><ConnectionState preview /></div>
    <section className="panel"><h2>Observed monitoring</h2><p>Outcome coverage, saved follow-up delivery and descriptive model movement are available in <Link to="/monitoring">Monitoring</Link> when an administrator loads mature outcomes.</p></section>
    <section className="panel"><h2>OPR scenario</h2><p className="muted">Hypothetical assumptions only. These inputs are not estimates of actual customer behaviour.</p><div className="scenario-layout"><form className="review-form" onSubmit={e=>e.preventDefault()}>{[['rate','OPR change (basis points)',-200,200],['renewal','Deposit renewal assumption (%)',0,100],['competitor','Competitor movement (basis points)',-200,200],['passThrough','Pass-through assumption (%)',0,100]].map(([key,label,min,max])=><div key={key}><label htmlFor={'scenario-'+key}>{label}</label><input id={'scenario-'+key} type="number" min={min} max={max} value={assumptions[key]} onChange={e=>setAssumptions({...assumptions,[key]:e.target.value})} /></div>)}<p className="muted">Deposit exit assumption: {assumptions.renewal!=='' && Number(assumptions.renewal)>=0 && Number(assumptions.renewal)<=100 ? 100-Number(assumptions.renewal)+'%' : 'Enter a renewal percentage from 0 to 100'} (complement of the renewal input).</p><button disabled>Calculate scenario · unavailable</button></form><div className="context-grid"><div className="context-card"><h3>Baseline</h3><p>Saved predictions remain unchanged.</p><p className="muted">Baseline exposures and period are not connected to this preview.</p></div><div className="context-card"><h3>Hypothetical scenario</h3><p>Not calculated</p><p className="muted">A scenario engine and justified assumptions are required to calculate monetary effects. No accuracy change or retention result is inferred.</p></div></div></div></section>
  </>;
}
