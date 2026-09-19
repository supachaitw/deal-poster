# deal-video render service (ffmpeg + libass + edge-tts) — ดู server.py
FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg \
 && rm -rf /var/lib/apt/lists/* \
 && pip install --no-cache-dir edge-tts==7.*
WORKDIR /app
COPY fonts/ /app/fonts/
COPY music/ /app/music/
COPY server.py /app/server.py
EXPOSE 8080
CMD ["python", "-u", "/app/server.py"]
