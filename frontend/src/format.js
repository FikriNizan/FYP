export const escapeHtml = value => String(value ?? '').replace(/[&<>"']/g, c => ({
  '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
}[c]));

export const isNumber = value => typeof value === 'number' && Number.isFinite(value);
export const percent = (value, digits = 1) => isNumber(value) ? (value * 100).toFixed(digits) + '%' : 'Not provided';
export const money = value => isNumber(value)
  ? new Intl.NumberFormat('en-MY', { style: 'currency', currency: 'MYR', maximumFractionDigits: 2 }).format(value)
  : 'Not provided';
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

export function activityChange(recent, baseline) {
  if (!isNumber(recent) || !isNumber(baseline) || baseline <= 0) return 'Not provided';
  const change = (recent / baseline - 1) * 100;
  if (Math.abs(change) < 0.05) return 'Similar to usual';
  return Math.abs(change).toFixed(1) + '% ' + (change < 0 ? 'lower' : 'higher');
}

const labels = {
  combined_flow_ratio_3m_to_12m: 'Transaction activity',
  inbound_flow_ratio_3m_to_12m: 'Incoming payments',
  outbound_flow_ratio_3m_to_12m: 'Outgoing payments',
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
