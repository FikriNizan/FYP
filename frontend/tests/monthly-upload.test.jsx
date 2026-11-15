import React from 'react';
import { beforeEach, expect, it, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import MonthlyAssessments from '../src/pages/MonthlyAssessments.jsx';
import { api } from '../src/api.js';

vi.mock('../src/api.js',async original=>({...await original(),api:{uploadAssessment:vi.fn()}}));
beforeEach(()=>vi.clearAllMocks());
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
