"""
web_app.py
==========
구조:
  ┌─ Streamlit 메인 프레임 (Python) ────────────────────────┐
  │  · 카카오 OAuth 콜백 처리                               │
  │  · 로그인 버튼 ← 여기서 렌더링 (sandbox 없음, 리다이렉트 가능) │
  │  · 환영 배너 / 로그아웃 버튼                            │
  └──────────────────────────────────────────────────────────┘
  ┌─ components.html iframe ────────────────────────────────┐
  │  · 계산기 UI (index.html)                               │
  │  · 탭 클릭 시 로그인 필요 → sendLoginRequest() 호출    │
  │    → postMessage로 메인 프레임에 신호만 보냄            │
  │    → 실제 리다이렉트는 메인 프레임 JS가 처리            │
  └──────────────────────────────────────────────────────────┘

핵심 원칙:
  iframe(sandbox) 안에서는 절대 외부 URL로 이동하지 않음.
  로그인 리다이렉트는 반드시 메인 프레임에서만 처리.

Streamlit Cloud Secrets:
  KAKAO_REST_API_KEY = "YOUR_REST_API_KEY"

카카오 개발자 콘솔:
  - 카카오 로그인 활성화 ON
  - Redirect URI: https://youngzip.streamlit.app/
  - 동의항목: 닉네임(필수), 프로필 이미지·이메일(선택)
"""

import json
import secrets
import urllib.parse
from pathlib import Path

import requests
import streamlit as st
import streamlit.components.v1 as components

# ════════════════════════════════════════════════════════════
# 설정값
# ════════════════════════════════════════════════════════════
REST_API_KEY = st.secrets["KAKAO_REST_API_KEY"]
REDIRECT_URI = "https://youngzip.streamlit.app/"  # 콘솔 등록값과 1:1 일치

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

st.markdown("""
<style>
  .block-container{padding-top:0.8rem !important; padding-bottom:0 !important}
  header[data-testid="stHeader"]{display:none}
  iframe{border:none !important; display:block;}

  /* 로그인 버튼 */
  .kakao-login-wrap{text-align:center; padding:8px 0 4px;}
  a.kakao-btn{
    display:inline-flex; align-items:center; gap:10px;
    background:#FEE500; color:#191919 !important;
    font-weight:800; font-size:15px; text-decoration:none !important;
    padding:13px 28px; border-radius:8px;
    box-shadow:0 2px 10px rgba(254,229,0,.5);
  }
  a.kakao-btn:hover{background:#F5DC00;}
  .kakao-logo{
    width:24px; height:24px; flex-shrink:0;
  }

  /* 환영 배너 */
  .welcome-bar{
    display:flex; align-items:center; gap:14px;
    background:#FFFDE7; border:1.5px solid #FEE500;
    border-radius:12px; padding:12px 16px; margin-bottom:4px;
  }
  .welcome-name{font-size:15px; font-weight:800; color:#3A1D00;}
  .welcome-email{font-size:11px; color:#6B7280; margin-top:2px;}
</style>
""", unsafe_allow_html=True)


# ════════════════════════════════════════════════════════════
# OAuth 헬퍼
# ════════════════════════════════════════════════════════════

def build_auth_url(state: str) -> str:
    """
    카카오 인증 URL 생성.
    safe=':/' → redirect_uri 슬래시가 %2F로 인코딩되지 않도록 보장.
    """
    query = (
        f"response_type=code"
        f"&client_id={urllib.parse.quote(REST_API_KEY, safe='')}"
        f"&redirect_uri={urllib.parse.quote(REDIRECT_URI, safe=':/')}"
        f"&state={urllib.parse.quote(state, safe='')}"
    )
    return f"{AUTH_URL}?{query}"


def get_access_token(code: str) -> str | None:
    """인가 코드 → 액세스 토큰. 카카오는 POST + form-data."""
    try:
        r = requests.post(TOKEN_URL, data={
            "grant_type":   "authorization_code",
            "client_id":    REST_API_KEY,
            "redirect_uri": REDIRECT_URI,
            "code":         code,
        }, timeout=10)
        r.raise_for_status()
        return r.json().get("access_token")
    except Exception as e:
        st.error(f"토큰 발급 실패: {e}")
        return None


def get_profile(access_token: str) -> dict | None:
    """액세스 토큰 → 사용자 프로필."""
    try:
        r = requests.get(PROFILE_URL,
                         headers={"Authorization": f"Bearer {access_token}"},
                         timeout=10)
        r.raise_for_status()
        data    = r.json()
        acct    = data.get("kakao_account", {})
        profile = acct.get("profile", {})
        return {
            "id":            str(data.get("id", "")),
            "nickname":      profile.get("nickname", ""),
            "profile_image": profile.get("profile_image_url", ""),
            "email":         acct.get("email", ""),
        }
    except Exception as e:
        st.error(f"프로필 조회 실패: {e}")
        return None


