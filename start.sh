#!/bin/bash
# start.sh

echo "=== 영끌내집 서버 시작 ==="
echo "RENDER_EXTERNAL_URL: ${RENDER_EXTERNAL_URL:-없음(로컬)}"
echo "PORT: ${PORT:-8501}"

# FastAPI 백그라운드 실행 (내부 전용 8000)
uvicorn main:app \
  --host 127.0.0.1 \
  --port 8000 \
  --workers 1 \
  --log-level info &

# FastAPI 준비 대기
echo "FastAPI 준비 대기 중..."
for i in $(seq 1 30); do
  if curl -sf http://localhost:8000/health > /dev/null 2>&1; then
    echo "FastAPI 준비 완료 (${i}초)"
    break
  fi
  sleep 1
done

# Streamlit 포그라운드 — $PORT 직접 점유
echo "Streamlit 시작 → 0.0.0.0:${PORT:-8501}"
exec streamlit run streamlit_app.py \
  --server.port "${PORT:-8501}" \
  --server.address 0.0.0.0 \
  --server.headless true \
  --server.enableCORS false \
  --server.enableXsrfProtection false \
  --server.enableWebsocketCompression false \
  --browser.serverAddress "youngzip.onrender.com" \
  --browser.serverPort 443 \
  --browser.gatherUsageStats false
