'use strict';
const crypto = require('crypto');

// TikTok Shop request signature (HMAC-SHA256) — per Partner Center "Sign your API request".
// Pure function: no clock, no network. Caller supplies timestamp inside `query`.
//
//   sign = hex(HMAC_SHA256(secret,
//            secret + path + concat(sorted {key}{value}) + body + secret))
//
// - query params `sign` and `access_token` are always excluded
// - keys sorted by ASCII (String.prototype.sort default)
// - body appended only when contentType is not multipart/form-data
// - body: pass the EXACT string that will be sent; objects are serialized with
//   JSON.stringify (compact) — then send that same serialization on the wire
function signRequest({ appSecret, path, query = {}, body = '', contentType = 'application/json' }) {
  if (!appSecret) throw new Error('appSecret is required');
  if (!path || !path.startsWith('/')) throw new Error('path must start with "/"');

  const paramString = Object.keys(query)
    .filter((k) => k !== 'sign' && k !== 'access_token')
    .sort()
    .map((k) => `${k}${query[k]}`)
    .join('');

  let input = path + paramString;

  const isMultipart = String(contentType).toLowerCase().startsWith('multipart/form-data');
  if (!isMultipart && body) {
    input += typeof body === 'string' ? body : JSON.stringify(body);
  }

  input = appSecret + input + appSecret;
  return crypto.createHmac('sha256', appSecret).update(input, 'utf8').digest('hex');
}

// Serialize a body object exactly as it must go on the wire to match the signature.
function serializeBody(body) {
  if (body == null || body === '') return '';
  return typeof body === 'string' ? body : JSON.stringify(body);
}

module.exports = { signRequest, serializeBody };
