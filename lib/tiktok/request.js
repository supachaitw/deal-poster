'use strict';
const { signRequest, serializeBody } = require('./sign');

const DEFAULT_HOST = 'https://open-api.tiktokglobalshop.com';

// Error thrown when the platform says the access token is expired/invalid —
// callers (n8n workflow / Token Keeper) catch this to trigger a refresh.
class TokenExpiredError extends Error {
  constructor(message, response) {
    super(message);
    this.name = 'TokenExpiredError';
    this.response = response;
  }
}

// TikTok business codes that mean "refresh the token and retry".
// 105001/105002 per creator-authorization guide; 36009005 observed live 30 ส.ค. 69
// ("Invalid credentials. The 'access_token' header is invalid", HTTP 401).
const TOKEN_ERROR_CODES = new Set([105001, 105002, 36009005]);

function defaultShouldRetry(status, json) {
  if (status === 429 || status >= 500) return true;
  // TikTok sometimes returns HTTP 200 with a throttling business code
  if (json && json.code === 429) return true;
  return false;
}

// ttRequest — signed request with per-endpoint version, retry + exponential backoff.
//
//   endpoint  '/affiliate_creator/{version}/open_collaborations/products/search'
//   version   '202405' — substituted into {version}
//   query     extra query params (page_size, page_token, ...) — app_key/sign/timestamp added here
//   body      object or exact string (must match what is signed)
//   accessToken  sent via x-tts-access-token header (not part of the signature)
//   httpFn    injectable: async ({method,url,headers,body}) => ({status, json})
//             n8n: wrap this.helpers.httpRequest · tests: mock
//   now       injectable clock (ms) for testability; defaults to Date.now
//   retry     { attempts, baseDelayMs, maxDelayMs, sleep } — sleep injectable for tests
async function ttRequest({
  host = DEFAULT_HOST,
  endpoint,
  version,
  method = 'POST',
  query = {},
  body = '',
  appKey,
  appSecret,
  accessToken,
  httpFn,
  now = () => Date.now(),
  retry = {},
}) {
  if (!endpoint) throw new Error('endpoint is required');
  if (!appKey || !appSecret) throw new Error('appKey and appSecret are required');
  if (typeof httpFn !== 'function') throw new Error('httpFn is required');
  if (endpoint.includes('{version}') && !version) throw new Error('version is required for this endpoint');

  const path = endpoint.replace('{version}', version || '');
  const attempts = retry.attempts ?? 4;
  const baseDelayMs = retry.baseDelayMs ?? 1000;
  const maxDelayMs = retry.maxDelayMs ?? 30000;
  const sleep = retry.sleep ?? ((ms) => new Promise((r) => setTimeout(r, ms)));
  const shouldRetry = retry.shouldRetry ?? defaultShouldRetry;

  const bodyStr = serializeBody(body);
  let lastErr;

  for (let attempt = 0; attempt < attempts; attempt++) {
    const q = {
      ...query,
      app_key: appKey,
      timestamp: Math.floor(now() / 1000),
    };
    q.sign = signRequest({ appSecret, path, query: q, body: bodyStr });

    const qs = Object.keys(q).map((k) => `${encodeURIComponent(k)}=${encodeURIComponent(q[k])}`).join('&');
    const url = `${host}${path}?${qs}`;
    const headers = { 'content-type': 'application/json' };
    if (accessToken) headers['x-tts-access-token'] = accessToken;

    let status, json;
    try {
      ({ status, json } = await httpFn({ method, url, headers, body: bodyStr || undefined }));
    } catch (err) {
      lastErr = err; // network-level failure — retry with backoff
      if (attempt < attempts - 1) {
        await sleep(backoffDelay(attempt, baseDelayMs, maxDelayMs));
        continue;
      }
      throw err;
    }

    if (json && TOKEN_ERROR_CODES.has(json.code)) {
      throw new TokenExpiredError(`token error ${json.code}: ${json.message}`, json);
    }
    if (shouldRetry(status, json)) {
      lastErr = new Error(`retryable response HTTP ${status} code ${json && json.code}`);
      if (attempt < attempts - 1) {
        await sleep(backoffDelay(attempt, baseDelayMs, maxDelayMs));
        continue;
      }
      throw lastErr;
    }
    if (status >= 400) throw new Error(`HTTP ${status}: ${JSON.stringify(json)}`);
    if (json && json.code !== 0) throw new Error(`TikTok error ${json.code}: ${json.message}`);
    return json;
  }
  throw lastErr;
}

function backoffDelay(attempt, baseDelayMs, maxDelayMs) {
  const exp = Math.min(baseDelayMs * 2 ** attempt, maxDelayMs);
  return Math.round(exp / 2 + Math.random() * (exp / 2)); // jitter: [exp/2, exp]
}

module.exports = { ttRequest, TokenExpiredError, backoffDelay, DEFAULT_HOST };
