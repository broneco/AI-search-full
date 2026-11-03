// Run with node --test tests/frontend_resilience.cjs; no browser or real service required.
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const ts = require('../frontend-admin/node_modules/typescript');

test('context capacity follows result count and the effective metadata budget', () => {
  const source=fs.readFileSync(path.join(__dirname,'../frontend-admin/app/lib/contextCapacity.ts'),'utf8');
  const compiled=ts.transpileModule(source,{compilerOptions:{module:ts.ModuleKind.CommonJS}}).outputText;
  const module={exports:{}};new Function('exports',compiled)(module.exports);
  const estimate=module.exports.estimateContextCapacity;
  const data={sample:{tokens:200,characters:600,utf8_bytes:900},model:{context_tokens:8192,max_output_tokens:2048,reserved_tokens:256,max_input_chars:120000,input_guard_bytes:null}};
  let result=estimate(data,5);
  assert.equal(result.tokens,1000);assert.equal(result.budgetTokens,5888);assert.equal(result.basis,'context');
  assert.equal(estimate(data,10).tokens,2000);
  result=estimate({...data,model:{...data.model,context_tokens:null,max_input_chars:6000}},5);
  assert.equal(result.basis,'characters');assert.equal(result.budgetTokens,2000);assert.equal(result.percentage,50);assert.equal(result.approximate,true);
  result=estimate({...data,model:{...data.model,input_guard_bytes:900}},5);
  assert.equal(result.basis,'context');assert.equal(result.applicationPercentage,500);assert.equal(result.exceeds,true);
  assert.equal(estimate({...data,sample:null},5),null);assert.equal(estimate(data,0),null);
  const zero=estimate({...data,model:{...data.model,context_tokens:2048}},5);
  assert.equal(zero.budgetTokens,0);assert.equal(zero.percentage,null);assert.equal(zero.exceeds,true);
});

test('an index snapshot includes chunking and chosen task models, excluding ranking settings', () => {
  const source = fs.readFileSync(path.join(__dirname, '../frontend-admin/app/lib/chunkingSnapshot.ts'), 'utf8');
  const compiled = ts.transpileModule(source, {compilerOptions:{module:ts.ModuleKind.CommonJS}}).outputText;
  const module={exports:{}};new Function('exports',compiled)(module.exports);
  const snapshot=module.exports.chunkingSnapshot;
  assert.equal(snapshot(null,'',''),null);
  const config={chunk_size:300,chunk_overlap:40,chunking_strategy:'agentic',enrich_with_summary:true,vector_limit:200,summary_custom_prompt:'Shrň přesně'};
  const result=snapshot(config,'summary-selected','classification-selected');
  assert.deepEqual(result,{schema_version:1,chunk_size:300,chunk_overlap:40,chunking_strategy:'agentic',enrich_with_summary:true,summary_custom_prompt:'Shrň přesně',summary_model_id:'summary-selected',classification_model_id:'classification-selected'});
  assert.equal(snapshot({...config,enrich_with_summary:false,chunking_strategy:'standard'},'summary-selected','classification-selected').summary_model_id,undefined);
});

