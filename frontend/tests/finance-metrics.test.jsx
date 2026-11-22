import React from 'react';
import { describe, expect, it } from 'vitest';
import { render, screen, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { PortfolioFinanceMetrics } from '../src/components/FinanceMetrics.jsx';
import FinancePerspective from '../src/components/FinancePerspective.jsx';
import { millions } from '../src/format.js';
import april from './fixtures/finance-april.json';

const NEGATIVE = 'Estimated relationship contribution is negative at the assumed cost; see cost sensitivity.';
const B_TEXT = "Fixed deposits don't cover waived transaction cost.";
const A_LABEL = 'Fee waiver condition not met';
const SIGN = 'The sign of these totals depends on both assumptions; both matter equally.';
const banned = [/loss/i, /minor/i, /positive under all|always positive/i, /\brobust/i, /\bresilient/i];
const sources = import.meta.glob('../src/**/*.{js,jsx}', { query:'?raw', import:'default', eager:true });
const FINANCE = { non_fd_balance_myr:18313.53, fd_balance_myr:0, estimated_monthly_fee_myr:0.2877666667, estimated_monthly_waiver_myr:25.6355666667 };

const customer = changes => Object.assign(structuredClone(april.customer.finance_metrics), changes);
const show = (metrics = april.customer.finance_metrics, finance = FINANCE) =>
  render(<MemoryRouter><FinancePerspective finance={finance} metrics={metrics} batch="april" cutoff="2024-04-30" /></MemoryRouter>);
const contributionBlock = () => screen.getByRole('group', { name:'Estimated monthly relationship contribution' });
const row = question => screen.getByText(question).closest('.yn');
const tableValues = section => [...section.querySelectorAll('tbody tr')].map(tr => [...tr.querySelectorAll('th,td')].map(c => c.textContent));

describe('Customer finance (Finance tab)', () => {
  it('shows contribution at stake with the monthly figure, beside and never multiplied by the risk', () => {
    const { container } = show();
    const block = contributionBlock();
    expect(within(block).getByText(/79\.92/)).toBeTruthy();
    expect(within(block).getByText(/26\.64 a month/)).toBeTruthy();
    expect(within(block).getByText('Shown beside the risk, never multiplied by it.')).toBeTruthy();
    expect(container.textContent).not.toContain('78.9%');  // The risk is in the header, not multiplied into this card.
    // Worked example: A and B both true; their texts sit in their own rows inside the contribution card.
    expect(within(row('Fee waiver deal kept?')).getByText('No')).toBeTruthy();
    expect(row('Fee waiver deal kept?').textContent).toContain(A_LABEL);
    expect(within(row('Do fixed deposit earnings cover the waived cost?')).getByText(B_TEXT)).toBeTruthy();
    expect(within(row('Do fixed deposit earnings cover the waived cost?')).getByText(/^Uncovered: RM\s?18\.23 a month\.$/)).toBeTruthy();
    expect(block.contains(row('Do fixed deposit earnings cover the waived cost?'))).toBe(true);
    // A and B are separate checks with their own amounts; no combined (25.64 + 18.23) figure.
    expect(row('Fee waiver deal kept?').textContent).toMatch(/25\.64/);
    expect(container.textContent).not.toMatch(/43\.87/);
    expect(container.textContent).not.toContain(NEGATIVE);
    for (const pattern of banned) expect(container.textContent).not.toMatch(pattern);
  });

  it('has no sensitivity tables on the customer tab and links to the Finance picture instead', () => {
    const { container } = show();
    expect(container.querySelectorAll('table')).toHaveLength(0);
    expect(container.querySelectorAll('details')).toHaveLength(0);
    expect(screen.getByRole('link', { name:/Finance picture/ }).getAttribute('href')).toBe('/finance?batch_id=april');
  });

  it('shows where the money sits, the fee-waiver condition against the tier threshold and the monthly breakdown', () => {
    show();
    const money = screen.getByRole('group', { name:'Where the money sits' });
    expect(within(money).getByText(/18,313\.53/)).toBeTruthy();
    expect(within(money).getByText('Operating 100%')).toBeTruthy();
    expect(within(money).getByText(/RM\s?0\.00 of RM\s?100,000\.00 required/)).toBeTruthy();
    expect(within(money).getByText(/fixed deposit needed for SME small/)).toBeTruthy();
    const breakdown = screen.getByRole('heading', { name:'Where the monthly figure comes from' }).closest('section');
    expect([...breakdown.querySelectorAll('.wf>span:first-child')].map(n => n.textContent))
      .toEqual(['Fee income', 'Assumed transaction cost', 'Fixed deposit earnings', 'Operating-balance earnings', 'Contribution a month']);
    expect(breakdown.textContent).toMatch(/-RM\s?18\.52/);
  });

  it('negative contribution with check B false shows the exact sentence and figure but no B text', () => {
    const metrics = customer({ contribution_monthly:-12.5, rar_3m:-37.5,
      fsl_a:{ status:'deal_kept', flagged:false, monthly:null }, fsl_b:{ status:'covered', flagged:false, monthly:null, shortfall:0, policy:false } });
    const { container } = show(metrics);
    expect(within(contributionBlock()).getByText(NEGATIVE)).toBeTruthy();
    expect(within(contributionBlock()).getByText(/12\.50 a month/)).toBeTruthy();
    expect(container.textContent).not.toContain(B_TEXT);
    expect(container.textContent).not.toContain('Uncovered');
    expect(container.textContent).not.toContain(A_LABEL);
    expect(within(row('Do fixed deposit earnings cover the waived cost?')).getByText('Yes')).toBeTruthy();
    for (const pattern of banned) expect(container.textContent).not.toMatch(pattern);
  });

  it('negative contribution with check B true shows the B text inside the contribution card', () => {
    const metrics = customer({ contribution_monthly:-12.5, rar_3m:-37.5, fsl_a:{ status:'deal_kept', flagged:false, monthly:null } });
    const { container } = show(metrics);
    expect(within(contributionBlock()).getByText(NEGATIVE)).toBeTruthy();
    expect(within(contributionBlock()).getByText(B_TEXT)).toBeTruthy();
    expect(container.textContent).not.toContain(A_LABEL);
  });

  it.each([
    ['A true, B false', { status:'deal_broken', flagged:true, monthly:25.6355666667 }, { status:'covered', flagged:false, monthly:null, shortfall:0, policy:false }, true, false],
    ['A false, B true', { status:'deal_kept', flagged:false, monthly:null }, april.customer.finance_metrics.fsl_b, false, true],
  ])('positive contribution with %s shows only the true checks', (_, fsl_a, fsl_b, aShown, bShown) => {
    const { container } = show(customer({ fsl_a, fsl_b }));
    const block = contributionBlock();
    expect(block.textContent.includes(A_LABEL)).toBe(aShown);
    expect(!!within(block).queryByText(B_TEXT)).toBe(bShown);
    expect(container.textContent.includes('Uncovered')).toBe(bShown);
    expect(container.textContent).not.toContain(NEGATIVE);
  });

  it('labels policy exemptions and keeps the B text off policy-exempt customers', () => {
    const metrics = customer({ tier_id:'CORP_XL', waiver_basis:'POLICY_EXEMPT', fd_threshold_myr:null, fsl_a:{ status:'policy_exemption', flagged:false, monthly:null },
      fsl_b:{ status:'policy', flagged:true, monthly:500, shortfall:500, policy:true } });
    const { container } = show(metrics);
    expect(within(row('Fee waiver deal kept?')).getByText('Policy exemption')).toBeTruthy();
    expect(within(row('Do fixed deposit earnings cover the waived cost?')).getByText('Policy exemption')).toBeTruthy();
    expect(container.textContent).not.toContain(B_TEXT);
    expect(container.textContent).not.toContain('Uncovered');
    expect(screen.getByText('Fee waiver by policy exemption')).toBeTruthy();
    expect(screen.queryByText(/required$/)).toBeNull();  // No progress bar for a policy exemption.
  });

  it('shows unavailable inputs as not provided, never as zero, with the backend reason', () => {
    const metrics = customer({ contribution_monthly:null, rar_3m:null, unavailable:['OPR not verified for this cutoff (verified rates end 10 Jul 2024)'],
      components:{ ...april.customer.finance_metrics.components, fd_earnings:null } });
    show(metrics);
    expect(within(contributionBlock()).getAllByText('Not provided').length).toBeGreaterThan(0);
    expect(screen.getByText('Not provided: OPR not verified for this cutoff (verified rates end 10 Jul 2024)')).toBeTruthy();
  });
});

describe('Finance picture (portfolio)', () => {
  it('formats totals in millions with a true minus sign', () => {
    expect([millions(-9508640), millions(878486), millions(0), millions(null)]).toEqual(['−RM9.51m', '+RM0.88m', 'RM0.00m', 'Not provided']);
  });

  it('shows deposit-condition and policy-exempt tiers as two cards, with the combined total secondary and checks never summed', () => {
    const { container } = render(<PortfolioFinanceMetrics metrics={april.portfolio} />);
    const fd = screen.getByRole('article', { name:'Tiers with a deposit condition' }), policy = screen.getByRole('article', { name:'Policy-exempt tiers' });
    expect(within(fd).getByText('+RM0.88m')).toBeTruthy();
    expect(within(policy).getByText('−RM6.84m')).toBeTruthy();
    expect(within(fd).getByText('SME small, SME medium, Corporate large')).toBeTruthy();
    expect(within(policy).getByText('Corporate extra-large, Government')).toBeTruthy();
    expect(within(policy).getByText(NEGATIVE)).toBeTruthy();
    expect(within(fd).queryByText(NEGATIVE)).toBeNull();
    expect(within(policy).getByText('Policy exemption: not checked')).toBeTruthy();
    // A and B are listed separately and never summed (deposit-condition: A 165 customers, B 314 customers).
    expect(fd.textContent).toMatch(/165 customers/);
    expect(fd.textContent).toMatch(/314 customers/);
    expect(container.textContent).not.toMatch(/479 customers/);
    const combined = container.querySelector('.finance-combined');
    expect(combined.textContent).toMatch(/^All customers combined: −RM5\.96m/);
    expect(fd.compareDocumentPosition(combined) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(screen.getByText(SIGN)).toBeTruthy();
    for (const pattern of banned) expect(container.textContent).not.toMatch(pattern);
  });

  it('shows both sensitivities side by side, same component and heading level, identical rows, always visible', () => {
    render(<PortfolioFinanceMetrics metrics={april.portfolio} />);
    const cost = screen.getByRole('region', { name:'If transaction cost is lower' }), premium = screen.getByRole('region', { name:'If deposits earn more or less' });
    expect(cost.parentElement).toBe(premium.parentElement);
    for (const table of [cost, premium]) {
      expect(table.closest('details')).toBeNull();
      expect(table.querySelector('h2')).toBeTruthy();
      expect(table.querySelectorAll('thead th')).toHaveLength(4);
      expect(table.querySelector('tbody tr:last-child').className).toBe('secondary-row');
    }
    expect(tableValues(cost).map(r => r[0])).toEqual(tableValues(premium).map(r => r[0]));
    expect([...cost.querySelectorAll('thead th')].map(th => th.textContent)).toEqual(['Cost ratio','1.0 (base)','0.75','0.5']);
    expect([...premium.querySelectorAll('thead th')].map(th => th.textContent)).toEqual(['Liquidity premium','0.0%','0.5% (base)','1.0%']);
    expect(tableValues(cost)).toEqual([
      ['Deposit-condition tiers','+RM0.88m','+RM2.84m','+RM4.79m'],
      ['Policy-exempt tiers','−RM6.84m','−RM2.42m','+RM2.00m'],
      ['All customers','−RM5.96m','+RM0.42m','+RM6.80m'],
    ]);
    expect(tableValues(premium)).toEqual([
      ['Deposit-condition tiers','−RM0.92m','+RM0.88m','+RM2.68m'],
      ['Policy-exempt tiers','−RM8.59m','−RM6.84m','−RM5.10m'],
      ['All customers','−RM9.51m','−RM5.96m','−RM2.42m'],
    ]);
  });
});

describe('Finance UI source rules', () => {
  it('never uses the word loss and never hard-codes the portfolio or customer figures', () => {
    expect(Object.keys(sources).length).toBeGreaterThan(10);
    for (const [file, text] of Object.entries(sources)) {
      expect(text, file).not.toMatch(/\bloss/i);
      for (const figure of ['9.51','5.96','2.42','0.92','0.88','2.68','2.84','4.79','6.84','79.92','26.64','18.23','100,000','100000']) expect(text.includes(figure), file + ' ' + figure).toBe(false);
    }
  });
});
