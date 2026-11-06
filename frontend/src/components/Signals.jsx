import React from 'react';
import { count, driverLabel, driverValue } from '../format.js';

function Signal({ driver, direction }) {
  return <div className="signal"><div className="signal-label"><strong>{driverLabel(driver)}</strong><span className={'signal-direction '+(direction==='lower' ? 'lower' : 'higher')}>{direction==='lower' ? 'Pushed the estimate lower' : 'Pushed the estimate higher'}</span></div><div className="signal-value">{driverValue(driver)}</div></div>;
}
export default function Signals({ customer }) {
  const explanation = customer.explanation;
  const higher = explanation.higher_risk_drivers || [], lower = explanation.lower_risk_drivers || [];
  return <section className="panel"><h2>Signals to investigate</h2><p className="muted">Start with the inputs that raised this estimate.</p>
    {higher.slice(0,3).map(driver => <Signal key={driver.feature} driver={driver} />)}
    {!higher.length && <p>No higher-risk signals were supplied.</p>}
    <details><summary>What does this mean?</summary><p>These model inputs pushed the predicted risk higher or lower relative to the model’s reference. They identify evidence to investigate, not confirmed causes or guaranteed remedies.</p></details>
    <details><summary>More model signals</summary>{higher.slice(3).map(driver => <Signal key={driver.feature} driver={driver} />)}<h3 className="spaced">Signals lowering the estimate</h3>{lower.map(driver => <Signal key={driver.feature} driver={driver} direction="lower" />)}{!lower.length && <p>No lower-risk signals were supplied.</p>}</details>
    <details><summary>Technical explanation</summary><p>SHAP values explain the model in calibrated log-odds. They are not probability percentage points.</p>
      <div className="technical">{JSON.stringify({ base_logodds: explanation.base_logodds, higher_risk_drivers: higher, lower_risk_drivers: lower, other_features_contribution_logodds: explanation.other_features_contribution_logodds, probability_clip_adjustment_logodds: explanation.probability_clip_adjustment_logodds }, null, 2)}</div>
      <p className="muted">Batch {customer.batch_id} · {count(customer.feature_count)} supplied model inputs</p>
    </details>
  </section>;
}
