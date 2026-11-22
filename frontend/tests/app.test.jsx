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
const summary = () => ({ batch,population:1000,flagged:208,flagged_share:.208,flagged_balances:{total:0,fixed_deposits:0,operating:0,records:208},below_threshold:792,flagged_review_counts:{awaiting_review:customer.review.version ? 207 : 208,prioritise:customer.review.version ? 1 : 0},finance:Object.fromEntries(['non_fd_balance_myr','fd_balance_myr','estimated_monthly_fee_myr','estimated_monthly_waiver_myr'].map(key=>['flagged_'+key,{total:0,records_with_value:208,records:208}])) });
function start(path='/overview?batch_id=enriched') { return render(<MemoryRouter initialEntries={[path]}><App /></MemoryRouter>); }
function editDecision() {
  fireEvent.change(screen.getByLabelText('Decision'),{target:{value:'prioritise'}});
  fireEvent.change(screen.getByLabelText('Decision reason'),{target:{value:'Committee development test'}});
  fireEvent.change(screen.getByLabelText('Reviewed by'),{target:{value:'Developer'}});
}
beforeEach(() => {
  vi.resetAllMocks();
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
    await screen.findByRole('heading',{name:'Overview'});
    expect(screen.getByText('1,000')).toBeTruthy();
    expect(screen.getByText('20.8% of customers')).toBeTruthy();
    fireEvent.click(screen.getByRole('button',{name:'Flagged · awaiting review'}));
    await waitFor(()=>expect(api.customers).toHaveBeenLastCalledWith('enriched',expect.objectContaining({flagged:true,workflow:'needs_review'})));
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
    expect(screen.getByText('At or above the review threshold (25.9%)')).toBeTruthy();
    expect(screen.getByText('a month, last 3 months').previousElementSibling.textContent).toMatch(/214,333\.04/);
    expect(screen.getByText(/^CIF 944 · /)).toBeTruthy();
    expect(screen.getByText('Awaiting review',{selector:'.badge'})).toBeTruthy();
    expect(screen.getByRole('heading',{name:'Signals to investigate'})).toBeTruthy();
    fireEvent.click(screen.getByRole('tab',{name:'Operations'}));
    expect(screen.getByRole('heading',{name:'Operations perspective'})).toBeTruthy();
    fireEvent.click(screen.getByRole('tab',{name:'Finance'}));
    const finance=screen.getByRole('heading',{name:'Finance perspective'}).closest('section');
    expect(within(finance).getByText(/2,016,997.13/)).toBeTruthy();
    expect(within(finance).getByText('Relationship contribution is not provided for this assessment.')).toBeTruthy();
    expect(within(finance).getByText(/^RM\s?0\.00$/)).toBeTruthy();                 // Zero fixed deposits stay zero.
    expect(within(finance).getByText(/Waived fees: RM\s?0\.00 a month/)).toBeTruthy(); // Zero waivers stay zero.
    expect(within(finance).queryByText(/Fee income/)).toBeNull();                       // Missing fees are never shown as zero.
    expect(screen.getByRole('tab',{name:'Finance'}).getAttribute('aria-selected')).toBe('true');
    expect(screen.getByText('84.4%')).toBeTruthy();
  });
  it('saves all editable fields with the expected version and reloads the accepted result',async()=>{
    start('/customer/944?batch_id=enriched');
    await screen.findByLabelText('Decision'); editDecision();
    fireEvent.click(screen.getByRole('button',{name:'Save decision'}));
    await waitFor(()=>expect(api.saveReview).toHaveBeenCalledWith('prediction',{decision:'prioritise',reason:'Committee development test',reviewer:'Developer',owner:'',next_action_date:null,operations_notes:'',finance_notes:'',expected_version:0}));
    await screen.findByText('Saved decision · version 1');
    expect(screen.getByLabelText('Decision').value).toBe('prioritise');
  });
  it('shows the save notice on the saving page only, and again after a second save',async()=>{
    const {container}=start('/customer/944?batch_id=enriched');
    const notice=()=>container.querySelector('#notification');
    expect(notice().getAttribute('role')).toBe('status');
    expect(notice().getAttribute('aria-live')).toBe('polite');
    await screen.findByLabelText('Decision'); editDecision();
    fireEvent.click(screen.getByRole('button',{name:'Save decision'}));
    await screen.findByText('Saved decision · version 1');              // The post-save refresh has run on this page.
    expect(notice().textContent).toBe('Decision saved for customer 944, February 2024. The original prediction and transaction history are preserved.');
    fireEvent.click(screen.getByRole('link',{name:'Overview'}));
    await screen.findByRole('heading',{name:'Overview'});
    expect(notice().textContent).toBe('');
    fireEvent.click(await screen.findByRole('link',{name:/Acceptance test company/}));
    await screen.findByText('Saved decision · version 1');
    expect(notice().textContent).toBe('');
    fireEvent.change(screen.getByLabelText('Decision'),{target:{value:'monitor'}});
    fireEvent.change(screen.getByLabelText('Decision reason'),{target:{value:'Second committee test'}});
    fireEvent.click(screen.getByRole('button',{name:'Save decision'}));
    await waitFor(()=>expect(api.saveReview).toHaveBeenCalledTimes(2));
    await waitFor(()=>expect(notice().textContent).toMatch(/^Decision saved for customer 944, February 2024\./));
  });
  it('retains a draft across navigation until the user saves',async()=>{
    start('/customer/944?batch_id=enriched');
    await screen.findByLabelText('Decision'); editDecision();
    fireEvent.click(screen.getByRole('link',{name:'Overview'}));
    await screen.findByRole('heading',{name:'Overview'});
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
  it('can discard a normal decision draft without saving or changing evidence',async()=>{
    start('/customer/944?batch_id=enriched');
    await screen.findByLabelText('Decision');editDecision();
    fireEvent.click(screen.getByRole('button',{name:'Discard decision changes'}));
    expect(screen.getByLabelText('Decision').value).toBe('');
    expect(screen.getByLabelText('Decision reason').value).toBe('');
    expect(screen.queryByText('Unsaved changes')).toBeNull();
    expect(api.saveReview).not.toHaveBeenCalled();
    expect(screen.getByText('84.4%')).toBeTruthy();
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


describe('Cutoff-safe Customer Review workflow',()=>{
  it.each([null,{target_churn:true,outcome_month:'2024-05-31'}])('omits retrospective outcome cards with outcome %s while preserving review and evidence',async(outcome)=>{
    customer.observed_outcome=outcome;
    start('/customer/944?batch_id=enriched');
    await screen.findByRole('heading',{name:'Acceptance test company'});
    expect(screen.queryByRole('heading',{name:/Observed outcome/})).toBeNull();
    expect(screen.getByText('Recent activity vs usual')).toBeTruthy();
    expect(screen.getByLabelText('Decision')).toBeTruthy();
    expect(screen.getByRole('heading',{name:'Summary'})).toBeTruthy();
    expect(screen.getByRole('tab',{name:'Operations'})).toBeTruthy();
    expect(screen.getByRole('tab',{name:'Finance'})).toBeTruthy();
  });
});

describe('Customer review layout (Phase C)',()=>{
  it('keeps the full committee decision panel beside every tab and labels tabs with icons',async()=>{
    start('/customer/944?batch_id=enriched');
    await screen.findByRole('heading',{name:'Acceptance test company'});
    for (const tab of ['Summary','Operations','Finance']) {
      fireEvent.click(screen.getByRole('tab',{name:tab}));
      const form=screen.getByRole('heading',{name:'Record committee decision'}).closest('aside');
      for (const label of ['Decision','Decision reason','Reviewed by','RM / action owner (optional)','Next follow-up date (optional)']) expect(within(form).getByLabelText(label)).toBeTruthy();
      expect(within(form).getByText('Notes from each perspective (optional)')).toBeTruthy();
      expect(within(form).getByRole('button',{name:'Save decision'})).toBeTruthy();
      expect(within(form).getByRole('button',{name:'Discard decision changes'}).disabled).toBe(true);
      expect(within(form).getByText('No decision saved yet')).toBeTruthy();
      expect(screen.getByRole('tab',{name:tab}).querySelector('svg')).toBeTruthy();
    }
  });
  it('shows signals with a relative bar and no numbers or percentage weights',async()=>{
    start('/customer/944?batch_id=enriched');
    const panel=(await screen.findByRole('heading',{name:'Signals to investigate'})).closest('section');
    expect(panel.querySelectorAll('.sig').length).toBeGreaterThan(0);
    for (const meter of panel.querySelectorAll('.meter')) { expect(meter.getAttribute('aria-hidden')).toBe('true'); expect(meter.textContent).toBe(''); }
    expect(panel.textContent).not.toMatch(/log-odds|logodds|SHAP|contribution_logodds|weight/i);
    expect(panel.querySelectorAll('details')).toHaveLength(0);
    for (const driver of [...customer.explanation.higher_risk_drivers, ...customer.explanation.lower_risk_drivers])
      expect(panel.textContent).not.toContain(String(driver.contribution_logodds));
  });
});
