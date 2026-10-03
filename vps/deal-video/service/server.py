# deal-video render service — รับข้อมูลดีล คืนคลิป Reels (mp4) แนวตั้ง 720x1280 พร้อมเสียงพากย์+เพลง
# รันใน container `deal-video` บน network n8n_default · n8n เรียก POST http://deal-video:8080/render
# body: {"name": str, "sale": num|null, "full": num|null, "img": url, "desc": str|null, "cat": str|null}
#       cat = property `หมวด` จาก Notion (บ้าน/gadget/ความงาม/…) ใช้เลือก hook เรียกกลุ่ม (รอบ #9) ไม่มีก็ได้
#       desc = คำบรรยายสินค้าสั้น ๆ — มีแล้วได้ทั้งท่อนพากย์และข้อความบนจอ, ไม่มีก็เรนเดอร์เหมือนเดิม
# (ใส่ "upload": {"url": rupload uri, "token": …} = อัปโหลดขึ้น IG ให้เลย ตอบ JSON แทนไฟล์)
# ตอบ 200 video/mp4 (header X-Voice: 1 = มีเสียงพากย์, 0 = TTS ล้มเลยได้แค่เพลง) · ผิดพลาด = 4xx/5xx JSON
# เรนเดอร์ทีละคลิป (HTTPServer ไม่ใช่ threaded) เพราะ VPS มี 1 core
import asyncio, base64, hashlib, json, math, os, re, shutil, subprocess, tempfile, time, traceback, urllib.error, urllib.parse, urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer

FONTS = '/app/fonts'
MUSIC = '/app/music/Carefree.mp3'
FPS = int(os.environ.get('FPS', '24'))   # #18: 30 → 24 (Reels รับได้ · วัด 11.0s → 9.7s)
# #18 27 ก.ย. 69 วัดบนคลิปเพลง 11.8 วิ (idle): graph เดิม veryfast 14.7s/745KB · graph ใหม่ (bg/fg ทำครั้งเดียว) veryfast 10.9s/715KB · superfast 10.1s/1.4MB · ultrafast 9.3s/4.2MB
# → คง veryfast (ไฟล์เท่าเดิม อัปโหลดไม่ช้าลง) · preset/crf/fps ตั้งผ่าน env ไว้ทดลอง
X264_PRESET = os.environ.get('X264_PRESET', 'veryfast')
X264_CRF = int(os.environ.get('X264_CRF', '22'))
VOICE = 'th-TH-NiwatNeural'   # ค่าหลัก + ตัวสำรอง edge-tts (edge-tts ไม่มี Krit)
# 27 ก.ย. 69 #16 user: "ใช้ Niwat สลับกับ K1" — สลับต่อดีลตาม hash ชื่อ (คงที่ ทำตัวอย่างซ้ำได้) · K1 = Krit MAI-Voice-2 ไม่ใส่สไตล์
# ⚠️ MAI-Voice-2 ไม่ตอบสนอง <prosody rate/pitch> (วัด 27 ก.ย.: rate -6% กับ 0% ยาวเท่ากัน) ใช้จังหวะธรรมชาติของมันเอง
# payload ใส่ "tts": "niwat"|"krit" เพื่อบังคับเสียง (ไว้ทำตัวอย่าง) · log: tts seg N ok (azure <key>)
VOICES = {'niwat': 'th-TH-NiwatNeural', 'krit': 'th-TH-Krit:MAI-Voice-2'}
VOICE_ORDER = ['niwat', 'krit']

# 27 ก.ย. 69 #17 — Gemini TTS (Google AI Studio) เป็นเสียงหลัก: user ฟัง 6 เสียงแล้ว "ok ทุกตัว" → สลับทั้ง 6 ตาม hash ชื่อ
# คำลงท้ายในบทเป็นชาย (ครับ/นะ) → เสียงหญิงแปลง ครับ→ค่ะ นะครับ→นะคะ ตอนสังเคราะห์ · ไม่มี SSML คุมสไตล์ด้วยประโยคสั่ง GEMINI_STYLE
# ล้ม/ชนโควตา (429) → ถอยทั้งคลิปไป Azure Niwat และตั้ง cooldown 90 วิ (ดีลถัดไปในรอบใช้ Azure เลย ไม่เสียเวลารอ retry)
# ⚠️ free tier ชน 429 ที่ ~5 คำขอ/นาที (5 ท่อน = 1 ดีล) → ใช้จริงต้องเปิด billing ของโปรเจกต์ที่ออก key · payload "tts": "gemini" | ชื่อเสียง (Puck…) | "niwat" | "krit"
GOOGLE_AI_KEY = os.environ.get('GOOGLE_AI_KEY', '').strip()
GEMINI_MODEL = 'gemini-3.8-flash-tts'
GEMINI_VOICES = [('Puck', 'm'), ('Achird', 'm'), ('Zubenelgenubi', 'm'), ('Leda', 'f'), ('Laomedeia', 'f'), ('Sulafat', 'f')]
# ⛔ ห้ามใส่คำสั่งสไตล์นำหน้าบท — วัด 27 ก.ย. 69: Gemini TTS อ่านคำสั่งออกเสียงไปด้วย (ท่อน 2.4 วิ → 4.1–13.5 วิ ตามความยาวคำสั่ง)
#   และ systemInstruction ใช้กับโมเดล TTS ไม่ได้ (400 'Developer instruction is not enabled') → ส่งข้อความล้วน ใช้โทนธรรมชาติของแต่ละเสียง
GEMINI_STYLE = ''
GEMINI_COOLDOWN_UNTIL = 0.0

