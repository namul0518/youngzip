"""
web_app.py — 네이버 소셜 로그인 통합
======================================
실행 전 준비:
  1) 같은 폴더에 .env 파일 생성 후 아래 두 줄 입력
     NAVER_CLIENT_ID=여기에_클라이언트_ID_입력
     NAVER_CLIENT_SECRET=여기에_클라이언트_시크릿_입력

  2) 네이버 개발자 센터 → 내 애플리케이션 → API 설정 탭
     Callback URL 에 반드시 등록:
     http://localhost:8501 (로컬 개발)
     https://your-domain.com (배포 시)

실행 명령:
  streamlit run web_app.py
"""

# ────────────────────────────────────────────────────────────
# IMPORT
# ────────────────────────────────────────────────────────────
import csv
import os
import secrets
from datetime import datetime
from pathlib import Path
from urllib.parse import urlencode

import requests
import streamlit as st
from dotenv import load_dotenv

# ════════════════════════════════════════════════════════════
# ★ 설정값 구획 ★
# .env 파일에서 로드 — 코드에 절대 직접 입력하지 마세요.
# ════════════════════════════════════════════════════════════
load_dotenv()

NAVER_CLIENT_ID     = os.getenv("NAVER_CLIENT_ID", "")
NAVER_CLIENT_SECRET = os.getenv("NAVER_CLIENT_SECRET", "")

# 네이버 로그인 후 돌아올 주소 (네이버 개발자 센터에 등록된 값과 일치해야 함)
REDIRECT_URI = "https://youngzip.streamlit.app"

# 로그인 데이터 저장 파일
LOGIN_DATA_FILE = Path(__file__).parent / "user_login_data.csv"

# ────────────────────────────────────────────────────────────
# 네이버 OAuth 상수
# ────────────────────────────────────────────────────────────
NAVER_AUTH_URL    = "https://nid.naver.com/oauth2.0/authorize"
NAVER_TOKEN_URL   = "https://nid.naver.com/oauth2.0/token"
NAVER_PROFILE_URL = "https://openapi.naver.com/v1/nid/me"

# ────────────────────────────────────────────────────────────
# 유틸 함수
# ────────────────────────────────────────────────────────────

def build_naver_auth_url(state: str) -> str:
    """네이버 인증 페이지 URL 생성."""
    params = {
        "response_type": "code",
        "client_id":     NAVER_CLIENT_ID,
        "redirect_uri":  REDIRECT_URI,
        "state":         state,
    }
    return f"{NAVER_AUTH_URL}?{urlencode(params)}"


def exchange_code_for_token(code: str, state: str) -> dict | None:
    """인증 코드 → 액세스 토큰 교환."""
    params = {
        "grant_type":    "authorization_code",
        "client_id":     NAVER_CLIENT_ID,
        "client_secret": NAVER_CLIENT_SECRET,
        "code":          code,
        "state":         state,
    }
    try:
        resp = requests.get(NAVER_TOKEN_URL, params=params, timeout=10)
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException as e:
        st.error(f"토큰 교환 실패: {e}")
        return None


