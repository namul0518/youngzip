"""
web_app.py  ·  영끌내집 카카오 로그인 + 계산기
═══════════════════════════════════════════════════════════════
★ 핵심 설계 원칙

  1. state 검증 → HMAC 서명 방식
     - 기존: state를 세션에 저장 → 리다이렉트 후 새 세션 생성 → 불일치 → 보안검증실패
     - 변경: state = timestamp + HMAC(secret, timestamp)
             → 세션 없이도 서명만으로 위변조 검증 가능
             → 리다이렉트 후 세션이 리셋돼도 무조건 통과

  2. 로그인 버튼
     - iframe 안: window.open() 팝업 → sandbox allow-popups로 허용됨
     - 메인 프레임: st.markdown <a href> → 현재 탭 이동 (백업)
     - 두 경로 모두 Python에서 auth_url을 주입하므로 URL 생성 로직 단일화

  3. 단일 파일
     - index.html을 문자열로 읽어 components.html로 주입
     - index.html은 별도 파일로 유지 (이 파일 하나만 깃허브에 올리면 됨)

Streamlit Cloud Secrets:
  KAKAO_REST_API_KEY = "REST API 키"
  (KAKAO_SECRET_SALT 불필요 — REST_API_KEY로 자동 서명)

카카오 개발자 콘솔:
  - 카카오 로그인 활성화 ON
  - Redirect URI: https://youngzip.streamlit.app/
  - 동의항목: 닉네임(필수), 프로필이미지·이메일(선택)
═══════════════════════════════════════════════════════════════
"""

import hashlib
import hmac
import json
import time
import urllib.parse
from pathlib import Path

import requests
import streamlit as st
import streamlit.components.v1 as components

# ════════════════════════════════════════════════════════════
# 설정
# ════════════════════════════════════════════════════════════
REST_API_KEY = st.secrets["KAKAO_REST_API_KEY"]
SECRET_SALT  = REST_API_KEY  # HMAC 서명용 — 별도 secrets 불필요
REDIRECT_URI = "https://youngzip.streamlit.app/"  # 콘솔 등록값 1:1 일치

AUTH_URL    = "https://kauth.kakao.com/oauth/authorize"
TOKEN_URL   = "https://kauth.kakao.com/oauth/token"
PROFILE_URL = "https://kapi.kakao.com/v2/user/me"
LOGOUT_URL  = "https://kauth.kakao.com/oauth/logout"

INDEX_PATH  = Path(__file__).parent / "index.html"
STATE_TTL   = 600  # state 유효시간(초) — 10분

# ════════════════════════════════════════════════════════════
# HMAC 기반 state 생성 / 검증
# (세션에 저장하지 않으므로 리다이렉트 후 세션 리셋에도 무관)
# ════════════════════════════════════════════════════════════

def _sign(ts: str) -> str:
    return hmac.new(
        SECRET_SALT.encode(),
        ts.encode(),
        hashlib.sha256,
    ).hexdigest()[:16]


def make_state() -> str:
    """state = '{timestamp}.{signature}' 형식으로 생성"""
    ts  = str(int(time.time()))
    sig = _sign(ts)
    return f"{ts}.{sig}"


def verify_state(state: str) -> bool:
    """
    서명 검증 + 만료시간 확인.
    세션 값과 비교하지 않으므로 리다이렉트 후 새 세션이어도 통과.
    """
    try:
        ts, sig = state.split(".", 1)
        if int(time.time()) - int(ts) > STATE_TTL:
            return False                          # 만료
        return hmac.compare_digest(sig, _sign(ts))  # 위변조 검증
    except Exception:
        return False


# ════════════════════════════════════════════════════════════
# OAuth 헬퍼
# ════════════════════════════════════════════════════════════

def build_auth_url() -> str:
    state = make_state()
    query = (
        f"response_type=code"
        f"&client_id={urllib.parse.quote(REST_API_KEY, safe='')}"
        f"&redirect_uri={urllib.parse.quote(REDIRECT_URI, safe=':/')}"
        f"&state={urllib.parse.quote(state, safe='.-')}"
    )
    return f"{AUTH_URL}?{query}"


