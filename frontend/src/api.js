export class ApiError extends Error {
  constructor(message, status, code) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.code = code;
  }
}

export function apiPath(path, params = {}) {
  if (!path.startsWith('/api/') && path !== '/api') throw new Error('Use a relative /api path');
  const query = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== '') query.set(key, String(value));
  }
  return path + (query.size ? '?' + query.toString() : '');
}

export async function request(path, { params, method = 'GET', body, signal } = {}) {
  const response = await fetch(apiPath(path, params), {
    method, signal, credentials: 'same-origin',
    headers: { Accept: 'application/json', ...(body === undefined ? {} : { 'Content-Type': 'application/json' }) },
    ...(body === undefined ? {} : { body: JSON.stringify(body) }),
  });
  let result;
  try { result = await response.json(); }
  catch { throw new ApiError('The server returned an unreadable response.', response.status, 'invalid_response'); }
  if (!response.ok) throw new ApiError(result.error?.message || 'Request failed.', response.status, result.error?.code);
  return result;
}

export const api = {
  cases: params => request('/api/cases', { params }),
  case: id => request('/api/cases/' + encodeURIComponent(id)),
  updateCase: (id, body) => request('/api/cases/' + encodeURIComponent(id), { method: 'PUT', body }),
  followUp: (id, task, body) => request('/api/cases/' + encodeURIComponent(id) + '/follow-ups' + (task ? '/' + encodeURIComponent(task) + '/events' : ''), { method: 'POST', body }),
  months: () => request('/api/months'),
  summary: batch => request('/api/summary', { params: { batch_id: batch } }),
  customers: (batch, params) => request('/api/customers', { params: { batch_id: batch, ...params } }),
  customer: (id, batch) => request('/api/customers/' + encodeURIComponent(id), { params: { batch_id: batch } }),
  saveReview: (prediction, body) => request('/api/predictions/' + encodeURIComponent(prediction) + '/review', { method: 'PUT', body }),
};
