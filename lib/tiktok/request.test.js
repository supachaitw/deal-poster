'use strict';
const test = require('node:test');
const assert = require('node:assert');
const { ttRequest, TokenExpiredError, backoffDelay } = require('./request');
const { signRequest } = require('./sign');

const baseArgs = {
  endpoint: '/affiliate_creator/{version}/open_collaborations/products/search',
  version: '202405',
  appKey: 'k1',
  appSecret: 's1',
  accessToken: 'tok',
  now: () => 1700000000000,
  retry: { sleep: async () => {}, attempts: 3, baseDelayMs: 1 },
};

test('builds signed url with version substituted, token in header only', async () => {
  let seen;
  const res = await ttRequest({
    ...baseArgs,
    query: { page_size: 20 },
    body: { title_keywords: ['x'] },
    httpFn: async (req) => { seen = req; return { status: 200, json: { code: 0, data: { ok: 1 } } }; },
  });
  assert.deepStrictEqual(res.data, { ok: 1 });

  const url = new URL(seen.url);
  assert.strictEqual(url.pathname, '/affiliate_creator/202405/open_collaborations/products/search');
  assert.strictEqual(url.searchParams.get('app_key'), 'k1');
  assert.strictEqual(url.searchParams.get('timestamp'), '1700000000');
  assert.strictEqual(seen.headers['x-tts-access-token'], 'tok');
  assert.strictEqual(url.searchParams.get('access_token'), null);

  // signature must validate against the same inputs
  const expected = signRequest({
    appSecret: 's1',
    path: url.pathname,
    query: { page_size: 20, app_key: 'k1', timestamp: 1700000000 },
    body: '{"title_keywords":["x"]}',
  });
  assert.strictEqual(url.searchParams.get('sign'), expected);
});

test('retries on 429 then succeeds', async () => {
  let calls = 0;
  const res = await ttRequest({
    ...baseArgs,
    httpFn: async () => {
      calls++;
      if (calls < 3) return { status: 429, json: { code: 429, message: 'rate limit' } };
      return { status: 200, json: { code: 0, data: {} } };
    },
  });
  assert.strictEqual(calls, 3);
  assert.strictEqual(res.code, 0);
});

test('gives up after attempts exhausted', async () => {
  let calls = 0;
  await assert.rejects(
    ttRequest({ ...baseArgs, httpFn: async () => { calls++; return { status: 500, json: null }; } }),
    /retryable/
  );
  assert.strictEqual(calls, 3);
});

test('throws TokenExpiredError on 105002 without retrying', async () => {
  let calls = 0;
  await assert.rejects(
    ttRequest({
      ...baseArgs,
      httpFn: async () => { calls++; return { status: 200, json: { code: 105002, message: 'expired' } }; },
    }),
    TokenExpiredError
  );
  assert.strictEqual(calls, 1);
});

test('non-zero business code throws plain error', async () => {
  await assert.rejects(
    ttRequest({ ...baseArgs, httpFn: async () => ({ status: 200, json: { code: 36004004, message: 'invalid auth code' } }) }),
    /36004004/
  );
});

test('retries network errors', async () => {
  let calls = 0;
  const res = await ttRequest({
    ...baseArgs,
    httpFn: async () => {
      calls++;
      if (calls === 1) throw new Error('ECONNRESET');
      return { status: 200, json: { code: 0 } };
    },
  });
  assert.strictEqual(calls, 2);
  assert.strictEqual(res.code, 0);
});

test('backoffDelay grows exponentially with jitter within bounds', () => {
  for (let a = 0; a < 5; a++) {
    const exp = Math.min(1000 * 2 ** a, 30000);
    for (let i = 0; i < 20; i++) {
      const d = backoffDelay(a, 1000, 30000);
      assert.ok(d >= exp / 2 && d <= exp, `attempt ${a}: ${d} outside [${exp / 2}, ${exp}]`);
    }
  }
});

test('requires version when endpoint has {version} placeholder', async () => {
  await assert.rejects(
    ttRequest({ ...baseArgs, version: undefined, httpFn: async () => ({ status: 200, json: { code: 0 } }) }),
    /version is required/
  );
});
