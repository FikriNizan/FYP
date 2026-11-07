import React from 'react';
import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import OperationsPerspective from '../src/components/OperationsPerspective.jsx';
import { ratioWidth } from '../src/presentation.js';

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
    const tracks=container.querySelectorAll('.service-track');
    expect(tracks[0].firstChild.style.width).toBe('0%');
    expect(tracks[1].firstChild.style.width).toBe('100%');
    expect(tracks[2].firstChild.style.width).toBe('0%');
    expect(tracks[2].getAttribute('aria-hidden')).toBe('true');
    expect(screen.getAllByText('Not provided')).toHaveLength(2);
    expect(screen.getByText(/Attrition reference/)).toBeTruthy();
    expect(container.querySelector('.attrition-marker')).toBeTruthy();
    expect(screen.queryByText('About these measures')).toBeNull();
  });

  it.each([0,null,-10])('omits markers and leaves both bars empty for average %s',average=>{
    const {container}=render(<OperationsPerspective cutoff="2024-02-29" operations={{combined_flow_mean_12m_myr:average,combined_flow_mean_3m_myr:50}} />);
    expect(container.querySelector('.attrition-marker')).toBeNull();
    expect(screen.queryByText(/Attrition reference/)).toBeNull();
    for(const bar of container.querySelectorAll('.activity-track i')) expect(bar.style.width).toBe('0%');
    expect(container.querySelectorAll('.service-value.unavailable-value')).toHaveLength(4);
  });
});
