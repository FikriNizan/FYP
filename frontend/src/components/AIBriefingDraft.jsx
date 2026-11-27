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

// Stored drafts may repeat a label when a fact was cited as both feature.X and signal.X: show each label once.
export const uniqueBasis = text => [...new Set(text.split('; '))].join('; ');

// Client questions for the RM: the question is said to the client; "Based on" is for the RM only.
export function ClientQuestions({ content }) {
  return <ol className="client-questions">{content.questions.map((q,i)=><li key={i}>
    <span className={q.source==='ai' ? 'ai-tag' : 'standard-tag'}>{q.source==='ai' ? 'AI-suggested' : 'Standard'}</span>{q.text}
    {q.basis && <small className="muted client-basis">Based on: {uniqueBasis(q.basis)}</small>}
  </li>)}</ol>;
}

// RM briefing discussion draft (on demand, per case). The customer Summary tab uses CustomerSummary.jsx.
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
    if(pending.current || !state)return;
    pending.current=true;setBusy(true);setError('');setReviewed(false);onReview?.(null);
    const generation=lifetime.current;
    try {
      const value=await api.aiDraft(purpose,recordId,state.evidence_hash);
      if(lifetime.current===generation)setState(value);
    } catch(e) {if(lifetime.current===generation)setError(e.message);}
    finally {if(lifetime.current===generation){setBusy(false);pending.current=false;}}
  }
  const draft=state?.draft, content=draft?.content || state?.fallback;
  const label=busy ? 'Generating' : draft ? 'Saved AI draft' : state?.state==='fallback' ? 'Deterministic fallback' : state?.state==='evidence_changed' ? 'Evidence changed · regenerate and review' : 'Not generated · deterministic fallback';
  return <section className="ai-draft briefing-section no-print">
    <h3>AI-suggested alternative wording</h3>
    <p role="status"><strong>{label}</strong>{draft && ' · '+new Date(draft.generated_at).toLocaleString('en-MY',{timeZone:'Asia/Kuala_Lumpur'})}</p>
    {draft && <p className="muted">Facts are from saved records. Items marked AI were drafted by Gemini for review.</p>}
    {error && <p role="alert">Request failed. {error}</p>}
    {state?.failure_code && <p className="muted">{state.failure_code==='provider_unavailable'
      ? 'Gemini is temporarily unavailable. The deterministic fallback is shown. '+(state.attempts>1 ? 'One automatic retry was attempted.' : 'No automatic retry was made.')
      : state.failure_code==='invalid_key_format'
      ? 'The backend API key has invalid formatting. Re-enter it locally and restart the session. No Gemini request was sent.'
      : 'Gemini did not return a usable draft ('+state.failure_code.replaceAll('_',' ')+'). The saved evidence remains available.'}</p>}
    {content?.format==='questions-1' && <ClientQuestions content={content} />}
    {<button disabled={!state || busy} onClick={generate}>{busy ? 'Generating…' : draft ? 'Regenerate questions' : 'Suggest client questions'}</button>}
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
