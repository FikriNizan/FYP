import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../api.js';
import { count, percent } from '../format.js';
import { featureMeta } from '../monitoringFeatures.js';
import { ErrorNotice } from '../components/Common.jsx';
import { ConnectionState } from '../components/Workspace.jsx';

// Milestone 7: read-only view of the offline scenario package. Every figure comes from the backend.
export const DEPOSIT_ONLY = 'This scenario changes deposit-related inputs only. Transaction activity, digital engagement and service-friction input values are held constant. Scenario-specific SHAP explanations are not computed.';
export const PASS_THROUGH = 'Own-bank pass-through affects the simulated FD offer rate. Competitor pass-through provides scenario context. Exit shares are separate illustrative assumptions, not estimated responses to the rate gap.';
export const KS_NOTE = 'KS is shown as a distance only, without p-values, because each scenario is a paired copy of the same customers rather than an independent sample.';
export const DRIFT_CAPTION = 'PSI and KS show whether the customer data look different from the reference. They do not show whether the model has become less accurate.';
const HYPOTHETICAL = 'Scenario scores are hypothetical and are not saved predictions. Saved predictions, explanations and review flags are unchanged.';
const fixed = (value, digits) => value === null || value === undefined ? 'Not applicable' : Number(value).toFixed(digits);

function Register({ register }) {
  const [, mild, severe] = register.scenarios;
  const rows = [
    ['OPR change (hypothetical hike)', `${register.scenarios.map(s => s.label + ' ' + s.shock_bp + ' bp').join(' · ')}`],
    ['Effective date and repricing lag', `${register.effective_date}; own rates reprice from ${register.repricing_from} (${register.lag_months}-month lag)`],
    ['Pass-through to FD offer rates', `This bank ${percent(register.own_pass_through, 0)}; competitors ${percent(register.competitor_pass_through, 0)} (${register.competitor_pass_through_use})`],
    ['Cohort', register.cohort],
    ['Share assigned to exit at maturity', `${mild.label} ${percent(mild.migrating_share, 0)} · ${severe.label} ${percent(severe.migrating_share, 0)}`],
    ['Maturity rule', register.renewal_rule],
    ['Customers assigned to exit', register.migrant_rule],
    ['Other customers', register.non_migrant_rule],
    ['Transaction response', register.transaction_response],
    ['Fees and waivers', register.fees_and_waivers],
    ['Version and seed', `${register.version} · seed ${register.seed}`],
  ];
  return <section className="panel" aria-labelledby="register-title"><h2 id="register-title">Assumption register</h2>
    <p className="muted">Assumptions, not estimates. They were fixed before any result was seen. OPR sizes follow real Bank Negara Malaysia moves: 25 bp steps, and a cumulative 125 bp in 2020 and in 2022–2023 (<a href={register.sources.opr_decisions}>BNM OPR decisions</a>).</p>
    <p>{PASS_THROUGH}</p>
    <div className="table-wrap"><table><tbody>{rows.map(([label, value]) => <tr key={label}><th scope="row">{label}</th><td>{value}</td></tr>)}</tbody></table></div>
  </section>;
}

function InputDrift({ scenarios, psi }) {
  const shocked = scenarios.filter(s => s.id !== 'no_shock');
  const changed = [...new Set(shocked.flatMap(s => s.changed_features))].sort();
  const total = Object.keys(scenarios[0].input_drift).length;
  return <section className="panel" aria-labelledby="input-drift-title"><h2 id="input-drift-title">1. Input drift</h2>
    <p className="muted">{DRIFT_CAPTION}</p>
    <p><strong>{count(changed.length)} of {count(total)} predictors change; {count(total - changed.length)} are unchanged by design.</strong> {DEPOSIT_ONLY}</p>
    <div className="table-wrap"><table><thead><tr><th scope="col">Input</th>{shocked.map(s => <React.Fragment key={s.id}><th scope="col">{s.label} PSI</th><th scope="col">{s.label} KS</th><th scope="col">{s.label} customers changed</th></React.Fragment>)}</tr></thead>
      <tbody>{changed.map(name => <tr key={name}><th scope="row">{featureMeta(name).label}</th>{shocked.map(s => { const d = s.input_drift[name]; return <React.Fragment key={s.id}><td>{fixed(d.psi, 4)} <small className="muted">{d.reading}</small></td><td>{fixed(d.ks, 3)}</td><td>{count(d.changed_values)}</td></React.Fragment>; })}</tr>)}</tbody></table></div>
    <p className="muted">PSI uses {psi.bins} bins taken from the reference (reference quantiles; one bin per value when there are at most {psi.value_bin_limit} values), a separate bin for missing values, and {psi.epsilon} in place of an empty bin. The readings below 0.10, 0.10–0.25 and above 0.25 are conventions (Siddiqi 2006; Yurdakul 2018), not pass or fail limits. {KS_NOTE} Each input is checked on its own, so a change in how inputs move together would not be seen.</p>
    <Coverage scenarios={shocked} />
  </section>;
}

