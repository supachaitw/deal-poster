#!/usr/bin/env python3
"""Post one MP4 to TikTok via Content Posting API (Direct Post, FILE_UPLOAD). Never prints tokens.

  tt_post.py <file.mp4> "<title>" [--sandbox] [--privacy SELF_ONLY|PUBLIC_TO_EVERYONE|MUTUAL_FOLLOW_FRIENDS] [--creator-only]

Flow: creator_info/query -> video/init (FILE_UPLOAD) -> PUT upload_url -> poll status/fetch.
Unaudited clients: privacy must be SELF_ONLY and the account must be private at post time.
"""
import os, sys, json, time, urllib.request

ENV = '/root/deal-video/service/' + '.' + 'env'
API = 'https://open.tiktokapis.com/v2/post/publish/'


def load_env():
    d = {}
    for l in open(ENV):
        l = l.rstrip('\n')
        if '=' in l and not l.startswith('#'):
            k, v = l.split('=', 1)
            d[k] = v
    return d


def call(url, token, body=None, method='POST', headers=None, raw=None):
    h = {'Authorization': 'Bearer ' + token}
    if headers: h.update(headers)
    data = raw if raw is not None else (json.dumps(body).encode() if body is not None else None)
    if data is not None and raw is None:
        h['Content-Type'] = 'application/json; charset=UTF-8'
    req = urllib.request.Request(url, data=data, headers=h, method=method)
    try:
        r = urllib.request.urlopen(req, timeout=120)
        txt = r.read().decode()
        return r.status, (json.loads(txt) if txt.strip().startswith('{') else txt)
    except urllib.error.HTTPError as e:
        txt = e.read().decode()[:500]
        try:
            return e.code, json.loads(txt)
        except Exception:
            return e.code, txt


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    sb = '--sandbox' in sys.argv
    privacy = 'SELF_ONLY'
    if '--privacy' in sys.argv:
        privacy = sys.argv[sys.argv.index('--privacy') + 1]
    P = 'TIKTOK_SB_' if sb else 'TIKTOK_'
    env = load_env()
    token = env[P + 'ACCESS_TOKEN']

    st, ci = call(API + 'creator_info/query/', token, body={})
    d = ci.get('data', {}) if isinstance(ci, dict) else {}
    print('creator_info:', st, json.dumps({'error': (ci.get('error') or {}).get('code') if isinstance(ci, dict) else ci,
                                           'nickname': d.get('creator_nickname'), 'privacy_options': d.get('privacy_level_options'),
                                           'max_duration': d.get('max_video_post_duration_sec'),
                                           'comment_disabled': d.get('comment_disabled'), 'duet_disabled': d.get('duet_disabled'),
                                           'stitch_disabled': d.get('stitch_disabled')}, ensure_ascii=False))
    if '--creator-only' in sys.argv or st != 200:
        return
    if privacy not in (d.get('privacy_level_options') or []):
        print('privacy %s not allowed for this creator; options=%s' % (privacy, d.get('privacy_level_options')))
        return

    path, title = args[0], args[1]
    size = os.path.getsize(path)
    body = {'post_info': {'title': title[:2200], 'privacy_level': privacy,
                          'disable_duet': False, 'disable_comment': False, 'disable_stitch': False,
                          'video_cover_timestamp_ms': 1000},
            'source_info': {'source': 'FILE_UPLOAD', 'video_size': size, 'chunk_size': size, 'total_chunk_count': 1}}
    st, init = call(API + 'video/init/', token, body=body)
    err = (init.get('error') or {}) if isinstance(init, dict) else {}
    print('init:', st, json.dumps({'error': err.get('code'), 'msg': err.get('message'), 'has_upload_url': bool((init.get('data') or {}).get('upload_url')) if isinstance(init, dict) else None,
                                   'publish_id_prefix': ((init.get('data') or {}).get('publish_id') or '')[:12] if isinstance(init, dict) else None}))
    if st != 200 or err.get('code') not in (None, 'ok'):
        return
    publish_id = init['data']['publish_id']
    upload_url = init['data']['upload_url']

    with open(path, 'rb') as f:
        blob = f.read()
    t0 = time.time()
    st, up = call(upload_url, token, method='PUT', raw=blob,
                  headers={'Content-Type': 'video/mp4', 'Content-Length': str(size),
                           'Content-Range': 'bytes 0-%d/%d' % (size - 1, size)})
    print('upload:', st, '%.1fs' % (time.time() - t0), 'bytes=%d' % size, (up if isinstance(up, str) else '')[:120])

    last = None
    for i in range(40):
        st, s = call(API + 'status/fetch/', token, body={'publish_id': publish_id})
        sd = (s.get('data') or {}) if isinstance(s, dict) else {}
        cur = (sd.get('status'), sd.get('fail_reason'), sd.get('publicaly_available_post_id'))
        if cur != last:
            print('status:', st, json.dumps({'status': sd.get('status'), 'fail_reason': sd.get('fail_reason'),
                                             'post_ids': sd.get('publicaly_available_post_id'),
                                             'uploaded_bytes': sd.get('uploaded_bytes'),
                                             'error': ((s.get('error') or {}).get('code') if isinstance(s, dict) else s)}))
            last = cur
        if sd.get('status') in ('PUBLISH_COMPLETE', 'FAILED'):
            break
        time.sleep(3)


if __name__ == '__main__':
    main()
