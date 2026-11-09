import React from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import App from '../src/App.jsx';
import FlowHistory from '../src/components/FlowHistory.jsx';
import { api } from '../src/api.js';
import { observedMonths } from '../src/flows.js';
import { discussionQuestions } from '../src/briefing.js';
import briefingPayload from './fixtures/briefing.json';
import demo from '../../backend/demo/notebook_case.json';

vi.mock('../src/api.js',async original=>({...await original(),api:{months:vi.fn(),summary:vi.fn(),customers:vi.fn(),customer:vi.fn(),saveReview:vi.fn(),case:vi.fn(),cases:vi.fn(),briefing:vi.fn(),downloadBriefing:vi.fn()}}));
const batch={batch_id:'enriched',cutoff_month:'2024-02-29',record_count:1000,source_kind:'saved_shap_export',imported_at:'2026-11-01T18:00:00Z',source:{customer_names_loaded:true,flow_history_loaded:true}};
let customer,reviewed;
function start(path) { render(<MemoryRouter initialEntries={[path]}><App /></MemoryRouter>); }
afterEach(()=>vi.restoreAllMocks());
beforeEach(()=>{
  vi.clearAllMocks();
  customer={cus_id:'944',customer_name:'Saved evidence company',batch_id:'enriched',prediction_id:'prediction',cutoff_month:'2024-02-29',calibrated_risk:.844,review_alert:true,probability_cutoff:.2586,review:{version:1,decision:'prioritise',reason:'Discuss observed activity',reviewer:'Committee',owner:'RM A',operations_notes:'Check payment experience',finance_notes:'Consider available balances'},finance:{non_fd_balance_myr:0,fd_balance_myr:null},operations:{combined_flow_mean_3m_myr:50,combined_flow_mean_12m_myr:100,outbound_failure_rate_3m:.4},explanation:demo.record,flow_history:[],actions:[]};
  reviewed={case_id:'case-a',version:1,status:'open',owner:'RM A',next_action_date:null,original:customer,latest:customer,original_review:customer.review,follow_ups:[],follow_up_counts:{planned:0,attempted:0,delivered:0},history:[],review_history:[],created_at:'2026-11-01T10:00:00Z'};
  api.months.mockResolvedValue({items:[batch]});
  api.summary.mockResolvedValue({batch,population:1000,flagged:208,below_threshold:792,flagged_review_counts:{awaiting_review:200,prioritise:8},finance:Object.fromEntries(['non_fd_balance_myr','fd_balance_myr','estimated_monthly_fee_myr','estimated_monthly_waiver_myr'].map(k=>['flagged_'+k,{total:null,records:208,records_with_value:0}]))});
  api.customers.mockResolvedValue({items:[customer],total:120});
  api.customer.mockResolvedValue({customer});
  api.case.mockImplementation(async()=>({case:structuredClone(reviewed)}));
  api.cases.mockImplementation(async()=>({items:[structuredClone(reviewed)],total:1}));
  api.briefing.mockImplementation(async()=>{
    if(reviewed.original.review.decision!=='prioritise') throw new Error('Selected case is no longer prioritised.');
    const payload=structuredClone(briefingPayload);
    payload.items[0].name=customer.customer_name;
    return payload;
  });
});

