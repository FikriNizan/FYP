import React from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import App from '../src/App.jsx';
import { api, ApiError } from '../src/api.js';
import demo from '../../backend/demo/notebook_case.json';

vi.mock('../src/api.js',async original=>({ ...await original(), api:{ months:vi.fn(),cases:vi.fn(),case:vi.fn(),updateCase:vi.fn(),followUp:vi.fn() } }));
let current;
const batch={batch_id:'feb',cutoff_month:'2024-02-29',source_kind:'saved_shap_export',record_count:1,source:{}};
const review={decision:'prioritise',reason:'Investigate reduced activity',reviewer:'Committee',owner:'RM A'};
function start(path='/cases/jan') { render(<MemoryRouter initialEntries={[path]}><App /></MemoryRouter>); }
beforeEach(()=>{
  vi.clearAllMocks();
  const customer={cus_id:'944',customer_name:'Constructed company',prediction_id:'jan',batch_id:'jan',cutoff_month:'2024-01-31',calibrated_risk:.84,review,explanation:demo.record,operations:{},flow_history:[],actions:[]};
  current={case_id:'jan',prediction_id:'jan',status:'open',owner:'RM A',next_action_date:null,version:1,created_at:'2026-01-01T00:00:00Z',original_review:review,original:customer,latest:{...customer,prediction_id:'feb',batch_id:'feb',cutoff_month:'2024-02-29',calibrated_risk:.12},follow_ups:[],follow_up_counts:{planned:0,attempted:0,delivered:0,cancelled:0},history:[],review_history:[]};
  api.months.mockResolvedValue({items:[batch]});
  api.case.mockImplementation(async()=>({case:structuredClone(current)}));
  api.cases.mockImplementation(async()=>({items:[structuredClone(current)],total:1}));
  api.updateCase.mockImplementation(async(_id,body)=>({case:{...structuredClone(current),...body,version:2}}));
  api.followUp.mockImplementation(async()=>({case:{...structuredClone(current),version:2}}));
});

