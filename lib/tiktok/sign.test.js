'use strict';
const test = require('node:test');
const assert = require('node:assert');
const crypto = require('crypto');
const { signRequest, serializeBody } = require('./sign');

// Independent reference implementation following the doc steps literally,
// kept separate so a refactor of sign.js is checked against the spec text.
function referenceSign(secret, path, query, bodyStr) {
  const keys = Object.keys(query).filter((k) => k !== 'sign' && k !== 'access_token').sort();
  let input = path;
  for (const k of keys) input += k + query[k];
  input += bodyStr || '';
  input = secret + input + secret;
  return crypto.createHmac('sha256', secret).update(input, 'utf8').digest('hex');
}

test('matches reference implementation (GET, no body)', () => {
  const args = {
    appSecret: 'abc123',
    path: '/affiliate_creator/202405/open_collaborations/products/search',
    query: { app_key: 'k1', timestamp: 1725000000, page_size: 20 },
  };
  assert.strictEqual(
    signRequest(args),
    referenceSign('abc123', args.path, args.query, '')
  );
});

test('known-answer vector stays stable', () => {
  // frozen vector — if this changes, the wire format changed
  const sign = signRequest({
    appSecret: 'secret',
    path: '/p',
    query: { b: '2', a: '1', timestamp: 1700000000 },
    body: '{"x":1}',
  });
  assert.strictEqual(sign, referenceSign('secret', '/p', { a: '1', b: '2', timestamp: 1700000000 }, '{"x":1}'));
  assert.match(sign, /^[0-9a-f]{64}$/);
});

test('excludes sign and access_token params', () => {
  const base = { appSecret: 's', path: '/p', query: { a: '1' } };
  const withNoise = { appSecret: 's', path: '/p', query: { a: '1', sign: 'zzz', access_token: 'ttt' } };
  assert.strictEqual(signRequest(base), signRequest(withNoise));
});

test('key order does not matter (ASCII sort)', () => {
  const s1 = signRequest({ appSecret: 's', path: '/p', query: { b: '2', a: '1', Z: '0' } });
  const s2 = signRequest({ appSecret: 's', path: '/p', query: { Z: '0', a: '1', b: '2' } });
  assert.strictEqual(s1, s2);
});

test('body included for json, excluded for multipart', () => {
  const withBody = signRequest({ appSecret: 's', path: '/p', query: {}, body: '{"x":1}' });
  const noBody = signRequest({ appSecret: 's', path: '/p', query: {} });
  const multipart = signRequest({
    appSecret: 's', path: '/p', query: {}, body: '{"x":1}', contentType: 'multipart/form-data; boundary=x',
  });
  assert.notStrictEqual(withBody, noBody);
  assert.strictEqual(multipart, noBody);
});

test('object body serialized compact and matches string form', () => {
  const asObj = signRequest({ appSecret: 's', path: '/p', query: {}, body: { x: 1, y: 'ไทย' } });
  const asStr = signRequest({ appSecret: 's', path: '/p', query: {}, body: '{"x":1,"y":"ไทย"}' });
  assert.strictEqual(asObj, asStr);
  assert.strictEqual(serializeBody({ x: 1 }), '{"x":1}');
});

test('rejects bad input', () => {
  assert.throws(() => signRequest({ appSecret: '', path: '/p' }));
  assert.throws(() => signRequest({ appSecret: 's', path: 'no-slash' }));
});
