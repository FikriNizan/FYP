import React from 'react';
import { describe, expect, it, vi } from 'vitest';
import { render, screen, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import Overview from '../src/pages/Overview.jsx';
import FinancePicture from '../src/pages/FinancePicture.jsx';
import { api } from '../src/api.js';
import april from './fixtures/finance-april.json';

vi.mock('../src/api.js', () => ({ api: { summary:vi.fn(), customers:vi.fn() } }));
const summary = changes => ({ batch:{ batch_id:'saved', cutoff_month:'2024-04-30' }, population:1000, flagged:206, flagged_share:.206, below_threshold:794,
  needs_committee_review:142, flagged_review_counts:{ awaiting_review:150, prioritise:0 },
  flagged_balances:{ total:61400000, fixed_deposits:43000000, operating:18400000, records:206 }, finance_metrics:april.portfolio, ...changes });

describe('Overview tiles and queue', () => {
  it('shows four tiles from the API, the deposits tile linking to the finance picture, and no Revenue at Risk section', async () => {
    api.summary.mockResolvedValue(summary());
    api.customers.mockResolvedValue({ total:0, items:[] });
    const { container } = render(<MemoryRouter><Overview batch="saved" revision={0} /></MemoryRouter>);
    const tiles = await screen.findByRole('group', { name:'Assessment at a glance' });
    expect([...tiles.children].map(t => t.querySelector('span').textContent))
      .toEqual(['Customers assessed', 'Flagged for review', 'Flagged, awaiting review', 'Deposits held by flagged customers']);
    expect(within(tiles).getByText('1,000')).toBeTruthy();
    expect(within(tiles).getByText('206')).toBeTruthy();
    expect(within(tiles).getByText('20.6% of customers')).toBeTruthy();
    expect(within(tiles).getByText('142')).toBeTruthy();
    const deposits = tiles.children[3];
    expect(deposits.tagName).toBe('A');
    expect(deposits.getAttribute('href')).toBe('/finance?batch_id=saved');
    expect(within(deposits).getByText('RM61.40m')).toBeTruthy();                                   // Fixed deposits + operating, from the API.
    expect(within(deposits).getByText('Fixed deposits RM43.00m · Operating RM18.40m')).toBeTruthy();
    // Revenue at Risk, fee subsidy and the by-tier table now live on the Finance picture, not here.
    expect(screen.queryByRole('region', { name:/Revenue at Risk/ })).toBeNull();
    expect(container.textContent).not.toMatch(/Revenue at Risk|By tier|sensitivity|Contribution at stake/i);
    expect(container.querySelectorAll('table')).toHaveLength(1);
    expect(screen.getByRole('heading', { name:'Review queue' })).toBeTruthy();
    expect(screen.getByRole('group', { name:'Customer filter' })).toBeTruthy();
  });

  it('shows missing balances as not provided, never as zero', async () => {
    api.summary.mockResolvedValue(summary({ flagged_balances:{ total:null, fixed_deposits:null, operating:null, records:206 } }));
    api.customers.mockResolvedValue({ total:0, items:[] });
    render(<MemoryRouter><Overview batch="saved" revision={0} /></MemoryRouter>);
    const tiles = await screen.findByRole('group', { name:'Assessment at a glance' });
    expect(within(tiles.children[3]).getByText('Not provided')).toBeTruthy();
    expect(within(tiles.children[3]).getByText('Fixed deposits Not provided · Operating Not provided')).toBeTruthy();
  });
});

describe('Finance picture page', () => {
  it('shows the definition, both cards and both tables with the exact caption', async () => {
    api.summary.mockResolvedValue(summary());
    render(<MemoryRouter><FinancePicture batch="saved" revision={0} /></MemoryRouter>);
    expect(await screen.findByRole('heading', { name:'Finance picture' })).toBeTruthy();
    expect(screen.getByText(/Contribution at stake = three months of estimated fees, minus assumed transaction cost, plus deposit earnings\. An estimate, not audited profit\./)).toBeTruthy();
    expect(screen.getByRole('article', { name:'Tiers with a deposit condition' })).toBeTruthy();
    expect(screen.getByRole('article', { name:'Policy-exempt tiers' })).toBeTruthy();
    expect(screen.getByText('The sign of these totals depends on both assumptions; both matter equally.')).toBeTruthy();
    expect(screen.queryByText(/verified OPR rates end/)).toBeNull();
  });

  it('states the fail-closed OPR reason when the cutoff is after the verified table', async () => {
    api.summary.mockResolvedValue(summary({ batch:{ batch_id:'saved', cutoff_month:'2024-07-31' }, finance_metrics:{ ...april.portfolio, opr_verified:false } }));
    render(<MemoryRouter><FinancePicture batch="saved" revision={0} /></MemoryRouter>);
    expect(await screen.findByText('Finance contribution is unavailable for this assessment: verified OPR rates end 10 Jul 2024.')).toBeTruthy();
  });
});
