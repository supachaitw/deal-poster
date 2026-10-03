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
# 3 ต.ค. 69: ผ่านได้เฉพาะเมื่อ 'ต่อท่อ' เข้า redact จริง (เดิมแค่มีคำว่า redact.py ที่ไหนก็ผ่าน) หรือใช้สคริปต์ที่ redact ในตัว
PIPED = re.search(r'\|\s*python3?\s+(\S*/)?scripts/redact\.py', cmd) is not None
if PIPED or re.search(r'scripts/(n8n_get|export_workflows|notion_secret)\.py', cmd):
    sys.exit(0)
RISKY = [
    (r'api/v1/(workflows|credentials)', 'n8n API ดิบ'),
    (r'api\.notion\.com|DP_NOTION|NOTION_TOKEN', 'Notion API (หน้า Config = ความลับทุกบล็อก — 3 ต.ค. 69 หลุด Azure key 35 ตัวจากการพิมพ์ "ตัวอย่างข้อความ")'),
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
# python heredoc: '# noraw' อย่างเดียวไม่พออีกแล้ว (3 ต.ค. 69 สคริปต์ที่มี # noraw พิมพ์ข้อความบล็อก Notion 40 ตัวแล้วหลุด) → ต้อง '# noraw' และต่อท่อ stdout เข้า redact.py ด้วย
if re.search(r"python3?\s+-\s*<<\s*'?\w+'?", cmd) and '# noraw' in cmd and PIPED:
    sys.exit(0)
sys.stderr.write('🔒 guard_bash: คำสั่งนี้แตะแหล่งความลับ (%s) และอาจพิมพ์ token ขึ้นจอ — เคยหลุดมาแล้ว 4 ครั้ง\n'
                 'ต้องทำ: heredoc ที่แตะแหล่งความลับต้องมี `# noraw` **และ** ปิดท้ายคำสั่งทั้งก้อนด้วย `| python3 scripts/redact.py` (เช่น `python3 - <<EOF ... EOF | python3 scripts/redact.py`) · '
                 'อ่านคีย์จาก Notion Config ใช้ `python3 scripts/notion_secret.py "<หัวข้อ>" --env FILE --key NAME` เท่านั้น · n8n ใช้ `scripts/n8n_get.py` · ห้าม print "ตัวอย่างข้อความ" ของบล็อก/ฟิลด์ลับแม้ตัดสั้น\n' % ', '.join(hits))
sys.exit(2)
