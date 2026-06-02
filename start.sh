#!/bin/bash
# start.sh
# ─────────────────────────────────────────────────────────────
# 구조 변경: Streamlit이 $PORT(외부) 직접 점유
#            FastAPI는 내부 8000 (OAuth 처리 전담)
#
# Render $PORT → Streamlit (WebSocket 직접 연결, 403 없음)
# /login/* /callback/* → Streamlit이 내부 FastAPI:8000으로 프록시
# ─────────────────────────────────────────────────────────────

set -e

echo "=== 영끌내집 서버 시작 ==="
echo "RENDER_EXTERNAL_URL: ${RENDER_EXTERNAL_URL:-없음(로컬)}"
echo "PORT: ${PORT:-8501}"

# 1. FastAPI 백그라운드 (내부 전용, 외부 노출 안 됨)
uvicorn main:app \
  --host 127.0.0.1 \
  --port 8000 \
  --workers 1 \
  --log-level info \
  &

FASTAPI_PID=$!
echo "FastAPI PID: $FASTAPI_PID (localhost:8000)"

# FastAPI 준비 대기
echo "FastAPI 준비 대기 중..."
for i in $(seq 1 20); do
  if curl -sf http://localhost:8000/health > /dev/null 2>&1; then
    echo "FastAPI 준비 완료 (${i}초)"
    break
  fi
  sleep 1
done

# 2. Streamlit 포그라운드 — $PORT 직접 점유 (Render가 이 포트를 외부에 노출)
echo "Streamlit 시작 → 0.0.0.0:${PORT:-8501}"
exec streamlit run streamlit_app.py \
  --server.port "${PORT:-8501}" \
  --server.address 0.0.0.0 \
  --server.headless true \
  --server.enableCORS false \
  --server.enableXsrfProtection false \
  --server.enableWebsocketCompression false