for (const frontend of ['frontend-admin', 'frontend-user']) {
  const source = fs.readFileSync(path.join(__dirname, '..', frontend, 'app/lib/apiRequest.ts'), 'utf8');
  const compiled = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText;
  const module = { exports: {} };
  new Function('exports', compiled)(module.exports);
  const { requestJson, ApiRequestError, chooseIndexSelection, chooseModelSelection, isExpiredSession, pollHealth } = module.exports;

  if (frontend === 'frontend-admin') test('registration chooses the exact embedding profile, never the first registry row', () => {
    const candidate = { candidate_id: 'new-space', name: 'nomic', digest: 'digest' };
    const expected = { id: 'new-space', kind: 'embedding', model: 'nomic', digest: 'digest' };
    const oldRecipe = { ...expected, id: 'old-recipe' };
    const rows = [{ ...expected, kind: 'chat', id: 'chat' }, oldRecipe, expected];
    assert.equal(module.exports.registeredEmbeddingId(candidate, rows), 'new-space');
    assert.equal(module.exports.registeredEmbeddingId(candidate, [oldRecipe]), undefined);
    assert.equal(module.exports.registeredEmbeddingId({ ...candidate, digest: 'changed' }, rows), undefined);
    assert.equal(module.exports.registeredEmbeddingId({ name:'nomic',digest:'digest' }, [oldRecipe,expected]), undefined);
  });

  test(`${frontend}: failed gateway replies, session ownership and recovery`, async () => {
    const original = global.fetch;
    try {
      global.fetch = async () => new Response('Service Unavailable: private proxy details', { status: 504 });
      await assert.rejects(requestJson('/config'), error => error instanceof ApiRequestError && error.status === 504 && !error.message.includes('private'));
      global.fetch = async () => new Response('<html>gateway timeout</html>', { status: 502 });
      await assert.rejects(requestJson('/models'), error => error instanceof ApiRequestError && error.status === 502);
      for (const status of [403, 422, 500, 503, 504]) assert.equal(isExpiredSession(new ApiRequestError(status, 'failure'), 'old', 'old'), false);
      assert.equal(isExpiredSession(new ApiRequestError(401, 'expired'), 'old', 'old'), true);
      assert.equal(isExpiredSession(new ApiRequestError(401, 'expired'), 'old', 'new'), false);
      global.fetch = async () => Response.json({ available: true });
      assert.deepEqual(await requestJson('/models'), { available: true });
      global.fetch = async () => new Response('not JSON', { status: 200 });
      await assert.rejects(requestJson('/models'), ApiRequestError);
    } finally { global.fetch = original; }
  });

  test(`${frontend}: timeouts cover response bodies; caller can abort`, async () => {
    const original = global.fetch;
    try {
      global.fetch = async (_url, { signal }) => ({ ok: true, status: 200,
        text: () => new Promise((_resolve, reject) => {
          if (signal.aborted) reject(new DOMException('aborted', 'AbortError'));
          else signal.addEventListener('abort', () => reject(new DOMException('aborted', 'AbortError')), { once: true });
        }) });
      await assert.rejects(requestJson('/slow-body', {}, { timeoutMs: 5 }), error => error instanceof ApiRequestError && error.status === 0);
      const controller = new AbortController();
      const pending = requestJson('/cancel', { signal: controller.signal });
      controller.abort();
      await assert.rejects(pending, error => error.name === 'AbortError');
    } finally { global.fetch = original; }
  });

  test(`${frontend}: retries recover defaults and preserve explicit index choices`, () => {
    const indexes = [{ index_id: 'default', ingestion_default: true, ready: true }];
    assert.equal(chooseIndexSelection('', indexes), 'default');
    assert.equal(chooseIndexSelection('explicit-missing', indexes), 'explicit-missing');
    assert.equal(chooseIndexSelection('', [{ ...indexes[0], ready: false }]), '');
    const models = [{ id: 'default', available: true }, { id: 'forbidden', available: false }];
    assert.equal(chooseModelSelection('', models, 'default'), 'default');
    assert.equal(chooseModelSelection('forbidden', models, 'default'), 'forbidden');
    assert.equal(chooseModelSelection('explicit-missing', models, 'default'), 'explicit-missing');
    assert.equal(chooseModelSelection('', models, 'forbidden'), '');
  });

  test(`${frontend}: health polling never overlaps and cleanup aborts without callbacks`, async () => {
    const original = global.fetch;
    let active = 0, peak = 0, calls = 0, statuses = 0;
    let stop;
    try {
      let started;
      const first = new Promise(resolve => { started = resolve; });
      global.fetch = (_url, { signal }) => new Promise((_resolve, reject) => {
        calls++; active++; peak = Math.max(peak, active); started();
        signal.addEventListener('abort', () => { active--; reject(new DOMException('aborted', 'AbortError')); }, { once: true });
      });
      stop = pollHealth('/health', () => { statuses++; }, { intervalMs: 1, timeoutMs: 1000 });
      await first;
      await new Promise(resolve => setTimeout(resolve, 15));
      assert.equal(calls, 1);
      stop();
      await new Promise(resolve => setTimeout(resolve, 10));
      assert.equal(active, 0);
      assert.equal(peak, 1);
      assert.equal(statuses, 0);
      assert.equal(calls, 1);
    } finally { stop?.(); global.fetch = original; }
  });
}
