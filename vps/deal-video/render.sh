#!/usr/bin/env bash
# deal-video sample: สร้างคลิป 9:16 ยาว 8 วิ จากรูปสินค้า 1 รูป (Ken Burns + ป้ายราคา + CTA)
# ข้อความทั้งหมดเรนเดอร์ด้วย libass (ASS subtitle) ไม่ใช้ drawtext —
# drawtext ทำวรรณยุกต์ที่ซ้อนบนสระบนหาย ("นึ่ง"→"นึง", "จิ๋ว"→"จิว") แม้ข้อความต้นทางครบ
set -euo pipefail
W=/root/deal-video
F=$W/fonts
S=$W/sample
mkdir -p "$F" "$S"
cd "$S"

for f in Kanit-Bold Kanit-SemiBold Kanit-Regular; do
  [ -s "$F/$f.ttf" ] || curl -sfL -o "$F/$f.ttf" "https://github.com/google/fonts/raw/main/ofl/kanit/$f.ttf"
done

# texts.json → subs.ass (UTF-8) + โหลดรูปสินค้า
python3 - <<'PY'
import json, urllib.request
t = json.load(open('texts.json', encoding='utf-8'))
req = urllib.request.Request(t['img'], headers={'User-Agent': 'Mozilla/5.0'})
open('product.jpg', 'wb').write(urllib.request.urlopen(req, timeout=20).read())

WHITE, GRAY, YELLOW = '&H00FFFFFF', '&H00E6E6E6', '&H003FD2FF'   # ASS = &HAABBGGRR
head = """[Script Info]
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
def ev(start, style, tags, text, end='0:00:08.00'):
    return 'Dialogue: 0,%s,%s,%s,,0,0,0,,{%s}%s\n' % (start, end, style, tags, text)

body  = ev('0:00:00.00', 'B', r'\an5\pos(360,118)\fs74\c' + WHITE, t['brand'])
body += ev('0:00:00.80', 'B', r'\an5\pos(586,198)\fs100\shad0\c' + WHITE, t['badge'])
body += ev('0:00:00.00', 'B', r'\an5\pos(360,846)\fs68\c' + WHITE, t['name'])
body += ev('0:00:01.40', 'R', r'\an5\pos(360,912)\fs58\fad(400,0)\c' + GRAY, t['old'])
body += ev('0:00:02.00', 'B', r'\an5\pos(360,1010)\fs155\fad(400,0)\c' + YELLOW, t['new'])
body += ev('0:00:03.20', 'B', r'\an5\pos(360,1160)\fs64\shad0\c' + WHITE, t['cta'])
body += ev('0:00:00.00', 'R', r'\an5\pos(360,1244)\fs46\alpha&H30&\c' + WHITE, t['handle'])
open('subs.ass', 'w', encoding='utf-8').write(head + body)
PY

cat > graph.txt <<EOF
[0:v]scale=720:1280:force_original_aspect_ratio=increase,crop=720:1280,boxblur=30:3,eq=brightness=-0.22:saturation=1.15,setsar=1[bg];
[1:v]scale=1200:1200:force_original_aspect_ratio=increase,crop=1200:1200,zoompan=z='min(zoom+0.0005,1.12)':d=240:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s=600x600:fps=30,setsar=1[fg];
[bg][fg]overlay=60:190:shortest=1,
drawbox=x=56:y=186:w=608:h=608:color=white@0.92:t=5,
drawbox=x=486:y=146:w=200:h=100:color=0xE53935@1:t=fill:enable='gte(t,0.8)',
drawbox=x=0:y=1108:w=720:h=104:color=0x8B5E3C@0.95:t=fill:enable='gte(t,3.2)',
ass=filename=$S/subs.ass:fontsdir=$F,
fade=t=in:st=0:d=0.4,fade=t=out:st=7.5:d=0.5,format=yuv420p[v]
EOF

ffmpeg -hide_banner -loglevel error -y \
  -loop 1 -framerate 30 -t 8 -i product.jpg \
  -i product.jpg \
  -f lavfi -t 8 -i anullsrc=r=44100:cl=stereo \
  -filter_complex_script graph.txt -map '[v]' -map 2:a \
  -c:v libx264 -preset veryfast -crf 22 -r 30 -c:a aac -b:a 64k \
  -shortest -movflags +faststart sample.mp4

ffmpeg -hide_banner -loglevel error -y -ss 4 -i sample.mp4 -frames:v 1 -q:v 3 frame_4s.jpg
ffmpeg -hide_banner -loglevel error -y -ss 4 -i sample.mp4 -frames:v 1 -vf "crop=720:120:0:815,scale=1440:240" zoom_name.png
ffmpeg -hide_banner -loglevel error -y -ss 4 -i sample.mp4 -frames:v 1 -vf "crop=720:110:0:1105,scale=1440:220" zoom_cta.png

ffprobe -v error -show_entries format=duration,size:stream=codec_name,width,height -of compact sample.mp4
