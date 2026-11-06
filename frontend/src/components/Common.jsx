import React from 'react';

export function ErrorNotice({ message }) {
  return <div className="error" role="alert">{message}</div>;
}
export function RiskBadge({ flagged }) {
  return <span className={'badge ' + (flagged ? 'flagged' : '')}>{flagged ? 'For review' : 'Below review threshold'}</span>;
}
export function Definition({ label, value }) {
  return <><dt>{label}</dt><dd>{value}</dd></>;
}
