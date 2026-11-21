import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import { count, dateLabel, forecastLabel, monthLabel } from '../format.js';
import { assessmentLink } from '../navigation.js';
import { api } from '../api.js';
import { ConnectionState } from '../components/Workspace.jsx';

function FileCard({id,title,hint,file,accept,onChange,busy}) {
  return <label className={`upl-file-card ${file?'upl-selected':''}`} htmlFor={id}>
    <span className="upl-glyph" aria-hidden="true">{file?<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="9"/><path d="m7 12 3 3 7-7"/></svg>:<svg viewBox="0 0 24 24"><path d="M12 17V3m-5 5 5-5 5 5M4 20h16"/></svg>}</span>
    <span className="upl-file-state">{file?'Selected':'Needed'}</span><strong>{title}</strong>
    <span className="upl-file-detail">{file?`${file.name} · ${new Intl.NumberFormat('en-MY',{maximumFractionDigits:1}).format(file.size/1024)} KB`:hint}</span>
    <span className="upl-file-action">{file?'Replace file':'Choose file'}</span>
    <input id={id} type="file" accept={accept} required disabled={busy} aria-label={title==='Prepared features'?'Prepared features CSV':'Companion manifest JSON'} onChange={e=>onChange(e.target.files[0]||null)}/>
  </label>;
}

// Phase B: earlier assessments are checked automatically from the packages already published. Every number
// and month below comes from the upload response or the saved-assessments API.
export function outcomeCheckLabel(check) {
  if (!check) return 'Not provided';
  if (check.state === 'checked') return 'Checked';
  if (check.state === 'waiting') return `Waiting for ${monthLabel(check.waiting_for_month)} data`;
  return 'Not checked';
}

function OutcomeCheckLine({ check }) {
  const month = monthLabel(check.cutoff_month);
  if (check.status === 'checked') return <p><strong>{month} is now ready to check.</strong> Outcomes derived from {forecastLabel(check.cutoff_month)} activity for {count(check.available)} of {count(check.records)} customers.</p>;
  if (check.status === 'already_present') return <p><strong>{month} was already checked.</strong> Outcomes from {forecastLabel(check.cutoff_month)} activity match the {count(check.already_present)} saved outcomes; nothing was changed.</p>;
  if (check.status === 'conflict') return <p><strong>{month} was not checked.</strong> Different outcomes are already saved for it, so they were kept and nothing was changed. Ask the administrator to review.</p>;
  if (check.status === 'not_available') return <p><strong>{month} could not be checked.</strong> The later packages do not cover its customers.</p>;
  if (check.status === 'error') return <p>{check.message}</p>;
  return null; // Still waiting: shown in the Outcome check column instead.
}

