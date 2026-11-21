import React from 'react';
import { beforeEach, expect, it, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import MonthlyAssessments from '../src/pages/MonthlyAssessments.jsx';
import { api } from '../src/api.js';

vi.mock('../src/api.js',async original=>({...await original(),api:{uploadAssessment:vi.fn()}}));
beforeEach(()=>vi.resetAllMocks());
it('shows real file states and an honest processing state before publication',async()=>{
  render(<MemoryRouter><MonthlyAssessments batches={[]} onPublished={vi.fn()}/></MemoryRouter>);
  expect(screen.getAllByText('Needed')).toHaveLength(2);
  expect(screen.getByText('1 Select files').className).toContain('upl-current');
  const csv=new File(['features'],'features.csv',{type:'text/csv'});
  const manifest=new File(['{}'],'manifest.json',{type:'application/json'});
  fireEvent.change(screen.getByLabelText('Prepared features CSV'),{target:{files:[csv]}});
  fireEvent.change(screen.getByLabelText('Companion manifest JSON'),{target:{files:[manifest]}});
  expect(screen.getAllByText('Selected')).toHaveLength(2);
  expect(screen.getByText(/features.csv ·/)).toBeTruthy();
  let finish;api.uploadAssessment.mockReturnValue(new Promise(resolve=>{finish=resolve;}));
  fireEvent.submit(screen.getByRole('button',{name:'Validate, score and publish'}).closest('form'));
  expect(screen.getByRole('progressbar')).toBeTruthy();
  expect(screen.getByText('2 Validate').className).not.toContain('upl-done');
  finish({batch_id:'april',cutoff_month:'2024-04-30',records:1000,already_imported:false});
  expect(await screen.findByRole('heading',{name:'Assessment published'})).toBeTruthy();
  expect(screen.getByText('5 Publish').className).toContain('upl-done');
});

async function publish(response, batches=[]) {
  const view=render(<MemoryRouter><MonthlyAssessments batches={batches} onPublished={vi.fn()}/></MemoryRouter>);
  fireEvent.change(screen.getByLabelText('Prepared features CSV'),{target:{files:[new File(['f'],'features.csv')]}});
  fireEvent.change(screen.getByLabelText('Companion manifest JSON'),{target:{files:[new File(['{}'],'manifest.json')]}});
  api.uploadAssessment.mockResolvedValue(response);
  fireEvent.submit(screen.getByRole('button',{name:'Validate, score and publish'}).closest('form'));
  await screen.findByRole('link',{name:'Open published assessment'});
  return view;
}
const check=(cutoff_month,status,extra={})=>({batch_id:cutoff_month+'-batch',cutoff_month,status,records:1000,available:status==='waiting'?0:1000,already_present:0,waiting_for_month:null,...extra});

it('says which earlier month is now ready to check, from the response, and links to Monitoring',async()=>{
  await publish({batch_id:'may',cutoff_month:'2024-05-31',records:1000,flagged:203,already_imported:false,outcome_checks:[
    check('2024-02-29','checked',{available:998,records:1000}),
    check('2024-03-31','waiting',{waiting_for_month:'2024-06-30'})]});
  const panel=screen.getByRole('status',{name:''});
  expect(panel.textContent).toContain('May 2024 published · 1,000 scored customers, 203 flagged for review');
  expect(panel.textContent).toContain('February 2024 is now ready to check. Outcomes derived from Mar–May 2024 activity for 998 of 1,000 customers.');
  expect(panel.textContent).not.toContain('March 2024');  // Still waiting: shown in the Outcome check column, not here.
  expect(screen.getByRole('link',{name:'Open Monitoring for February 2024'}).getAttribute('href')).toBe('/monitoring?batch_id=2024-02-29-batch');
});

it('keeps existing outcomes: already checked is reported, and a different saved outcome is a conflict, never overwritten',async()=>{
  await publish({batch_id:'may',cutoff_month:'2024-05-31',records:1000,already_imported:true,outcome_checks:[
    check('2024-02-29','already_present',{already_present:1000}),check('2024-01-31','conflict',{message:'x'})]});
  expect(screen.getByText(/February 2024 was already checked\./).closest('p').textContent)
    .toBe('February 2024 was already checked. Outcomes from Mar–May 2024 activity match the 1,000 saved outcomes; nothing was changed.');
  expect(screen.getByText(/January 2024 was not checked\./).closest('p').textContent).toContain('they were kept and nothing was changed');
  expect(screen.queryByRole('link',{name:'Open Monitoring for January 2024'})).toBeNull();
});

it('keeps every saved-assessment column and adds Outcome check, with no reset control',async()=>{
  const row=(id,cutoff,outcome_check)=>({batch_id:id,cutoff_month:cutoff,source_kind:'prepared_month_scored',record_count:1000,
    protocol_sha256:'p',imported_at:'2026-11-22T00:00:00Z',source:{evidence_coverage:{names_available:1000,histories_available:1000}},outcome_check});
  render(<MemoryRouter><MonthlyAssessments batches={[
    row('apr','2024-04-30',{state:'waiting',waiting_for_month:'2024-06-30',ready_after_month:'2024-07-31',loaded:0,records:1000}),
    row('feb','2024-02-29',{state:'checked',waiting_for_month:null,loaded:1000,records:1000}),
    row('jan','2024-01-31',{state:'not_checked',waiting_for_month:null,loaded:0,records:1000})]} onPublished={vi.fn()}/></MemoryRouter>);
  expect(screen.getAllByRole('columnheader').map(h=>h.textContent)).toEqual(['Assessment','Coverage','Available evidence','Imported','Outcome check','Action']);
  const rows=screen.getAllByRole('row').slice(1);
  // Owner decision (Phase C): a waiting assessment names the LAST month of its forecast window.
  expect(rows.map(r=>r.querySelectorAll('td')[4].textContent)).toEqual(['Ready after July 2024 data','Checked','Not checked']);
  expect(screen.getAllByRole('link',{name:'Open overview'})).toHaveLength(3);
  expect(screen.getAllByText('Source details')).toHaveLength(3);
  expect(screen.queryByRole('button',{name:/reset/i})).toBeNull();
  expect(document.body.textContent).not.toMatch(/reset/i);
});
