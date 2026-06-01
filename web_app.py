import streamlit as st
import streamlit.components.v1 as components
from pathlib import Path
import secrets
import urllib.parse

# 1. 설정값 (본인 정보로 되어있는지 확인하세요)
CLIENT_ID = st.secrets["NAVER_CLIENT_ID"]
CLIENT_SECRET = st.secrets["NAVER_CLIENT_SECRET"]
REDIRECT_URI = "https://youngzip.streamlit.app"
INDEX_PATH = Path(__file__).parent / "index.html"

st.set_page_config(page_title="영끌내집", layout="centered", initial_sidebar_state="collapsed")

# 2. 네이버 로그인 URL 생성
auth_url = f"https://nid.naver.com/oauth2.0/authorize?response_type=code&client_id={CLIENT_ID}&redirect_uri={REDIRECT_URI}&state={secrets.token_urlsafe(16)}"

# 3. 로그인 처리 로직 (이건 그대로 두셔도 됩니다)
if "code" in st.query_params:
    st.session_state["logged_in"] = True
    st.rerun()

# 4. 화면 구성: 로그인 안 했으면 버튼 띄우고, 했으면 계산기 띄우기
if not st.session_state.get("logged_in"):
    st.markdown(f"""
        <div style="text-align:center; padding:50px 20px;">
            <h1 style="color:#1E293B;">🏠 영끌내집</h1>
            <p style="color:#64748B; margin-bottom:30px;">로그인 후 모든 계산 기능을 이용하세요.</p>
            <a href="{auth_url}" target="_top" style="
                display:inline-block; background:#03C75A; color:white; 
                padding:18px 40px; border-radius:12px; text-decoration:none; 
                font-weight:bold; font-size:18px; box-shadow: 0 4px 10px rgba(3,199,90,0.3);">
                네이버 계정으로 시작하기
            </a>
        </div>
    """, unsafe_allow_html=True)
else:
    # 로그인 성공 시 계산기 띄우기
    if st.button("로그아웃"):
        st.session_state["logged_in"] = False
        st.rerun()
    components.html(INDEX_PATH.read_text(encoding="utf-8"), height=900, scrolling=True)
