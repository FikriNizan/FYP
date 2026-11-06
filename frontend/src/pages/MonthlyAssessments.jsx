import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import { count, dateLabel, monthLabel } from '../format.js';
import { assessmentLink } from '../navigation.js';
import { ConnectionState } from '../components/Workspace.jsx';

export default function MonthlyAssessments({ batches = [] }) {
  const [showPreview,setShowPreview] = useState(false);
  const [state,setState] = useState('pending');
  const stages = ['Select','Validate','Score','Publish'];
  const active = {pending:0,processing:1,validated:2,failed:1,published:3}[state];
  return <>
    <div className="heading"><div><h1>Monthly Assessments</h1><p className="muted">Open saved evidence and check its customer and history coverage.</p></div><ConnectionState /></div>
    <section className="panel"><div className="section-heading"><h2>Saved assessments</h2><span className="muted">{count(batches.length)} preserved batches</span></div>
      <div className="table-wrap"><table><thead><tr><th>Assessment</th><th>Coverage</th><th>Available evidence</th><th>Imported</th><th>Action</th></tr></thead><tbody>{batches.map(b=><tr key={b.batch_id}><td><strong>{monthLabel(b.cutoff_month)}</strong><div className="muted">Batch {b.batch_id.slice(0,12)}</div><details><summary>Source details</summary><p className="source-id">{b.batch_id}</p><p className="muted">Protocol {b.protocol_sha256 || 'Not provided'}</p></details></td><td>{count(b.record_count)} {b.record_count===1 ? 'customer' : 'customers'}<div className="muted">{b.source_kind==='notebook_case_sample' ? 'Single-case sample' : 'Saved portfolio export'}</div></td><td>Predicted risk &amp; model signals<div className="muted">Names: {b.source?.customer_names_loaded ? 'Available' : 'Not provided'} · Flows: {b.source?.flow_history_loaded ? 'Available' : 'Not provided'}</div></td><td>{dateLabel(b.imported_at)}</td><td><Link className="button" to={assessmentLink('/overview',b.batch_id)}>Open overview</Link></td></tr>)}{!batches.length && <tr><td colSpan="5">No saved assessments are available.</td></tr>}</tbody></table></div>
    </section>
    <section className="panel"><div className="section-heading"><div><h2>Upload monthly package</h2><p className="muted">Upload and scoring services are not connected.</p></div><ConnectionState unavailable /></div><div className="heading-actions spaced"><button disabled>Upload monthly package</button><button onClick={()=>setShowPreview(v=>!v)} aria-expanded={showPreview}>Explore workflow preview</button></div>
      {showPreview && <div className="preview-workspace"><ConnectionState preview /><p>No file is accepted, scored or published in this preview. Saved assessments stay unchanged.</p><ol className="workflow-steps">{stages.map((stage,i)=><li key={stage} aria-current={i===active ? 'step' : undefined}><span>{i+1}</span>{stage}</li>)}</ol>
        <label className="field-label" htmlFor="upload-preview-state">Preview state</label><select id="upload-preview-state" value={state} onChange={e=>setState(e.target.value)}><option value="pending">Pending selection</option><option value="processing">Processing example</option><option value="validated">Validated example</option><option value="failed">Failed validation example</option><option value="published">Published example</option></select>
        <div className="preview-state" role="status">
          {state==='pending' && <><h3>Select a prepared monthly package</h3><p>The final accepted format will follow the agreed data contract.</p><input type="file" disabled aria-label="Monthly package upload unavailable" /></>}
          {state==='processing' && <><h3>Validation in progress · preview</h3><p>A real service would report schema, cutoff, model-policy and completeness checks here.</p><progress aria-label="Example validation processing" /></>}
          {state==='validated' && <><h3>Ready for scoring · preview</h3><p>This illustrates the handoff to frozen-model inference. No model has run.</p><button disabled>Score package · unavailable</button></>}
          {state==='failed' && <><h3>Validation failed · constructed example</h3><ul><li>Package cutoff is missing.</li><li>Required model-input columns do not match the agreed contract.</li></ul><p>Correct the package metadata and columns, then select it again. Previously published evidence remains available above.</p><button onClick={()=>setState('pending')}>Preview correction and resubmission</button></>}
          {state==='published' && <><h3>Published state · preview only</h3><p>A verified package would appear in Saved assessments after an actual publication. This example adds no batch or customer records.</p></>}
        </div>
      </div>}
    </section>
  </>;
}