describe('Reviewed cases',()=>{
  it('shows original and latest contexts and filters across assessments',async()=>{
    start('/reviewed?batch_id=feb');
    await screen.findByText('Constructed company');
    expect(screen.getByText('January 2024')).toBeTruthy();
    fireEvent.change(screen.getByLabelText('Case status'),{target:{value:'deferred'}});
    fireEvent.change(screen.getByLabelText('Owner'),{target:{value:'RM A'}});
    fireEvent.click(screen.getByRole('button',{name:'Apply filters'}));
    await waitFor(()=>expect(api.cases).toHaveBeenLastCalledWith(expect.objectContaining({status:'deferred',owner:'RM A',offset:0})));
    expect(api.cases.mock.calls.at(-1)[0].batch_id).toBeUndefined();
    await screen.findByRole('link',{name:'Open case'});
    fireEvent.click(screen.getByRole('link',{name:'Open case'}));
    await screen.findByText('84.0%');
    expect(screen.getByText('12.0%')).toBeTruthy();
  });
  it('saves an explicit case closure reason with version and nullable next date',async()=>{
    start();
    await screen.findByRole('heading',{name:'Constructed company'});
    fireEvent.click(screen.getByRole('tab',{name:'Manage case'}));
    fireEvent.change(screen.getByLabelText('Case status'),{target:{value:'closed'}});
    fireEvent.change(screen.getByLabelText('Change reason'),{target:{value:'No further follow-up required'}});
    fireEvent.change(screen.getByLabelText('Changed by'),{target:{value:'Reviewer'}});
    fireEvent.click(screen.getByRole('button',{name:'Save case changes'}));
    await waitFor(()=>expect(api.updateCase).toHaveBeenCalledWith('jan',{status:'closed',owner:'RM A',next_action_date:null,notes:'No further follow-up required',recorded_by:'Reviewer',expected_version:1}));
    await screen.findByText('Reopen the case to record another follow-up.');
    expect(screen.getByText('84.0%')).toBeTruthy();
  });
  it('records completion against the same planned task',async()=>{
    current.follow_ups=[{follow_up_id:'task-1',action_type:'customer_contact',planned_date:'2026-01-01',current:{action_status:'planned'},history:[]}];
    start();
    await screen.findByLabelText('Task');
    fireEvent.change(screen.getByLabelText('Task'),{target:{value:'task-1'}});
    expect(screen.getByLabelText('Action type').disabled).toBe(true);
    expect(screen.getByLabelText('Follow-up status').value).toBe('');
    fireEvent.change(screen.getByLabelText('Follow-up status'),{target:{value:'delivered'}});
    fireEvent.change(screen.getByLabelText('Actual event date'),{target:{value:'2026-01-02'}});
    fireEvent.change(screen.getByLabelText('Follow-up notes'),{target:{value:'Completed customer discussion'}});
    fireEvent.change(screen.getByLabelText('Recorded by'),{target:{value:'RM A'}});
    fireEvent.click(screen.getByRole('button',{name:'Record follow-up'}));
    await waitFor(()=>expect(api.followUp).toHaveBeenCalledWith('jan','task-1',{action_type:'customer_contact',action_status:'delivered',action_date:'2026-01-02',notes:'Completed customer discussion',recorded_by:'RM A',expected_version:1}));
  });
  it('preserves conflicted notes until explicit reload',async()=>{
    api.updateCase.mockRejectedValue(new ApiError('This case changed.',409,'review_conflict'));
    start();
    await screen.findByLabelText('Change reason');
    fireEvent.click(screen.getByRole('tab',{name:'Manage case'}));
    fireEvent.change(screen.getByLabelText('Change reason'),{target:{value:'Keep this draft'}});
    fireEvent.change(screen.getByLabelText('Changed by'),{target:{value:'Reviewer'}});
    fireEvent.click(screen.getByRole('button',{name:'Save case changes'}));
    await screen.findByRole('alert');
    expect(screen.getByLabelText('Change reason').value).toBe('Keep this draft');
    expect(screen.getByRole('button',{name:'Save case changes'}).closest('fieldset').disabled).toBe(true);
    current={...current,version:2,owner:'RM B'};
    fireEvent.click(screen.getByRole('button',{name:'Discard drafts and load latest case'}));
    await waitFor(()=>expect(screen.getByLabelText('Owner').value).toBe('RM B'));
    expect(screen.getByLabelText('Change reason').value).toBe('');
  });
  it('retains case drafts during navigation and keeps their original save version',async()=>{
    start();
    await screen.findByLabelText('Change reason');
    fireEvent.click(screen.getByRole('tab',{name:'Manage case'}));
    fireEvent.change(screen.getByLabelText('Change reason'),{target:{value:'Draft before navigation'}});
    fireEvent.change(screen.getByLabelText('Changed by'),{target:{value:'Reviewer'}});
    fireEvent.click(screen.getByRole('link',{name:'← Reviewed Customers'}));
    await screen.findByRole('link',{name:'Open case'});
    current.version=2;
    fireEvent.click(screen.getByRole('link',{name:'Open case'}));
    await screen.findByLabelText('Change reason');
    expect(screen.getByLabelText('Change reason').value).toBe('Draft before navigation');
    fireEvent.click(screen.getByRole('button',{name:'Save case changes'}));
    await waitFor(()=>expect(api.updateCase).toHaveBeenCalledWith('jan',expect.objectContaining({expected_version:1})));
  });

  it('retains independent task drafts when switching tasks and navigating away',async()=>{
    current.follow_ups=['a','b'].map(id=>({follow_up_id:id,action_type:'customer_contact',planned_date:'2026-01-01',current:{action_status:'planned'},history:[]}));
    start();await screen.findByLabelText('Task');
    fireEvent.change(screen.getByLabelText('Follow-up notes'),{target:{value:'New task draft'}});
    fireEvent.change(screen.getByLabelText('Task'),{target:{value:'a'}});
    expect(screen.getByLabelText('Follow-up status').value).toBe('');
    fireEvent.change(screen.getByLabelText('Follow-up notes'),{target:{value:'Task A draft'}});
    fireEvent.change(screen.getByLabelText('Follow-up status'),{target:{value:'attempted'}});
    fireEvent.change(screen.getByLabelText('Task'),{target:{value:'b'}});
    expect(screen.getByLabelText('Follow-up notes').value).toBe('');
    expect(screen.getByLabelText('Follow-up status').value).toBe('');
    fireEvent.change(screen.getByLabelText('Task'),{target:{value:'a'}});
    expect(screen.getByLabelText('Follow-up notes').value).toBe('Task A draft');
    expect(screen.getByLabelText('Follow-up status').value).toBe('attempted');
    fireEvent.click(screen.getByRole('link',{name:'← Reviewed Customers'}));
    await screen.findByRole('link',{name:'Open case'});fireEvent.click(screen.getByRole('link',{name:'Open case'}));
    await screen.findByLabelText('Task');
    expect(screen.getByLabelText('Follow-up notes').value).toBe('Task A draft');
    fireEvent.change(screen.getByLabelText('Task'),{target:{value:''}});
    expect(screen.getByLabelText('Follow-up notes').value).toBe('New task draft');
    expect(api.followUp).not.toHaveBeenCalled();
  });

  it('requires a deliberate outcome for existing tasks before saving',async()=>{
    current.follow_ups=[{follow_up_id:'a',action_type:'customer_contact',planned_date:'2026-01-01',current:{action_status:'planned'},history:[]}];
    start();await screen.findByLabelText('Task');
    fireEvent.change(screen.getByLabelText('Task'),{target:{value:'a'}});
    fireEvent.change(screen.getByLabelText('Actual event date'),{target:{value:'2026-01-02'}});
    fireEvent.change(screen.getByLabelText('Follow-up notes'),{target:{value:'No answer'}});
    fireEvent.change(screen.getByLabelText('Recorded by'),{target:{value:'RM A'}});
    fireEvent.click(screen.getByRole('button',{name:'Record follow-up'}));
    expect(api.followUp).not.toHaveBeenCalled();
    fireEvent.change(screen.getByLabelText('Follow-up status'),{target:{value:'attempted'}});
    fireEvent.click(screen.getByRole('button',{name:'Record follow-up'}));
    await waitFor(()=>expect(api.followUp).toHaveBeenCalledWith('jan','a',expect.objectContaining({action_status:'attempted',expected_version:1})));
  });

  it('discards only the chosen form while retaining the other form draft',async()=>{
    start();await screen.findByLabelText('Task');
    fireEvent.change(screen.getByLabelText('Follow-up notes'),{target:{value:'Contact draft'}});
    expect(screen.getByText('Unsaved follow-up changes')).toBeTruthy();
    fireEvent.click(screen.getByRole('tab',{name:'Manage case'}));
    fireEvent.change(screen.getByLabelText('Owner'),{target:{value:'Unwanted owner'}});
    expect(screen.getByText('Unsaved case changes')).toBeTruthy();
    fireEvent.click(screen.getByRole('button',{name:'Discard case changes'}));
    expect(screen.getByLabelText('Owner').value).toBe('RM A');
    fireEvent.click(screen.getByRole('tab',{name:'Record follow-up'}));
    expect(screen.getByLabelText('Follow-up notes').value).toBe('Contact draft');
    fireEvent.click(screen.getByRole('button',{name:'Discard follow-up changes'}));
    expect(screen.getByLabelText('Follow-up notes').value).toBe('');
    expect(screen.getByRole('button',{name:'Discard follow-up changes'}).disabled).toBe(true);
    expect(api.followUp).not.toHaveBeenCalled();expect(api.updateCase).not.toHaveBeenCalled();
  });

  it('keeps worklist filters, page and briefing selection on return and can clear filters',async()=>{
    api.cases.mockImplementation(async()=>({items:[structuredClone(current)],total:120}));
    start('/reviewed?status=open&owner=RM%20A&q=944&decision=prioritise&offset=50&pick=jan');
    await screen.findByRole('link',{name:'Open case'});fireEvent.click(screen.getByRole('link',{name:'Open case'}));
    await screen.findByRole('heading',{name:'Constructed company'});fireEvent.click(screen.getByRole('link',{name:'← Reviewed Customers'}));
    await screen.findByRole('link',{name:'Open case'});
    expect(screen.getByLabelText('Customer').value).toBe('944');
    expect(screen.getByLabelText('Case status').value).toBe('open');
    expect(screen.getByLabelText('Owner').value).toBe('RM A');
    expect(screen.getByRole('checkbox').checked).toBe(true);
    expect(api.cases).toHaveBeenLastCalledWith({q:'944',status:'open',owner:'RM A',decision:'prioritise',offset:50,limit:50});
    fireEvent.click(screen.getByRole('button',{name:'Clear filters'}));
    await waitFor(()=>expect(api.cases).toHaveBeenLastCalledWith({q:'',status:'',owner:'',decision:'',offset:0,limit:50}));
    expect(screen.getByRole('checkbox').checked).toBe(true);
  });

  it('retains case edits and advances their version after this session saves follow-up',async()=>{
    api.followUp.mockImplementation(async()=>({case:{...structuredClone(current),version:2}}));
    api.updateCase.mockImplementation(async(_id,body)=>({case:{...structuredClone(current),...body,version:3}}));
    start();await screen.findByLabelText('Task');fireEvent.click(screen.getByRole('tab',{name:'Manage case'}));
    fireEvent.change(screen.getByLabelText('Change reason'),{target:{value:'Reassign after contact'}});
    fireEvent.change(screen.getByLabelText('Changed by'),{target:{value:'Committee'}});
    fireEvent.click(screen.getByRole('tab',{name:'Record follow-up'}));
    fireEvent.change(screen.getByLabelText('Planned date'),{target:{value:'2026-11-10'}});
    fireEvent.change(screen.getByLabelText('Follow-up notes'),{target:{value:'Plan discussion'}});
    fireEvent.change(screen.getByLabelText('Recorded by'),{target:{value:'RM A'}});
    fireEvent.click(screen.getByRole('button',{name:'Record follow-up'}));
    await screen.findByText('Follow-up recorded. Its event history is preserved.');
    fireEvent.click(screen.getByRole('tab',{name:'Manage case'}));
    expect(screen.getByLabelText('Change reason').value).toBe('Reassign after contact');
    fireEvent.click(screen.getByRole('button',{name:'Save case changes'}));
    await waitFor(()=>expect(api.updateCase).toHaveBeenCalledWith('jan',expect.objectContaining({expected_version:2})));
  });

  it('supports keyboard switching between follow-up and case management',async()=>{
    start();await screen.findByLabelText('Task');
    const followup=screen.getByRole('tab',{name:'Record follow-up'});
    followup.focus();fireEvent.keyDown(followup,{key:'ArrowRight'});
    expect(screen.getByRole('tab',{name:'Manage case'}).getAttribute('aria-selected')).toBe('true');
    expect(screen.getByRole('button',{name:'Save case changes'})).toBeTruthy();
    fireEvent.keyDown(document.activeElement,{key:'Home'});
    expect(screen.getByRole('tab',{name:'Record follow-up'}).getAttribute('aria-selected')).toBe('true');
  });
});
