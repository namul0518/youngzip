"""
main.py  ·  영끌내집 FastAPI 서버
═══════════════════════════════════════════════════════════════
역할:
  1. 카카오 / 네이버 OAuth 콜백 처리
  2. 로그인 성공 시 서명된 JWT 세션 토큰 발급
  3. Streamlit 앱으로 토큰을 전달 (/app?token=XXX)
  4. 정적 파일(calculator.html) 서빙
  5. /me API — Streamlit이 토큰으로 유저 정보 조회

흐름:
  브라우저
    → FastAPI /login/kakao  (카카오 인증 URL로 리다이렉트)
    → 카카오 로그인
    → FastAPI /callback/kakao  (code 수신 → 토큰 발급 → JWT 생성)
    → Streamlit /app?token=JWT
    → Streamlit이 /me?token=JWT 호출 → 유저 정보 반환

환경변수 (Railway Variables):
  KAKAO_REST_API_KEY
  NAVER_CLIENT_ID
  NAVER_CLIENT_SECRET
  JWT_SECRET          ← 아무 랜덤 문자열 (32자 이상)
  BASE_URL            ← https://yourapp.up.railway.app
  STREAMLIT_URL       ← http://localhost:8501  (같은 앱이면 이걸로)
═══════════════════════════════════════════════════════════════
"""

import hashlib
import hmac
import json
import os
import time
import urllib.parse
from pathlib import Path

import httpx
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

# ════════════════════════════════════════════════════════════
# 환경변수
# ════════════════════════════════════════════════════════════
KAKAO_KEY        = os.environ["KAKAO_REST_API_KEY"]
NAVER_ID         = os.environ["NAVER_CLIENT_ID"]
NAVER_SECRET     = os.environ["NAVER_CLIENT_SECRET"]
JWT_SECRET       = os.environ["JWT_SECRET"]
BASE_URL         = os.environ["BASE_URL"].rstrip("/")   # ex: https://xxx.up.railway.app
STREAMLIT_URL    = os.environ.get("STREAMLIT_URL", "http://localhost:8501")

KAKAO_REDIRECT   = f"{BASE_URL}/callback/kakao"
NAVER_REDIRECT   = f"{BASE_URL}/callback/naver"

# OAuth 엔드포인트
KAKAO_AUTH_URL   = "https://kauth.kakao.com/oauth/authorize"
KAKAO_TOKEN_URL  = "https://kauth.kakao.com/oauth/token"
KAKAO_PROFILE    = "https://kapi.kakao.com/v2/user/me"

NAVER_AUTH_URL   = "https://nid.naver.com/oauth2.0/authorize"
NAVER_TOKEN_URL  = "https://nid.naver.com/oauth2.0/token"
NAVER_PROFILE    = "https://openapi.naver.com/v1/nid/me"

STATE_TTL        = 600   # state 유효시간(초)

# ════════════════════════════════════════════════════════════
# JWT (서명된 토큰) — 외부 라이브러리 없이 직접 구현
# ════════════════════════════════════════════════════════════

def _sign(payload_b64: str) -> str:
    return hmac.new(
        JWT_SECRET.encode(),
        payload_b64.encode(),
        hashlib.sha256,
    ).hexdigest()


def issue_token(profile: dict, ttl: int = 3600) -> str:
    """사용자 프로필을 담은 서명 토큰 발급. ttl초 후 만료."""
    payload = json.dumps({
        **profile,
        "exp": int(time.time()) + ttl,
    }, ensure_ascii=False)
    import base64
    b64 = base64.urlsafe_b64encode(payload.encode()).decode().rstrip("=")
    sig = _sign(b64)
    return f"{b64}.{sig}"


def verify_token(token: str) -> dict:
    """토큰 검증 → 프로필 딕셔너리 반환. 실패 시 예외."""
    import base64
    try:
        b64, sig = token.rsplit(".", 1)
    except ValueError:
        raise HTTPException(401, "토큰 형식 오류")
    if not hmac.compare_digest(sig, _sign(b64)):
        raise HTTPException(401, "토큰 서명 불일치")
    padding = "=" * (4 - len(b64) % 4)
    try:
        payload = json.loads(base64.urlsafe_b64decode(b64 + padding))
    except Exception:
        raise HTTPException(401, "토큰 디코딩 실패")
    if payload.get("exp", 0) < int(time.time()):
        raise HTTPException(401, "토큰 만료")
    return payload


# ════════════════════════════════════════════════════════════
# HMAC state (CSRF 방지)
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
        if int(time.time()) - int(ts) > STATE_TTL:
            return False
        expected = hmac.new(JWT_SECRET.encode(), f"{provider}:{ts}".encode(),
                            hashlib.sha256).hexdigest()[:16]
        return hmac.compare_digest(sig, expected)
    except Exception:
        return False


