# รันบน host (python3 stdlib ล้วน) — วัดความยาวเสียงพากย์แต่ละท่อน แล้วจัดเวลาให้ข้อความบนจอ
# ขึ้นตรงกับตอนที่เสียงพูดถึง จากนั้นเขียน subs.ass + graph.txt + สั่ง ffmpeg
import json, math, subprocess, sys, urllib.request

VAR = sys.argv[1] if len(sys.argv) > 1 else 'female'   # female | male
W = '/root/deal-video'
F = W + '/fonts'
S = W + '/sample'
MUSIC = W + '/music/Carefree.mp3'
FPS = 30

t = json.load(open(S + '/texts.json', encoding='utf-8'))
req = urllib.request.Request(t['img'], headers={'User-Agent': 'Mozilla/5.0'})
open(S + '/product.jpg', 'wb').write(urllib.request.urlopen(req, timeout=20).read())

def dur(p):
    out = subprocess.check_output(['ffprobe', '-v', 'error', '-show_entries', 'format=duration',
                                   '-of', 'default=nw=1:nk=1', p])
    return float(out)

v = t['variants'][VAR]
n = len(v['vo'])
# ตัดช่วงเงียบหัว-ท้ายของแต่ละท่อน (edge-tts เติมเงียบมาให้ ทำให้จังหวะยืด)
# แล้วแต่งเนื้อเสียงให้ไม่ "แห้ง" แบบ TTS: ตัดเสียงทุ้มเกิน · บีบไดนามิกเบา ๆ แบบไมค์จริง ·
# เสียงสะท้อนห้องสั้นมาก (ให้รู้สึกว่าอัดในห้อง ไม่ใช่เสียงที่สังเคราะห์ลอย ๆ)
VOICE_FX = ('silenceremove=start_periods=1:start_threshold=-45dB:start_silence=0.04,areverse,'
            'silenceremove=start_periods=1:start_threshold=-45dB:start_silence=0.08,areverse,'
            'highpass=f=90,equalizer=f=200:t=q:w=1:g=1.5,equalizer=f=3500:t=q:w=1.2:g=2,'
            'acompressor=threshold=-20dB:ratio=2.5:attack=8:release=120:makeup=2,'
            'aecho=0.85:0.6:22|41:0.10|0.06')
for i in range(n):
    subprocess.check_call(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-y',
                           '-i', '%s/vo_%s_%d.mp3' % (S, VAR, i), '-af', VOICE_FX,
                           '%s/vo_%s_%d.wav' % (S, VAR, i)])
d = [dur('%s/vo_%s_%d.wav' % (S, VAR, i)) for i in range(n)]
LEAD, TAIL = 0.35, 1.2
gaps = v['gap']                                        # เว้นจังหวะไม่เท่ากัน แบบคนพูดจริง
starts = []
cur = LEAD
for i, x in enumerate(d):
    starts.append(cur)
    cur += x + (gaps[i] if i < len(gaps) else 0)
end_voice = starts[-1] + d[-1]
D = math.ceil((end_voice + TAIL) * 10) / 10          # ความยาวคลิปตามเสียงพากย์
s_old, s_new, s_cta = starts[1], starts[2], starts[3]
print('durations', [round(x, 2) for x in d], '| starts', [round(x, 2) for x in starts], '| clip', D)

def ts(sec):
    h = int(sec // 3600); m = int(sec % 3600 // 60); s = sec % 60
    return '%d:%02d:%05.2f' % (h, m, s)

WHITE, GRAY, YELLOW = '&H00FFFFFF', '&H00E6E6E6', '&H003FD2FF'
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
def ev(start, style, tags, text):
    return 'Dialogue: 0,%s,%s,%s,,0,0,0,,{%s}%s\n' % (ts(start), ts(D), style, tags, text)

body  = ev(0,     'B', r'\an5\pos(360,118)\fs74\c' + WHITE, t['brand'])
body += ev(0.8,   'B', r'\an5\pos(586,198)\fs100\shad0\c' + WHITE, t['badge'])
body += ev(0,     'B', r'\an5\pos(360,846)\fs68\c' + WHITE, t['name'])
body += ev(s_old, 'R', r'\an5\pos(360,912)\fs58\fad(300,0)\c' + GRAY, t['old'])
body += ev(s_new, 'B', r'\an5\pos(360,1010)\fs155\fad(300,0)\c' + YELLOW, t['new'])
body += ev(s_cta, 'B', r'\an5\pos(360,1160)\fs64\shad0\c' + WHITE, t['cta'])
body += ev(0,     'R', r'\an5\pos(360,1244)\fs46\alpha&H30&\c' + WHITE, t['handle'])
open(S + '/subs.ass', 'w', encoding='utf-8').write(head + body)

frames = int(round(D * FPS))
delays = ''.join('[%d:a]aformat=sample_rates=44100:channel_layouts=stereo,adelay=%d:all=1[a%d];\n'
                 % (i + 2, round(starts[i] * 1000), i) for i in range(n))
mix_in = ''.join('[a%d]' % i for i in range(n))
graph = f"""[0:v]scale=720:1280:force_original_aspect_ratio=increase,crop=720:1280,boxblur=30:3,eq=brightness=-0.22:saturation=1.15,setsar=1[bg];
[1:v]scale=1200:1200:force_original_aspect_ratio=increase,crop=1200:1200,zoompan=z='min(zoom+0.0005,1.14)':d={frames}:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s=600x600:fps={FPS},setsar=1[fg];
[bg][fg]overlay=60:190:shortest=1,
drawbox=x=56:y=186:w=608:h=608:color=white@0.92:t=5,
drawbox=x=486:y=146:w=200:h=100:color=0xE53935@1:t=fill:enable='gte(t,0.8)',
drawbox=x=0:y=1108:w=720:h=104:color=0x8B5E3C@0.95:t=fill:enable='gte(t,{s_cta:.2f})',
ass=filename={S}/subs.ass:fontsdir={F},
fade=t=in:st=0:d=0.4,fade=t=out:st={D - 0.5:.2f}:d=0.5,format=yuv420p[v];
{delays}{mix_in}amix=inputs={n}:normalize=0:duration=longest,apad,atrim=0:{D},volume=1.6[vo];
[{n + 2}:a]aformat=sample_rates=44100:channel_layouts=stereo,atrim=0:{D},asetpts=N/SR/TB,volume=0.14,afade=t=in:st=0:d=0.6,afade=t=out:st={D - 1.2:.2f}:d=1.2[mu];
[vo][mu]amix=inputs=2:normalize=0:duration=first,loudnorm=I=-14:TP=-1.5:LRA=11,aresample=44100[aout]
"""
open(S + '/graph.txt', 'w', encoding='utf-8').write(graph)

cmd = ['ffmpeg', '-hide_banner', '-loglevel', 'error', '-y',
       '-loop', '1', '-framerate', str(FPS), '-t', str(D), '-i', S + '/product.jpg',
       '-i', S + '/product.jpg']
for i in range(n):
    cmd += ['-i', '%s/vo_%s_%d.wav' % (S, VAR, i)]
cmd += ['-i', MUSIC,
        '-filter_complex_script', S + '/graph.txt', '-map', '[v]', '-map', '[aout]',
        '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '22', '-r', str(FPS),
        '-c:a', 'aac', '-b:a', '128k', '-movflags', '+faststart', '%s/sample_%s.mp4' % (S, VAR)]
subprocess.check_call(cmd)
print('rendered sample_%s.mp4' % VAR)
