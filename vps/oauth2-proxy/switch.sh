#!/usr/bin/env bash
# switch home.srv1277799.hstgr.cloud between basic-auth (home-auth) and Google login (google-auth via oauth2-proxy)
#   bash /root/oauth2-proxy/switch.sh          -> Google login (needs CLIENT_ID/SECRET in /root/oauth2-proxy/.env)
#   bash /root/oauth2-proxy/switch.sh rollback -> back to basic-auth (oauth2-proxy container left running, harmless)
set -euo pipefail
D=/root/oauth2-proxy
COMPOSE_HOME=/docker/n8n/docker-compose.home.yml
HOST=home.srv1277799.hstgr.cloud

flip() {  # $1 = from, $2 = to
  sed -i -E "s/(traefik\.http\.routers\.home(-api)?\.middlewares=)$1/\1$2/" "$COMPOSE_HOME"
  grep -nE 'routers\.home(-api)?\.middlewares=' "$COMPOSE_HOME"
  ( cd /docker/n8n && docker compose -f docker-compose.home.yml up -d --no-build --no-deps --force-recreate home home-metrics )
  sleep 4
}

if [ "${1:-}" = "rollback" ]; then
  flip google-auth home-auth
  echo "home. now basic-auth again: $(curl -s -o /dev/null -w '%{http_code}' https://$HOST/) (expect 401)"
  exit 0
fi

# --- preflight ---
. "$D/.env"
[ -n "${OAUTH2_PROXY_CLIENT_ID:-}" ] && [ -n "${OAUTH2_PROXY_CLIENT_SECRET:-}" ] || { echo "fill OAUTH2_PROXY_CLIENT_ID / OAUTH2_PROXY_CLIENT_SECRET in $D/.env first"; exit 1; }
if [ -z "${OAUTH2_PROXY_COOKIE_SECRET:-}" ]; then
  [ -s "$D/.cookie-secret" ] || python3 -c "import secrets,base64;print(base64.urlsafe_b64encode(secrets.token_bytes(32)).decode())" > "$D/.cookie-secret"
  echo "OAUTH2_PROXY_COOKIE_SECRET=$(cat "$D/.cookie-secret")" >> "$D/.env"
fi
chmod 600 "$D/.env" "$D/.cookie-secret" 2>/dev/null || true
[ -s "$D/emails.txt" ] || { echo "put the allowed Gmail address(es) in $D/emails.txt (one per line)"; exit 1; }

# --- start proxy and check it answers ---
( cd "$D" && docker compose up -d )
for i in 1 2 3 4 5 6; do sleep 2; docker exec oauth2-proxy wget -qO- http://localhost:4180/ping >/dev/null 2>&1 && break; done
code=$(curl -s -o /dev/null -w '%{http_code}' "https://$HOST/oauth2/auth")
loc=$(curl -s -o /dev/null -w '%{redirect_url}' "https://$HOST/oauth2/start")
echo "/oauth2/auth -> $code (expect 401) · /oauth2/start -> ${loc:0:60} (expect accounts.google.com)"
[ "$code" = "401" ] && [[ "$loc" == https://accounts.google.com/* ]] || { echo "oauth2-proxy not healthy — not switching. docker logs oauth2-proxy"; exit 1; }

# --- switch routers ---
flip home-auth google-auth
loc=$(curl -s -o /dev/null -w '%{http_code} %{redirect_url}' "https://$HOST/")
echo "home. now: $loc (expect 302 to accounts.google.com)"
echo "course.html still public: $(curl -s -o /dev/null -w '%{http_code}' https://$HOST/course.html) (expect 200)"
