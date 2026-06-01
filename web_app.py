import streamlit as st
import streamlit.components.v1 as components
from pathlib import Path
import secrets

# 1. 설정
INDEX_PATH = Path(__file__).parent / "index.html"
CLIENT_ID = st.secrets["NAVER_CLIENT_ID"]
REDIRECT_URI = "https://youngzip.streamlit.app"
auth_url = f"https://nid.naver.com/oauth2.0/authorize?response_type=code&client_id={CLIENT_ID}&redirect_uri={REDIRECT_URI}&state={secrets.token_urlsafe(16)}"

st.set_page_config(page_title="영끌내집", layout="centered")

# 2. 로그인 처리 (로그인 버튼을 누르고 돌아왔을 때)
if "code" in st.query_params:
    st.session_state["logged_in"] = True
    st.rerun()

# 3. 화면 구성: 로그인 안 했으면 로그인 버튼 띄우기
if not st.session_state.get("logged_in"):
    st.markdown(f"""
        <div style="text-align:center; padding:20px; background:#F0FDF4; border-radius:10px; margin-bottom:10px;">
            <a href="{auth_url}" target="_top" style="color:#03C75A; font-weight:bold; text-decoration:none; font-size:16px;">
                🔒 정책대출·맞춤유형 이용을 위해 로그인하세요 (클릭)
            </a>
        </div>
    """, unsafe_allow_html=True)
else:
    if st.button("로그아웃"):
        st.session_state["logged_in"] = False
        st.rerun()

# 4. 계산기 띄우기 (무조건 보임)
html_content = INDEX_PATH.read_text(encoding="utf-8")
components.html(html_content, height=900, scrolling=True)
