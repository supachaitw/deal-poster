#!/bin/sh
# วิเคราะห์คลิป TikTok หรือ Instagram Reel จากลิงก์ (รันบน VPS): ดาวน์โหลด → เฟรม tile → ถอดเสียง/ข้อความ/โครงสร้างด้วย Gemini 2.5 Flash (key อยู่ใน container deal-video ไม่พิมพ์ออกมา)
#   sh scripts/tt_analyze.sh "https://vt.tiktok.com/XXXX/" [คำถามเพิ่มเติม]
# ผล: /tmp/tt_an/video.mp4, /tmp/tt_an/tile.jpg (ดูด้วย Read), ข้อความวิเคราะห์บน stdout
set -e
URL0="$1"; EXTRA="${2:-}"
[ -n "$URL0" ] || { echo "usage: $0 <tiktok url> [extra question]"; exit 1; }
D=/tmp/tt_an; mkdir -p "$D"; cd "$D"
UA="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0 Safari/537.36"
case "$URL0" in
  *instagram.com*)
    # Instagram (4 ต.ค. 69): หน้า HTML ตรง ๆ ไม่มี video_url (เป็น shell ขอล็อกอิน) แต่หน้า /embed/captioned/ render ด้วย headless chrome แล้วมี <video src>
    CODE=$(echo "$URL0" | sed -n 's#.*/\(reel\|p\|reels\)/\([A-Za-z0-9_-]*\).*#\2#p'); [ -n "$CODE" ] || { echo "ไม่พบรหัสโพสต์ใน URL"; exit 1; }
    docker run --rm zenika/alpine-chrome --no-sandbox --headless --disable-gpu --dump-dom --virtual-time-budget=10000 --user-agent="$UA" "https://www.instagram.com/reel/$CODE/embed/captioned/" > dom.html 2>/dev/null
    python3 - <<'PY'
import re, html
s = open('/tmp/tt_an/dom.html', encoding='utf-8', errors='ignore').read()
m = re.search(r'<video[^>]*src="([^"]+)"', s)
open('/tmp/tt_an/play.txt', 'w').write(html.unescape(m.group(1)) if m else '')
cap = re.search(r'class="Caption[^"]*"[^>]*>(.*?)</div>', s, re.S)
print('caption:', re.sub(r'<[^>]+>', ' ', cap.group(1))[:300] if cap else None)
print('video src found:', bool(m))
PY
    [ -s play.txt ] || { echo "ไม่พบวิดีโอ (โพสต์ส่วนตัว/ถูกลบ/เป็นรูป) — ขอให้ user ส่งไฟล์มาทาง Telegram แทน"; exit 2; }
    curl -sL -A "$UA" -e "https://www.instagram.com/" "$(cat play.txt)" -o video.mp4 ;;
  *)
    URL=$(curl -sIL -A "$UA" "$URL0" | grep -i '^location:' | tail -1 | tr -d '\r' | awk '{print $2}'); [ -n "$URL" ] || URL="$URL0"
    echo "resolved: ${URL%%\?*}"
    curl -sL -A "$UA" -c jar.txt "$URL" -o page.html
    python3 - <<'PY'
import re, json
s = open('/tmp/tt_an/page.html', encoding='utf-8', errors='ignore').read()
m = re.search(r'"playAddr":"((?:[^"\\]|\\.)*)"', s) or re.search(r'"downloadAddr":"((?:[^"\\]|\\.)*)"', s)
open('/tmp/tt_an/play.txt', 'w').write(json.loads('"' + m.group(1) + '"') if m else '')
d = re.search(r'"desc":"((?:[^"\\]|\\.)*)"', s); a = re.search(r'"uniqueId":"([^"]+)"', s); dur = re.search(r'"duration":(\d+)', s)
print('author:', a.group(1) if a else None, '| duration:', dur.group(1) if dur else None)
print('desc:', (json.loads('"' + d.group(1) + '"') if d else '')[:300])
print('playAddr found:', bool(m))
PY
    [ -s play.txt ] || { echo "no playAddr (หน้าอาจเป็น slideshow/ต้องล็อกอิน) — ลองเปิดลิงก์ในเบราว์เซอร์แล้วส่งไฟล์มาแทน"; exit 2; }
    curl -sL -A "$UA" -b jar.txt -e "https://www.tiktok.com/" -H "Range: bytes=0-" "$(cat play.txt)" -o video.mp4 ;;
esac
ffprobe -v error -select_streams v -show_entries stream=width,height,duration -of csv=p=0 video.mp4
ffmpeg -hide_banner -loglevel error -y -i video.mp4 -vf "fps=1/6,scale=200:-1,tile=6x2" -frames:v 1 tile.jpg && echo "tile: $D/tile.jpg"
cp video.mp4 /root/deal-video/tiktok/_tt_analyze.mp4
docker exec -i deal-video python3 - "$EXTRA" <<'PY'
import os, sys, json, base64, urllib.request
K = os.environ['GOOGLE_AI_KEY']
b = open('/tiktok/_tt_analyze.mp4', 'rb').read()
if len(b) > 19_000_000:
    print('video too large for inline (%d MB) — ตัดสั้นลงก่อน' % (len(b) // 1_000_000)); sys.exit(3)
q = ('นี่คือคลิปสั้นภาษาไทย (TikTok/Instagram) ช่วยวิเคราะห์ให้ครบและละเอียด: (1) คลิปนี้เกี่ยวกับอะไร ใครพูด/รูปแบบ (2) ถอดคำพูดและข้อความบนจอทั้งหมดตามลำดับเวลา (ใส่เวลาโดยประมาณ) '
     '(3) เทคนิค/ขั้นตอน/เครื่องมือที่สอนหรือใช้ ทีละข้อ (4) โครงสร้างการตัดต่อ: hook กี่วินาที, มุมกล้อง, การเคลื่อนกล้อง, ความยาวต่อฉาก, ตัวหนังสือบนจอ, เสียง/เพลง '
     '(5) ถ้าเป็นคลิปรีวิว/ขายสินค้า: สินค้าอะไร เล่าเรื่องยังไง CTA คืออะไร (6) แยกโครง Hook / Promise / Body / Open loop / CTA ของคลิปนี้พร้อมเวลา') + (('\n' + sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1] else '')
body = {'contents': [{'parts': [{'inline_data': {'mime_type': 'video/mp4', 'data': base64.b64encode(b).decode()}}, {'text': q}]}]}
r = json.load(urllib.request.urlopen(urllib.request.Request('https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent', json.dumps(body).encode(), {'Content-Type': 'application/json', 'x-goog-api-key': K}), timeout=300))
print(r['candidates'][0]['content']['parts'][0]['text'])
PY
rm -f /root/deal-video/tiktok/_tt_analyze.mp4
