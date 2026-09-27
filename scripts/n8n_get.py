#!/usr/bin/env python3
"""ดู workflow จาก n8n API แบบปลอดภัย (ผ่าน redact เสมอ)
  python3 scripts/n8n_get.py <workflow_id>                 # รายชื่อ node + type + connections
  python3 scripts/n8n_get.py <workflow_id> "<node name>"   # พารามิเตอร์ของ node (jsCode/expression เต็ม) หลัง redact
  python3 scripts/n8n_get.py <workflow_id> "<node name>" --raw-to FILE   # เขียน JSON ดิบลงไฟล์ (ไม่ขึ้นจอ) ไว้ patch ต่อ
key: env N8N_KEY หรือ DP_N8N_KEY (บน VPS: set -a; . /root/home-metrics/.env; set +a)
"""
import json, os, sys, urllib.request
sys.path.insert(0, os.path.dirname(__file__))
from redact import redact

BASE = os.environ.get('N8N_BASE', 'https://n8n.srv1277799.hstgr.cloud')
KEY = os.environ.get('N8N_KEY') or os.environ.get('DP_N8N_KEY') or ''
if not KEY:
    sys.exit('need N8N_KEY / DP_N8N_KEY in env')
wid = sys.argv[1]
wf = json.loads(urllib.request.urlopen(urllib.request.Request(BASE + '/api/v1/workflows/' + wid, headers={'X-N8N-API-KEY': KEY}), timeout=60).read())
if len(sys.argv) == 2:
    print(redact('%s | active=%s | nodes=%d' % (wf['name'], wf['active'], len(wf['nodes']))))
    for n in wf['nodes']:
        print(redact('  %-28s %-40s v%s%s' % (n['name'], n['type'], n.get('typeVersion'), '  [disabled]' if n.get('disabled') else '')))
    print('connections:')
    for k, v in wf['connections'].items():
        outs = [[c['node'] for c in branch] for branch in v.get('main', [])]
        print(redact('  %s -> %s' % (k, outs)))
    sys.exit()
name = sys.argv[2]
node = next((n for n in wf['nodes'] if n['name'] == name), None)
if not node:
    sys.exit('no node named %r' % name)
if '--raw-to' in sys.argv:
    out = sys.argv[sys.argv.index('--raw-to') + 1]
    json.dump(node, open(out, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print('raw node written to', out, '(not printed)')
    sys.exit()
p = dict(node['parameters'])
code = p.pop('jsCode', None)
print(redact(json.dumps({k: v for k, v in node.items() if k not in ('parameters', 'credentials')}, ensure_ascii=False)))
print(redact(json.dumps(p, ensure_ascii=False, indent=1)))
if code is not None:
    print('---- jsCode ----')
    print(redact(code))
