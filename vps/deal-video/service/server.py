# deal-video render service — รับข้อมูลดีล คืนคลิป Reels (mp4) แนวตั้ง 720x1280 พร้อมเสียงพากย์+เพลง
# รันใน container `deal-video` บน network n8n_default · n8n เรียก POST http://deal-video:8080/render
# body: {"name": str, "sale": num|null, "full": num|null, "img": url, "desc": str|null}
#       desc = คำบรรยายสินค้าสั้น ๆ — มีแล้วได้ทั้งท่อนพากย์และข้อความบนจอ, ไม่มีก็เรนเดอร์เหมือนเดิม
# (ใส่ "upload": {"url": rupload uri, "token": …} = อัปโหลดขึ้น IG ให้เลย ตอบ JSON แทนไฟล์)
# ตอบ 200 video/mp4 (header X-Voice: 1 = มีเสียงพากย์, 0 = TTS ล้มเลยได้แค่เพลง) · ผิดพลาด = 4xx/5xx JSON
# เรนเดอร์ทีละคลิป (HTTPServer ไม่ใช่ threaded) เพราะ VPS มี 1 core
import asyncio, hashlib, json, math, os, re, shutil, subprocess, tempfile, traceback, urllib.error, urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer

FONTS = '/app/fonts'
MUSIC = '/app/music/Carefree.mp3'
FPS = 30
VOICE = 'th-TH-PremwadeeNeural'

# ---------- ตัวเลขเป็นคำอ่านไทย (อ่านตัวเลขตรง ๆ ฟังเป็นหุ่นยนต์ที่สุด) ----------
DIG = ['ศูนย์', 'หนึ่ง', 'สอง', 'สาม', 'สี่', 'ห้า', 'หก', 'เจ็ด', 'แปด', 'เก้า']
UNIT = ['', 'สิบ', 'ร้อย', 'พัน', 'หมื่น', 'แสน']

def thai_words(n):
    n = int(round(n))
    if n == 0:
        return DIG[0]
    if n >= 1000000:
        return thai_words(n // 1000000) + 'ล้าน' + (thai_words(n % 1000000) if n % 1000000 else '')
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
    return thai_words(lead) + ('' if n == lead else 'กว่า')

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
         'โอ้โห | อันนี้น่าสนใจ', 'บอกต่อเลย | ดีลนี้']
CTAS = ['ใครสนใจ | กดลิ้งค์ในไบโอได้เลยน้า', 'สนใจ | กดลิ้งค์ในไบโอเลยค่ะ',
        'อยากได้ | กดลิ้งค์ในไบโอเลยน้า']
