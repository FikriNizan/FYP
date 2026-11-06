import React from 'react';
import { count, driverLabel, driverValue } from '../format.js';

function Signal({ driver }) {
  return <div className="signal"><span><strong>{driverLabel(driver)}</strong><br /><small className="muted">{driver.group}</small></span><span className="signal-value">{driverValue(driver)}</span></div>;
}
export default function Signals({ customer }) {
  const explanation = customer.explanation;
  const higher = explanation.higher_risk_drivers || [], lower = explanation.lower_risk_drivers || [];
  return <section className="panel"><h2>Signals to investigate</h2><p className="muted">These signals raised the model’s estimate. Discuss them across Operations and Finance; they do not confirm a cause.</p>
    {higher.slice(0,3).map(driver => <Signal key={driver.feature} driver={driver} />)}
    {!higher.length && <p>No higher-risk signals were supplied.</p>}
    <details><summary>More model signals</summary>{higher.slice(3).map(driver => <Signal key={driver.feature} driver={driver} />)}<h3 className="spaced">Signals lowering the estimate</h3>{lower.map(driver => <Signal key={driver.feature} driver={driver} />)}{!lower.length && <p>No lower-risk signals were supplied.</p>}</details>
    <details><summary>Technical explanation</summary><p>SHAP values explain the model in calibrated log-odds. They are not probability percentage points.</p>
      <div className="technical">{JSON.stringify({ base_logodds: explanation.base_logodds, higher_risk_drivers: higher, lower_risk_drivers: lower, other_features_contribution_logodds: explanation.other_features_contribution_logodds, probability_clip_adjustment_logodds: explanation.probability_clip_adjustment_logodds }, null, 2)}</div>
      <p className="muted">Batch {customer.batch_id} · {count(customer.feature_count)} supplied model inputs</p>
    </details>
  </section>;
}
