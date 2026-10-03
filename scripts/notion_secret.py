#!/usr/bin/env python3
"""อ่านค่าลับจากหน้า Notion "🔐 Claude Daily Brief — Config" ใต้หัวข้อที่กำหนด แล้วเขียนลงไฟล์ env — ไม่พิมพ์ค่าใด ๆ ขึ้นจอ (3 ต.ค. 69)

  python3 scripts/notion_secret.py "<ข้อความในหัวข้อ>" --env /path/to/envfile --key ENV_NAME [--pattern REGEX]

- หา block (heading/paragraph/toggle) ที่มีข้อความหัวข้อ → รวมข้อความของ block นั้น + ลูกของมัน + block ถัดไปจนถึงหัวข้อถัดไป
- ดึงค่าด้วย --pattern (ค่าเริ่มต้น: token รูปแบบที่รู้จัก หรือสตริงไม่มีช่องว่างยาว ≥ 24 หลังป้าย Key:/key=/…)
- เขียน/แทนบรรทัด ENV_NAME= ในไฟล์ env (chmod 600, เขียนลง .new แล้ว os.replace)
- พิมพ์แค่: พบหัวข้อไหม · พบค่าไหม · ความยาว · 6 ตัวแรกของ prefix เมื่อเป็นรูปแบบที่รู้จัก (sk-ant-/ntn_/EAA) · ชื่อไฟล์ที่เขียน
ต้องมี DP_NOTION ใน env (set -a; . /root/home-metrics/.env; set +a)
"""
import os, re, sys, json, urllib.request

def main():
    args = sys.argv[1:]
    if not args or '--env' not in args or '--key' not in args:
        print(__doc__); sys.exit(1)
    heading = args[0]
    envp = args[args.index('--env') + 1]; name = args[args.index('--key') + 1]
    pat = args[args.index('--pattern') + 1] if '--pattern' in args else None
    tok = os.environ.get('DP_NOTION') or os.environ.get('NOTION_TOKEN')
    if not tok:
        print('need DP_NOTION in env'); sys.exit(1)
    H = {'Authorization': 'Bearer ' + tok, 'Notion-Version': '2022-06-28', 'Content-Type': 'application/json'}
    def api(path, body=None):
        req = urllib.request.Request('https://api.notion.com/v1/' + path, json.dumps(body).encode() if body is not None else None, H)
        return json.load(urllib.request.urlopen(req, timeout=30))
    res = api('search', {'query': 'Claude Daily Brief', 'filter': {'property': 'object', 'value': 'page'}})
    pages = [p for p in res['results'] if 'Config' in json.dumps(p.get('properties', {}), ensure_ascii=False)]
    if not pages:
        print('config page not found'); sys.exit(1)
    def children(bid):
        out, cur = [], None
        while True:
            r = api('blocks/%s/children?page_size=100' % bid + (('&start_cursor=' + cur) if cur else ''))
            out += r['results']
            if not r.get('has_more'): break
            cur = r['next_cursor']
        return out
    def txt(b):
        return ''.join(x.get('plain_text', '') for x in b.get(b['type'], {}).get('rich_text', []))
    def deep(b):
        t = txt(b)
        if b.get('has_children'):
            t += '\n' + '\n'.join(deep(c) for c in children(b['id']))
        return t
    blocks = children(pages[0]['id'])
    idx = [i for i, b in enumerate(blocks) if heading in txt(b)]
    if not idx:
        print('heading not found:', heading); sys.exit(1)
    i = idx[0]; chunk = [deep(blocks[i])]
    for b in blocks[i + 1:]:
        if b['type'].startswith('heading'): break
        chunk.append(deep(b))
    text = '\n'.join(chunk)
    text = re.sub(r'[\u200b\u200c\u200d\ufeff]', '', text)
    pats = [pat] if pat else [r'sk-ant-[A-Za-z0-9_-]{30,}', r'\bntn_[A-Za-z0-9]{20,}', r'\bsecret_[A-Za-z0-9]{30,}', r'EAA[A-Za-z0-9]{40,}',
                              r'(?i)(?:key|token|secret|password)\s*[:=：]\s*([^\s]{24,})', r'(?<![\w/])[A-Za-z0-9_+/=-]{32,}(?![\w/])']
    val = None
    for p in pats:
        m = re.search(p, text)
        if m:
            val = m.group(1) if m.groups() else m.group(0); break
    print('heading found: yes | value found:', bool(val), '| len:', len(val or ''), '| prefix:', (val or '')[:6] if val and re.match(r'(sk-ant|ntn_|EAA|secret_)', val) else '-')
    if not val: sys.exit(1)
    lines = []
    if os.path.exists(envp):
        lines = [l for l in open(envp).read().splitlines() if not l.startswith(name + '=')]
    lines.append(name + '=' + val)
    tmp = envp + '.new'
    with open(tmp, 'w') as f: f.write('\n'.join(lines) + '\n')
    os.chmod(tmp, 0o600); os.replace(tmp, envp)
    print('written %s to %s' % (name, envp))

if __name__ == '__main__':
    main()
