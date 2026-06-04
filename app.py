"""
app.py  ·  영집: 영끌로 사는 똘똘한 내 집  ·  Streamlit 단독 배포
════════════════════════════════════════════════════════
구조: FastAPI 없음 · Nginx 없음 · 프록시 없음

OAuth 흐름:
  1. 로그인 버튼 → 네이버 인증 페이지 (현재 탭 이동)
  2. 인증 완료 → ?code=XXX&state=YYY 로 앱 복귀
  3. Streamlit이 직접 code 처리 → 세션 저장

Render 환경변수:
  NAVER_CLIENT_ID
  NAVER_CLIENT_SECRET
  HMAC_SECRET          ← 아무 랜덤 문자열 32자 이상
  RENDER_EXTERNAL_URL  ← Render 자동 주입
════════════════════════════════════════════════════════
"""

import base64
import hashlib
import hmac
import json
import os
import time
import urllib.parse
from pathlib import Path

import httpx
import streamlit as st
import streamlit.components.v1 as components

# ════════════════════════════════════════════════════════
# 환경변수
# ════════════════════════════════════════════════════════
NAVER_ID     = os.environ.get("NAVER_CLIENT_ID", "")
NAVER_SECRET = os.environ.get("NAVER_CLIENT_SECRET", "")
HMAC_SECRET  = os.environ.get("HMAC_SECRET", "dev_secret_change_in_production")

BASE_URL = (
    os.environ.get("RENDER_EXTERNAL_URL")
    or os.environ.get("BASE_URL", "http://localhost:8501")
).rstrip("/")

NAVER_REDIRECT = f"{BASE_URL}/"

# ════════════════════════════════════════════════════════
# HMAC state — 세션 없이 서명으로만 검증
# ════════════════════════════════════════════════════════

def _sig(msg: str) -> str:
    return hmac.new(
        HMAC_SECRET.encode(), msg.encode(), hashlib.sha256
    ).hexdigest()[:20]

def make_state(provider: str) -> str:
    ts = str(int(time.time()))
    return f"{provider}|{ts}|{_sig(f'{provider}|{ts}')}"

def verify_state(state: str, provider: str) -> bool:
    try:
        p, ts, sig = state.split("|", 2)
        if p != provider:
            return False
        if int(time.time()) - int(ts) > 600:
            return False
        return hmac.compare_digest(sig, _sig(f"{p}|{ts}"))
    except Exception:
        return False

# ════════════════════════════════════════════════════════
# OAuth URL 생성
# ════════════════════════════════════════════════════════

def naver_auth_url() -> str:
    return (
        "https://nid.naver.com/oauth2.0/authorize?"
        + urllib.parse.urlencode({
            "response_type": "code",
            "client_id":     NAVER_ID,
            "redirect_uri":  NAVER_REDIRECT,
            "state":         make_state("naver"),
        })
    )

# ════════════════════════════════════════════════════════
# 토큰 + 프로필 조회
# ════════════════════════════════════════════════════════

