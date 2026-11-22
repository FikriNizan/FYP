import React from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen, fireEvent, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import Monitoring from '../src/pages/Monitoring.jsx';
import { api } from '../src/api.js';

vi.mock('../src/api.js',async original=>({...await original(),api:{monitoring:vi.fn(),monitoringTrend:vi.fn(),scenarios:vi.fn()}}));
const batches=[{batch_id:'april',cutoff_month:'2024-04-30',record_count:1000},{batch_id:'feb',cutoff_month:'2024-02-29',record_count:1000}];
const empty={records:0,positives:0,negatives:0,expected_positives:null,observed_rate:null,mean_risk:null,brier:null,reference_brier:null,flagged:0,flagged_positives:0,flagged_positive:null,
  true_positives:0,false_positives:0,false_negatives:0,true_negatives:0,precision:null,recall:null,f1:null};
const waiting={state:'waiting',loaded:0,records:1000,waiting_for_month:'2024-05-31',ready_after_month:'2024-07-31',window:['2024-05-31','2024-06-30','2024-07-31']};
const checked={state:'checked',loaded:1000,records:1000,waiting_for_month:null,ready_after_month:'2024-05-31',window:['2024-03-31','2024-04-30','2024-05-31']};
const base={batch_id:'april',cutoff_month:'2024-04-30',outcome_month:'2024-07-31',records:1000,state:'not_loaded',outcome_check:waiting,
  outcome_coverage:{loaded:0,unavailable:1000,documented_delivery:0,without_recorded_delivery:0},
  observed_all:empty,documented_delivery:empty,without_recorded_delivery:empty,delivery_types:{},drift:null,interpretation:'No causal effects are inferred.'};
const febStats={...empty,records:1000,positives:171,negatives:829,expected_positives:160.8,observed_rate:.171,mean_risk:.16,brier:.127,reference_brier:.14,flagged:208,flagged_positives:83,
  true_positives:83,false_positives:125,false_negatives:88,true_negatives:704,precision:83/208,recall:83/171,f1:166/379};
const feb={...base,batch_id:'feb',cutoff_month:'2024-02-29',outcome_month:'2024-05-31',state:'loaded',outcome_check:checked,
  outcome_coverage:{loaded:1000,unavailable:0,documented_delivery:3,without_recorded_delivery:997},observed_all:febStats,
  documented_delivery:{...empty,records:3,positives:1,negatives:2},without_recorded_delivery:{...empty,records:997,positives:170,negatives:827},
  drift:{previous_month:'2024-01-31',previous_mean_risk:.15,current_mean_risk:.16,previous_flagged:200,current_flagged:208,
    features:[{feature:'combined_flow_mean_1m_myr',previous_median:110900,current_median:111600}]}};
const trendItem=(id,cutoff,check,extra={})=>({batch_id:id,cutoff_month:cutoff,records:1000,state:'loaded',loaded:check.loaded,outcome_check:check,
  precision:null,recall:null,expected_positives:null,positives:null,...extra});
const trend=(febCheck=checked)=>({protocol_sha256:'same',batches:[
  trendItem('feb','2024-02-29',febCheck,febCheck.state==='checked'?{precision:83/208,recall:83/171,expected_positives:160.8,positives:171}:{}),
  trendItem('april','2024-04-30',waiting)]});
function start(path='/monitoring'){return render(<MemoryRouter initialEntries={[path]}><Monitoring batches={batches}/></MemoryRouter>);}
beforeEach(()=>{vi.resetAllMocks();});

