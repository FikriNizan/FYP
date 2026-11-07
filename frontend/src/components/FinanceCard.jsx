import React from 'react';
import { money } from '../format.js';
import Icon from './Icon.jsx';

export default function FinanceCard({ label, icon, kind, value, missing = false, children }) {
  return <article className={'finance-card '+kind+(missing ? ' is-missing' : '')}>
    <div className="finance-card-top"><span className="finance-icon"><Icon name={icon} /></span><span className="finance-kind">{kind==='exposure' ? 'Exposure' : 'Historical estimate'}</span></div>
    <h3>{label}</h3>
    <strong className="finance-value">{money(value)}</strong>
    {children}
  </article>;
}
