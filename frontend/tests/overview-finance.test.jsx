import React from 'react';
import { describe, expect, it, vi } from 'vitest';
import { render, screen, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import Overview from '../src/pages/Overview.jsx';
import { api } from '../src/api.js';

vi.mock('../src/api.js', () => ({ api: { summary:vi.fn(), customers:vi.fn() } }));

describe('Overview financial context', () => {
  it('shows complete flagged coverage before the queue while preserving missing totals and zeros', async () => {
    const keys=['non_fd_balance_myr','fd_balance_myr','estimated_monthly_fee_myr','estimated_monthly_waiver_myr'];
    api.summary.mockResolvedValue({batch:{batch_id:'saved',cutoff_month:'2024-02-29'},population:10,flagged:4,below_threshold:6,flagged_review_counts:{awaiting_review:4,prioritise:0},finance:Object.fromEntries(keys.map((key,i)=>['flagged_'+key,{total:i===2 ? null : 0,records:i===3 ? 0 : 4,records_with_value:i===0 ? 3 : 0}]))});
    api.customers.mockResolvedValue({total:0,items:[]});
    render(<MemoryRouter><Overview batch="saved" revision={0} /></MemoryRouter>);
    const section=await screen.findByRole('region',{name:'Financial context for flagged customers'});
    expect(section.closest('details')).toBeNull();
    expect(within(section).getByText('Totals across the 4 flagged customers in this assessment.')).toBeTruthy();
    expect(within(section).getByText('3 of 4 records available')).toBeTruthy();
    expect(within(section).getByText('0 of 0 records available')).toBeTruthy();
    const cards=section.querySelectorAll('article');
    expect(cards).toHaveLength(4);
    expect(within(cards[2]).getByText('Not provided')).toBeTruthy();
    expect(within(cards[1]).getByText(/0\.00/)).toBeTruthy();
    expect(cards[0].querySelector('.coverage-track').getAttribute('aria-hidden')).toBe('true');
    expect(cards[0].querySelector('.coverage-track i').style.width).toBe('75%');
    expect(cards[3].querySelector('.coverage-track i').style.width).toBe('0%');
    const queue=screen.getByRole('heading',{name:'Customer review queue'}).closest('section');
    expect(section.nextElementSibling).toBe(queue);
  });
});
