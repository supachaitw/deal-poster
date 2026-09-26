#!/usr/bin/env bash
# deals-site — public deals website at deals.srv1277799.hstgr.cloud
#   /root/deals-site/{gen.py,s.css}  generator (cron */10)   ·  /root/deals-site/html  static output
#   /root/deals-site/deals.map       id -> affiliate url for nginx `map` (gen.py reloads nginx when it changes)
#   /root/deals-proxy/nginx.conf     nginx config (kept at the old path so older notes still point somewhere real)
# Run on the VPS: bash /root/deals-site/deploy.sh   (recreates the deals-proxy container, ~2 s downtime)
set -euo pipefail
DOMAIN="deals.srv1277799.hstgr.cloud"
NAME="deals-proxy"
NET="n8n_default"
ROOT="/root/deals-site"

mkdir -p "$ROOT/html" "$ROOT/log" "$ROOT/cache"
touch "$ROOT/deals.map"
[ -s "$ROOT/html/index.html" ] || NO_RELOAD=1 python3 "$ROOT/gen.py"

docker rm -f "$NAME" 2>/dev/null || true
docker run -d --name "$NAME" --restart unless-stopped --network "$NET" \
  -v /root/deals-proxy/nginx.conf:/etc/nginx/conf.d/default.conf:ro \
  -v "$ROOT/deals.map:/etc/nginx/deals.map:ro" \
  -v "$ROOT/html:/usr/share/nginx/html:ro" \
  -v "$ROOT/log:/var/log/nginx" \
  -v "$ROOT/cache:/var/cache/nginx" \
  --label "traefik.enable=true" \
  --label "traefik.docker.network=${NET}" \
  --label "traefik.http.routers.deals.rule=Host(\`${DOMAIN}\`)" \
  --label "traefik.http.routers.deals.entrypoints=web,websecure" \
  --label "traefik.http.routers.deals.tls=true" \
  --label "traefik.http.routers.deals.tls.certresolver=mytlschallenge" \
  --label "traefik.http.services.deals.loadbalancer.server.port=80" \
  nginx:alpine

# cron: rebuild every 10 minutes (idempotent install)
LINE="*/10 * * * * /usr/bin/python3 $ROOT/gen.py >> $ROOT/gen.log 2>&1"
( crontab -l 2>/dev/null | grep -v "deals-site/gen.py" ; echo "$LINE" ) | crontab -
echo "started:"; docker ps --filter "name=${NAME}" --format "{{.Names}} | {{.Status}}"
