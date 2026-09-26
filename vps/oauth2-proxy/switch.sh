#!/usr/bin/env bash
# switch the Home Console between basic-auth (home-auth) and Google login (oauth2-proxy)
#   bash /root/oauth2-proxy/switch.sh          -> Google login (needs CLIENT_ID/SECRET in /root/oauth2-proxy/.env)
#   bash /root/oauth2-proxy/switch.sh rollback -> back to basic-auth (proxies left running, harmless)
# after the switch:
#   home.srv1277799.hstgr.cloud  -> only e-mails in emails.txt (owner), whole console
#   dp.srv1277799.hstgr.cloud    -> any Google account, only /dealposter.html + /api/dealposter*
set -euo pipefail
D=/root/oauth2-proxy
COMPOSE_HOME=/docker/n8n/docker-compose.home.yml
HOME_HOST=home.srv1277799.hstgr.cloud
DP_HOST=dp.srv1277799.hstgr.cloud

recreate_home() {
  ( cd /docker/n8n && docker compose -f docker-compose.home.yml up -d --no-build --no-deps --force-recreate home home-metrics )
  sleep 4
}
flip() {  # $1 = from, $2 = to  (routers home + home-api only; the dp-* routers always use google-auth-dp)
  sed -i -E "s/(traefik\.http\.routers\.home(-api)?\.middlewares=)$1/\1$2/" "$COMPOSE_HOME"
  grep -nE 'routers\.home(-api)?\.middlewares=' "$COMPOSE_HOME"
  recreate_home
}

if [ "${1:-}" = "rollback" ]; then
  flip google-auth home-auth
  echo "home. basic-auth again: $(curl -s -o /dev/null -w '%{http_code}' https://$HOME_HOST/) (expect 401)"
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
[ -s "$D/emails.txt" ] || { echo "put the owner's Gmail address in $D/emails.txt"; exit 1; }

# --- start both proxies and check they answer through traefik ---
( cd "$D" && docker compose up -d )
for c in oauth2-proxy oauth2-proxy-dp; do
  for i in 1 2 3 4 5 6 7 8; do sleep 2; docker exec "$c" wget -qO- http://localhost:4180/ping >/dev/null 2>&1 && break; done
done
ok=1
for h in $HOME_HOST $DP_HOST; do
  code=$(curl -s -o /dev/null -w '%{http_code}' "https://$h/oauth2/auth")
  loc=$(curl -s -o /dev/null -w '%{redirect_url}' "https://$h/oauth2/start")
  echo "$h  /oauth2/auth -> $code (expect 401) · /oauth2/start -> ${loc:0:45} (expect accounts.google.com)"
  [ "$code" = "401" ] && [[ "$loc" == https://accounts.google.com/* ]] || ok=0
done
[ "$ok" = 1 ] || { echo "a proxy is not healthy — NOT switching. docker logs oauth2-proxy / oauth2-proxy-dp"; exit 1; }

# --- switch routers (also applies the dp-* router labels in the compose file) ---
flip home-auth google-auth
echo "home./          -> $(curl -s -o /dev/null -w '%{http_code} %{redirect_url}' https://$HOME_HOST/ | cut -c1-60) (expect 302 accounts.google.com)"
echo "home./course    -> $(curl -s -o /dev/null -w '%{http_code}' https://$HOME_HOST/course.html) (expect 200, still public)"
echo "dp./            -> $(curl -s -o /dev/null -w '%{http_code} %{redirect_url}' https://$DP_HOST/) (expect 302 /dealposter.html)"
echo "dp./dealposter  -> $(curl -s -o /dev/null -w '%{http_code} %{redirect_url}' https://$DP_HOST/dealposter.html | cut -c1-60) (expect 302 accounts.google.com)"
echo "dp./index.html  -> $(curl -s -o /dev/null -w '%{http_code}' https://$DP_HOST/index.html) (expect 404)"
echo "dp./api/metrics -> $(curl -s -o /dev/null -w '%{http_code}' https://$DP_HOST/api/metrics) (expect 404)"
