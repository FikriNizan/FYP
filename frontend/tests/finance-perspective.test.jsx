import React from 'react';
import { describe, expect, it } from 'vitest';
import { render, screen, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import FinancePerspective from '../src/components/FinancePerspective.jsx';
import { balanceShares, relativeEstimateWidths } from '../src/presentation.js';

describe('Finance display calculations',()=>{
  it('rounds complementary shares to a total of 100.0 and keeps a zero balance',()=>{
    for(const pair of [[1,2],[1250000,480000],[2016997.13,0],[0,10]]) {
      const shares=balanceShares(...pair);
      expect((shares.operating+shares.deposit).toFixed(1)).toBe('100.0');
    }
    expect(balanceShares(2016997.13,0)).toEqual({operating:100,deposit:0});
  });
  it.each([[null,10],[10,null],[0,0],[-1,10]])('does not calculate a split for %s and %s',(a,b)=>{
    expect(balanceShares(a,b)).toBeNull();
  });
  it('compares estimates only when both exist and the larger is positive',()=>{
    expect(relativeEstimateWidths(null,0)).toBeNull();
    expect(relativeEstimateWidths(0,0)).toBeNull();
    expect(relativeEstimateWidths(0,50)).toEqual({fee:0,waiver:100});
    expect(relativeEstimateWidths(100,25)).toEqual({fee:100,waiver:25});
  });
});

describe('Finance perspective',()=>{
  const show=finance=>render(<MemoryRouter><FinancePerspective finance={finance} cutoff="2024-02-29" batch="feb" /></MemoryRouter>);
  it('preserves customer 944 missing fees and zero fixed deposits and waivers within one section',()=>{
    const {container}=show({non_fd_balance_myr:2016997.13,fd_balance_myr:0,estimated_monthly_fee_myr:null,estimated_monthly_waiver_myr:0});
    const money=screen.getByRole('group',{name:'Where the money sits'});
    expect(within(money).getByText(/2,016,997.13/)).toBeTruthy();
    expect(within(money).getByText(/^RM\s?0\.00$/)).toBeTruthy();                 // Zero fixed deposits stay zero.
    expect(within(money).getByRole('img',{name:'Operating 100.0 percent, fixed deposit 0.0 percent'})).toBeTruthy();
    expect(screen.getByText(/Waived fees: RM\s?0\.00 a month\./)).toBeTruthy();   // Zero waivers stay zero.
    expect(screen.getByText('Relationship contribution is not provided for this assessment.')).toBeTruthy();
    expect(container.textContent).not.toMatch(/Fee income/);                          // Missing fees are never shown as RM0.00.
  });
  it.each([[null,50],[0,0]])('omits the allocation bar for balances %s and %s',(operating,deposit)=>{
    const {container}=show({non_fd_balance_myr:operating,fd_balance_myr:deposit,estimated_monthly_fee_myr:100,estimated_monthly_waiver_myr:0});
    expect(container.querySelector('.alloc')).toBeNull();
    if(operating===null) expect(within(screen.getByRole('group',{name:'Where the money sits'})).getByText('Not provided')).toBeTruthy();
  });
});
