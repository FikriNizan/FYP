import React from 'react';
import { describe, expect, it } from 'vitest';
import { render, screen, within } from '@testing-library/react';
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
  it('preserves customer 944 missing fees and zero fixed deposits and waivers within one section',()=>{
    const {container}=render(<FinancePerspective finance={{non_fd_balance_myr:2016997.13,fd_balance_myr:0,estimated_monthly_fee_myr:null,estimated_monthly_waiver_myr:0}} />);
    const section=screen.getByRole('heading',{name:'Finance perspective'}).closest('section');
    expect(within(section).getAllByText('Not provided')).toHaveLength(1);
    expect(within(section).getAllByText(/0.00/)).toHaveLength(2);
    expect(within(section).getByText(/2,016,997.13/)).toBeTruthy();
    expect(within(section).getByRole('img',{name:'Operating 100.0 percent, fixed deposit 0.0 percent'})).toBeTruthy();
    expect(container.querySelector('.finance-card.is-missing h3').textContent).toBe('Estimated monthly fees');
    expect(screen.getByText('No value was supplied for this assessment.')).toBeTruthy();
    expect(container.querySelector('.estimate .coverage-track')).toBeNull();
  });
  it.each([[null,50],[0,0]])('omits the split panel for balances %s and %s',(operating,deposit)=>{
    const {container}=render(<FinancePerspective finance={{non_fd_balance_myr:operating,fd_balance_myr:deposit,estimated_monthly_fee_myr:100,estimated_monthly_waiver_myr:0}} />);
    expect(container.querySelector('.balance-split-panel')).toBeNull();
    const bars=container.querySelectorAll('.estimate .coverage-track i');
    expect(bars[0].style.width).toBe('100%');
    expect(bars[1].style.width).toBe('0%');
    if(operating===null) expect(screen.getByText('Share not shown while the other balance is not provided')).toBeTruthy();
  });
});