# ดีลที่ไม่มีราคาเลย: ใส่ท่อนกลางไว้ไม่ให้คลิปโล่ง (ห้ามอ้างว่าถูก/ใกล้หมด — เราไม่รู้ราคาด้วยซ้ำ)
NOPRICE = ['เดี๋ยวพาไปดูใกล้ ๆ นะคะ', 'ลองดูกันนะคะ | ว่าเป็นยังไง']
# 'ลิ้งค์' สะกดให้เสียงสูงตามที่คนพูดจริง (user 19 ก.ย. 69: 'ลิงก์' เสียงต่ำไป) — บนจอยังเขียน 'ลิงก์' ตามพจนานุกรม
# ⛔ ห้ามใช้ <prosody> ซ้อนเพื่อดันคำเดียว — Azure ไทยตัดเป็นคนละประโยค เติมหยุด ~2.7 วิ (วัดแล้ว 2.06 → 4.72 วิ)
# เครื่องหมาย ' | ' ในบท = หยุดหายใจสั้น ๆ ~0.33 วิ — แทนด้วย '… ' (ellipsis+space) ก่อนส่ง TTS (user 19 ก.ย. 69: คำในท่อนราคายังติดกัน)
# ⚠️ ช่องว่างรอบ ellipsis มีผลมาก (วัด 19 ก.ย. 69): ' … ' ≈ +1.1 วิ/จุด · '… ' ≈ +0.33 · '…' ติดคำ ≈ +0.09 — ต้องเป็น '… ' เท่านั้น
# ⛔ ห้ามใช้ SSML <break> — Azure เสียงไทยเติมหยุด ~1.4 วิต่อจุดไม่ว่า time= เท่าไร (วัดแล้ว: 5 จุด → ท่อน 4.5 วิกลายเป็น 12 วิ)
#    ', ' ≈ +0.33 วิเท่ากับ '… ' · '. ' ไม่หยุดเลย
PAUSE_MARK = '… '
# 'บาท…เองค่ะ' ใช้ '…' ติดคำโดยตรง = หยุดสั้นกว่า (~0.1 วิ) — user 19 ก.ย. 69 ขอให้ช่วง บาท→เอง แคบลง
# rate/pitch ต่อบทบาท: ท่อนเปิดเร็ว-สูง · ราคาเดิมเรียบ · ราคาใหม่ตื่นเต้น · ปิดช้าลงเป็นกันเอง
PROSODY = {'hook': ('+4%', '+8Hz'), 'desc': ('-2%', '+4Hz'), 'old': ('-6%', '+0Hz'), 'new': ('-8%', '+12Hz'), 'cta': ('-6%', '+4Hz')}   # user 19 ก.ย. 69: เดิมเร็วไป (+14/+6/+10/+2)
GAP_AFTER = {'hook': 0.4, 'desc': 0.35, 'old': 0.3, 'new': 0.5, 'cta': 0}   # เว้นวรรคระหว่างท่อนให้หายใจ (เดิม 0.18/0.12/0.32 ติดกันเกิน)
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
    segs = [('hook', HOOKS[h % len(HOOKS)])]
    desc = clean_desc(d.get('desc'))
    if desc:
        segs.append(('desc', desc))
    pct = None
    if sale and full and full > sale:
        pct = round((full - sale) / full * 100)
        segs.append(('old', 'ปกติขายตั้ง%sบาท' % approx_words(full)))
        tail = ''
        if pct >= 50:
            tail = ' | ลดไปเกินครึ่งเลยนะ'
        elif pct >= 15:
            tail = ' | ลดไปตั้ง%sเปอร์เซ็นต์แน่ะ' % thai_words(pct)
        segs.append(('new', 'ตอนนี้เหลือแค่ | %sบาท…เองค่ะ%s' % (thai_words(sale), tail)))
    elif sale:
        segs.append(('new', 'ตอนนี้ราคาแค่ | %sบาท…เองค่ะ' % thai_words(sale)))
    elif full:
        segs.append(('new', 'ราคา%sบาทค่ะ' % thai_words(full)))
    else:
        segs.append(('new', NOPRICE[(h // 3) % len(NOPRICE)]))   # ไม่มีราคาเลย = คลิปจะเหลือแค่ hook+CTA (7 วิ) โล่งไป
    segs.append(('cta', CTAS[(h // 7) % len(CTAS)]))
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
AZ_REGION = os.environ.get('AZURE_SPEECH_REGION', 'eastus')

def azure_tts(text, rate, pitch, out):
    """Azure Speech (ทางการ) — key มาจาก .env ของ container · เสียงเดียวกับ edge-tts แต่เสถียร"""
    ssml = ('<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" xml:lang="th-TH">'
            '<voice name="%s"><prosody rate="%s" pitch="%s">%s</prosody></voice></speak>'
            % (VOICE, rate, pitch, text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
               .replace(' | ', PAUSE_MARK)))
    r = urllib.request.Request('https://%s.tts.speech.microsoft.com/cognitiveservices/v1' % AZ_REGION,
                               data=ssml.encode('utf-8'), method='POST', headers={
                                   'Ocp-Apim-Subscription-Key': AZ_KEY, 'Content-Type': 'application/ssml+xml',
                                   'X-Microsoft-OutputFormat': 'audio-24khz-96kbitrate-mono-mp3', 'User-Agent': 'deal-video'})
    data = urllib.request.urlopen(r, timeout=30).read()
    if len(data) < 1000:
        raise ValueError('azure: empty audio')
    open(out, 'wb').write(data)

async def _tts(segs, W, seed):
    if AZ_KEY:
        last = None
        for i, (role, text) in enumerate(segs):
            rate, pitch = prosody_for(role, seed)
            for k in range(3):
                try:
                    azure_tts(text, rate, pitch, '%s/vo_%d.mp3' % (W, i))
                    last = None
                    break
                except Exception as e:
                    last = e
                    await asyncio.sleep(2 * (k + 1))
            if last:
                print('azure tts failed seg %d: %s -> fallback edge-tts' % (i, last), flush=True)
                break
            print('tts seg %d ok (azure)' % i, flush=True)
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

def make_voice(segs, W, seed):
    asyncio.run(asyncio.wait_for(_tts(segs, W, seed), timeout=150))
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
        voiced = True
        try:
            wavs = make_voice(segs, W, seed)
            durs = [dur(w) for w in wavs]
        except Exception:
            traceback.print_exc()
            voiced, wavs = False, []
            durs = [1.3] * len(segs)          # ไม่มีเสียง: จังหวะข้อความตายตัว
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
            desc_text = next((t for r, t in segs if r == 'desc'), '')
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
        badge = ("drawbox=x=486:y=146:w=200:h=100:color=0xE53935@1:t=fill:enable='gte(t,0.8)',\n" if pct else '')
        g = f"""[0:v]scale=720:1280:force_original_aspect_ratio=increase,crop=720:1280,boxblur=30:3,eq=brightness=-0.22:saturation=1.15,setsar=1[bg];
[1:v]scale=1200:1200:force_original_aspect_ratio=increase,crop=1200:1200,zoompan=z='min(zoom+0.0005,1.14)':d={frames}:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s=600x600:fps={FPS},setsar=1[fg];
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
               '-loop', '1', '-framerate', str(FPS), '-t', str(D), '-i', W + '/product.jpg', '-i', W + '/product.jpg']
        for w in wavs:
            cmd += ['-i', w]
        cmd += ['-i', MUSIC, '-filter_complex_script', W + '/graph.txt', '-map', '[v]', '-map', '[aout]',
                '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '22', '-r', str(FPS),
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
            mp4, voiced, D, lines = render(d)
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
                try:
                    body = urllib.request.urlopen(r, timeout=120).read().decode('utf-8', 'replace')
                    code = 200
                except urllib.error.HTTPError as he:
                    body, code = he.read().decode('utf-8', 'replace')[:800], he.code
                return self._json(200 if code == 200 else 502, {
                    'uploaded': code == 200, 'status': code, 'response': body[:800],
                    'bytes': len(mp4), 'voice': voiced, 'duration': D, 'lines': lines})
        except subprocess.CalledProcessError as e:
            return self._json(500, {'error': 'ffmpeg failed', 'detail': (e.stderr or b'')[-800:].decode('utf-8', 'replace')})
        except Exception as e:
            traceback.print_exc()
            return self._json(500, {'error': str(e)[:500]})
        self.send_response(200)
        self.send_header('Content-Type', 'video/mp4')
        self.send_header('Content-Length', str(len(mp4)))
        self.send_header('X-Voice', '1' if voiced else '0')
        self.send_header('X-Duration', str(D))
        self.end_headers()
        self.wfile.write(mp4)

    def log_message(self, fmt, *args):
        print('%s - %s' % (self.address_string(), fmt % args), flush=True)

if __name__ == '__main__':
    print('deal-video listening :8080', flush=True)
    HTTPServer(('0.0.0.0', 8080), H).serve_forever()
