"""
web_app.py
==========
역할: 네이버 로그인 처리 + 탭 권한 제어 + index.html 계산기 렌더링

탭 권한:
  1탭(주담대 한도)   → 비로그인 가능
  2탭(정책대출 진단) → 로그인 필수
  3탭(맞춤유형 추천) → 로그인 필수

탭 전환 흐름:
  1. 사용자가 index.html 탭 버튼 클릭
  2. index.html: postMessage({type:'TAB_CLICK', tab:n}) 발송
  3. web_app.py: st.query_params 로 탭 번호 수신 (JS→Streamlit bridge)
     → 비로그인 + 2·3탭: Python이 직접 로그인 안내 렌더링 (iframe 밖)
     → 로그인 + 모든 탭: index.html 에 SET_TAB 메시지로 탭 전환 허가

Streamlit Cloud Secrets:
  NAVER_CLIENT_ID     = "YOUR_CLIENT_ID"
  NAVER_CLIENT_SECRET = "YOUR_CLIENT_SECRET"

네이버 개발자 센터 Callback URL:
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

# ── 전역 CSS ─────────────────────────────────────────────────
st.markdown("""
<style>
  .block-container{padding-top:0.5rem !important; padding-bottom:0 !important}
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
  /* 로그인 게이트 박스 */
  .login-gate{
    text-align:center; padding:48px 20px 36px;
    border:2px dashed #E2E8F0; border-radius:14px;
    background:#F8FAFC; margin-top:8px;
  }
  .login-gate-icon{font-size:38px; margin-bottom:14px;}
  .login-gate-title{font-size:16px; font-weight:800; color:#1E293B; margin-bottom:8px;}
  .login-gate-sub{font-size:13px; color:#64748B; margin-bottom:28px;}
  .login-gate-hint{font-size:11px; color:#CBD5E1; margin-top:16px;}
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
        st.error("보안 검증 실패. 다시 시도해 주세요.")
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
    # 탭 상태 초기화 (로그인 직후 1탭으로)
    st.session_state["active_tab"] = 0
    st.query_params.clear()
    st.rerun()


handle_callback()


# ════════════════════════════════════════════════════════════
# 탭 클릭 이벤트 수신 (index.html postMessage → query_params)
#
# index.html 의 handleTabClick(n) 이 postMessage 로 전달하지만
# Streamlit은 postMessage를 직접 받지 못하므로,
# 대신 index.html 안에 Streamlit.setComponentValue를 사용하는
# bridge snippet 을 주입해 query_params 로 탭번호를 전달한다.
# ════════════════════════════════════════════════════════════

# query_params 에서 탭 요청 수신
requested_tab = st.query_params.get("tab")
if requested_tab is not None:
    try:
        tab_num = int(requested_tab)
        st.session_state["active_tab"] = tab_num
    except ValueError:
        pass
    # query_params 에서 tab 제거 (중복 처리 방지)
    params = dict(st.query_params)
    params.pop("tab", None)
    st.query_params.update(params)
    st.rerun()

# 현재 활성 탭 (기본 0)
active_tab: int = st.session_state.get("active_tab", 0)
is_logged_in: bool = bool(st.session_state.get("user_profile"))

# CSRF state 준비
if "oauth_state" not in st.session_state:
    st.session_state["oauth_state"] = secrets.token_urlsafe(16)
auth_url = build_auth_url(st.session_state["oauth_state"])

# auth_url 검증
if not auth_url.startswith("https://nid.naver.com"):
    st.error("⚠️ 로그인 URL 생성 실패. CLIENT_ID 설정을 확인하세요.")
    st.stop()


# ════════════════════════════════════════════════════════════
# 상단 배너: 로그인 후 환영 / 로그인 전 미니 안내
# ════════════════════════════════════════════════════════════

profile = st.session_state.get("user_profile")

if is_logged_in and profile:
    nickname = profile.get("nickname") or profile.get("name", "사용자")
    email    = profile.get("email", "")
    img_url  = profile.get("profile_image", "")
    img_tag  = (
        f'<img src="{img_url}" '
        f'style="width:40px;height:40px;border-radius:50%;object-fit:cover;flex-shrink:0">'
        if img_url else '<span style="font-size:26px">👤</span>'
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
        # iframe 밖 최상위 창에서 네이버 서버 로그아웃
        st.markdown(
            f'<script>window.top.location.href="{logout_target}";</script>',
            unsafe_allow_html=True,
        )
        st.stop()


# ════════════════════════════════════════════════════════════
# 탭 권한 분기
# ════════════════════════════════════════════════════════════

# 비로그인 상태에서 2·3탭 요청 → active_tab 을 강제로 0으로
if not is_logged_in and active_tab in (1, 2):
    # 로그인 게이트를 iframe 밖(Python)에서 렌더링
    tab_name = "정책대출 진단" if active_tab == 1 else "맞춤 유형 추천"

    st.markdown(f"""
    <div class="login-gate">
      <div class="login-gate-icon">🔒</div>
      <div class="login-gate-title">로그인이 필요한 서비스입니다</div>
      <div class="login-gate-sub">
        <b>{tab_name}</b> 탭은 로그인 후 이용할 수 있습니다.
      </div>
      <a href="{auth_url}" target="_top" class="naver-btn">
        <span class="naver-n">N</span>네이버 계정으로 로그인
      </a>
      <div class="login-gate-hint">로그인 후 모든 기능을 무료로 이용할 수 있습니다.</div>
    </div>
    """, unsafe_allow_html=True)

    # index.html 은 1탭 활성화 상태로만 표시 (뒤에서 SET_TAB 0 주입)
    active_tab = 0


# ════════════════════════════════════════════════════════════
# index.html 렌더링
# ─ JS 변수 주입: APP_LOGGED_IN, APP_AUTH_URL
# ─ bridge snippet: handleTabClick → location.href 에 ?tab=N 추가
#   → Streamlit 이 query_params 로 읽어 active_tab 갱신 후 rerun
# ─ SET_TAB 메시지: active_tab 값으로 탭 강제 전환
# ════════════════════════════════════════════════════════════

if not INDEX_PATH.exists():
    st.error(f"index.html 파일을 찾을 수 없습니다: {INDEX_PATH}")
    st.stop()

html_raw = INDEX_PATH.read_text(encoding="utf-8")

logout_full = f"{LOGOUT_URL}?returl={urllib.parse.quote(REDIRECT_URI, safe='')}"

inject = f"""
<script>
/* ── web_app.py 주입 변수 ── */
var APP_LOGGED_IN  = {json.dumps(is_logged_in)};
var APP_AUTH_URL   = {json.dumps(auth_url)};
var APP_LOGOUT_URL = {json.dumps(logout_full)};
var APP_ACTIVE_TAB = {json.dumps(active_tab)};

/* ── handleTabClick: query_params 방식으로 Streamlit 에 탭번호 전달 ── */
/* index.html 의 handleTabClick(n) 이 이 함수를 호출한다 */
(function patchHandleTabClick(){{
  var _orig = window.handleTabClick || function(){{}};
  window.handleTabClick = function(n){{
    /* 1탭은 iframe 내부에서 즉시 전환 */
    if(n === 0){{ if(typeof goTab==='function') goTab(0); return; }}
    /* 2·3탭: 현재 페이지 URL 에 ?tab=N 추가 → Streamlit rerun 유발 */
    var url = window.top.location.href.split('?')[0];
    window.top.location.href = url + '?tab=' + n;
  }};
}})();

/* ── 페이지 로드 후 active_tab 으로 탭 강제 전환 ── */
window.addEventListener('DOMContentLoaded', function(){{
  if(typeof goTab === 'function'){{
    goTab(APP_ACTIVE_TAB);
  }}
}});
</script>
"""

html_injected = html_raw.replace("<head>", "<head>" + inject, 1)
components.html(html_injected, height=900, scrolling=True)