describe('Monitoring · Outcomes',()=>{
  it('shows readiness cards with "Ready after <last window month> data" and an empty state when nothing is checkable',async()=>{
    api.monitoring.mockResolvedValue(base);api.monitoringTrend.mockResolvedValue(trend({...waiting,ready_after_month:'2024-05-31'}));
    const {container}=start();
    const ready=(await screen.findByRole('heading',{name:'Which assessments can be checked'})).closest('section');
    expect([...ready.querySelectorAll('.rstep')].map(card=>card.textContent)).toEqual(['February 2024Ready after May 2024 data','April 2024Ready after July 2024 data']);
    expect(screen.getByText('Nothing to check yet.')).toBeTruthy();
    expect(screen.getByText('April 2024 forecasts May–Jul 2024. It becomes checkable when the July 2024 package is uploaded in Monthly Assessments.')).toBeTruthy();
    expect(screen.queryByText('Caught')).toBeNull();                       // No outcomes are invented.
    expect(container.textContent).not.toMatch(/Brier/);
    expect(api.monitoring).toHaveBeenCalledWith('april');
  });

  it('shows the 2x2 with the exact labels, plain sentences, F1, expected vs actual and the follow-up split',async()=>{
    api.monitoring.mockResolvedValue(feb);api.monitoringTrend.mockResolvedValue(trend());
    const {container}=start('/monitoring?batch_id=feb');
    const matrix=await screen.findByRole('table',{name:'Flags against observed outcomes'});
    expect(within(matrix).getAllByRole('columnheader').map(h=>h.textContent)).toEqual(['Activity halved','Not halved']);
    expect(within(matrix).getAllByRole('rowheader').map(h=>h.textContent)).toEqual(['Flagged','Not flagged']);
    expect(within(matrix).getAllByRole('cell').map(c=>c.textContent)).toEqual(['83Caught','125False alarmMay include customers an RM kept','88Missed','704Correctly quiet']);
    expect(screen.getByText(/flags were real drops/).closest('span').textContent).toBe('83 of 208 flags were real drops (39.9%).');
    expect(screen.getByText(/The model caught/).closest('span').textContent).toBe('The model caught 83 of 171 drops (48.5%).');
    expect(screen.getByText('F1 0.44')).toBeTruthy();
    const expected=screen.getByRole('heading',{name:'Expected vs actual drops'}).closest('section');
    expect(within(expected).getByText('161')).toBeTruthy();
    expect(within(expected).getByText('171')).toBeTruthy();
    expect(within(expected).getByText('More drops than the predicted risk expected.')).toBeTruthy();
    const followed=screen.getByRole('heading',{name:'Follow-up and outcomes'}).closest('section');
    expect(within(followed).getByText('All customers with outcomes · follow-up inside the Mar–May 2024 window')).toBeTruthy();
    expect([...followed.querySelectorAll('.fu b')].map(b=>b.textContent)).toEqual(['Follow-up delivered','No delivered follow-up recorded']);
    expect(within(followed).getByRole('img',{name:'1 halved, 2 not halved'})).toBeTruthy();
    expect(within(followed).getByRole('img',{name:'170 halved, 827 not halved'})).toBeTruthy();
    expect([...followed.querySelectorAll('.key span')].map(s=>s.textContent)).toEqual(['Activity halved','Not halved']);
    expect(followed.querySelector('.hint').textContent).toBe('A followed-up customer whose activity was not halved counts as a false alarm, but the RM may have kept them. No record does not prove no contact.');
    expect(screen.queryByText('Were flags followed up?')).toBeNull();
    expect(container.textContent).not.toMatch(/Activity held|recorded follow-up/);
    expect(container.textContent).not.toMatch(/Brier|reference/i);           // Brier stays in the API and docs.
    expect(screen.queryByRole('combobox')).toBeNull();                      // No population selector toggle.
  });

  it('lays out readiness, two equal-height rows and month by month full width',async()=>{
    api.monitoring.mockResolvedValue(feb);api.monitoringTrend.mockResolvedValue(trend());
    const {container}=start('/monitoring?batch_id=feb');
    await screen.findByRole('table',{name:'Flags against observed outcomes'});
    const panel=container.querySelector('[role=tabpanel]');
    const title=node=>node.querySelector('h2').textContent;
    expect([...panel.children].map(n=>n.classList.contains('row-eq') ? [...n.children].map(title) : title(n))).toEqual([
      'Which assessments can be checked',
      ["How did February 2024's flags turn out?",'Follow-up and outcomes'],
      ['Expected vs actual drops','Input movement since last month'],
      'Month by month']);
    expect(panel.querySelectorAll('.two-columns')).toHaveLength(0);
  });

  it('without outcomes keeps input movement and month by month, each full width',async()=>{
    api.monitoring.mockResolvedValue(base);api.monitoringTrend.mockResolvedValue(trend({...waiting,ready_after_month:'2024-05-31'}));
    const {container}=start();
    await screen.findByText('Nothing to check yet.');
    const panel=container.querySelector('[role=tabpanel]');
    expect([...panel.children].map(n=>n.querySelector('h2')?.textContent ?? n.textContent)).toEqual([
      'Which assessments can be checked','Nothing to check yet.April 2024 forecasts May–Jul 2024. It becomes checkable when the July 2024 package is uploaded in Monthly Assessments.',
      'Input movement since last month','Month by month']);
    expect(panel.querySelectorAll('.row-eq')).toHaveLength(0);
  });

  it('keeps unavailable outcomes out of the counts and never counts them as zero',async()=>{
    api.monitoring.mockResolvedValue({...feb,outcome_coverage:{...feb.outcome_coverage,loaded:998,unavailable:2}});api.monitoringTrend.mockResolvedValue(trend());
    start('/monitoring?batch_id=feb');
    expect(await screen.findByText('2 unavailable outcomes are excluded and never counted as zero.')).toBeTruthy();
  });

  it('shows month by month for checked assessments and the readiness label for the rest, plus input movement',async()=>{
    api.monitoring.mockResolvedValue(feb);api.monitoringTrend.mockResolvedValue(trend());
    start('/monitoring?batch_id=feb');
    const months=(await screen.findByRole('heading',{name:'Month by month'})).closest('section');
    const rows=[...months.querySelectorAll('tbody tr')].map(r=>[...r.children].map(c=>c.textContent));
    expect(rows).toEqual([['Flags that were real drops','39.9%','Ready after July 2024 data'],['Drops the model caught','48.5%','Ready after July 2024 data'],['Expected vs actual drops','161 / 171','Ready after July 2024 data']]);
    const movement=screen.getByRole('heading',{name:'Input movement since last month'}).closest('section');
    expect([...movement.querySelectorAll('tbody tr')].map(r=>[...r.children].map(c=>c.textContent.replace(/ /g,' '))))
      .toEqual([['Average predicted risk','15.0%','16.0%'],['Flagged customers','200','208'],['Median combined flow, latest month','RM 110,900.00','RM 111,600.00']]);
    expect(movement.querySelectorAll('details')).toHaveLength(0);
  });

  it('switches assessment from a readiness card and keeps the error state honest',async()=>{
    api.monitoring.mockImplementation(async id=>id==='feb'?feb:base);api.monitoringTrend.mockResolvedValue(trend());
    start();
    fireEvent.click(await screen.findByRole('button',{name:/February 2024/}));
    expect(await screen.findByText('Caught')).toBeTruthy();
    expect(api.monitoring).toHaveBeenLastCalledWith('feb');
  });

  it('shows a loading error without invented performance values',async()=>{
    api.monitoring.mockRejectedValue(new Error('Saved monitoring data is unavailable.'));api.monitoringTrend.mockResolvedValue(trend());
    start();
    expect((await screen.findByRole('alert')).textContent).toBe('Saved monitoring data is unavailable.');
    expect(screen.queryByText('Caught')).toBeNull();
  });
});

describe('Monitoring tabs',()=>{
  it('has exactly two tabs and opens the rate-shock what-if from the URL',async()=>{
    api.scenarios.mockResolvedValue({state:'not_generated'});
    start('/monitoring?tab=rate-shock');
    expect(screen.getAllByRole('tab').map(t=>t.textContent)).toEqual(['Outcomes','Rate-shock what-if']);
    expect(screen.getByRole('tab',{name:'Rate-shock what-if'}).getAttribute('aria-selected')).toBe('true');
    expect(await screen.findByText(/Not calculated\./)).toBeTruthy();
    expect(api.monitoring).not.toHaveBeenCalled();
  });
});
