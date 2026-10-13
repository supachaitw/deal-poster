---
name: run-deal-poster
description: Run, smoke-test and drive Deal Poster on the VPS — render a test clip from the deal-video service, check n8n workflows/running executions, regenerate paiyaadeals.com and its click stats, read/export workflows safely. Use when asked to run, start, test, screenshot or check deal-poster / deal-video / the deals site.
---

Deal Poster is not an app you build from this repo: the live system is n8n workflows
(source of truth = n8n, this repo holds sanitized exports) plus two services that already
run on **this VPS (srv1277799)** — the `deal-video` container (`POST /render` → mp4) and the
static site generator `/root/deals-site/gen.py`. Drive all of it with
`.claude/skills/run-deal-poster/smoke.sh`; it renders one clip (nothing is posted), checks
n8n and the site, and leaves a frame of the clip at `/tmp/dp-smoke/frame.jpg`.

All paths are relative to the repo root (`/srv/claude/deal-poster` on the VPS).
Read `CLAUDE.md` before changing anything — it has the hard rules (secrets, deploy windows).

## Prerequisites

Only works on the VPS (docker containers `deal-video`, `n8n`, `deals-proxy` are local).
Everything needed is already installed there: `docker`, `python3`, `ffmpeg`, `jq`, `curl`.
Secrets come from `/root/home-metrics/.env` (`DP_N8N_KEY`, `DP_NOTION`) — never print them;
pipe anything that touches them through `python3 scripts/redact.py` (the `guard_bash` hook
blocks commands that don't).

## Run (agent path) — smoke driver

```bash
cd /srv/claude/deal-poster
sh .claude/skills/run-deal-poster/smoke.sh all | python3 scripts/redact.py
```

Modes: `all` (default) · `n8n` · `render` · `site`. Expected output (≈20 s):

- `n8n`: the 6 core workflows listed as `active`, `running executions: 0`, `safe to deploy deal-video: True`
  (False while a posting round is in progress — BKK xx:00–xx:25 of 00/06/09/12/15/18/21 — or an execution is running).
- `render`: `deal-video health ok`, `render ok X-Voice=0 … 13.5s ≈ 700 KB 16 s`, then
  `/tmp/dp-smoke/clip.mp4` + **`/tmp/dp-smoke/frame.jpg`** (look at it: product image, red −31% badge, Thai caption).
  The request has `voice:false` + `storyboard:false` and no `telegram/discord/tiktok/fb_reel` keys, so no TTS/Gemini
  spend and nothing is posted anywhere.
- `site`: last `gen.log` build line, real (non-bot) click stats, `https://paiyaadeals.com -> HTTP 200`, `/go?d=… -> 302`.

Render a different deal / with voice (TTS costs money, still posts nothing):

```bash
sh /root/deal-video/sample.sh      # voice + music clips of the same deal -> /root/deal-video/sample_{voice,music}.mp4
```

## Read / change n8n workflows

```bash
set -a; . /root/home-metrics/.env; set +a
N8N_KEY=$DP_N8N_KEY python3 scripts/n8n_get.py E6i2xEAcaUsUFKWm | python3 scripts/redact.py        # node list
N8N_KEY=$DP_N8N_KEY python3 scripts/n8n_get.py E6i2xEAcaUsUFKWm "Split Approved" | python3 scripts/redact.py   # one node's code
N8N_KEY=$DP_N8N_KEY python3 scripts/export_workflows.py | python3 scripts/redact.py                 # refresh workflows/*.json (sanitized)
```

Workflow IDs are in `CLAUDE.md` (table "Workflows"). To patch: `n8n_get.py <id> --raw-to FILE`,
edit, `PUT /api/v1/workflows/{id}` with `{name,nodes,connections,settings}`, then deactivate→activate.
**Never PUT a file from `workflows/` into n8n** (tokens are `REPLACE_*`).

## Deploy deal-video (only after `safe to deploy … True`)

```bash
cp vps/deal-video/service/server.py /root/deal-video/service/server.py   # repo -> live (or edit live, then copy back)
cd /root/deal-video/service && sh deploy.sh && sh /root/deal-video/sample.sh
```

Rebuild the site by hand (cron does it every 10 min): `python3 /root/deals-site/gen.py`
(`NO_RELOAD=1` skips the nginx reload; `gen.py stats` = click stats).

## Test

There is no unit-test suite in this repo; `smoke.sh` is the test. The bot repo next door has
`node --test` (`/srv/claude/discord-ops-bot`).

## Gotchas

- `docker exec deal-video wget …` fails: the image has no wget/curl — use `python3 -c "import urllib.request…"` inside the container (the driver does).
- n8n `GET /api/v1/workflows?limit=50` paginates and silently omitted Caption Writer → the driver GETs each id directly.
- `render` with `voice:true` on a quiet key hits Gemini/Azure; `voice:false` is the cheap path. Adding a `telegram`, `discord`, `tiktok` or `fb_reel` key to the request **posts for real** — don't, unless the (clip, deal) pair is correct (CLAUDE.md 2 Oct lesson).
- Rendering while a posting round is running only slows the round (service renders one request at a time); deploying (`deploy.sh`) during a round kills the clip in flight — hence the `safe to deploy` line.
- `gen.py stats` counts only clicks whose referer is our own site; raw `go.log` is ~99% the VPS health check + cloud scanners.
- The guard hook rejects heredocs that mention `api.notion.com`/`DP_NOTION` unless they carry `# noraw` **and** the whole command ends in `| python3 scripts/redact.py`; `grep` on `.env` files is blocked outright.

## Troubleshooting

- `FAIL: /root/home-metrics/.env missing` → not on the VPS, or the env file was moved; see `SETUP.md`.
- `OCI runtime exec failed … "wget": executable file not found` → see Gotchas; use python inside the container.
- `render` timeout (>300 s) → `docker logs --tail 50 deal-video`; Veo/storyboard calls can take minutes but are off in the smoke request, so a hang means ffmpeg OOM (container limit 700 m) or the service is mid-redeploy.
