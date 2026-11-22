import React from 'react';
import { describe, expect, it } from 'vitest';
import { render, screen, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import Guide from '../src/pages/Guide.jsx';

const show = () => render(<MemoryRouter><Guide /></MemoryRouter>);
const section = name => { if (!document.querySelector('h1')) show(); return screen.getByRole('heading', { name }).closest('section'); };

describe('Guide (final tweaks, item 7)', () => {
  it('has the approved title, subtitle and sections in order', () => {
    const { container } = show();
    expect(screen.getByRole('heading', { level:1 }).textContent).toBe('How to use this workspace');
    expect(screen.getByText('One meeting each month: see who is flagged, decide, then follow up.')).toBeTruthy();
    expect([...container.querySelectorAll('h2')].map(h => h.textContent)).toEqual(['The monthly workflow', 'Four words to know', 'Good to remember',
      'A lower score later never erases a decision', 'For data owners: reading Monitoring']);
  });

  it('shows four numbered workflow steps with icons and page badges', () => {
    const steps = [...section('The monthly workflow').querySelectorAll('.g-step')];
    expect(steps.map(s => [s.querySelector('.g-num').textContent, s.querySelector('h3').textContent, s.querySelector('p').textContent, s.querySelector('.badge').textContent])).toEqual([
      ['1', 'Choose the month', 'See how many customers are flagged and who is still waiting for review.', 'Overview'],
      ['2', 'Review a customer', 'Summary, Operations and Finance show why they were flagged.', 'Customer review'],
      ['3', 'Record the decision', 'Prioritise for RM, Monitor or No immediate action, with a reason.', 'Record committee decision'],
      ['4', 'Follow up', 'For prioritised customers, print the RM briefing, then log each follow-up.', 'Reviewed Customers']]);
    for (const step of steps) expect(step.querySelector('.round svg.icon path, .round svg.icon rect, .round svg.icon circle')).toBeTruthy();
  });

  it('defines the four words, with contribution at stake named as Revenue at Risk', () => {
    const terms = [...section('Four words to know').querySelectorAll('.g-term')].map(t => [t.querySelector('h3').textContent, t.querySelector('p').textContent]);
    expect(terms).toEqual([
      ['Predicted risk', "The model's estimated chance of a volume drop in the next three months."],
      ['Flagged', 'Risk is above the review line. A prompt to look, not a verdict.'],
      ['Volume drop', 'Transaction flow falls to half or less of its usual level. The account may stay open.'],
      ['Contribution at stake', 'What the relationship earns the bank over three months. An estimate, not a forecast. Called Revenue at Risk (RaR) in the project report.']]);
  });

  it('keeps three reminders and the labelled decision example', () => {
    expect([...section('Good to remember').querySelectorAll('.hint')].map(h => h.textContent)).toEqual([
      "Signals explain the score. They don't prove the cause.", 'Items marked AI are drafts for your review.', 'RM figures are estimates based on stated assumptions.']);
    const example = section('A lower score later never erases a decision');
    expect([...example.querySelectorAll('.context-card')].map(c => c.textContent)).toEqual([
      'January review70.0%Committee: Prioritise for RM', 'February assessment18.0%The January decision stays. The case closes only when the team closes it.']);
    expect(within(example).getByText('Example values for explanation only.')).toBeTruthy();
  });

  it('explains Monitoring in five points, links to it and keeps the fallback command closed', () => {
    const monitoring = section('For data owners: reading Monitoring');
    expect(within(monitoring).getByRole('link', { name:'Open Monitoring →' }).getAttribute('href')).toBe('/monitoring');
    expect([...monitoring.querySelectorAll('.hint b')].map(b => b.textContent)).toEqual(['Outcomes check themselves.',
      'The grid compares flags with real volume drops:', 'Follow-ups count', 'Input movement', 'Rate-shock what-if']);
    const fallback = monitoring.querySelector('details');
    expect(fallback.open).toBe(false);
    expect(fallback.querySelector('summary').textContent).toBe('Administrator fallback');
    expect(fallback.querySelector('code').textContent).toBe('python -m flask --app app load-outcomes --batch-id BATCH --observed-through YYYY-MM-DD');
  });

  it('drops the old method paragraphs and the identity-or-access sentence (kept in docs/USER_GUIDE.md)', () => {
    const { container } = show();
    expect(container.textContent).not.toMatch(/identity or access|Four different questions|From evidence to follow-up|Brier|Demo preview/);
  });
});
