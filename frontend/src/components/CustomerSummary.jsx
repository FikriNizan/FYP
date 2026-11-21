import React, { useEffect, useState } from 'react';
import { api } from '../api.js';
import Icon from './Icon.jsx';

// Customer review Summary tab. The server renders every fact sentence from saved records; Gemini may add one
// validated link note and meeting questions, which are labelled. Summaries are produced only by the offline
// batch for flagged customers, so this view only reads them (no generation control).
export const AI_HEADER = 'Summary · AI-assisted';
export const AI_INTRO = 'Facts are from saved records. Items marked AI were drafted by Gemini for review.';
export const FACT_INTRO = 'Facts are from saved records.';
export const STALE_NOTE = 'The stored summary was written for earlier evidence, so standard text is shown until the summary batch is re-run.';

function useSummary(recordId) {
  const [state, setState] = useState(null), [error, setError] = useState('');
  useEffect(() => {
    let active = true;
    setState(null); setError('');
    const controller = new AbortController();
    if (recordId && api.aiDraft) api.aiDraft('summary', recordId, null, controller.signal)
      .then(value => { if (active) setState(value); })
      .catch(e => { if (active && e.name !== 'AbortError') setError(e.message); });
    return () => { active = false; controller.abort(); };
  }, [recordId]);
  return [state, error];
}

const section = (content, id) => content?.sections?.find(s => s.id === id);

function Fact({ item }) {
  return <p>{item.source === 'ai' && <span className="ai-badge">AI note</span>}{item.text}</p>;
}

export default function CustomerSummary({ recordId, children }) {
  const [state, error] = useSummary(recordId);
  const draft = state?.draft, content = draft?.content || state?.fallback;
  const bottom = section(content, 'bottom_line'), link = section(content, 'link'), footnote = section(content, 'footnote');
  return <>
    <section className="panel ai-summary" aria-labelledby="summary-title">
      <h2 id="summary-title">{draft ? AI_HEADER : 'Summary'}</h2>
      <p className="muted">{draft ? AI_INTRO : FACT_INTRO}</p>
      {!state && !error && <p role="status">Loading summary…</p>}
      {error && <p role="alert">The summary could not be loaded. {error}</p>}
      {state?.state === 'evidence_changed' && <p className="muted">{STALE_NOTE}</p>}
      {bottom && <div className="callout"><span className="round"><Icon name="info" /></span><div>
        {bottom.items.map((item, i) => <Fact item={item} key={i} />)}
        {link && link.items.map((item, i) => <p className="ai-link-note" key={'link' + i}><span className="ai-badge">AI note</span>{item.text}</p>)}
        {footnote && <p className="muted">{footnote.items.map(item => item.text).join(' ')}</p>}
      </div></div>}
    </section>
    {children}
    {!!content?.questions?.length && <section className="panel" aria-labelledby="meeting-questions-title">
      <h2 id="meeting-questions-title">Questions for the meeting</h2>
      <p className="muted">For the committee's Operations and Finance colleagues; not for the customer.</p>
      <ol className="meeting-questions">{content.questions.map((q, i) => <li key={i}>
        <span className={q.source === 'ai' ? 'ai-badge' : 'standard-badge'}>{q.source === 'ai' ? 'AI' : 'Standard'}</span>
        <span className="audience-badge">{q.audience === 'finance' ? 'Finance' : 'Operations'}</span>{q.text}
      </li>)}</ol>
    </section>}
  </>;
}
