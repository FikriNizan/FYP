import React from 'react';
import { driverLabel, driverValue } from '../format.js';
import Icon from './Icon.jsx';

// Saved SHAP drivers shown in plain words. The bar is the driver's strength relative to the strongest shown
// driver (width only); no weight, log-odds or percentage is displayed. Influence is not proof of cause.
const SHOWN_HIGHER = 4, SHOWN_LOWER = 2;

function Signal({ driver, strongest, lower, label }) {
  const width = strongest > 0 ? Math.min(100, Math.abs(driver.contribution_logodds) / strongest * 100) : 0;
  return <div className="sig">
    <span className={'round ' + (lower ? 'green' : 'red')}><Icon name={lower ? 'down' : 'up'} /></span>
    <span><strong>{label || driverLabel(driver)}</strong><span className="sig-value">{driverValue(driver)} · {lower ? 'pushed the estimate down' : 'pushed the estimate up'}</span></span>
    <span className={'meter ' + (lower ? 'lower' : '')} aria-hidden="true"><i style={{ width: width + '%' }} /></span>
  </div>;
}

export default function Signals({ customer }) {
  const explanation = customer.explanation;
  const strength = driver => Math.abs(driver.contribution_logodds || 0);
  const higher = [...(explanation.higher_risk_drivers || [])].sort((a, b) => strength(b) - strength(a)).slice(0, SHOWN_HIGHER);
  const lower = [...(explanation.lower_risk_drivers || [])].sort((a, b) => strength(b) - strength(a)).slice(0, SHOWN_LOWER);
  const strongest = Math.max(0, ...[...higher, ...lower].map(strength));
  return <section className="panel" aria-labelledby="signals-title"><h2 id="signals-title">Signals to investigate</h2>
    <p className="muted">What pushed this estimate up or down. Not proof of cause. Bar length shows relative influence among the signals shown.</p>
    {higher.map(driver => <Signal key={driver.feature} driver={driver} strongest={strongest} label={customer.driver_labels?.[driver.feature]} />)}
    {!higher.length && <p>No signals pushing the estimate up were supplied.</p>}
    {lower.map(driver => <Signal key={driver.feature} driver={driver} strongest={strongest} label={customer.driver_labels?.[driver.feature]} lower />)}
  </section>;
}
