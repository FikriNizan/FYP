import React from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import Monitoring from '../src/pages/Monitoring.jsx';
import { api } from '../src/api.js';

vi.mock('../src/api.js',async original=>({...await original(),api:{monitoring:vi.fn(),monitoringTrend:vi.fn()}}));
const batches=[{batch_id:'april',cutoff_month:'2024-04-30',record_count:1000}];
const empty={records:0,positives:0,observed_rate:null,mean_risk:null,brier:null,reference_brier:null,flagged:0,flagged_positives:0,flagged_positive:null,
  true_positives:0,false_positives:0,false_negatives:0,true_negatives:0,precision:null,recall:null,f1:null};
const base={batch_id:'april',cutoff_month:'2024-04-30',outcome_month:'2024-07-31',records:1000,state:'not_loaded',
  outcome_coverage:{loaded:0,unavailable:1000,documented_delivery:0,without_recorded_delivery:0},
  observed_all:empty,documented_delivery:empty,without_recorded_delivery:empty,delivery_types:{},
  drift:null,interpretation:'No causal effects are inferred.'};
const trend={protocol_sha256:'same',batches:[{batch_id:'april',cutoff_month:'2024-04-30',records:1000,
  state:'not_loaded',loaded:0,unavailable:1000,mean_risk_all:.16,flagged_rate_all:.2,
  mean_risk_loaded:null,observed_rate:null,gap:null,brier:null,reference_brier:null,flagged_positive:null}]};
function start(){render(<MemoryRouter><Monitoring batches={batches}/></MemoryRouter>);}
beforeEach(()=>{vi.resetAllMocks();api.monitoringTrend.mockResolvedValue(trend);});
function openGuide(){fireEvent.click(screen.getByText('How to read this page'));}

