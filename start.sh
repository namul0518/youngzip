#!/bin/bash
# start.sh
# ─────────────────────────────────────────────────────────────
# 실행 순서:
#   1. Streamlit → localhost:8501 (내부용, 외부 노출 안 됨)
#   2. FastAPI   → 0.0.0.0:$PORT (Render가 외부에 노출)
#
# Render는 $PORT 환경변수를 자동 주입함 (기본 10000번대)
# RENDER_EXTERNAL_URL도 자동 주입 → main.py에서 BASE_URL로 사용
# ─────────────────────────────────────────────────────────────

set -e

echo "=== 영끌내집 서버 시작 ==="
echo "BASE_URL(RENDER): ${RENDER_EXTERNAL_URL:-없음(로컬모드)}"
echo "PORT: ${PORT:-8000}"

# 1. Streamlit 백그라운드 실행
streamlit run streamlit_app.py \
  --server.port 8501 \
  --server.address 127.0.0.1 \
  --server.headless true \
  --server.enableCORS false \
  --server.enableXsrfProtection false \
  --server.enableWebsocketCompression false \
  &

STREAMLIT_PID=$!
echo "Streamlit PID: $STREAMLIT_PID (localhost:8501)"

# Streamlit이 뜰 때까지 최대 30초 대기
echo "Streamlit 준비 대기 중..."
for i in $(seq 1 30); do
  if curl -sf http://localhost:8501/healthz > /dev/null 2>&1; then
    echo "Streamlit 준비 완료 (${i}초)"
    break
  fi
  sleep 1
done

# 2. FastAPI 포그라운드 실행 (Render가 이 프로세스를 바라봄)
echo "FastAPI 시작 → 0.0.0.0:${PORT:-8000}"
exec uvicorn main:app \
  --host 0.0.0.0 \
  --port "${PORT:-8000}" \
  --workers 1 \
  --log-level info
