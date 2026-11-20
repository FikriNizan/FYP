import React, { useEffect, useRef, useState } from 'react';
import { api } from '../api.js';

function observationPeriod(period) {
  const date=value=>new Date(value+'T00:00:00Z').toLocaleDateString('en-MY',{day:'numeric',month:'short',year:'numeric',timeZone:'Asia/Kuala_Lumpur'});
  if(period.recent) return 'Recent: '+observationPeriod(period.recent)+'; baseline: '+observationPeriod(period.baseline);
  if(period.start) return date(period.start)+' to '+date(period.end);
  if(period.as_of) return 'As of '+date(period.as_of);
  if(period.forecast) return 'Assessment '+date(period.cutoff)+'; forecast '+period.forecast;
  if(period.assessment) return 'Assessment '+date(period.assessment);
  if(period.event_date) return 'Event '+date(period.event_date);
  return 'Date unavailable';
}

// Server-rendered meeting card: fact sentences come from saved evidence; only items tagged
// source 'ai' were written by Gemini, and they are labelled so readers can tell them apart.
function CardItem({ item }) {
  return <p className={item.source==='ai' ? 'ai-note' : undefined}>{item.source==='ai' && <span className="ai-tag">AI note</span>}{item.text}</p>;
}

function SummaryCard({ content }) {
  const closing=content.sections.find(s=>s.id==='closing'), footnote=content.sections.find(s=>s.id==='footnote');
  return <div className="summary-card">
    {content.sections.filter(s=>s.id!=='closing' && s.id!=='footnote').map(s=><div className="summary-section" key={s.id}>
      <h4>{s.title}</h4>{s.items.map((item,i)=><CardItem item={item} key={i} />)}
    </div>)}
    {!!content.questions.length && <div className="summary-section"><h4>Questions for the meeting</h4><ul>{content.questions.map((q,i)=><li key={i}>
      <span className="audience-tag">{q.audience==='finance' ? 'Finance' : 'Operations'}</span>
      <span className={q.source==='ai' ? 'ai-tag' : 'standard-tag'}>{q.source==='ai' ? 'AI' : 'Standard'}</span>{q.text}
    </li>)}</ul></div>}
    {footnote && <p className="muted card-footnote">{footnote.items.map(item=>item.text).join(' ')}</p>}
    {closing && <div className="summary-section"><h4>{closing.title}</h4>{closing.items.map((item,i)=><CardItem item={item} key={i} />)}</div>}
  </div>;
}

export default function AIBriefingDraft({ purpose='discussion', recordId, onReview }) {
  const [state,setState]=useState(null), [error,setError]=useState(''), [busy,setBusy]=useState(false);
  const [attempt,setAttempt]=useState(0), [reviewed,setReviewed]=useState(false);
  const lifetime=useRef(0), pending=useRef(false);
  useEffect(()=>{
    const generation=++lifetime.current;
    setState(null);setError('');setBusy(false);setReviewed(false);pending.current=false;
    onReview?.(null);
    const controller=new AbortController();
    if(recordId && api.aiDraft) api.aiDraft(purpose,recordId,null,controller.signal).then(value=>{
      if(lifetime.current===generation) setState(value);
    }).catch(e=>{if(lifetime.current===generation && e.name!=='AbortError')setError(e.message);});
    return ()=>{++lifetime.current;controller.abort();};
  },[purpose,recordId,attempt]);
  async function generate() {
    if(purpose==='summary' || pending.current || !state)return;
    pending.current=true;setBusy(true);setError('');setReviewed(false);onReview?.(null);
    const generation=lifetime.current;
    try {
      const value=await api.aiDraft(purpose,recordId,state.evidence_hash);
      if(lifetime.current===generation)setState(value);
    } catch(e) {if(lifetime.current===generation)setError(e.message);}
    finally {if(lifetime.current===generation){setBusy(false);pending.current=false;}}
  }
  const draft=state?.draft, content=draft?.content || state?.fallback;
  // Summaries are generated only by the offline batch for flagged customers; this view only reads them.
  const summary=purpose==='summary';
  const label=summary ? (draft ? 'AI-generated summary (stored)' : 'Deterministic summary · no stored AI draft for this assessment')
    : busy ? 'Generating' : draft ? 'Saved AI draft' : state?.state==='fallback' ? 'Deterministic fallback' : state?.state==='evidence_changed' ? 'Evidence changed · regenerate and review' : 'Not generated · deterministic fallback';
  return <section className={summary ? 'panel ai-draft no-print' : 'ai-draft briefing-section no-print'}>
    <h3>{summary ? 'What stands out' : 'Discussion draft'}</h3>
    <p role="status"><strong>{label}</strong>{draft && ' · '+new Date(draft.generated_at).toLocaleString('en-MY',{timeZone:'Asia/Kuala_Lumpur'})}</p>
    {draft && <p className="muted">AI draft · review before use</p>}
    {error && <p role="alert">Request failed. {error}</p>}
    {!summary && state?.failure_code && <p className="muted">{state.failure_code==='provider_unavailable'
      ? 'Gemini is temporarily unavailable. The deterministic fallback is shown. '+(state.attempts>1 ? 'One automatic retry was attempted.' : 'No automatic retry was made.')
      : state.failure_code==='invalid_key_format'
      ? 'The backend API key has invalid formatting. Re-enter it locally and restart the session. No Gemini request was sent.'
      : 'Gemini did not return a usable draft ('+state.failure_code.replaceAll('_',' ')+'). The saved evidence remains available.'}</p>}
    {content?.format==='sections-1' ? <SummaryCard content={content} /> : <>
      {content?.blocks.map((block,i)=><p key={i}>{block.text}</p>)}
      {!!content?.questions.length && <ul>{content.questions.map((q,i)=><li key={i}>{q.text}</li>)}</ul>}
    </>}
    {!summary && <button disabled={!state || busy} onClick={generate}>{busy ? 'Generating…' : draft ? 'Regenerate draft' : 'Generate discussion draft'}</button>}
    {error && <button disabled={busy} onClick={()=>setAttempt(n=>n+1)}>Reload saved evidence</button>}
    {draft && purpose==='discussion' && <label className="field-label"><input type="checkbox" checked={reviewed} onChange={e=>{
      setReviewed(e.target.checked);onReview?.(e.target.checked ? {case_id:recordId,draft_id:draft.draft_id,evidence_hash:state.evidence_hash,acknowledged:true} : null);
    }} /> I have reviewed this exact AI draft and its supporting evidence</label>}
    {state && <details><summary>View supporting evidence</summary><p>{state.limitations}</p><p className="muted">{state.provider} · {state.model} · {draft?.validation_version || 'Deterministic content'}</p>
      <dl>{state.evidence.map(f=><React.Fragment key={f.id}><dt>{f.label}</dt><dd>{f.display} · {f.direction ? 'Influence on estimate: '+f.direction+' · ' : ''}{observationPeriod(f.period)}<br />{f.meaning}<br /><small>{f.id} · {f.units}{f.attribution_units ? ' · '+f.contribution_logodds+' '+f.attribution_units : ''}<br />Saved prediction: {f.source?.prediction_id}</small></dd></React.Fragment>)}</dl>
      {draft && <p>Checks run: {draft.content.checks.join(', ')}. These checks do not certify every sentence as true.</p>}
    </details>}
  </section>;
}