def voice_for(seed, d=None):
    k = str((d or {}).get('tts') or '').strip()
    names = [v for v, _ in GEMINI_VOICES]
    if k in names and GOOGLE_AI_KEY:
        return 'gemini:' + k
    k = k.lower()
    if k in VOICES:
        return k
    if GOOGLE_AI_KEY and (k == 'gemini' or not k) and time.time() >= GEMINI_COOLDOWN_UNTIL:
        return 'gemini:' + names[(seed // 59) % len(names)]
    return VOICE_ORDER[(seed // 53) % len(VOICE_ORDER)]

def feminize(t):
    return t.replace('นะครับ', 'นะคะ').replace('ครับ', 'ค่ะ')

def gemini_tts(text, voice, out):
    """Gemini TTS: คืน wav (mime audio/wav) → แปลงเป็น mp3 ที่ out ด้วย ffmpeg · โยน exception เมื่อล้ม (429 รวมอยู่ด้วย)"""
    import base64
    body = {'contents': [{'parts': [{'text': GEMINI_STYLE + text}]}],
            'generationConfig': {'responseModalities': ['AUDIO'], 'speechConfig': {'voiceConfig': {'prebuiltVoiceConfig': {'voiceName': voice}}}}}
    req = urllib.request.Request('https://generativelanguage.googleapis.com/v1beta/models/%s:generateContent' % GEMINI_MODEL,
                                 json.dumps(body).encode('utf-8'), {'Content-Type': 'application/json', 'x-goog-api-key': GOOGLE_AI_KEY})
    r = json.loads(urllib.request.urlopen(req, timeout=60).read().decode('utf-8'))
    part = r['candidates'][0]['content']['parts'][0]['inlineData']
    raw = base64.b64decode(part['data']); mime = part.get('mimeType', '')
    src = out + '.src'
    open(src, 'wb').write(raw)
    if 'wav' in mime or raw[:4] == b'RIFF':
        cmd = ['ffmpeg', '-hide_banner', '-loglevel', 'error', '-y', '-i', src, '-b:a', '96k', out]
    else:   # raw L16 (เอกสารเก่า): audio/L16;codec=pcm;rate=24000
        m = re.search(r'rate=(\d+)', mime)
        cmd = ['ffmpeg', '-hide_banner', '-loglevel', 'error', '-y', '-f', 's16le', '-ar', m.group(1) if m else '24000', '-ac', '1', '-i', src, '-b:a', '96k', out]
    subprocess.run(cmd, check=True)
    os.remove(src)   # 27 ก.ย. 69: user ฟัง 8 เสียงเทียบแล้วเลือก Niwat (ชาย) — Premwadee "ฟังแล้วรู้ว่าเป็น AI" · บทเปลี่ยนคำลงท้ายเป็น ครับ/นะ ทั้งชุด

# ---------- ตัวเลขเป็นคำอ่านไทย (อ่านตัวเลขตรง ๆ ฟังเป็นหุ่นยนต์ที่สุด) ----------
DIG = ['ศูนย์', 'หนึ่ง', 'สอง', 'สาม', 'สี่', 'ห้า', 'หก', 'เจ็ด', 'แปด', 'เก้า']
UNIT = ['', 'สิบ', 'ร้อย', 'พัน', 'หมื่น', 'แสน']

# ตัวเลขในบทมีช่องว่างคั่นหน้า-หลังเสมอ (รอบ #11 26 ก.ย. 69): 'ลดไปตั้งสี่สิบเอ็ดเปอร์เซ็นต์' ติดกัน Azure อ่าน "เอ็ด" สูงเพี้ยน
# เทียบให้ user ฟัง 3 แบบ: ติดกัน / เว้นวรรค 'สี่สิบเอ็ด เปอร์เซ็นต์' / เลขอารบิก '41' → เว้นวรรคกับเลขอารบิกผ่านทั้งคู่ เลือกเว้นวรรค (คำอ่านไทยพิสูจน์แล้วกับหลักพัน)
def thai_words(n):
    return ' ' + _thai_words(n) + ' '

def _thai_words(n):
    n = int(round(n))
    if n == 0:
        return DIG[0]
    if n >= 1000000:
        return _thai_words(n // 1000000) + 'ล้าน' + (_thai_words(n % 1000000) if n % 1000000 else '')
    s = str(n)
    out = ''
    for i, ch in enumerate(s):
        d = int(ch)
        pos = len(s) - i - 1
        if d == 0:
            continue
        if pos == 1 and d == 1:
            out += 'สิบ'
        elif pos == 1 and d == 2:
            out += 'ยี่สิบ'
        elif pos == 0 and d == 1 and len(s) > 1:
            out += 'เอ็ด'
        else:
            out += DIG[d] + UNIT[pos]
    # "หนึ่งร้อย…" → "ร้อย…" แบบที่คนพูดจริง
    if out.startswith('หนึ่ง') and len(out) > 5:
        out = out[5:]
    return out

def approx_words(n):
    """329 → สามร้อยกว่า · 1290 → พันกว่า · 300 → สามร้อย"""
    n = int(round(n))
    if n < 100:
        return thai_words(n)
    m = 10 ** (len(str(n)) - 1)
    lead = n // m * m
    return ' ' + _thai_words(lead) + ('' if n == lead else 'กว่า') + ' '

def money(n):
    n = float(n)
    return '{:,.0f}'.format(n) if n == int(n) else '{:,.2f}'.format(n)

# ---------- ตัดชื่อสินค้าเป็นไม่เกิน 2 บรรทัด ----------
COMBINING = set(chr(c) for c in list(range(0x0E31, 0x0E32)) + list(range(0x0E34, 0x0E3B)) + list(range(0x0E47, 0x0E4F)))
LEADING_VOWEL = set('เแโใไ')

def safe_cut(s, i):
    # ห้ามตัดก่อนสระบน/ล่าง/วรรณยุกต์ (ตัวอักษรจะหลุดจากพยัญชนะ) และห้ามตัดหลังสระหน้า
    while 0 < i < len(s) and (s[i] in COMBINING or s[i] == 'ำ' or s[i - 1] in LEADING_VOWEL):
        i -= 1
    return i

def wrap_name(name, per_line=26, lines=2):
    name = ' '.join(name.split())
    out = []
    rest = name
    while rest and len(out) < lines:
        if len(rest) <= per_line:
            out.append(rest)
            rest = ''
            break
        cut = rest.rfind(' ', 0, per_line + 1)
        if cut < per_line * 0.5:
            cut = safe_cut(rest, per_line)
        out.append(rest[:cut].strip())
        rest = rest[cut:].strip()
    if rest:
        last = out[-1]
        if len(last) > per_line - 1:
            last = last[:safe_cut(last, per_line - 1)]
        out[-1] = last.rstrip() + '…'
    return out

# ---------- บทพูด ----------
HOOKS = ['เดี๋ยวนะ! อันนี้ต้องดู', 'ใครหาอยู่ ดูนี่เลย!', 'เดี๋ยวก่อน! ดีลนี้คุ้มมาก',
         'โอ้โห | อันนี้น่าสนใจ', 'บอกต่อเลย | ดีลนี้',
         # รอบ #7 (21 ก.ย. 69) — เปิดด้วยคำเชื่อมแบบคนพูดจริง ไม่ใช่ประโยคประกาศทุกอัน
         'คือว่า | เจอของดีมาอีกแล้วครับ', 'เอ้า | มาดูอันนี้กันหน่อย',
         'นี่ | กำลังหาอะไรแบบนี้อยู่รึเปล่า',
         # (รอบ #9 ตัด 'โอเค | อันนี้อยากให้ดูจริง ๆ' — "โอเค…" คือคำเปิดที่ทุกแหล่งปี 2026 บอกให้เลิก เสีย 2 วิแรกเปล่า)
         'เห็นแล้วต้องหยุดดูเลยอ่ะ', 'อันนี้นะครับ | เก็บไว้ก่อนเลย',
         # รอบ #9 (26 ก.ย. 69) — จากเทรนด์ TikTok ไทย ก.ย. 69: แฮชแท็กสาย "บอกต่อ" ติด 8/30 อันดับ · hook สั้น <12 คำ
         # สาย "บอกต่อ"
         'ของดีบอกต่อครับ | อันนี้', 'เจอแล้วต้องบอกต่อ | ไม่บอกไม่ได้', 'เพื่อนถามมาเยอะ | เอามาบอกต่อครับ',
         # สายคำถามด้วยคำลงท้าย (ห้ามใช้ '?' — ยังไม่ได้วัดว่า Azure เติมหยุดเท่าไร)
         'ใครกำลังมองหาอยู่มั้ยครับ | อันนี้เลย', 'เคยเห็นอันนี้กันรึยัง',
         # สาย Gen Z 2569 (คำเดียวต่อประโยค เสียงยังสุภาพ) — ⛔ คำทับศัพท์อังกฤษ (เทส/ชีเสิร์ฟ) Azure ไทยอ่านเพี้ยน ใช้ได้แต่คำไทย (ทำถึง/เริ่ด/ฉ่ำ)
         'ทำถึงในราคานี้ | ต้องดู', 'เริ่ดมากอันนี้ | มาดูกัน']   # ถอด 'เทสมาก' 26 ก.ย. 69 — user ฟังแล้ว Azure อ่านเพี้ยน
# รอบ #9 — hook สาย urgency แบบไม่โกหก: พูดถึง "ลดอยู่ตอนนี้" ซึ่งจริงเฉพาะดีลที่มีทั้งราคาเต็ม+ราคาลด
#    (ห้ามอ้างใกล้หมด/ถูกสุด — เราไม่รู้สต๊อกและไม่ได้เทียบราคา) ใช้ปนกับ HOOKS ปกติเมื่อมีส่วนลด
DISCOUNT_HOOKS = ['ราคานี้ | อยากให้เห็นตอนลดครับ', 'ตอนนี้ลดอยู่นะ | รีบดูก่อน']
# รอบ #9 — hook ชูตัวเลข (เทรนด์ 2026: บอกผลลัพธ์/ตัวเลขใน 2 วิแรกทำวิวดีสุด) ใช้กับดีลลด ≥ 20% ราวครึ่งหนึ่ง
#    %s = เปอร์เซ็นต์เป็นคำอ่าน · เมื่อใช้ hook นี้ ท่อนราคาจะไม่พูดเปอร์เซ็นต์ซ้ำอีก
PCT_HOOKS = ['ลด%sเปอร์เซ็นต์ครับ | ดูก่อนเลย', 'ถูกลง%sเปอร์เซ็นต์ | อันนี้ต้องดู', '%sเปอร์เซ็นต์นะครับ | ลดไปขนาดนี้']
PCT_HOOK_MIN = 20
# รอบ #9 — hook เรียกกลุ่ม (identity call) ตาม property `หมวด` ของ Notion ที่ n8n ส่งมาใน payload เป็น "cat"
#    ใช้ราว 1 ใน 3 ของดีลที่มีหมวด · ไม่มีหมวด/หมวดไม่รู้จัก = ข้ามไปใช้ hook ปกติ · ห้ามอ้างคุณภาพสินค้า
CAT_HOOKS = {
    'บ้าน': ['สายบ้านต้องดู | อันนี้', 'ใครชอบจัดบ้าน | มาดูอันนี้ครับ'],
    'gadget': ['สายไอที | ต้องดูอันนี้', 'ใครชอบของไอที | เก็บอันนี้ไว้ก่อน'],   # 'แก็ดเจ็ต' → 'สายไอที' 26 ก.ย. 69 (คำทับศัพท์อ่านเพี้ยน)
    'ความงาม': ['สายบิวตี้ | ดูอันนี้ก่อนครับ', 'ใครชอบของสวย ๆ | มาดูครับ'],
    'แฟชั่น': ['สายแฟชั่น | ต้องดูอันนี้', 'ใครชอบแต่งตัว | อันนี้เลยครับ'],
    'อาหาร': ['สายกิน | อันนี้ต้องดู', 'ใครชอบของอร่อย | มาทางนี้ครับ'],
    'รถ': ['สายรถ | ดูอันนี้ก่อนครับ', 'ใครมีรถ | อันนี้น่าสนใจนะ'],
    'สัตว์เลี้ยง': ['ทาสหมาทาสแมว | มาดูอันนี้ครับ', 'ใครมีน้องที่บ้าน | อันนี้เลย'],
    'Fitness': ['สายออกกำลังกาย | ต้องดูอันนี้', 'ใครฟิตอยู่ | มาดูครับ'],
    'กาแฟ': ['สายกาแฟ | อันนี้ต้องดูครับ', 'ใครติดกาแฟ | มาทางนี้เลย'],
}
# 28 ก.ย. 69 #20: IG จำกัดบัญชี 30 วัน (prohibited commercial practices) — CTA เลิกพูด 'ลิ้งค์ในไบโอ' ทุกคลิป → บอกชื่อเว็บ paiyaadeals.com เป็นคำพูด
# 2 ต.ค. 69: user ฟังแล้ว 'paiyaadeals.com' เพี้ยน (Gemini อ่านสะกด) → ส่งเทียบ 4 แบบ เลือก A/B → บทพูดใช้ 'ป้ายยาดีล ดอทคอม' (บนจอยังเขียน paiyaadeals.com)
# (Gemini อ่านโดเมนอังกฤษได้ · ถ้าถอยไป Azure Niwat อาจสะกดแปลก ยอมรับได้ช่วงนี้)
CTAS = ['ดูดีลนี้ได้ที่ ป้ายยาดีล ดอทคอม ครับ', 'รายละเอียดอยู่ที่ ป้ายยาดีล ดอทคอม นะ', 'สนใจ | เข้าไปดูที่ ป้ายยาดีล ดอทคอม ได้เลย',
        'เก็บไว้ก่อนได้ | ดีลนี้อยู่ที่ ป้ายยาดีล ดอทคอม', 'อยากได้ | ไปที่ ป้ายยาดีล ดอทคอม เลยครับ', 'ใครสนใจ | ดูได้ที่ ป้ายยาดีล ดอทคอม นะ',
        'ไปดูที่ ป้ายยาดีล ดอทคอม กันครับ | แล้วมาบอกกันว่าเป็นไง', 'ดีลเต็ม ๆ อยู่ที่ ป้ายยาดีล ดอทคอม | ฝากติดตามด้วยนะ']
# ท่อนนำก่อนคำบรรยาย / ราคา — เติมคำเชื่อมแบบพูดคุยแทนการยิงข้อมูลตรง ๆ (%s = เนื้อความเดิม)
#    ถ่วงน้ำหนักด้วยการใส่ '%s' เปล่าซ้ำหลายช่อง — คนพูดจริงไม่ได้ขึ้นต้นด้วยคำเชื่อมทุกประโยค
#    (รอบแรกให้น้ำหนักเท่ากัน 4 ช่อง แล้วลองรันกับดีลจริง 12 ตัว คำเชื่อมโผล่ 11/12 ฟังแล้วจะจำเจกว่าเดิม)
DESC_LEADS = ['%s', '%s', '%s', 'คือ | %s', 'ตัวนี้ | %s']
OLD_LINES = ['ปกติขายตั้ง%sบาท', 'คือปกติ | ขายตั้ง%sบาทนะครับ', 'ราคาเต็ม | ตั้ง%sบาทแน่ะ',
             'ปกติเห็นอยู่%sบาทนะครับ', 'ราคาป้าย | %sบาทครับ']   # รอบ #9
# 'บาทเอง' ติดกันไม่มีตัวคั่น — 26 ก.ย. 69 #14 user: "บาท,เอง ยังไม่ติดกัน แก้ให้ติดกันเลย" (ผ่านมา: '…' 0.14 → '… ' 1.3 → ', ' 0.33 → ไม่มี) · 'บาท, ฉ่ำมาก'/'บาท, เท่านั้น' คงลูกน้ำ
NEW_LINES = ['ตอนนี้เหลือแค่ | %sบาทเองครับ', 'แต่ตอนนี้ | เหลือแค่%sบาทเองครับ',
             'ลดมาเหลือ | %sบาทเอง',
             # รอบ #9 — ศัพท์ 2569 ในท่อนตื่นเต้น
             'ตอนนี้ | %sบาท, ฉ่ำมากครับ', '%sบาท, เท่านั้นครับตอนนี้']   # ถอด 'ชีเสิร์ฟ' 26 ก.ย. 69 — Azure อ่านเพี้ยน
# 'เองน้า' → 'เอง' 26 ก.ย. 69 #13: user ฟังแล้ว 'น้า' ท้าย 'เอง' ออกเสียงเป็น "เอง..นะ" แยกคำ → ตัดทิ้ง ('เองค่ะ' คงเดิม)
SALE_LINES = ['ตอนนี้ราคาแค่ | %sบาทเองครับ', 'ราคาแค่ | %sบาทเอง']
FULL_LINES = ['ราคา%sบาทครับ', 'ราคาอยู่ที่ | %sบาทครับ']
# ดีลที่ไม่มีราคาเลย: ใส่ท่อนกลางไว้ไม่ให้คลิปโล่ง (ห้ามอ้างว่าถูก/ใกล้หมด — เราไม่รู้ราคาด้วยซ้ำ)
NOPRICE = ['เดี๋ยวพาไปดูใกล้ ๆ นะครับ', 'ลองดูกันนะครับ | ว่าเป็นยังไง',
           'คือ | อยากให้ลองดูกันเอง', 'ตัวนี้ | ไปดูรายละเอียดกันนะ']
# 'ลิ้งค์' สะกดให้เสียงสูงตามที่คนพูดจริง (user 19 ก.ย. 69: 'ลิงก์' เสียงต่ำไป) — บนจอยังเขียน 'ลิงก์' ตามพจนานุกรม
# ⛔ ห้ามใช้ <prosody> ซ้อนเพื่อดันคำเดียว — Azure ไทยตัดเป็นคนละประโยค เติมหยุด ~2.7 วิ (วัดแล้ว 2.06 → 4.72 วิ)
# เครื่องหมาย ' | ' ในบท = หยุดหายใจสั้น ๆ ~0.33 วิ — แทนด้วย '… ' (ellipsis+space) ก่อนส่ง TTS (user 19 ก.ย. 69: คำในท่อนราคายังติดกัน)
# ⚠️ ช่องว่างรอบ ellipsis มีผลมาก (วัด 19 ก.ย. 69): ' … ' ≈ +1.1 วิ/จุด · '… ' ≈ +0.33 · '…' ติดคำ ≈ +0.09 — ต้องเป็น '… ' เท่านั้น
# ⛔ ห้ามใช้ SSML <break> — Azure เสียงไทยเติมหยุด ~1.4 วิต่อจุดไม่ว่า time= เท่าไร (วัดแล้ว: 5 จุด → ท่อน 4.5 วิกลายเป็น 12 วิ)
#    ', ' ≈ +0.33 วิเท่ากับ '… ' · '. ' ไม่หยุดเลย
PAUSE_MARK = '… '
# 'บาท, เองค่ะ' — ช่วง บาท→เอง วัดจริงด้วย ffprobe 26 ก.ย. 69 (Azure Premwadee): 'บาท…เอง' +0.14 วิ (user: ติดกันเกิน) · 'บาท… เอง' +1.3 วิ (user: ห่างเกิน
#   — หลัง 'บาท' Azure ถือ '… ' เป็นจบประโยค) · 'บาท, เอง' +0.33 วิ ← ใช้อันนี้ · ⚠️ ' | ' (= '… ') ที่อื่นในบทได้แค่ 0.17–0.31 วิ แต่ต่อท้าย 'บาท' เป็น 1.3 วิ อย่าใช้หลังหน่วยเงิน
# rate/pitch ต่อบทบาท: ท่อนเปิดเร็ว-สูง · ราคาเดิมเรียบ · ราคาใหม่ตื่นเต้น · ปิดช้าลงเป็นกันเอง
PROSODY = {'hook': ('+0%', '+4Hz'), 'desc': ('-6%', '+2Hz'), 'old': ('-10%', '+0Hz'), 'new': ('-12%', '+6Hz'), 'cta': ('-10%', '+2Hz')}   # 27 ก.ย. #15 เสียงชาย Niwat: pitch ลดครึ่งจากค่าที่จูนกับ Premwadee (+8/+4/0/+12/+4) · rate เดิม   # user 19 ก.ย. 69: เดิมเร็วไป (+14/+6/+10/+2) · 26 ก.ย. #10: ช้าลงอีก 4 ทุกท่อน (+4/-2/-6/-8/-6)
GAP_AFTER = {'hook': 0.55, 'desc': 0.5, 'old': 0.45, 'new': 0.65, 'cta': 0}   # เว้นวรรคระหว่างท่อนให้หายใจ (เดิม 0.18/0.12/0.32 ติดกันเกิน · #10 26 ก.ย.: 0.4/0.35/0.3/0.5 → +0.15 ทุกช่วง user ว่ายังไม่ดี)
# ขยับความเร็ว/ระดับเสียง/ช่วงเว้น รอบค่ากลางนิดหน่อยตามดีล (คงที่ต่อดีล ไม่ใช่สุ่มใหม่ทุกครั้ง)
# — คลิปหลายตัวเรียงกันในฟีดจะได้ไม่ฟังเหมือนอ่านสคริปต์ใบเดียวกันเป๊ะ ๆ
ROLE_BITS = {'hook': 0, 'desc': 40, 'old': 10, 'new': 20, 'cta': 30}

def jitter(seed, bits, span):
    return (((seed >> bits) % 1001) / 1000.0 * 2 - 1) * span

def prosody_for(role, seed):
    rate, pitch = PROSODY[role]
    b = ROLE_BITS[role]
    return ('%+d%%' % (int(rate.rstrip('%')) + int(round(jitter(seed, b, 2.5)))),
            '%+dHz' % (int(pitch.replace('Hz', '')) + int(round(jitter(seed, b + 5, 2.5)))))

def gap_for(role, seed):
    return max(0.15, GAP_AFTER[role] + jitter(seed, ROLE_BITS[role] + 7, 0.08))

# ---------- สลับรอบมีพากย์ / เพลงล้วน (22 ก.ย. 69) ----------
# user ขอให้สลับกับคลิปแบบไม่มีเสียงพากย์ (ยังมีเพลง) เป็นรอบ ๆ
# ตัดสินใจที่ service ไม่ใช่ที่ n8n → ไม่ต้องแตะ workflow ที่โพสต์ลง 4 แพลตฟอร์ม
# payload ส่ง "voice": true/false มา = บังคับ (เผื่อทดสอบมือ) · ไม่ส่ง = auto ตามรอบ
ROUND_HOURS = [0, 6, 9, 12, 15, 18, 21]   # ต้องตรงกับ cron ของ Deal Poster v1 — แก้ที่นั่นต้องแก้ที่นี่ด้วย

def voice_for_round(now=None):
    # Asia/Bangkok = UTC+7 ตลอดปี ไม่มี DST เลยบวกตรง ๆ ไม่ต้องพึ่ง tzdata ในคอนเทนเนอร์
    now = (now if now is not None else time.time()) + 7 * 3600
    hour = time.gmtime(now).tm_hour
    idx = max(i for i, h in enumerate(ROUND_HOURS) if h <= hour)
    # +วันด้วย เพื่อให้สลอตเดิมพลิกทุกวัน ไม่งั้น 00:00 จะมีพากย์ตลอดกาลและเทียบผลไม่ได้
    # (รอบ/วันเป็นเลขคี่ = 7 → ข้ามวันแล้วยังสลับต่อเนื่อง ไม่ซ้ำสองรอบติด)
    return ((int(now // 86400) + idx) % 2) == 0

def silent_durs(segs, budget=7.5, floor=1.0):
    # คลิปไม่มีพากย์ = คนต้องอ่านเอง แบ่งเวลาตามความยาวข้อความแทนการให้เท่ากันทุกท่อน
    # (เดิมตายตัว 1.3 วิ/ท่อน → คำบรรยาย 90 ตัวได้เวลาเท่า hook 20 ตัว อ่านไม่ทัน)
    # คุมด้วย budget รวม ความยาวคลิปเลยใกล้เคียงแบบมีพากย์ ไม่ยืดจนคนเลื่อนผ่าน
    w = [max(len(t), 8) for _, t in segs]
    tot = float(sum(w))
    return [max(floor, budget * x / tot) for x in w]

DESC_MAX = 90   # ตัวอักษร — ยาวกว่านี้ท่อนพากย์กินเวลาเกิน ~5 วิ และขึ้นจอ 2 บรรทัดไม่พอ

def clean_desc(s):
    # ข้อความมาจาก Claude ผ่าน Notion — ตัดลิงก์/แฮชแท็ก/อีโมจิออกให้เหลือที่อ่านออกเสียงได้
    s = ' '.join(str(s or '').split())
    s = re.sub(r'https?://\S+', '', s)
    s = re.sub(r'#\S+', '', s)
    s = ''.join(c for c in s if ord(c) < 0x2000)   # ทิ้งอีโมจิและเครื่องหมายพิเศษ
    s = ' '.join(s.split()).strip(' -|,.')
    if len(s) > DESC_MAX:
        s = s[:safe_cut(s, DESC_MAX)].rstrip() + '…'
    return s

# ---------- บทพูดไม่ซ้ำ (3 ต.ค. 69 #20 — user: "บทพูดเริ่มซ้ำ ๆ เดิม ให้คิดบทพูดให้ทันสมัยอยู่เรื่อย ๆ") ----------
# 2 ชั้น: (1) pool เดิมเลือกแบบ "ใช้ล่าสุดน้อยสุด" (LRU) จาก SCRIPT_LOG แทน hash ล้วน → ไม่ได้ยินสำนวนเดิมซ้ำในวันเดียวกัน
#         (2) ถ้ามี ANTHROPIC_API_KEY ในไฟล์ env ของ service → ให้ Haiku เขียน hook/desc/cta ใหม่รายดีลตาม STYLE_FILE (แนวเทรนด์ แก้ไฟล์ได้ไม่ต้อง deploy)
#             ผ่านด่านตรวจ (ไม่มีตัวเลข/คำทับศัพท์/'?'/อักษรอังกฤษนอกชื่อสินค้า, CTA ต้องมี 'ป้ายยาดีล ดอทคอม') ไม่ผ่าน/ล้ม/ช้า → ใช้ pool
#         ท่อนราคายังเป็นแม่แบบ + thai_words เสมอ (ไม่ให้ LLM พูดตัวเลข) · log ทุกคลิป '[script] src=… hook=…'
SCRIPT_LOG = os.environ.get('SCRIPT_LOG', '/tiktok/script_log.jsonl')
STYLE_FILE = os.environ.get('SCRIPT_STYLE_FILE', '/tiktok/script_style.txt')
LLM_SCRIPT_MODEL = os.environ.get('LLM_SCRIPT_MODEL', 'claude-sonnet-5')   # 3 ต.ค. 69 เทียบ 3 ดีล: Haiku 4.5 ไทยสะดุด ('เข้าไปยั่วเลย', 'รวด ๆ', แต่งสรรพคุณ) · Sonnet 5 เป็นธรรมชาติกว่า (~฿0.15/คลิป)
LLM_SCRIPT_KEY = os.environ.get('ANTHROPIC_API_KEY', '').strip()
LLM_SCRIPT = os.environ.get('LLM_SCRIPT', '1') == '1' and bool(LLM_SCRIPT_KEY)
LLM_SCRIPT_COOLDOWN_UNTIL = 0.0
SCRIPT_RECENT_N = 40
SCRIPT_BANNED = ('เทส', 'ชีเสิร์ฟ', 'แก็ดเจ็ต', 'ไบโอ', 'ลิงก์', 'ลิ้งค์', 'ใช้แล้ว', 'ถูกสุด', 'ใกล้หมด', 'โอเค')
STYLE_DEFAULT = """แนวบทพูดคลิปดีล TikTok ไทย (ต.ค. 2569) — แก้ไฟล์ /root/deal-video/tiktok/script_style.txt ได้เลยเมื่อเทรนด์เปลี่ยน
- 2 วินาทีแรกต้องมีเหตุให้หยุดดู: สถานการณ์ที่คนดูเจอเอง (เวลา…ทีไร / ใครเป็นแบบนี้บ้าง), เรียกกลุ่ม (สายกาแฟ, คนทำงานออฟฟิศ, ทาสแมว), บอกต่อ (เจอแล้วต้องบอก), ถามด้วยคำลงท้าย (…มั้ยครับ / …รึเปล่า)
- ภาษาพูดจริง สั้น เป็นกันเอง เหมือนเพื่อนเล่าให้ฟัง ไม่ใช่โฆษณาอ่านสคริปต์ · ห้ามเปิดด้วย "โอเค" "สวัสดีครับ" "วันนี้"
- ศัพท์ที่ยังใช้ได้ปี 2569: ทำถึง เริ่ด ฉ่ำ ปัง คุ้ม ของมันต้องมี สายประหยัด — ใช้ไม่เกิน 1 คำต่อบท ไม่ฝืน
- ท้ายคลิปชวนทำอะไรสักอย่างสลับกันไป: เซฟไว้ก่อน / ส่งให้เพื่อน / กดติดตาม / ไปดูที่เว็บ"""

def script_recent(n=SCRIPT_RECENT_N):
    try:
        lines = open(SCRIPT_LOG, encoding='utf-8').read().splitlines()[-n:]
        return [json.loads(l) for l in lines if l.strip()]
    except Exception:
        return []

def script_log(rec):
    try:
        rec['ts'] = time.strftime('%Y-%m-%d %H:%M', time.gmtime(time.time() + 7 * 3600))
        with open(SCRIPT_LOG, 'a', encoding='utf-8') as f:
            f.write(json.dumps(rec, ensure_ascii=False) + '\n')
        lines = open(SCRIPT_LOG, encoding='utf-8').read().splitlines()
        if len(lines) > 1000:
            tmp = SCRIPT_LOG + '.new'
            open(tmp, 'w', encoding='utf-8').write('\n'.join(lines[-600:]) + '\n')
            os.replace(tmp, SCRIPT_LOG)
    except Exception:
        pass

def pick(pool, h, recent_t):
    """เลือกจาก pool: ตัวที่ไม่ได้ใช้ในคลิปล่าสุดนานสุดก่อน (recent_t = แม่แบบที่ใช้ไป เรียงเก่า→ใหม่) · เสมอกัน = ตัวที่ใกล้ตำแหน่ง hash"""
    last = {}
    for i, t in enumerate(recent_t):
        last[t] = i
    n = len(pool)
    order = [pool[(h + i) % n] for i in range(n)]
    return min(order, key=lambda c: last.get(c, -1))

def script_ok(v, name):
    if '?' in v or '#' in v or v.count(' | ') > 2:
        return False
    for w in re.findall(r'\S*\d\S*', v):                                 # ตัวเลขใช้ได้เฉพาะที่เป็นส่วนของชื่อรุ่นในชื่อสินค้า (M4, 780ml) — ราคา/เปอร์เซ็นต์ห้าม
        if w.lower() not in (name or '').lower():
            return False
    if any(b in v for b in SCRIPT_BANNED):
        return False
    if re.search(r'[^฀-๿A-Za-z0-9 \|,\.!…\-\'"()%/+]', v):   # อิโมจิ/อักษรอื่น  # ตัวเลขผ่านด่านนี้ได้ แต่ถูกคุมด้วยกติกา "ต้องอยู่ในชื่อสินค้า" ด้านบน
        return False
    nm = (name or '').lower()
    for w in re.findall(r'[A-Za-z]+', v):
        if w.lower() not in nm:                                      # คำอังกฤษใช้ได้เฉพาะที่อยู่ในชื่อสินค้า
            return False
    return True

def llm_script(d, pct, recent):
    global LLM_SCRIPT_COOLDOWN_UNTIL
    if not LLM_SCRIPT or time.time() < LLM_SCRIPT_COOLDOWN_UNTIL:
        return None
    t0 = time.time()
    try:
        try:
            style = open(STYLE_FILE, encoding='utf-8').read().strip() or STYLE_DEFAULT
        except Exception:
            style = STYLE_DEFAULT
        name = (d.get('name') or '')[:120]
        desc = clean_desc(d.get('desc')) or ''
        avoid = [r.get('hook_t') for r in recent if r.get('hook_t')][-25:] + [r.get('cta_t') for r in recent if r.get('cta_t')][-12:]
        sys_p = ('คุณเขียนบทพูด (voice-over เสียงผู้ชาย ลงท้าย ครับ/นะครับ แบบธรรมชาติ ไม่ทุกประโยค) สำหรับคลิป TikTok แนะนำดีลสินค้า ยาว ~15 วินาที '
                 'ผู้พูดคือคนชอบแชร์ดีล ไม่ใช่คนขาย และยังไม่เคยใช้สินค้า\n'
                 'ตอบเป็น JSON อย่างเดียว: {"hook": "...", "desc": "...", "cta": "..."}\n'
                 '- hook: 1 ประโยค 4–12 คำ ดึงให้หยุดดูใน 2 วินาที ผูกกับสินค้า/หมวด/สถานการณ์ใช้งาน สลับสไตล์ไม่ซ้ำกับรายการ avoid\n'
                 '- desc: 1 ประโยคพูด ไม่เกิน 25 คำ เล่าว่าของคืออะไร ใช้ข้อมูลที่ให้เท่านั้น ห้ามเดาสเปก ถ้าข้อมูลไม่พอให้ส่งสตริงว่าง\n'
                 '- cta: 1 ประโยค ต้องมีคำว่า "ป้ายยาดีล ดอทคอม" (ชื่อเว็บแบบอ่าน) ตรงตามนี้ 1 ครั้ง สำนวนไม่ซ้ำกับ avoid\n'
                 'กติกาเสียง: ภาษาไทยล้วน · คำอังกฤษใช้ได้เฉพาะคำที่อยู่ในชื่อสินค้า และต้องสะกดอังกฤษตามเดิม ห้ามถอดเสียงเป็นไทย · '
                 'ห้ามมีตัวเลข ราคา เปอร์เซ็นต์ (ส่วนนั้นระบบพูดเอง) · ห้ามเครื่องหมาย ? อิโมจิ แฮชแท็ก · ใช้ " | " ได้ไม่เกิน 1 จุดต่อประโยคเป็นจังหวะหายใจ · '
                 'ห้ามอ้างว่าใช้แล้วดี ถูกสุด ใกล้หมด ของแท้ · ห้ามเติมสรรพคุณหรือผลลัพธ์ที่ไม่อยู่ในข้อมูล (เช่น ผ่อนคลายกล้ามเนื้อ อุ่นใจทั้งวัน ช่วยได้จริง) · ห้ามพูดถึงลิงก์หรือไบโอ · ทุกประโยคต้องสมบูรณ์ อ่านออกเสียงแล้วไม่สะดุด\n'
                 'แนวทางสไตล์ปัจจุบัน:\n' + style)
        user = json.dumps({'name': name, 'cat': d.get('cat') or '', 'desc': desc, 'has_discount': bool(pct),
                           'has_price': bool(d.get('sale') or d.get('full')), 'avoid': avoid}, ensure_ascii=False)
        body = {'model': LLM_SCRIPT_MODEL, 'max_tokens': 1500, 'temperature': 1.0, 'system': sys_p, 'thinking': {'type': 'disabled'},   # Sonnet 5 กับ prompt ยาวเคยคิด (thinking) จน max_tokens 300 หมดโดยไม่มี text (stop=max_tokens len=0) → ปิด thinking + เพดานกว้าง
                'messages': [{'role': 'user', 'content': user}]}
        req = urllib.request.Request('https://api.anthropic.com/v1/messages', json.dumps(body).encode('utf-8'),
                                     {'content-type': 'application/json', 'x-api-key': LLM_SCRIPT_KEY, 'anthropic-version': '2023-06-01'})
        j = None
        for attempt in range(2):   # ตอบไม่เป็น JSON (เกิดกับ Sonnet 1/3 ตอนเทส) → ยิงซ้ำ 1 ครั้ง
            r = json.load(urllib.request.urlopen(req, timeout=15))
            txt = ''.join(c.get('text', '') for c in r.get('content', []) if c.get('type') == 'text')
            m = re.search(r'\{.*\}', txt, re.S)
            if m:
                try:
                    j = json.loads(m.group(0)); break
                except Exception:
                    pass
            print('[script] llm non-json reply (attempt %d) stop=%s len=%d' % (attempt + 1, r.get('stop_reason'), len(txt)), flush=True)
        if j is None:
            return None
        out = {}
        for k_, lo, hi in (('hook', 6, 70), ('cta', 12, 90), ('desc', 8, 120)):
            v = re.sub(r'\s+', ' ', str(j.get(k_) or '')).replace('?', '').strip()
            good = bool(v) and lo <= len(v) <= hi and script_ok(v, name)
            if k_ == 'desc':
                out[k_] = v if good else None
                if v and not good:
                    print('[script] llm desc dropped (len %d)' % len(v), flush=True)
            elif good:
                out[k_] = v
            else:
                print('[script] llm reject %s=%r' % (k_, v[:60]), flush=True)
                return None
        if out['cta'].count('ป้ายยาดีล ดอทคอม') != 1:
            print('[script] llm reject cta (no site)', flush=True)
            return None
        print('[script] llm ok %.1fs' % (time.time() - t0), flush=True)
        return out
    except Exception as e:
        if isinstance(e, (urllib.error.URLError, TimeoutError, OSError)):   # API ล่ม/ช้า/429 → พัก 10 นาที · บั๊ก parse ไม่ต้องพัก
            LLM_SCRIPT_COOLDOWN_UNTIL = time.time() + 600
        print('[script] llm failed %s -> pool%s' % (str(e)[:100], ' (cooldown 10m)' if LLM_SCRIPT_COOLDOWN_UNTIL > time.time() else ''), flush=True)
        return None

def script_for(d):
    name, sale, full = d.get('name') or '', d.get('sale'), d.get('full')
    h = int(hashlib.md5(name.encode('utf-8')).hexdigest(), 16)
    pct = None
    if sale and full and full > sale:
        pct = round((full - sale) / full * 100)
    # เลือกชนิด hook (รอบ #9): เรียกกลุ่มตามหมวด → ชูตัวเลข → urgency ตอนลด → ปกติ · ทุกอย่างคงที่ต่อดีลด้วย hash ชื่อ
    cat = str(d.get('cat') or '').strip()
    pct_hook = False
    recent = script_recent()
    R = lambda key: [r.get(key) for r in recent if r.get(key)]
    rh, rc, ro, rn = R('hook_t'), R('cta_t'), R('old_t'), R('new_t')
    if cat in CAT_HOOKS and (h // 31) % 3 == 0:
        pool = CAT_HOOKS[cat]
        hook = hook_t = pick(pool, h // 37, rh)
    elif pct and pct >= PCT_HOOK_MIN and (h // 29) % 2 == 0:
        hook_t = pick(PCT_HOOKS, h // 41, rh)
        hook = hook_t % thai_words(pct)
        pct_hook = True
    elif pct and (h // 43) % 5 == 0:
        hook = hook_t = pick(DISCOUNT_HOOKS, h // 47, rh)
    else:
        hook = hook_t = pick(HOOKS, h, rh)
    L = llm_script(d, pct, recent)
    if L and not pct_hook:
        hook = hook_t = L['hook']
    segs = [('hook', hook)]
    desc = clean_desc(d.get('desc'))
    if desc and L and L.get('desc'):
        segs.append(('desc', L['desc']))
    elif desc:
        segs.append(('desc', DESC_LEADS[(h // 11) % len(DESC_LEADS)] % desc))
    old_t = new_t = None
    if pct:
        old_t = pick(OLD_LINES, h // 13, ro)
        segs.append(('old', old_t % approx_words(full)))
        tail = ''
        if pct_hook:
            tail = ''                      # hook พูดเปอร์เซ็นต์ไปแล้ว ไม่ซ้ำ
        elif pct >= 50:
            tail = ' | ลดไปเกินครึ่งเลยนะ'
        elif pct >= 15:
            tail = ' | ลดไปตั้ง%sเปอร์เซ็นต์แน่ะ' % thai_words(pct)
        new_t = pick(NEW_LINES, h // 17, rn)
        line = new_t % thai_words(sale)
        if tail and line.endswith('เอง'):
            tail = ',' + tail[2:]   # 'เอง | ลด…' → 'เอง, ลด…' — วัด 26 ก.ย. 69: 'เอง… ' Azure ถือจบประโยค หยุด 1.34 วิ · ', ' 0.58 · ('เองน้า… ' 0.43 แต่ user ให้ตัด น้า)
        segs.append(('new', line + tail))
    elif sale:
        new_t = pick(SALE_LINES, h // 19, rn)
        segs.append(('new', new_t % thai_words(sale)))
    elif full:
        new_t = pick(FULL_LINES, h // 23, rn)
        segs.append(('new', new_t % thai_words(full)))
    else:
        new_t = pick(NOPRICE, h // 3, rn)
        segs.append(('new', new_t))   # ไม่มีราคาเลย = คลิปจะเหลือแค่ hook+CTA (7 วิ) โล่งไป
    cta_t = L['cta'] if L else pick(CTAS, h // 7, rc)
    segs.append(('cta', cta_t))
    script_log({'name': name[:40], 'src': 'llm' if L else 'pool', 'hook_t': hook_t, 'cta_t': cta_t, 'old_t': old_t, 'new_t': new_t})
    print('[script] src=%s hook=%s' % ('llm' if L else 'pool', hook[:50]), flush=True)
    segs = [(r, re.sub(' {2,}', ' ', t).strip()) for r, t in segs]   # ช่องว่างซ้ำจาก thai_words/approx_words
    return segs, pct, h

# ---------- งานเสียง ----------
VOICE_FX = ('silenceremove=start_periods=1:start_threshold=-45dB:start_silence=0.04,areverse,'
            'silenceremove=start_periods=1:start_threshold=-45dB:start_silence=0.08,areverse,'
            'highpass=f=90,equalizer=f=200:t=q:w=1:g=1.5,equalizer=f=3500:t=q:w=1.2:g=2,'
            'acompressor=threshold=-20dB:ratio=2.5:attack=8:release=120:makeup=2,'
            'aecho=0.85:0.6:22|41:0.10|0.06')

def run(cmd):
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, timeout=240)

def dur(p):
    return float(subprocess.check_output(['ffprobe', '-v', 'error', '-show_entries', 'format=duration',
                                          '-of', 'default=nw=1:nk=1', p]))

AZ_KEY = os.environ.get('AZURE_SPEECH_KEY', '')

# ---------- Shopee affiliate link (27 ก.ย. 69) ----------
# user: "ส่งลิงก์ Shopee ไหนก็ได้ แล้วให้แปลงเป็นลิงก์ affiliate ให้" → ใช้ Shopee Affiliate Open API (GraphQL generateShortLink)
# creds ใน /root/deal-video/service/.env: SHOPEE_AFF_APP_ID / SHOPEE_AFF_SECRET (จากหน้า affiliate.shopee.co.th → Open API) — ไม่มี = ตอบ ok:false เฉย ๆ
# ลายเซ็น: Authorization: SHA256 Credential=<appId>, Timestamp=<unix s>, Signature=sha256(appId + timestamp + payload + secret)
# intake (Extract/Prep ใน 3 workflow) POST /afflink {url} → {ok, link, original, final, reason} · แปลงไม่ได้ intake ใช้ลิงก์เดิม
import hashlib
SHOPEE_AFF_APP_ID = os.environ.get('SHOPEE_AFF_APP_ID', '').strip()
SHOPEE_AFF_SECRET = os.environ.get('SHOPEE_AFF_SECRET', '').strip()
SHOPEE_AFF_ENDPOINT = 'https://open-api.affiliate.shopee.co.th/graphql'
UA_BROWSER = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36'

def is_shopee_affiliate(u):
    return bool(re.match(r'https?://(s\.shopee\.co\.th|shope\.ee)/', u or '', re.I))

def is_shopee(u):
    return bool(re.search(r'https?://([a-z0-9-]+\.)*(shopee\.co\.th|shp\.ee|shopee\.com)/', u or '', re.I))

def resolve_url(u, hops=6):
    """ตาม redirect ทีละขั้น (ไม่โหลด body) คืน URL ปลายทาง — th.shp.ee / shp.ee เป็นลิงก์แชร์จากแอป"""
    cur = u
    for _ in range(hops):
        req = urllib.request.Request(cur, method='HEAD', headers={'User-Agent': UA_BROWSER})
        class NoRedir(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, *a, **k):
                return None
        try:
            urllib.request.build_opener(NoRedir).open(req, timeout=10)
            return cur
        except urllib.error.HTTPError as e:
            loc = e.headers.get('Location')
            if e.code in (301, 302, 303, 307, 308) and loc:
                cur = urllib.parse.urljoin(cur, loc)
                # shopee universal-link ห่อปลายทางไว้ใน ?redir=
                q = urllib.parse.parse_qs(urllib.parse.urlparse(cur).query)
                if 'universal-link' in cur and q.get('redir'):
                    cur = q['redir'][0]
                continue
            return cur
        except Exception:
            return cur
    return cur

def shopee_product_url(u):
    """ทำ URL สินค้าให้สะอาด: https://shopee.co.th/<slug>-i.<shop>.<item> หรือ /product/<shop>/<item> → คืน None ถ้าไม่ใช่หน้าสินค้า/ร้าน"""
    p = urllib.parse.urlparse(u)
    if not re.search(r'(^|\.)shopee\.co\.th$', p.netloc, re.I) or p.netloc.lower().startswith('sv.'):
        return None
    m = re.search(r'-i\.(\d+)\.(\d+)', p.path) or re.search(r'/product/(\d+)/(\d+)', p.path)
    if m:
        return 'https://shopee.co.th/product/%s/%s' % (m.group(1), m.group(2))
    if re.match(r'^/[A-Za-z0-9_.]+/?$', p.path):          # หน้าร้าน /shopname
        return 'https://shopee.co.th' + p.path.rstrip('/')
    return None

def shopee_short_link(origin_url, sub_id='dealposter'):
    payload = json.dumps({'query': 'mutation{generateShortLink(input:{originUrl:%s,subIds:[%s]}){shortLink}}'
                          % (json.dumps(origin_url), json.dumps(sub_id))}, separators=(',', ':'))
    ts = str(int(time.time()))
    sig = hashlib.sha256((SHOPEE_AFF_APP_ID + ts + payload + SHOPEE_AFF_SECRET).encode('utf-8')).hexdigest()
    req = urllib.request.Request(SHOPEE_AFF_ENDPOINT, data=payload.encode('utf-8'), method='POST', headers={
        'Content-Type': 'application/json',
        'Authorization': 'SHA256 Credential=%s, Timestamp=%s, Signature=%s' % (SHOPEE_AFF_APP_ID, ts, sig)})
    body = json.loads(urllib.request.urlopen(req, timeout=15).read().decode('utf-8'))
    if body.get('errors'):
        raise RuntimeError(json.dumps(body['errors'], ensure_ascii=False)[:300])
    return body['data']['generateShortLink']['shortLink']

def tg_send_video(tg, mp4, caption):
    """28 ก.ย. 69: ส่งคลิปเข้า Telegram (ให้ user เอาไปอัปโหลด TikTok เอง — IG พักอยู่) · tg = {url: https://api.telegram.org/bot…/sendVideo, chat_id, caption}
    token มากับ request ภายใน network n8n_default เท่านั้น ไม่เก็บ/ไม่ log"""
    import uuid
    url = str(tg.get('url', ''))
    if not url.startswith('https://api.telegram.org/'):
        raise ValueError('telegram url must be api.telegram.org')
    b = uuid.uuid4().hex
    def part(name, val, fname=None, ct=None):
        h = '--%s\r\nContent-Disposition: form-data; name="%s"' % (b, name)
        if fname:
            h += '; filename="%s"\r\nContent-Type: %s' % (fname, ct)
        return h.encode() + b'\r\n\r\n' + (val if isinstance(val, bytes) else str(val).encode('utf-8')) + b'\r\n'
    body = (part('chat_id', tg.get('chat_id', '')) + part('caption', (caption or '')[:1000]) + part('supports_streaming', 'true')
            + part('video', mp4, 'deal.mp4', 'video/mp4') + ('--%s--\r\n' % b).encode())
    req = urllib.request.Request(url, body, {'Content-Type': 'multipart/form-data; boundary=' + b}, method='POST')
    r = json.loads(urllib.request.urlopen(req, timeout=120).read().decode('utf-8', 'replace'))
    return bool(r.get('ok')), (r.get('result') or {}).get('message_id')

def tg_send_photo(tg, jpg, caption):
    """2 ต.ค. 69: ส่งรูปสินค้า (binary — Telegram ดึงจาก Shopee/Lazada CDN เองไม่ได้) ให้ user เอาไปทำคลิป Veo เองใน aipass/Flow"""
    import uuid
    url = str(tg.get('url', '')).replace('/sendVideo', '/sendPhoto')
    if not url.startswith('https://api.telegram.org/'):
        raise ValueError('telegram url must be api.telegram.org')
    b = uuid.uuid4().hex
    def part(name, val, fname=None, ct=None):
        h = '--%s\r\nContent-Disposition: form-data; name="%s"' % (b, name)
        if fname:
            h += '; filename="%s"\r\nContent-Type: %s' % (fname, ct)
        return h.encode() + b'\r\n\r\n' + (val if isinstance(val, bytes) else str(val).encode('utf-8')) + b'\r\n'
    body = (part('chat_id', tg.get('chat_id', '')) + part('caption', (caption or '')[:1000]) + part('photo', jpg, 'product.jpg', 'image/jpeg') + ('--%s--\r\n' % b).encode())
    req = urllib.request.Request(url, body, {'Content-Type': 'multipart/form-data; boundary=' + b}, method='POST')
    r = json.loads(urllib.request.urlopen(req, timeout=60).read().decode('utf-8', 'replace'))
    return bool(r.get('ok')), (r.get('result') or {}).get('message_id')

# ---------- TikTok Content Posting API (28 ก.ย. 69) ----------
# โพสต์คลิปเข้า TikTok ตรงจาก service · client key/secret จาก env (TIKTOK_[SB_]CLIENT_KEY/SECRET) ·
# access/refresh token อยู่ในไฟล์ที่ mount มา (/tiktok/tokens.json — env ตรึงตอนสร้าง container จึงเก็บ token ที่ refresh ได้ในไฟล์)
# ยังไม่ผ่าน audit: privacy ต้อง SELF_ONLY และบัญชีต้อง private ตอนโพสต์ (TikTok ตอบ unaudited_client_can_only_post_to_private_accounts)
TIKTOK_TOKENS = os.environ.get('TIKTOK_TOKENS', '/tiktok/tokens.json')
TT_API = 'https://open.tiktokapis.com/v2/'

def tt_load():
    try:
        with open(TIKTOK_TOKENS) as f:
            return json.load(f)
    except Exception:
        return {}

def tt_save(t):
    tmp = TIKTOK_TOKENS + '.new'
    with open(tmp, 'w') as f:
        json.dump(t, f)
    os.chmod(tmp, 0o600)
    os.replace(tmp, TIKTOK_TOKENS)

def tt_http(url, token, body=None, method='POST', raw=None, headers=None):
    h = {'Authorization': 'Bearer ' + token}
    if headers:
        h.update(headers)
    data = raw
    if raw is None and body is not None:
        data = json.dumps(body).encode('utf-8'); h['Content-Type'] = 'application/json; charset=UTF-8'
    req = urllib.request.Request(url, data=data, headers=h, method=method)
    try:
        r = urllib.request.urlopen(req, timeout=120)
        txt = r.read().decode('utf-8', 'replace'); code = r.status
    except urllib.error.HTTPError as e:
        txt = e.read().decode('utf-8', 'replace')[:600]; code = e.code
    try:
        return code, json.loads(txt)
    except Exception:
        return code, {'raw': txt[:300]}

def tt_token(mode):
    """คืน access token ของโหมด (sandbox|prod) · เหลืออายุ < 30 นาที → refresh แล้วเขียนไฟล์"""
    P = 'TIKTOK_SB_' if mode == 'sandbox' else 'TIKTOK_'
    ck, cs = os.environ.get(P + 'CLIENT_KEY', ''), os.environ.get(P + 'CLIENT_SECRET', '')
    t = tt_load(); m = t.get(mode) or {}
    if not m.get('access_token'):
        raise RuntimeError('no tiktok token for ' + mode)
    if m.get('expires', 0) - time.time() < 1800:
        if not (ck and cs and m.get('refresh_token')):
            raise RuntimeError('tiktok token expired and cannot refresh')
        data = urllib.parse.urlencode({'client_key': ck, 'client_secret': cs, 'grant_type': 'refresh_token', 'refresh_token': m['refresh_token']}).encode()
        req = urllib.request.Request(TT_API + 'oauth/token/', data=data, headers={'Content-Type': 'application/x-www-form-urlencoded'})
        r = json.loads(urllib.request.urlopen(req, timeout=30).read().decode('utf-8'))
        if 'access_token' not in r:
            raise RuntimeError('tiktok refresh failed: ' + str(r.get('error_description') or r.get('error'))[:200])
        m = {'access_token': r['access_token'], 'refresh_token': r.get('refresh_token') or m['refresh_token'], 'open_id': r.get('open_id') or m.get('open_id', ''),
             'expires': int(time.time()) + int(r.get('expires_in', 86400))}
        t[mode] = m; tt_save(t)
        print('[tiktok] token refreshed (%s)' % mode, flush=True)
    return m['access_token']

# ---------- Facebook Reels ของเพจ (3 ต.ค. 69 user: "คลิปเคลื่อนไหวลงที่อื่นด้วยมั้ย" → "เริ่มเลย") ----------
# /render {fb_reel:{page_id, token, description}} → start (video_reels) → POST binary ไป rupload.facebook.com/video-reels → finish PUBLISHED → poll status ≤ 60 วิ
# token = page token ตัวเดียวกับ IG (มากับ request ใน n8n_default ไม่เก็บ/ไม่ log) · ล้ม = fb_reel.ok:false + HTTP 502 (TG/TikTok ที่ส่งไปแล้วไม่กระทบ)
FB_GRAPH = 'https://graph.facebook.com/v21.0/'

def fb_http(url, data=None, headers=None, method=None, raw=None, timeout=60):
    import urllib.parse
    body = raw if raw is not None else (urllib.parse.urlencode(data).encode() if data is not None else None)
    req = urllib.request.Request(url, data=body, headers=headers or {}, method=method)
    try:
        r = urllib.request.urlopen(req, timeout=timeout)
        return r.status, json.loads(r.read().decode('utf-8', 'replace') or '{}')
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode('utf-8', 'replace'))
        except Exception:
            return e.code, {}

def fb_reel_post(fr, mp4):
    """fr = {page_id, token, description} → {ok, video_id, post_id, status, phase, error, upload_s} (ไม่มี token)"""
    import urllib.parse
    out = {'ok': False}
    try:
        page, tok = str(fr.get('page_id') or ''), fr.get('token') or ''
        if not page or not tok:
            out['error'] = 'missing page_id/token'; return out
        c, r = fb_http(FB_GRAPH + page + '/video_reels', {'upload_phase': 'start', 'access_token': tok})
        vid = r.get('video_id')
        if c != 200 or not vid:
            out['error'] = 'start: ' + json.dumps(r.get('error') or r, ensure_ascii=False)[:200]; return out
        out['video_id'] = vid
        up_url = r.get('upload_url') or ('https://rupload.facebook.com/video-upload/v21.0/' + vid)   # ใช้ upload_url ที่ start คืนมา (path จริงคือ video-upload ไม่ใช่ video-reels — เจอ 3 ต.ค. 69 InvalidEndpointError)
        if not up_url.startswith('https://rupload.facebook.com/'):
            out['error'] = 'start: unexpected upload_url host'; return out
        t0 = time.time()
        c, r = fb_http(up_url, raw=mp4, method='POST', timeout=180,
                       headers={'Authorization': 'OAuth ' + tok, 'offset': '0', 'file_size': str(len(mp4)), 'Content-Type': 'application/octet-stream'})
        out['upload_s'] = round(time.time() - t0, 1)
        if c != 200 or not r.get('success'):
            out['error'] = 'upload: HTTP %s %s' % (c, json.dumps(r, ensure_ascii=False)[:200]); return out
        c, r = fb_http(FB_GRAPH + page + '/video_reels', {'upload_phase': 'finish', 'video_id': vid, 'video_state': 'PUBLISHED',
                                                         'description': (fr.get('description') or '')[:2000], 'access_token': tok})
        if c != 200 or not r.get('success'):
            out['error'] = 'finish: ' + json.dumps(r.get('error') or r, ensure_ascii=False)[:200]; return out
        out['post_id'] = r.get('post_id')
        for _ in range(12):
            c, s = fb_http(FB_GRAPH + vid + '?fields=status&access_token=' + urllib.parse.quote(tok))
            st = s.get('status') or {}
            out['status'] = st.get('video_status'); out['phase'] = (st.get('publishing_phase') or {}).get('status')
            if st.get('video_status') == 'error' or (st.get('processing_phase') or {}).get('status') == 'error':
                out['error'] = 'processing: ' + json.dumps(st, ensure_ascii=False)[:300]; return out
            if out['phase'] == 'complete' or st.get('video_status') == 'ready':
                break
            time.sleep(5)
        out['ok'] = True
        return out
    except Exception as e:
        out['error'] = str(e)[:200]; return out

def tt_post(tt, mp4):
    """tt = {mode: sandbox|prod, privacy: SELF_ONLY|PUBLIC_TO_EVERYONE|…, title} → dict สรุป (ไม่มี token)"""
    mode = tt.get('mode') or 'sandbox'; privacy = tt.get('privacy') or 'SELF_ONLY'
    out = {'ok': False, 'mode': mode, 'privacy': privacy}
    try:
        token = tt_token(mode)
        code, ci = tt_http(TT_API + 'post/publish/creator_info/query/', token, body={})
        cd = ci.get('data') or {}
        out['creator'] = cd.get('creator_nickname'); out['privacy_options'] = cd.get('privacy_level_options')
        if code != 200 or (ci.get('error') or {}).get('code') not in (None, 'ok'):
            out['error'] = 'creator_info: ' + str((ci.get('error') or {}).get('code') or code); return out
        if privacy not in (cd.get('privacy_level_options') or []):
            out['error'] = 'privacy_not_allowed'; return out
        body = {'post_info': {'title': (tt.get('title') or '')[:2200], 'privacy_level': privacy,
                              'disable_duet': False, 'disable_comment': False, 'disable_stitch': False, 'video_cover_timestamp_ms': 1000},
                'source_info': {'source': 'FILE_UPLOAD', 'video_size': len(mp4), 'chunk_size': len(mp4), 'total_chunk_count': 1}}
        code, init = tt_http(TT_API + 'post/publish/video/init/', token, body=body)
        ie = (init.get('error') or {})
        if code != 200 or ie.get('code') not in (None, 'ok'):
            out['error'] = 'init: ' + str(ie.get('code') or code); return out
        pid = init['data']['publish_id']; out['publish_id'] = pid
        t0 = time.time()
        code, up = tt_http(init['data']['upload_url'], token, method='PUT', raw=mp4,
                           headers={'Content-Type': 'video/mp4', 'Content-Length': str(len(mp4)), 'Content-Range': 'bytes 0-%d/%d' % (len(mp4) - 1, len(mp4))})
        out['upload_s'] = round(time.time() - t0, 1); out['upload_status'] = code
        if code not in (200, 201):
            out['error'] = 'upload: %s %s' % (code, str(up)[:200]); return out
        st = {}
        for i in range(20):
            time.sleep(3)
            code, s = tt_http(TT_API + 'post/publish/status/fetch/', token, body={'publish_id': pid})
            st = s.get('data') or {}
            if st.get('status') in ('PUBLISH_COMPLETE', 'FAILED'):
                break
        out['status'] = st.get('status'); out['post_ids'] = st.get('publicaly_available_post_id'); out['fail_reason'] = st.get('fail_reason')
        out['ok'] = st.get('status') == 'PUBLISH_COMPLETE'
        if not out['ok'] and not out.get('error'):
            out['error'] = 'status: ' + str(st.get('status')) + (' ' + str(st.get('fail_reason')) if st.get('fail_reason') else '')
    except Exception as e:
        out['error'] = str(e)[:300]
    return out

def afflink(u):
    u = (u or '').strip()
    out = {'ok': False, 'link': None, 'original': u, 'final': None, 'reason': ''}
    if not u or not is_shopee(u):
        out['reason'] = 'not a shopee url'; return out
    if is_shopee_affiliate(u):
        out.update(ok=True, link=u, final=u, reason='already affiliate'); return out
    final = resolve_url(u); out['final'] = final
    origin = shopee_product_url(final)
    if not origin:
        out['reason'] = 'no product in link (video/other share?)'; return out
    if not (SHOPEE_AFF_APP_ID and SHOPEE_AFF_SECRET):
        out['reason'] = 'no credentials'; out['origin'] = origin; return out
    try:
        out.update(ok=True, link=shopee_short_link(origin), origin=origin, reason='generated')
    except Exception as e:
        out['reason'] = 'api: ' + str(e)[:200]
    return out

AZ_REGION = os.environ.get('AZURE_SPEECH_REGION', 'eastus')

def azure_tts(text, rate, pitch, out, voice=VOICE):
    """Azure Speech (ทางการ) — key มาจาก .env ของ container · เสียงเดียวกับ edge-tts แต่เสถียร"""
    ssml = ('<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" xmlns:mstts="https://www.w3.org/2001/mstts" xml:lang="th-TH">'
            '<voice name="%s"><prosody rate="%s" pitch="%s">%s</prosody></voice></speak>'
            % (voice, rate, pitch, text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
               .replace(' | ', PAUSE_MARK)))
    r = urllib.request.Request('https://%s.tts.speech.microsoft.com/cognitiveservices/v1' % AZ_REGION,
                               data=ssml.encode('utf-8'), method='POST', headers={
                                   'Ocp-Apim-Subscription-Key': AZ_KEY, 'Content-Type': 'application/ssml+xml',
                                   'X-Microsoft-OutputFormat': 'audio-24khz-96kbitrate-mono-mp3', 'User-Agent': 'deal-video'})
    data = urllib.request.urlopen(r, timeout=30).read()
    if len(data) < 1000:
        raise ValueError('azure: empty audio')
    open(out, 'wb').write(data)

async def _tts(segs, W, seed, vkey='niwat'):
    global GEMINI_COOLDOWN_UNTIL
    if vkey.startswith('gemini:'):
        voice = vkey.split(':', 1)[1]
        gender = dict(GEMINI_VOICES).get(voice, 'm')
        failed = None
        for i, (role, text) in enumerate(segs):
            t = text.replace(' | ', ', ').replace('…', ',').replace(',,', ',')
            if gender == 'f':
                t = feminize(t)
            for k in range(3):
                try:
                    gemini_tts(t, voice, '%s/vo_%d.mp3' % (W, i))
                    failed = None
                    break
                except urllib.error.HTTPError as e:
                    body = ''
                    try:
                        body = e.read().decode('utf-8', 'replace')
                    except Exception:
                        pass
                    failed = 'HTTP %d' % e.code
                    if e.code == 429:
                        # free tier = 10 คำขอ/วัน/โมเดล (quotaId …PerDay…-FreeTier) → พัก 6 ชม. ถอย Azure ทันที
                        # paid tier (เปิด billing 27 ก.ย. 69) เหลือเพดานต่อนาที ~10 คำขอ (quotaId GenerateRequestsPerMinutePerProjectPerModel) → รอตาม retryDelay (≤20 วิ) แล้วลองใหม่ 1 ครั้ง ค่อยถอย
                        daily = 'PerDay' in body
                        if daily:
                            GEMINI_COOLDOWN_UNTIL = time.time() + 6 * 3600
                            failed = 'HTTP 429 (daily quota)'
                            break
                        m = re.search(r'retryDelay\W+(\d+)', body)
                        wait = min(int(m.group(1)) if m else 15, 20)
                        failed = 'HTTP 429 (per-minute quota)'
                        if k == 0:
                            print('gemini 429 per-minute → wait %ds' % wait, flush=True)
                            await asyncio.sleep(wait)
                            continue
                        GEMINI_COOLDOWN_UNTIL = time.time() + 60
                        break
                    await asyncio.sleep(2 * (k + 1))
                except Exception as e:
                    failed = str(e)[:80]
                    await asyncio.sleep(2 * (k + 1))
            if failed:
                print('gemini tts failed seg %d (%s): %s -> fallback azure niwat' % (i, voice, failed), flush=True)
                break
            print('tts seg %d ok (gemini %s)' % (i, voice), flush=True)
        if failed is None:
            return
        vkey = 'niwat'
    if AZ_KEY:
        last = None
        for i, (role, text) in enumerate(segs):
            rate, pitch = prosody_for(role, seed)
            for k in range(3):
                try:
                    azure_tts(text, rate, pitch, '%s/vo_%d.mp3' % (W, i), VOICES[vkey])
                    last = None
                    break
                except Exception as e:
                    last = e
                    await asyncio.sleep(2 * (k + 1))
            if last:
                print('azure tts failed seg %d: %s -> fallback edge-tts' % (i, last), flush=True)
                break
            print('tts seg %d ok (azure %s)' % (i, vkey), flush=True)
        if last is None:
            return
    # ทางสำรอง: edge-tts (ไม่เป็นทางการ) — ใช้เมื่อไม่มี key หรือ Azure ล้ม
    import edge_tts
    # edge-tts ตอบ NoAudioReceived แบบสุ่มบ่อยมาก (ข้อความเดิมรอบนี้ล้ม รอบหน้าผ่าน — วัด 19 ก.ย. 69 บางท่อนต้องลอง 4–6 ครั้ง)
    # → ลองซ้ำพร้อมถอยเวลา · ทางแก้จริงคือย้ายไป Azure Speech (ทางการ)
    for i, (role, text) in enumerate(segs):
        rate, pitch = prosody_for(role, seed)
        for k in range(8):
            try:
                await edge_tts.Communicate(text.replace(' | ', PAUSE_MARK), VOICE, rate=rate, pitch=pitch).save('%s/vo_%d.mp3' % (W, i))
                break
            except Exception:
                if k == 7:
                    raise
                await asyncio.sleep(1.5 * (k + 1))
        print('tts seg %d ok after %d tries' % (i, k + 1), flush=True)

def make_voice(segs, W, seed, vkey='niwat'):
    asyncio.run(asyncio.wait_for(_tts(segs, W, seed, vkey), timeout=150))
    wavs = []
    for i in range(len(segs)):
        wav = '%s/vo_%d.wav' % (W, i)
        run(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-y', '-i', '%s/vo_%d.mp3' % (W, i), '-af', VOICE_FX, wav])
        wavs.append(wav)
    return wavs

# ---------- ASS ----------
def ts(sec):
    return '%d:%02d:%05.2f' % (int(sec // 3600), int(sec % 3600 // 60), sec % 60)

def ass_escape(s):
    return s.replace('\\', '＼').replace('{', '(').replace('}', ')').replace('\n', ' ')

WHITE, GRAY, YELLOW = '&H00FFFFFF', '&H00E6E6E6', '&H003FD2FF'
HEAD = """[Script Info]
ScriptType: v4.00+
PlayResX: 720
PlayResY: 1280
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: B,Kanit,48,&H00FFFFFF,&H00FFFFFF,&H00000000,&H8C000000,-1,0,0,0,100,100,0,0,1,0,3,8,20,20,0,1
Style: R,Kanit,38,&H00FFFFFF,&H00FFFFFF,&H00000000,&H8C000000,0,0,0,0,100,100,0,0,1,0,3,8,20,20,0,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

# ---------- Veo (Google) ฉากสินค้าเคลื่อนไหวแทนรูปนิ่ง — ทดลอง 2 ต.ค. 69 (user: "ทำผ่าน API เลย ลอง 3 ดีลก่อน") ----------
# /render {"veo": true} → ส่งรูปสินค้าให้ Veo 3.1 Lite สร้างคลิป 8 วิ 9:16 720p (image-to-video) แล้วใช้เป็นพื้นหลังทั้งเฟรม
# แทน bg เบลอ+รูปซูม · ป้ายราคา/บทพากย์/เพลง เหมือนเดิม · ล้ม/ถูกกรอง/ช้าเกิน → ถอยไปเรนเดอร์แบบเดิม ไม่ถือว่าล้ม (ดู JSON `veo` / log [render] veo)
# ราคา Gemini API (ต.ค. 69): Lite $0.05/วินาที ≈ $0.40/คลิป · Fast $0.10/วิ · Standard $0.40/วิ · ใช้ key เดียวกับ Gemini TTS (GOOGLE_AI_KEY) billing เปิดแล้ว
# คลิป Veo 8 วิ สั้นกว่าคลิปเรา (~20 วิ) → ทำ boomerang (ไป-กลับ 16 วิ) แล้ว loop ตอนเรนเดอร์หลัก ไม่มีรอยต่อกระตุก
# ⚠️ ใช้เวลา ~1–3 นาที/คลิป (service เรนเดอร์ทีละคลิป → บล็อกคำขอถัดไป) ใส่ veo เฉพาะดีลเด่น 1 ตัว/รอบเท่านั้น
VEO_MODEL = os.environ.get('VEO_MODEL', 'veo-3.1-fast-generate-preview')   # 2 ต.ค. 69 user: 'ใช้ Fast' (Lite วาดของทรงเฉพาะผิดรุ่น) ≈ $0.80/คลิป
VEO_TIMEOUT = int(os.environ.get('VEO_TIMEOUT', '240'))
VEO_TRIM = float(os.environ.get('VEO_TRIM', '1.0'))   # วินาทีที่ตัดทิ้งจากหัวคลิป Veo (เฟรมแรก = รูปนิ่งต้นทาง)
# 2 ต.ค. 69 user: "ส่งให้ดูก่อนโพสต์ แล้วค่อยเปิดอัตโนมัติ" → /render {review:{url,chat_id,caption}} + veo:true
# Veo สำเร็จ = เก็บคลิปไว้ PENDING_DIR (mount /tiktok = /root/deal-video/tiktok บน host) + ส่งเข้า Telegram พร้อม '#veo <id>' บรรทัดแรก
# ไม่โพสต์ TikTok · user ตอบกลับ (reply) ข้อความนั้นว่า "โพสต์" → Intake TG เรียก POST /publish {id} → tt_post ด้วย tiktok opts ที่เก็บไว้ · "ไม่" → /discard
# Veo ล้ม/ข้าม/เกินโควตา → ทำแบบเดิม (telegram + tiktok ตรง) · คลิปค้าง > 48 ชม. ลบทิ้ง · โควตา Veo/วัน VEO_DAILY_MAX (นับใน /tiktok/veo_count.json เวลาไทย)
# 3 ต.ค. 69 user: 'คลิปที่คุณสร้างให้ โพสต์ได้เลย ผมค่อยไปดูเอง' → VEO_REVIEW=0 (ค่าเริ่มต้น) = Veo สำเร็จแล้วลง TikTok ตรง + ส่ง TG เป็นสำเนา (ไม่รอ reply)
# ตั้ง env VEO_REVIEW=1 ถ้าจะกลับไปใช้ขั้นรอตรวจ · ฟิลด์ review ยังต้องส่งมาเพราะ path 'รูป+prompt ให้ user ทำเอง' ใช้ url/chat_id จากมัน
VEO_REVIEW = os.environ.get('VEO_REVIEW', '0') == '1'
PENDING_DIR = os.environ.get('VEO_PENDING_DIR', '/tiktok/pending')
VEO_DAILY_MAX = int(os.environ.get('VEO_DAILY_MAX', '4'))   # 2 ต.ค. 69 user: 'ใช้ Fast 4 คลิป/วัน สลับกับผม gen ใน Flow เองแล้วส่งคลิปให้' → รอบ 00/06/09/12 ได้ Veo API, รอบ 15/18/21 user ส่งคลิปเอง
# คลิปที่ user สร้างเอง (Flow): ทุก /render ที่มี page_id จะเก็บข้อมูลดีลไว้ DEALS_DIR/<page_id>.json (7 วัน) และต่อท้าย caption ใน Telegram ด้วย '#d <page_id>'
# → user Reply ข้อความคลิปนั้นด้วยวิดีโอ → Intake TG (Extract) เห็น message.video + '#d <id>' → POST /render {deal_id, bg_video:<tg file url>, tiktok, telegram} → service เติมฟิลด์ดีลจากไฟล์ → ประกอบ+ลง TikTok ตรง (user ทำเองถือว่าอนุมัติแล้ว)
DEALS_DIR = os.environ.get('DEALS_DIR', '/tiktok/deals')

def deal_save(pid, d, title):
    try:
        os.makedirs(DEALS_DIR, exist_ok=True)
        now = time.time()
        for f in os.listdir(DEALS_DIR):
            fp = os.path.join(DEALS_DIR, f)
            if now - os.path.getmtime(fp) > 7 * 86400:
                os.remove(fp)
        rec = {k: d.get(k) for k in ('name', 'sale', 'full', 'desc', 'cat', 'img')} | {'title': title, 'saved': now}
        fr = d.get('fb_reel')
        if isinstance(fr, dict) and fr.get('token'):   # 3 ต.ค. 69 user: 'คลิปที่ผมส่งเองลง Facebook Reels ด้วย' → จำ page_id/token/description ไว้ให้ path deal_id (ไฟล์ 600 ใน volume /tiktok)
            rec['fb_reel'] = {'page_id': fr.get('page_id'), 'token': fr.get('token'), 'description': fr.get('description') or title}
        fp = os.path.join(DEALS_DIR, pid + '.json')
        json.dump(rec, open(fp, 'w'), ensure_ascii=False)
        os.chmod(fp, 0o600)
    except Exception:
        traceback.print_exc()

def deal_load(pid):
    try:
        return json.load(open(os.path.join(DEALS_DIR, pid + '.json')))
    except Exception:
        return None
VEO_COUNT_FILE = os.environ.get('VEO_COUNT_FILE', '/tiktok/veo_count.json')

def safe_id(x):
    return re.sub(r'[^A-Za-z0-9_-]', '', str(x or ''))[:64]

def veo_quota_take():
    day = time.strftime('%Y-%m-%d', time.gmtime(time.time() + 7 * 3600))
    try:
        c = json.load(open(VEO_COUNT_FILE))
    except Exception:
        c = {}
    n = int(c.get(day, 0))
    if n >= VEO_DAILY_MAX:
        return False
    try:
        os.makedirs(os.path.dirname(VEO_COUNT_FILE), exist_ok=True)
        json.dump({day: n + 1}, open(VEO_COUNT_FILE, 'w'))
    except Exception:
        traceback.print_exc()
    return True

def pending_path(pid, ext):
    return os.path.join(PENDING_DIR, pid + ext)

def pending_save(pid, mp4, meta):
    os.makedirs(PENDING_DIR, exist_ok=True)
    now = time.time()
    for f in os.listdir(PENDING_DIR):
        fp = os.path.join(PENDING_DIR, f)
        try:
            if now - os.path.getmtime(fp) > 48 * 3600:
                os.remove(fp)
        except Exception:
            pass
    open(pending_path(pid, '.mp4'), 'wb').write(mp4)
    json.dump(meta, open(pending_path(pid, '.json'), 'w'), ensure_ascii=False)

def pending_load(pid):
    try:
        return json.load(open(pending_path(pid, '.json'))), open(pending_path(pid, '.mp4'), 'rb').read()
    except Exception:
        return None, None

def pending_drop(pid, state=None):
    for ext in ('.mp4', '.json'):
        try:
            os.remove(pending_path(pid, ext))
        except Exception:
            pass
    if state:   # 2 ต.ค. 69: จำผลไว้ 48 ชม. ให้ตอบ user ได้ว่า "ลงไปแล้ว/ทิ้งไปแล้ว เมื่อ …" แทน "ไม่มีคลิปค้าง" (user ตอบซ้ำแล้วงง)
        try:
            json.dump({'state': state, 'at': time.strftime('%H:%M', time.gmtime(time.time() + 7 * 3600))}, open(pending_path(pid, '.done'), 'w'))
        except Exception:
            pass
VEO_PROMPT = ('Realistic e-commerce product video of the exact item shown in the reference image. '
              'The product sits on a clean neutral surface and slowly rotates while the camera slowly orbits around it, soft natural daylight, '
              'shallow depth of field, vertical 9:16 framing with the product centered in the upper half of the frame '
              'and empty space in the lower third. Keep the product colors, shape, proportions and printed details exactly as in the image. '
              'No people, no hands, no text, no captions, no logos, no watermarks, no extra products.')

def _boomerang(W, mp4, gen_s, model):
    # boomerang: reverse ต้องบัฟเฟอร์ทั้งคลิป (~190 เฟรม 720x1280 ≈ 260MB) ยังอยู่ในลิมิต --memory 700m
    t1 = time.time()
    # 2 ต.ค. 69: Veo (ทั้ง API image-to-video และ Flow frames-to-video) เริ่มจากรูปต้นทางเป๊ะ ~1 วิแรก (มีขอบดำ/ตัวหนังสือบนรูป) และ boomerang พากลับมาอีกตอนท้าย → ตัดหัว VEO_TRIM วิ
    # 2 ต.ค. 69: Veo Fast (image-to-video จากรูปจัตุรัส) คืนคลิป 9:16 ที่มี**แถบดำบน/ล่างตลอดคลิป** → วัดแถบดำเองจากเฟรมเดียว (cropdetect ของ ffmpeg
    # บนฉากสว่างคืนกล่องเล็กกลางเฟรม ใช้ไม่ได้) : อ่านเฟรมเป็น gray → หาแถวบน/ล่างที่ค่าเฉลี่ย < 24 → ครอปเฉพาะแถบเต็มความกว้าง (Lite ซูมเต็มเฟรมเอง = ไม่ครอป)
    pre = ''
    try:
        fw, fh = [int(x) for x in subprocess.check_output(['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries', 'stream=width,height', '-of', 'csv=p=0', W + '/veo.mp4']).decode().strip().split(',')[:2]]
        raw = subprocess.run(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-ss', str(VEO_TRIM + 1.0), '-i', W + '/veo.mp4', '-frames:v', '1', '-vf', 'format=gray', '-f', 'rawvideo', '-'],
                             capture_output=True, timeout=60).stdout
        if len(raw) >= fw * fh:
            def rowmean(y):
                r = raw[y * fw:(y + 1) * fw]
                return sum(r) / fw
            top = 0
            while top < fh // 3 and rowmean(top) < 24:
                top += 1
            bot = 0
            while bot < fh // 3 and rowmean(fh - 1 - bot) < 24:
                bot += 1
            if top + bot >= 80 and fh - top - bot >= 300:
                pre = 'crop=%d:%d:0:%d,' % (fw, fh - top - bot, top)
    except Exception:
        traceback.print_exc()
    print('[render] veo crop=%s' % (pre or 'none'), flush=True)
    run(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-y', '-ss', str(VEO_TRIM), '-i', W + '/veo.mp4', '-filter_complex',
         # 2 ต.ค. 69: boom.mp4 = 'ช่องบน' 720x790 โดยตรง — แนวนอน (aipass 16:9) ย่อให้สูง 790 พอดี (ตัดแค่ข้าง สินค้าเห็นเต็มตัว) · แนวตั้ง 9:16 (API) ย่อกว้าง 720 แล้วตัดเอาส่วนบน y 40 (สินค้าอยู่ครึ่งบนตาม prompt)
         # เดิมย่อเป็น 720x1280 แล้วค่อยตัด 790 → คลิปแนวนอนของ user ถูกซูม 1.78x สินค้าโดนตัดครึ่งใต้แถบมืด (user: 'แถบสีดำบังสินค้าหมดเลย')
         # 2 ต.ค. 69 (รอบ 3) user: 'เอาตัวหนังสือลง เอาสีดำออก ไม่ลดขนาดภาพ' → กลับเป็นเต็มเฟรม 720x1280 (scale increase + crop กลาง = เห็นสินค้าเต็มความสูงเสมอ) ตัวหนังสือย้ายลงล่าง+ขอบดำ ไม่มีแถบ
         f'[0:v]{pre}fps={FPS},scale=720:1280:force_original_aspect_ratio=increase,crop=720:1280,setsar=1,split[a][b];[b]reverse[r];[a][r]concat=n=2:v=1:a=0[v]',
         '-map', '[v]', '-an', '-c:v', 'libx264', '-preset', 'ultrafast', '-crf', '18', W + '/boom.mp4'])
    return {'ok': True, 'gen_s': gen_s, 'prep_s': round(time.time() - t1, 1), 'bytes': len(mp4), 'model': model, 'src_dur': round(dur(W + '/veo.mp4'), 1)}

def veo_clip(W, d):
    """สร้างคลิป Veo จาก W/product.jpg → W/boom.mp4 (720x1280 ไป-กลับ 16 วิ) · คืน dict {ok, gen_s, error, ...} ไม่ throw"""
    key = os.environ.get('GOOGLE_AI_KEY')
    t0 = time.time()
    if d.get('bg_video'):
        # 2 ต.ค. 69: คลิปที่ user สร้างเองใน Flow (Veo 3.1 Fast) แล้วส่งมาทาง Telegram → n8n/สคริปต์ส่ง URL ไฟล์มา ไม่ต้องเรียก Veo
        try:
            mp4 = urllib.request.urlopen(urllib.request.Request(str(d['bg_video']), headers={'User-Agent': 'Mozilla/5.0'}), timeout=120).read()
            open(W + '/veo.mp4', 'wb').write(mp4)
            return _boomerang(W, mp4, round(time.time() - t0, 1), 'bg_video')
        except Exception as e:
            return {'ok': False, 'error': 'bg_video: ' + str(e)[:160]}
    if not key:
        return {'ok': False, 'error': 'no GOOGLE_AI_KEY'}
    if not veo_quota_take():
        return {'ok': False, 'error': 'daily cap %d' % VEO_DAILY_MAX}
    try:
        img = open(W + '/product.jpg', 'rb').read()
        mime = 'image/png' if img[:4] == b'\x89PNG' else ('image/webp' if img[8:12] == b'WEBP' else 'image/jpeg')
        model = d.get('veo_model') or VEO_MODEL      # 2 ต.ค. 69: ทดสอบรุ่น/prompt ต่อคำขอได้ (Lite วาดพาวเวอร์แบงค์เป็นคนละรุ่น)
        prompt = (d.get('veo_prompt') or VEO_PROMPT) + ((' The product is: ' + str(d.get('veo_desc'))) if d.get('veo_desc') else '')
        body = {'instances': [{'prompt': prompt, 'image': {'bytesBase64Encoded': base64.b64encode(img).decode(), 'mimeType': mime}}],
                'parameters': {'aspectRatio': '9:16', 'durationSeconds': 8, 'resolution': '720p', 'sampleCount': 1}}
        base = 'https://generativelanguage.googleapis.com/v1beta/'
        op = json.load(urllib.request.urlopen(urllib.request.Request(base + 'models/%s:predictLongRunning' % model, json.dumps(body).encode(),
                                                                     {'x-goog-api-key': key, 'Content-Type': 'application/json'}), timeout=60))
        name = op['name']
        while not op.get('done'):
            if time.time() - t0 > VEO_TIMEOUT:
                return {'ok': False, 'error': 'timeout %ds' % VEO_TIMEOUT, 'gen_s': round(time.time() - t0, 1)}
            time.sleep(8)
            op = json.load(urllib.request.urlopen(urllib.request.Request(base + name, headers={'x-goog-api-key': key}), timeout=30))
        if op.get('error'):
            return {'ok': False, 'error': str(op['error'])[:200], 'gen_s': round(time.time() - t0, 1)}
        gv = (op.get('response') or {}).get('generateVideoResponse') or {}
        samples = gv.get('generatedSamples') or []
        if not samples:
            return {'ok': False, 'error': 'no sample (filtered=%s %s)' % (gv.get('raiMediaFilteredCount'), [str(x)[:100] for x in (gv.get('raiMediaFilteredReasons') or [])]),
                    'gen_s': round(time.time() - t0, 1)}
        mp4 = urllib.request.urlopen(urllib.request.Request(samples[0]['video']['uri'], headers={'x-goog-api-key': key}), timeout=120).read()
        open(W + '/veo.mp4', 'wb').write(mp4)
        return _boomerang(W, mp4, round(time.time() - t0, 1), model)
    except urllib.error.HTTPError as e:
        return {'ok': False, 'error': 'http %s %s' % (e.code, e.read().decode('utf-8', 'replace')[:200]), 'gen_s': round(time.time() - t0, 1)}
    except Exception as e:
        return {'ok': False, 'error': str(e)[:200], 'gen_s': round(time.time() - t0, 1)}

def render(d):
    W = tempfile.mkdtemp(prefix='reel_')
    try:
        req = urllib.request.Request(d['img'], headers={'User-Agent': 'Mozilla/5.0'})
        data = urllib.request.urlopen(req, timeout=30).read()
        if len(data) < 2000:
            raise ValueError('image too small')
        open(W + '/product.jpg', 'wb').write(data)

        veo = None
        if d.get('veo') and 'lazada-creative-center' in str(d.get('img', '')):
            # og:image ของ Lazada เป็นแบนเนอร์การตลาด (การ์ดชมพูมีช่องดำ) ไม่ใช่รูปสินค้า → Veo ทำออกมาเป็นแท็บเล็ต/กล่องโชว์แบนเนอร์ (เทส 2 ต.ค. 69 3/3) ข้ามไปใช้แบบเดิม
            veo = {'ok': False, 'error': 'skip: lazada banner image'}
            print('[render] veo skipped (lazada banner image)', flush=True)
        elif d.get('veo') or d.get('bg_video'):
            veo = veo_clip(W, d)
            print('[render] veo ok=%s gen=%ss err=%s' % (veo.get('ok'), veo.get('gen_s'), veo.get('error')), flush=True)
        use_veo = bool(veo and veo.get('ok'))

        segs, pct, seed = script_for(d)
        roles = [r for r, _ in segs]
        want = d.get('voice')
        forced = want is not None
        want = voice_for_round() if not forced else bool(want)
        voiced, wavs = False, []
        if want:
            try:
                vkey = voice_for(seed, d)
                print('[render] tts voice=%s' % vkey, flush=True)
                wavs = make_voice(segs, W, seed, vkey)
                durs = [dur(w) for w in wavs]
                voiced = True
            except Exception:
                traceback.print_exc()   # TTS ล้ม → ถอยไปเพลงล้วน ไม่ถือว่าเรนเดอร์ล้ม
        if not voiced:
            durs = silent_durs(segs)
        print('[render] voice=%s (%s)' % (voiced, 'req' if forced else 'auto'), flush=True)
        LEAD, TAIL = 0.5, 1.2
        starts, cur = [], LEAD
        for i, x in enumerate(durs):
            starts.append(cur)
            cur += x + (gap_for(roles[i], seed) if i < len(durs) - 1 else 0)
        D = max(7.0, math.ceil((starts[-1] + durs[-1] + TAIL) * 10) / 10)
        at = {r: starts[i] for i, r in enumerate(roles)}

        sale, full = d.get('sale'), d.get('full')
        name_lines = wrap_name(d.get('name') or '')
        # โหมด Veo: ไม่มีแถบมืด → ตัวหนังสือใส่ขอบดำ (\bord) ให้อ่านออกบนฉากสว่าง และเลื่อนบล็อกชื่อ/ราคาลง DY px (วิดีโอเต็มเฟรม สินค้ามักอยู่กลาง)
        OUT = r'\bord3\3c&H000000&' if use_veo else ''
        DY = 150 if use_veo else 0
        def ev(start, style, tags, text):
            return 'Dialogue: 0,%s,%s,%s,,0,0,0,,{%s}%s\n' % (ts(start), ts(D), style, tags + OUT, ass_escape(text))
        def ev2(start, end, style, tags, text):
            return 'Dialogue: 0,%s,%s,%s,,0,0,0,,{%s}%s\n' % (ts(start), ts(end), style, tags + OUT, ass_escape(text))
        body = ev(0, 'B', r'\an5\pos(360,118)\fs74\c' + WHITE, 'ป้ายยาดีลเด็ด')
        if pct:
            body += ev(0.8, 'B', r'\an5\pos(586,198)\fs100\shad0\c' + WHITE, '-%d%%' % pct)
        if len(name_lines) == 2:
            body += ev(0, 'B', r'\an5\pos(360,%d)\fs54\c' % (836 + DY) + WHITE, name_lines[0])
            body += ev(0, 'B', r'\an5\pos(360,%d)\fs54\c' % (896 + DY) + WHITE, name_lines[1])
            y_old, y_new = 958 + DY, 1036 + DY
        else:
            body += ev(0, 'B', r'\an5\pos(360,%d)\fs64\c' % (846 + DY) + WHITE, name_lines[0] if name_lines else '')
            y_old, y_new = 912 + DY, 1010 + DY
        # คำบรรยายใช้พื้นที่เดียวกับบล็อกราคา แล้วหายไปตอนราคาขึ้น
        # (y 800-1100 มีที่พอสำหรับชื่อ+ราคาเท่านั้น ใส่พร้อมกันทั้งสามไม่ได้)
        if 'desc' in at:
            # ⛔ ห้ามดึงจาก segs — ตั้งแต่รอบ #7 ท่อนพากย์มีคำเชื่อม/ตัวคั่น ' | ' ปนอยู่ (DESC_LEADS)
            # ซึ่งเป็นสัญญาณให้ TTS หยุดหายใจเท่านั้น ขึ้นจอต้องเป็นคำบรรยายล้วน
            desc_text = clean_desc(d.get('desc'))
            if 'old' in at:
                desc_end = at['old']
            elif (sale or full) and 'new' in at:
                desc_end = at['new']
            else:
                desc_end = D          # ไม่มีราคาให้ขึ้นจอ — ปล่อยคำบรรยายค้างไว้ไม่ให้จอโล่ง
            desc_lines = wrap_name(desc_text, per_line=30, lines=2)
            y_desc = (966 if len(desc_lines) == 2 else 992) + DY
            for i, ln in enumerate(desc_lines):
                body += ev2(at['desc'], desc_end, 'R',
                            r'\an5\pos(360,%d)\fs46\fad(250,250)\c%s' % (y_desc + i * 54, WHITE), ln)
        if 'old' in at:
            body += ev(at['old'], 'R', r'\an5\pos(360,%d)\fs54\fad(300,0)\c%s' % (y_old, GRAY), 'จากปกติ %s บาท' % money(full))
        # ไม่มีราคาเลย = ยังมีท่อน 'new' (ท่อนกลางไว้ไม่ให้คลิปโล่ง) แต่ไม่มีอะไรจะขึ้นจอ
        if 'new' in at and (sale or full):
            txt = ('เหลือ %s บาท' % money(sale)) if sale else ('ราคา %s บาท' % money(full))
            fs = 150 if len(txt) <= 13 else 118
            if len(name_lines) == 2:
                fs = int(fs * 0.9)
            body += ev(at['new'], 'B', r'\an5\pos(360,%d)\fs%d\fad(300,0)\c%s' % (y_new, fs, YELLOW), txt)
        if use_veo:
            body += ev(at['cta'], 'B', r'\an5\pos(360,1251)\fs46\shad0\bord0\c' + WHITE, 'ดูดีลนี้ที่ paiyaadeals.com')   # แถบ CTA ชิดขอบล่าง (y 1222–1280) ไม่มีบรรทัด @ ในโหมดนี้
        else:
            body += ev(at['cta'], 'B', r'\an5\pos(360,1160)\fs64\shad0\c' + WHITE, 'ดูดีลนี้ที่ paiyaadeals.com')
            body += ev(0, 'R', r'\an5\pos(360,1244)\fs46\alpha&H30&\c' + WHITE, '@paiyaa_deals')
        open(W + '/subs.ass', 'w', encoding='utf-8').write(HEAD + body)

        frames = int(round(D * FPS))
        n = len(wavs)
        # 27 ก.ย. 69 #18 ลดต้นทุน ffmpeg: พื้นหลังเบลอและรูปสินค้าย่อทำครั้งเดียวเป็น PNG (เดิมกรอง boxblur 30:3 บน 720x1280 และ zoompan บน 1200x1200 ทุกเฟรม)
        t_pre = time.time()
        run(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-y', '-i', W + '/product.jpg', '-vf',
             'scale=720:1280:force_original_aspect_ratio=increase,crop=720:1280,boxblur=30:3,eq=brightness=-0.22:saturation=1.15', W + '/bg.png'])
        run(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-y', '-i', W + '/product.jpg', '-vf',
             'scale=720:720:force_original_aspect_ratio=increase,crop=720:720', W + '/fg.png'])
        print('[render] pre-scale %.1fs' % (time.time() - t_pre), flush=True)
        badge = ("drawbox=x=486:y=146:w=200:h=100:color=0xE53935@1:t=fill:enable='gte(t,0.8)',\n" if pct else '')
        if use_veo:
            # คลิป Veo เต็มเฟรม (input 0 = boom.mp4 loop) · fg.png (input 1) ไม่ใช้แต่คงไว้ให้เลข input ของเสียงเท่าเดิม
            # แถบมืดบน/ล่างแบบไล่ 3 ขั้นให้ตัวหนังสืออ่านออกบนฉากสว่าง
            # 2 ต.ค. 69 user: "ตัวหนังสือบังสินค้า และภาพเคลื่อนนิดเดียว" → (1) ฉาก Veo คมเฉพาะช่องบน y 0–860 (crop กลางเฟรม) ส่วนล่างเป็น bg.png เบลอของรูปสินค้า = ที่วางตัวหนังสือไม่ทับสินค้า
            # (2) ซูมช้าต่อเนื่องทั้งคลิป (crop ตาม t แล้ว scale กลับ 720x1280) ให้มีการเคลื่อนไหวแม้คลิป Veo สั้น/นิ่ง · input 1 = bg.png (ไม่ใช่ fg.png)
            g = f"""[1:v]nullsink;
[0:v]setsar=1,zoompan=z='1+0.16*in/{frames}':d=1:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s=720x1280:fps={FPS},
{badge}"""
        else:
            g = f"""[0:v]setsar=1[bg];
[1:v]zoompan=z='min(zoom+0.0005,1.14)':d={frames}:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s=600x600:fps={FPS},setsar=1[fg];
[bg][fg]overlay=60:190:shortest=1,
drawbox=x=56:y=186:w=608:h=608:color=white@0.92:t=5,
{badge}"""
        cta_box = 'x=0:y=1222:w=720:h=58:color=0x8B5E3C@0.85' if use_veo else 'x=0:y=1108:w=720:h=104:color=0x8B5E3C@0.95'
        g += f"""drawbox={cta_box}:t=fill:enable='gte(t,{at['cta']:.2f})',
ass=filename={W}/subs.ass:fontsdir={FONTS},
fade=t=in:st=0:d=0.4,fade=t=out:st={D - 0.5:.2f}:d=0.5,format=yuv420p[v];
[{n + 2}:a]aformat=sample_rates=44100:channel_layouts=stereo,atrim=0:{D},asetpts=N/SR/TB,volume={0.14 if voiced else 0.5},afade=t=in:st=0:d=0.6,afade=t=out:st={D - 1.2:.2f}:d=1.2[mu];
"""
        if voiced:
            g += ''.join('[%d:a]aformat=sample_rates=44100:channel_layouts=stereo,adelay=%d:all=1[a%d];\n'
                         % (i + 2, round(starts[i] * 1000), i) for i in range(n))
            g += ''.join('[a%d]' % i for i in range(n)) + f'amix=inputs={n}:normalize=0:duration=longest,apad,atrim=0:{D},volume=1.6[vo];\n'
            g += '[vo][mu]amix=inputs=2:normalize=0:duration=first,loudnorm=I=-14:TP=-1.5:LRA=11,aresample=44100[aout]\n'
        else:
            g += '[mu]apad,atrim=0:%s,loudnorm=I=-14:TP=-1.5:LRA=11,aresample=44100[aout]\n' % D
        open(W + '/graph.txt', 'w', encoding='utf-8').write(g)

        cmd = ['ffmpeg', '-hide_banner', '-loglevel', 'error', '-y']
        if use_veo:
            cmd += ['-stream_loop', '-1', '-t', str(D), '-i', W + '/boom.mp4', '-loop', '1', '-framerate', str(FPS), '-t', str(D), '-i', W + '/bg.png']
        else:
            cmd += ['-loop', '1', '-framerate', str(FPS), '-t', str(D), '-i', W + '/bg.png', '-i', W + '/fg.png']
        for w in wavs:
            cmd += ['-i', w]
        cmd += ['-i', MUSIC, '-filter_complex_script', W + '/graph.txt', '-map', '[v]', '-map', '[aout]',
                '-c:v', 'libx264', '-preset', X264_PRESET, '-crf', str(X264_CRF), '-r', str(FPS),
                '-c:a', 'aac', '-b:a', '128k', '-movflags', '+faststart', W + '/out.mp4']
        run(cmd)
        return open(W + '/out.mp4', 'rb').read(), voiced, D, [t for _, t in segs], veo
    finally:
        shutil.rmtree(W, ignore_errors=True)

class H(BaseHTTPRequestHandler):
    def _json(self, code, obj):
        b = json.dumps(obj, ensure_ascii=False).encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def do_GET(self):
        if self.path == '/health':
            return self._json(200, {'ok': True})
        self._json(404, {'error': 'not found'})

    def do_POST(self):
        if self.path == '/afflink':
            try:
                d = json.loads(self.rfile.read(int(self.headers.get('Content-Length') or 0)).decode('utf-8'))
                r = afflink(d.get('url'))
                print('[afflink] %s -> %s (%s)' % ((d.get('url') or '')[:60], r.get('link'), r.get('reason')), flush=True)
                return self._json(200, r)
            except Exception as e:
                return self._json(500, {'ok': False, 'error': str(e)[:200]})
        if self.path in ('/publish', '/discard'):
            try:
                d = json.loads(self.rfile.read(int(self.headers.get('Content-Length') or 0)).decode('utf-8'))
                pid = safe_id(d.get('id'))
                meta, mp4 = pending_load(pid)
                if not meta:
                    try:
                        dn = json.load(open(pending_path(pid, '.done')))
                        msg = ('คลิปนี้ลง TikTok ไปแล้วเมื่อ %s น.' if dn.get('state') == 'published' else 'คลิปนี้ถูกทิ้งไปแล้วเมื่อ %s น.') % dn.get('at')
                    except Exception:
                        msg = 'ไม่มีคลิปค้างรหัสนี้ (หมดอายุ 48 ชม.)'
                    return self._json(404, {'ok': False, 'id': pid, 'error': msg})
                if self.path == '/discard':
                    pending_drop(pid, 'discarded')
                    print('[review] discard %s %s' % (pid, (meta.get('name') or '')[:40]), flush=True)
                    return self._json(200, {'ok': True, 'id': pid, 'name': meta.get('name'), 'discarded': True})
                tt = d.get('tiktok') or meta.get('tiktok') or {}
                t_u = time.time()
                r = tt_post(tt, mp4)
                print('[timing] tiktok=%.1fs ok=%s mode=%s privacy=%s status=%s err=%s (review publish %s)' % (time.time() - t_u, r.get('ok'), r.get('mode'), r.get('privacy'), r.get('status'), r.get('error'), pid), flush=True)
                fr_r = None
                if r.get('ok') and meta.get('fb_reel'):
                    fr_r = fb_reel_post(meta['fb_reel'], mp4)
                    print('[timing] fb_reel ok=%s status=%s err=%s (review publish %s)' % (fr_r.get('ok'), fr_r.get('status'), fr_r.get('error'), pid), flush=True)
                if r.get('ok'):
                    pending_drop(pid, 'published')
                return self._json(200 if r.get('ok') else 502, {'ok': bool(r.get('ok')), 'id': pid, 'name': meta.get('name'), 'tiktok': r, 'fb_reel': fr_r, 'error': r.get('error')})
            except Exception as e:
                traceback.print_exc()
                return self._json(500, {'ok': False, 'error': str(e)[:200]})
        if self.path != '/render':
            return self._json(404, {'error': 'not found'})
        try:
            d = json.loads(self.rfile.read(int(self.headers.get('Content-Length') or 0)).decode('utf-8'))
            if d.get('deal_id'):
                sd = deal_load(safe_id(d['deal_id']))
                if not sd:
                    return self._json(404, {'error': 'ไม่พบข้อมูลดีลรหัสนี้ (เก็บไว้ 7 วัน)', 'deal_id': d['deal_id']})
                for k in ('name', 'sale', 'full', 'desc', 'cat', 'img'):
                    d.setdefault(k, sd.get(k))
                d.setdefault('page_id', safe_id(d['deal_id']))
                if isinstance(d.get('tiktok'), dict) and not d['tiktok'].get('title'):
                    d['tiktok']['title'] = sd.get('title') or ''
                d['_saved_title'] = sd.get('title')
                if 'fb_reel' not in d and isinstance(sd.get('fb_reel'), dict):
                    d['fb_reel'] = dict(sd['fb_reel'], post=True)   # คลิปที่ user ส่งเอง → ลง FB Reels ด้วย (เหมือน TikTok)
            if not d.get('img'):
                return self._json(400, {'error': 'img required'})
            for k in ('sale', 'full'):
                try:
                    d[k] = float(d[k]) if d.get(k) not in (None, '', 0) else None
                except (TypeError, ValueError):
                    d[k] = None
            forced = d.get('voice') is not None   # โหมดบังคับ/auto ใช้ตอบ header+JSON ด้านล่าง (เดิมนิยามแค่ใน render() → NameError ทำทุก request ตอบ 500 ตั้งแต่ 22 ก.ย. 69)
            t_r = time.time()
            mp4, voiced, D, lines, veo = render(d)
            render_s = round(time.time() - t_r, 1)
            print('[timing] render=%.1fs dur=%s voice=%s veo=%s' % (render_s, D, voiced, (veo or {}).get('ok')), flush=True)
            tg = d.get('telegram'); tt = d.get('tiktok')
            fr = d.get('fb_reel') if (isinstance(d.get('fb_reel'), dict) and d['fb_reel'].get('post', True) and d['fb_reel'].get('token')) else None
            rv = d.get('review')
            pid_d = safe_id(d.get('page_id'))
            # 3 ต.ค. 69: โหมดไม่รอตรวจ — บอกใน caption TG ว่าคลิปนี้เป็น Veo และลง TikTok ให้แล้ว (ต่อหน้า caption ก่อนตัด 960 ตัว ไม่ให้ '#d' ท้ายหาย)
            pre = ('🎬 คลิป Veo (gen %ss) → ลง TikTok อัตโนมัติ\n' % (veo or {}).get('gen_s', '?')) if (rv and (veo or {}).get('ok') and not VEO_REVIEW and tt) else ''
            if pid_d and not d.get('deal_id'):
                deal_save(pid_d, d, ((tg or {}).get('caption') or (rv or {}).get('caption') or '').split('\n\n', 1)[-1])
            if tg and tg.get('caption') is not None and (pre or (pid_d and not d.get('deal_id'))):
                tg['caption'] = pre + str(tg['caption'])[:960 - len(pre)] + (('\n#d ' + pid_d) if (pid_d and not d.get('deal_id')) else '')
            if rv and VEO_REVIEW and (veo or {}).get('ok'):
                pid = safe_id(d.get('page_id')) or hashlib.md5((d.get('name') or '').encode('utf-8')).hexdigest()[:16]
                pending_save(pid, mp4, {'name': d.get('name'), 'tiktok': tt, 'fb_reel': fr, 'created': time.time(), 'caption': rv.get('caption'), 'veo': veo})
                cap = '#veo ' + pid + '\n' + (rv.get('caption') or '') + '\n\n✅ ตอบกลับ (reply) ข้อความนี้ว่า "โพสต์" เพื่อลง TikTok · "ไม่" เพื่อทิ้ง'
                t_u = time.time()
                try:
                    sent, mid = tg_send_video(rv, mp4, cap)
                except Exception as e:
                    sent, mid = False, str(e)[:200]
                print('[timing] review-telegram=%.1fs sent=%s pending=%s bytes=%d' % (time.time() - t_u, sent, pid, len(mp4)), flush=True)
                return self._json(200 if sent else 502, {'review': True, 'pending_id': pid, 'sent': sent, 'message_id': mid, 'bytes': len(mp4), 'voice': voiced,
                                                          'voice_mode': 'req' if forced else 'auto', 'duration': D, 'lines': lines, 'render_s': render_s, 'veo': veo})
            if tg or tt or fr:
                out = {'bytes': len(mp4), 'voice': voiced, 'voice_mode': 'req' if forced else 'auto', 'duration': D, 'lines': lines, 'render_s': render_s, 'veo': veo}
                ok = True
                # 2 ต.ค. 69: ขอ Veo แต่ไม่ได้ (เกินโควตา 4/วัน, ล้ม, รูปแบนเนอร์) และมี review → ส่ง "รูปสินค้า + prompt" ให้ user ทำคลิป Veo เองใน aipass/Flow แล้ว Reply คลิปกลับที่ข้อความรูป (caption มี #d)
                if tg and rv and d.get('veo') and not (veo or {}).get('ok') and pid_d and 'lazada-creative-center' not in str(d.get('img', '')):
                    try:
                        jpg = urllib.request.urlopen(urllib.request.Request(d['img'], headers={'User-Agent': 'Mozilla/5.0'}), timeout=30).read()
                        capP = ('🖼 ดีลเด่นรอบนี้ — ทำคลิป Veo เอง: ' + (d.get('name') or '')[:80] + '\n\n1) เซฟรูปนี้ 2) ใน aipass เลือก Veo 3.1 Fast + 9:16 แนบรูป วาง prompt ด้านล่าง 3) Reply คลิปที่ได้กลับมาที่ข้อความนี้\n\n'
                                + VEO_PROMPT + '\n\n#d ' + pid_d)
                        ps, pm = tg_send_photo(tg, jpg, capP)
                        out['photo_sent'] = ps; out['photo_message_id'] = pm
                        print('[review] veo unavailable (%s) -> photo for manual Veo sent=%s' % ((veo or {}).get('error'), ps), flush=True)
                    except Exception as e:
                        out['photo_sent'] = False; out['photo_error'] = str(e)[:120]
                if tg:
                    t_u = time.time()
                    try:
                        sent, mid = tg_send_video(tg, mp4, tg.get('caption') or '')
                    except Exception as e:
                        sent, mid = False, str(e)[:200]
                    print('[timing] telegram=%.1fs sent=%s bytes=%d' % (time.time() - t_u, sent, len(mp4)), flush=True)
                    out.update(sent=sent, message_id=mid); ok = ok and sent
                if tt:
                    t_u = time.time()
                    r = tt_post(tt, mp4)
                    print('[timing] tiktok=%.1fs ok=%s mode=%s privacy=%s status=%s err=%s' % (time.time() - t_u, r.get('ok'), r.get('mode'), r.get('privacy'), r.get('status'), r.get('error')), flush=True)
                    out['tiktok'] = r; ok = ok and bool(r.get('ok'))
                if fr:
                    t_u = time.time()
                    r = fb_reel_post(fr, mp4)
                    print('[timing] fb_reel=%.1fs ok=%s status=%s phase=%s upload=%ss err=%s' % (time.time() - t_u, r.get('ok'), r.get('status'), r.get('phase'), r.get('upload_s'), r.get('error')), flush=True)
                    out['fb_reel'] = r; ok = ok and bool(r.get('ok'))
                return self._json(200 if ok else 502, out)
            up = d.get('upload')
            if up:
                # อัปโหลดให้เลย (resumable ของ IG) — ส่ง binary ออกจาก Code node ของ n8n ไม่ได้
                # (task runner serialize Buffer เพี้ยน → Meta ตอบ Video Transcoding Error)
                # token มากับ request ภายใน network n8n_default เท่านั้น ไม่เก็บ/ไม่ log
                if not str(up.get('url', '')).startswith('https://rupload.facebook.com/'):
                    return self._json(400, {'error': 'upload url must be rupload.facebook.com'})
                r = urllib.request.Request(up['url'], data=mp4, method='POST', headers={
                    'Authorization': 'OAuth ' + up['token'], 'offset': '0', 'file_size': str(len(mp4)),
                    'Content-Type': 'application/octet-stream'})
                t_u = time.time()
                try:
                    body = urllib.request.urlopen(r, timeout=120).read().decode('utf-8', 'replace')
                    code = 200
                except urllib.error.HTTPError as he:
                    body, code = he.read().decode('utf-8', 'replace')[:800], he.code
                upload_s = round(time.time() - t_u, 1)
                print('[timing] upload=%.1fs status=%s bytes=%d' % (upload_s, code, len(mp4)), flush=True)
                return self._json(200 if code == 200 else 502, {
                    'uploaded': code == 200, 'status': code, 'response': body[:800],
                    'bytes': len(mp4), 'voice': voiced, 'voice_mode': 'req' if forced else 'auto',
                    'duration': D, 'lines': lines, 'render_s': render_s, 'upload_s': upload_s, 'veo': veo})
        except subprocess.CalledProcessError as e:
            return self._json(500, {'error': 'ffmpeg failed', 'detail': (e.stderr or b'')[-800:].decode('utf-8', 'replace')})
        except Exception as e:
            traceback.print_exc()
            return self._json(500, {'error': str(e)[:500]})
        self.send_response(200)
        self.send_header('Content-Type', 'video/mp4')
        self.send_header('Content-Length', str(len(mp4)))
        self.send_header('X-Voice', '1' if voiced else '0')
        self.send_header('X-Voice-Mode', 'req' if forced else 'auto')
        self.send_header('X-Duration', str(D))
        self.send_header('X-Veo', '1' if (veo or {}).get('ok') else '0')
        self.end_headers()
        self.wfile.write(mp4)

    def log_message(self, fmt, *args):
        print('%s - %s' % (self.address_string(), fmt % args), flush=True)

if __name__ == '__main__':
    print('deal-video listening :8080', flush=True)
    HTTPServer(('0.0.0.0', int(os.environ.get('PORT', '8080'))), H).serve_forever()
