import React from 'react';
import { describe, expect, it } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import FlowHistory, { recentVsUsual } from '../src/components/FlowHistory.jsx';
import Signals from '../src/components/Signals.jsx';
import { driverValue } from '../src/format.js';

const nb = text => text.replace(/ /g, ' ');
const value = (feature, v) => nb(driverValue({ feature, value: v }));

describe('Signals: unit-aware values', () => {
  it('shows counts as whole numbers with a unit, rates as %, money as RM', () => {
    expect(value('inbound_count_mean_12m', 1007.08)).toBe('1,007 collections a month');
    expect(value('session_transactions_mean_3m', 0)).toBe('0 per session');
    expect(value('active_fd_count', 2)).toBe('2 active fixed deposits');
    expect(value('combined_zero_months_3m', 1)).toBe('1 of the last 3 months with none');
    expect(value('login_failure_rate_3m', 0.571)).toBe('57.1%');
    expect(value('passive_session_rate_3m', 1)).toBe('100.0%');
    expect(value('inbound_share_3m', 0.317)).toBe('31.7%');
    expect(value('non_fd_balance_myr', 72721.7)).toBe('RM 72,721.70');
    expect(value('combined_flow_mean_3m_myr', 34309.94)).toBe('RM 34,309.94 a month');
    expect(value('combined_flow_ratio_3m_to_12m', 0.0676)).toBe('6.76% of the 12-month average');
    expect(value('combined_flow_change_3m_vs_previous_3m', -0.42)).toBe('42.0% lower than the previous 3 months');
    expect(value('login_success_recency_days', 27)).toBe('27 days ago');
    expect(value('inbound_recency_months', 1)).toBe('1 month ago');
    expect(value('tier_id', 'SME_M')).toBe('SME medium');
    expect(value('login_failure_rate_3m', null)).toBe('Not provided');
  });
});

describe('Chart takeaway', () => {
  const history = [{ snapshot_month:'2024-03-31', combined_flow_myr:20000, inbound_myr:5000, outbound_success_myr:15000 },
    { snapshot_month:'2024-04-30', combined_flow_myr:69150.12, inbound_myr:9150.12, outbound_success_myr:60000 }];
  it('leads with the 3-month average against the 12-month average, from the API values', () => {
    expect(nb(recentVsUsual(34309.94, 0.0676))).toBe('Last 3 months averaged RM 34,309.94 a month, 93.2% below the 12-month average.');
    expect(nb(recentVsUsual(120, 1.2))).toBe('Last 3 months averaged RM 120.00 a month, 20.0% above the 12-month average.');
    expect(recentVsUsual(null, 0.5)).toBeNull();
    const { container } = render(<FlowHistory history={history} baseline={507767.16} recent={34309.94} ratio={0.0676} cutoff="2024-04-30" />);
    const lead = container.querySelector('.chart-takeaway');
    expect(nb(lead.textContent)).toBe('Last 3 months averaged RM 34,309.94 a month, 93.2% below the 12-month average.');
    const secondary = lead.nextElementSibling;
    expect(secondary.className).toBe('muted');                                 // Month-on-month is secondary text now.
    expect(nb(secondary.textContent)).toBe('April 2024: RM 69,150.12. 245.8% higher than the previous recorded month.');
    fireEvent.change(screen.getByLabelText('Measure'), { target:{ value:'inbound_myr' } });
    expect(container.querySelectorAll('.chart-takeaway')).toHaveLength(1);     // Other measures keep the monthly takeaway.
    expect(container.textContent).not.toContain('Last 3 months averaged');
  });
  it('keeps the monthly takeaway as the lead when the API values are not provided', () => {
    const { container } = render(<FlowHistory history={history} baseline={507767.16} cutoff="2024-04-30" />);
    expect(nb(container.querySelector('.chart-takeaway').textContent)).toMatch(/^April 2024: RM 69,150\.12\./);
    expect(container.textContent).not.toContain('Last 3 months averaged');
  });
});

describe('Final tweaks: Signals subtitle and the flow-chart reading note', () => {
  it('adds the relative-influence sentence to the Signals subtitle (item 12)', () => {
    const { container } = render(<Signals customer={{ explanation:{ higher_risk_drivers:[], lower_risk_drivers:[] } }} />);
    expect(container.querySelector('h2 + p.muted').textContent)
      .toBe('What pushed this estimate up or down. Not proof of cause. Bar length shows relative influence among the signals shown.');
  });

  it('puts "How to read the lines" in a closed details element with the same text; legend and lines stay visible (item 13)', () => {
    const { container } = render(<FlowHistory history={[{ snapshot_month:'2024-03-31', combined_flow_myr:150 }]} baseline={200} />);
    const note = container.querySelector('details.chart-reference-note');
    expect(note.open).toBe(false);
    expect(note.querySelector('summary').textContent).toBe('How to read the lines');
    expect(note.querySelector('p').textContent).toBe('The dotted line is the trailing twelve-month average of combined flow. The red dashed line is the attrition reference: half of that average. The defined drop is a next-three-month average at or below this reference. Those months are not yet observed, so the line shows the reference level, not an outcome.');
    expect(container.querySelector('.baseline')).toBeTruthy();
    expect(container.querySelector('.reference-line')).toBeTruthy();
    for (const visible of [container.querySelector('svg.chart'), container.querySelector('.line-label.average'),
      container.querySelector('.line-label.attrition'), container.querySelector('.legend')]) {
      expect(visible).toBeTruthy();
      expect(note.contains(visible)).toBe(false);
    }
  });
});