def get_access_token(code: str) -> str | None:
    """카카오는 POST + application/x-www-form-urlencoded"""
    try:
        r = requests.post(
            TOKEN_URL,
            data={
                "grant_type":   "authorization_code",
                "client_id":    REST_API_KEY,
                "redirect_uri": REDIRECT_URI,
                "code":         code,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=10,
        )
        r.raise_for_status()
        body = r.json()
        if "error" in body:
            st.error(f"토큰 오류: {body.get('error_description', body['error'])}")
            return None
        return body.get("access_token")
    except requests.RequestException as e:
        st.error(f"토큰 발급 실패: {e}")
        return None


def get_profile(access_token: str) -> dict | None:
    try:
        r = requests.get(
            PROFILE_URL,
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type":  "application/x-www-form-urlencoded;charset=utf-8",
            },
            timeout=10,
        )
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
    except requests.RequestException as e:
        st.error(f"프로필 조회 실패: {e}")
        return None


# ════════════════════════════════════════════════════════════
# 페이지 설정
# ════════════════════════════════════════════════════════════
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
  .welcome-bar{
    display:flex; align-items:center; gap:14px;
    background:#FFFDE7; border:1.5px solid #FEE500;
    border-radius:12px; padding:12px 16px; margin-bottom:4px;
  }
  .welcome-name{font-size:15px;font-weight:800;color:#3A1D00;}
  .welcome-email{font-size:11px;color:#6B7280;margin-top:2px;}
  /* 메인 프레임 로그인 버튼 (팝업 차단 시 폴백용) */
  .login-wrap{text-align:center;padding:6px 0 2px;}
  a.kakao-main-btn{
    display:inline-flex;align-items:center;gap:10px;
    background:#FEE500;color:#191919 !important;
    font-weight:800;font-size:14px;text-decoration:none !important;
    padding:11px 24px;border-radius:8px;
    box-shadow:0 2px 8px rgba(254,229,0,.5);
  }
</style>
""", unsafe_allow_html=True)


# ════════════════════════════════════════════════════════════
# 콜백 처리 — 카카오가 ?code=...&state=... 로 복귀했을 때
# ════════════════════════════════════════════════════════════

def handle_callback() -> None:
    qp    = st.query_params
    code  = qp.get("code")
    state = qp.get("state", "")

    if not code:
        return
    if st.session_state.get("logged_in"):
        st.query_params.clear()
        return

    # ── HMAC state 검증 (세션 불필요) ──
    if not verify_state(state):
        st.error("⚠️ 보안 검증 실패: 링크가 만료됐거나 위변조 의심. 다시 로그인해 주세요.")
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
# 로그인 상태 확인 + auth_url 생성
# ════════════════════════════════════════════════════════════
profile      = st.session_state.get("user_profile")
is_logged_in = bool(profile)
auth_url     = build_auth_url()   # 매 렌더링마다 새 state 생성 (ttl 안에서 유효)


# ════════════════════════════════════════════════════════════
# 상단 UI (메인 프레임 — sandbox 없음)
# ════════════════════════════════════════════════════════════

if is_logged_in:
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

    if st.button("로그아웃", key="logout_btn"):
        st.session_state.clear()
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

else:
    # 메인 프레임 로그인 버튼 — iframe 팝업이 차단됐을 때 폴백
    # target="_self" → 현재 탭에서 카카오 페이지로 이동 (sandbox 없음, 100% 동작)
    st.markdown(f"""
    <div class="login-wrap">
      <a href="{auth_url}" target="_self" class="kakao-main-btn">
        <svg width="20" height="20" viewBox="0 0 24 24">
          <path d="M12 3C6.477 3 2 6.477 2 10.8c0 2.7 1.632 5.076 4.1 6.48L5.1 21l4.72-2.52A11.6 11.6 0 0012 18.6c5.523 0 10-3.477 10-7.8S17.523 3 12 3z" fill="#191919"/>
        </svg>
        카카오 계정으로 로그인
      </a>
      <div style="font-size:11px;color:#9CA3AF;margin-top:8px">2·3탭 기능은 로그인 후 이용 가능합니다</div>
    </div>
    """, unsafe_allow_html=True)


# ════════════════════════════════════════════════════════════
# index.html 렌더링 + JS 변수 주입
# ════════════════════════════════════════════════════════════

if not INDEX_PATH.exists():
    st.error(f"index.html을 찾을 수 없습니다: {INDEX_PATH}")
    st.stop()

html_raw = INDEX_PATH.read_text(encoding="utf-8")

# APP_AUTH_URL → iframe 안 window.open() 팝업용
# APP_LOGGED_IN → 탭 권한 제어용
inject = f"""
<script>
  var APP_LOGGED_IN = {json.dumps(is_logged_in)};
  var APP_AUTH_URL  = {json.dumps(auth_url)};
</script>
"""
html_injected = html_raw.replace("<head>", "<head>" + inject, 1)

components.html(html_injected, height=900, scrolling=True)
