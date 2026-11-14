import React from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import Monitoring from '../src/pages/Monitoring.jsx';
import { api } from '../src/api.js';

vi.mock('../src/api.js',async original=>({...await original(),api:{monitoring:vi.fn()}}));
const batches=[{batch_id:'april',cutoff_month:'2024-04-30',record_count:1000}];
const base={batch_id:'april',cutoff_month:'2024-04-30',outcome_month:'2024-07-31',records:1000,
  outcome_coverage:{loaded:0,unavailable:1000,documented_delivery:0,without_recorded_delivery:0},
  documented_delivery:{records:0,observed_rate:null,mean_risk:null,brier:null,flagged_positive:null},
  without_recorded_delivery:{records:0,observed_rate:null,mean_risk:null,brier:null,flagged_positive:null},
  drift:null,interpretation:'No causal effects are inferred.'};
function start(){render(<MemoryRouter><Monitoring batches={batches}/></MemoryRouter>);}
beforeEach(()=>vi.clearAllMocks());

describe('Outcome monitoring',()=>{
  it('keeps unloaded outcomes unavailable instead of treating them as negatives',async()=>{
    api.monitoring.mockResolvedValue(base);
    start();
    expect(await screen.findByText(/Unavailable includes outcomes not imported/)).toBeTruthy();
    expect(screen.getByText(/This page does not create labels/)).toBeTruthy();
    expect(api.monitoring).toHaveBeenCalledWith('april');
  });
  it('labels delivered and unrecorded groups as descriptive, without causal claims',async()=>{
    api.monitoring.mockResolvedValue({...base,
      outcome_coverage:{loaded:1000,unavailable:0,documented_delivery:3,without_recorded_delivery:997},
      documented_delivery:{records:3,observed_rate:1/3,mean_risk:.2,brier:.15,flagged_positive:.5},
      without_recorded_delivery:{records:997,observed_rate:.18,mean_risk:.16,brier:.12,flagged_positive:.4}});
    start();
    expect(await screen.findByText('Documented delivery',{selector:'h3'})).toBeTruthy();
    expect(screen.getByText('No recorded delivery',{selector:'h3'})).toBeTruthy();
    expect(screen.getByText(/do not prove retention benefit/)).toBeTruthy();
  });
});
