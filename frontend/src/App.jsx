import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Link, NavLink, Route, Routes, useLocation, useSearchParams } from 'react-router-dom';
import { api } from './api.js';
import { count, monthLabel } from './format.js';
import { ErrorNotice } from './components/Common.jsx';
import Icon from './components/Icon.jsx';
import Overview from './pages/Overview.jsx';
import CustomerReview from './pages/CustomerReview.jsx';
import ReviewedCustomers from './pages/ReviewedCustomers.jsx';
import CaseDetail from './pages/CaseDetail.jsx';
import MonthlyAssessments from './pages/MonthlyAssessments.jsx';
import Briefing from './pages/Briefing.jsx';
import Guide from './pages/Guide.jsx';
import ResearchPreview from './pages/ResearchPreview.jsx';
import Monitoring from './pages/Monitoring.jsx';
import { preferredBatches } from './navigation.js';

function description(batch) {
  return `${monthLabel(batch.cutoff_month)} · ${count(batch.record_count)} ${batch.record_count===1 ? 'customer' : 'customers'}${batch.source_kind === 'notebook_case_sample' ? ' (case sample)' : ''} · ${batch.source.customer_names_loaded ? 'names' : 'IDs'}${batch.source.flow_history_loaded ? ' + trends' : ''} · ${batch.batch_id.slice(0,6)}`;
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
  const [selectedBatch,setSelectedBatch] = useState(null);
  const [overviewSearch,setOverviewSearch] = useState('');
  const [reviewedSearch,setReviewedSearch] = useState('');
  const batch = requested || selectedBatch || batches?.[0]?.batch_id;
  const validBatch = batches?.find(b => b.batch_id === batch);
  const assessmentScoped = ['/', '/overview'].includes(location.pathname) || location.pathname.startsWith('/customer/');
  const returnSearch = params.get('return');
  const overviewPath = '/overview'+(returnSearch?.startsWith('?') ? returnSearch : overviewSearch || (batch ? '?batch_id='+encodeURIComponent(batch) : ''));
  const worklist=params.get('worklist');
  const reviewedPath='/reviewed'+(worklist?.startsWith('?') ? worklist : reviewedSearch);
  const area=location.pathname.startsWith('/customer/') ? 'Customer review' : location.pathname.startsWith('/cases/') ? 'Case follow-up' : ({'/reviewed':'Reviewed Customers','/assessments':'Monthly Assessments','/monitoring':'Monitoring','/briefing':'RM Briefing','/guide':'Guide','/research':'OPR preview'})[location.pathname] || 'Overview';

  useEffect(() => {
    let active = true;
    setError('');
    api.months().then(result => { if (active) setBatches(preferredBatches(result.items)); })
      .catch(error => { if (active) setError(error.message); });
    return () => { active = false; };
  }, [attempt]);
  useEffect(() => {
    if (assessmentScoped && batch && !requested) { const next=new URLSearchParams(params); next.set('batch_id',batch); setParams(next,{replace:true}); }
  }, [assessmentScoped,batch, requested, setParams,params]);
  useEffect(()=>{if(validBatch) setSelectedBatch(validBatch.batch_id);},[validBatch]);
  useEffect(()=>{if(['/', '/overview'].includes(location.pathname)) setOverviewSearch(location.search);},[location.pathname,location.search]);
  useEffect(()=>{if(location.pathname==='/reviewed')setReviewedSearch(location.search);},[location.pathname,location.search]);
  useEffect(()=>{document.querySelector('.rail-help')?.removeAttribute('open');},[location.pathname]);
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
  const changeAssessment = value => {
    setSelectedBatch(value);
    if (location.pathname.startsWith('/customer/')) {
      const back = new URLSearchParams(returnSearch?.startsWith('?') ? returnSearch : overviewSearch);
      back.set('batch_id',value); back.delete('offset');
      const search='?'+back.toString(); setOverviewSearch(search);
      setParams({batch_id:value,return:search});
    } else { const next=new URLSearchParams(params);next.set('batch_id',value);next.delete('offset');setParams(next); }
  };

  let content;
  if (error && (assessmentScoped || location.pathname==='/assessments')) content = <><ErrorNotice message={error} /><button onClick={() => setAttempt(old => old + 1)}>Try again</button></>;
  else if (!batches && (assessmentScoped || location.pathname==='/assessments')) content = <p>Loading assessments…</p>;
  else if (!batches?.length && assessmentScoped) content = <section className="panel empty"><h1>No assessments available</h1><p>No assessments are saved yet. Open Monthly Assessments to see how monthly packages will be added.</p><Link className="button" to="/assessments">Monthly Assessments</Link></section>;
  else if (!validBatch && assessmentScoped) content = <ErrorNotice message="This assessment is not available. Choose another assessment above." />;
  else content = <Routes>
    <Route path="/" element={<Overview batch={batch} revision={revision} />} />
    <Route path="/overview" element={<Overview batch={batch} revision={revision} />} />
    <Route path="/customer/:id" element={<CustomerReview batch={batch} revision={revision} workflow={workflow} />} />
    <Route path="/reviewed" element={<ReviewedCustomers revision={revision} />} />
    <Route path="/cases/:id" element={<CaseDetail key={location.pathname} workflow={workflow} />} />
    <Route path="/assessments" element={<MonthlyAssessments batches={batches || []} onPublished={async () => { const result = await api.months(); setBatches(preferredBatches(result.items)); refresh(); }} />} />
    <Route path="/monitoring" element={<Monitoring batches={batches || []} />} />
    <Route path="/briefing" element={<Briefing batches={batches || []} />} />
    <Route path="/guide" element={<Guide />} />
    <Route path="/research" element={<ResearchPreview />} />
    <Route path="*" element={<ErrorNotice message="This page is not available. Open the monthly overview." />} />
  </Routes>;

  return <>
    <a className="skip-link" href="#workspace" onClick={event=>{event.preventDefault();const workspace=document.getElementById('workspace');workspace?.focus();workspace?.scrollIntoView?.({block:'start'});}}>Skip to workspace</a>
    <div className="app-shell"><aside className="workspace-rail">
      <Link className="brand" aria-label="TxB Retention Studio" onClick={avoidNavigation} to={overviewPath}><span className="brand-mark"><Icon name="brand"/></span><span><strong>TxB</strong><span>Retention Studio</span></span></Link>
      <p className="rail-context">Operations &amp; Finance</p>
      <nav className="app-nav" aria-label="Workspace"><NavLink onClick={avoidNavigation} to={overviewPath} className={({isActive})=>isActive || location.pathname.startsWith('/customer/') || location.pathname==='/' ? 'active' : ''}><Icon name="overview"/><span>Overview</span></NavLink><NavLink onClick={avoidNavigation} to={reviewedPath} className={({isActive})=>isActive || location.pathname.startsWith('/cases/') || location.pathname==='/briefing' ? 'active' : ''}><Icon name="cases"/><span>Reviewed Customers</span></NavLink><NavLink onClick={avoidNavigation} to="/assessments"><Icon name="calendar"/><span>Monthly Assessments</span></NavLink><NavLink onClick={avoidNavigation} to="/monitoring"><Icon name="research"/><span>Monitoring</span></NavLink></nav>
      <details className="rail-help"><summary><Icon name="guide"/>Help &amp; previews</summary><div className="header-utilities"><Link onClick={avoidNavigation} to="/guide"><Icon name="guide"/>Guide</Link><Link onClick={avoidNavigation} to="/research"><Icon name="research"/><span>OPR<small>Design preview</small></span></Link></div></details><p className="rail-note">Decisions grounded in saved evidence.</p>
    </aside><div className="workspace-main">
    <header className={'app-header '+(!assessmentScoped ? 'context-only' : '')}><div className="workspace-location"><span>Committee workspace</span><strong>{area}</strong></div>
      {assessmentScoped && <div className="month-control"><label htmlFor="batch-select">Assessment</label><select id="batch-select" value={validBatch ? batch : ''} disabled={!batches?.length || saving} onChange={event => changeAssessment(event.target.value)}>
        {!validBatch && <option value="">{batches?.length ? 'Choose an assessment' : 'No assessments'}</option>}
        {batches?.map(item => <option key={item.batch_id} value={item.batch_id}>{description(item)}</option>)}
      </select></div>}
    </header>
    <main id="workspace" tabIndex={-1}>{content}</main>
    <div id="notification" role="status" aria-live="polite">{notice}</div>
    </div></div>
  </>;
}
