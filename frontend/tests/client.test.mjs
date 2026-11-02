import test from 'node:test';
import assert from 'node:assert/strict';
import { apiPath, request, ApiError } from '../src/api.js';
import { percent, money, forecastLabel, activityChange, escapeHtml } from '../src/format.js';

test('unknown financial values stay distinct from zero and risk uses a 0–1 scale', () => {
  assert.equal(money(null), 'Not provided');
  assert.notEqual(money(0), 'Not provided');
  assert.equal(percent(0), '0.0%');
  assert.equal(percent(0.844091949823281), '84.4%');
  assert.equal(percent(NaN), 'Not provided');
});
test('observed change and forecast use their own time definitions', () => {
  assert.equal(activityChange(214333.04,24622928.0491667), '99.1% lower');
  assert.equal(activityChange(100,0), 'Not provided');
  assert.equal(forecastLabel('2024-02-29'), 'Mar–May 2024');
  assert.equal(forecastLabel('2024-11-30'), 'Dec 2024–Feb 2025');
});
test('URLs retain explicit batch scope and encode customer search text', () => {
  const path = apiPath('/api/customers', {batch_id:'abc',q:'A&B',offset:0,flagged:false,decision:''});
  const parsed = new URL('http://localhost'+path);
  assert.equal(parsed.searchParams.get('q'), 'A&B');
  assert.equal(parsed.searchParams.get('batch_id'), 'abc');
  assert.equal(parsed.searchParams.get('flagged'), 'false');
  assert.equal(parsed.searchParams.get('offset'), '0');
  assert.equal(parsed.searchParams.has('decision'), false);
  assert.throws(() => apiPath('https://example.com/api'));
});
test('customer and review text are escaped before HTML insertion', () => {
  assert.equal(escapeHtml('<img src=x onerror="x">&'), '&lt;img src=x onerror=&quot;x&quot;&gt;&amp;');
});
test('review conflicts remain visible to the caller and never auto-retry', async () => {
  const original = globalThis.fetch;
  let calls=0;
  globalThis.fetch = async () => { calls++; return {ok:false,status:409,json:async()=>({error:{code:'review_conflict',message:'Reload this review'}})}; };
  try {
    await assert.rejects(request('/api/predictions/p/review',{method:'PUT',body:{expected_version:0}}), error => error instanceof ApiError && error.status===409 && error.code==='review_conflict');
    assert.equal(calls,1);
  } finally { globalThis.fetch=original; }
});
test('a non-JSON response produces a useful error', async () => {
  const original = globalThis.fetch;
  globalThis.fetch = async () => ({status:502,json:async()=>{throw new Error('not JSON');}});
  try { await assert.rejects(request('/api/health'),error=>error.code==='invalid_response' && error.status===502); }
  finally { globalThis.fetch=original; }
});