describe('Work-focused frontend',()=>{
  it('returns to the same assessment, query, decision filter and queue page',async()=>{
    start('/overview?batch_id=enriched&filter=all&decision=monitor&q=944&offset=50');
    await screen.findByRole('link',{name:'Open review'});
    fireEvent.click(screen.getByRole('link',{name:'Open review'}));
    await screen.findByRole('heading',{name:'Saved evidence company'});
    fireEvent.click(screen.getByRole('link',{name:'← Back to review queue'}));
    await screen.findByRole('heading',{name:'Overview'});
    expect(screen.getByLabelText('Find customer').value).toBe('944');
    expect(screen.getByLabelText('Committee decision').value).toBe('monitor');
    expect(screen.getByRole('button',{name:'All customers'}).getAttribute('aria-pressed')).toBe('true');
    expect(api.customers).toHaveBeenLastCalledWith('enriched',{q:'944',decision:'monitor',offset:50,limit:50});
  });

  it('keeps gaps, true zeros and cutoff boundaries in all flow measures',()=>{
    const history=[{snapshot_month:'2024-01-31',combined_flow_myr:0,inbound_myr:0,outbound_success_myr:0},{snapshot_month:'2024-03-31',combined_flow_myr:100,inbound_myr:30,outbound_success_myr:70},{snapshot_month:'2024-04-30',combined_flow_myr:999999}];
    expect(observedMonths(history,'2024-03-31').map(r=>r.snapshot_month)).toEqual(['2024-01-31','2024-02-29','2024-03-31']);
    const {container}=render(<FlowHistory history={history} cutoff="2024-03-31" baseline={50} />);
    expect(container.querySelectorAll('rect')).toHaveLength(2);
    expect(container.querySelector('rect').getAttribute('height')).toBe('0');
    expect(screen.getByText('February 2024')).toBeTruthy();
    expect(screen.queryByText('April 2024')).toBeNull();
    fireEvent.change(screen.getByLabelText('Measure'),{target:{value:'inbound_myr'}});
    expect(container.querySelector('.baseline')).toBeNull();
    expect(screen.getByRole('img').getAttribute('aria-label')).toContain('Incoming flow');
  });

  it('shows saved coverage while failed-upload previews never send a file or mutate records',async()=>{
    const fetchSpy=vi.spyOn(globalThis,'fetch');
    start('/assessments');
    await screen.findByRole('link',{name:'Open overview'});
    expect(screen.getByText('1,000 customers')).toBeTruthy();
    expect(screen.getByRole('button',{name:'Upload monthly package'}).disabled).toBe(true);
    fireEvent.click(screen.getByRole('button',{name:'Explore workflow preview'}));
    fireEvent.change(screen.getByLabelText('Preview state'),{target:{value:'failed'}});
    expect(screen.getByRole('heading',{name:'Validation failed · constructed example'})).toBeTruthy();
    expect(screen.getByText('Package cutoff is missing.')).toBeTruthy();
    expect(screen.getByRole('link',{name:'Open overview'}).getAttribute('href')).toBe('/overview?batch_id=enriched');
    fireEvent.click(screen.getByRole('button',{name:'Preview correction and resubmission'}));
    expect(screen.getByLabelText('Monthly package upload unavailable').disabled).toBe(true);
    expect(fetchSpy).not.toHaveBeenCalled(); fetchSpy.mockRestore();
  });

  it('changes only hypothetical OPR inputs and never invents a calculated output',async()=>{
    const fetchSpy=vi.spyOn(globalThis,'fetch');
    start('/research');
    await screen.findByLabelText('Deposit renewal assumption (%)');
    fireEvent.change(screen.getByLabelText('Deposit renewal assumption (%)'),{target:{value:'65'}});
    expect(screen.getByText(/Deposit exit assumption: 35%/)).toBeTruthy();
    expect(screen.getAllByText('Not calculated').length).toBeGreaterThan(0);
    expect(screen.getByRole('button',{name:'Calculate scenario · unavailable'}).disabled).toBe(true);
    expect(fetchSpy).not.toHaveBeenCalled(); fetchSpy.mockRestore();
  });

  it('builds an explicitly selected briefing with real evidence, questions, AI unavailable and browser print',async()=>{
    const print=vi.spyOn(window,'print').mockImplementation(()=>{});
    start('/briefing?case_id=case-a');
    await screen.findByRole('heading',{name:'Saved evidence company'});
    expect(api.briefing).toHaveBeenCalledWith(['case-a']);
    expect(screen.getByText('AI draft not available yet.')).toBeTruthy();
    expect(screen.getByRole('button',{name:'Generate AI draft · unavailable'}).disabled).toBe(true);
    expect(screen.getByRole('button',{name:'Download PDF'}).disabled).toBe(false);
    expect(screen.getByText(/Recent recorded transaction activity is lower/)).toBeTruthy();
    expect(screen.getByText('No newer assessment month is available.')).toBeTruthy();
    fireEvent.change(screen.getByLabelText('AI state preview'),{target:{value:'ready'}});
    expect(screen.getByRole('heading',{name:'Example draft · human review required'})).toBeTruthy();
    expect(screen.getByText(/It was not generated by an AI service/)).toBeTruthy();
    fireEvent.change(screen.getByLabelText('AI state preview'),{target:{value:'error'}});
    expect(screen.getByRole('heading',{name:'Draft request failed · demo preview'})).toBeTruthy();
    expect(screen.getAllByText('Not provided').length).toBeGreaterThan(0);
    fireEvent.click(screen.getByRole('button',{name:'Print briefing'}));
    await waitFor(()=>expect(print).toHaveBeenCalledOnce()); print.mockRestore();
  });

  it('selects only prioritised cases and blocks briefings for a changed committee decision',async()=>{
    start('/reviewed');
    await screen.findByRole('checkbox');
    fireEvent.click(screen.getByRole('checkbox'));
    const briefingURL=new URL(screen.getByRole('link',{name:'Prepare RM briefing'}).getAttribute('href'),'http://localhost');
    expect(briefingURL.searchParams.get('case_id')).toBe('case-a');
    expect(briefingURL.searchParams.get('worklist')).toContain('pick=case-a');
    reviewed.original.review.decision='monitor';
    fireEvent.click(screen.getByRole('link',{name:'Prepare RM briefing'}));
    await screen.findByRole('alert');
    expect(screen.getByRole('button',{name:'Print briefing'}).disabled).toBe(true);
  });

  it('keeps questions bounded to supplied evidence and exposes a labelled cross-month example',async()=>{
    expect(discussionQuestions({operations:{},explanation:{higher_risk_drivers:[]}})).toEqual([]);
    expect(discussionQuestions(customer).length).toBeLessThanOrEqual(3);
    start('/guide');
    await screen.findByText('70.0%');
    expect(screen.getByText('18.0%')).toBeTruthy();
    expect(screen.getByText('Demo preview')).toBeTruthy();
    expect(api.case).not.toHaveBeenCalled();
  });
});
