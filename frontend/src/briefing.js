import { driverLabel, isNumber } from './format.js';

// Deterministic, bounded questions. No model service or invented customer explanation.
export function discussionQuestions(customer) {
  const ops = customer.operations || {};
  const questions = [];
  if (isNumber(ops.combined_flow_mean_3m_myr) && isNumber(ops.combined_flow_mean_12m_myr)
      && ops.combined_flow_mean_12m_myr > 0 && ops.combined_flow_mean_3m_myr < ops.combined_flow_mean_12m_myr) {
    questions.push({source:'Observed three- and twelve-month flow averages',text:'Recent recorded transaction activity is lower than the trailing average. Has the way you use these accounts changed?'});
  }
  const drivers = customer.explanation?.higher_risk_drivers || [];
  for (const driver of drivers) {
    if (questions.length >= 3) break;
    if (/failure|passive_session/.test(driver.feature) && isNumber(driver.value) && driver.value > 0) {
      questions.push({source:driverLabel(driver),text:driver.feature.includes('login')
        ? 'The recorded login difficulty rate contributed to this estimate. Have you experienced difficulties signing in?'
        : driver.feature.includes('passive') ? 'Some recorded sessions had no transactions. Was that consistent with what your team intended to do?'
        : 'The recorded payment failure rate contributed to this estimate. Have you experienced difficulties completing payments?'});
    }
  }
  if (questions.length < 2 && drivers.length) questions.push({source:driverLabel(drivers[0]),text:'Does this recorded measure match your experience, and is there any context we should understand?'});
  return questions.slice(0,3);
}
