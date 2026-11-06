import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Link, Route, Routes, useLocation, useSearchParams } from 'react-router-dom';
import { api } from './api.js';
import { count, monthLabel } from './format.js';
import { ErrorNotice } from './components/Common.jsx';
import Overview from './pages/Overview.jsx';
import CustomerReview from './pages/CustomerReview.jsx';
import { assessmentLink, preferredBatches } from './navigation.js';

function description(batch) {
  return `${monthLabel(batch.cutoff_month)} · ${count(batch.record_count)} customers${batch.source_kind === 'notebook_case_sample' ? ' (case sample)' : ''} · ${batch.source.customer_names_loaded ? 'names' : 'IDs'}${batch.source.flow_history_loaded ? ' + trends' : ''} · ${batch.batch_id.slice(0,6)}`;
}

export default function App() {
  const [batches, setBatches] = useState(null);
  const [error, setError] = useState('');
  const [attempt, setAttempt] = useState(0);
  const [params, setParams] = useSearchParams();
  const location = useLocation();
  const [drafts, setDrafts] = useState({});
  const [saving, setSaving] = useState(false);
  const [revision, setRevision] = useState(0);
  const [notice, setNotice] = useState('');
  const requested = params.get('batch_id');
  const batch = requested || batches?.[0]?.batch_id;
  const validBatch = batches?.find(b => b.batch_id === batch);

  useEffect(() => {
    let active = true;
    setError('');
    api.months().then(result => { if (active) setBatches(preferredBatches(result.items)); })
      .catch(error => { if (active) setError(error.message); });
    return () => { active = false; };
  }, [attempt]);
  useEffect(() => {
    if (batch && !requested) setParams({ batch_id: batch }, { replace: true });
  }, [batch, requested, setParams]);
  useEffect(() => {
    const warn = event => { if (saving || Object.keys(drafts).length) { event.preventDefault(); event.returnValue = ''; } };
    window.addEventListener('beforeunload', warn);
    return () => window.removeEventListener('beforeunload', warn);
  }, [drafts, saving]);

  const rememberDraft = useCallback((id, value) => setDrafts(old => ({ ...old, [id]: value })), []);
  const discardDraft = useCallback(id => setDrafts(old => { const next = { ...old }; delete next[id]; return next; }), []);
  const refresh = useCallback(() => setRevision(old => old + 1), []);
  const saved = useCallback(customer => {
    discardDraft(customer.prediction_id);
    setNotice(`Decision saved for customer ${customer.cus_id}, ${monthLabel(customer.cutoff_month)}. The original prediction and transaction history are preserved.`);
    refresh();
  }, [discardDraft, refresh]);
  const workflow = useMemo(() => ({ drafts, rememberDraft, discardDraft, saving, setSaving, saved, refresh }),
    [drafts, rememberDraft, discardDraft, saving, saved, refresh]);
  const avoidNavigation = event => { if (saving) event.preventDefault(); };

  let content;
  if (error) content = <><ErrorNotice message={error} /><button onClick={() => setAttempt(old => old + 1)}>Try again</button></>;
  else if (!batches) content = <p>Loading assessments…</p>;
  else if (!batches.length) content = <section className="panel empty"><h1>No assessments available</h1><p>Import a prepared assessment to begin.</p></section>;
  else if (!validBatch) content = <ErrorNotice message="This assessment is not available. Choose another assessment above." />;
  else content = <Routes>
    <Route path="/" element={<Overview batch={batch} revision={revision} />} />
    <Route path="/overview" element={<Overview batch={batch} revision={revision} />} />
    <Route path="/customer/:id" element={<CustomerReview batch={batch} revision={revision} workflow={workflow} />} />
    <Route path="*" element={<ErrorNotice message="This page is not available. Open the monthly overview." />} />
  </Routes>;

  return <>
    <header className="app-header"><div><Link className="brand" onClick={avoidNavigation} to={assessmentLink('/overview', batch || '')}>TxB Retention Studio</Link><p>Operations &amp; Finance</p></div>
      <div className="month-control"><label htmlFor="batch-select">Assessment</label><select id="batch-select" value={validBatch ? batch : ''} disabled={!batches?.length || saving} onChange={event => setParams({ batch_id: event.target.value })}>
        {!validBatch && <option value="">{batches?.length ? 'Choose an assessment' : 'No assessments'}</option>}
        {batches?.map(item => <option key={item.batch_id} value={item.batch_id}>{description(item)}</option>)}
      </select></div>
    </header>
    <nav className="app-nav" aria-label="Workspace"><Link onClick={avoidNavigation} to={assessmentLink('/overview', batch || '')}>Monthly overview</Link><span>{location.pathname.startsWith('/customer/') ? 'Customer review' : ''}</span></nav>
    <main>{content}</main>
    <div id="notification" role="status" aria-live="polite">{notice}</div>
  </>;
}
