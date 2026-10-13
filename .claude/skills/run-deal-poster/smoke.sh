#!/bin/sh
# Deal Poster smoke driver — run ON THE VPS (srv1277799) from the repo root:
#   sh .claude/skills/run-deal-poster/smoke.sh [render|site|n8n|all] | python3 scripts/redact.py
# Touches nothing that posts: renders one music-only clip (no telegram/tiktok/fb_reel keys), reads n8n, reads logs.
# Output files: /tmp/dp-smoke/clip.mp4 + frame.jpg (frame at 3 s = the "screenshot" of the rendered clip).
set -u
MODE=${1:-all}
OUT=/tmp/dp-smoke; mkdir -p "$OUT"
cd "$(dirname "$0")/../../.." || exit 1
fail() { echo "FAIL: $*"; exit 1; }

n8n_env() {   # DP_N8N_KEY / DP_NOTION live in /root/home-metrics/.env (chmod 600) — never echo them
  [ -f /root/home-metrics/.env ] || fail "/root/home-metrics/.env missing (see SETUP.md)"
  set -a; . /root/home-metrics/.env; set +a
  export N8N_KEY="${DP_N8N_KEY:?DP_N8N_KEY not in env file}"
}

if [ "$MODE" = n8n ] || [ "$MODE" = all ]; then
  n8n_env
  # Active workflows + running executions (deploying deal-video while running>0 or inside a posting round = forbidden, see CLAUDE.md)
  python3 - <<'PY' || fail "n8n API"
# noraw — prints names/ids/flags only
import json, os, urllib.request, datetime
H = {'X-N8N-API-KEY': os.environ['N8N_KEY']}
N = 'https://n8n.srv1277799.hstgr.cloud/api/v1'
# GET each id directly — the list endpoint paginates (limit=50 still missed Caption Writer) and would misreport 'MISSING'
want = {'E6i2xEAcaUsUFKWm': 'Deal Poster v1', 'e8aD2wCvsVYmefrq': 'Deal Caption Writer', 'JUE23JTCBbCsW1lS': 'Deal Intake Telegram',
        'Kq3cRuTbwF9cMkA1': 'Deal Intake Form', '731A7ASm8bI0F79B': 'Deal Intake LINE', 'UXGp6aS7EclTqCtl': 'Threads Token Keeper'}
for i, n in want.items():
    try:
        w = json.loads(urllib.request.urlopen(urllib.request.Request(N + '/workflows/' + i, headers=H), timeout=20).read())
        print('%-22s %s %s' % (n, i, 'active' if w.get('active') else 'INACTIVE'))
    except Exception as e:
        print('%-22s %s MISSING (%s)' % (n, i, str(e)[:60]))
ex = json.loads(urllib.request.urlopen(urllib.request.Request(N + '/executions?status=running&limit=20', headers=H), timeout=20).read())['data']
print('running executions:', len(ex))
h = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=7)))
inround = h.hour in (0, 6, 9, 12, 15, 18, 21) and h.minute < 25
print('BKK %s · posting round in progress: %s' % (h.strftime('%H:%M'), inround))
print('safe to deploy deal-video:', (len(ex) == 0 and not inround))
PY
fi

if [ "$MODE" = render ] || [ "$MODE" = all ]; then
  docker exec deal-video python3 -c "import urllib.request;assert b'true' in urllib.request.urlopen('http://localhost:8080/health',timeout=5).read()" || fail "deal-video /health"
  echo "deal-video health ok"
  # One music-only clip (voice:false = no TTS spend; no telegram/discord/tiktok/fb_reel keys = nothing is posted anywhere).
  docker exec -i deal-video python3 - <<'PY' || fail "render"
import json, urllib.request, time
deal = {"name": "SANWA SUPPLY Nylon Dual Phone Holding Casual Bag", "sale": 1008, "full": 1469,
        "desc": "กระเป๋าสะพายแคชชวลสำหรับใส่โทรศัพท์ขนาดใหญ่สองเครื่องพร้อมกัน", "cat": "gadget",
        "img": "https://lzd-img-push.slatic.net/lazada-creative-center/f71831a1-9f8b-447d-a7eb-66e09f43e26d.jpg", "voice": False, "storyboard": False}
t = time.time()
r = urllib.request.urlopen(urllib.request.Request('http://localhost:8080/render', json.dumps(deal).encode(), {'Content-Type': 'application/json'}), timeout=300)
data = r.read(); open('/tmp/smoke.mp4', 'wb').write(data)
print('render ok  X-Voice=%s X-Voice-Mode=%s X-Duration=%ss  %d KB  %.1fs' % (r.headers.get('X-Voice'), r.headers.get('X-Voice-Mode'), r.headers.get('X-Duration'), len(data) // 1024, time.time() - t))
PY
  docker cp deal-video:/tmp/smoke.mp4 "$OUT/clip.mp4" >/dev/null
  ffmpeg -hide_banner -loglevel error -y -ss 3 -i "$OUT/clip.mp4" -frames:v 1 "$OUT/frame.jpg" || fail "ffmpeg frame"
  ffprobe -v error -show_entries format=duration -of csv=p=0 "$OUT/clip.mp4" | sed 's/^/clip duration s: /'
  echo "screenshot: $OUT/frame.jpg"
  docker logs --since 5m deal-video 2>&1 | grep -E '^\[render\]|\[timing\]' | tail -3
fi

if [ "$MODE" = site ] || [ "$MODE" = all ]; then
  # Static site generator (Notion -> /root/deals-site/html) + its click stats. gen.py runs from cron every 10 min; NO_RELOAD=1 skips nginx reload.
  tail -1 /root/deals-site/gen.log
  python3 /root/deals-site/gen.py stats | head -4
  curl -s -o /dev/null -w 'https://paiyaadeals.com -> HTTP %{http_code} in %{time_total}s\n' https://paiyaadeals.com/
  id=$(grep -oE '^"[0-9a-f]{32}"' /root/deals-site/map/deals.map | head -1 | tr -d '"')
  curl -s -o /dev/null -w "/go?d=<first id> -> HTTP %{http_code} (302 = redirect to shop)\n" "https://paiyaadeals.com/go?d=$id"
fi
echo "smoke done ($MODE)"
