import React, { useEffect, useState } from 'react';
import { api } from '../api.js';
import { count, dateLabel, percent } from '../format.js';
import { featureMeta } from '../monitoringFeatures.js';
import Icon from './Icon.jsx';

// Milestone 7 OPR stress demonstration (package m7-opr-2), read-only. Every figure comes from the backend.
export const DEPOSIT_ONLY = 'This scenario changes deposit-related inputs only. Transaction activity, digital engagement and service-friction input values are held constant. Scenario-specific SHAP explanations are not computed.';
export const PASS_THROUGH = 'Own-bank pass-through affects the simulated FD offer rate. Competitor pass-through provides scenario context. Exit shares are separate illustrative assumptions, not estimated responses to the rate gap.';
export const KS_NOTE = 'KS is shown as a distance only, without p-values, because each scenario is a paired copy of the same customers rather than an independent sample.';
export const SCOPE = 'Performance not evaluated: hypothetical outcomes are unavailable.';
const WORDS = { 'No shift':['No','w-no'], 'Little shift':['Little','w-little'], 'Moderate shift':['Moderate','w-moderate'], 'Large shift':['Large','w-large'] };
const fixed = (value, digits) => value === null || value === undefined ? 'Not applicable' : Number(value).toFixed(digits);

function Assumed({ data, selected, choose }) {
  const register = data.register, scenario = data.scenarios.find(s => s.id === selected);
  return <section className="panel" aria-labelledby="assumed-title"><h2 id="assumed-title">What was assumed?</h2>
    <p className="muted">A hypothetical Bank Negara Malaysia rate rise from {dateLabel(register.effective_date)}; deposits reprice from {dateLabel(register.repricing_from)}. Pick a scenario.</p>
    <div className="scen" role="group" aria-label="Scenario">{data.scenarios.map(s => <button key={s.id} type="button" aria-pressed={s.id === selected} onClick={() => choose(s.id)}>
      <b>{s.label}</b><span>{s.shock_bp ? `OPR +${count(s.shock_bp)} bp` : 'Reference'}</span></button>)}</div>
    <div className="assume">
      <p><span className="round"><Icon name="up" /></span><span>Our fixed deposit rate rises by <b>{percent(register.own_pass_through, 0)} of the rise</b>, when each deposit matures.</span></p>
      <p><span className="round"><Icon name="users" /></span><span><b>{percent(scenario.migrating_share, 0)}</b> of fixed deposit holders are assigned to leave at maturity. An illustrative share, not an estimate.</span></p>
      <p><span className="round"><Icon name="payment-failed" /></span><span>Payments, collections, sign-ins and sessions are <b>held constant</b>.</span></p>
    </div>
  </section>;
}

function Deposits({ scenarios }) {
  const largest = Math.max(1, ...scenarios.map(s => s.assigned_exit_customers));
  const height = value => Math.max(value ? 3 : 0, value / largest * 100) + '%';
  return <section className="panel" aria-labelledby="deposits-title"><h2 id="deposits-title">What changed in deposits?</h2>
    <p className="muted">Customers, by scenario</p>
    <div className="gbars" role="img" aria-label={scenarios.map(s => `${s.label}: ${s.assigned_exit_customers} assigned, ${s.exit_affected_customers} actually affected`).join('; ')}>
      {scenarios.map(s => <div className="gcol" key={s.id}><div className="gpair">
        <i className="assigned" style={{ height: height(s.assigned_exit_customers) }}><em>{count(s.assigned_exit_customers)}</em></i>
        <i className="affected" style={{ height: height(s.exit_affected_customers) }}><em>{count(s.exit_affected_customers)}</em></i>
      </div><span>{s.label}</span></div>)}
    </div>
    <div className="key"><span><i className="assigned" />Assigned to leave at maturity</span><span><i className="affected" />Actually affected in the window</span></div>
    <p>Assigned customers are a seeded share of the {count(scenarios[0].cohort_size)} customers with a fixed deposit in January. Only those whose deposit matured in the window, and was still active, were actually affected.</p>
  </section>;
}

function Output({ scenarios, selected }) {
  const s = scenarios.find(item => item.id === selected), p = s.prediction_change;
  const customers = p.risk.reference_available;
  return <section className="panel" aria-labelledby="output-title"><h2 id="output-title">What changed in model output and workload?</h2>
    <p className="muted">{count(customers)} customers · {s.label}</p>
    <div className="kv"><span>Customers flagged for review</span><b>{count(p.flagged)}</b></div>
    <div className="kv"><span>Customers moving into or out of review</span><b>{count(p.crossed_into_review + p.crossed_out_of_review)}</b></div>
    <div className="kv"><span>Customers whose score changed at all</span><b>{count(s.customers_score_changed)}</b></div>
    <div className="kv"><span>Average predicted risk</span><b>{percent(p.mean_risk, 2)}</b></div>
    <div className="fbars" role="img" aria-label="Flagged customers by scenario, out of all customers">{scenarios.map(item => <div className="fbar" key={item.id}>
      <span>{item.label}</span><span className="t"><i style={{ width: (item.prediction_change.flagged / customers * 100) + '%' }} /></span><b>{count(item.prediction_change.flagged)}</b></div>)}</div>
    <p className="muted">Bars run from zero to all {count(customers)} customers.</p>
  </section>;
}

