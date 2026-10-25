"""gcost.py - estimate spend on the shared Google AI Studio prepaid credit (deal-video + lofi).

25 ต.ค. 69 (user: 'โพสทุกรอบใช้ไปเท่าไหร่ เหลือเท่าไหร่แจ้งผมด้วย' + 'รวม lofi ด้วย'):
Google has no API for the prepaid balance, so every billed call is written to a ledger with the
cost computed from usageMetadata × the published per-token price, and the balance is
'last balance the user read off the Billing page' minus everything logged since.

Ledgers (one JSON object per line: t, src, kind, model, in, out, usd):
  /tiktok/gcost.jsonl          deal-video (TTS, alignment, storyboard, storyboard check, Veo)
  /lofilogs/gcost.jsonl        lofi lyria-gen.py ($0.08 per song) - host /opt/lofi/logs, mounted ro
Balance anchor: /tiktok/gcost_balance.json {thb, at}  ← set from the Billing page:
  docker exec deal-video python3 /app/gcost.py set 974.34
  docker exec deal-video python3 /app/gcost.py status
"""
import json, os, sys, time

LEDGER = os.environ.get('GCOST_LEDGER', '/tiktok/gcost.jsonl')
LOFI_LEDGER = os.environ.get('GCOST_LOFI_LEDGER', '/lofilogs/gcost.jsonl')
BAL_FILE = os.environ.get('GCOST_BALANCE', '/tiktok/gcost_balance.json')
# Billing page: 'THB8,398.13 Billing Account Tier Cap' = Tier 1's $250 ceiling → 33.59 THB/USD (25 ต.ค. 69)
THB_PER_USD = float(os.environ.get('GCOST_THB_PER_USD', '33.59'))

# USD per 1M tokens (input, output) - ai.google.dev/gemini-api/docs/pricing, paid tier, read 25 ต.ค. 69
# 3.8 models double from 1 Jan 2027 (the page says so); thinking tokens bill as output
PRICES = {
    'gemini-3.8-flash-tts': (0.50, 9.00),
    'gemini-3.1-flash-tts-preview': (1.00, 20.00),
    'gemini-2.5-flash-preview-tts': (0.50, 10.00),
    'gemini-2.5-pro-preview-tts': (1.00, 20.00),
    'gemini-3.1-flash-image': (0.50, 60.00),        # 2K image ≈ $0.101
    'gemini-3.8-flash': (0.75, 3.75),
    'gemini-2.5-flash': (0.30, 2.50),               # audio input is $1.00 - only used for images here
}
PRICES_2027 = {'gemini-3.8-flash-tts': (1.00, 18.00), 'gemini-3.8-flash': (1.50, 7.50)}
UNKNOWN = (1.00, 20.00)   # not in the table → count high rather than low
# Veo is per second of video (not on the pricing page any more; values from the Oct 2026 notes in CLAUDE.md)
VEO_PER_S = {'lite': 0.05, 'fast': 0.10, 'std': 0.40}


def price(model):
    m = (model or '').replace('-preview', '') if (model or '').startswith('gemini-3.1-flash-image') else (model or '')
    if time.time() >= 1798736400:   # 2027-01-01 00:00 UTC+7
        if m in PRICES_2027:
            return PRICES_2027[m]
    return PRICES.get(m, UNKNOWN)


def _write(rec, path=LEDGER):
    try:
        with open(path, 'a') as f:
            f.write(json.dumps(rec) + '\n')
    except Exception as e:
        print('[gcost] write failed: %s' % str(e)[:80], flush=True)


def add_tokens(kind, model, usage):
    """usage = usageMetadata of a generateContent reply. Never throws."""
    try:
        u = usage or {}
        tin = int(u.get('promptTokenCount') or 0)
        tout = int(u.get('candidatesTokenCount') or 0) + int(u.get('thoughtsTokenCount') or 0)
        pi, po = price(model)
        usd = (tin * pi + tout * po) / 1e6
        _write({'t': round(time.time(), 1), 'src': 'deal', 'kind': kind, 'model': model, 'in': tin, 'out': tout, 'usd': round(usd, 6)})
    except Exception as e:
        print('[gcost] add failed: %s' % str(e)[:80], flush=True)


