# deal-video render service — รับข้อมูลดีล คืนคลิป Reels (mp4) แนวตั้ง 720x1280 พร้อมเสียงพากย์+เพลง
# รันใน container `deal-video` บน network n8n_default · n8n เรียก POST http://deal-video:8080/render
# body: {"name": str, "sale": num|null, "full": num|null, "img": url, "desc": str|null, "cat": str|null}
#       cat = property `หมวด` จาก Notion (บ้าน/gadget/ความงาม/…) ใช้เลือก hook เรียกกลุ่ม (รอบ #9) ไม่มีก็ได้
#       desc = คำบรรยายสินค้าสั้น ๆ — มีแล้วได้ทั้งท่อนพากย์และข้อความบนจอ, ไม่มีก็เรนเดอร์เหมือนเดิม
# (ใส่ "upload": {"url": rupload uri, "token": …} = อัปโหลดขึ้น IG ให้เลย ตอบ JSON แทนไฟล์)
# ตอบ 200 video/mp4 (header X-Voice: 1 = มีเสียงพากย์, 0 = TTS ล้มเลยได้แค่เพลง) · ผิดพลาด = 4xx/5xx JSON
# เรนเดอร์ทีละคลิป (HTTPServer ไม่ใช่ threaded) เพราะ VPS มี 1 core
import asyncio, hashlib, json, math, os, re, shutil, subprocess, tempfile, time, traceback, urllib.error, urllib.parse, urllib.request
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
CTAS = ['ใครสนใจ | กดลิ้งค์ในไบโอได้เลยนะ', 'สนใจ | กดลิ้งค์ในไบโอเลยครับ',
        'อยากได้ | กดลิ้งค์ในไบโอเลยนะ',
        'ถูกใจ | แวะกดลิ้งค์ในไบโอนะครับ', 'เผื่อใครสนใจ | ลิ้งค์อยู่ในไบโอนะ',
        'สนใจก็ | ตามไปดูที่ลิ้งค์ในไบโอเลยครับ',
        # รอบ #9 — ปิดแบบเพื่อนบอกเพื่อน + ชวนติดตาม/เก็บไว้ (ผู้ติดตาม IG ยังน้อย · save เป็นสัญญาณ algorithm)
        'ใครอยากได้ | ลิ้งค์ในไบโอเลยนะ | ไปจัด', 'ลิ้งค์อยู่ในไบโอนะครับ | สาดไปสมาชิก',
        'ไปดูที่ลิ้งค์ในไบโอกันครับ | แล้วมาบอกกันว่าเป็นไง', 'ลิ้งค์ในไบโอเลยครับ | ฝากติดตามด้วยนะ',
        'เก็บไว้ก่อนได้ | ลิ้งค์ในไบโอนะ']
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

