import React, { useId } from 'react';

export function ConnectionState({ preview = false, unavailable = false, children }) {
  return <span className={'connection-state '+(preview ? 'preview' : unavailable ? 'unavailable' : '')}>{children || (preview ? 'Demo preview' : unavailable ? 'Unavailable pending integration' : 'Connected to saved data')}</span>;
}

export function Explanation({ term = 'What does this mean?', children }) {
  return <details className="inline-help"><summary>{term}</summary><div>{children}</div></details>;
}

export function PerspectiveTabs({ value, onChange }) {
  const id = useId();
  const tabs = ['Summary','Operations','Finance'];
  return <div role="tablist" aria-label="Evidence perspective" className="perspective-tabs" onKeyDown={event => {
    if (!['ArrowLeft','ArrowRight','Home','End'].includes(event.key)) return;
    event.preventDefault();
    const current = tabs.indexOf(value);
    const index = event.key === 'Home' ? 0 : event.key === 'End' ? 2 : (current+(event.key==='ArrowRight' ? 1 : 2))%3;
    onChange(tabs[index]); event.currentTarget.querySelectorAll('[role=tab]')[index].focus();
  }}>{tabs.map(label => <button key={label} id={id+'-'+label} type="button" role="tab" aria-selected={value===label} aria-controls="perspective-panel" tabIndex={value===label ? 0 : -1} onClick={()=>onChange(label)}>{label}</button>)}</div>;
}
