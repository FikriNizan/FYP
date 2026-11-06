import React from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import App from '../src/App.jsx';
import { api, ApiError } from '../src/api.js';
import { preferredBatches } from '../src/navigation.js';
import demo from '../../backend/demo/notebook_case.json';
import FlowHistory from '../src/components/FlowHistory.jsx';

vi.mock('../src/api.js', async original => ({ ...await original(), api: { months: vi.fn(), summary: vi.fn(), customers: vi.fn(), customer: vi.fn(), saveReview: vi.fn() } }));
const batch = { batch_id:'enriched', cutoff_month:'2024-02-29', source_kind:'saved_shap_export', record_count:1000, imported_at:'2026-11-02', source:{customer_names_loaded:true,flow_history_loaded:true} };
const emptyReview = { decision:'awaiting_review',reason:'',reviewer:null,owner:'',next_action_date:null,operations_notes:'',finance_notes:'',version:0 };
let customer;
const summary = () => ({ batch,population:1000,flagged:208,below_threshold:792,flagged_review_counts:{awaiting_review:customer.review.version ? 207 : 208,prioritise:customer.review.version ? 1 : 0},finance:Object.fromEntries(['non_fd_balance_myr','fd_balance_myr','estimated_monthly_fee_myr','estimated_monthly_waiver_myr'].map(key=>['flagged_'+key,{total:0,records_with_value:208,records:208}])) });
function start(path='/overview?batch_id=enriched') { return render(<MemoryRouter initialEntries={[path]}><App /></MemoryRouter>); }
function editDecision() {
  fireEvent.change(screen.getByLabelText('Decision'),{target:{value:'prioritise'}});
  fireEvent.change(screen.getByLabelText('Decision reason'),{target:{value:'Committee development test'}});
  fireEvent.change(screen.getByLabelText('Reviewed by'),{target:{value:'Developer'}});
}
beforeEach(() => {
  vi.clearAllMocks();
  const explanation = demo.record;
  customer = { prediction_id:'prediction',batch_id:'enriched',cus_id:'944',customer_name:'Acceptance test company',cutoff_month:'2024-02-29',customer_type:'CORPORATE',calibrated_risk:.844091949823281,probability_cutoff:.2586013233784648,review_alert:true,review:{...emptyReview},finance:{fd_balance_myr:0,non_fd_balance_myr:2016997.13,estimated_monthly_fee_myr:null,estimated_monthly_waiver_myr:0},operations:{combined_flow_mean_3m_myr:214333.04,combined_flow_mean_12m_myr:24622928.0491667},explanation:{...explanation,higher_risk_drivers:explanation.higher_risk_drivers||[],lower_risk_drivers:explanation.lower_risk_drivers||[]},flow_history:[],feature_count:78 };
  api.months.mockResolvedValue({items:[batch]});
  api.summary.mockImplementation(async()=>summary());
  api.customers.mockImplementation(async()=>({batch,total:1,items:[structuredClone(customer)]}));
  api.customer.mockImplementation(async()=>({batch,customer:structuredClone(customer)}));
  api.saveReview.mockImplementation(async(_id,body)=>{customer.review={...body,version:1};return{review:customer.review};});
});
afterEach(() => { vi.restoreAllMocks(); });

