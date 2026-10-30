// Run with node --test tests/frontend_resilience.cjs; no browser or real service required.
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const ts = require('../frontend-admin/node_modules/typescript');

for (const frontend of ['frontend-admin', 'frontend-user']) {
  const source = fs.readFileSync(path.join(__dirname, '..', frontend, 'app/lib/apiRequest.ts'), 'utf8');
  const compiled = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText;
  const module = { exports: {} };
  new Function('exports', compiled)(module.exports);
  const { requestJson, ApiRequestError, chooseIndexSelection, chooseModelSelection, isExpiredSession, pollHealth } = module.exports;

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
