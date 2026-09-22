#!/bin/sh
# สร้างคลิปตัวอย่าง 2 แบบจากดีลเดียวกัน (มีพากย์ / เพลงล้วน) ไว้ฟังเทียบตอนปรับเสียง
#
# รันบน VPS:  sh /root/deal-video/sample.sh
#             sh /root/deal-video/sample.sh '{"name":"...","sale":99,"full":199,"desc":"...","img":"https://..."}'
# ได้ไฟล์:     /root/deal-video/sample_voice.mp4  และ  sample_music.mp4
#
# ทำไมต้องมีสคริปต์นี้: คิวดีลว่างเมื่อไหร่ก็ไม่มีคลิปให้ฟัง และรอรอบโพสต์จริงรอบละ 3 ชม.
# ตัวนี้บังคับโหมดด้วยฟิลด์ "voice" ของ /render จึงเทียบสองแบบจากดีลเดียวกันได้ทันที
# (ดู CLAUDE.md หัวข้อ "บันทึกการปรับเสียง" — ทุกรอบที่ปรับต้องส่งตัวอย่างให้ user ฟังตัดสิน)
set -e
OUT=${OUT:-/root/deal-video}

docker exec -i deal-video python3 - "$@" <<'PY'
import json, sys, urllib.request

# ดีลตั้งต้น: มีครบทั้งราคาเต็ม/ราคาลด/คำบรรยาย จึงได้บทพูดครบทุกท่อน (hook→desc→old→new→cta)
deal = {
    "name": "SANWA SUPPLY Nylon Dual Phone Holding Casual Bag",
    "sale": 1008,
    "full": 1469,
    "desc": "กระเป๋าสะพายแคชชวลสำหรับใส่โทรศัพท์ขนาดใหญ่สองเครื่องพร้อมกัน",
    "img": "https://lzd-img-push.slatic.net/lazada-creative-center/f71831a1-9f8b-447d-a7eb-66e09f43e26d.jpg?x-oss-process=image/quality,q_80/format,jpg",
}
if len(sys.argv) > 1 and sys.argv[1].strip():
    deal.update(json.loads(sys.argv[1]))

for voice, fn in ((True, '/tmp/sample_voice.mp4'), (False, '/tmp/sample_music.mp4')):
    body = json.dumps(dict(deal, voice=voice)).encode('utf-8')
    req = urllib.request.Request('http://localhost:8080/render', body,
                                 {'Content-Type': 'application/json'})
    r = urllib.request.urlopen(req, timeout=300)
    data = r.read()
    with open(fn, 'wb') as f:
        f.write(data)
    print('%-26s X-Voice=%s  %ss  %d KB'
          % (fn, r.headers.get('X-Voice'), r.headers.get('X-Duration'), len(data) // 1024))
PY

docker cp deal-video:/tmp/sample_voice.mp4 "$OUT/sample_voice.mp4"
docker cp deal-video:/tmp/sample_music.mp4 "$OUT/sample_music.mp4"
ls -lh "$OUT"/sample_voice.mp4 "$OUT"/sample_music.mp4
