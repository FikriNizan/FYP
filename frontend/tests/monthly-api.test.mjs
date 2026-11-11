import test from 'node:test';
import assert from 'node:assert/strict';
import { api, ApiError } from '../src/api.js';

test('monthly adapter sends exactly two files as multipart without overriding the boundary',async()=>{
  const original=globalThis.fetch;
  const csv=new File(['original bytes'],'features.csv');
  const manifest=new File(['{}'],'manifest.json');
  globalThis.fetch=async(path,options)=>{
    assert.equal(path,'/api/assessments'); assert.equal(options.method,'POST');
    assert.equal(options.credentials,'same-origin');
    assert.equal(options.headers['Content-Type'],undefined);
    assert(options.body instanceof FormData);
    assert.deepEqual([...options.body.keys()],['features','manifest']);
    assert.equal(await options.body.get('features').text(),'original bytes');
    return Response.json({batch_id:'exact-batch',already_imported:false},{status:201});
  };
  try { assert.equal((await api.uploadAssessment(csv,manifest)).batch_id,'exact-batch'); }
  finally { globalThis.fetch=original; }
});

test('monthly adapter preserves actionable errors and handles an unreadable server response',async()=>{
  const original=globalThis.fetch;
  try {
    globalThis.fetch=async()=>Response.json({error:{code:'assessment_conflict',message:'Cutoff already published'}},{status:409});
    await assert.rejects(api.uploadAssessment(new File([''],'f.csv'),new File([''],'m.json')),e=>e instanceof ApiError && e.status===409 && e.code==='assessment_conflict');
    globalThis.fetch=async()=>new Response('not JSON',{status:502});
    await assert.rejects(api.uploadAssessment(new File([''],'f.csv'),new File([''],'m.json')),e=>e.code==='invalid_response' && e.message.includes('Check saved assessments'));
  } finally { globalThis.fetch=original; }
});
