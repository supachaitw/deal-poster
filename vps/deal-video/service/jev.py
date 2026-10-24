"""Jev (TypeSafe jev-1.13 ผ่าน OpenRouter Decisions API) — ด่านตัดสินใจของ deal-video (24 ต.ค. 69)

ใช้ 2 เรื่อง (server.py เป็นคนเรียก):
  1. tt_risk  — ดีลนี้เสี่ยงโดน TikTok ลบไหม (อาหารเสริม/ลดน้ำหนัก/ยา/เครื่องสำอางอ้างผล) → ไม่ส่งร่าง TikTok
  2. claim    — ข้อความอ้างสรรพคุณที่กฎโฆษณา อย. ห้ามไหม → ไม่พากย์/ไม่ขึ้นจอ (คำบรรยายจาก Notion + บทที่ LLM เขียน)
regex เดิมใน server.py ยังทำงานก่อนเสมอ (เจอ = ตัดทันที ไม่ถาม Jev) — Jev เพิ่ม "จับได้" อย่างเดียว ไม่เคยปลด
ไม่มี key / ปิด / ล้ม / ช้า → คืน None ให้ผู้เรียกใช้ regex อย่างเดียวเหมือนเดิม · ล้มแล้วพัก COOLDOWN_S ไม่ถามซ้ำถี่ ๆ
stdlib ล้วน (urllib) · ห้ามพิมพ์ key · log '[jev] …' ทุก request พร้อม usage.cost
"""
import json, os, time, urllib.error, urllib.request

JEV_URL = 'https://openrouter.ai/api/alpha/decisions'
KEY = os.environ.get('OPENROUTER_API_KEY', '').strip()
MODEL = os.environ.get('JEV_MODEL', 'typesafe/jev-1.13')
ENABLED = os.environ.get('JEV_ENABLED', '1') != '0' and bool(KEY)
TIMEOUT = float(os.environ.get('JEV_TIMEOUT', '10'))
TT_RISK_MIN = float(os.environ.get('JEV_TT_RISK_MIN', '0.5'))    # P(ไม่ปลอดภัย) ≥ นี้ = ไม่ส่ง TikTok
CLAIM_MIN = float(os.environ.get('JEV_CLAIM_MIN', '0.5'))        # P(อ้างสรรพคุณ) ≥ นี้ = ตัดข้อความ
COOLDOWN_S = float(os.environ.get('JEV_COOLDOWN', '300'))
RETRY_DELAY_S = 1.0
CACHE_MAX = 300
MAX_BATCH = 8   # ท่อนบทต่อ request (hook/promise/loop/cta/desc/price = 6)

_cooldown_until = 0.0
_claim_cache = {}   # text -> prob (float)
_tt_cache = {}      # (name, desc) -> {'prob','choice'}