describe('React full-stack foundation', () => {
  it('shows API counts and sends the selected batch with search and filters',async()=>{
    start();
    await screen.findByRole('heading',{name:'Monthly overview'});
    expect(screen.getByText('1,000')).toBeTruthy();
    expect(screen.getByText('792 below the review threshold')).toBeTruthy();
    fireEvent.click(screen.getByRole('button',{name:'Flagged · awaiting review'}));
    await waitFor(()=>expect(api.customers).toHaveBeenLastCalledWith('enriched',expect.objectContaining({flagged:true,decision:'awaiting_review'})));
    await screen.findByLabelText('Find customer');
    fireEvent.change(screen.getByLabelText('Find customer'),{target:{value:'A&B'}});
    fireEvent.click(screen.getByRole('button',{name:'Search'}));
    await waitFor(()=>expect(api.customers).toHaveBeenLastCalledWith('enriched',expect.objectContaining({q:'A&B'})));
  });
  it('renders the risk and distinct missing/zero financial values, with shared signals',async()=>{
    start('/customer/944?batch_id=enriched');
    await screen.findByRole('heading',{name:'Acceptance test company'});
    expect(screen.getByText('84.4%')).toBeTruthy();
    expect(screen.getByText('99.1% lower')).toBeTruthy();
    const finance=screen.getByRole('heading',{name:'Finance perspective'}).closest('section');
    expect(within(finance).getByText(/2,016,997.13/)).toBeTruthy();
    expect(within(finance).getByText('Not provided')).toBeTruthy();
    expect(within(finance).getAllByText(/0.00/)).toHaveLength(2);
    const headings=screen.getAllByRole('heading',{level:2}).map(node=>node.textContent);
    expect(headings.indexOf('Signals to investigate')).toBeLessThan(headings.indexOf('Operations perspective'));
  });
  it('saves all editable fields with the expected version and reloads the accepted result',async()=>{
    start('/customer/944?batch_id=enriched');
    await screen.findByLabelText('Decision'); editDecision();
    fireEvent.click(screen.getByRole('button',{name:'Save decision'}));
    await waitFor(()=>expect(api.saveReview).toHaveBeenCalledWith('prediction',{decision:'prioritise',reason:'Committee development test',reviewer:'Developer',owner:'',next_action_date:null,operations_notes:'',finance_notes:'',expected_version:0}));
    await screen.findByText('Saved decision · version 1');
    expect(screen.getByLabelText('Decision').value).toBe('prioritise');
  });
  it('retains a draft across navigation until the user saves',async()=>{
    start('/customer/944?batch_id=enriched');
    await screen.findByLabelText('Decision'); editDecision();
    fireEvent.click(screen.getByRole('link',{name:'Monthly overview'}));
    await screen.findByRole('heading',{name:'Monthly overview'});
    fireEvent.click(screen.getByRole('link',{name:'Open review'}));
    await screen.findByLabelText('Decision reason');
    expect(screen.getByLabelText('Decision reason').value).toBe('Committee development test');
    expect(screen.getByText('Unsaved changes')).toBeTruthy();
    expect(api.saveReview).not.toHaveBeenCalled();
  });
  it('preserves a conflicted draft and reloads saved evidence only after explicit discard',async()=>{
    api.saveReview.mockRejectedValue(new ApiError('This review changed. Reload it before saving your decision.',409,'review_conflict'));
    start('/customer/944?batch_id=enriched');
    await screen.findByLabelText('Decision'); editDecision();
    fireEvent.click(screen.getByRole('button',{name:'Save decision'}));
    await screen.findByRole('alert');
    expect(screen.getByLabelText('Decision reason').value).toBe('Committee development test');
    expect(api.saveReview).toHaveBeenCalledTimes(1);
    customer.review={...emptyReview,decision:'monitor',reason:'Another saved decision',reviewer:'Other reviewer',version:1};
    fireEvent.click(screen.getByRole('button',{name:'Discard draft and load latest decision'}));
    await screen.findByText('Saved decision · version 1');
    expect(screen.getByLabelText('Decision reason').value).toBe('Another saved decision');
  });
  it('makes an unavailable batch explicit instead of silently switching assessment',async()=>{
    start('/overview?batch_id=missing');
    await screen.findByRole('alert');
    expect(api.customers).not.toHaveBeenCalled();
    expect(screen.getByRole('alert').textContent).toContain('not available');
  });
  it('renders a zero-flow month as observed zero alongside its exact amount',()=>{
    const history=[{snapshot_month:'2024-01-31',inbound_myr:60,outbound_success_myr:40,combined_flow_myr:100},{snapshot_month:'2024-02-29',inbound_myr:0,outbound_success_myr:0,combined_flow_myr:0}];
    const {container}=render(<FlowHistory history={history} baseline={50} />);
    expect(screen.getByRole('img')).toBeTruthy();
    expect(screen.getByText('February 2024')).toBeTruthy();
    expect(screen.getAllByText(/0.00/).length).toBeGreaterThanOrEqual(3);
    expect(container.querySelectorAll('rect')[1].getAttribute('height')).toBe('0');
  });
  it('prefers the latest full export and keeps older batches selectable',()=>{
    const sample={...batch,batch_id:'sample',source_kind:'notebook_case_sample',imported_at:'2026-11-03'};
    const old={...batch,batch_id:'old',imported_at:'2026-10-01'};
    expect(preferredBatches([sample,old,batch]).map(b=>b.batch_id)).toEqual(['enriched','old','sample']);
  });
});
