export const escapeHtml = value => String(value ?? '').replace(/[&<>"']/g, c => ({
  '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
}[c]));

export const isNumber = value => typeof value === 'number' && Number.isFinite(value);
export const percent = (value, digits = 1) => isNumber(value) ? (value * 100).toFixed(digits) + '%' : 'Not provided';
export const money = value => isNumber(value)
  ? new Intl.NumberFormat('en-MY', { style: 'currency', currency: 'MYR', maximumFractionDigits: 2 }).format(value)
  : 'Not provided';
// Portfolio totals in millions, e.g. −RM1.23m or +RM4.56m (U+2212 minus); values come from the backend.
export const millions = value => isNumber(value)
  ? (value < 0 ? '−' : value > 0 ? '+' : '') + 'RM' + (Math.abs(value) / 1e6).toFixed(2) + 'm'
  : 'Not provided';
// Balances (never negative here) in millions without a sign, e.g. RM61.40m; values come from the backend.
export const millionsPlain = value => isNumber(value) ? 'RM' + (value / 1e6).toFixed(2) + 'm' : 'Not provided';
// Display names for the synthetic tier reference table (labels only; thresholds come from the backend).
export const tierLabel = tier => ({ SME_S:'SME small', SME_M:'SME medium', CORP_L:'Corporate large', CORP_XL:'Corporate extra-large', GOV:'Government' }[tier] || tier || 'Tier not provided');
// Owner decision: a waiting assessment names the LAST month of its forecast window.
export const readyAfterLabel = month => `Ready after ${monthLabel(month)} data`;
export const count = value => isNumber(value) ? new Intl.NumberFormat('en-MY').format(value) : 'Not provided';

export function dateLabel(value) {
  if (!value) return 'Not scheduled';
  const timestamp = value.includes('T');
  const date = new Date(timestamp ? value : value.slice(0,10)+'T00:00:00Z');
  return Number.isNaN(date.valueOf()) ? 'Not provided' : new Intl.DateTimeFormat('en-MY',{day:'numeric',month:'short',year:'numeric',timeZone:timestamp ? 'Asia/Kuala_Lumpur' : 'UTC'}).format(date);
}

export function malaysiaToday() {
  return new Intl.DateTimeFormat('en-CA',{year:'numeric',month:'2-digit',day:'2-digit',timeZone:'Asia/Kuala_Lumpur'}).format(new Date());
}

export function monthLabel(value) {
  if (!value) return 'Not provided';
  const date = new Date(value + 'T00:00:00Z');
  return Number.isNaN(date.valueOf()) ? 'Not provided'
    : new Intl.DateTimeFormat('en-MY', { month: 'long', year: 'numeric', timeZone: 'UTC' }).format(date);
}

export function forecastLabel(cutoff) {
  const [year, month] = cutoff.split('-').map(Number);
  const first = new Date(Date.UTC(year, month, 1));
  const last = new Date(Date.UTC(year, month + 2, 1));
  const format = new Intl.DateTimeFormat('en-MY', { month: 'short', timeZone: 'UTC' });
  return `${format.format(first)}${first.getUTCFullYear() !== last.getUTCFullYear() ? ' ' + first.getUTCFullYear() : ''}–${format.format(last)} ${last.getUTCFullYear()}`;
}

export const decisionLabel = decision => ({
  awaiting_review: 'Awaiting review', prioritise: 'Prioritised for RM',
  monitor: 'Monitor', no_immediate_action: 'No immediate action',
}[decision] || 'Not provided');

export const caseStatusLabel = status => ({
  open: 'Open',
  deferred: 'Deferred',
  closed: 'Closed',
}[status] || status);

export const workflowLabel = (state, original=false) => ({
  reviewed:'Reviewed for this assessment', existing_case:original ? 'Existing case for its original assessment' : 'Existing case - new assessment',
  case_conflict:'Existing cases - select one', below_threshold:'Below review threshold',
  needs_reassessment:'Needs reassessment',needs_first_review:'Needs first review',
}[state] || 'Review context unavailable');

export function activityChange(recent, baseline) {
  if (!isNumber(recent) || !isNumber(baseline) || baseline <= 0) return 'Not provided';
  const change = (recent / baseline - 1) * 100;
  if (Math.abs(change) < 0.05) return 'Similar to usual';
  return Math.abs(change).toFixed(1) + '% ' + (change < 0 ? 'lower' : 'higher');
}

const labels = {
  combined_flow_ratio_3m_to_12m: 'Combined flow',
  inbound_flow_ratio_3m_to_12m: 'Collections',
  outbound_flow_ratio_3m_to_12m: 'Payments',
  outbound_failure_rate_3m: 'Payment failures',
  outbound_bank_failure_rate_3m: 'Bank-attributed payment failures',
  login_failure_rate_3m: 'Login difficulties',
  passive_session_rate_3m: 'Sessions without transactions',
  fd_maturing_30d_count: 'Fixed deposits maturing within 30 days',
  non_fd_balance_myr: 'Operating account balances',
  fd_balance_myr: 'Fixed deposit balances',
  login_success_count_mean_12m: 'Usual successful logins',
  approver_session_share_3m: 'Sessions involving approvers',
};
export const driverLabel = driver => labels[driver.feature] || driver.label || driver.feature.replaceAll('_', ' ');
export function driverValue(driver) {
  if (driver.value === null || driver.value === undefined) return 'Not provided';
  if (driver.feature.includes('_ratio_')) return percent(driver.value, 2) + ' of the twelve-month average';
  if (/_rate_|_share_/.test(driver.feature)) return percent(driver.value);
  if (driver.feature.endsWith('_myr')) return money(driver.value);
  return isNumber(driver.value) ? new Intl.NumberFormat('en-MY', { maximumFractionDigits: 2 }).format(driver.value) : String(driver.value);
}
