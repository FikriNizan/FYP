import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import { count, dateLabel, monthLabel } from '../format.js';
import { assessmentLink } from '../navigation.js';
import { api } from '../api.js';
import { ConnectionState } from '../components/Workspace.jsx';

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
      <div className="table-wrap"><table><thead><tr><th>Assessment</th><th>Coverage</th><th>Available evidence</th><th>Imported</th><th>Action</th></tr></thead><tbody>{batches.map(b=><tr key={b.batch_id}><td><strong>{monthLabel(b.cutoff_month)}</strong><div className="muted">Batch {b.batch_id.slice(0,12)}</div><details><summary>Source details</summary><p className="source-id">{b.batch_id}</p><p className="muted">Protocol {b.protocol_sha256 || 'Not provided'}</p></details></td><td>{count(b.record_count)} {b.record_count===1 ? 'customer' : 'customers'}<div className="muted">{b.source_kind==='notebook_case_sample' ? 'Single-case sample' : b.source_kind==='prepared_month_scored' ? 'Newly scored prepared package' : 'Saved portfolio export'}</div></td><td>Predicted risk &amp; model signals<div className="muted">Names: {count(b.source?.evidence_coverage?.names_available ?? (b.source?.customer_names_loaded ? b.record_count : 0))} of {count(b.record_count)} available ? Flows: {count(b.source?.evidence_coverage?.histories_available ?? (b.source?.flow_history_loaded ? b.record_count : 0))} of {count(b.record_count)} available</div></td><td>{dateLabel(b.imported_at)}</td><td><Link className="button" to={assessmentLink('/overview',b.batch_id)}>Open overview</Link></td></tr>)}{!batches.length && <tr><td colSpan="5">No saved assessments are available.</td></tr>}</tbody></table></div>
    </section>
    <section className="panel" aria-labelledby="monthly-upload-heading"><h2 id="monthly-upload-heading">Upload monthly package</h2>
      <p>Select one complete month of prepared features and its matching manifest. The server validates, scores with the saved model, verifies and publishes the assessment.</p>
      <form onSubmit={submit} aria-busy={busy}>
        <label className="field-label" htmlFor="monthly-features">Prepared features CSV</label>
        <input id="monthly-features" type="file" accept=".csv,text/csv" required disabled={busy} onChange={e=>setFeatures(e.target.files[0] || null)} />
        <label className="field-label" htmlFor="monthly-manifest">Companion manifest JSON</label>
        <input id="monthly-manifest" type="file" accept=".json,application/json" required disabled={busy} onChange={e=>setManifest(e.target.files[0] || null)} />
        <p className="muted">Select features.csv and manifest.json. No model, script or verification report is needed. A checksum checks package consistency, not the truth of the underlying data.</p>
        <button className="primary" type="submit" disabled={busy || !features || !manifest}>{busy ? 'Processing package\u2026' : 'Validate, score and publish'}</button>
      </form>
      {busy && <div role="status"><progress aria-label="Monthly package processing" /><p>Processing the complete package. Publication is confirmed only when the server responds.</p></div>}
      {error && <p role="alert">{error}</p>}
      {result && <div role="status"><h3>{result.already_imported ? 'Assessment already published' : 'Assessment published'}</h3><p>{monthLabel(result.cutoff_month)} · {count(result.records)} scored customers{result.already_imported ? ' · No new records were created.' : ''}</p><Link className="button" to={assessmentLink('/overview',result.batch_id)}>Open published assessment</Link></div>}
      {result?.enrichment?.status==='unavailable' && <p className="muted">{result.enrichment.message}</p>}
    </section>
  </>;
}
