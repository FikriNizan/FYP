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
  uploadAssessment: async (features, manifest) => {
    const body = new FormData(); body.append('features',features); body.append('manifest',manifest);
    let response;
    try { response = await fetch('/api/assessments', {method:'POST', credentials:'same-origin', headers:{Accept:'application/json'}, body}); }
    catch { throw new ApiError('Connection lost during processing. Check saved assessments, then safely resubmit the unchanged package.',0,'network_error'); }
    let result;
    try { result = await response.json(); }
    catch { throw new ApiError('The server returned an unreadable response. Check saved assessments before retrying.',response.status,'invalid_response'); }
    if (!response.ok) throw new ApiError(result.error?.message || 'Monthly processing failed. Correct the package and try again.',response.status,result.error?.code);
    return result;
  },
  briefing: ids => request('/api/briefings?' + new URLSearchParams(ids.map(id=>['case_id',id]))),
  downloadBriefing: async (ids, snapshots, signal) => {
    const response=await fetch('/api/briefings/pdf', {
      method:'POST', credentials:'same-origin', signal,
      headers:{Accept:'application/pdf','Content-Type':'application/json'},
      body:JSON.stringify({case_ids:ids,snapshots}),
    });
    if (!response.ok) {
      let result;
      try { result=await response.json(); } catch { throw new ApiError('The PDF service returned an unreadable response. Try again.',response.status,'invalid_response'); }
      const error=new ApiError(result.error?.message || 'PDF download failed. Try again.',response.status,result.error?.code);
      error.briefing=result.briefing;
      throw error;
    }
    if (!response.headers.get('Content-Type')?.startsWith('application/pdf')) throw new ApiError('The server did not return a PDF. Try again.',response.status,'invalid_pdf');
    const blob=await response.blob();
    if (!(await blob.slice(0,5).text()).startsWith('%PDF-')) throw new ApiError('The downloaded file is not a valid PDF. Try again.',response.status,'invalid_pdf');
    const filename=response.headers.get('Content-Disposition')?.match(/filename="?([A-Za-z0-9_-]+\.pdf)"?/)?.[1] || 'txb-rm-briefing.pdf';
    return {blob,filename};
  },
  cases: params => request('/api/cases', { params }),
  case: id => request('/api/cases/' + encodeURIComponent(id)),
  updateCase: (id, body) => request('/api/cases/' + encodeURIComponent(id), { method: 'PUT', body }),
  followUp: (id, task, body) => request('/api/cases/' + encodeURIComponent(id) + '/follow-ups' + (task ? '/' + encodeURIComponent(task) + '/events' : ''), { method: 'POST', body }),
  months: () => request('/api/months'),
  summary: batch => request('/api/summary', { params: { batch_id: batch } }),
  monitoring: batch => request('/api/monitoring', { params: { batch_id: batch } }),
  customers: (batch, params) => request('/api/customers', { params: { batch_id: batch, ...params } }),
  customer: (id, batch) => request('/api/customers/' + encodeURIComponent(id), { params: { batch_id: batch } }),
  saveReview: (prediction, body) => request('/api/predictions/' + encodeURIComponent(prediction) + '/review', { method: 'PUT', body }),
};
