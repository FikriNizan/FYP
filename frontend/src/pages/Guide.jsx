import React from 'react';
import { Link } from 'react-router-dom';
import Icon from '../components/Icon.jsx';

// Approved wording: docs/design/final-tweaks-mockup.html ("Guide" screen). Longer method notes live in docs/USER_GUIDE.md.
const STEPS = [
  ['calendar', 'Choose the month', 'See how many customers are flagged and who is still waiting for review.', 'Overview'],
  ['search', 'Review a customer', 'Summary, Operations and Finance show why they were flagged.', 'Customer review'],
  ['cases', 'Record the decision', 'Prioritise for RM, Monitor or No immediate action, with a reason.', 'Record committee decision'],
  ['message', 'Follow up', 'For prioritised customers, print the RM briefing, then log each follow-up.', 'Reviewed Customers'],
];
const TERMS = [
  ['research', 'Predicted risk', "The model's estimated chance of a volume drop in the next three months."],
  ['flag', 'Flagged', 'Risk is above the review line. A prompt to look, not a verdict.'],
  ['down', 'Volume drop', 'Transaction flow falls to half or less of its usual level. The account may stay open.'],
  ['coin', 'Contribution at stake', 'What the relationship earns the bank over three months. An estimate, not a forecast. Called Revenue at Risk (RaR) in the project report.'],
];
const REMEMBER = [
  "Signals explain the score. They don't prove the cause.",
  'Items marked AI are drafts for your review.',
  'RM figures are estimates based on stated assumptions.',
];
const MONITORING = [
  ['clock', 'Outcomes check themselves.', ' Uploading a month grades the assessment from three months earlier. While a month is missing, it waits; nothing is guessed.'],
  ['grid', 'The grid compares flags with real volume drops:', ' Caught, False alarm, Missed, Correctly quiet.'],
  ['message', 'Follow-ups count', ' only when delivered (visit, contact or service fix) and dated inside the three-month window. No record does not prove no contact.'],
  ['research', 'Input movement', ' compares this month with last month. Descriptive only, with no alert threshold.'],
  ['up', 'Rate-shock what-if', ' is a stress test run offline on one saved assessment, named on the tab. It never changes saved predictions.'],
];

const Hint = ({ icon, children }) => <p className="hint"><span className="round small"><Icon name={icon} /></span><span>{children}</span></p>;

export default function Guide() {
  return <>
    <div className="heading"><div><h1>How to use this workspace</h1><p className="muted">One meeting each month: see who is flagged, decide, then follow up.</p></div></div>
    <section className="panel" aria-labelledby="guide-workflow"><h2 id="guide-workflow">The monthly workflow</h2><ol className="g-steps">
      {STEPS.map(([icon, title, text, page], index) => <li className="g-step" key={title}><span className="g-num">{index + 1}</span><span className="round"><Icon name={icon} /></span>
        <h3>{title}</h3><p className="muted">{text}</p><span className="badge">{page}</span></li>)}</ol></section>
    <section className="panel" aria-labelledby="guide-terms"><h2 id="guide-terms">Four words to know</h2><div className="g-terms">
      {TERMS.map(([icon, title, text]) => <div className="g-term" key={title}><span className="round"><Icon name={icon} /></span><div><h3>{title}</h3><p className="muted">{text}</p></div></div>)}</div></section>
    <section className="panel" aria-labelledby="guide-remember"><h2 id="guide-remember">Good to remember</h2><div className="hints g-three">
      {REMEMBER.map(text => <Hint key={text} icon="info">{text}</Hint>)}</div></section>
    <section className="panel" aria-labelledby="guide-decision"><h2 id="guide-decision">A lower score later never erases a decision</h2><div className="context-grid g-example">
      <div className="context-card original-context"><p className="eyebrow">January review</p><p className="number">70.0%</p><p>Committee: Prioritise for RM</p></div>
      <div className="context-card"><p className="eyebrow">February assessment</p><p className="number">18.0%</p><p>The January decision stays. The case closes only when the team closes it.</p></div></div>
      <p className="muted">Example values for explanation only.</p></section>
    <section className="panel" aria-labelledby="guide-monitoring"><div className="section-heading"><h2 id="guide-monitoring">For data owners: reading Monitoring</h2><Link className="button" to="/monitoring">Open Monitoring →</Link></div>
      <div className="hints g-two">{MONITORING.map(([icon, lead, rest]) => <Hint key={lead} icon={icon}><b>{lead}</b>{rest}</Hint>)}</div>
      <details><summary>Administrator fallback</summary><p className="muted">If outcomes must be loaded outside the browser:</p><pre><code>python -m flask --app app load-outcomes --batch-id BATCH --observed-through YYYY-MM-DD</code></pre><p className="muted">Add <code>--apply</code> to save. Needs the research folder setting.</p></details></section>
  </>;
}