function Inputs({ scenarios, selected, psi, labels = {} }) {
  const label = feature => labels[feature] || featureMeta(feature).label;
  const s = scenarios.find(item => item.id === selected);
  const changed = [...new Set(scenarios.flatMap(item => item.changed_features))].sort();
  const rate = s.input_drift.fd_balance_weighted_offer_rate;
  const others = scenarios.filter(item => item.id !== 'no_shock');
  return <section className="panel" aria-labelledby="inputs-title"><h2 id="inputs-title">Which inputs moved?</h2>
    <p className="muted">How different the inputs look from the no-change reference · {s.label} · {count(changed.length)} of {count(Object.keys(s.input_drift).length)} inputs can change</p>
    {changed.map(name => { const [word, tone] = WORDS[s.input_drift[name].reading] || ['Not applicable', 'w-no'];
      return <div className="inrow" key={name}><span>{label(name)}</span><span className={'word ' + tone}>{word}</span></div>; })}
    <details className="tech"><summary>Technical detail</summary>
      <p className="muted">Shift sizes use the population stability index (PSI): below {psi.convention[0]} little, {psi.convention[0]}–{psi.convention[1]} moderate, above {psi.convention[1]} large. These are common conventions, not pass or fail limits. {KS_NOTE}</p>
      <div className="table-wrap"><table className="sens"><thead><tr><th scope="col">Input</th>{others.map(o => <React.Fragment key={o.id}><th scope="col">{o.label} PSI</th><th scope="col">{o.label} KS</th></React.Fragment>)}</tr></thead>
        <tbody>{changed.map(name => <tr key={name}><th scope="row">{label(name)}</th>{others.map(o => <React.Fragment key={o.id}><td>{fixed(o.input_drift[name].psi, 4)}</td><td>{fixed(o.input_drift[name].ks, 3)}</td></React.Fragment>)}</tr>)}
          <tr><th scope="row">Predicted risk (scores)</th>{others.map(o => <React.Fragment key={o.id}><td>{fixed(o.prediction_change.risk.psi, 5)}</td><td>{fixed(o.prediction_change.risk.ks, 3)}</td></React.Fragment>)}</tr></tbody></table></div>
      <p className="muted">Coverage: PSI includes a missing-value bin; KS uses non-missing values only. The weighted fixed deposit rate is blank for customers with no deposit, so it is compared on {count(rate.reference_available)} reference customers against {others.map(o => `${count(o.input_drift.fd_balance_weighted_offer_rate.current_available)} (${o.label.toLowerCase()})`).join(' and ')}.</p>
    </details>
  </section>;
}

export default function RateShock() {
  const [data, setData] = useState(null), [error, setError] = useState(''), [selected, setSelected] = useState('severe');
  useEffect(() => {
    let active = true;
    api.scenarios().then(result => { if (active) setData(result); }).catch(e => { if (active) setError(e.message); });
    return () => { active = false; };
  }, []);
  if (error) return <p role="alert" className="error">{error}</p>;
  if (!data) return <p role="status">Loading scenario package…</p>;
  if (data.state === 'not_generated') return <section className="panel"><h2>No scenario package</h2><p>Not calculated. The scenario package is generated offline by an administrator; nothing is calculated in the browser.</p></section>;
  if (data.state !== 'ready') return <section className="panel"><h2>Scenario package unavailable</h2><p>The scenario package failed its integrity checks, so no figures are shown.</p></section>;
  return <>
    <Assumed data={data} selected={selected} choose={setSelected} />
    <div className="two-columns"><Deposits scenarios={data.scenarios} /><Output scenarios={data.scenarios} selected={selected} /></div>
    <Inputs scenarios={data.scenarios} selected={selected} psi={data.psi} labels={data.feature_labels} />
    <section className="panel scope-box" aria-label="Scope"><span className="round warn"><Icon name="info" /></span><div>
      <p><b>{SCOPE}</b></p><p className="muted">{DEPOSIT_ONLY}</p><p className="muted">{PASS_THROUGH}</p>
      <p className="muted">Scenario scores are hypothetical and are not saved predictions; saved predictions, explanations and review flags are unchanged.</p></div></section>
  </>;
}
