import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../api.js';
import { dateLabel, monthLabel } from '../format.js';
import { assessmentLink } from '../navigation.js';
import { ErrorNotice } from '../components/Common.jsx';
import Icon from '../components/Icon.jsx';
import { DEFINITION, PortfolioFinanceMetrics } from '../components/FinanceMetrics.jsx';

// Opened from the Overview "Deposits held by flagged customers" tile. Every figure comes from /api/summary.
export default function FinancePicture({ batch, revision }) {
  const [summary, setSummary] = useState(null);
  const [error, setError] = useState('');
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    let active = true;
    setSummary(null); setError('');
    api.summary(batch).then(result => { if (active) setSummary(result); }).catch(e => { if (active) setError(e.message); });
    return () => { active = false; };
  }, [batch, revision, attempt]);
  if (error) return <><ErrorNotice message={error} /><button onClick={() => setAttempt(n => n + 1)}>Try again</button></>;
  if (!summary || summary.batch.batch_id !== batch) return <p role="status">Loading finance picture…</p>;
  const metrics = summary.finance_metrics;
  const reason = metrics && !metrics.opr_verified ? 'Finance contribution is unavailable for this assessment: verified OPR rates end ' + dateLabel(metrics.opr_verified_through) + '.' : null;
  return <>
    <Link className="back-link" to={assessmentLink('/overview', batch)}><Icon name="left" />Overview</Link>
    <div className="heading"><div><h1>Finance picture</h1><p className="muted">{monthLabel(summary.batch.cutoff_month)} assessment · {DEFINITION}</p></div></div>
    {reason && <p className="scope-note">{reason}</p>}
    {metrics ? <PortfolioFinanceMetrics metrics={metrics} /> : <p>Finance contribution is not provided for this assessment.</p>}
  </>;
}
