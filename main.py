"""
main.py  ·  영끌내집 FastAPI — 단일 포트, Render 최적화
═══════════════════════════════════════════════════════════════
구조:
  Render $PORT → Streamlit (직접 점유, WebSocket 정상)
  내부 FastAPI(localhost:8000):
    /login/kakao     → 카카오 인증 URL 리다이렉트
    /login/naver     → 네이버 인증 URL 리다이렉트
    /callback/kakao  → 코드 수신 → JWT 발급 → BASE_URL?token=
    /callback/naver  → 코드 수신 → JWT 발급 → BASE_URL?token=
    /me?token=XXX    → JWT 검증 → 유저 정보 반환
    /health          → 헬스체크

시작 방식 (start.sh):
  1. FastAPI → localhost:8000 (내부 전용)
  2. Streamlit → 0.0.0.0:$PORT (외부 직접 노출, WebSocket 403 없음)

환경변수:
  KAKAO_REST_API_KEY    카카오 REST API 키
  NAVER_CLIENT_ID       네이버 Client ID
  NAVER_CLIENT_SECRET   네이버 Client Secret
  JWT_SECRET            랜덤 문자열 32자 이상
  RENDER_EXTERNAL_URL   Render가 자동 주입 (https://youngzip.onrender.com)
                        로컬: BASE_URL=http://localhost:8000 으로 대체
═══════════════════════════════════════════════════════════════
"""

import base64
import hashlib
import hmac
import json
import logging
import os
import time
import urllib.parse
from pathlib import Path

import httpx
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("youngzip")

# ════════════════════════════════════════════════════════════
# 환경변수 — Render는 RENDER_EXTERNAL_URL을 자동으로 주입함
# ════════════════════════════════════════════════════════════
KAKAO_KEY    = os.environ["KAKAO_REST_API_KEY"]
NAVER_ID     = os.environ["NAVER_CLIENT_ID"]
NAVER_SECRET = os.environ["NAVER_CLIENT_SECRET"]
JWT_SECRET   = os.environ["JWT_SECRET"]

# BASE_URL: Render는 RENDER_EXTERNAL_URL 자동 주입, 로컬은 BASE_URL 설정
BASE_URL = (
    os.environ.get("RENDER_EXTERNAL_URL")   # Render 배포 시 자동
    or os.environ.get("BASE_URL", "http://localhost:8000")  # 로컬 개발
).rstrip("/")

# OAuth 콜백 후 브라우저를 보낼 목적지
# Streamlit이 $PORT를 직접 점유하므로 외부 URL = BASE_URL
STREAMLIT_REDIRECT = BASE_URL   # 브라우저 리다이렉트용

KAKAO_REDIRECT = f"{BASE_URL}/callback/kakao"
NAVER_REDIRECT = f"{BASE_URL}/callback/naver"

log.info(f"BASE_URL: {BASE_URL}")
log.info(f"KAKAO_REDIRECT: {KAKAO_REDIRECT}")
log.info(f"NAVER_REDIRECT: {NAVER_REDIRECT}")

# ════════════════════════════════════════════════════════════
# JWT
# ════════════════════════════════════════════════════════════

def _sign(b64: str) -> str:
    return hmac.new(JWT_SECRET.encode(), b64.encode(), hashlib.sha256).hexdigest()


def issue_token(profile: dict, ttl: int = 7200) -> str:
    payload = json.dumps({**profile, "exp": int(time.time()) + ttl}, ensure_ascii=False)
    b64 = base64.urlsafe_b64encode(payload.encode()).decode().rstrip("=")
    return f"{b64}.{_sign(b64)}"


def verify_token(token: str) -> dict:
    try:
        b64, sig = token.rsplit(".", 1)
    except ValueError:
        raise HTTPException(401, "토큰 형식 오류")
    if not hmac.compare_digest(sig, _sign(b64)):
        raise HTTPException(401, "서명 불일치")
    pad = "=" * (4 - len(b64) % 4)
    try:
        payload = json.loads(base64.urlsafe_b64decode(b64 + pad))
    except Exception:
        raise HTTPException(401, "디코딩 실패")
    if payload.get("exp", 0) < int(time.time()):
        raise HTTPException(401, "토큰 만료")
    return payload


# ════════════════════════════════════════════════════════════
# HMAC state (CSRF 방지) — 세션 불필요
# ════════════════════════════════════════════════════════════

def make_state(provider: str) -> str:
    ts  = str(int(time.time()))
    sig = hmac.new(JWT_SECRET.encode(), f"{provider}:{ts}".encode(),
                   hashlib.sha256).hexdigest()[:16]
    return f"{provider}:{ts}:{sig}"


def verify_state(state: str, provider: str) -> bool:
    try:
        prov, ts, sig = state.split(":", 2)
        if prov != provider:
            return False
        if int(time.time()) - int(ts) > 600:
            return False
        expected = hmac.new(JWT_SECRET.encode(), f"{provider}:{ts}".encode(),
                            hashlib.sha256).hexdigest()[:16]
        return hmac.compare_digest(sig, expected)
    except Exception:
        return False


# ════════════════════════════════════════════════════════════
# FastAPI
# ════════════════════════════════════════════════════════════
app = FastAPI(docs_url=None, redoc_url=None)