TT_CRITERIA = {
    'safe': 'สินค้าทั่วไปที่ไม่เกี่ยวกับสุขภาพหรือร่างกาย เช่น ของใช้ในบ้าน แกดเจ็ต เสื้อผ้า รองเท้า กระเป๋า อาหาร ขนม เครื่องดื่ม '
            'ของแต่งบ้าน เครื่องครัว ของเล่น สัตว์เลี้ยง เครื่องเขียน อุปกรณ์กีฬา เครื่องสำอางทั่วไปที่ไม่อ้างผล',
    'supplement': 'อาหารเสริม วิตามิน แร่ธาตุ โปรไบโอติก คอลลาเจน กลูต้า เวย์โปรตีน ไฟเบอร์ผง สมุนไพรแบบกิน น้ำมันปลา ชาเพื่อสุขภาพ',
    'weight_loss': 'สินค้าหรือข้อความเกี่ยวกับลดน้ำหนัก ลดพุง ลดไขมัน คุมหิว อิ่มนาน เผาผลาญ ดีท็อกซ์ บล็อกแป้ง',
    'medical': 'ยา อุปกรณ์การแพทย์ เครื่องวัดความดัน/น้ำตาล เครื่องมือรักษา ถุงยาง ยาฆ่าเชื้อ ผลิตภัณฑ์ที่อ้างว่ารักษาหรือป้องกันโรค',
    'cosmetic_claim': 'เครื่องสำอาง สกินแคร์ หรือของใช้ส่วนตัวที่อ้างผลลัพธ์ต่อร่างกาย เช่น ผิวขาว ลดสิว ลดริ้วรอย ยกกระชับ '
                      'ปลูกผม ฆ่าเชื้อ 99% ระงับกลิ่นถาวร',
}
CLAIM_CRITERIA = {
    'claim': 'ข้อความอ้างผลต่อร่างกาย สุขภาพ ผิว โรค น้ำหนัก ภูมิคุ้มกัน สมอง สมรรถภาพ หรือการฆ่าเชื้อ/แบคทีเรีย/ไวรัส '
             'หรืออ้างสรรพคุณทางการแพทย์ บำบัด บรรเทา รักษา ป้องกันโรค (สิ่งที่กฎโฆษณา อย. ห้าม)',
    'none': 'บอกแค่คุณสมบัติทั่วไปของสินค้า เช่น วัสดุ ขนาด สี ความจุ รสชาติ ดีไซน์ ความสะดวก ราคา โปรโมชัน การใช้งาน '
            'โดยไม่อ้างผลต่อสุขภาพหรือร่างกาย',
}


def _trim(s, n):
    s = ' '.join(str(s or '').split())
    return s[:n]


def _probs(ans):
    """probabilities ของคำตอบ choice — ไม่มีให้ใช้ choice=1.0 · ไม่มีอะไรเลย = {}"""
    if not isinstance(ans, dict):
        return {}
    p = ans.get('probabilities')
    if isinstance(p, dict) and p:
        out = {}
        for k, v in p.items():
            try:
                out[k] = max(0.0, min(1.0, float(v)))
            except (TypeError, ValueError):
                pass
        if out:
            return out
    c = ans.get('choice')
    return {c: 1.0} if isinstance(c, str) and c else {}


def tt_from_answer(ans):
    """→ {'prob': P(ไม่ปลอดภัย), 'choice': ชื่อกลุ่ม} หรือ None"""
    p = _probs(ans)
    if not p:
        return None
    safe = p.get('safe', 0.0)
    choice = ans.get('choice') if isinstance(ans.get('choice'), str) and ans.get('choice') in TT_CRITERIA else max(p, key=p.get)
    return {'prob': round(1.0 - safe, 3), 'choice': choice}


def claim_from_answer(ans):
    """→ P(อ้างสรรพคุณ) หรือ None"""
    p = _probs(ans)
    if not p:
        return None
    if 'claim' in p:
        return round(p['claim'], 3)
    return round(1.0 - p.get('none', 0.0), 3)


def decide(state, questions, opener=None, sleep=time.sleep, now=time.time):
    """ยิง Decisions API ครั้งเดียว (+retry 1 ครั้งเมื่อ 429/5xx/timeout) → answers dict หรือ None
    opener/sleep/now ฉีดได้สำหรับเทสต์ (ห้ามยิงจริงในเทสต์)"""
    global _cooldown_until
    if not ENABLED or not questions:
        return None
    if now() < _cooldown_until:
        return None
    opener = opener or urllib.request.urlopen
    body = json.dumps({'model': MODEL, 'state': state, 'questions': questions}, ensure_ascii=False).encode('utf-8')
    req = urllib.request.Request(JEV_URL, data=body, method='POST', headers={
        'Authorization': 'Bearer ' + KEY,
        'Content-Type': 'application/json',
    })
    t0 = now()
    last = ''
    for attempt in range(2):
        try:
            with opener(req, timeout=TIMEOUT) as r:
                data = json.loads(r.read().decode('utf-8'))
            answers = data.get('answers') if isinstance(data, dict) else None
            if not isinstance(answers, dict):
                print('[jev] reply without answers', flush=True)
                return None
            cost = (data.get('usage') or {}).get('cost') if isinstance(data.get('usage'), dict) else None
            print('[jev] q=%s cost=%s ms=%d' % (','.join(questions.keys()), cost if cost is not None else '?', int((now() - t0) * 1000)), flush=True)
            return answers
        except urllib.error.HTTPError as e:
            last = 'HTTP %s' % e.code
            try:
                last += ' ' + e.read().decode('utf-8', 'replace')[:120]
            except Exception:
                pass
            retry = e.code == 429 or e.code >= 500
        except Exception as e:   # timeout / network / JSON
            last = type(e).__name__ + ': ' + str(e)[:120]
            retry = True
        if not retry or attempt == 1:
            break
        sleep(RETRY_DELAY_S)
    _cooldown_until = now() + COOLDOWN_S
    print('[jev] unavailable (%s) — regex only for %ds' % (last, int(COOLDOWN_S)), flush=True)
    return None


