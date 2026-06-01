import streamlit as st
import streamlit.components.v1 as components
from pathlib import Path

# 설정
INDEX_PATH = Path(__file__).parent / "index.html"
st.set_page_config(page_title="영끌내집", layout="centered")

# 로그인 안 되어 있으면 로그인 버튼 띄우기 (target="_top" 덕분에 무조건 잘 뜹니다)
if not st.session_state.get("logged_in"):
    st.markdown(f"""
        <div style="text-align:center; padding:20px;">
            <a href="https://nid.naver.com/..." target="_top" style="background:#03C75A; color:white; padding:15px; border-radius:10px; text-decoration:none;">
                네이버 로그인
            </a>
        </div>
    """, unsafe_allow_html=True)

# 2. 계산기는 무조건 띄우기
html_raw = INDEX_PATH.read_text(encoding="utf-8")
components.html(html_raw, height=900, scrolling=True)
