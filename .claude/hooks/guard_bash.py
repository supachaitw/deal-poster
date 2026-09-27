#!/usr/bin/env python3
"""PreToolUse hook (Bash) — กันผู้ช่วย print ความลับขึ้นจอ (27 ก.ย. 69 หลังหลุด 3 ครั้ง)
บล็อก (exit 2) เมื่อคำสั่งแตะ "แหล่งความลับ" แต่ไม่ได้กรองผ่าน scripts/redact.py และไม่ได้เก็บลงไฟล์/ตัวแปรแทนการพิมพ์
แหล่งความลับ: n8n API (workflows/credentials) · docker inspect · env/printenv · cat/less/head/tail/grep ไฟล์ .env · git show/diff ของ workflows/ ที่ยัง raw
ข้อยกเว้น: มี "| python3 scripts/redact.py" / "redact.py" ในคำสั่ง · หรือเป็น python heredoc ที่ไม่ print (ตรวจไม่ได้ → ผ่าน แต่เตือน)
"""
import json, re, sys
try:
    data = json.load(sys.stdin)
except Exception:
    sys.exit(0)
if data.get('tool_name') != 'Bash':
    sys.exit(0)
cmd = (data.get('tool_input') or {}).get('command') or ''
if 'redact.py' in cmd or 'n8n_get.py' in cmd or 'export_workflows.py' in cmd:
    sys.exit(0)
RISKY = [
    (r'api/v1/(workflows|credentials)', 'n8n API ดิบ'),
    (r'\bdocker\s+inspect\b', 'docker inspect (มี env/secret)'),
    (r'(^|[;&|]\s*)(env|printenv)\b', 'env/printenv'),
    (r'\b(cat|less|more|head|tail|grep|sed|awk)\b[^|;&]*\.env\b', 'อ่านไฟล์ .env'),
    (r'\becho\s+"?\$\{?(DP_|N8N_|AZURE_|SHOPEE_|LINE_|FB_|TG_|TELEGRAM_|NOTION_|BITKUB_)', 'echo ตัวแปรลับ'),
    (r'\bcurl\b[^|]*\b(api\.telegram\.org/bot|graph\.facebook\.com/[^ ]*access_token=)', 'URL ที่มี token'),
]
hits = [why for pat, why in RISKY if re.search(pat, cmd)]
if not hits:
    sys.exit(0)
# ถ้าเป็น curl -s ... ไป n8n แล้วต่อท่อเข้า python ที่ "ไม่ print ของดิบ" ตรวจไม่ได้ → ให้ผ่านเฉพาะเมื่อผลถูกเขียนลงไฟล์ (-o / > file) หรือ assign ตัวแปร
safe_sink = re.search(r'(-o\s+\S+|>\s*/\S+|=\$\()', cmd)
if safe_sink and 'print(' not in cmd:
    sys.exit(0)
# python heredoc: ตรวจไม่ได้ว่า print อะไร → ต้องประกาศเอง: import redact หรือมีมาร์กเกอร์ '# noraw' (= ยืนยันว่าไม่ print ค่าดิบจากแหล่งความลับ)
if re.search(r"python3?\s+-\s*<<\s*'?\w+'?", cmd) and ('redact' in cmd or '# noraw' in cmd):
    sys.exit(0)
sys.stderr.write('🔒 guard_bash: คำสั่งนี้แตะแหล่งความลับ (%s) และอาจพิมพ์ token ขึ้นจอ — เคยหลุดมาแล้ว 3 ครั้ง\n'
                 'ทำแบบใดแบบหนึ่ง: ต่อท่อ `| python3 scripts/redact.py` · ใช้ `python3 scripts/n8n_get.py <id> [node]` · '
                 'หรือเขียนลงไฟล์/ตัวแปรแล้วประมวลผลใน script โดยไม่ print ค่าดิบ (print เฉพาะฟิลด์ที่เลือกแล้ว redact)\n' % ', '.join(hits))
sys.exit(2)
