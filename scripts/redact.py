#!/usr/bin/env python3
"""ตัวกรองความลับก่อนขึ้นหน้าจอ — ใช้เป็นท่อ:  <คำสั่ง> | python3 scripts/redact.py
หรือ  python3 scripts/redact.py <ไฟล์>

ทำไมต้องมี (27 ก.ย. 69): ผู้ช่วยเผลอ print token ออกทาง output ของเครื่องมือมาแล้ว 3 ครั้ง
(FB page token ตอน dump jsCode · Telegram bot token บางส่วนตอน print url ของ node · Bitkub HMAC secret ตอนดูพารามิเตอร์ Crypto node)
ทุกครั้งเกิดจาก "print ของดิบจาก n8n API / docker inspect / .env" → กติกา: ของพวกนี้ต้องผ่านตัวกรองนี้เสมอ
(hook ใน .claude/settings.json บังคับอีกชั้น: คำสั่งที่แตะแหล่งความลับแล้วไม่ต่อท่อมาที่นี่จะถูกบล็อก)

จับทั้งแบบรู้จัก (token รูปแบบเฉพาะ) และแบบทั่วไป (ค่าของคีย์ชื่อ secret/token/key/password/authorization + สตริงสุ่มยาว)
"""
import re, sys

KNOWN = [
    (re.compile(r'EAA[A-Za-z0-9]{40,}'), '<FB_TOKEN>'),
    (re.compile(r'TH[A-Z][A-Za-z0-9]{40,}'), '<THREADS_TOKEN>'),
    (re.compile(r'\d{6,}:[A-Za-z0-9_-]{30,}'), '<TELEGRAM_BOT_TOKEN>'),   # ไม่ใส่ \b เพราะมักติดกับ 'bot'
    (re.compile(r'sk-ant-[A-Za-z0-9_-]{10,}'), '<ANTHROPIC_KEY>'),
    (re.compile(r'eyJ[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}'), '<JWT>'),
    (re.compile(r'(?i)(bearer\s+)[A-Za-z0-9+/=_.-]{20,}'), r'\1<BEARER_TOKEN>'),
    (re.compile(r'\bntn_[A-Za-z0-9]{20,}'), '<NOTION_TOKEN>'),
    (re.compile(r'\bsecret_[A-Za-z0-9]{30,}'), '<NOTION_TOKEN>'),
    (re.compile(r'\bxox[abp]-[A-Za-z0-9-]{20,}'), '<SLACK_TOKEN>'),
    (re.compile(r'\bAKIA[0-9A-Z]{16}\b'), '<AWS_KEY>'),
    (re.compile(r'\bgh[pousr]_[A-Za-z0-9]{30,}'), '<GITHUB_TOKEN>'),
    (re.compile(r'\bglpat-[A-Za-z0-9_-]{20,}'), '<GITLAB_TOKEN>'),
]
# ค่าของคีย์ที่ชื่อบ่งบอกว่าเป็นความลับ — JSON ("secret": "..."), env (SECRET=...), header (X-API-Key: ...)
KEYNAMES = r'(?:secret|token|password|passwd|pwd|api[_-]?key|apikey|access[_-]?key|private[_-]?key|authorization|auth|credential|client[_-]?secret|signature|sig|key)'
KEYED = [
    re.compile(r'(?i)("(?:[a-z0-9_.-]*' + KEYNAMES + r'[a-z0-9_.-]*)"\s*:\s*")([^"]{8,})(")'),
    re.compile(r'(?i)(\b[A-Z0-9_]*' + KEYNAMES.upper().replace('(?:', '(?:') + r'[A-Z0-9_]*\s*=\s*["\']?)([^\s"\']{8,})(["\']?)'),
    re.compile(r'(?i)((?:x-api-key|ocp-apim-subscription-key|x-n8n-api-key|x-tts-access-token|api-key)\s*[:=]\s*["\']?)([^\s"\',]{8,})'),
]
# สตริงสุ่มยาว (hex ≥ 32 หรือ base64/alnum ≥ 40 ที่ไม่มีช่องว่าง) — กัน token รูปแบบที่ยังไม่รู้จัก · ยกเว้น URL path ธรรมดา/hash git สั้น
RANDOM = [
    (re.compile(r'(?<![/=\w])(?<!"id": ")(?<!"id":")[0-9a-f]{32,}(?![\w])'), '<HEX>'),   # ยกเว้น Notion page id ใน URL (/d/…, ?d=…) และ "id": "…"
    (re.compile(r'(?<![/\w.-])[A-Za-z0-9+/=_-]{48,}(?![\w/-])'), '<LONG_RANDOM>'),
]

def redact(text):
    for pat, rep in KNOWN:
        text = pat.sub(rep, text)
    for pat in KEYED:
        text = pat.sub(lambda m: m.group(1) + '<REDACTED>' + (m.group(3) if m.lastindex and m.lastindex >= 3 else ''), text)
    for pat, rep in RANDOM:
        text = pat.sub(rep, text)
    return text

if __name__ == '__main__':
    src = open(sys.argv[1], encoding='utf-8', errors='replace').read() if len(sys.argv) > 1 else sys.stdin.read()
    sys.stdout.write(redact(src))
