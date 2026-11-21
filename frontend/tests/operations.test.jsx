import React from 'react';
import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import OperationsPerspective, { LEVEL_RULE } from '../src/components/OperationsPerspective.jsx';
import { ratioWidth } from '../src/presentation.js';

const level = (value, level, p75 = .2) => ({ value, level, p75, customers: 1000 });

describe('Operations evidence',()=>{
  it('clamps display bars without changing the displayed rates or amounts',()=>{
    expect(ratioWidth(200,100)).toBe(100);
    expect(ratioWidth(-20,100)).toBe(0);
    expect(ratioWidth(null,100)).toBe(0);
    expect(ratioWidth(100,0)).toBe(0);
    const {container}=render(<OperationsPerspective cutoff="2024-02-29" operations={{combined_flow_mean_12m_myr:100,combined_flow_mean_3m_myr:200,login_failure_rate_3m:0,outbound_failure_rate_3m:1.2,outbound_bank_failure_rate_3m:null}} />);
    expect(screen.getByRole('heading',{name:'Operations perspective'})).toBeTruthy();
    expect(screen.getByText('100.0% higher')).toBeTruthy();
    expect(screen.getByText('0.0%')).toBeTruthy();
    expect(screen.getByText('120.0%')).toBeTruthy();
    expect(container.querySelector('.activity-row.recent i').style.width).toBe('100%');
    // Order: sign-in failures, sessions without transactions, outgoing payment failures, failures on our side.
    const tracks=container.querySelectorAll('.service-track');
    expect(tracks[0].firstChild.style.width).toBe('0%');
    expect(tracks[2].firstChild.style.width).toBe('100%');
    expect(tracks[3].firstChild.style.width).toBe('0%');
    expect(tracks[3].getAttribute('aria-hidden')).toBe('true');
    expect(container.querySelectorAll('.service-value.unavailable-value')).toHaveLength(2);
    expect(screen.getByText(/Attrition reference/)).toBeTruthy();
    expect(container.querySelector('.attrition-marker')).toBeTruthy();
  });

  it.each([0,null,-10])('omits markers and leaves both bars empty for average %s',average=>{
    const {container}=render(<OperationsPerspective cutoff="2024-02-29" operations={{combined_flow_mean_12m_myr:average,combined_flow_mean_3m_myr:50}} />);
    expect(container.querySelector('.attrition-marker')).toBeNull();
    expect(screen.queryByText(/Attrition reference/)).toBeNull();
    for(const bar of container.querySelectorAll('.activity-track i')) expect(bar.style.width).toBe('0%');
    expect(container.querySelectorAll('.service-value.unavailable-value')).toHaveLength(4);
  });

  it('shows service first, the backend level word and a hint only for high measures, with the rule in one line',()=>{
    const {container}=render(<OperationsPerspective cutoff="2024-04-30" operations={{combined_flow_mean_12m_myr:100,combined_flow_mean_3m_myr:40,login_failure_rate_3m:.57,passive_session_rate_3m:.1,outbound_failure_rate_3m:.05,outbound_bank_failure_rate_3m:null}}
      levels={{login_failure_rate_3m:level(.57,'high'),passive_session_rate_3m:level(.1,'usual'),outbound_failure_rate_3m:level(.05,'usual'),outbound_bank_failure_rate_3m:level(null,'not_provided')}} />);
    const headings=[...container.querySelectorAll('h2:not(.sr-only)')].map(h=>h.textContent);
    expect(headings).toEqual(['Service experience','Activity level']);
    expect([...container.querySelectorAll('.service-label')].map(n=>n.textContent)).toEqual(['Sign-in failures','Sessions without transactions','Outgoing payment failures','Payment failures on our side']);
    expect([...container.querySelectorAll('.level')].map(n=>n.textContent)).toEqual(['High','Usual','Usual','Not provided']);
    expect(container.querySelectorAll('.hint')).toHaveLength(1);
    expect(container.querySelector('.hint').textContent).toMatch(/^Sign-in failures are high/);
    expect(screen.getByText(new RegExp(LEVEL_RULE.replace(/\./g,'\\.')))).toBeTruthy();
    expect(LEVEL_RULE).toBe('High = higher than 3 in 4 customers in this assessment.');
    expect(container.textContent).not.toMatch(/75th|percentile|p75/i);  // One plain line; no statistics on screen.
  });
});
