import React from 'react';
import { beforeEach, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import AIBriefingDraft from '../src/components/AIBriefingDraft.jsx';
import { api } from '../src/api.js';

vi.mock('../src/api.js',()=>({api:{aiDraft:vi.fn()}}));
const content={blocks:[{text:'Recorded evidence for discussion.',kind:'recorded_observation',evidence_ids:['fact']}],questions:[],checks:['known_references']};
const fallback={state:'not_generated',evidence_hash:'hash',fallback:content,draft:null,evidence:[],provider:'gemini',model:'configured-model',limitations:'Review before use.'};
const saved={...fallback,state:'saved',draft:{draft_id:'draft-a',generated_at:'2026-11-19T10:00:00Z',validation_version:'m6-narrative-1',content}};
beforeEach(()=>{vi.clearAllMocks();api.aiDraft.mockResolvedValue(fallback);});

it('reads without generation, generates explicitly once while pending and discloses evidence',async()=>{
  let finish;const promise=new Promise(resolve=>{finish=resolve;});
  api.aiDraft.mockResolvedValueOnce(fallback).mockReturnValueOnce(promise);
  render(<AIBriefingDraft purpose="summary" recordId="p" />);
  const button=await screen.findByRole('button',{name:'Generate summary'});
  await waitFor(()=>expect(button.disabled).toBe(false));
  expect(api.aiDraft.mock.calls[0].slice(0,3)).toEqual(['summary','p',null]);
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
  render(<AIBriefingDraft purpose="summary" recordId="p" />);
  const button=await screen.findByRole('button',{name:'Generate summary'});
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
  fireEvent.click(screen.getByRole('button',{name:'Regenerate draft'}));
  expect(onReview).toHaveBeenLastCalledWith(null);
  await waitFor(()=>expect(check.checked).toBe(false));
});

it('suppresses generation results after changing customer or component lifetime',async()=>{
  let finish;const promise=new Promise(resolve=>{finish=resolve;});
  api.aiDraft.mockResolvedValueOnce(fallback).mockReturnValueOnce(promise).mockResolvedValueOnce({...fallback,evidence_hash:'other'});
  const view=render(<AIBriefingDraft purpose="summary" recordId="first" />);
  const button=await screen.findByRole('button',{name:'Generate summary'});
  await waitFor(()=>expect(button.disabled).toBe(false));fireEvent.click(button);
  view.rerender(<AIBriefingDraft purpose="summary" recordId="second" />);
  await waitFor(()=>expect(api.aiDraft).toHaveBeenCalledTimes(3));
  finish(saved);await new Promise(resolve=>setTimeout(resolve,10));
  expect(screen.queryByText('Saved AI draft')).toBeNull();view.unmount();
});

it('labels fallback and changed evidence honestly',async()=>{
  api.aiDraft.mockResolvedValueOnce({...fallback,state:'evidence_changed'}).mockResolvedValueOnce({...fallback,state:'fallback',failure_code:'not_configured'});
  render(<AIBriefingDraft recordId="case-a" />);
  expect(await screen.findByText('Evidence changed · regenerate and review')).toBeTruthy();
  fireEvent.click(screen.getByRole('button',{name:'Generate discussion draft'}));
  expect(await screen.findByText('Deterministic fallback')).toBeTruthy();
  expect(screen.getByText(/not configured/)).toBeTruthy();
});

it('explains provider unavailability without implying a successful draft or automatic retry',async()=>{
  api.aiDraft.mockResolvedValue({...fallback,state:'fallback',failure_code:'provider_unavailable'});
  render(<AIBriefingDraft purpose="summary" recordId="p" />);
  expect(await screen.findByText('Gemini is temporarily unavailable. The deterministic fallback is shown. No automatic retry was made.')).toBeTruthy();
  expect(screen.queryByText('Saved AI draft')).toBeNull();
  expect(api.aiDraft).toHaveBeenCalledTimes(1);
  expect(screen.getByRole('button',{name:'Generate summary'}).disabled).toBe(false);
});

it('reports malformed backend key configuration without exposing credentials',async()=>{
  api.aiDraft.mockResolvedValue({...fallback,state:'fallback',failure_code:'invalid_key_format'});
  render(<AIBriefingDraft purpose="summary" recordId="p" />);
  expect(await screen.findByText('The backend API key has invalid formatting. Re-enter it locally and restart the session. No Gemini request was sent.')).toBeTruthy();
  expect(screen.queryByText('Saved AI draft')).toBeNull();
  expect(api.aiDraft).toHaveBeenCalledTimes(1);
});