def naver_login(code: str, state: str) -> dict | None:
    with httpx.Client(timeout=15) as c:
        r = c.get(
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
            st.error(f"네이버 토큰 실패: {r.text}")
            return None
        access_token = r.json().get("access_token")

        r2 = c.get(
            "https://openapi.naver.com/v1/nid/me",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        if r2.status_code != 200:
            return None
        d = r2.json()
        if d.get("resultcode") != "00":
            return None
        resp = d.get("response", {})
        return {
            "provider":      "naver",
            "id":            resp.get("id", ""),
            "nickname":      resp.get("nickname", resp.get("name", "")),
            "profile_image": resp.get("profile_image", ""),
            "email":         resp.get("email", ""),
        }

# ════════════════════════════════════════════════════════
# 콜백 처리
# ════════════════════════════════════════════════════════

def handle_callback():
    qp    = st.query_params
    code  = qp.get("code")
    state = qp.get("state", "")
    error = qp.get("error", "")

    if error:
        st.query_params.clear()
        st.session_state["login_error"] = f"로그인 취소 또는 오류: {error}"
        return

    if not code:
        return

    if st.session_state.get("logged_in"):
        st.query_params.clear()
        return

    provider = state.split("|")[0] if "|" in state else ""

    if not verify_state(state, provider):
        st.query_params.clear()
        st.session_state["login_error"] = "보안 검증 실패. 다시 로그인해 주세요."
        return

    with st.spinner("로그인 처리 중..."):
        if provider == "naver":
            profile = naver_login(code, state)
        else:
            profile = None

    st.query_params.clear()

    if profile:
        st.session_state.update({
            "logged_in":    True,
            "user_profile": profile,
        })
        st.session_state.pop("login_error", None)
    else:
        st.session_state["login_error"] = "프로필 조회 실패. 다시 시도해 주세요."

    st.rerun()

# ════════════════════════════════════════════════════════
# 페이지 설정
# ════════════════════════════════════════════════════════
st.set_page_config(
    page_title="영집: 영끌로 사는 똘똘한 내 집",
    page_icon="🏠",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown("""
<style>
  html, body {
    overflow: visible !important;
    height: auto !important;
  }
  [data-testid="stAppViewContainer"] {
    overflow: visible !important;
    height: auto !important;
  }
  .stApp {
    height: auto !important;
    overflow: visible !important;
  }
  section[data-testid="stMain"] {
    overflow: visible !important;
    height: auto !important;
  }
  .block-container{
    padding-top:0.8rem !important;
    padding-bottom:0 !important;
    max-width:720px !important;
    margin:0 auto !important;
  }
  header[data-testid="stHeader"]{display:none}
  iframe{border:none !important; display:block; overflow:hidden;}

  .login-wrap{display:flex;gap:10px;justify-content:center;padding:6px 0 2px;flex-wrap:wrap;}
  a.naver-btn{
    display:inline-flex;align-items:center;gap:8px;
    background:#03C75A;color:#fff !important;
    font-weight:800;font-size:14px;text-decoration:none !important;
    padding:11px 28px;border-radius:8px;
    box-shadow:0 2px 8px rgba(3,199,90,.35);
  }
  .naver-n{
    width:20px;height:20px;background:#fff;border-radius:3px;
    display:inline-flex;align-items:center;justify-content:center;
    font-weight:900;color:#03C75A;font-size:13px;flex-shrink:0;
  }
  .welcome-bar{
    display:flex;align-items:center;gap:12px;
    background:#F0F9FF;border:1.5px solid #BAE6FD;
    border-radius:12px;padding:10px 14px;margin-bottom:4px;
  }
  .welcome-name{font-size:14px;font-weight:800;color:#0C4A6E;}
  .welcome-sub{font-size:11px;color:#6B7280;margin-top:1px;}
  .err-bar{
    background:#FEF2F2;border:1px solid #FECACA;
    border-radius:10px;padding:10px 14px;
    font-size:13px;color:#991B1B;margin-bottom:6px;
  }
</style>
""", unsafe_allow_html=True)

# ════════════════════════════════════════════════════════
# 콜백 처리 (반드시 UI 렌더링 전에 실행)
# ════════════════════════════════════════════════════════
handle_callback()

# ════════════════════════════════════════════════════════
# 로그인 상태
# ════════════════════════════════════════════════════════
profile      = st.session_state.get("user_profile")
is_logged_in = bool(profile)
login_error  = st.session_state.get("login_error")

if "naver_url" not in st.session_state:
    st.session_state["naver_url"] = naver_auth_url()

naver_url = st.session_state["naver_url"]

# ════════════════════════════════════════════════════════
# 상단 UI
# ════════════════════════════════════════════════════════

if login_error:
    st.markdown(f'<div class="err-bar">⚠️ {login_error}</div>',
                unsafe_allow_html=True)

if is_logged_in:
    nickname = profile.get("nickname") or "사용자"
    email    = profile.get("email", "")
    img_url  = profile.get("profile_image", "")

    img_tag = (
        f'<img src="{img_url}" style="width:38px;height:38px;'
        'border-radius:50%;object-fit:cover;flex-shrink:0">'
        if img_url else '<span style="font-size:26px">👤</span>'
    )
    st.markdown(f"""
    <div class="welcome-bar">
      {img_tag}
      <div>
        <div class="welcome-name">환영합니다, {nickname}님 👋</div>
        <div class="welcome-sub">🟢 네이버&nbsp;&nbsp;{email}</div>
      </div>
    </div>""", unsafe_allow_html=True)

    if st.button("로그아웃"):
        st.session_state.clear()
        st.rerun()

else:
    st.markdown(f"""
    <div class="login-wrap">
      <a href="{naver_url}" target="_self" class="naver-btn">
        <span class="naver-n">N</span>
        네이버 로그인
      </a>
    </div>
    <div style="text-align:center;font-size:11px;color:#9CA3AF;
    margin-top:6px;margin-bottom:2px">
      2·3탭 기능은 로그인 후 이용 가능합니다
    </div>
    """, unsafe_allow_html=True)

# ════════════════════════════════════════════════════════
# 계산기 렌더링
# ════════════════════════════════════════════════════════
CALC = Path(__file__).parent / "calculator.html"
if not CALC.exists():
    st.error("calculator.html 파일이 없습니다.")
    st.stop()

html = CALC.read_text(encoding="utf-8")
extra_css = """
<style>
  #loginGate button { display: none !important; }
</style>
"""
html = html.replace(
    "<head>",
    f"<head>{extra_css}<script>var APP_LOGGED_IN={json.dumps(is_logged_in)};var APP_AUTH_URL='';</script>",
    1,
)
components.html(html, height=2600, scrolling=False)
