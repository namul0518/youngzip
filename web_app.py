import streamlit as st
import streamlit.components.v1 as components
from pathlib import Path
import secrets

# 설정
INDEX_PATH = Path(__file__).parent / "index.html"
st.set_page_config(page_title="영끌내집", layout="centered", initial_sidebar_state="collapsed")

# 로그인 상태 관리
if "logged_in" not in st.session_state:
    st.session_state["logged_in"] = False

# 네이버 로그인 URL (임시)
auth_url = "https://nid.naver.com/oauth2.0/authorize?..." # 기존에 쓰던 URL 그대로 사용하세요

# 1. 상단 로그인 바 (로그인 안 했을 때만 표시)
if not st.session_state["logged_in"]:
    st.markdown(f"""
        <div style="background:#F0FDF4; padding:15px; border-radius:10px; text-align:center; margin-bottom:10px;">
            <a href="{auth_url}" target="_top" style="color:#03C75A; font-weight:bold; text-decoration:none;">
                🔒 정책대출/맞춤유형 이용을 위해 로그인하세요 →
            </a>
        </div>
    """, unsafe_allow_html=True)
else:
    if st.button("로그아웃"):
        st.session_state["logged_in"] = False
        st.rerun()

# 2. 계산기 띄우기 (이건 무조건 뜹니다!)
html_content = INDEX_PATH.read_text(encoding="utf-8")
components.html(html_content, height=900, scrolling=True)