# ════════════════════════════════════════════════════════════
# FastAPI 앱
# ════════════════════════════════════════════════════════════
app = FastAPI(docs_url=None, redoc_url=None)

# 정적 파일 서빙 (calculator.html 등)
STATIC_DIR = Path(__file__).parent / "static"
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


# ── 헬스체크 ──────────────────────────────────────────────────
@app.get("/health")
async def health():
    return {"status": "ok"}


# ════════════════════════════════════════════════════════════
# 카카오 로그인
# ════════════════════════════════════════════════════════════

@app.get("/login/kakao")
async def login_kakao():
    """카카오 인증 페이지로 리다이렉트"""
    state = make_state("kakao")
    params = {
        "response_type": "code",
        "client_id":     KAKAO_KEY,
        "redirect_uri":  KAKAO_REDIRECT,
        "state":         state,
    }
    url = f"{KAKAO_AUTH_URL}?{urllib.parse.urlencode(params)}"
    return RedirectResponse(url)


@app.get("/callback/kakao")
async def callback_kakao(
    code:  str = Query(...),
    state: str = Query(""),
    error: str = Query(""),
):
    """카카오 콜백 — code 수신 → 토큰 발급 → JWT → Streamlit으로"""
    if error:
        return RedirectResponse(f"{STREAMLIT_URL}?login_error={error}")
    if not verify_state(state, "kakao"):
        return RedirectResponse(f"{STREAMLIT_URL}?login_error=state_mismatch")

    async with httpx.AsyncClient() as client:
        # 액세스 토큰
        r = await client.post(KAKAO_TOKEN_URL, data={
            "grant_type":   "authorization_code",
            "client_id":    KAKAO_KEY,
            "redirect_uri": KAKAO_REDIRECT,
            "code":         code,
        }, headers={"Content-Type": "application/x-www-form-urlencoded"})
        if r.status_code != 200:
            return RedirectResponse(f"{STREAMLIT_URL}?login_error=token_fail")
        access_token = r.json().get("access_token")

        # 프로필
        r2 = await client.get(KAKAO_PROFILE,
                              headers={"Authorization": f"Bearer {access_token}"})
        if r2.status_code != 200:
            return RedirectResponse(f"{STREAMLIT_URL}?login_error=profile_fail")
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
    return RedirectResponse(f"{STREAMLIT_URL}?token={token}")


# ════════════════════════════════════════════════════════════
# 네이버 로그인
# ════════════════════════════════════════════════════════════

@app.get("/login/naver")
async def login_naver():
    """네이버 인증 페이지로 리다이렉트"""
    state = make_state("naver")
    params = {
        "response_type": "code",
        "client_id":     NAVER_ID,
        "redirect_uri":  NAVER_REDIRECT,
        "state":         state,
    }
    url = f"{NAVER_AUTH_URL}?{urllib.parse.urlencode(params)}"
    return RedirectResponse(url)


@app.get("/callback/naver")
async def callback_naver(
    code:  str = Query(...),
    state: str = Query(""),
    error: str = Query(""),
):
    """네이버 콜백 — code 수신 → 토큰 발급 → JWT → Streamlit으로"""
    if error:
        return RedirectResponse(f"{STREAMLIT_URL}?login_error={error}")
    if not verify_state(state, "naver"):
        return RedirectResponse(f"{STREAMLIT_URL}?login_error=state_mismatch")

    async with httpx.AsyncClient() as client:
        r = await client.get(NAVER_TOKEN_URL, params={
            "grant_type":    "authorization_code",
            "client_id":     NAVER_ID,
            "client_secret": NAVER_SECRET,
            "code":          code,
            "state":         state,
        })
        if r.status_code != 200:
            return RedirectResponse(f"{STREAMLIT_URL}?login_error=token_fail")
        access_token = r.json().get("access_token")

        r2 = await client.get(NAVER_PROFILE,
                              headers={"Authorization": f"Bearer {access_token}"})
        if r2.status_code != 200:
            return RedirectResponse(f"{STREAMLIT_URL}?login_error=profile_fail")
        data = r2.json()
        if data.get("resultcode") != "00":
            return RedirectResponse(f"{STREAMLIT_URL}?login_error=profile_fail")
        resp = data.get("response", {})

    user = {
        "provider":      "naver",
        "id":            resp.get("id", ""),
        "nickname":      resp.get("nickname", resp.get("name", "")),
        "profile_image": resp.get("profile_image", ""),
        "email":         resp.get("email", ""),
    }
    token = issue_token(user)
    return RedirectResponse(f"{STREAMLIT_URL}?token={token}")


# ════════════════════════════════════════════════════════════
# /me — Streamlit이 호출하는 유저 정보 API
# ════════════════════════════════════════════════════════════

@app.get("/me")
async def me(token: str = Query(...)):
    """JWT 검증 후 사용자 정보 반환. Streamlit에서 호출."""
    profile = verify_token(token)
    profile.pop("exp", None)
    return profile
