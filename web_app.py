"""
web_app.py — 영끌내집
======================
탭 권한:
  1탭(주담대 한도)   → 누구나
  2탭(정책대출 진단) → 로그인 필수
  3탭(맞춤유형 추천) → 로그인 필수

작동 방식:
  - APP_LOGGED_IN 변수를 index.html에 주입
  - 로그인 상태면 handleTabClick이 goTab(n)을 즉시 실행 → 2·3탭 정상 진입
  - 비로그인 상태에서 2·3탭 클릭 시 postMessage(NEED_LOGIN) 발송
    → Streamlit이 streamlit-js 없이도 components.html 위에
      로그인 안내를 st.empty() 로 덮어씌움 (단, rerun 필요)
  - 가장 간단한 해결: 비로그인이면 2·3탭 버튼 자체를 Python CSS로 비활성화
    + 계산기 위에 로그인 배너 상시 표시

Streamlit Cloud Secrets:
  NAVER_CLIENT_ID     = "YOUR_CLIENT_ID"
  NAVER_CLIENT_SECRET = "YOUR_CLIENT_SECRET"

Callback URL (네이버 개발자 센터 등록 필수):
  https://youngzip.streamlit.app
"""

import json
import secrets
import urllib.parse
from pathlib import Path

import requests
import streamlit as st
import streamlit.components.v1 as components

# ════════════════════════════════════════════════════════════
# ★ 설정값 구획 ★
# ════════════════════════════════════════════════════════════
CLIENT_ID     = st.secrets["NAVER_CLIENT_ID"]
CLIENT_SECRET = st.secrets["NAVER_CLIENT_SECRET"]
REDIRECT_URI  = "https://youngzip.streamlit.app"

AUTH_URL    = "https://nid.naver.com/oauth2.0/authorize"
TOKEN_URL   = "https://nid.naver.com/oauth2.0/token"
PROFILE_URL = "https://openapi.naver.com/v1/nid/me"
LOGOUT_URL  = "https://nid.naver.com/nidlogin.logout"

INDEX_PATH = Path(__file__).parent / "index.html"

# ── 페이지 설정 ──────────────────────────────────────────────
st.set_page_config(
    page_title="영끌내집 — 내 집 마련 계산기",
    page_icon="🏠",
    layout="centered",
    initial_sidebar_state="collapsed",
)

st.markdown("""
<style>
  .block-container{padding-top:0.5rem !important; padding-bottom:0 !important}
  header[data-testid="stHeader"]{display:none}
  iframe{border:none !important; display:block;}
  .naver-btn{
    display:inline-flex; align-items:center; gap:10px;
    background:#03C75A; color:#fff !important;
    font-weight:800; font-size:15px; text-decoration:none;
    padding:12px 26px; border-radius:8px;
    box-shadow:0 2px 10px rgba(3,199,90,.3);
    transition:background .15s;
  }
  .naver-btn:hover{background:#02b050;}
  .naver-n{
    width:22px; height:22px; background:#fff; border-radius:3px;
    display:inline-flex; align-items:center; justify-content:center;
    font-weight:900; color:#03C75A; font-size:14px; flex-shrink:0;
  }
  .welcome-bar{
    display:flex; align-items:center; gap:12px;
    background:#F0FDF4; border:1.5px solid #BBF7D0;
    border-radius:12px; padding:10px 14px; margin-bottom:8px;
  }
  .welcome-name{font-size:14px; font-weight:800; color:#065F46;}
  .welcome-email{font-size:11px; color:#6B7280; margin-top:1px;}
  /* 로그인 배너 (계산기 위에 표시) */
  .login-banner{
    display:flex; align-items:center; justify-content:space-between;
    background:#EFF6FF; border:1.5px solid #BFDBFE;
    border-radius:10px; padding:10px 16px; margin-bottom:8px; gap:12px;
  }
  .login-banner-text{font-size:12px; color:#1E40AF; font-weight:600;}
</style>
""", unsafe_allow_html=True)


# ════════════════════════════════════════════════════════════
# OAuth 헬퍼
# ════════════════════════════════════════════════════════════

def build_auth_url(state: str) -> str:
    return (
        f"{AUTH_URL}?"
        + urllib.parse.urlencode({
            "response_type": "code",
            "client_id":     CLIENT_ID,
            "redirect_uri":  REDIRECT_URI,
            "state":         state,
        })
    )

def get_access_token(code: str, state: str) -> str | None:
    try:
        r = requests.get(TOKEN_URL, params={
            "grant_type": "authorization_code",
            "client_id": CLIENT_ID, "client_secret": CLIENT_SECRET,
            "code": code, "state": state,
        }, timeout=10)
        r.raise_for_status()
        return r.json().get("access_token")
    except Exception as e:
        st.error(f"토큰 발급 실패: {e}")
        return None

