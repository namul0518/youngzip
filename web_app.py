"""
web_app.py
==========
역할:
  - 네이버 소셜 로그인 처리 (인증, 토큰, 프로필, 로그아웃)
  - 로그인 상태를 index.html 에 JS 변수로 주입하여 탭 권한 제어
  - 계산기 렌더링 (index.html)

탭 권한:
  1탭(주담대 한도)  → 비로그인도 사용 가능
  2탭(정책대출 진단) → 로그인 필수
  3탭(맞춤유형 추천) → 로그인 필수

Streamlit Cloud Secrets 설정:
  NAVER_CLIENT_ID     = "YOUR_CLIENT_ID"
  NAVER_CLIENT_SECRET = "YOUR_CLIENT_SECRET"

네이버 개발자 센터 Callback URL 등록 필수:
  https://youngzip.streamlit.app/
"""

import json
import secrets
import urllib.parse
from pathlib import Path

import requests
import streamlit as st
import streamlit.components.v1 as components

# ════════════════════════════════════════════════════════════
# ★ 설정값 구획 — st.secrets 에서만 읽음, 코드에 키값 없음 ★
# ════════════════════════════════════════════════════════════
CLIENT_ID     = st.secrets["NAVER_CLIENT_ID"]
CLIENT_SECRET = st.secrets["NAVER_CLIENT_SECRET"]
REDIRECT_URI  = "https://youngzip.streamlit.app/"  # 고정값

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

# ── 전역 CSS ─────────────────────────────────────────────────
st.markdown("""
<style>
  .block-container{padding-top:0.8rem !important; padding-bottom:0 !important}
  header[data-testid="stHeader"]{display:none}
  iframe{border:none !important; display:block;}
  /* 네이버 로그인 버튼 */
  .naver-btn{
    display:inline-flex; align-items:center; gap:10px;
    background:#03C75A; color:#fff !important;
    font-weight:800; font-size:15px; text-decoration:none;
    padding:13px 28px; border-radius:8px;
    box-shadow:0 2px 10px rgba(3,199,90,.35);
    transition:background .15s;
  }
  .naver-btn:hover{background:#02b050;}
  .naver-n{
    width:24px; height:24px; background:#fff; border-radius:4px;
    display:inline-flex; align-items:center; justify-content:center;
    font-weight:900; color:#03C75A; font-size:16px; flex-shrink:0;
  }
  /* 환영 배너 */
  .welcome-bar{
    display:flex; align-items:center; gap:14px;
    background:#F0FDF4; border:1.5px solid #BBF7D0;
    border-radius:12px; padding:12px 16px; margin-bottom:10px;
  }
  .welcome-name{font-size:15px; font-weight:800; color:#065F46;}
  .welcome-email{font-size:11px; color:#6B7280; margin-top:2px;}
</style>
""", unsafe_allow_html=True)


# ════════════════════════════════════════════════════════════
# OAuth 헬퍼 함수
# ════════════════════════════════════════════════════════════

def build_auth_url(state: str) -> str:
    params = {
        "response_type": "code",
        "client_id":     CLIENT_ID,
        "redirect_uri":  REDIRECT_URI,
        "state":         state,
    }
    return f"{AUTH_URL}?{urllib.parse.urlencode(params)}"


def get_access_token(code: str, state: str) -> str | None:
    params = {
        "grant_type":    "authorization_code",
        "client_id":     CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "code":          code,
        "state":         state,
    }
    try:
        r = requests.get(TOKEN_URL, params=params, timeout=10)
        r.raise_for_status()
        return r.json().get("access_token")
    except Exception as e:
        st.error(f"토큰 발급 실패: {e}")
        return None


def get_profile(access_token: str) -> dict | None:
    headers = {"Authorization": f"Bearer {access_token}"}
    try:
        r = requests.get(PROFILE_URL, headers=headers, timeout=10)
        r.raise_for_status()
        data = r.json()
        if data.get("resultcode") == "00":
            return data.get("response", {})
        st.error(f"프로필 오류: {data.get('message')}")
        return None
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
        st.query_params.clear()
        return
    if state != saved:
        st.error("보안 검증 실패 (state 불일치). 다시 시도해 주세요.")
        st.query_params.clear()
        return

    with st.spinner("로그인 처리 중..."):
        token = get_access_token(code, state)
        if not token:
            st.query_params.clear()
            return
        prof = get_profile(token)
        if not prof:
            st.query_params.clear()
            return

    st.session_state["logged_in"]    = True
    st.session_state["user_profile"] = prof
    st.query_params.clear()
    st.rerun()


handle_callback()


# ════════════════════════════════════════════════════════════
# 로그인 상태 확인
# ════════════════════════════════════════════════════════════

profile     = st.session_state.get("user_profile")
is_logged_in = bool(profile)

# CSRF state (로그인 전 항상 준비)
if "oauth_state" not in st.session_state:
    st.session_state["oauth_state"] = secrets.token_urlsafe(16)
auth_url = build_auth_url(st.session_state["oauth_state"])

# ════════════════════════════════════════════════════════════
# 상단 UI: 환영 배너(로그인 후) or 로그인 유도 배너(로그인 전)
# ════════════════════════════════════════════════════════════

if is_logged_in:
    nickname = profile.get("nickname") or profile.get("name", "사용자")
    email    = profile.get("email", "")
    img_url  = profile.get("profile_image", "")

    img_tag = (
        f'<img src="{img_url}" '
        f'style="width:40px;height:40px;border-radius:50%;object-fit:cover;flex-shrink:0">'
        if img_url else '<span style="font-size:28px">👤</span>'
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
        return_url    = urllib.parse.quote(REDIRECT_URI, safe="")
        logout_target = f"{LOGOUT_URL}?returl={return_url}"
        # st.markdown script는 Streamlit 메인 프레임에서 실행되므로 정상 작동
        st.markdown(
            f'<meta http-equiv="refresh" content="0;url={logout_target}">',
            unsafe_allow_html=True,
        )
        st.stop()

# ════════════════════════════════════════════════════════════
# index.html 렌더링
# 로그인 상태(is_logged_in)와 로그인 URL(auth_url)을
# JS 변수로 주입하여 index.html 내부에서 탭 권한 제어
# ════════════════════════════════════════════════════════════

if not INDEX_PATH.exists():
    st.error(f"index.html 파일을 찾을 수 없습니다: {INDEX_PATH}")
    st.stop()

html_raw = INDEX_PATH.read_text(encoding="utf-8")

# <head> 바로 뒤에 JS 변수 주입 (index.html 수정 불필요)
inject = f"""
<script>
  /* web_app.py 주입: 탭 권한 제어용 변수 */
  var APP_LOGGED_IN  = {json.dumps(is_logged_in)};
  var APP_AUTH_URL   = {json.dumps(auth_url)};
  var APP_LOGOUT_URL = {json.dumps(f"{LOGOUT_URL}?returl={urllib.parse.quote(REDIRECT_URI, safe='')}")};
</script>
"""
html_injected = html_raw.replace("<head>", "<head>" + inject, 1)

# height=900, scrolling=True: iframe 내부 스크롤로 처리
components.html(html_injected, height=900, scrolling=True)