describe('Outcome monitoring',()=>{
  it('keeps unloaded outcomes unavailable and preserves interpretation in the guide',async()=>{
    api.monitoring.mockResolvedValue(base);start();
    expect((await screen.findAllByText('Not loaded')).length).toBeGreaterThan(0);
    expect(screen.queryByText('Model performance')).toBeNull();
    expect(screen.getAllByText('Not provided',{selector:'td'}).length).toBeGreaterThan(0);
    openGuide();
    expect(screen.getByText(/Unavailable includes outcomes not imported/)).toBeTruthy();
    expect(screen.getByText(/This page does not create labels/)).toBeTruthy();
    expect(api.monitoring).toHaveBeenCalledWith('april');
    expect(api.monitoringTrend).toHaveBeenCalledWith('april');
  });
  it('renders a window-open state without inventing outcomes',async()=>{
    api.monitoring.mockResolvedValue({...base,state:'window_open',outcome_month:'2999-07-31'});start();
    expect(await screen.findByText('Window open')).toBeTruthy();
    expect(screen.getByText(/Outcomes cannot be assessed yet/)).toBeTruthy();
  });
  it('renders partly loaded coverage and the empty delivery state',async()=>{
    api.monitoring.mockResolvedValue({...base,state:'partly_loaded',
      outcome_coverage:{loaded:1,unavailable:999,documented_delivery:0,without_recorded_delivery:1},
      observed_all:{...empty,records:1,positives:0,observed_rate:0,mean_risk:.2,brier:.04,reference_brier:0},
      without_recorded_delivery:{...empty,records:1,positives:0,observed_rate:0,mean_risk:.2}});
    start();
    expect(await screen.findByText('Partly loaded')).toBeTruthy();
    expect(screen.getByText(/999 unavailable outcomes/)).toBeTruthy();
    expect(screen.getByText(/No documented deliveries were recorded/)).toBeTruthy();
  });
  it('shows descriptive groups and the same-customer comparison',async()=>{
    api.monitoring.mockResolvedValue({...base,state:'loaded',
      outcome_coverage:{loaded:1000,unavailable:0,documented_delivery:3,without_recorded_delivery:997},
      observed_all:{...empty,records:1000,positives:184,observed_rate:.184,mean_risk:.16,brier:.127,reference_brier:.150,flagged:208,flagged_positives:40,
        true_positives:40,false_positives:168,false_negatives:144,true_negatives:648,precision:40/208,recall:40/184,f1:80/392},
      documented_delivery:{...empty,records:3,positives:1,observed_rate:1/3,mean_risk:.2,flagged:2,flagged_positives:1},
      without_recorded_delivery:{...empty,records:997,positives:183,observed_rate:183/997,mean_risk:.16,flagged:206,flagged_positives:39}});
    start();
    expect(await screen.findByText('Documented delivery',{selector:'h3'})).toBeTruthy();
    expect(screen.getByText('No recorded delivery',{selector:'h3'})).toBeTruthy();
    expect(screen.getAllByText('40 of 208',{exact:false}).length).toBeGreaterThan(0);
    fireEvent.click(screen.getByText('Classification details'));
    expect(screen.getByText(/Missed observed drops: 144/)).toBeTruthy();
    expect(screen.getByText(/Of all observed volume drops, how many were flagged/)).toBeTruthy();
    openGuide();expect(screen.getByText(/do not prove retention benefit/)).toBeTruthy();
  });
  it('switches the panel population without changing cross-month scope',async()=>{
    api.monitoring.mockResolvedValue({...base,state:'loaded',
      outcome_coverage:{loaded:2,unavailable:998,documented_delivery:1,without_recorded_delivery:1},
      observed_all:{...empty,records:2,positives:1,observed_rate:.5,mean_risk:.4,brier:.21,reference_brier:.25,
        flagged:1,flagged_positives:1,true_positives:1,false_positives:0,false_negatives:0,true_negatives:1,precision:1,recall:1,f1:1},
      documented_delivery:{...empty,records:1,positives:1,observed_rate:1,mean_risk:.7},
      without_recorded_delivery:{...empty,records:1,positives:0,observed_rate:0,mean_risk:.1,brier:.01,reference_brier:0,
        flagged:0,flagged_positives:0,true_positives:0,false_positives:0,false_negatives:0,true_negatives:1}});
    start();
    expect(await screen.findByLabelText('Performance population')).toBeTruthy();
    expect(screen.getByText('50.0%')).toBeTruthy();
    fireEvent.change(screen.getByLabelText('Performance population'),{target:{value:'without_recorded_delivery'}});
    expect(screen.getByText('0.0%')).toBeTruthy();
    expect(screen.getAllByText('10.0%').length).toBeGreaterThan(0);
    expect(screen.getByText(/Based on 1 of 2 customers with loaded outcomes/)).toBeTruthy();
    expect(screen.getByText(/Each month uses all customers with loaded outcomes/)).toBeTruthy();
    fireEvent.click(screen.getByText('Classification details'));
    expect(screen.getByText(/Precision/)).toBeTruthy();
  });
  it('shows no selected-group ratios when all loaded customers have documented delivery',async()=>{
    api.monitoring.mockResolvedValue({...base,state:'loaded',
      outcome_coverage:{loaded:1,unavailable:999,documented_delivery:1,without_recorded_delivery:0},
      observed_all:{...empty,records:1,positives:1,observed_rate:1,mean_risk:.5,brier:.25,reference_brier:0},
      documented_delivery:{...empty,records:1,positives:1,observed_rate:1,mean_risk:.5}});
    start();await screen.findByLabelText('Performance population');
    fireEvent.change(screen.getByLabelText('Performance population'),{target:{value:'without_recorded_delivery'}});
    expect(screen.getByText(/No customers with loaded outcomes in this selected population/)).toBeTruthy();
    expect(screen.queryByText('Same-group constant reference')).toBeNull();
  });
  it('retains a valid panel choice and recomputes it after assessment switching',async()=>{
    const april={...base,state:'loaded',outcome_coverage:{loaded:2,unavailable:998,documented_delivery:1,without_recorded_delivery:1},
      observed_all:{...empty,records:2,positives:1,observed_rate:.5,mean_risk:.4,brier:.2,reference_brier:.25},
      without_recorded_delivery:{...empty,records:1,positives:0,observed_rate:0,mean_risk:.1,brier:.01,reference_brier:0}};
    const march={...base,batch_id:'march',cutoff_month:'2024-03-31',outcome_month:'2024-06-30',state:'loaded',
      outcome_coverage:{loaded:1,unavailable:999,documented_delivery:1,without_recorded_delivery:0},
      observed_all:{...empty,records:1,positives:1,observed_rate:1,mean_risk:.9,brier:.01,reference_brier:0}};
    api.monitoring.mockImplementation(id=>Promise.resolve(id==='april'?april:march));
    render(<MemoryRouter><Monitoring batches={[...batches,{batch_id:'march',cutoff_month:'2024-03-31',record_count:1000}]}/></MemoryRouter>);
    await screen.findByLabelText('Performance population');
    fireEvent.change(screen.getByLabelText('Performance population'),{target:{value:'without_recorded_delivery'}});
    expect(screen.getAllByText('10.0%').length).toBeGreaterThan(0);
    fireEvent.click(screen.getByRole('button',{name:'Mar 2024'}));
    expect(await screen.findByText(/No customers with loaded outcomes in this selected population/)).toBeTruthy();
    expect(screen.getByLabelText('Performance population').value).toBe('without_recorded_delivery');
    expect(screen.queryByText('10.0%')).toBeNull();
  });
  it('shows a loading error without invented performance values',async()=>{
    api.monitoring.mockRejectedValue(new Error('Saved report unavailable'));
    start();
    expect(await screen.findByText('Saved report unavailable')).toBeTruthy();
    expect(screen.queryByText('Model performance')).toBeNull();
  });
  it('shows curated movement and expands remaining features',async()=>{
    const feature=(name)=>({feature:name,previous_available:1000,current_available:1000,previous_median:10,current_median:12,unit:'saved feature units'});
    api.monitoring.mockResolvedValue({...base,drift:{previous_month:'2024-03-31',previous_records:1000,current_records:1000,
      previous_mean_risk:.1,current_mean_risk:.2,previous_flagged_rate:.15,current_flagged_rate:.25,
      features:[feature('combined_flow_mean_3m_myr'),feature('active_account_count')]}});
    start();expect((await screen.findAllByText(/Combined flow, 3-month mean/)).length).toBeGreaterThan(0);
    fireEvent.click(screen.getByText('Show all 78 features'));
    expect(screen.getByText(/Active Account Count/)).toBeTruthy();
  });
});