def get_profile(access_token: str) -> dict | None:
    try:
        r = requests.get(PROFILE_URL,
            headers={"Authorization": f"Bearer {access_token}"}, timeout=10)
        r.raise_for_status()
        data = r.json()
        return data.get("response") if data.get("resultcode") == "00" else None
    except Exception as e:
        st.error(f"프로필 조회 실패: {e}")
        return None


# ════════════════════════════════════════════════════════════
# OAuth 콜백 처리
# ════════════════════════════════════════════════════════════

def handle_callback() -> None:
    qp    = st.query_params
    code  = qp.get("code")
    state = qp.get("state")
    saved = st.session_state.get("oauth_state")

    if not code or not state:
        return
    if st.session_state.get("logged_in"):
        st.query_params.clear(); return
    if state != saved:
        st.error("보안 검증 실패. 다시 시도해 주세요.")
        st.query_params.clear(); return

    with st.spinner("로그인 처리 중..."):
        token = get_access_token(code, state)
        if not token:
            st.query_params.clear(); return
        prof = get_profile(token)
        if not prof:
            st.query_params.clear(); return

    st.session_state["logged_in"]    = True
    st.session_state["user_profile"] = prof
    st.query_params.clear()
    st.rerun()


handle_callback()

# ════════════════════════════════════════════════════════════
# 상태
# ════════════════════════════════════════════════════════════
profile      = st.session_state.get("user_profile")
is_logged_in = bool(profile)

if "oauth_state" not in st.session_state:
    st.session_state["oauth_state"] = secrets.token_urlsafe(16)
auth_url = build_auth_url(st.session_state["oauth_state"])

logout_url_full = (
    f"{LOGOUT_URL}?returl={urllib.parse.quote(REDIRECT_URI, safe='')}"
)

# ════════════════════════════════════════════════════════════
# 상단 UI
# ════════════════════════════════════════════════════════════

if is_logged_in and profile:
    # ── 환영 배너 ──────────────────────────────────────────
    nickname = profile.get("nickname") or profile.get("name", "사용자")
    email    = profile.get("email", "")
    img_url  = profile.get("profile_image", "")
    img_tag  = (
        f'<img src="{img_url}" style="width:38px;height:38px;'
        f'border-radius:50%;object-fit:cover;flex-shrink:0">'
        if img_url else '<span style="font-size:24px">👤</span>'
    )
    st.markdown(f"""
    <div class="welcome-bar">
      {img_tag}
      <div>
        <div class="welcome-name">환영합니다, {nickname}님 👋</div>
        <div class="welcome-email">{email}</div>
      </div>
    </div>
    """, unsafe_allow_html=True)

    if st.button("로그아웃", key="logout_btn"):
        st.session_state.clear()
        st.markdown(
            f'<script>window.top.location.href="{logout_url_full}";</script>',
            unsafe_allow_html=True,
        )
        st.stop()

else:
    # ── 비로그인: 계산기 위에 로그인 유도 배너 표시 ─────────
    st.markdown(f"""
    <div class="login-banner">
      <span class="login-banner-text">
        🔒 정책대출 진단·맞춤유형 추천 탭은 로그인 후 이용 가능합니다.
      </span>
      <a href="{auth_url}" target="_top" class="naver-btn" style="font-size:13px;padding:8px 16px;white-space:nowrap">
        <span class="naver-n">N</span>로그인
      </a>
    </div>
    """, unsafe_allow_html=True)

# ════════════════════════════════════════════════════════════
# index.html 렌더링
# — APP_LOGGED_IN 주입으로 handleTabClick 내부에서 권한 판단
# — 로그인 상태이면 goTab(n) 즉시 실행, 비로그인이면 클릭 무반응
# ════════════════════════════════════════════════════════════

if not INDEX_PATH.exists():
    st.error(f"index.html 파일을 찾을 수 없습니다: {INDEX_PATH}")
    st.stop()

html_raw = INDEX_PATH.read_text(encoding="utf-8")

inject = f"""
<script>
/* ── web_app.py 주입 ── */
var APP_LOGGED_IN  = {json.dumps(is_logged_in)};
var APP_AUTH_URL   = {json.dumps(auth_url)};
var APP_LOGOUT_URL = {json.dumps(logout_url_full)};
</script>
"""

html_injected = html_raw.replace("<head>", "<head>" + inject, 1)
if not st.session_state.get("logged_in"):
    st.markdown(f"""
        <div style="text-align:center; padding:20px;">
            <a href="{auth_url}" target="_top" style="
                background:#03C75A; color:white; padding:15px 30px; 
                border-radius:10px; text-decoration:none; font-weight:bold;
                box-shadow: 0 4px 6px rgba(0,0,0,0.1);">
                네이버 계정으로 시작하기 (로그인)
            </a>
        </div>
    """, unsafe_allow_html=True)
components.html(html_injected, height=900, scrolling=True)
