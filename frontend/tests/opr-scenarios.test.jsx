import React from 'react';
import { describe, expect, it, vi } from 'vitest';
import { render, screen, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import ResearchPreview, { DEPOSIT_ONLY, DRIFT_CAPTION } from '../src/pages/ResearchPreview.jsx';
import { api } from '../src/api.js';
import pkg from './fixtures/opr-scenarios.json';

vi.mock('../src/api.js', () => ({ api: { scenarios: vi.fn() } }));
const source = import.meta.glob('../src/pages/ResearchPreview.jsx', { query:'?raw', import:'default', eager:true });
// Banned claims (Milestone 7): no performance-change claims, no robustness claims, no "loss".
const BANNED = [/\baccuracy\b/i, /\bF1\b/, /\bAP\b/, /\brecall\b/i, /\bprecision\b/i, /will fail/i, /\brobust/i, /\bresilient/i, /stable to OPR/i, /\bloss/i];

async function show(payload) {
  api.scenarios.mockResolvedValue(payload);
  const view = render(<MemoryRouter><ResearchPreview /></MemoryRouter>);
  await screen.findByRole('heading', { name:'OPR stress demonstration' });
  return view;
}

describe('OPR stress demonstration', () => {
  it('keeps the three outputs separate and says performance is not computed', async () => {
    const { container } = await show(pkg);
    for (const name of ['Assumption register', '1. Input drift', '2. Prediction change', '3. Performance change'])
      expect(await screen.findByRole('heading', { name })).toBeTruthy();
    const performance = screen.getByRole('region', { name:'3. Performance change' });
    expect(performance.textContent).toMatch(/^3\. Performance changeNot computed\./);
    expect(performance.querySelector('table')).toBeNull();
    expect(container.textContent).toContain(DEPOSIT_ONLY);
    expect(container.textContent).toContain(DRIFT_CAPTION);
    expect(container.textContent).toContain('Scenario scores are hypothetical and are not saved predictions.');
  });

  it('shows the changed inputs, unchanged-by-design count and figures from the package', async () => {
    await show(pkg);
    const shocked = pkg.scenarios.filter(s => s.id !== 'no_shock');
    const changed = [...new Set(shocked.flatMap(s => s.changed_features))];
    const total = Object.keys(pkg.scenarios[0].input_drift).length;
    const input = screen.getByRole('region', { name:'1. Input drift' });
    expect(input.textContent).toContain(`${changed.length} of ${total} predictors change; ${total - changed.length} are unchanged by design.`);
    expect(input.querySelectorAll('tbody tr')).toHaveLength(changed.length);
    const severe = shocked.find(s => s.id === 'severe');
    expect(input.textContent).toContain(severe.input_drift.fd_balance_weighted_offer_rate.psi.toFixed(4));
    const prediction = screen.getByRole('region', { name:'2. Prediction change' });
    const rows = [...prediction.querySelectorAll('tbody tr')];
    expect(rows.map(r => r.querySelector('th').textContent)).toEqual(pkg.scenarios.map(s => s.label));
    expect(rows[2].textContent).toContain(severe.prediction_change.risk.psi.toFixed(5));
    expect(within(prediction).getByText(`Flagged (saved: ${pkg.scenarios[0].prediction_change.saved_flagged})`)).toBeTruthy();
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
    await screen.findByRole('heading', { name:'3. Performance change' });
    const texts = [container.textContent, ...Object.values(source)];
    expect(Object.keys(source)).toHaveLength(1);
    for (const text of texts) for (const pattern of BANNED) expect(text).not.toMatch(pattern);
  });
});