export default function MonthlyAssessments({ batches = [], onPublished }) {
  const [features,setFeatures] = useState(null);
  const [manifest,setManifest] = useState(null);
  const [busy,setBusy] = useState(false);
  const [error,setError] = useState('');
  const [result,setResult] = useState(null);
  async function submit(event) {
    event.preventDefault(); setError(''); setResult(null); setBusy(true);
    try {
      const published = await api.uploadAssessment(features,manifest);
      setResult(published);
      try { await onPublished?.(); }
      catch { setError('The assessment is published, but the list could not refresh. Open it using the link below or reload the page.'); }
    } catch (failure) { setError(failure.message); }
    finally { setBusy(false); }
  }
  return <>
    <div className="heading"><div><h1>Monthly Assessments</h1><p className="muted">Open saved evidence and check its customer and history coverage.</p></div><ConnectionState /></div>
    <section className="panel"><div className="section-heading"><h2>Saved assessments</h2><span className="muted">{count(batches.length)} preserved batches</span></div>
      <div className="table-wrap"><table><thead><tr><th>Assessment</th><th>Coverage</th><th>Available evidence</th><th>Imported</th><th>Outcome check</th><th>Action</th></tr></thead><tbody>{batches.map(b=><tr key={b.batch_id}><td><strong>{monthLabel(b.cutoff_month)}</strong><div className="muted">Batch {b.batch_id.slice(0,12)}</div><details><summary>Source details</summary><p className="source-id">{b.batch_id}</p><p className="muted">Protocol {b.protocol_sha256 || 'Not provided'}</p></details></td><td>{count(b.record_count)} {b.record_count===1 ? 'customer' : 'customers'}<div className="muted">{b.source_kind==='notebook_case_sample' ? 'Single-case sample' : b.source_kind==='prepared_month_scored' ? 'Newly scored prepared package' : 'Saved portfolio export'}</div></td><td>Predicted risk &amp; model signals<div className="muted">Names: {count(b.source?.evidence_coverage?.names_available ?? (b.source?.customer_names_loaded ? b.record_count : 0))} of {count(b.record_count)} available · Flows: {count(b.source?.evidence_coverage?.histories_available ?? (b.source?.flow_history_loaded ? b.record_count : 0))} of {count(b.record_count)} available</div></td><td>{dateLabel(b.imported_at)}</td><td>{outcomeCheckLabel(b.outcome_check)}{b.outcome_check?.state==='checked' && b.outcome_check.loaded<b.outcome_check.records && <div className="muted">{count(b.outcome_check.loaded)} of {count(b.outcome_check.records)} customers</div>}</td><td><Link className="button" to={assessmentLink('/overview',b.batch_id)}>Open overview</Link></td></tr>)}{!batches.length && <tr><td colSpan="6">No saved assessments are available.</td></tr>}</tbody></table></div>
    </section>
    <section className="panel upl-panel" aria-labelledby="monthly-upload-heading"><h2 id="monthly-upload-heading">Upload monthly package</h2>
      <p>Select one complete month of prepared features and its matching manifest. The server validates, scores with the saved model, verifies and publishes the assessment.</p>
      <ol className={`upl-stages ${busy?'upl-processing':''}`} aria-label="Publication steps">{['Select files','Validate','Score','Verify','Publish'].map((stage,index)=><li key={stage} className={result?'upl-done':!busy&&index===0?'upl-current':''}>{index+1} {stage}</li>)}</ol>
      <form onSubmit={submit} aria-busy={busy}>
        <div className="upl-files"><FileCard id="monthly-features" title="Prepared features" hint="features.csv, the prepared customer features for one month." file={features} accept=".csv,text/csv" onChange={setFeatures} busy={busy}/><FileCard id="monthly-manifest" title="Companion manifest" hint="manifest.json, the checksum file for this month." file={manifest} accept=".json,application/json" onChange={setManifest} busy={busy}/></div>
        <p className="muted">Select features.csv and manifest.json. No model, script or verification report is needed. A checksum checks package consistency, not the truth of the underlying data.</p>
        <button className="primary" type="submit" disabled={busy || !features || !manifest}>Validate, score and publish</button>
      </form>
      {busy && <div className="upl-busy" role="status"><progress aria-label="Monthly package processing" /><p>Processing the complete package. Publication is confirmed only when the server responds.</p></div>}
      {error && <div className="upl-error" role="alert">{error}</div>}
      {result && <div className="upl-success" role="status"><h3>{result.already_imported ? 'Assessment already published' : 'Assessment published'}</h3><p>{monthLabel(result.cutoff_month)} published · {count(result.records)} scored customers{typeof result.flagged==='number' ? `, ${count(result.flagged)} flagged for review` : ''}{result.already_imported ? ' · No new records were created.' : ''}</p>
        {(result.outcome_checks || []).map((check,i)=><OutcomeCheckLine key={check.batch_id || i} check={check} />)}
        <Link className="button" to={assessmentLink('/overview',result.batch_id)}>Open published assessment</Link>
        {(result.outcome_checks || []).filter(c=>c.status==='checked' || c.status==='already_present').map(c=><Link key={c.batch_id} className="button" to={'/monitoring?batch_id='+encodeURIComponent(c.batch_id)}>Open Monitoring for {monthLabel(c.cutoff_month)}</Link>)}
      </div>}
      {result?.enrichment?.status==='unavailable' && <p className="muted">{result.enrichment.message}</p>}
    </section>
  </>;
}
