import React from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, useNavigate } from 'react-router-dom';
import Briefing from '../src/pages/Briefing.jsx';
import { api, ApiError } from '../src/api.js';
import fixture from './fixtures/briefing.json';

vi.mock('../src/api.js',async original=>({...await original(),api:{briefing:vi.fn(),downloadBriefing:vi.fn()}}));
const deferred=()=>{let resolve,reject;const promise=new Promise((a,b)=>{resolve=a;reject=b;});return {promise,resolve,reject};};
const payload=(name='Selected company',id='case-a')=>{
  const data=structuredClone(fixture);
  data.items[0].name=name;data.items[0].case_id=id;
  data.snapshots[0].case_id=id;
  return data;
};
function Navigation() {
  const navigate=useNavigate();
  return <><button onClick={()=>navigate('/briefing?case_id=case-b&worklist=%3Fowner%3DRM%2BA')}>Change selection</button><Briefing /></>;
}
function start(query='?case_id=case-a') {
  return render(<MemoryRouter initialEntries={['/briefing'+query]}><Navigation /></MemoryRouter>);
}
let click;
beforeEach(()=>{
  vi.clearAllMocks();
  api.briefing.mockResolvedValue(payload());
  api.downloadBriefing.mockResolvedValue({blob:new Blob(['%PDF-1.7\nexample']),filename:'txb-rm-briefing.pdf'});
  vi.stubGlobal('URL',Object.assign(URL,{createObjectURL:vi.fn(()=>'blob:test-pdf'),revokeObjectURL:vi.fn()}));
  click=vi.spyOn(HTMLAnchorElement.prototype,'click').mockImplementation(()=>{});
});

