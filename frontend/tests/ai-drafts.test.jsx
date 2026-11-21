import React from 'react';
import { beforeEach, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import AIBriefingDraft, { ClientQuestions } from '../src/components/AIBriefingDraft.jsx';
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

// Summaries are produced by the offline batch; the page only reads stored drafts.
it('shows a stored batch summary as AI-generated with no generation control',async()=>{
  api.aiDraft.mockResolvedValue(saved);
  render(<AIBriefingDraft purpose="summary" recordId="p" />);
  expect(await screen.findByText('AI-generated summary (stored)')).toBeTruthy();
  expect(screen.getByText('AI draft · review before use')).toBeTruthy();
  expect(screen.getByText('Recorded evidence for discussion.')).toBeTruthy();
  expect(screen.queryAllByRole('button')).toHaveLength(0);
  expect(screen.queryByRole('checkbox')).toBeNull();
  expect(api.aiDraft).toHaveBeenCalledTimes(1);
  expect(api.aiDraft.mock.calls[0].slice(0,3)).toEqual(['summary','p',null]);
});

it('falls back to deterministic summary text when no current stored draft exists',async()=>{
  for(const state of ['not_generated','evidence_changed']) {
    api.aiDraft.mockResolvedValue({...fallback,state});
    const view=render(<AIBriefingDraft purpose="summary" recordId={'p-'+state} />);
    expect(await screen.findByText('Deterministic summary · no stored AI draft for this assessment')).toBeTruthy();
    expect(screen.getByText('Recorded evidence for discussion.')).toBeTruthy();
    expect(screen.queryByText('AI draft · review before use')).toBeNull();
    expect(screen.queryAllByRole('button')).toHaveLength(0);
    view.unmount();
  }
  expect(api.aiDraft.mock.calls.every(call=>call[0]==='summary' && call[2]===null)).toBe(true);
});

// m6-narrative-5 server-rendered card: fixed sections, AI items labelled, questions tagged by audience.
const sectionCard={format:'sections-1',evidence_ids:[],checks:['known_references'],sections:[
  {id:'bottom_line',title:'Bottom line',items:[{text:'Risk sentence from saved evidence.',source:'evidence',evidence_ids:['prediction.risk']},
    {text:'A short connecting note.',source:'ai',evidence_ids:['prediction.risk']}]},
  {id:'operations',title:'Operations: what is happening',items:[{text:'Operations fact.',source:'evidence',evidence_ids:[]}]},
  {id:'finance',title:'Finance: what is at stake',items:[{text:'Finance fact.',source:'evidence',evidence_ids:[]}]},
  {id:'weighed',title:'What the model weighed',items:[{text:'Weighed fact.',source:'evidence',evidence_ids:[]}]},
  {id:'closing',title:'Decision',items:[{text:"Prioritisation is the committee's decision.",source:'standard',evidence_ids:[]}]}],
  questions:[{audience:'operations',text:'Could Operations check the record?',source:'ai',evidence_ids:[]},
    {audience:'finance',text:'Could Finance confirm the position?',source:'template',evidence_ids:[]}]};
const deterministicCard={...sectionCard,checks:[],sections:sectionCard.sections.map(s=>({...s,items:s.items.filter(item=>item.source!=='ai')})),
  questions:sectionCard.questions.map(q=>({...q,source:'template'}))};

it('renders the summary card sections in fixed order with questions before the decision',async()=>{
  api.aiDraft.mockResolvedValue({...saved,draft:{...saved.draft,content:sectionCard}});
  render(<AIBriefingDraft purpose="summary" recordId="p" />);
  await screen.findByText('Risk sentence from saved evidence.');
  expect(screen.getAllByRole('heading',{level:4}).map(h=>h.textContent)).toEqual(['Bottom line','Operations: what is happening',
    'Finance: what is at stake','What the model weighed','Questions for the meeting','Decision']);
  expect(screen.queryAllByRole('button')).toHaveLength(0);
});

it('labels only AI-written sentences and tags questions by audience and source',async()=>{
  api.aiDraft.mockResolvedValue({...saved,draft:{...saved.draft,content:sectionCard}});
  render(<AIBriefingDraft purpose="summary" recordId="p" />);
  const note=await screen.findByText('A short connecting note.');
  expect(screen.getAllByText('AI note')).toHaveLength(1);
  expect(note.closest('p').textContent).toBe('AI noteA short connecting note.');
  expect(screen.getByText('Risk sentence from saved evidence.').closest('p').textContent).toBe('Risk sentence from saved evidence.');
  expect(screen.getByText('Could Operations check the record?').closest('li').textContent).toBe('OperationsAICould Operations check the record?');
  expect(screen.getByText('Could Finance confirm the position?').closest('li').textContent).toBe('FinanceStandardCould Finance confirm the position?');
});

it('shows the deterministic fallback card with no AI labels',async()=>{
  api.aiDraft.mockResolvedValue({...fallback,fallback:deterministicCard});
  render(<AIBriefingDraft purpose="summary" recordId="p" />);
  expect(await screen.findByText('Deterministic summary · no stored AI draft for this assessment')).toBeTruthy();
  expect(screen.getByText('Operations fact.')).toBeTruthy();
  expect(screen.queryByText('AI note')).toBeNull();
  expect(screen.queryByText('AI')).toBeNull();
  expect(screen.getAllByText('Standard')).toHaveLength(2);
});

it('places the 12-month footnote after the questions and before the decision, without a heading',async()=>{
  const withFootnote={...sectionCard,sections:[...sectionCard.sections.slice(0,4),
    {id:'footnote',title:'',items:[{text:'12-month averages include the latest 3 months.',source:'standard',evidence_ids:[]}]},sectionCard.sections[4]]};
  api.aiDraft.mockResolvedValue({...saved,draft:{...saved.draft,content:withFootnote}});
  const view=render(<AIBriefingDraft purpose="summary" recordId="p" />);
  const footnote=await screen.findByText('12-month averages include the latest 3 months.');
  const text=view.container.textContent;
  expect(text.indexOf('Could Finance confirm the position?')).toBeLessThan(text.indexOf('12-month averages include'));
  expect(text.indexOf('12-month averages include')).toBeLessThan(text.indexOf('Decision'));
  expect(footnote.tagName).toBe('P');
  expect(screen.getAllByRole('heading',{level:4}).map(h=>h.textContent)).not.toContain('');
  // The summary card is screen-only; print/PDF never show it, so no blank heading can be printed.
  expect(view.container.querySelector('section').classList.contains('no-print')).toBe(true);
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