def script_for(d):
    name, sale, full = d.get('name') or '', d.get('sale'), d.get('full')
    h = int(hashlib.md5(name.encode('utf-8')).hexdigest(), 16)
    pct = None
    if sale and full and full > sale:
        pct = round((full - sale) / full * 100)
    # เลือกชนิด hook (รอบ #9): เรียกกลุ่มตามหมวด → ชูตัวเลข → urgency ตอนลด → ปกติ · ทุกอย่างคงที่ต่อดีลด้วย hash ชื่อ
    cat = str(d.get('cat') or '').strip()
    pct_hook = False
    if cat in CAT_HOOKS and (h // 31) % 3 == 0:
        pool = CAT_HOOKS[cat]
        hook = pool[(h // 37) % len(pool)]
    elif pct and pct >= PCT_HOOK_MIN and (h // 29) % 2 == 0:
        hook = PCT_HOOKS[(h // 41) % len(PCT_HOOKS)] % thai_words(pct)
        pct_hook = True
    elif pct and (h // 43) % 5 == 0:
        hook = DISCOUNT_HOOKS[(h // 47) % len(DISCOUNT_HOOKS)]
    else:
        hook = HOOKS[h % len(HOOKS)]
    segs = [('hook', hook)]
    desc = clean_desc(d.get('desc'))
    if desc:
        segs.append(('desc', DESC_LEADS[(h // 11) % len(DESC_LEADS)] % desc))
    if pct:
        segs.append(('old', OLD_LINES[(h // 13) % len(OLD_LINES)] % approx_words(full)))
        tail = ''
        if pct_hook:
            tail = ''                      # hook พูดเปอร์เซ็นต์ไปแล้ว ไม่ซ้ำ
        elif pct >= 50:
            tail = ' | ลดไปเกินครึ่งเลยนะ'
        elif pct >= 15:
            tail = ' | ลดไปตั้ง%sเปอร์เซ็นต์แน่ะ' % thai_words(pct)
        line = NEW_LINES[(h // 17) % len(NEW_LINES)] % thai_words(sale)
        if tail and line.endswith('เอง'):
            tail = ',' + tail[2:]   # 'เอง | ลด…' → 'เอง, ลด…' — วัด 26 ก.ย. 69: 'เอง… ' Azure ถือจบประโยค หยุด 1.34 วิ · ', ' 0.58 · ('เองน้า… ' 0.43 แต่ user ให้ตัด น้า)
        segs.append(('new', line + tail))
    elif sale:
        segs.append(('new', SALE_LINES[(h // 19) % len(SALE_LINES)] % thai_words(sale)))
    elif full:
        segs.append(('new', FULL_LINES[(h // 23) % len(FULL_LINES)] % thai_words(full)))
    else:
        segs.append(('new', NOPRICE[(h // 3) % len(NOPRICE)]))   # ไม่มีราคาเลย = คลิปจะเหลือแค่ hook+CTA (7 วิ) โล่งไป
    segs.append(('cta', CTAS[(h // 7) % len(CTAS)]))
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

def render(d):
    W = tempfile.mkdtemp(prefix='reel_')
    try:
        req = urllib.request.Request(d['img'], headers={'User-Agent': 'Mozilla/5.0'})
        data = urllib.request.urlopen(req, timeout=30).read()
        if len(data) < 2000:
            raise ValueError('image too small')
        open(W + '/product.jpg', 'wb').write(data)

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
        def ev(start, style, tags, text):
            return 'Dialogue: 0,%s,%s,%s,,0,0,0,,{%s}%s\n' % (ts(start), ts(D), style, tags, ass_escape(text))
        def ev2(start, end, style, tags, text):
            return 'Dialogue: 0,%s,%s,%s,,0,0,0,,{%s}%s\n' % (ts(start), ts(end), style, tags, ass_escape(text))
        body = ev(0, 'B', r'\an5\pos(360,118)\fs74\c' + WHITE, 'ป้ายยาดีลเด็ด')
        if pct:
            body += ev(0.8, 'B', r'\an5\pos(586,198)\fs100\shad0\c' + WHITE, '-%d%%' % pct)
        if len(name_lines) == 2:
            body += ev(0, 'B', r'\an5\pos(360,836)\fs54\c' + WHITE, name_lines[0])
            body += ev(0, 'B', r'\an5\pos(360,896)\fs54\c' + WHITE, name_lines[1])
            y_old, y_new = 958, 1036
        else:
            body += ev(0, 'B', r'\an5\pos(360,846)\fs64\c' + WHITE, name_lines[0] if name_lines else '')
            y_old, y_new = 912, 1010
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
            y_desc = 966 if len(desc_lines) == 2 else 992
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
        body += ev(at['cta'], 'B', r'\an5\pos(360,1160)\fs64\shad0\c' + WHITE, 'กดลิงก์ในไบโอ ไปที่ร้านเลย')
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
        g = f"""[0:v]setsar=1[bg];
[1:v]zoompan=z='min(zoom+0.0005,1.14)':d={frames}:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s=600x600:fps={FPS},setsar=1[fg];
[bg][fg]overlay=60:190:shortest=1,
drawbox=x=56:y=186:w=608:h=608:color=white@0.92:t=5,
{badge}drawbox=x=0:y=1108:w=720:h=104:color=0x8B5E3C@0.95:t=fill:enable='gte(t,{at['cta']:.2f})',
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

        cmd = ['ffmpeg', '-hide_banner', '-loglevel', 'error', '-y',
               '-loop', '1', '-framerate', str(FPS), '-t', str(D), '-i', W + '/bg.png', '-i', W + '/fg.png']
        for w in wavs:
            cmd += ['-i', w]
        cmd += ['-i', MUSIC, '-filter_complex_script', W + '/graph.txt', '-map', '[v]', '-map', '[aout]',
                '-c:v', 'libx264', '-preset', X264_PRESET, '-crf', str(X264_CRF), '-r', str(FPS),
                '-c:a', 'aac', '-b:a', '128k', '-movflags', '+faststart', W + '/out.mp4']
        run(cmd)
        return open(W + '/out.mp4', 'rb').read(), voiced, D, [t for _, t in segs]
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
        if self.path != '/render':
            return self._json(404, {'error': 'not found'})
        try:
            d = json.loads(self.rfile.read(int(self.headers.get('Content-Length') or 0)).decode('utf-8'))
            if not d.get('img'):
                return self._json(400, {'error': 'img required'})
            for k in ('sale', 'full'):
                try:
                    d[k] = float(d[k]) if d.get(k) not in (None, '', 0) else None
                except (TypeError, ValueError):
                    d[k] = None
            forced = d.get('voice') is not None   # โหมดบังคับ/auto ใช้ตอบ header+JSON ด้านล่าง (เดิมนิยามแค่ใน render() → NameError ทำทุก request ตอบ 500 ตั้งแต่ 22 ก.ย. 69)
            t_r = time.time()
            mp4, voiced, D, lines = render(d)
            render_s = round(time.time() - t_r, 1)
            print('[timing] render=%.1fs dur=%s voice=%s' % (render_s, D, voiced), flush=True)
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
                    'duration': D, 'lines': lines, 'render_s': render_s, 'upload_s': upload_s})
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
        self.end_headers()
        self.wfile.write(mp4)

    def log_message(self, fmt, *args):
        print('%s - %s' % (self.address_string(), fmt % args), flush=True)

if __name__ == '__main__':
    print('deal-video listening :8080', flush=True)
    HTTPServer(('0.0.0.0', int(os.environ.get('PORT', '8080'))), H).serve_forever()