def _cache_put(cache, k, v):
    if len(cache) >= CACHE_MAX:
        cache.pop(next(iter(cache)))
    cache[k] = v


def _claim_q(text):
    return {'type': 'choice',
            'instructions': 'ข้อความโฆษณานี้อ้างสรรพคุณต่อร่างกาย/สุขภาพ/ผิว/โรค ที่กฎโฆษณา อย. ห้ามหรือไม่: "%s"' % _trim(text, 300),
            'criteria': CLAIM_CRITERIA}


def deal_gate(name, desc, **kw):
    """ถามครั้งเดียวต่อดีล: เสี่ยง TikTok + คำบรรยายอ้างสรรพคุณ (เติม cache ให้ claim_prob(desc) ใช้ต่อ)
    → {'prob','choice'} ของ tt_risk หรือ None (Jev ใช้ไม่ได้)"""
    name = _trim(name, 200); desc = _trim(desc, 400)
    key = (name, desc)
    if key in _tt_cache:
        return _tt_cache[key]
    qs = {'tt_risk': {
        'type': 'choice',
        'instructions': 'สินค้านี้อยู่กลุ่มไหน — ใช้ตัดสินว่าคลิปจะเสี่ยงโดน TikTok ลบฐาน Community Guidelines (สุขภาพ/อาหารเสริม/ลดน้ำหนัก/อ้างผล) หรือไม่',
        'criteria': TT_CRITERIA,
    }}
    if desc and desc not in _claim_cache:
        qs['claim_desc'] = _claim_q(desc)
    ans = decide({'product_name': name, 'description': desc}, qs, **kw)
    if ans is None:
        return None
    tt = tt_from_answer(ans.get('tt_risk'))
    if tt is not None:
        _cache_put(_tt_cache, key, tt)
    if 'claim_desc' in qs:
        p = claim_from_answer(ans.get('claim_desc'))
        if p is not None:
            _cache_put(_claim_cache, desc, p)
    return tt


def claim_probs(texts, **kw):
    """texts = {key: ข้อความ} → {key: P(อ้างสรรพคุณ) | None} ถามเฉพาะที่ยังไม่อยู่ใน cache รวมใน request เดียว (≤ MAX_BATCH)"""
    out = {}
    ask = {}
    for k, t in (texts or {}).items():
        t = _trim(t, 300)
        if not t:
            out[k] = None
        elif t in _claim_cache:
            out[k] = _claim_cache[t]
        elif len(ask) < MAX_BATCH:
            ask[k] = t
            out[k] = None
        else:
            out[k] = None
    if not ask:
        return out
    qs = {('claim_%s' % k): _claim_q(t) for k, t in ask.items()}
    ans = decide({'texts': ask}, qs, **kw)
    if ans is None:
        return out
    for k, t in ask.items():
        p = claim_from_answer(ans.get('claim_%s' % k))
        if p is not None:
            _cache_put(_claim_cache, t, p)
            out[k] = p
    return out


def claim_prob(text, **kw):
    """ข้อความเดียว → P(อ้างสรรพคุณ) | None"""
    return claim_probs({'t': text}, **kw).get('t')
