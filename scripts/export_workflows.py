#!/usr/bin/env python3
"""Export all Deal Poster workflows from n8n into workflows/*.json, sanitized.

Usage (on the VPS):  set -a; . /root/home-metrics/.env; set +a; python3 scripts/export_workflows.py
Other machines:       N8N_KEY=<n8n api key> python3 scripts/export_workflows.py

Only {name,nodes,connections,settings} are kept (the same shape PUT accepts).
Secrets are replaced by REPLACE_* placeholders by regex — the script refuses to
write a file that still contains anything secret-looking, and prints nothing secret.
"""
import json, os, re, sys, urllib.request

N8N = 'https://n8n.srv1277799.hstgr.cloud'
KEY = os.environ.get('N8N_KEY') or os.environ.get('DP_N8N_KEY')
if not KEY:
    sys.exit('need N8N_KEY (or DP_N8N_KEY from /root/home-metrics/.env)')

WORKFLOWS = {
    'E6i2xEAcaUsUFKWm': 'deal-poster-v1.json',
    'e8aD2wCvsVYmefrq': 'deal-caption-writer.json',
    'Kq3cRuTbwF9cMkA1': 'deal-intake-form.json',
    'JUE23JTCBbCsW1lS': 'deal-intake-telegram.json',
    '731A7ASm8bI0F79B': 'deal-intake-line.json',
    'UXGp6aS7EclTqCtl': 'threads-token-keeper.json',
    'teJKfYg0xuG9OSfc': 'deal-landing-page.json',
    'qHcCduq7ec3an1zk': 'tiktok-oauth-callback.json',
}

# order matters: the more specific patterns first
SANITIZE = [
    (r'EAA[A-Za-z0-9]{40,}', 'REPLACE_FB_PAGE_TOKEN'),
    (r'TH[A-Z][A-Za-z0-9]{40,}', 'REPLACE_THREADS_TOKEN'),
    (r'(?<=bot)\d{6,}:[A-Za-z0-9_-]{30,}', 'REPLACE_TELEGRAM_BOT_TOKEN'),
    (r'sk-ant-[A-Za-z0-9_-]{40,}', 'REPLACE_ANTHROPIC_API_KEY'),
    (r'eyJ[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}', 'REPLACE_N8N_API_KEY'),
    (r'(?<=Bearer )[A-Za-z0-9+/=_-]{60,}', 'REPLACE_LINE_CHANNEL_TOKEN'),
    (r'(?:ntn_|secret_)[A-Za-z0-9]{30,}', 'REPLACE_NOTION_TOKEN'),
]
# anything matching these after sanitizing = refuse to write
LEAK = re.compile(r'EAA[A-Za-z0-9]{40,}|TH[A-Z][A-Za-z0-9]{40,}|\d{6,}:[A-Za-z0-9_-]{30,}|sk-ant-|eyJ[A-Za-z0-9_-]{20,}\.|Bearer [A-Za-z0-9+/=_-]{60,}|ntn_|secret_[A-Za-z0-9]{30,}')

root = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'workflows')
for wid, fname in WORKFLOWS.items():
    req = urllib.request.Request(f'{N8N}/api/v1/workflows/{wid}', headers={'X-N8N-API-KEY': KEY})
    w = json.load(urllib.request.urlopen(req, timeout=30))
    out = {k: w[k] for k in ('name', 'nodes', 'connections', 'settings')}
    text = json.dumps(out, ensure_ascii=False, indent=2) + '\n'
    n_sub = 0
    for pat, rep in SANITIZE:
        text, n = re.subn(pat, rep, text)
        n_sub += n
    m = LEAK.search(text)
    if m:
        sys.exit(f'{fname}: secret-looking string left at offset {m.start()} (pattern {m.group(0)[:4]}…) — not written')
    with open(os.path.join(root, fname), 'w', encoding='utf-8') as f:
        f.write(text)
    print(f'{fname:28} nodes={len(out["nodes"]):2}  sanitized={n_sub:2}  active={w["active"]}  updated={w["updatedAt"][:16]}')
