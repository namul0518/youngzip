#!/bin/bash
# start.sh — Railway 시작 스크립트
# nginx → FastAPI(8000) + Streamlit(8501) 앞단 리버스 프록시

set -e

# nginx.conf의 ${PORT} 치환
envsubst '${PORT}' < /app/nginx.conf > /tmp/nginx.conf

# FastAPI 백그라운드 실행
uvicorn main:app --host 127.0.0.1 --port 8000 &

# Streamlit 백그라운드 실행
streamlit run streamlit_app.py \
  --server.port 8501 \
  --server.address 127.0.0.1 \
  --server.headless true \
  --server.enableCORS false \
  --server.enableXsrfProtection false &

# 두 서버가 뜰 때까지 잠깐 대기
sleep 3

# nginx 포그라운드 실행 (Railway가 이 프로세스를 바라봄)
nginx -c /tmp/nginx.conf -g 'daemon off;'
