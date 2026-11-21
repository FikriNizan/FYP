import React from 'react';
import { describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, within } from '@testing-library/react';
import RateShock, { DEPOSIT_ONLY, KS_NOTE, PASS_THROUGH, SCOPE } from '../src/components/RateShock.jsx';
import { api } from '../src/api.js';
import pkg from './fixtures/opr-scenarios.json';

vi.mock('../src/api.js', () => ({ api: { scenarios: vi.fn() } }));
const source = import.meta.glob('../src/components/RateShock.jsx', { query:'?raw', import:'default', eager:true });
// Banned claims: no performance-change claims, no robustness/resilience claims, no "loss", no verdict colours.
const BANNED = [/\baccuracy\b/i, /\bF1\b/, /\bAP\b/, /\brecall\b/i, /\bprecision\b/i, /will fail/i, /\brobust/i, /\bresilient/i, /stable to OPR/i, /\bloss/i,
  /main drivers/i, /significant/i, /p-value(?!s, because)/i, /\bminor\b/i, /healthy/i];

async function show(payload) {
  api.scenarios.mockResolvedValue(payload);
  const view = render(<RateShock />);
  if (payload.state === 'ready') await screen.findByRole('heading', { name:'What was assumed?' });
  return view;
}
const severe = pkg.scenarios.find(s => s.id === 'severe');

describe('Rate-shock what-if (m7-opr-2 package)', () => {
  it('answers the three questions in order and ends with the scope note and the approved sentences', async () => {
    const { container } = await show(pkg);
    const headings = [...container.querySelectorAll('h2')].map(h => h.textContent);
    expect(headings).toEqual(['What was assumed?', 'What changed in deposits?', 'What changed in model output and workload?', 'Which inputs moved?']);
    const scope = screen.getByRole('region', { name:'Scope' });
    expect(within(scope).getByText(SCOPE)).toBeTruthy();
    expect(SCOPE).toBe('Performance not evaluated: hypothetical outcomes are unavailable.');
    expect(within(scope).getByText(DEPOSIT_ONLY)).toBeTruthy();
    expect(within(scope).getByText(PASS_THROUGH)).toBeTruthy();
    expect(DEPOSIT_ONLY).toBe(pkg.note);
    expect(container.querySelectorAll('details')).toHaveLength(1);  // One "Technical detail" disclosure only.
    expect(container.querySelector('details summary').textContent).toBe('Technical detail');
  });

  it('shows customers assigned to leave beside those actually affected, with the denominator sentence', async () => {
    await show(pkg);
    const deposits = screen.getByRole('heading', { name:'What changed in deposits?' }).closest('section');
    const bars = within(deposits).getByRole('img');
    for (const s of pkg.scenarios) expect(bars.getAttribute('aria-label')).toContain(`${s.label}: ${s.assigned_exit_customers} assigned, ${s.exit_affected_customers} actually affected`);
    expect(within(deposits).getByText('Assigned to leave at maturity')).toBeTruthy();
    expect(within(deposits).getByText('Actually affected in the window')).toBeTruthy();
    expect(deposits.textContent).toContain(`a seeded share of the ${pkg.scenarios[0].cohort_size} customers with a fixed deposit in January`);
  });

  it('shows output and workload from the package, with flagged bars from zero to all customers', async () => {
    const { container } = await show(pkg);
    const output = screen.getByRole('heading', { name:'What changed in model output and workload?' }).closest('section');
    const p = severe.prediction_change, customers = p.risk.reference_available;
    expect(within(output).getByText('Customers flagged for review').nextSibling.textContent).toBe(String(p.flagged));
    expect(within(output).getByText('Customers moving into or out of review').nextSibling.textContent).toBe(String(p.crossed_into_review + p.crossed_out_of_review));
    expect(within(output).getByText('Customers whose score changed at all').nextSibling.textContent).toBe(String(severe.customers_score_changed));
    const widths = [...output.querySelectorAll('.fbar .t i')].map(i => i.style.width);
    expect(widths).toEqual(pkg.scenarios.map(s => (s.prediction_change.flagged / customers * 100) + '%'));
    fireEvent.click(screen.getByRole('button', { name:/^Mild/ }));
    expect(within(output).getByText('Customers whose score changed at all').nextSibling.textContent)
      .toBe(String(pkg.scenarios.find(s => s.id === 'mild').customers_score_changed));
    expect(container.querySelector('.ok, .healthy, .verdict')).toBeNull();
  });

  it('describes input shifts in words, with PSI/KS, the paired no-p-value reason and coverage only in Technical detail', async () => {
    await show(pkg);
    const inputs = screen.getByRole('heading', { name:'Which inputs moved?' }).closest('section');
    const changed = [...new Set(pkg.scenarios.flatMap(s => s.changed_features))];
    expect(inputs.querySelectorAll('.inrow')).toHaveLength(changed.length);
    for (const word of inputs.querySelectorAll('.inrow .word')) expect(['No', 'Little', 'Moderate', 'Large']).toContain(word.textContent);
    expect([...inputs.querySelectorAll('.inrow>span:first-child')].map(n => n.textContent)).toEqual(changed.sort().map(name => pkg.feature_labels[name]));
    const tech = inputs.querySelector('details');
    expect(tech.textContent).toContain(KS_NOTE);
    expect(tech.textContent).toContain(severe.input_drift.fd_balance_weighted_offer_rate.psi.toFixed(4));
    const rate = severe.input_drift.fd_balance_weighted_offer_rate;
    expect(tech.textContent).toContain(`compared on ${rate.reference_available} reference customers`);
    expect(tech.textContent).toContain(`${rate.current_available} (severe)`);
    expect([...inputs.childNodes].filter(n => n !== tech).map(n => n.textContent).join(' ')).not.toMatch(/PSI|KS\b/);
  });

  it('never invents figures when the package is missing or fails its checks', async () => {
    const { container, unmount } = await show({ state:'not_generated' });
    expect(await screen.findByText(/Not calculated\./)).toBeTruthy();
    expect(container.querySelector('table')).toBeNull();
    unmount();
    const invalid = await show({ state:'invalid' });
    expect(await screen.findByText(/failed its integrity checks/)).toBeTruthy();
    expect(invalid.container.querySelector('table')).toBeNull();
  });

  it('contains no performance, robustness or loss claims in the page or its source', async () => {
    const { container } = await show(pkg);
    fireEvent.click(container.querySelector('details summary'));
    const texts = [container.textContent, ...Object.values(source)];
    expect(Object.keys(source)).toHaveLength(1);
    for (const text of texts) for (const pattern of BANNED) expect(text).not.toMatch(pattern);
  });
});
