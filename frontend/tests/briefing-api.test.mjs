import test from 'node:test';
import assert from 'node:assert/strict';
import { api, ApiError } from '../src/api.js';

test('PDF adapter sends only selected IDs and snapshots, and returns an actual PDF blob',async()=>{
  const original=globalThis.fetch;
  globalThis.fetch=async(path,options)=>{
    assert.equal(path,'/api/briefings/pdf');
    assert.equal(options.method,'POST');
    assert.deepEqual(JSON.parse(options.body),{case_ids:['case-b','case-a'],snapshots:[{case_version:3}]});
    return new Response('%PDF-1.7\nexample',{headers:{'Content-Type':'application/pdf','Content-Disposition':'attachment; filename=txb-rm-briefing-2-cases.pdf'}});
  };
  try {
    const result=await api.downloadBriefing(['case-b','case-a'],[{case_version:3}]);
    assert.equal(result.filename,'txb-rm-briefing-2-cases.pdf');
    assert.match(await result.blob.text(),/^%PDF-/);
  } finally {globalThis.fetch=original;}
});

test('PDF adapter carries refreshed evidence on conflict and rejects a non-PDF success response',async()=>{
  const original=globalThis.fetch;
  try {
    globalThis.fetch=async()=>new Response(JSON.stringify({error:{code:'briefing_changed',message:'Review updated evidence'},briefing:{items:[]}}),{status:409,headers:{'Content-Type':'application/json'}});
    await assert.rejects(api.downloadBriefing(['case-a'],[]),e=>e instanceof ApiError && e.code==='briefing_changed' && e.briefing.items.length===0);
    globalThis.fetch=async()=>new Response('<html>Error</html>',{headers:{'Content-Type':'text/html'}});
    await assert.rejects(api.downloadBriefing(['case-a'],[]),e=>e.code==='invalid_pdf');
    globalThis.fetch=async()=>new Response('not a PDF',{headers:{'Content-Type':'application/pdf'}});
    await assert.rejects(api.downloadBriefing(['case-a'],[]),e=>e.code==='invalid_pdf');
  } finally {globalThis.fetch=original;}
});
