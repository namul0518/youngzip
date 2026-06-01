"""
web_app.py
==========
역할: 네이버 소셜 로그인 처리 + 로그인 성공 시 index.html 계산기 표시.

배포 전 Streamlit Cloud Secrets 설정 (깃허브에 키값 올리지 마세요):
  Settings → Secrets 에 아래 내용 입력
  ─────────────────────────────────────────
  NAVER_CLIENT_ID     = "YOUR_CLIENT_ID"
  NAVER_CLIENT_SECRET = "YOUR_CLIENT_SECRET"
  NAVER_REDIRECT_URI  = "https://youngzip.streamlit.app"
  ─────────────────────────────────────────

로컬 테스트 시: .streamlit/secrets.toml 파일 생성 후 위 내용 입력.
"""

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
REDIRECT_URI  = st.secrets["https://youngzip.streamlit.app"]

# 네이버 OAuth 엔드포인트
AUTH_URL    = "https://nid.naver.com/oauth2.0/authorize"
TOKEN_URL   = "https://nid.naver.com/oauth2.0/token"
PROFILE_URL = "https://openapi.naver.com/v1/nid/me"
LOGOUT_URL  = "https://nid.naver.com/nidlogin.logout"

# index.html 경로 (web_app.py 와 같은 폴더)
INDEX_PATH  = Path(__file__).parent / "index.html"

# ── 페이지 설정 ──────────────────────────────────────────────
st.set_page_config(
    page_title="영집 — 내 집 마련 계산기",
    page_icon="🏠",
    layout="centered",
    initial_sidebar_state="collapsed",
)

# ── 전역 CSS: Streamlit 기본 여백 제거 + 로그인 버튼 스타일 ──
st.markdown("""
<style>
  /* Streamlit 기본 상단 여백 최소화 */
  .block-container{padding-top:1rem !important; padding-bottom:0 !important}
  header[data-testid="stHeader"]{display:none}
  /* 네이버 로그인 버튼 */
  .naver-btn{
    display:inline-flex;align-items:center;gap:10px;
    background:#03C75A;color:#fff !important;
    font-weight:800;font-size:15px;text-decoration:none;
    padding:13px 28px;border-radius:8px;
    box-shadow:0 2px 10px rgba(3,199,90,.35);
    transition:background .15s;
  }
  .naver-btn:hover{background:#02b050;}
  .naver-n{
    width:24px;height:24px;background:#fff;border-radius:4px;
    display:inline-flex;align-items:center;justify-content:center;
    font-weight:900;color:#03C75A;font-size:16px;flex-shrink:0;
  }
  /* 사용자 환영 배너 */
  .welcome-bar{
    display:flex;align-items:center;gap:14px;
    background:#F0FDF4;border:1.5px solid #BBF7D0;
    border-radius:12px;padding:12px 16px;margin-bottom:14px;
  }
  .welcome-name{font-size:15px;font-weight:800;color:#065F46}
  .welcome-email{font-size:11px;color:#6B7280;margin-top:2px}
  /* iframe 컨테이너 */
  iframe{border:none !important;display:block;}
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
    """인증 코드 → 액세스 토큰."""
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
        data = r.json()
        return data.get("access_token")
    except Exception as e:
        st.error(f"토큰 발급 실패: {e}")
        return None


def get_profile(access_token: str) -> dict | None:
    """액세스 토큰 → 사용자 프로필."""
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
# OAuth 콜백 처리 (네이버가 ?code=&state= 붙여 돌려보낼 때)
# ════════════════════════════════════════════════════════════

def handle_callback() -> None:
    qp        = st.query_params
    code      = qp.get("code")
    state     = qp.get("state")
    saved     = st.session_state.get("oauth_state")

    if not code or not state:
        return
    if st.session_state.get("logged_in"):   # 이미 처리됨
        st.query_params.clear()
        return
    if state != saved:
        st.error("⚠️ 보안 검증 실패. 다시 시도해 주세요.")
        st.query_params.clear()
        return

    with st.spinner("로그인 처리 중..."):
        token = get_access_token(code, state)
        if not token:
            st.query_params.clear()
            return
        profile = get_profile(token)
        if not profile:
            st.query_params.clear()
            return

    st.session_state["logged_in"]    = True
    st.session_state["user_profile"] = profile
    st.query_params.clear()
    st.rerun()


handle_callback()


# ════════════════════════════════════════════════════════════
# 화면 분기: 로그인 전 / 로그인 후
# ════════════════════════════════════════════════════════════

profile = st.session_state.get("user_profile")

# ── A. 로그인 완료 화면 ──────────────────────────────────────
if profile:
    nickname = profile.get("nickname") or profile.get("name", "사용자")
    email    = profile.get("email", "")
    img_url  = profile.get("profile_image", "")

    # 환영 배너
    img_tag = (f'<img src="{img_url}" '
               f'style="width:44px;height:44px;border-radius:50%;object-fit:cover">'
               if img_url else '<span style="font-size:32px">👤</span>')
    st.markdown(f"""
    <div class="welcome-bar">
      {img_tag}
      <div>
        <div class="welcome-name">환영합니다, {nickname}님 👋</div>
        <div class="welcome-email">{email}</div>
      </div>
    </div>
    """, unsafe_allow_html=True)

    # 로그아웃 버튼 — 네이버 서버 세션까지 삭제
    if st.button("로그아웃", key="logout"):
        st.session_state.clear()
        # 네이버 서버 세션 삭제 후 앱으로 복귀
        st.markdown(
            f'<meta http-equiv="refresh" content="0;url={LOGOUT_URL}?returl='
            f'{urllib.parse.quote(REDIRECT_URI, safe="")}">',
            unsafe_allow_html=True,
        )
        st.stop()

    # ── 계산기 (index.html) 렌더링 ──────────────────────────
    if not INDEX_PATH.exists():
        st.error(f"index.html 파일이 없습니다: {INDEX_PATH}")
        st.stop()

    html_code = INDEX_PATH.read_text(encoding="utf-8")

    # components.html 높이: ResizeObserver가 실제 높이를 부모에 보고하므로
    # 초기값을 넉넉하게 잡고 JS가 자동 조절함
    components.html(html_code, height=4000, scrolling=False)

# ── B. 로그인 전 화면 ─────────────────────────────────────────
else:
    # CSRF 방어 state 생성 (세션당 1회)
    if "oauth_state" not in st.session_state:
        st.session_state["oauth_state"] = secrets.token_urlsafe(16)

    auth_url = build_auth_url(st.session_state["oauth_state"])

    st.markdown("""
    <div style="text-align:center;padding:60px 20px 30px">
      <div style="font-size:2.2rem;font-weight:900;color:#1E293B;margin-bottom:8px">
        🏠 영집
      </div>
      <div style="font-size:1rem;color:#64748B;margin-bottom:32px">
        내 집 마련 계산기 · 주담대 한도 · 정책대출 진단
      </div>
    """, unsafe_allow_html=True)

    st.markdown(
        f'<a href="{auth_url}" class="naver-btn" target="_self">'
        f'<span class="naver-n">N</span>네이버 계정으로 시작하기</a>',
        unsafe_allow_html=True,
    )

    st.markdown("""
      <div style="font-size:11px;color:#94A3B8;margin-top:18px">
        로그인 후 모든 계산 기능을 무료로 이용할 수 있습니다.
      </div>
    </div>
    """, unsafe_allow_html=True)