# ════════════════════════════════════════════════════════════
# CSRF state 초기화 (항상 맨 먼저)
# ════════════════════════════════════════════════════════════
if "oauth_state" not in st.session_state:
    st.session_state["oauth_state"] = secrets.token_urlsafe(16)


# ════════════════════════════════════════════════════════════
# 콜백 처리 — 카카오가 ?code=...&state=... 로 돌아왔을 때
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
    if state and saved and state != saved:
        st.error("보안 검증 실패. 다시 시도해 주세요.")
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

    st.session_state.update({
        "logged_in":    True,
        "user_profile": prof,
        "access_token": token,
    })
    st.query_params.clear()
    st.rerun()


handle_callback()


# ════════════════════════════════════════════════════════════
# 로그인 상태
# ════════════════════════════════════════════════════════════
profile      = st.session_state.get("user_profile")
is_logged_in = bool(profile)
auth_url     = build_auth_url(st.session_state["oauth_state"])


# ════════════════════════════════════════════════════════════
# 상단 UI (메인 프레임 — sandbox 없음)
# ════════════════════════════════════════════════════════════

if is_logged_in:
    # ── 환영 배너 ──
    nickname = profile.get("nickname") or "사용자"
    email    = profile.get("email", "")
    img_url  = profile.get("profile_image", "")
    img_tag  = (
        f'<img src="{img_url}" '
        'style="width:40px;height:40px;border-radius:50%;object-fit:cover;flex-shrink:0">'
        if img_url else '<span style="font-size:28px">👤</span>'
    )
    st.markdown(f"""
    <div class="welcome-bar">
      {img_tag}
      <div>
        <div class="welcome-name">환영합니다, {nickname}님 👋</div>
        <div class="welcome-email">{email}</div>
      </div>
    </div>""", unsafe_allow_html=True)

    # ── 로그아웃 ──
    if st.button("로그아웃", key="logout_btn"):
        st.session_state.clear()
        logout_target = (
            f"{LOGOUT_URL}"
            f"?client_id={urllib.parse.quote(REST_API_KEY, safe='')}"
            f"&logout_redirect_uri={urllib.parse.quote(REDIRECT_URI, safe=':/')}"
        )
        # 메인 프레임에서 실행 → sandbox 없음 → 정상 동작
        st.markdown(
            f'<meta http-equiv="refresh" content="0;url={logout_target}">',
            unsafe_allow_html=True,
        )
        st.stop()

else:
    # ── 로그인 버튼 — 메인 프레임 <a href> → sandbox 없이 직접 이동 ──
    # href 를 Python에서 직접 주입하므로 JS 불필요, iframe 우회 불필요
    st.markdown(f"""
    <div class="kakao-login-wrap">
      <a href="{auth_url}" class="kakao-btn">
        <svg class="kakao-logo" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
          <path d="M12 3C6.477 3 2 6.477 2 10.8c0 2.7 1.632 5.076 4.1 6.48L5.1 21l4.72-2.52A11.6 11.6 0 0012 18.6c5.523 0 10-3.477 10-7.8S17.523 3 12 3z" fill="#191919"/>
        </svg>
        카카오 계정으로 로그인
      </a>
      <div style="font-size:11px;color:#9CA3AF;margin-top:10px">
        2·3탭 기능은 로그인 후 이용할 수 있습니다
      </div>
    </div>
    """, unsafe_allow_html=True)


# ════════════════════════════════════════════════════════════
# index.html 렌더링
# is_logged_in 만 주입 — auth_url은 더 이상 iframe 안에서 쓰지 않음
# ════════════════════════════════════════════════════════════

if not INDEX_PATH.exists():
    st.error(f"index.html을 찾을 수 없습니다: {INDEX_PATH}")
    st.stop()

html_raw = INDEX_PATH.read_text(encoding="utf-8")

inject = f"""
<script>
  /* web_app.py 주입 */
  var APP_LOGGED_IN = {json.dumps(is_logged_in)};
  /* APP_AUTH_URL 은 더 이상 iframe 안에서 사용하지 않음.
     로그인 버튼은 메인 프레임(Python)에서 렌더링됨. */
  var APP_AUTH_URL  = '';
</script>
"""
html_injected = html_raw.replace("<head>", "<head>" + inject, 1)

components.html(html_injected, height=900, scrolling=True)
