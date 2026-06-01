"""
web_app.py
==========
역할:
  - 카카오 소셜 로그인 처리 (인증, 토큰, 프로필, 로그아웃)
  - 로그인 상태를 index.html 에 JS 변수로 주입하여 탭 권한 제어
  - 계산기 렌더링 (index.html)

탭 권한:
  1탭(주담대 한도)   → 비로그인도 사용 가능
  2탭(정책대출 진단) → 로그인 필수
  3탭(맞춤유형 추천) → 로그인 필수

Streamlit Cloud Secrets 설정:
  KAKAO_REST_API_KEY = "YOUR_REST_API_KEY"

카카오 개발자 콘솔 설정 필수:
  - 카카오 로그인 → 활성화 ON
  - Redirect URI 등록: https://youngzip.streamlit.app
  - 동의항목: 닉네임(필수), 프로필 이미지(선택), 이메일(선택) 활성화
"""

import json
import secrets
import urllib.parse
from pathlib import Path

import requests
import streamlit as st
import streamlit.components.v1 as components

# ════════════════════════════════════════════════════════════
# 설정값 — st.secrets 에서만 읽음, 코드에 키값 없음
# ════════════════════════════════════════════════════════════
REST_API_KEY = st.secrets["KAKAO_REST_API_KEY"]

# 카카오 개발자 콘솔 Redirect URI 등록값과 1글자도 다르면 안 됨
REDIRECT_URI = "https://youngzip.streamlit.app"

AUTH_URL    = "https://kauth.kakao.com/oauth/authorize"
TOKEN_URL   = "https://kauth.kakao.com/oauth/token"
PROFILE_URL = "https://kapi.kakao.com/v2/user/me"
LOGOUT_URL  = "https://kauth.kakao.com/oauth/logout"

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
  /* 환영 배너 */
  .welcome-bar{
    display:flex; align-items:center; gap:14px;
    background:#FFFDE7; border:1.5px solid #FEE500;
    border-radius:12px; padding:12px 16px; margin-bottom:10px;
  }
  .welcome-name{font-size:15px; font-weight:800; color:#3A1D00;}
  .welcome-email{font-size:11px; color:#6B7280; margin-top:2px;}
</style>
""", unsafe_allow_html=True)


# ════════════════════════════════════════════════════════════
# OAuth 헬퍼 함수
# ════════════════════════════════════════════════════════════

def build_auth_url(state: str) -> str:
    """
    카카오 인증 요청 URL 생성.
    safe=':/' 로 redirect_uri의 슬래시가 %2F로 인코딩되는 것을 방지.
    """
    query = (
        f"response_type=code"
        f"&client_id={urllib.parse.quote(REST_API_KEY, safe='')}"
        f"&redirect_uri={urllib.parse.quote(REDIRECT_URI, safe=':/')}"
        f"&state={urllib.parse.quote(state, safe='')}"
    )
    return f"{AUTH_URL}?{query}"


def get_access_token(code: str) -> str | None:
    """인가 코드 → 액세스 토큰 교환. 카카오는 POST + form-data 방식."""
    data = {
        "grant_type":   "authorization_code",
        "client_id":    REST_API_KEY,
        "redirect_uri": REDIRECT_URI,
        "code":         code,
    }
    try:
        r = requests.post(TOKEN_URL, data=data, timeout=10)
        r.raise_for_status()
        return r.json().get("access_token")
    except Exception as e:
        st.error(f"토큰 발급 실패: {e}")
        return None


def get_profile(access_token: str) -> dict | None:
    """액세스 토큰 → 사용자 프로필 조회."""
    headers = {"Authorization": f"Bearer {access_token}"}
    try:
        r = requests.get(PROFILE_URL, headers=headers, timeout=10)
        r.raise_for_status()
        data          = r.json()
        kakao_account = data.get("kakao_account", {})
        profile       = kakao_account.get("profile", {})
        return {
            "id":            str(data.get("id", "")),
            "nickname":      profile.get("nickname", ""),
            "profile_image": profile.get("profile_image_url", ""),
            "email":         kakao_account.get("email", ""),
        }
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

    if not code:
        return
    if st.session_state.get("logged_in"):
        st.query_params.clear()
        return
    # state 불일치 → CSRF 의심, 차단
    if state and saved and state != saved:
        st.error("보안 검증 실패 (state 불일치). 다시 시도해 주세요.")
        st.query_params.clear()
        return

    with st.spinner("로그인 처리 중..."):
        token = get_access_token(code)
        if not token:
            st.query_params.clear()
            return
        prof = get_profile(token)
        if not prof:
            st.query_params.clear()
            return

    st.session_state["logged_in"]    = True
    st.session_state["user_profile"] = prof
    st.session_state["access_token"] = token
    st.query_params.clear()
    st.rerun()


handle_callback()


# ════════════════════════════════════════════════════════════
# 로그인 상태 확인
# ════════════════════════════════════════════════════════════

profile      = st.session_state.get("user_profile")
is_logged_in = bool(profile)

# CSRF state — 로그인 전 항상 준비
if "oauth_state" not in st.session_state:
    st.session_state["oauth_state"] = secrets.token_urlsafe(16)
auth_url = build_auth_url(st.session_state["oauth_state"])


# ════════════════════════════════════════════════════════════
# 상단 UI: 환영 배너(로그인 후) / 없음(로그인 전)
# ════════════════════════════════════════════════════════════

if is_logged_in:
    nickname = profile.get("nickname") or "사용자"
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
        # 카카오 로그아웃: 세션 만료 후 앱으로 복귀
        logout_target = (
            f"{LOGOUT_URL}"
            f"?client_id={urllib.parse.quote(REST_API_KEY, safe='')}"
            f"&logout_redirect_uri={urllib.parse.quote(REDIRECT_URI, safe=':/')}"
        )
        st.markdown(
            f'<meta http-equiv="refresh" content="0;url={logout_target}">',
            unsafe_allow_html=True,
        )
        st.stop()


# ════════════════════════════════════════════════════════════
# index.html 렌더링
# is_logged_in / auth_url 을 JS 변수로 주입 → 탭 권한 제어
# ════════════════════════════════════════════════════════════

if not INDEX_PATH.exists():
    st.error(f"index.html 파일을 찾을 수 없습니다: {INDEX_PATH}")
    st.stop()

html_raw = INDEX_PATH.read_text(encoding="utf-8")

inject = f"""
<script>
  /* web_app.py 주입: 탭 권한 제어용 변수 */
  var APP_LOGGED_IN = {json.dumps(is_logged_in)};
  var APP_AUTH_URL  = {json.dumps(auth_url)};
</script>
"""
html_injected = html_raw.replace("<head>", "<head>" + inject, 1)

components.html(html_injected, height=900, scrolling=True)
