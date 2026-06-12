# chord-transcriber web app — 本番用イメージ
FROM python:3.12-slim

# ffmpeg（m4a/aac 等の変換）と libsndfile（soundfile が使用）
RUN apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Render / Cloud Run などは待受ポートを $PORT で渡す
ENV PORT=8000
EXPOSE 8000

# 音声解析は時間がかかるためワーカータイムアウトを延長。
# 無料枠(メモリ512MB想定)で OOM しないようワーカーは1。
CMD ["sh", "-c", "gunicorn -w 1 -t 180 -b 0.0.0.0:${PORT} webapp:app"]
