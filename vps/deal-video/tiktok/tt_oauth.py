#!/usr/bin/env python3
"""TikTok Login Kit helper for Paiyaa Deals. Never prints tokens.

  tt_oauth.py exchange <code> [--sandbox]   exchange auth code (PKCE) -> writes TIKTOK[_SB]_ACCESS_TOKEN / REFRESH_TOKEN / OPEN_ID / EXPIRES to the service env file
  tt_oauth.py refresh [--sandbox]            refresh access token
  tt_oauth.py whoami [--sandbox]             GET user/info (display_name, open_id prefix) to verify the connected account
"""
import os, sys, json, time, urllib.request, urllib.parse
ENV = '/root/deal-video/service/' + '.' + 'env'
TOKEN_URL = 'https://open.tiktokapis.com/v2/oauth/token/'


def load_env():
    d = {}
    for l in open(ENV):
        l = l.rstrip('\n')
        if '=' in l and not l.startswith('#'):
            k, v = l.split('=', 1)
            d[k] = v
    return d


def save_env(add):
    lines = [l.rstrip('\n') for l in open(ENV)]
    lines = [l for l in lines if not any(l.startswith(k + '=') for k in add)]
    lines += ['%s=%s' % (k, v) for k, v in add.items()]
    tmp = ENV + '.new'
    with open(tmp, 'w') as f:
        f.write('\n'.join(lines) + '\n')
    os.chmod(tmp, 0o600)
    os.replace(tmp, ENV)


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
    P = 'TIKTOK_SB_' if sb else 'TIKTOK_'
    env = load_env()
    ck, cs = env[P + 'CLIENT_KEY'], env[P + 'CLIENT_SECRET']
    cmd = args[0] if args else 'help'
    if cmd == 'exchange':
        code = urllib.parse.unquote(args[1])
        r = post_form(TOKEN_URL, {'client_key': ck, 'client_secret': cs, 'code': code, 'grant_type': 'authorization_code',
                                  'redirect_uri': env['TIKTOK_REDIRECT_URI'], 'code_verifier': env[P + 'CODE_VERIFIER']})
    elif cmd == 'refresh':
        r = post_form(TOKEN_URL, {'client_key': ck, 'client_secret': cs, 'grant_type': 'refresh_token',
                                  'refresh_token': env[P + 'REFRESH_TOKEN']})
    elif cmd == 'whoami':
        req = urllib.request.Request('https://open.tiktokapis.com/v2/user/info/?fields=open_id,display_name',   # username needs user.info.profile (not requested)
                                     headers={'Authorization': 'Bearer ' + env[P + 'ACCESS_TOKEN']})
        try:
            r = json.load(urllib.request.urlopen(req, timeout=30))
        except urllib.error.HTTPError as e:
            r = {'http_error': e.code, 'body': e.read().decode()[:300]}
        u = r.get('data', {}).get('user', {})
        print(json.dumps({'display_name': u.get('display_name'), 'username': u.get('username'),
                          'open_id_prefix': (u.get('open_id') or '')[:6], 'error': r.get('error'),
                          'http_error': r.get('http_error'), 'body': r.get('body')}, ensure_ascii=False))
        return
    else:
        print(__doc__)
        return
    if 'access_token' in r:
        save_env({P + 'ACCESS_TOKEN': r['access_token'],
                  P + 'REFRESH_TOKEN': r.get('refresh_token', env.get(P + 'REFRESH_TOKEN', '')),
                  P + 'OPEN_ID': r.get('open_id', ''),
                  P + 'EXPIRES': str(int(time.time()) + int(r.get('expires_in', 0)))})
        print(json.dumps({'ok': True, 'scope': r.get('scope'), 'expires_in': r.get('expires_in'),
                          'refresh_expires_in': r.get('refresh_expires_in'), 'open_id_prefix': r.get('open_id', '')[:6]}))
    else:
        print(json.dumps({k: v for k, v in r.items() if k in ('error', 'error_description', 'http_error', 'body', 'log_id')}))


if __name__ == '__main__':
    main()
