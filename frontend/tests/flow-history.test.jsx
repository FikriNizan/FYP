import React from 'react';
import { describe, expect, it } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import FlowHistory from '../src/components/FlowHistory.jsx';
import { money } from '../src/format.js';

const history=[
  {snapshot_month:'2024-01-31',combined_flow_myr:0,inbound_myr:0},
  {snapshot_month:'2024-02-29',combined_flow_myr:null},
  {snapshot_month:'2024-03-31',combined_flow_myr:150,inbound_myr:75},
];

describe('Flow history reference levels',()=>{
  it('includes a larger average in the scale and draws its half-value reference without adding rectangles',()=>{
    const {container}=render(<FlowHistory history={history} baseline={200} />);
    const average=container.querySelector('.baseline');
    const reference=container.querySelector('.reference-line');
    expect(Number(average.getAttribute('y1'))).toBeCloseTo(215-200/220*170);
    expect(Number(reference.getAttribute('y1'))).toBeCloseTo((215+Number(average.getAttribute('y1')))/2);
    expect(container.querySelectorAll('rect')).toHaveLength(2);
    expect(container.querySelector('rect').getAttribute('height')).toBe('0');
    expect(container.querySelectorAll('title')).toHaveLength(0);
    expect(screen.getByRole('img').getAttribute('aria-label')).toContain('Two reference lines');
    expect(screen.getByText(/reference level, not an outcome/)).toBeTruthy();
    fireEvent.change(screen.getByLabelText('Measure'),{target:{value:'inbound_myr'}});
    expect(container.querySelector('.baseline')).toBeNull();
    expect(container.querySelector('.reference-line')).toBeNull();
    expect(screen.getByRole('img').getAttribute('aria-label')).toContain('Incoming flow');
    fireEvent.change(screen.getByLabelText('Measure'),{target:{value:'outbound_success_myr'}});
    expect(container.querySelector('.baseline')).toBeNull();
    expect(container.querySelector('.reference-line')).toBeNull();
  });

  it.each([0,null,-10])('omits both lines for non-positive or missing average %s',baseline=>{
    const {container}=render(<FlowHistory history={history} baseline={baseline} />);
    expect(container.querySelectorAll('.baseline,.reference-line')).toHaveLength(0);
    expect(screen.getByText(/No positive trailing twelve-month average was provided/)).toBeTruthy();
  });

  it('shows exact, zero and missing tooltip values on pointer interaction and clears them when changing measure',()=>{
    const {container}=render(<FlowHistory history={history} baseline={200} />);
    const hits=container.querySelectorAll('path.hit');
    fireEvent.pointerEnter(hits[2]);
    let tooltip=container.querySelector('.chart-tooltip');
    expect(tooltip.getAttribute('aria-hidden')).toBe('true');
    expect(tooltip.textContent).toContain('March 2024');
    expect(tooltip.textContent).toContain('Combined flow: '+money(150));
    expect(tooltip.textContent).toContain('25.0% below the 12-month average');
    fireEvent.pointerLeave(hits[2]);
    expect(container.querySelector('.chart-tooltip')).toBeNull();
    fireEvent.pointerDown(hits[0]);
    expect(container.querySelector('.chart-tooltip').textContent).toContain('Combined flow: '+money(0));
    fireEvent.pointerEnter(hits[1]);
    tooltip=container.querySelector('.chart-tooltip');
    expect(tooltip.textContent).toContain('Combined flow: not provided');
    expect(tooltip.textContent).not.toContain('12-month average');
    fireEvent.change(screen.getByLabelText('Measure'),{target:{value:'inbound_myr'}});
    expect(container.querySelector('.chart-tooltip')).toBeNull();
    expect(screen.getByText('Read exact monthly amounts')).toBeTruthy();
  });
});
