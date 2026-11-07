import React, { useEffect, useState } from 'react';
import { Link, useParams, useSearchParams } from 'react-router-dom';
import { api } from '../api.js';
import { caseStatusLabel, dateLabel, decisionLabel, malaysiaToday, monthLabel, percent } from '../format.js';
import { assessmentLink } from '../navigation.js';
import { ErrorNotice } from '../components/Common.jsx';
import Signals from '../components/Signals.jsx';
import FlowHistory from '../components/FlowHistory.jsx';

const types = { customer_contact:'Customer contact', rm_visit:'RM visit', service_fix:'Service action', other:'Other' };
const states = { planned:'Planned', attempted:'Attempted', delivered:'Completed', cancelled:'Cancelled' };
const emptyAction = { action_type:'customer_contact',action_status:'planned',action_date:'',notes:'',recorded_by:'' };
const taskKey = id => id || 'new';
const timestamp = value => new Intl.DateTimeFormat('en-MY',{dateStyle:'medium',timeStyle:'short',timeZone:'Asia/Kuala_Lumpur'}).format(new Date(value));

export default function CaseDetail({ workflow }) {
  const { id } = useParams();
  const [params] = useSearchParams();
  const back = params.get('worklist');
  const returnPath = '/reviewed'+(back?.startsWith('?') ? back : '');
  const draftKey = 'case:'+id;
  const remembered = workflow.drafts[draftKey];
  const [data,setData] = useState(null);
  const [error,setError] = useState('');
  const [attempt,setAttempt] = useState(0);
  const [caseDraft,setCaseDraft] = useState(remembered?.caseDraft || null);
  const [actionDrafts,setActionDrafts] = useState(remembered?.actionDrafts || {});
  const [taskId,setTaskId] = useState(remembered?.taskId || '');
  const [editor,setEditor] = useState(remembered?.editor || 'followup');
  const [busy,setBusy] = useState(false);
  const [conflict,setConflict] = useState(false);
  const [notice,setNotice] = useState('');
  const dirty = caseDraft !== null || Object.keys(actionDrafts).length>0;

  useEffect(()=>{
    if (dirty) workflow.rememberDraft(draftKey,{caseDraft,actionDrafts,taskId,editor});
    else workflow.discardDraft(draftKey);
  },[dirty,caseDraft,actionDrafts,taskId,editor,draftKey,workflow.rememberDraft,workflow.discardDraft]);
  useEffect(()=>{
    let active=true;
    api.case(id).then(result=>{if(active){setData(result.case);setError('');}}).catch(e=>{if(active)setError(e.message);});
    return ()=>{active=false;};
  },[id,attempt]);

  function loadLatest() {
    setCaseDraft(null);setActionDrafts({});setTaskId('');setConflict(false);setError('');setData(null);setAttempt(n=>n+1);
  }
  function discard(kind) {
    if (kind==='case') setCaseDraft(null);
    else setActionDrafts(old=>{const next={...old};delete next[taskKey(taskId)];return next;});
    setError('');setNotice('Unsaved '+(kind==='case' ? 'case changes' : 'follow-up changes')+' discarded.');
  }
  async function save(kind,event) {
    event.preventDefault();
    if (busy || conflict) return;
    const submittedVersion = kind==='case' ? caseDraft?.expectedVersion || data.version : actionDrafts[taskKey(taskId)]?.expectedVersion || data.version;
    setBusy(true);workflow.setSaving(true);setError('');setNotice('');
    try {
      const result=kind==='case'
        ? await api.updateCase(id,{...caseFields,next_action_date:caseFields.next_action_date || null,expected_version:submittedVersion})
        : await api.followUp(id,taskId,{...action,expected_version:submittedVersion});
      setData(result.case);setConflict(false);
      // Only rebase drafts known to precede this session's own accepted write.
      setCaseDraft(old=>kind==='case' ? null : old?.expectedVersion===submittedVersion ? {...old,expectedVersion:result.case.version} : old);
      setActionDrafts(old=>Object.fromEntries(Object.entries(old)
        .filter(([key])=>kind!=='action' || key!==taskKey(taskId))
        .map(([key,draft])=>[key,draft.expectedVersion===submittedVersion ? {...draft,expectedVersion:result.case.version} : draft])));
      if (kind==='action') setTaskId('');
      setNotice(kind==='case' ? 'Case updated. The original decision is preserved.' : 'Follow-up recorded. Its event history is preserved.');
      workflow.refresh();
    } catch(e) {setError(e.message);if(e.status===409)setConflict(true);}
    finally {setBusy(false);workflow.setSaving(false);}
  }
  if(!data) return error ? <><ErrorNotice message={error}/><button onClick={loadLatest}>Try again</button></> : <p role="status">Loading reviewed case…</p>;
  const c=data.original, latest=data.latest, originalReview=data.original_review;
  const caseFields=caseDraft?.fields || {status:data.status,owner:data.owner,next_action_date:data.next_action_date || '',notes:'',recorded_by:''};
  const selectedTask=data.follow_ups.find(t=>t.follow_up_id===taskId);
  const action=actionDrafts[taskKey(taskId)]?.fields || (selectedTask ? {...emptyAction,action_type:selectedTask.action_type,action_status:''} : {...emptyAction});
  const actionDirty=!!actionDrafts[taskKey(taskId)];
  const otherDraftCount=Object.keys(actionDrafts).filter(key=>key!==taskKey(taskId)).length;
  const editCase=(key,value)=>setCaseDraft({fields:{...caseFields,[key]:value},expectedVersion:caseDraft?.expectedVersion || data.version});
  const editAction=(key,value)=>setActionDrafts(old=>({...old,[taskKey(taskId)]:{fields:{...action,[key]:value},expectedVersion:old[taskKey(taskId)]?.expectedVersion || data.version}}));
  const chooseEditor=value=>{setEditor(value);requestAnimationFrame(()=>document.getElementById(value==='manage' ? 'manage-editor' : 'followup-editor')?.scrollIntoView?.({block:'nearest'}));};
  return <>
    <Link className="back-link" to={returnPath}>← Reviewed Customers</Link>
    <div className="heading"><div><h1>{latest.customer_name || c.customer_name || 'Customer '+c.cus_id}</h1><p className="muted">Customer {c.cus_id} · Opened {timestamp(data.created_at)} · Case version {data.version}</p></div><div className="heading-actions"><span className={'badge status-'+data.status}>{caseStatusLabel(data.status)}</span>{c.review.decision==='prioritise' && <Link className="button" to={'/briefing?case_id='+encodeURIComponent(data.case_id)}>Prepare RM briefing</Link>}</div></div>
    <div className="case-summary"><div><span>Case owner</span><strong>{data.owner || 'Unassigned'}</strong></div><div><span>Next follow-up</span><strong>{dateLabel(data.next_action_date)}</strong></div><div><span>Current committee decision</span><strong>{decisionLabel(c.review.decision)}</strong></div><div className="case-action-tabs" role="tablist" aria-label="Case action" onKeyDown={event=>{if(!['ArrowLeft','ArrowRight','Home','End'].includes(event.key))return;event.preventDefault();const next=event.key==='Home' ? 'followup' : event.key==='End' ? 'manage' : editor==='manage' ? 'followup' : 'manage';chooseEditor(next);document.getElementById(next==='manage' ? 'manage-tab' : 'followup-tab')?.focus();}}><button role="tab" id="followup-tab" tabIndex={editor==='followup' ? 0 : -1} aria-selected={editor==='followup'} aria-controls="followup-editor" onClick={()=>chooseEditor('followup')}>Record follow-up</button><button role="tab" id="manage-tab" tabIndex={editor==='manage' ? 0 : -1} aria-selected={editor==='manage'} aria-controls="manage-editor" onClick={()=>chooseEditor('manage')}>Manage case</button></div></div>
    <div className="context-grid assessment-comparison">
      <section className="context-card original-context"><h2>At the time of review</h2><p className="comparison-date">{monthLabel(c.cutoff_month)}</p><strong className="number">{percent(c.calibrated_risk)}</strong><p>{decisionLabel(originalReview.decision)}</p><p>{originalReview.reason}</p><p className="muted">Reviewed by {originalReview.reviewer}</p><Link className="button" to={assessmentLink('/customer/'+encodeURIComponent(c.cus_id),c.batch_id)}>Open original assessment</Link></section>
      <section className="context-card"><h2>Latest available assessment</h2><p className="comparison-date">{monthLabel(latest.cutoff_month)}</p><strong className="number">{percent(latest.calibrated_risk)}</strong><p>{latest.cutoff_month<=c.cutoff_month ? 'No newer assessment month is available.' : 'Separate saved evidence for the same customer.'}</p><p className="muted">A change in predicted risk does not close this case or establish an intervention result.</p><Link className="button" to={assessmentLink('/customer/'+encodeURIComponent(c.cus_id),latest.batch_id)}>Open latest assessment</Link></section>
    </div>
    {error && <ErrorNotice message={error}/>}
    {conflict && <button className="primary" onClick={loadLatest}>Discard drafts and load latest case</button>}
    {notice && <p role="status" className="success">{notice}</p>}
    <div className="case-layout">
      <aside id="case-action-editor" className="case-editor">
        <section id="followup-editor" className="panel" role="tabpanel" aria-labelledby="followup-tab" hidden={editor!=='followup'}>
          <h2>Record follow-up</h2><p className="muted">Plan a next step or record what actually happened. Each task keeps its own draft.</p>
          {data.status==='closed' ? <p>Reopen the case to record another follow-up.</p> : <form className="review-form" onSubmit={e=>save('action',e)}><fieldset disabled={busy || conflict}>
            <label htmlFor="follow-up-task">Task</label><select id="follow-up-task" value={taskId} onChange={e=>setTaskId(e.target.value)}><option value="">New follow-up{actionDrafts.new ? ' · draft' : ''}</option>{data.follow_ups.filter(t=>['planned','attempted'].includes(t.current.action_status) || actionDrafts[t.follow_up_id]).map(t=><option key={t.follow_up_id} value={t.follow_up_id}>{types[t.action_type]} · {dateLabel(t.planned_date || t.current.action_date)} · {t.follow_up_id.slice(0,8)}{actionDrafts[t.follow_up_id] ? ' · draft' : ''}</option>)}</select>
            {otherDraftCount>0 && <p className="draft-hint">{otherDraftCount} other task {otherDraftCount===1 ? 'draft is' : 'drafts are'} retained. Switch Task to resume.</p>}
            <label htmlFor="action-type">Action type</label><select id="action-type" disabled={!!taskId} value={action.action_type} onChange={e=>editAction('action_type',e.target.value)}>{Object.entries(types).map(([key,label])=><option key={key} value={key}>{label}</option>)}</select>
            <label htmlFor="action-state">Follow-up status</label><select id="action-state" required value={action.action_status} onChange={e=>editAction('action_status',e.target.value)}>{taskId && <option value="">Choose what happened</option>}{Object.entries(states).filter(([key])=>taskId ? key!=='planned' : key!=='cancelled').map(([key,label])=><option key={key} value={key}>{label}</option>)}</select>
            <label htmlFor="event-date">{action.action_status==='planned' ? 'Planned date' : 'Actual event date'}</label><input id="event-date" type="date" required max={action.action_status && action.action_status!=='planned' ? malaysiaToday() : undefined} value={action.action_date} onChange={e=>editAction('action_date',e.target.value)}/>
            <label htmlFor="event-notes">Follow-up notes</label><textarea id="event-notes" required maxLength={4000} value={action.notes} onChange={e=>editAction('notes',e.target.value)}/>
            <label htmlFor="event-author">Recorded by</label><input id="event-author" required maxLength={200} value={action.recorded_by} onChange={e=>editAction('recorded_by',e.target.value)}/>
            <p className={'form-state '+(actionDirty ? 'is-dirty' : '')} role="status">{actionDirty ? 'Unsaved follow-up changes' : 'No unsaved changes for this task'}</p>
            <div className="form-actions"><button className="primary">{busy ? 'Saving…' : 'Record follow-up'}</button><button type="button" disabled={!actionDirty} onClick={()=>discard('action')}>Discard follow-up changes</button></div>
          </fieldset></form>}
        </section>
        <section id="manage-editor" className="panel review-form" role="tabpanel" aria-labelledby="manage-tab" hidden={editor!=='manage'}>
          <h2>Manage this case</h2><p className="muted">Change current ownership or case status with a reason. The opening committee decision stays intact.</p><form onSubmit={e=>save('case',e)}><fieldset disabled={busy || conflict}>
            <label htmlFor="case-status">Case status</label><select id="case-status" value={caseFields.status} onChange={e=>editCase('status',e.target.value)}><option value="open">Open</option><option value="deferred">Deferred</option><option value="closed">Closed</option></select>
            {caseFields.status==='closed' && data.follow_ups.some(t=>['planned','attempted'].includes(t.current.action_status)) && <p className="muted">Unfinished follow-ups remain in history. Reopen the case before adding task events.</p>}
            <label htmlFor="case-owner">Owner</label><input id="case-owner" maxLength={200} value={caseFields.owner} onChange={e=>editCase('owner',e.target.value)}/>
            <label htmlFor="case-next">Next-action date</label><input id="case-next" type="date" value={caseFields.next_action_date || ''} onChange={e=>editCase('next_action_date',e.target.value || null)}/>
            <label htmlFor="case-reason">Change reason</label><textarea id="case-reason" required maxLength={4000} value={caseFields.notes} onChange={e=>editCase('notes',e.target.value)}/>
            <label htmlFor="case-author">Changed by</label><input id="case-author" required maxLength={200} value={caseFields.recorded_by} onChange={e=>editCase('recorded_by',e.target.value)}/>
            <p className={'form-state '+(caseDraft ? 'is-dirty' : '')} role="status">{caseDraft ? 'Unsaved case changes' : 'Saved case · version '+data.version}</p>
            <div className="form-actions"><button className="primary">{busy ? 'Saving…' : 'Save case changes'}</button><button type="button" disabled={!caseDraft} onClick={()=>discard('case')}>Discard case changes</button></div>
          </fieldset></form>
        </section>
      </aside>
      <div className="case-content">
        <section className="panel"><h2>Follow-up activity</h2><p className="muted">Plans, attempts and completed work remain distinct. Planned work is not a delivered intervention.</p>
          {!data.follow_ups.length && <div className="empty"><h3>No follow-up recorded yet</h3><p>A saved decision does not require immediate outreach.</p></div>}
          {data.follow_ups.map(task=><article className="task-card" key={task.follow_up_id}><div className="section-heading"><h3>{types[task.action_type]}</h3><span className={'badge status-'+task.current.action_status}>{states[task.current.action_status]}</span></div><p className="muted">Case owner: {data.owner || 'Unassigned'} · Planned: {task.planned_date ? dateLabel(task.planned_date) : 'No prior plan'}</p><ol className="timeline">{task.history.map(event=><li key={event.event_id}><strong>{states[event.action_status]} · {dateLabel(event.action_date)}</strong><p>{event.notes}</p><small className="muted">{event.recorded_by} · Recorded {timestamp(event.recorded_at)}</small></li>)}</ol></article>)}
        </section>
        <section className="panel"><details><summary>Latest evidence · {monthLabel(latest.cutoff_month)}</summary><Signals customer={latest}/><FlowHistory history={latest.flow_history} baseline={latest.operations.combined_flow_mean_12m_myr} cutoff={latest.cutoff_month}/></details></section>
        <section className="panel"><details><summary>Audit history</summary><h3>Case events</h3><ol className="timeline">{data.history.map((event,i)=><li key={i}><strong>{event.kind.replaceAll('_',' ')} · {event.status || states[event.action_status]}</strong><p>{event.notes}</p>{event.owner!==undefined && <p className="muted">Owner: {event.owner || 'Unassigned'} · Next: {dateLabel(event.next_action_date)}</p>}<small className="muted">{event.recorded_by} · {timestamp(event.recorded_at)}</small></li>)}</ol><h3>Committee review versions</h3>{data.review_history.map(r=><article className="task-card" key={r.version}><strong>Version {r.version} · {decisionLabel(r.decision)}</strong><p>{r.reason}</p><small className="muted">{r.reviewer} · {timestamp(r.saved_at)}</small></article>)}<h3>Earlier action notes</h3><p className="muted">Legacy notes are preserved separately; no task relationship has been inferred.</p>{c.actions.length ? c.actions.map(a=><article className="task-card" key={a.action_id}><strong>{types[a.action_type]} · {states[a.action_status]} · {dateLabel(a.action_date)}</strong><p>{a.notes}</p><small className="muted">{a.recorded_by} · {timestamp(a.recorded_at)}</small></article>) : <p className="muted">No legacy action notes.</p>}</details></section>
      </div>
    </div>
  </>;
}
