import React, { useEffect, useMemo, useState } from 'react';
import { Link, useLocation, useSearchParams } from 'react-router-dom';
import { api } from '../api.js';
import { caseStatusLabel, count, dateLabel, decisionLabel, malaysiaToday, monthLabel } from '../format.js';
import { ErrorNotice } from '../components/Common.jsx';
import { ConnectionState } from '../components/Workspace.jsx';

export default function ReviewedCustomers({ revision }) {
  const [params,setParams] = useSearchParams();
  const location = useLocation();
  const q=params.get('q') || '',status=params.get('status') || '',decision=params.get('decision') || '',owner=params.get('owner') || '';
  const query=useMemo(()=>({q,status,decision,owner}),[q,status,decision,owner]);
  const [filters,setFilters]=useState(query);
  useEffect(()=>setFilters(query),[query]);
  const offset=Math.max(0,Number.parseInt(params.get('offset') || '0',10) || 0);
  const [data, setData] = useState(null);
  const [error, setError] = useState('');
  const [attempt, setAttempt] = useState(0);
  const selected=[...new Set(params.getAll('pick'))].slice(0,10);
  const setSelected = value => {const next=new URLSearchParams(params);next.delete('pick');(typeof value==='function' ? value(selected) : value).forEach(id=>next.append('pick',id));setParams(next,{replace:true});};
  const update=values=>{const next=new URLSearchParams(params);for(const [key,value] of Object.entries(values)) value ? next.set(key,String(value)) : next.delete(key);setParams(next);};
  const caseLink = id => '/cases/'+id+'?worklist='+encodeURIComponent(location.search);
  const briefingQuery = new URLSearchParams(selected.map(id=>['case_id',id]));
  if(location.search)briefingQuery.set('worklist',location.search);
  useEffect(() => {
    let active = true;
    setError(''); setData(null);
    api.cases({ ...query, offset, limit:50 }).then(result => { if (active) setData(result); })
      .catch(e => { if (active) setError(e.message); });
    return () => { active = false; };
  }, [query, offset, revision, attempt]);
  return <>
    <div className="heading"><div><h1>Reviewed Customers</h1><p className="muted">Resume follow-up across assessments, with the original decision preserved.</p></div><ConnectionState unavailable={!!error}>{error ? 'Saved data unavailable' : data ? 'Connected to saved data' : 'Loading saved data…'}</ConnectionState></div>
    <section className="panel"><h2>Find a reviewed case</h2>
      <form className="case-filters" onSubmit={e => { e.preventDefault(); update({...filters,offset:0}); }}>
        <label>Customer<input type="search" placeholder="Company name or ID" value={filters.q} onChange={e => setFilters({ ...filters,q:e.target.value })} /></label>
        <label>Case status<select value={filters.status} onChange={e => setFilters({ ...filters,status:e.target.value })}><option value="">All statuses</option><option value="open">Open</option><option value="deferred">Deferred</option><option value="closed">Closed</option></select></label>
        <label>Current decision<select value={filters.decision} onChange={e => setFilters({ ...filters,decision:e.target.value })}><option value="">All decisions</option>{['prioritise','monitor','no_immediate_action'].map(d => <option key={d} value={d}>{decisionLabel(d)}</option>)}</select></label>
        <label>Owner<input value={filters.owner} placeholder="RM or team" onChange={e => setFilters({ ...filters,owner:e.target.value })} /></label><div className="filter-actions"><button className="primary">Apply filters</button><button type="button" onClick={()=>{setFilters({q:'',status:'',decision:'',owner:''});update({q:'',status:'',decision:'',owner:'',offset:0});}}>Clear filters</button></div>
      </form>
      <p className="filter-help">Decision filters the latest saved committee judgement linked to each case. The opening judgement remains visible in the case.</p>
    </section>
    <div className="briefing-selection"><span>{selected.length} prioritised cases selected (up to 10)</span>{selected.length ? <><Link className="button primary" to={'/briefing?'+briefingQuery}>Prepare RM briefing</Link><button onClick={()=>setSelected([])}>Clear selection</button></> : <button disabled>Prepare RM briefing</button>}<span className="muted">Select currently prioritised cases to prepare a discussion.</span></div>
    {error ? <><ErrorNotice message={error} /><button onClick={() => setAttempt(n => n+1)}>Try again</button></> : !data ? <p role="status">Loading reviewed cases…</p> : <section className="panel">
      <div className="section-heading"><h2>Saved decisions</h2><span className="muted">{data ? count(data.total) : '…'} {data?.total===1 ? 'case' : 'cases'} · Full rationale and history in each case</span></div>
      <div className="table-wrap"><table><thead><tr><th>Briefing</th><th>Customer</th><th>Current decision</th><th>Opened from assessment</th><th>Owner / next follow-up</th><th>Case</th></tr></thead><tbody>
        {data.items.map(c => <tr key={c.case_id}>
          <td><input type="checkbox" aria-label={'Select customer '+c.original.cus_id+' case '+c.case_id.slice(0,8)+' for briefing'} checked={selected.includes(c.case_id)} disabled={(c.current_review || c.original.review).decision!=='prioritise' || (!selected.includes(c.case_id) && selected.length>=10)} onChange={e=>setSelected(old=>e.target.checked ? [...old,c.case_id] : old.filter(id=>id!==c.case_id))} /></td>
          <td><Link className="customer-name" to={caseLink(c.case_id)}>{c.latest.customer_name || c.original.customer_name || 'Customer '+c.original.cus_id}</Link><div className="muted">ID {c.original.cus_id}</div></td>
          <td><span className="badge">{decisionLabel((c.current_review || c.original.review).decision)}</span><div className="muted">{monthLabel(c.current_review?.assessment_month || c.original.cutoff_month)} committee review</div>{(c.current_review || c.original.review).decision !== c.original_review.decision && <p className="muted">Originally {decisionLabel(c.original_review.decision)}</p>}</td>
          <td>{monthLabel(c.original.cutoff_month)}<div className="muted">Batch {c.original.batch_id.slice(0,8)}</div></td>
          <td>{c.owner || 'Unassigned'}<div className="muted">{dateLabel(c.next_action_date)}</div>{c.next_action_date && c.next_action_date<malaysiaToday() && c.status!=='closed' && <span className="badge overdue">Overdue</span>}</td>
          <td><span className={'badge status-'+c.status}>{caseStatusLabel(c.status)}</span><p><Link className="button" to={caseLink(c.case_id)}>Open case</Link></p></td>
        </tr>)}
        {!data.items.length && <tr><td colSpan="6"><div className="empty"><h3>No reviewed cases found</h3><p>Save a committee decision in Customer Review, or adjust these filters.</p></div></td></tr>}
      </tbody></table></div>
      <div className="pagination"><span className="muted">{data.total ? `${offset+1}–${Math.min(offset+50,data.total)}` : '0'} of {count(data.total)} {data.total===1 ? 'case' : 'cases'}</span><div className="pagination-controls"><button disabled={!offset} onClick={() => update({offset:offset-50})}>Previous</button><button disabled={offset+50 >= data.total} onClick={() => update({offset:offset+50})}>Next</button></div></div>
    </section>}
  </>;
}
