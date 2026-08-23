#!/usr/bin/env bash
# deals-proxy — subdomain deals.srv1277799.hstgr.cloud -> n8n /webhook/deals
set -euo pipefail
DOMAIN="deals.srv1277799.hstgr.cloud"
NAME="deals-proxy"
NET="n8n_default"

docker rm -f "$NAME" 2>/dev/null || true
docker run -d --name "$NAME" --restart unless-stopped --network "$NET" \
  -v /root/deals-proxy/nginx.conf:/etc/nginx/conf.d/default.conf:ro \
  --label "traefik.enable=true" \
  --label "traefik.docker.network=${NET}" \
  --label "traefik.http.routers.deals.rule=Host(\`${DOMAIN}\`)" \
  --label "traefik.http.routers.deals.entrypoints=web,websecure" \
  --label "traefik.http.routers.deals.tls=true" \
  --label "traefik.http.routers.deals.tls.certresolver=mytlschallenge" \
  --label "traefik.http.services.deals.loadbalancer.server.port=80" \
  nginx:alpine
echo "started:"
docker ps --filter "name=${NAME}" --format "{{.Names}} | {{.Status}}"
