import React from 'react';
import { describe, expect, it } from 'vitest';
import { render, screen, within } from '@testing-library/react';
import { CustomerFinanceMetrics, PortfolioFinanceMetrics } from '../src/components/FinanceMetrics.jsx';
import FinancePerspective from '../src/components/FinancePerspective.jsx';
import { millions } from '../src/format.js';
import april from './fixtures/finance-april.json';

const NEGATIVE = 'Estimated relationship contribution is negative at the assumed cost; see cost sensitivity.';
const B_LABEL = "Deposits don't cover waived transaction cost";
const A_LABEL = 'Fee waiver condition not met';
const banned = [/loss/i, /minor/i, /positive under all|always positive/i];
const sources = import.meta.glob('../src/**/*.{js,jsx}', { query:'?raw', import:'default', eager:true });

const customer = changes => {
  const m = structuredClone(april.customer.finance_metrics);
  return Object.assign(m, changes);
};
const contributionBlock = () => screen.getByRole('group', { name:'Estimated monthly relationship contribution' });
const tableValues = section => [...section.querySelectorAll('tbody tr')].map(tr => [...tr.querySelectorAll('th,td')].map(c => c.textContent));

describe('Customer finance metrics (Finance tab)', () => {
  it('shows the worked example with contribution at stake beside, not multiplied into, the risk', () => {
    const { container } = render(<CustomerFinanceMetrics metrics={april.customer.finance_metrics} risk={april.customer.calibrated_risk} />);
    const stake = screen.getByRole('group', { name:'Risk and contribution at stake' });
    expect(within(stake).getByText('78.9%')).toBeTruthy();
    expect(within(stake).getByText(/79\.92/)).toBeTruthy();
    expect(within(contributionBlock()).getByText(/26\.64 a month/)).toBeTruthy();
    // Worked example: A and B are both true, and both labels sit beside the contribution figure.
    expect(within(contributionBlock()).getByText(B_LABEL)).toBeTruthy();
    expect(within(contributionBlock()).getByText(A_LABEL)).toBeTruthy();
    expect(container.textContent).not.toContain(NEGATIVE);
    // A and B are separate checks with their own amounts; no combined (25.64 + 18.23) figure.
    const a = screen.getByRole('article', { name:'Check A: fee waiver condition' }), b = screen.getByRole('article', { name:'Check B: deposits vs waived cost' });
    expect(a.textContent).toMatch(/25\.64/);
    expect(b.textContent).toMatch(/18\.23/);
    expect(container.textContent).not.toMatch(/43\.87/);
    expect(a.querySelector('h4').textContent).toBe('Check A · fee waiver condition');
    expect(b.querySelector('h4').textContent).toBe('Check B · deposits vs waived cost');
    for (const pattern of banned) expect(container.textContent).not.toMatch(pattern);
  });

  it('shows both sensitivities as equal, always-open tables with three backend columns', () => {
    const { container } = render(<CustomerFinanceMetrics metrics={april.customer.finance_metrics} risk={0.5} />);
    const cost = screen.getByRole('region', { name:'Cost ratio sensitivity' }), premium = screen.getByRole('region', { name:'Liquidity premium sensitivity' });
    for (const table of [cost, premium]) {
      expect(table.closest('details')).toBeNull();
      expect(table.querySelectorAll('thead th')).toHaveLength(4);
      expect(table.querySelectorAll('tbody tr')).toHaveLength(4);
      expect(table.querySelector('h3')).toBeTruthy();
    }
    expect(cost.parentElement).toBe(premium.parentElement);
    expect([...cost.querySelectorAll('thead th')].map(th => th.textContent)).toEqual(['Measure','1.0 (base)','0.75','0.5']);
    expect([...premium.querySelectorAll('thead th')].map(th => th.textContent)).toEqual(['Measure','0.0%','0.5% (base)','1.0%']);
    const contribution = tableValues(cost).find(row => row[0] === 'Contribution a month');
    expect(contribution.slice(1).map(v => v.replace(/[^\d.]/g, ''))).toEqual(['26.64','31.27','35.90']);
    expect(container.querySelectorAll('details')).toHaveLength(0);
  });

  it('negative contribution with check B false shows the sentence and figure but no B label', () => {
    const metrics = customer({ contribution_monthly:-12.5, rar_3m:-37.5,
      fsl_a:{ status:'deal_kept', flagged:false, monthly:null }, fsl_b:{ status:'covered', flagged:false, monthly:null, shortfall:0, policy:false } });
    const { container } = render(<CustomerFinanceMetrics metrics={metrics} risk={0.2} />);
    expect(within(contributionBlock()).getByText(NEGATIVE)).toBeTruthy();
    expect(within(contributionBlock()).getByText(/12\.50 a month/)).toBeTruthy();
    expect(container.textContent).not.toContain(B_LABEL);
    expect(container.textContent).not.toContain(A_LABEL);
    for (const pattern of banned) expect(container.textContent).not.toMatch(pattern);
  });

  it('negative contribution with check B true shows the B label beside the figure', () => {
    const metrics = customer({ contribution_monthly:-12.5, rar_3m:-37.5, fsl_a:{ status:'deal_kept', flagged:false, monthly:null } });
    const { container } = render(<CustomerFinanceMetrics metrics={metrics} risk={0.2} />);
    expect(within(contributionBlock()).getByText(NEGATIVE)).toBeTruthy();
    expect(within(contributionBlock()).getByText(B_LABEL)).toBeTruthy();
    expect(container.textContent).not.toContain(A_LABEL);
  });

  it.each([
    ['A true, B false', { status:'deal_broken', flagged:true, monthly:25.6355666667 }, { status:'covered', flagged:false, monthly:null, shortfall:0, policy:false }, true, false],
    ['A false, B true', { status:'deal_kept', flagged:false, monthly:null }, april.customer.finance_metrics.fsl_b, false, true],
  ])('positive contribution with %s lists only the true checks', (_, fsl_a, fsl_b, aShown, bShown) => {
    const { container } = render(<CustomerFinanceMetrics metrics={customer({ fsl_a, fsl_b })} risk={0.2} />);
    const block = contributionBlock();
    expect(!!within(block).queryByText(A_LABEL)).toBe(aShown);
    expect(!!within(block).queryByText(B_LABEL)).toBe(bShown);
    expect(container.textContent.includes(B_LABEL)).toBe(bShown);
    expect(container.textContent).not.toContain(NEGATIVE);
  });

  it('labels policy exemptions and keeps the B label off policy-exempt customers', () => {
    const metrics = customer({ tier_id:'CORP_XL', waiver_basis:'POLICY_EXEMPT', fsl_a:{ status:'policy_exemption', flagged:false, monthly:null },
      fsl_b:{ status:'policy', flagged:true, monthly:500, shortfall:500, policy:true } });
    const { container } = render(<CustomerFinanceMetrics metrics={metrics} risk={0.2} />);
    expect(within(screen.getByRole('article', { name:'Check A: fee waiver condition' })).getByText('Policy exemption')).toBeTruthy();
    expect(within(screen.getByRole('article', { name:'Check B: deposits vs waived cost' })).getByText('Policy')).toBeTruthy();
    expect(container.textContent).not.toContain(B_LABEL);
  });

  it('shows unavailable inputs as not provided, never as zero', () => {
    const metrics = customer({ contribution_monthly:null, rar_3m:null, unavailable:['fixed deposit balance missing'],
      components:{ ...april.customer.finance_metrics.components, fd_earnings:null } });
    render(<CustomerFinanceMetrics metrics={metrics} risk={0.2} />);
    expect(within(contributionBlock()).getByText('Not provided')).toBeTruthy();
    expect(screen.getByText('Not provided: fixed deposit balance missing')).toBeTruthy();
  });

  it('is part of the Finance perspective and absent without backend metrics', () => {
    const finance = { non_fd_balance_myr:1, fd_balance_myr:0, estimated_monthly_fee_myr:1, estimated_monthly_waiver_myr:1 };
    const { rerender } = render(<FinancePerspective finance={finance} metrics={april.customer.finance_metrics} risk={0.3} />);
    expect(screen.getByRole('heading', { name:'Relationship contribution (estimate)' })).toBeTruthy();
    rerender(<FinancePerspective finance={finance} />);
    expect(screen.queryByRole('heading', { name:'Relationship contribution (estimate)' })).toBeNull();
  });
});