# ── 헬스체크 ──────────────────────────────────────────────────
@app.get("/health")
async def health():
    return {"status": "ok", "base_url": BASE_URL}


# ── 유저 정보 API ────────────────────────────────────────────
@app.get("/me")
async def me(token: str = Query(...)):
    profile = verify_token(token)
    profile.pop("exp", None)
    return profile


# ════════════════════════════════════════════════════════════
# 카카오 OAuth
# ════════════════════════════════════════════════════════════

@app.get("/login/kakao")
async def login_kakao():
    state  = make_state("kakao")
    params = urllib.parse.urlencode({
        "response_type": "code",
        "client_id":     KAKAO_KEY,
        "redirect_uri":  KAKAO_REDIRECT,
        "state":         state,
    })
    url = f"https://kauth.kakao.com/oauth/authorize?{params}"
    log.info(f"카카오 로그인 시작 → {url[:80]}...")
    return RedirectResponse(url)


@app.get("/callback/kakao")
async def callback_kakao(
    code:  str = Query(...),
    state: str = Query(""),
    error: str = Query(""),
):
    log.info(f"카카오 콜백 수신 code={code[:10]}... state={state[:20]}...")

    if error:
        log.error(f"카카오 에러: {error}")
        return RedirectResponse(f"{STREAMLIT_REDIRECT}?login_error={error}")

    if not verify_state(state, "kakao"):
        log.error("state 검증 실패")
        return RedirectResponse(f"{STREAMLIT_REDIRECT}?login_error=state_mismatch")

    async with httpx.AsyncClient(timeout=15) as client:
        # 액세스 토큰
        r = await client.post(
            "https://kauth.kakao.com/oauth/token",
            data={
                "grant_type":   "authorization_code",
                "client_id":    KAKAO_KEY,
                "redirect_uri": KAKAO_REDIRECT,
                "code":         code,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        if r.status_code != 200:
            log.error(f"토큰 실패: {r.text}")
            return RedirectResponse(f"{STREAMLIT_REDIRECT}?login_error=token_fail")

        access_token = r.json().get("access_token")
        log.info("카카오 액세스 토큰 발급 성공")

        # 프로필
        r2 = await client.get(
            "https://kapi.kakao.com/v2/user/me",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        if r2.status_code != 200:
            return RedirectResponse(f"{STREAMLIT_REDIRECT}?login_error=profile_fail")

        data    = r2.json()
        acct    = data.get("kakao_account", {})
        profile = acct.get("profile", {})

    user = {
        "provider":      "kakao",
        "id":            str(data.get("id", "")),
        "nickname":      profile.get("nickname", ""),
        "profile_image": profile.get("profile_image_url", ""),
        "email":         acct.get("email", ""),
    }
    token = issue_token(user)
    log.info(f"카카오 로그인 성공: {user['nickname']}")
    return RedirectResponse(f"{STREAMLIT_REDIRECT}?token={token}")


# ════════════════════════════════════════════════════════════
# 네이버 OAuth
# ════════════════════════════════════════════════════════════

@app.get("/login/naver")
async def login_naver():
    state  = make_state("naver")
    params = urllib.parse.urlencode({
        "response_type": "code",
        "client_id":     NAVER_ID,
        "redirect_uri":  NAVER_REDIRECT,
        "state":         state,
    })
    url = f"https://nid.naver.com/oauth2.0/authorize?{params}"
    log.info(f"네이버 로그인 시작 → {url[:80]}...")
    return RedirectResponse(url)


@app.get("/callback/naver")
async def callback_naver(
    code:  str = Query(...),
    state: str = Query(""),
    error: str = Query(""),
):
    log.info(f"네이버 콜백 수신 code={code[:10]}...")

    if error:
        return RedirectResponse(f"{STREAMLIT_REDIRECT}?login_error={error}")

    if not verify_state(state, "naver"):
        log.error("state 검증 실패")
        return RedirectResponse(f"{STREAMLIT_REDIRECT}?login_error=state_mismatch")

    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.get(
            "https://nid.naver.com/oauth2.0/token",
            params={
                "grant_type":    "authorization_code",
                "client_id":     NAVER_ID,
                "client_secret": NAVER_SECRET,
                "code":          code,
                "state":         state,
            },
        )
        if r.status_code != 200:
            return RedirectResponse(f"{STREAMLIT_REDIRECT}?login_error=token_fail")

        access_token = r.json().get("access_token")

        r2 = await client.get(
            "https://openapi.naver.com/v1/nid/me",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        if r2.status_code != 200:
            return RedirectResponse(f"{STREAMLIT_REDIRECT}?login_error=profile_fail")

        data = r2.json()
        if data.get("resultcode") != "00":
            return RedirectResponse(f"{STREAMLIT_REDIRECT}?login_error=profile_fail")
        resp = data.get("response", {})

    user = {
        "provider":      "naver",
        "id":            resp.get("id", ""),
        "nickname":      resp.get("nickname", resp.get("name", "")),
        "profile_image": resp.get("profile_image", ""),
        "email":         resp.get("email", ""),
    }
    token = issue_token(user)
    log.info(f"네이버 로그인 성공: {user['nickname']}")
    return RedirectResponse(f"{STREAMLIT_REDIRECT}?token={token}")