function Coverage({ scenarios }) {
  const rate = scenarios[0]?.input_drift.fd_balance_weighted_offer_rate;
  if (!rate) return null;
  return <p className="muted">Coverage: PSI includes a missing-value bin, while KS uses non-missing values only. The weighted FD rate is blank for a customer with no fixed deposit, so it is compared on {count(rate.reference_available)} reference customers against {scenarios.map(s => `${count(s.input_drift.fd_balance_weighted_offer_rate.current_available)} (${s.label.toLowerCase()})`).join(' and ')}. A customer who loses all fixed deposits has no weighted rate; that is not a data defect.</p>;
}

function PredictionChange({ scenarios }) {
  return <section className="panel" aria-labelledby="prediction-change-title"><h2 id="prediction-change-title">2. Prediction change</h2>
    <p className="muted">The frozen champion scores shocked copies of the April 2024 features under the same saved review rule. {HYPOTHETICAL}</p>
    <p className="muted">Different denominators: customers assigned to exit are a seeded share of the {count(scenarios[0].cohort_size)} customers with a fixed deposit in January; only those with a deposit maturing between March and April can be affected, and only deposits still active after maturity change.</p>
    <div className="table-wrap"><table><thead><tr><th scope="col">Scenario</th><th scope="col">Customers assigned to exit at maturity</th><th scope="col">Actually affected in the window</th><th scope="col">Customers whose score changed</th><th scope="col">Score PSI</th><th scope="col">Score KS</th><th scope="col">Into review</th><th scope="col">Out of review</th><th scope="col">Flagged (saved: {count(scenarios[0].prediction_change.saved_flagged)})</th><th scope="col">Mean estimated risk</th></tr></thead>
      <tbody>{scenarios.map(s => { const p = s.prediction_change; return <tr key={s.id}><th scope="row">{s.label}</th><td>{count(s.assigned_exit_customers)} of {count(s.cohort_size)} <small className="muted">{count(s.eligible_exit_customers)} with a deposit maturing in the window</small></td><td>{count(s.exit_affected_customers)} customers · {count(s.exit_affected_fds)} FDs closed <small className="muted">{count(s.repriced_fds)} FDs repriced for {count(s.repriced_customers)} other customers</small></td><td>{count(s.customers_score_changed)}</td><td>{fixed(p.risk.psi, 5)}</td><td>{fixed(p.risk.ks, 3)}</td><td>{count(p.crossed_into_review)}</td><td>{count(p.crossed_out_of_review)}</td><td>{count(p.flagged)}</td><td>{percent(p.saved_mean_risk, 2)} → {percent(p.mean_risk, 2)}</td></tr>; })}</tbody></table></div>
    <details><summary>Flagged customers only (secondary view)</summary><ul>{scenarios.map(s => <li key={s.id}>{s.label}: {count(s.prediction_change.flagged_only.still_flagged)} of {count(s.prediction_change.flagged_only.customers)} stay flagged; score KS {fixed(s.prediction_change.flagged_only.risk.ks, 3)}.</li>)}</ul></details>
  </section>;
}

export default function ResearchPreview() {
  const [data, setData] = useState(null);
  const [error, setError] = useState('');
  useEffect(() => {
    let active = true;
    api.scenarios().then(result => { if (active) setData(result); }).catch(e => { if (active) setError(e.message); });
    return () => { active = false; };
  }, []);
  return <>
    <div className="heading"><div><h1>OPR stress demonstration</h1><p className="muted">An assumption-based synthetic stress scenario. It is not a forecast of Bank Negara Malaysia policy, not evidence of customer behaviour, and not a performance evaluation.</p></div><ConnectionState preview>Scenario package</ConnectionState></div>
    {error && <ErrorNotice message={error} />}
    {!data && !error && <p role="status">Loading scenario package…</p>}
    {data?.state === 'not_generated' && <section className="panel"><h2>No scenario package</h2><p>Not calculated. The scenario package is generated offline by an administrator; nothing is calculated in the browser.</p></section>}
    {data?.state === 'invalid' && <section className="panel"><h2>Scenario package unavailable</h2><p>The scenario package failed its integrity checks, so no figures are shown.</p></section>}
    {data?.state === 'ready' && <>
      <section className="panel"><h2>What this shows</h2><p><strong>{DEPOSIT_ONLY}</strong></p><p className="muted">Reference: {data.reference}. Before scoring, the run checked that the recomputed deposit inputs equal the saved ones exactly ({count(data.gates.parity.features.length)} inputs) and that the frozen model reproduces the saved April scores (largest difference {data.gates.reproduction.max_abs_risk_difference}; {count(data.gates.reproduction.flag_mismatches)} review-flag differences).</p><p className="muted">Observed outcomes and descriptive movement between real months are in <Link to="/monitoring">Monitoring</Link>.</p></section>
      <Register register={data.register} />
      <InputDrift scenarios={data.scenarios} psi={data.psi} />
      <PredictionChange scenarios={data.scenarios} />
      <section className="panel" aria-labelledby="performance-title"><h2 id="performance-title">3. Performance change</h2><p><strong>Not computed.</strong> Performance not evaluated: hypothetical outcomes are unavailable.</p></section>
    </>}
  </>;
}
