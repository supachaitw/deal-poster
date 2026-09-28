#!/usr/bin/env python3
"""TikTok Login Kit helper for Paiyaa Deals. Never prints tokens.

  tt_oauth.py exchange <code> [--sandbox]   exchange auth code (PKCE) -> tokens.json[mode] = {access_token, refresh_token, open_id, expires}
  tt_oauth.py refresh [--sandbox]            refresh access token
  tt_oauth.py whoami [--sandbox]             GET user/info (display_name, open_id prefix) to verify the connected account

client key/secret + PKCE verifier come from the service env file; tokens live in tokens.json
(mounted into the deal-video container as /tiktok/tokens.json so the service can refresh them itself).
"""
import os, sys, json, time, urllib.request, urllib.parse
ENV = '/root/deal-video/service/' + '.' + 'env'
TOKENS = '/root/deal-video/tiktok/tokens.json'
TOKEN_URL = 'https://open.tiktokapis.com/v2/oauth/token/'


def load_env():
    d = {}
    for l in open(ENV):
        l = l.rstrip('\n')
        if '=' in l and not l.startswith('#'):
            k, v = l.split('=', 1)
            d[k] = v
    return d


def load_tokens():
    try:
        return json.load(open(TOKENS))
    except Exception:
        return {}


def save_tokens(t):
    tmp = TOKENS + '.new'
    with open(tmp, 'w') as f:
        json.dump(t, f)
    os.chmod(tmp, 0o600)
    os.replace(tmp, TOKENS)


def post_form(url, data):
    req = urllib.request.Request(url, data=urllib.parse.urlencode(data).encode(),
                                 headers={'Content-Type': 'application/x-www-form-urlencoded'})
    try:
        return json.load(urllib.request.urlopen(req, timeout=30))
    except urllib.error.HTTPError as e:
        return {'http_error': e.code, 'body': e.read().decode()[:300]}


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    sb = '--sandbox' in sys.argv
    mode = 'sandbox' if sb else 'prod'
    P = 'TIKTOK_SB_' if sb else 'TIKTOK_'
    env = load_env()
    ck, cs = env[P + 'CLIENT_KEY'], env[P + 'CLIENT_SECRET']
    toks = load_tokens()
    cur = toks.get(mode) or {}
    cmd = args[0] if args else 'help'
    if cmd == 'exchange':
        code = urllib.parse.unquote(args[1])
        r = post_form(TOKEN_URL, {'client_key': ck, 'client_secret': cs, 'code': code, 'grant_type': 'authorization_code',
                                  'redirect_uri': env['TIKTOK_REDIRECT_URI'], 'code_verifier': env[P + 'CODE_VERIFIER']})
    elif cmd == 'refresh':
        r = post_form(TOKEN_URL, {'client_key': ck, 'client_secret': cs, 'grant_type': 'refresh_token',
                                  'refresh_token': cur['refresh_token']})
    elif cmd == 'whoami':
        req = urllib.request.Request('https://open.tiktokapis.com/v2/user/info/?fields=open_id,display_name',   # username needs user.info.profile (not requested)
                                     headers={'Authorization': 'Bearer ' + cur['access_token']})
        try:
            r = json.load(urllib.request.urlopen(req, timeout=30))
        except urllib.error.HTTPError as e:
            r = {'http_error': e.code, 'body': e.read().decode()[:300]}
        u = r.get('data', {}).get('user', {})
        print(json.dumps({'display_name': u.get('display_name'), 'open_id_prefix': (u.get('open_id') or '')[:6],
                          'expires_in_h': round((cur.get('expires', 0) - time.time()) / 3600, 1),
                          'error': (r.get('error') or {}).get('code'), 'http_error': r.get('http_error'), 'body': r.get('body')}, ensure_ascii=False))
        return
    else:
        print(__doc__)
        return
    if 'access_token' in r:
        toks[mode] = {'access_token': r['access_token'], 'refresh_token': r.get('refresh_token') or cur.get('refresh_token', ''),
                      'open_id': r.get('open_id') or cur.get('open_id', ''), 'expires': int(time.time()) + int(r.get('expires_in', 0))}
        save_tokens(toks)
        print(json.dumps({'ok': True, 'mode': mode, 'scope': r.get('scope'), 'expires_in': r.get('expires_in'),
                          'refresh_expires_in': r.get('refresh_expires_in'), 'open_id_prefix': (r.get('open_id') or '')[:6]}))
    else:
        print(json.dumps({k: v for k, v in r.items() if k in ('error', 'error_description', 'http_error', 'body', 'log_id')}))


if __name__ == '__main__':
    main()
