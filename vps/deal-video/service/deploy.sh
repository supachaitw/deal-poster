#!/bin/sh
# รันบน VPS: /root/deal-video/service/deploy.sh
# ไม่เปิด port ออกนอกเครื่อง ไม่มี label traefik — n8n เรียกภายใน network n8n_default ที่ http://deal-video:8080
set -e
cd "$(dirname "$0")"
rm -rf fonts music && cp -r /root/deal-video/fonts fonts && cp -r /root/deal-video/music music
docker build -q -t deal-video:latest .
docker rm -f deal-video 2>/dev/null || true
# .env = AZURE_SPEECH_KEY / AZURE_SPEECH_REGION (ค่าจริงอยู่หน้า Notion Config หัวข้อ Azure Speech · ไฟล์นี้ไม่อยู่ใน repo)
ENVF=""; [ -f .env ] && ENVF="--env-file .env"
docker run -d --name deal-video --restart unless-stopped --network n8n_default \
  --cpus 0.8 --memory 700m $ENVF deal-video:latest
sleep 2
docker exec n8n-n8n-1 wget -qO- http://deal-video:8080/health && echo
