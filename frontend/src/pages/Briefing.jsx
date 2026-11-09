import React, { useEffect, useRef, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { api } from '../api.js';
import { ErrorNotice } from '../components/Common.jsx';
import { ConnectionState } from '../components/Workspace.jsx';
import AIBriefingDraft from '../components/AIBriefingDraft.jsx';
import './briefing.css';

function EvidenceSection({ value, className = '', itemsFirst = false, longRows = false }) {
  const items=value.items.length ? <ul>{value.items.map((item,i)=><li key={i}>{item}</li>)}</ul> : null;
  return <section className={className}><h3>{value.title}</h3>
    {itemsFirst && (items || <p>No model signals were provided.</p>)}
    {value.paragraphs.map((text,i)=><p className="briefing-note" key={i}>{text}</p>)}
    {!!value.rows.length && <dl className={longRows ? 'briefing-followups' : undefined}>{value.rows.map(([label,text],i)=><React.Fragment key={i}><dt>{label}</dt><dd className="briefing-note">{text}</dd></React.Fragment>)}</dl>}
    {!itemsFirst && items}
  </section>;
}

export default function Briefing() {
  const [params] = useSearchParams();
  const back=params.get('worklist');
  const reviewedPath='/reviewed'+(back?.startsWith('?') ? back : '');
  const ids=[...new Set(params.getAll('case_id'))];
  const selectionKey=JSON.stringify(ids);
  const liveKey=useRef(selectionKey);
  liveKey.current=selectionKey;
  const mounted=useRef(false), controller=useRef(null);
  const [state,setState]=useState(null);
  const [operation,setOperation]=useState(null);
  const [attempt,setAttempt]=useState(0);
  const validSelection=ids.length>0 && ids.length<=10;
  const current=state?.key===selectionKey ? state : null;
  const payload=current?.payload;
  const busy=operation?.key===selectionKey;
  const ready=validSelection && !!payload?.items.length && !current?.needsReview && !busy;
  useEffect(()=>{
    let active=true;
    mounted.current=true;
    setState(null);setOperation(null);
    if (validSelection) api.briefing(ids).then(payload=>{
      if(active) setState({key:selectionKey,payload});
    }).catch(error=>{
      if(active) setState({key:selectionKey,error:error.message});
    });
    return ()=>{active=false;mounted.current=false;controller.current?.abort();controller.current=null;};
  },[selectionKey,attempt]);

  async function exportBriefing(kind) {
    if (!ready || controller.current) return;
    const key=selectionKey;
    const abort=new AbortController();
    controller.current=abort;
    setOperation({key,kind});
    setState(old=>({...old,error:null}));
    const stillCurrent=()=>mounted.current && liveKey.current===key && !abort.signal.aborted;
    try {
      if(kind==='print') {
        const fresh=await api.briefing(ids);
        if(!stillCurrent()) return;
        if(JSON.stringify(fresh.snapshots)!==JSON.stringify(payload.snapshots)) {
          setState({key,payload:fresh,needsReview:true,error:'Saved evidence changed. Review the refreshed briefing before printing or downloading.'});
          return;
        }
        window.print();
      } else {
        const {blob,filename}=await api.downloadBriefing(ids,payload.snapshots,abort.signal);
        if(!stillCurrent()) return;
        const url=URL.createObjectURL(blob);
        const link=document.createElement('a');
        link.href=url;link.download=filename;document.body.append(link);link.click();link.remove();
        // Allow the browser to consume the object URL before releasing it.
        setTimeout(()=>URL.revokeObjectURL(url),1000);
      }
    } catch(error) {
      if(!stillCurrent()) return;
      if(error.code==='briefing_changed' && error.briefing) setState({key,payload:error.briefing,needsReview:true,error:error.message});
      else if([404,422].includes(error.status) && error.code!=='pdf_font_unsupported') setState({key,error:error.message});
      else setState(old=>({...old,error:error.message}));
    } finally {
      if(controller.current===abort) controller.current=null;
      if(stillCurrent()) setOperation(null);
    }
  }

  return <>
    <div className="heading no-print"><div><h1>RM Briefing</h1><p className="muted">Structured briefing preview from explicitly selected saved cases. Review before sharing.</p></div><div className="heading-actions"><Link className="button" to={reviewedPath}>Choose cases</Link><button disabled={!ready} onClick={()=>exportBriefing('print')}>Print briefing</button><button className="primary" disabled={!ready} onClick={()=>exportBriefing('pdf')}>{busy && operation.kind==='pdf' ? 'Downloading PDF…' : 'Download PDF'}</button></div></div>
    {current?.error && <div className="no-print"><ErrorNotice message={current.error} />{!current.needsReview && <button onClick={()=>setAttempt(n=>n+1)}>Reload selected evidence</button>}</div>}
    {current?.needsReview && <p className="no-print briefing-refresh"><strong>Review the updated evidence below.</strong> <button onClick={()=>setState(old=>({...old,needsReview:false,error:null}))}>I have reviewed the updated briefing</button></p>}
    {busy && <p className="no-print" role="status">{operation.kind==='pdf' ? 'Preparing the PDF from freshly checked saved evidence…' : 'Checking saved evidence before printing…'}</p>}
    {!validSelection ? <section className="panel empty"><h2>Select up to ten prioritised cases</h2><p>Choose cases in Reviewed Customers, then open a briefing.</p></section> : !current ? <p role="status">Loading selected case evidence…</p> : payload?.items.map(item=><article className="panel briefing-sheet" key={item.case_id}>
      <div className="section-heading"><div><h2>{item.name}</h2><p className="muted">Relationship discussion brief · Customer {item.customer_id} · Case {item.case_id.slice(0,12)}</p><small className="muted">Internal use · Review before sharing.</small></div><ConnectionState /></div>
      <div className="briefing-context"><EvidenceSection value={item.original} /><EvidenceSection value={item.latest} /></div>
      {item.sample_note && <p className="scope-note">{item.sample_note}</p>}
      <EvidenceSection value={item.activity} className="briefing-section" />
      <EvidenceSection value={item.signals} className="briefing-section" itemsFirst />
      <div className="briefing-context"><EvidenceSection value={item.operations} /><EvidenceSection value={item.finance} /></div>
      <EvidenceSection value={item.decision} className="briefing-section" longRows />
      <section className="briefing-section"><h3>Questions for the customer</h3>{item.questions.length ? <ol>{item.questions.map((q,i)=><li key={i}><p>{q.text}</p><small className="muted">Evidence: {q.source} · {q.month}</small></li>)}</ol> : <p>No evidence-linked question is available from the supplied measures. Review the case before preparing questions.</p>}</section>
      <div className="no-print"><AIBriefingDraft customer={item.ai_context} /></div>
      <details className="briefing-sources"><summary>Evidence sources and identifiers</summary><p className="source-id">{item.traceability.map(([label,text])=><React.Fragment key={label}>{label}: {text}<br /></React.Fragment>)}</p></details>
      <p className="print-only source-id">{item.traceability.map(([label,text])=><React.Fragment key={label}>{label}: {text}<br /></React.Fragment>)}</p>
    </article>)}
  </>;
}