describe('Portfolio finance metrics (Overview)', () => {
  it('formats totals in millions with a true minus sign', () => {
    expect([millions(-9508640), millions(878486), millions(0), millions(null)]).toEqual(['−RM9.51m', '+RM0.88m', 'RM0.00m', 'Not provided']);
  });

  it('shows FD-threshold and policy-exempt tiers separately, with the combined total secondary', () => {
    const { container } = render(<PortfolioFinanceMetrics metrics={april.portfolio} />);
    const fd = screen.getByRole('article', { name:'FD-threshold tiers' }), policy = screen.getByRole('article', { name:'Policy-exempt tiers' });
    expect(within(fd).getByText('+RM0.88m')).toBeTruthy();
    expect(within(policy).getByText('−RM6.84m')).toBeTruthy();
    expect(within(policy).getByText(NEGATIVE)).toBeTruthy();
    expect(within(fd).queryByText(NEGATIVE)).toBeNull();
    expect(within(policy).getByText('Policy exemption: not checked')).toBeTruthy();
    // A and B are listed separately and never summed (FD-threshold: A 165 customers, B 314 customers).
    expect(fd.textContent).toMatch(/165 customers/);
    expect(fd.textContent).toMatch(/314 customers/);
    expect(container.textContent).not.toMatch(/479 customers/);
    const combined = container.querySelector('.finance-combined');
    expect(combined.textContent).toMatch(/^All customers combined \(secondary\)/);
    expect(fd.compareDocumentPosition(combined) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(screen.getByText('The sign of these totals depends on both assumptions; both matter equally.')).toBeTruthy();
    for (const pattern of banned) expect(container.textContent).not.toMatch(pattern);
  });

  it('shows both sensitivities equally with the backend April figures', () => {
    render(<PortfolioFinanceMetrics metrics={april.portfolio} />);
    const cost = screen.getByRole('region', { name:'Cost ratio sensitivity' }), premium = screen.getByRole('region', { name:'Liquidity premium sensitivity' });
    expect(cost.parentElement).toBe(premium.parentElement);
    for (const table of [cost, premium]) {
      expect(table.closest('details')).toBeNull();
      expect(table.querySelector('h3')).toBeTruthy();
      expect(table.querySelectorAll('thead th')).toHaveLength(4);
    }
    expect([...cost.querySelectorAll('thead th')].map(th => th.textContent)).toEqual(['Group','1.0 (base)','0.75','0.5']);
    expect([...premium.querySelectorAll('thead th')].map(th => th.textContent)).toEqual(['Group','0.0%','0.5% (base)','1.0%']);
    expect(tableValues(cost)).toEqual([
      ['FD-threshold tiers','+RM0.88m','+RM2.84m','+RM4.79m'],
      ['Policy-exempt tiers','−RM6.84m','−RM2.42m','+RM2.00m'],
      ['All customers combined','−RM5.96m','+RM0.42m','+RM6.80m'],
    ]);
    expect(tableValues(premium)).toEqual([
      ['FD-threshold tiers','−RM0.92m','+RM0.88m','+RM2.68m'],
      ['Policy-exempt tiers','−RM8.59m','−RM6.84m','−RM5.10m'],
      ['All customers combined','−RM9.51m','−RM5.96m','−RM2.42m'],
    ]);
    for (const table of [cost, premium]) expect(table.querySelector('tbody tr:last-child').className).toBe('secondary-row');
  });
});

describe('Finance UI source rules', () => {
  it('never uses the word loss and never hard-codes the portfolio figures', () => {
    expect(Object.keys(sources).length).toBeGreaterThan(10);
    for (const [file, text] of Object.entries(sources)) {
      expect(text, file).not.toMatch(/\bloss/i);
      for (const figure of ['9.51','5.96','2.42','0.92','0.88','2.68','2.84','4.79','6.84','79.92','26.64']) expect(text.includes(figure), file + ' ' + figure).toBe(false);
    }
  });
});