def fetch_naver_profile(access_token: str) -> dict | None:
    """액세스 토큰 → 네이버 사용자 프로필 조회."""
    headers = {"Authorization": f"Bearer {access_token}"}
    try:
        resp = requests.get(NAVER_PROFILE_URL, headers=headers, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        if data.get("resultcode") == "00":
            return data.get("response", {})
        st.error(f"프로필 조회 오류: {data.get('message', '알 수 없음')}")
        return None
    except requests.RequestException as e:
        st.error(f"프로필 조회 실패: {e}")
        return None


def save_login_data(profile: dict) -> None:
    """
    로그인 성공 시 user_login_data.csv 에 사용자 정보 기록.
    파일이 없으면 헤더 포함하여 새로 생성.
    """
    fieldnames = ["timestamp", "naver_id", "name", "nickname",
                  "email", "profile_image", "mobile"]
    row = {
        "timestamp":     datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "naver_id":      profile.get("id", ""),
        "name":          profile.get("name", ""),
        "nickname":      profile.get("nickname", ""),
        "email":         profile.get("email", ""),
        "profile_image": profile.get("profile_image", ""),
        "mobile":        profile.get("mobile", ""),
    }
    file_exists = LOGIN_DATA_FILE.exists()
    with open(LOGIN_DATA_FILE, "a", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if not file_exists:
            writer.writeheader()
        writer.writerow(row)


def logout() -> None:
    """세션 초기화."""
    for key in ["user_profile", "oauth_state", "logged_in"]:
        st.session_state.pop(key, None)


# ────────────────────────────────────────────────────────────
# OAuth 콜백 처리 (URL 쿼리 파라미터 감지)
# ────────────────────────────────────────────────────────────

def handle_oauth_callback() -> None:
    """
    네이버가 Redirect URI 로 돌려보낸 code & state 를 처리.
    Streamlit은 쿼리 파라미터를 st.query_params 로 읽는다.
    """
    params     = st.query_params
    code       = params.get("code")
    state      = params.get("state")
    saved_state = st.session_state.get("oauth_state")

    if not code or not state:
        return

    # state 검증 (CSRF 방어)
    if state != saved_state:
        st.error("⚠️ 보안 검증 실패 (state 불일치). 다시 로그인해 주세요.")
        st.query_params.clear()
        return

    # 이미 처리됨
    if st.session_state.get("logged_in"):
        st.query_params.clear()
        return

    with st.spinner("로그인 처리 중..."):
        token_data = exchange_code_for_token(code, state)
        if not token_data or "access_token" not in token_data:
            st.error("토큰 발급 실패. 다시 시도해 주세요.")
            st.query_params.clear()
            return

        access_token = token_data["access_token"]
        profile = fetch_naver_profile(access_token)
        if not profile:
            st.query_params.clear()
            return

        # 세션 저장
        st.session_state["user_profile"] = profile
        st.session_state["logged_in"]    = True

        # CSV 기록
        save_login_data(profile)

    st.query_params.clear()
    st.rerun()


# ────────────────────────────────────────────────────────────
# 페이지 설정
# ────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="부동산 분석 엔진",
    page_icon="🏠",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
  .naver-btn{
    display:inline-flex;align-items:center;gap:10px;
    background:#03C75A;color:#fff;font-weight:800;font-size:15px;
    padding:12px 24px;border-radius:8px;text-decoration:none;
    box-shadow:0 2px 8px rgba(3,199,90,.35);transition:background .15s;
  }
  .naver-btn:hover{background:#02b050;color:#fff;}
  .naver-logo{width:22px;height:22px;background:#fff;border-radius:3px;
              display:flex;align-items:center;justify-content:center;
              font-weight:900;color:#03C75A;font-size:15px;flex-shrink:0;}
  .user-welcome{display:flex;align-items:center;gap:12px;
                background:#F0FDF4;border:1.5px solid #BBF7D0;
                border-radius:12px;padding:12px 16px;margin-bottom:16px;}
  .user-name{font-size:15px;font-weight:800;color:#065F46;}
  .user-sub{font-size:11px;color:#6B7280;margin-top:2px;}
  .logout-btn{margin-left:auto;font-size:11px;color:#94A3B8;
              cursor:pointer;text-decoration:underline;}
</style>
""", unsafe_allow_html=True)

# ────────────────────────────────────────────────────────────
# 설정값 검증
# ────────────────────────────────────────────────────────────
if not NAVER_CLIENT_ID or not NAVER_CLIENT_SECRET:
    st.error("⚠️ 네이버 API 키가 설정되지 않았습니다.")
    st.markdown("""
    **같은 폴더에 `.env` 파일을 만들고 아래 내용을 입력하세요:**
    ```
    NAVER_CLIENT_ID=여기에_클라이언트_ID_입력
    NAVER_CLIENT_SECRET=여기에_클라이언트_시크릿_입력
    ```
    저장 후 `streamlit run web_app.py` 로 재실행하세요.
    """)
    st.stop()

# ────────────────────────────────────────────────────────────
# OAuth 콜백 처리 (URL에 code가 붙어 돌아온 경우)
# ────────────────────────────────────────────────────────────
handle_oauth_callback()

# ────────────────────────────────────────────────────────────
# 로그인 상태 UI
# ────────────────────────────────────────────────────────────
profile = st.session_state.get("user_profile")

if profile:
    # ── 로그인 완료: 상단 환영 배너 ──────────────────────────
    nickname = profile.get("nickname") or profile.get("name", "사용자")
    img_url  = profile.get("profile_image", "")
    email    = profile.get("email", "")

    col_img, col_txt, col_out = st.columns([1, 8, 2])
    with col_img:
        if img_url:
            st.image(img_url, width=52)
        else:
            st.markdown("👤")
    with col_txt:
        st.markdown(
            f'<div class="user-name">환영합니다, {nickname}님 👋</div>'
            f'<div class="user-sub">{email}</div>',
            unsafe_allow_html=True,
        )
    with col_out:
        if st.button("로그아웃", key="logout_btn"):
            logout()
            st.rerun()

    st.markdown("---")

else:
    # ── 미로그인: 로그인 버튼 표시 ──────────────────────────
    st.markdown("### 🔐 네이버 로그인")
    st.caption("서비스 이용을 위해 네이버 계정으로 로그인해 주세요.")

    # CSRF 방어용 state 생성 (세션당 1회)
    if "oauth_state" not in st.session_state:
        st.session_state["oauth_state"] = secrets.token_urlsafe(16)

    auth_url = build_naver_auth_url(st.session_state["oauth_state"])

    st.markdown(
        f'<a href="{auth_url}" class="naver-btn" target="_self">'
        f'<span class="naver-logo">N</span>네이버로 로그인</a>',
        unsafe_allow_html=True,
    )
    st.markdown("---")

# ────────────────────────────────────────────────────────────
# 이하 기존 서비스 로직 (로그인 여부와 무관하게 표시)
# 로그인 필수로 만들려면 아래 블록을 else: 또는 if profile: 로 감싸세요.
# ────────────────────────────────────────────────────────────
st.markdown("## 🏠 부동산 분석 엔진")
st.caption("주담대 한도 계산 + 정책대출 자격 진단 + 맞춤 유형 추천")

# ↓ 여기에 기존 web_app.py 의 나머지 로직을 그대로 붙여넣으세요 ↓
st.info("기존 서비스 콘텐츠가 이 아래에 이어집니다.")