describe('Briefing selection and direct PDF',()=>{
  it('deduplicates IDs in chosen order and downloads the selected preview snapshots',async()=>{
    const combined={items:[payload('Company B','case-b').items[0],payload('Company A','case-a').items[0]],snapshots:[payload('Company B','case-b').snapshots[0],payload('Company A','case-a').snapshots[0]]};
    api.briefing.mockResolvedValue(combined);
    start('?case_id=case-b&case_id=case-a&case_id=case-b&worklist=%3Fowner%3DRM%2BA');
    await screen.findByRole('heading',{name:'Company B'});
    expect(screen.getByRole('heading',{name:'Company A'})).toBeTruthy();
    expect(api.briefing).toHaveBeenCalledWith(['case-b','case-a']);
    expect(screen.getByRole('link',{name:'Choose cases'}).getAttribute('href')).toBe('/reviewed?owner=RM+A');
    fireEvent.click(screen.getByRole('button',{name:'Download PDF'}));
    await waitFor(()=>expect(click).toHaveBeenCalledOnce());
    expect(api.downloadBriefing).toHaveBeenCalledWith(['case-b','case-a'],combined.snapshots,expect.any(AbortSignal));
    expect(URL.createObjectURL).toHaveBeenCalledOnce();
  });

  it('hides earlier evidence and disables export throughout a changed selection loading state',async()=>{
    const next=deferred();api.briefing.mockResolvedValueOnce(payload()).mockReturnValueOnce(next.promise);
    start();await screen.findByRole('heading',{name:'Selected company'});
    fireEvent.click(screen.getByRole('button',{name:'Change selection'}));
    expect(screen.queryByRole('heading',{name:'Selected company'})).toBeNull();
    expect(screen.getByRole('button',{name:'Download PDF'}).disabled).toBe(true);
    expect(screen.getByRole('button',{name:'Print briefing'}).disabled).toBe(true);
    next.resolve(payload('New company','case-b'));
    await screen.findByRole('heading',{name:'New company'});
    expect(screen.getByRole('button',{name:'Download PDF'}).disabled).toBe(false);
  });

  it('never downloads an earlier selection even if its request finishes after navigation',async()=>{
    const download=deferred();api.downloadBriefing.mockReturnValue(download.promise);
    start();await screen.findByRole('heading',{name:'Selected company'});
    fireEvent.click(screen.getByRole('button',{name:'Download PDF'}));
    const signal=api.downloadBriefing.mock.calls[0][2];
    api.briefing.mockResolvedValue(payload('New company','case-b'));
    fireEvent.click(screen.getByRole('button',{name:'Change selection'}));
    await screen.findByRole('heading',{name:'New company'});
    expect(signal.aborted).toBe(true);
    download.resolve({blob:new Blob(['%PDF-1.7']),filename:'wrong.pdf'});
    await waitFor(()=>expect(screen.getByRole('button',{name:'Download PDF'}).disabled).toBe(false));
    expect(click).not.toHaveBeenCalled();
  });

  it('refreshes changed evidence and requires review before a retry can download',async()=>{
    const error=new ApiError('Saved evidence changed. Review the refreshed briefing before downloading.',409,'briefing_changed');
    error.briefing=payload('Updated company');error.briefing.snapshots[0].review_version++;
    api.downloadBriefing.mockRejectedValueOnce(error);
    start();await screen.findByRole('heading',{name:'Selected company'});
    fireEvent.click(screen.getByRole('button',{name:'Download PDF'}));
    await screen.findByRole('heading',{name:'Updated company'});
    expect(screen.getByRole('button',{name:'Download PDF'}).disabled).toBe(true);
    expect(click).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole('button',{name:'I have reviewed the updated briefing'}));
    fireEvent.click(screen.getByRole('button',{name:'Download PDF'}));
    await waitFor(()=>expect(click).toHaveBeenCalledOnce());
    expect(api.downloadBriefing.mock.calls[1][1]).toEqual(error.briefing.snapshots);
  });

  it.each([404,422])('clears a missing or ineligible preview after export rejects it (%s)',async status=>{
    api.downloadBriefing.mockRejectedValue(new ApiError('Selected case unavailable',status,'invalid_case'));
    start();await screen.findByRole('heading',{name:'Selected company'});
    fireEvent.click(screen.getByRole('button',{name:'Download PDF'}));
    await screen.findByRole('alert');
    expect(screen.queryByRole('heading',{name:'Selected company'})).toBeNull();
    expect(screen.getByRole('button',{name:'Print briefing'}).disabled).toBe(true);
    expect(click).not.toHaveBeenCalled();
  });

  it('retains the selection and permits retry after an export failure',async()=>{
    api.downloadBriefing.mockRejectedValueOnce(new ApiError('Export failed. Try again.',500,'internal_error'));
    start();await screen.findByRole('heading',{name:'Selected company'});
    fireEvent.click(screen.getByRole('button',{name:'Download PDF'}));
    await screen.findByRole('alert');
    expect(screen.getByRole('heading',{name:'Selected company'})).toBeTruthy();
    fireEvent.click(screen.getByRole('button',{name:'Download PDF'}));
    await waitFor(()=>expect(click).toHaveBeenCalledOnce());
    expect(api.downloadBriefing.mock.calls[1][0]).toEqual(['case-a']);
  });

  it('does not let a late preview response replace the newer selected case',async()=>{
    const earlier=deferred();
    api.briefing.mockReturnValueOnce(earlier.promise).mockResolvedValueOnce(payload('New company','case-b'));
    start();fireEvent.click(screen.getByRole('button',{name:'Change selection'}));
    await screen.findByRole('heading',{name:'New company'});
    earlier.resolve(payload('Earlier company'));
    await waitFor(()=>expect(screen.queryByRole('heading',{name:'Earlier company'})).toBeNull());
    expect(screen.getByRole('heading',{name:'New company'})).toBeTruthy();
  });

  it('recovers a missing preview without losing the selected IDs or return context',async()=>{
    api.briefing.mockRejectedValueOnce(new ApiError('Case not found',404,'not_found'));
    start('?case_id=case-a&worklist=%3Fowner%3DRM%2BA');
    await screen.findByRole('alert');
    expect(screen.getByRole('button',{name:'Download PDF'}).disabled).toBe(true);
    fireEvent.click(screen.getByRole('button',{name:'Reload selected evidence'}));
    await screen.findByRole('heading',{name:'Selected company'});
    expect(api.briefing).toHaveBeenLastCalledWith(['case-a']);
    expect(screen.getByRole('link',{name:'Choose cases'}).getAttribute('href')).toBe('/reviewed?owner=RM+A');
  });

  it('also rechecks freshness before opening the print dialog',async()=>{
    const print=vi.spyOn(window,'print').mockImplementation(()=>{});
    const updated=payload('Updated company');updated.snapshots[0].case_version++;
    api.briefing.mockResolvedValueOnce(payload()).mockResolvedValue(updated);
    start();await screen.findByRole('heading',{name:'Selected company'});
    fireEvent.click(screen.getByRole('button',{name:'Print briefing'}));
    await screen.findByRole('heading',{name:'Updated company'});
    expect(print).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole('button',{name:'I have reviewed the updated briefing'}));
    fireEvent.click(screen.getByRole('button',{name:'Print briefing'}));
    await waitFor(()=>expect(print).toHaveBeenCalledOnce());
    print.mockRestore();
  });

  it.each(['','?'+Array.from({length:11},(_,i)=>'case_id=case-'+i).join('&')])('blocks invalid selection %s',async query=>{
    start(query);
    expect(screen.getByRole('button',{name:'Download PDF'}).disabled).toBe(true);
    expect(api.briefing).not.toHaveBeenCalled();
  });
});
