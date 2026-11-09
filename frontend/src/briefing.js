import { driverLabel, isNumber } from './format.js';

// Deterministic, bounded questions. No model service or invented customer explanation.
export function discussionQuestions(customer) {
  const ops = customer.operations || {};
  const questions = [];
  const seen = new Set();
  if (isNumber(ops.combined_flow_mean_3m_myr) && isNumber(ops.combined_flow_mean_12m_myr)
      && ops.combined_flow_mean_12m_myr > 0 && ops.combined_flow_mean_3m_myr < ops.combined_flow_mean_12m_myr) {
    questions.push({source:'Observed three- and twelve-month flow averages',text:'Recent recorded transaction activity is lower than the trailing average. Has the way you use these accounts changed?'});
  }
  const drivers = customer.explanation?.higher_risk_drivers || [];
  for (const driver of drivers) {
    if (questions.length >= 3) break;
    const category=driver.feature==='login_failure_rate_3m' ? 'login' : driver.feature==='passive_session_rate_3m' ? 'sessions' : ['outbound_failure_rate_3m','outbound_bank_failure_rate_3m'].includes(driver.feature) ? 'payment' : null;
    if (category && !seen.has(category) && isNumber(driver.value) && driver.value > 0) {
      seen.add(category);
      questions.push({source:driverLabel(driver),text:driver.feature.includes('login')
        ? 'The recorded login difficulty rate contributed to this estimate. Have you experienced difficulties signing in?'
        : driver.feature.includes('passive') ? 'Some recorded sessions had no transactions. Was that consistent with what your team intended to do?'
        : 'The recorded payment failure rate contributed to this estimate. Have you experienced difficulties completing payments?'});
    }
  }
  return questions.slice(0,3);
}
