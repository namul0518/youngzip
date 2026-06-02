"""
streamlit_app.py  ·  영끌내집 계산기 UI
═══════════════════════════════════════════════════════════════
역할:
  - 로그인 버튼 → FastAPI /login/kakao 또는 /login/naver 로 이동
  - 콜백 후 URL ?token=JWT 수신 → /me API로 유저 정보 확인
  - 계산기 (index.html → components.html)
  - 탭 권한 제어 (APP_LOGGED_IN JS 변수 주입)

환경변수:
  FASTAPI_URL  ← FastAPI 서버 주소 ex: https://xxx.up.railway.app
                 로컬 개발 시: http://localhost:8000
═══════════════════════════════════════════════════════════════
"""

import json
import os
from pathlib import Path

import httpx
import streamlit as st
import streamlit.components.v1 as components

# ════════════════════════════════════════════════════════════
# 설정
# ════════════════════════════════════════════════════════════
FASTAPI_URL  = os.environ.get("FASTAPI_URL", "http://localhost:8000").rstrip("/")
KAKAO_LOGIN  = f"{FASTAPI_URL}/login/kakao"
NAVER_LOGIN  = f"{FASTAPI_URL}/login/naver"

CALCULATOR   = Path(__file__).parent / "static" / "calculator.html"

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

  /* 로그인 버튼 영역 */
  .login-wrap{
    display:flex; gap:10px; justify-content:center;
    padding:6px 0 2px; flex-wrap:wrap;
  }
  a.kakao-btn{
    display:inline-flex; align-items:center; gap:8px;
    background:#FEE500; color:#191919 !important;
    font-weight:800; font-size:14px; text-decoration:none !important;
    padding:11px 22px; border-radius:8px;
    box-shadow:0 2px 8px rgba(254,229,0,.45);
  }
  a.naver-btn{
    display:inline-flex; align-items:center; gap:8px;
    background:#03C75A; color:#fff !important;
    font-weight:800; font-size:14px; text-decoration:none !important;
    padding:11px 22px; border-radius:8px;
    box-shadow:0 2px 8px rgba(3,199,90,.35);
  }
  .naver-n{
    width:20px; height:20px; background:#fff; border-radius:3px;
    display:inline-flex; align-items:center; justify-content:center;
    font-weight:900; color:#03C75A; font-size:13px; flex-shrink:0;
  }

  /* 환영 배너 */
  .welcome-bar{
    display:flex; align-items:center; gap:12px;
    background:#F0F9FF; border:1.5px solid #BAE6FD;
    border-radius:12px; padding:10px 14px; margin-bottom:4px;
  }
  .welcome-name{font-size:14px; font-weight:800; color:#0C4A6E;}
  .welcome-sub{font-size:11px; color:#6B7280; margin-top:1px;}

  /* 에러 배너 */
  .err-bar{
    background:#FEF2F2; border:1px solid #FECACA;
    border-radius:10px; padding:10px 14px;
    font-size:13px; color:#991B1B; margin-bottom:6px;
  }
</style>
""", unsafe_allow_html=True)


# ════════════════════════════════════════════════════════════
# ?token=JWT 콜백 처리
# FastAPI가 로그인 성공 후 Streamlit URL에 ?token=XXX 붙여서 리다이렉트
# ════════════════════════════════════════════════════════════

def handle_token_callback() -> None:
    token       = st.query_params.get("token")
    login_error = st.query_params.get("login_error")

    # 에러 처리
    if login_error:
        st.query_params.clear()
        err_map = {
            "state_mismatch": "보안 검증 실패. 다시 시도해 주세요.",
            "token_fail":     "인증 서버 오류. 잠시 후 다시 시도해 주세요.",
            "profile_fail":   "프로필 조회 실패. 잠시 후 다시 시도해 주세요.",
        }
        st.session_state["login_error"] = err_map.get(login_error, f"로그인 오류: {login_error}")
        return

    if not token:
        return
    if st.session_state.get("logged_in"):
        st.query_params.clear()
        return

    # FastAPI /me 로 토큰 검증 + 유저 정보 수신
    try:
        r = httpx.get(f"{FASTAPI_URL}/me", params={"token": token}, timeout=10)
        if r.status_code == 200:
            profile = r.json()
            st.session_state.update({
                "logged_in":    True,
                "user_profile": profile,
                "jwt_token":    token,
            })
            st.session_state.pop("login_error", None)
        else:
            st.session_state["login_error"] = "토큰 검증 실패. 다시 로그인해 주세요."
    except Exception as e:
        st.session_state["login_error"] = f"서버 연결 실패: {e}"

    st.query_params.clear()
    st.rerun()


handle_token_callback()

# ════════════════════════════════════════════════════════════
# 로그인 상태
# ════════════════════════════════════════════════════════════
profile      = st.session_state.get("user_profile")
is_logged_in = bool(profile)
login_error  = st.session_state.get("login_error")


# ════════════════════════════════════════════════════════════
# 상단 UI
# ════════════════════════════════════════════════════════════

# 에러 배너
if login_error:
    st.markdown(f'<div class="err-bar">⚠️ {login_error}</div>',
                unsafe_allow_html=True)

if is_logged_in:
    # 환영 배너
    nickname  = profile.get("nickname") or "사용자"
    email     = profile.get("email", "")
    img_url   = profile.get("profile_image", "")
    provider  = profile.get("provider", "")
    provider_badge = "🟡 카카오" if provider == "kakao" else "🟢 네이버"

    img_tag = (
        f'<img src="{img_url}" '
        'style="width:38px;height:38px;border-radius:50%;object-fit:cover;flex-shrink:0">'
        if img_url else '<span style="font-size:26px">👤</span>'
    )
    st.markdown(f"""
    <div class="welcome-bar">
      {img_tag}
      <div>
        <div class="welcome-name">환영합니다, {nickname}님 👋</div>
        <div class="welcome-sub">{provider_badge} &nbsp;{email}</div>
      </div>
    </div>""", unsafe_allow_html=True)

    if st.button("로그아웃", key="logout_btn"):
        st.session_state.clear()
        st.rerun()

else:
    # 로그인 버튼 2개 — FastAPI 서버로 직접 이동 (OAuth 처리는 FastAPI 담당)
    # target="_self" → 현재 탭 이동, sandbox 없음, 100% 동작 보장
    st.markdown(f"""
    <div class="login-wrap">
      <a href="{KAKAO_LOGIN}" target="_self" class="kakao-btn">
        <svg width="20" height="20" viewBox="0 0 24 24">
          <path d="M12 3C6.477 3 2 6.477 2 10.8c0 2.7 1.632 5.076 4.1 6.48L5.1 21l4.72-2.52A11.6 11.6 0 0012 18.6c5.523 0 10-3.477 10-7.8S17.523 3 12 3z" fill="#191919"/>
        </svg>
        카카오 로그인
      </a>
      <a href="{NAVER_LOGIN}" target="_self" class="naver-btn">
        <span class="naver-n">N</span>
        네이버 로그인
      </a>
    </div>
    <div style="text-align:center;font-size:11px;color:#9CA3AF;margin-top:6px;margin-bottom:2px">
      2·3탭 기능은 로그인 후 이용 가능합니다
    </div>
    """, unsafe_allow_html=True)


# ════════════════════════════════════════════════════════════
# 계산기 렌더링
# APP_LOGGED_IN / APP_AUTH_URL 주입 → 탭 권한 제어
# APP_AUTH_URL은 더 이상 iframe 안에서 사용 안 함 (빈값)
# ════════════════════════════════════════════════════════════

if not CALCULATOR.exists():
    st.error(f"calculator.html을 찾을 수 없습니다: {CALCULATOR}")
    st.stop()

html_raw = CALCULATOR.read_text(encoding="utf-8")

inject = f"""
<script>
  var APP_LOGGED_IN = {json.dumps(is_logged_in)};
  var APP_AUTH_URL  = '';  /* 로그인은 메인 프레임 버튼으로만 처리 */
</script>
"""
html_injected = html_raw.replace("<head>", "<head>" + inject, 1)
components.html(html_injected, height=900, scrolling=True)
