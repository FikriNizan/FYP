import React from 'react';
import { beforeEach, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import AIBriefingDraft, { ClientQuestions } from '../src/components/AIBriefingDraft.jsx';
import CustomerSummary from '../src/components/CustomerSummary.jsx';
import { api } from '../src/api.js';

vi.mock('../src/api.js',()=>({api:{aiDraft:vi.fn()}}));
const content={format:'questions-1',questions:[{text:'Recorded evidence for discussion.',source:'standard',basis:'fact',evidence_ids:[]}],evidence_ids:[],checks:['known_references']};
const fallback={state:'not_generated',evidence_hash:'hash',fallback:content,draft:null,evidence:[],provider:'gemini',model:'configured-model',limitations:'Review before use.'};
const saved={...fallback,state:'saved',draft:{draft_id:'draft-a',generated_at:'2026-11-19T10:00:00Z',validation_version:'m6-narrative-1',content}};
beforeEach(()=>{vi.resetAllMocks();api.aiDraft.mockResolvedValue(fallback);});

// On-demand generation exists only for RM discussion drafts.
it('reads without generation, generates explicitly once while pending and discloses evidence',async()=>{
  let finish;const promise=new Promise(resolve=>{finish=resolve;});
  api.aiDraft.mockResolvedValueOnce(fallback).mockReturnValueOnce(promise);
  render(<AIBriefingDraft recordId="case-a" />);
  const button=await screen.findByRole('button',{name:'Suggest client questions'});
  await waitFor(()=>expect(button.disabled).toBe(false));
  expect(api.aiDraft.mock.calls[0].slice(0,3)).toEqual(['discussion','case-a',null]);
  fireEvent.click(button);fireEvent.click(button);
  expect(api.aiDraft).toHaveBeenCalledTimes(2);
  expect(screen.getByText('Generating')).toBeTruthy();
  expect(screen.getByText('Recorded evidence for discussion.')).toBeTruthy();
  finish(saved);
  expect(await screen.findByText('Saved AI draft')).toBeTruthy();
  fireEvent.click(screen.getByText('View supporting evidence'));
  expect(screen.getByText(/known_references/)).toBeTruthy();
});

it('keeps evidence on failure and offers reload/retry without fake success',async()=>{
  api.aiDraft.mockResolvedValueOnce(fallback).mockRejectedValueOnce(new Error('Offline'));
  render(<AIBriefingDraft recordId="case-a" />);
  const button=await screen.findByRole('button',{name:'Suggest client questions'});
  await waitFor(()=>expect(button.disabled).toBe(false));fireEvent.click(button);
  expect(await screen.findByRole('alert')).toHaveProperty('textContent','Request failed. Offline');
  expect(screen.getByText('Recorded evidence for discussion.')).toBeTruthy();
  expect(screen.queryByText('Saved AI draft')).toBeNull();
  fireEvent.click(screen.getByRole('button',{name:'Reload saved evidence'}));
  await waitFor(()=>expect(api.aiDraft).toHaveBeenCalledTimes(3));
});

it('requires exact draft acknowledgement and resets it on regeneration',async()=>{
  api.aiDraft.mockResolvedValue(saved);const onReview=vi.fn();
  render(<AIBriefingDraft recordId="case-a" onReview={onReview} />);
  const check=await screen.findByRole('checkbox');
  expect(check.checked).toBe(false);fireEvent.click(check);
  expect(onReview).toHaveBeenLastCalledWith({case_id:'case-a',draft_id:'draft-a',evidence_hash:'hash',acknowledged:true});
  fireEvent.click(screen.getByRole('button',{name:'Regenerate questions'}));
  expect(onReview).toHaveBeenLastCalledWith(null);
  await waitFor(()=>expect(check.checked).toBe(false));
});

it('suppresses generation results after changing case or component lifetime',async()=>{
  let finish;const promise=new Promise(resolve=>{finish=resolve;});
  api.aiDraft.mockResolvedValueOnce(fallback).mockReturnValueOnce(promise).mockResolvedValueOnce({...fallback,evidence_hash:'other'});
  const view=render(<AIBriefingDraft recordId="first" />);
  const button=await screen.findByRole('button',{name:'Suggest client questions'});
  await waitFor(()=>expect(button.disabled).toBe(false));fireEvent.click(button);
  view.rerender(<AIBriefingDraft recordId="second" />);
  await waitFor(()=>expect(api.aiDraft).toHaveBeenCalledTimes(3));
  finish(saved);await new Promise(resolve=>setTimeout(resolve,10));
  expect(screen.queryByText('Saved AI draft')).toBeNull();view.unmount();
});

it('labels fallback and changed evidence honestly',async()=>{
  api.aiDraft.mockResolvedValueOnce({...fallback,state:'evidence_changed'}).mockResolvedValueOnce({...fallback,state:'fallback',failure_code:'not_configured'});
  render(<AIBriefingDraft recordId="case-a" />);
  expect(await screen.findByText('Evidence changed · regenerate and review')).toBeTruthy();
  fireEvent.click(screen.getByRole('button',{name:'Suggest client questions'}));
  expect(await screen.findByText('Deterministic fallback')).toBeTruthy();
  expect(screen.getByText(/not configured/)).toBeTruthy();
});

it('explains provider unavailability without implying a successful draft and states retry honestly',async()=>{
  api.aiDraft.mockResolvedValue({...fallback,state:'fallback',failure_code:'provider_unavailable',attempts:1});
  const view=render(<AIBriefingDraft recordId="case-a" />);
  expect(await screen.findByText('Gemini is temporarily unavailable. The deterministic fallback is shown. No automatic retry was made.')).toBeTruthy();
  expect(screen.queryByText('Saved AI draft')).toBeNull();
  expect(api.aiDraft).toHaveBeenCalledTimes(1);
  expect(screen.getByRole('button',{name:'Suggest client questions'}).disabled).toBe(false);
  view.unmount();
  api.aiDraft.mockResolvedValue({...fallback,state:'fallback',failure_code:'provider_unavailable',attempts:2});
  render(<AIBriefingDraft recordId="case-b" />);
  expect(await screen.findByText('Gemini is temporarily unavailable. The deterministic fallback is shown. One automatic retry was attempted.')).toBeTruthy();
});

it('reports malformed backend key configuration without exposing credentials',async()=>{
  api.aiDraft.mockResolvedValue({...fallback,state:'fallback',failure_code:'invalid_key_format'});
  render(<AIBriefingDraft recordId="case-a" />);
  expect(await screen.findByText('The backend API key has invalid formatting. Re-enter it locally and restart the session. No Gemini request was sent.')).toBeTruthy();
  expect(screen.queryByText('Saved AI draft')).toBeNull();
  expect(api.aiDraft).toHaveBeenCalledTimes(1);
});

// Customer Summary tab (CustomerSummary.jsx): the server bottom line, an optional validated AI link note, and the
// meeting questions. Summaries are produced by the offline batch; the page only reads stored drafts.
const sectionCard={format:'sections-1',evidence_ids:[],checks:['known_references'],sections:[
  {id:'bottom_line',title:'Bottom line',items:[{text:'Risk sentence from saved evidence.',source:'evidence',evidence_ids:['prediction.risk']},
    {text:'Strongest signals raising the estimate: payment failure rate (details in Signals to investigate).',source:'evidence',evidence_ids:[]}]},
  {id:'link',title:'What links these signals',items:[{text:'A short connecting note.',source:'ai',evidence_ids:['prediction.risk']}]},
  {id:'operations',title:'Operations: what is happening',items:[{text:'Operations fact.',source:'evidence',evidence_ids:[]}]},
  {id:'finance',title:'Finance: what is at stake',items:[{text:'Finance fact.',source:'evidence',evidence_ids:[]}]},
  {id:'weighed',title:'What the model weighed',items:[{text:'Weighed fact.',source:'evidence',evidence_ids:[]}]},
  {id:'footnote',title:'',items:[{text:'Prediction for May–Jul 2024, based on data up to 30 Apr 2024.',source:'standard',evidence_ids:[]}]},
  {id:'closing',title:'Decision',items:[{text:"Prioritisation is the committee's decision.",source:'standard',evidence_ids:[]}]}],
  questions:[{audience:'operations',text:'Could Operations check the record?',source:'ai',evidence_ids:[]},
    {audience:'finance',text:'Could Finance confirm the position?',source:'template',evidence_ids:[]}]};
const noLink={...sectionCard,sections:sectionCard.sections.filter(s=>s.id!=='link')};
const deterministicCard={...noLink,checks:[],questions:sectionCard.questions.map(q=>({...q,source:'template'}))};
const stored=content=>({...saved,draft:{...saved.draft,content}});
const summaryView=(id='p',children=null)=>render(<CustomerSummary recordId={id}>{children}</CustomerSummary>);

it('labels a stored summary "Summary · AI-assisted" with the facts sentence, and has no generation control',async()=>{
  api.aiDraft.mockResolvedValue(stored(sectionCard));
  summaryView();
  expect(await screen.findByRole('heading',{name:'Summary · AI-assisted'})).toBeTruthy();
  expect(screen.getByText('Facts are from saved records. Items marked AI were drafted by Gemini for review.')).toBeTruthy();
  expect(screen.queryByText('AI-generated summary (stored)')).toBeNull();
  expect(screen.queryByText('AI draft · review before use')).toBeNull();
  expect(screen.queryAllByRole('button')).toHaveLength(0);
  expect(screen.queryByRole('checkbox')).toBeNull();
  expect(api.aiDraft).toHaveBeenCalledTimes(1);
  expect(api.aiDraft.mock.calls[0].slice(0,3)).toEqual(['summary','p',null]);
});

it('shows the server bottom line and footnote only; the card sections stay in the briefing, not on this tab',async()=>{
  api.aiDraft.mockResolvedValue(stored(sectionCard));
  const view=summaryView();
  await screen.findByText('Risk sentence from saved evidence.');
  // Layout (27 Nov 2026): the sentence is split at its first ': ' into a dt label and a dd value; its text is unchanged.
  const signals=screen.getByText('Strongest signals raising the estimate');
  expect(signals.tagName).toBe('DT');
  expect(signals.closest('dl').querySelector('dd').textContent).toBe('payment failure rate (details in Signals to investigate)');  // Trailing '.' dropped for display.
  expect(screen.getByText('Prediction for May–Jul 2024, based on data up to 30 Apr 2024.')).toBeTruthy();
  for(const text of ['Operations fact.','Finance fact.','Weighed fact.',"Prioritisation is the committee's decision.",'Bottom line','What the model weighed'])
    expect(view.container.textContent).not.toContain(text);
});

it('shows the AI note below a divider with its badge only when a validated link note exists',async()=>{
  api.aiDraft.mockResolvedValue(stored(sectionCard));
  const view=summaryView('with-link');
  const note=await screen.findByText('A short connecting note.');
  expect(note.closest('p').className).toBe('ai-link-note');
  expect(note.closest('p').textContent).toBe('AI noteA short connecting note.');
  expect(screen.getAllByText('AI note')).toHaveLength(1);
  expect(screen.getByText('Risk sentence from saved evidence.').closest('p').textContent).toBe('Risk sentence from saved evidence.');
  view.unmount();
  api.aiDraft.mockResolvedValue(stored(noLink));
  summaryView('without-link');
  await screen.findByText('Risk sentence from saved evidence.');
  expect(screen.queryByText('AI note')).toBeNull();
  expect(document.querySelector('.ai-link-note')).toBeNull();
});

it('lists questions for the meeting with AI and Standard badges after the tab content',async()=>{
  api.aiDraft.mockResolvedValue(stored(sectionCard));
  const view=summaryView('p',<p>Chart and signals</p>);
  const heading=await screen.findByRole('heading',{name:'Questions for the meeting'});
  expect(screen.queryByRole('heading',{name:'Questions for the customer'})).toBeNull();
  expect(screen.getByText('Could Operations check the record?').closest('li').textContent).toBe('AIOperationsCould Operations check the record?');
  expect(screen.getByText('Could Finance confirm the position?').closest('li').textContent).toBe('StandardFinanceCould Finance confirm the position?');
  const text=view.container.textContent;
  expect(text.indexOf('Risk sentence')).toBeLessThan(text.indexOf('Chart and signals'));
  expect(text.indexOf('Chart and signals')).toBeLessThan(text.indexOf(heading.textContent));
});

// render-9: every meeting question carries a deterministic "Based on" line built from its cited facts.
it('shows a Based on line under each summary meeting question that has one',async()=>{
  const withBasis={...noLink,questions:[
    {audience:'operations',text:'Has the customer reported trouble completing payments online?',source:'ai',
      evidence_ids:['feature.outbound_failure_rate_3m'],basis:'Payment failure rate'},
    {audience:'finance',text:'Could Finance confirm the position?',source:'template',evidence_ids:[]}]};
  api.aiDraft.mockResolvedValue(stored(withBasis));
  summaryView('with-basis');
  const ops=(await screen.findByText('Has the customer reported trouble completing payments online?')).closest('li');
  expect(ops.querySelector('.client-basis').textContent).toBe('Based on: Payment failure rate');
  expect(ops.querySelector('.client-basis').className).toBe('muted client-basis');
  expect(screen.getByText('Could Finance confirm the position?').closest('li').querySelector('.client-basis')).toBeNull();
});

// Summary layout (27 Nov 2026, frontend only): the bottom line as a fact grid placed by evidence_ids.
const bottomItems=[
  {text:'Strongest signals raising the estimate: payment failure rate (details in Signals to investigate).',source:'evidence',evidence_ids:[]},
  {text:'Usual monthly combined flow (12-month average): RM 115.8 million.',source:'evidence',evidence_ids:['feature.combined_flow_mean_12m_myr']},
  {text:'Flagged for committee review: at or above the 25.9% threshold, which was set from past data to balance catching real cases against false alerts.',
    source:'evidence',evidence_ids:['prediction.flag','prediction.threshold']},
  {text:'Estimated chance that average monthly combined flow (Collection + Disbursement) over May–Jul 2024 falls to half or less of its usual level: 56.7%, more likely than not.',
    source:'evidence',evidence_ids:['prediction.risk']},
  {text:'No signal raised the estimate notably.',source:'evidence',evidence_ids:[]}];
const layoutCard=(items,withLink=true)=>({...sectionCard,sections:sectionCard.sections.map(s=>s.id==='bottom_line'?{...s,items}:s)
  .filter(s=>withLink||s.id!=='link')});
const cells=()=>[...document.querySelectorAll('.fact-grid > .fact')];

it('splits each bottom-line sentence at its first ": " into a label and a value without changing the text',async()=>{
  api.aiDraft.mockResolvedValue(stored(layoutCard(bottomItems)));
  summaryView('split');
  await screen.findByText('Estimated chance that average monthly combined flow (Collection + Disbursement) over May–Jul 2024 falls to half or less of its usual level');
  const risk=cells()[0];
  expect(risk.tagName).toBe('DL');
  expect(risk.querySelector('dt').textContent).toBe('Estimated chance that average monthly combined flow (Collection + Disbursement) over May–Jul 2024 falls to half or less of its usual level');
  expect(risk.querySelector('dd').textContent).toBe('56.7%, more likely than not');  // Trailing '.' dropped for display.
  // Only the first ': ' splits; the value keeps its own text (first-letter capitalisation is CSS only).
  const signals=cells().find(c=>c.textContent.startsWith('Strongest'));
  expect(signals.querySelector('dd').textContent).toBe('payment failure rate (details in Signals to investigate)');
  for(const cell of cells().filter(c=>c.tagName==='DL'))
    expect(bottomItems.map(i=>i.text)).toContain(cell.querySelector('dt').textContent+': '+cell.querySelector('dd').textContent+'.');
  // A sentence without ': ' is plain text in a full-width cell.
  const plain=screen.getByText('No signal raised the estimate notably.');
  expect(plain.tagName).toBe('P');
  expect(plain.className).toBe('fact wide');
});

it('drops one trailing full stop from fact values for display only, leaving the stored text unchanged',async()=>{
  const items=[
    {text:'Usual monthly combined flow (12-month average): RM 137,601.',source:'evidence',evidence_ids:['feature.combined_flow_mean_12m_myr']},
    {text:'Label without a full stop: value with no full stop',source:'evidence',evidence_ids:[]},
    {text:'Label with two: value ending in an ellipsis...',source:'evidence',evidence_ids:[]},
    {text:'No signal raised the estimate notably.',source:'evidence',evidence_ids:[]}];
  const card=layoutCard(items);
  api.aiDraft.mockResolvedValue(stored(card));
  summaryView('dots');
  await screen.findByText('Usual monthly combined flow (12-month average)');
  const value=label=>screen.getByText(label).closest('dl').querySelector('dd').textContent;
  expect(value('Usual monthly combined flow (12-month average)')).toBe('RM 137,601');
  expect(value('Label without a full stop')).toBe('value with no full stop');
  expect(value('Label with two')).toBe('value ending in an ellipsis..');  // Only one full stop is dropped.
  expect(screen.getByText('No signal raised the estimate notably.').tagName).toBe('P');  // Plain cells keep their text.
  expect(card.sections.find(s=>s.id==='bottom_line').items[0].text).toBe('Usual monthly combined flow (12-month average): RM 137,601.');
});

it('places bottom-line cells by evidence_ids: hero, the flag and usual-flow pair, then the rest',async()=>{
  api.aiDraft.mockResolvedValue(stored(layoutCard(bottomItems)));
  summaryView('placement');
  await screen.findByText('Strongest signals raising the estimate');
  expect(cells().map(c=>[c.className,c.querySelector('dt')?.textContent || c.textContent])).toEqual([
    ['fact hero','Estimated chance that average monthly combined flow (Collection + Disbursement) over May–Jul 2024 falls to half or less of its usual level'],
    ['fact pair','Usual monthly combined flow (12-month average)'],
    ['fact pair','Flagged for committee review'],
    ['fact wide','Strongest signals raising the estimate'],
    ['fact wide','No signal raised the estimate notably.']]);
});

it('gives the flag or usual-flow cell the full width when its partner is missing',async()=>{
  for(const [id,keep] of [['flag-only','prediction.flag'],['usual-only','feature.combined_flow_mean_12m_myr']]) {
    const items=bottomItems.filter(i=>!(i.evidence_ids.includes('prediction.flag')||i.evidence_ids.includes('feature.combined_flow_mean_12m_myr'))
      || i.evidence_ids.includes(keep));
    api.aiDraft.mockResolvedValue(stored(layoutCard(items)));
    const view=summaryView(id);
    await screen.findByText('Strongest signals raising the estimate');
    const single=cells().find(c=>c.querySelector('dt') && (c.textContent.startsWith('Flagged') || c.textContent.startsWith('Usual')));
    expect(single.className).toBe('fact wide');
    expect(document.querySelectorAll('.fact.pair')).toHaveLength(0);
    view.unmount();
  }
});

it('shows the AI note in its own box below the fact grid and keeps the footnote last',async()=>{
  api.aiDraft.mockResolvedValue(stored(layoutCard(bottomItems)));
  summaryView('boxes');
  const note=(await screen.findByText('A short connecting note.')).closest('p');
  const box=note.parentElement;
  expect(box.className).toBe('ai-link-box');
  expect(box.querySelector('.ai-badge').textContent).toBe('AI note');
  const content=document.querySelector('.fact-grid').parentElement;
  expect([...content.children].map(c=>c.className)).toEqual(['fact-grid','ai-link-box','muted summary-footnote']);
  expect(content.lastElementChild.textContent).toBe('Prediction for May–Jul 2024, based on data up to 30 Apr 2024.');
  api.aiDraft.mockResolvedValue(stored(layoutCard(bottomItems,false)));
  summaryView('no-box');
  await screen.findAllByText('Strongest signals raising the estimate');
  expect(document.querySelectorAll('.ai-link-box')).toHaveLength(1);  // Only the first view's box; none without a link note.
});

it('renders "Based on" as its own element after the meeting question text',async()=>{
  const withBasis={...noLink,questions:[{audience:'operations',text:'Has the customer reported trouble completing payments online?',
    source:'ai',evidence_ids:['feature.outbound_failure_rate_3m'],basis:'Payment failure rate'}]};
  api.aiDraft.mockResolvedValue(stored(withBasis));
  summaryView('basis-block');
  const item=(await screen.findByText(/Has the customer reported trouble completing payments online\?/)).closest('li');
  const basis=item.querySelector('.client-basis');
  expect(basis.tagName).toBe('SMALL');
  expect(basis.parentElement).toBe(item);
  expect(item.lastElementChild).toBe(basis);
  expect(basis.previousSibling.nodeType).toBe(Node.TEXT_NODE);  // The question text ends before the Based on element.
  expect(basis.previousSibling.textContent).toBe('Has the customer reported trouble completing payments online?');
  expect(item.closest('ol').className).toBe('meeting-questions');  // The block-line CSS rule targets .meeting-questions .client-basis.
});

it('falls back to standard text with no AI labels when no current stored draft exists, and says why when the evidence changed',async()=>{
  for(const state of ['not_generated','evidence_changed']) {
    api.aiDraft.mockResolvedValue({...fallback,state,fallback:deterministicCard});
    const view=summaryView('p-'+state);
    expect(await screen.findByRole('heading',{name:'Summary'})).toBeTruthy();
    expect(screen.getByText('Facts are from saved records.')).toBeTruthy();
    expect(screen.getByText('Risk sentence from saved evidence.')).toBeTruthy();
    expect(screen.queryByText(/AI-assisted/)).toBeNull();
    expect(screen.queryByText('AI note')).toBeNull();
    expect(screen.queryByText('AI')).toBeNull();
    expect(screen.getAllByText('Standard')).toHaveLength(2);
    expect(!!screen.queryByText(/written for earlier evidence/)).toBe(state==='evidence_changed');
    expect(screen.queryAllByRole('button')).toHaveLength(0);
    view.unmount();
  }
  expect(api.aiDraft.mock.calls.every(call=>call[0]==='summary' && call[2]===null)).toBe(true);
});

// m6-narrative-7: the on-demand purpose produces client questions; "Based on" is for the RM only.
const clientContent={format:'questions-1',evidence_ids:['feature.login_failure_rate_3m'],checks:['client_language'],questions:[
  {text:'Have you or your team had any difficulty signing in to online banking?',source:'ai',basis:'Login failure rate',evidence_ids:['feature.login_failure_rate_3m']},
  {text:'How has business activity been for you lately, and do you expect any changes ahead?',source:'standard',basis:'Combined flow vs 12-month average: 0.87% of the twelve-month average',evidence_ids:[]}]};

it('shows AI-suggested and standard client questions with an RM-only basis line',async()=>{
  api.aiDraft.mockResolvedValue({...saved,draft:{...saved.draft,content:clientContent}});
  render(<AIBriefingDraft recordId="case-a" />);
  expect(await screen.findByRole('heading',{name:'AI-suggested client questions'})).toBeTruthy();
  const ai=screen.getByText('Have you or your team had any difficulty signing in to online banking?').closest('li');
  expect(ai.querySelector('.ai-tag').textContent).toBe('AI-suggested');
  expect(ai.querySelector('.client-basis').textContent).toBe('Based on: Login failure rate');
  const standard=screen.getByText(/How has business activity been/).closest('li');
  expect(standard.querySelector('.standard-tag').textContent).toBe('Standard');
  expect(screen.getByRole('button',{name:'Regenerate questions'})).toBeTruthy();
  expect(screen.getByRole('checkbox')).toBeTruthy();  // Acknowledgement flow unchanged.
});

it('renders the same client questions for the print section without exposing the basis in the question text',()=>{
  const view=render(<ClientQuestions content={clientContent} />);
  const items=[...view.container.querySelectorAll('li')];
  expect(items.map(li=>li.querySelector('.ai-tag, .standard-tag').textContent)).toEqual(['AI-suggested','Standard']);
  for(const [index,q] of clientContent.questions.entries()) {
    expect(items[index].textContent).toBe((q.source==='ai'?'AI-suggested':'Standard')+q.text+'Based on: '+q.basis);
    expect(q.text).not.toContain(q.basis);
  }
});