def add_veo(model, seconds):
    try:
        tier = 'lite' if 'lite' in (model or '') else 'fast' if 'fast' in (model or '') else 'std'
        usd = VEO_PER_S[tier] * float(seconds)
        _write({'t': round(time.time(), 1), 'src': 'deal', 'kind': 'veo', 'model': model, 'sec': seconds, 'usd': round(usd, 4)})
    except Exception as e:
        print('[gcost] veo add failed: %s' % str(e)[:80], flush=True)


def _read(path):
    out = []
    try:
        for line in open(path):
            try:
                out.append(json.loads(line))
            except Exception:
                pass
    except FileNotFoundError:
        pass
    return out


def entries(since=0):
    return sorted([e for p in (LEDGER, LOFI_LEDGER) for e in _read(p) if e.get('t', 0) > since], key=lambda e: e['t'])


def anchor():
    try:
        return json.load(open(BAL_FILE))
    except Exception:
        return None


def set_balance(thb):
    a = {'thb': float(thb), 'at': round(time.time(), 1)}
    json.dump(a, open(BAL_FILE + '.new', 'w')); os.replace(BAL_FILE + '.new', BAL_FILE)
    return a


def balance():
    """(estimated THB left, anchor) or (None, None) when never set"""
    a = anchor()
    if not a:
        return None, None
    return a['thb'] - sum(e['usd'] for e in entries(a['at'])) * THB_PER_USD, a


KIND_TH = {'tts': 'เสียงพากย์', 'align': 'จับจังหวะเสียง', 'storyboard': 'storyboard', 'sb_check': 'ตรวจ storyboard', 'veo': 'Veo', 'lyria': 'เพลง lofi'}


def summary(since, until=None):
    es = [e for e in entries(since) if until is None or e['t'] <= until]
    by = {}
    for e in es:
        k = e.get('kind') if e.get('src') == 'deal' else 'lyria'
        by[k] = by.get(k, 0) + e['usd'] * THB_PER_USD
    return sum(by.values()), by, len(es)


def report_text(since, until=None, title='รอบนี้'):
    tot, by, n = summary(since, until)
    parts = ' · '.join('%s ฿%.2f' % (KIND_TH.get(k, k), v) for k, v in sorted(by.items(), key=lambda x: -x[1]))
    left, a = balance()
    es = entries(time.time() - 3 * 86400)
    span = (time.time() - es[0]['t']) / 86400 if es else 0   # ledger เพิ่งเริ่ม → ยังไม่คำนวณจำนวนวัน (ต้องมีข้อมูล ≥ 12 ชม.)
    per_day = (sum(e['usd'] for e in es) * THB_PER_USD / span) if span >= 0.5 else 0
    lines = ['💳 Google AI Studio %s ใช้ไป ~฿%.2f%s' % (title, tot, (' (%s)' % parts) if parts else '')]
    if left is not None:
        when = time.strftime('%d/%m %H:%M', time.gmtime(a['at'] + 7 * 3600))
        days = (' · ราว %.0f วัน ที่ ~฿%.0f/วัน' % (left / per_day, per_day)) if per_day > 1 else ''
        lines.append('คงเหลือประมาณ ฿%.0f%s  (ประมาณจาก ฿%.2f ที่อ่านจากหน้า Billing %s น.)' % (left, days, a['thb'], when))
        if left < 200:
            lines.append('⚠️ ใกล้หมด — เติมที่ https://ai.studio/projects → Billing แล้วส่งยอดใหม่มาให้ตั้งค่า')
    return '\n'.join(lines)


if __name__ == '__main__':
    cmd = sys.argv[1] if len(sys.argv) > 1 else 'status'
    if cmd == 'set':
        print(set_balance(sys.argv[2]))
    elif cmd == 'status':
        print(report_text(time.time() - 86400, title='24 ชม.'))
    else:
        sys.exit('usage: gcost.py set <thb> | status')
